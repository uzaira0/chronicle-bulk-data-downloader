from __future__ import annotations

import asyncio
import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import aiofiles
import httpx
import regex as re

from chronicle_bulk_data_downloader.constants import (
    CONNECTION_TIMEOUT,
    MAX_RETRIES,
    RATE_LIMIT_DELAY,
    REQUEST_TIMEOUT,
)

if TYPE_CHECKING:
    import polars as pl
else:
    try:
        import polars as pl
    except ImportError:
        pl = None

from chronicle_bulk_data_downloader.enums import (
    ChronicleDeviceType,
    ChronicleDownloadDataType,
    OutputFormat,
)
from chronicle_bulk_data_downloader.utils import (
    get_local_timezone,
    get_matching_files_from_folder,
)

from .callbacks import CancellationCheck, ProgressCallback
from .config import DateRangeConfig, DownloadConfig, FilePatterns
from .exceptions import (
    AuthenticationError,
    ChronicleAPIError,
    DownloadCancelledError,
    NoParticipantsError,
)

LOGGER = logging.getLogger(__name__)


class ChronicleDownloader:
    """
    Core downloader for Chronicle bulk data.

    This class handles all business logic for downloading data from Chronicle API,
    including authentication, participant filtering, data retrieval, file organization,
    and archiving. It is completely independent of any GUI framework.
    """

    def __init__(
        self,
        config: DownloadConfig,
        progress_callback: ProgressCallback | None = None,
        cancellation_check: CancellationCheck | None = None,
    ):
        """
        Initialize the Chronicle downloader.

        Args:
            config: Complete download configuration
            progress_callback: Optional callback for progress updates
            cancellation_check: Optional callback to check if download should be cancelled
        """
        self.config = config
        self.progress_callback = progress_callback
        self.cancellation_check = cancellation_check

        self.file_patterns = FilePatterns()
        self._http_client: httpx.AsyncClient | None = None
        self._client_lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(1)

    async def _get_client(self) -> httpx.AsyncClient:
        """
        Gets or creates an HTTP client with proper configuration.

        Returns:
            Configured async HTTP client
        """
        async with self._client_lock:
            if self._http_client is None or self._http_client.is_closed:
                LOGGER.debug("Creating new HTTP client")
                self._http_client = httpx.AsyncClient(
                    http2=True,
                    timeout=httpx.Timeout(
                        timeout=CONNECTION_TIMEOUT, read=REQUEST_TIMEOUT
                    ),
                    limits=httpx.Limits(
                        max_keepalive_connections=1,
                        max_connections=1,
                        keepalive_expiry=CONNECTION_TIMEOUT,
                    ),
                    follow_redirects=True,
                )
            return self._http_client

    async def _close_client(self) -> None:
        """Safely closes the HTTP client if it exists."""
        async with self._client_lock:
            if self._http_client is not None and not self._http_client.is_closed:
                try:
                    await self._http_client.aclose()
                    LOGGER.debug("HTTP client closed successfully")
                finally:
                    self._http_client = None

    def _is_cancelled(self) -> bool:
        """
        Check if download should be cancelled.

        Returns:
            True if cancelled, False otherwise
        """
        if self.cancellation_check is not None:
            return self.cancellation_check()
        return False

    def _update_progress(
        self,
        progress_percent: int,
        completed_files: int | None = None,
        total_files: int | None = None,
    ) -> None:
        """
        Update progress via callback if available.

        Args:
            progress_percent: Progress percentage (0-100)
            completed_files: Number of files completed
            total_files: Total number of files
        """
        if self.progress_callback is not None:
            self.progress_callback(progress_percent, completed_files, total_files)

    async def get_participants(self) -> list[str]:
        """
        Retrieve list of participant IDs from Chronicle API.

        Returns:
            List of participant IDs

        Raises:
            AuthenticationError: If authentication fails
            ChronicleAPIError: If API request fails
            DownloadCancelledError: If download is cancelled
        """
        if self._is_cancelled():
            raise DownloadCancelledError()

        try:
            client = await self._get_client()
            response = await client.get(
                f"https://api.getmethodic.com/chronicle/v3/study/{self.config.auth.study_id}/participants/stats",
                headers={"Authorization": f"Bearer {self.config.auth.auth_token}"},
                timeout=REQUEST_TIMEOUT,
            )
            response.raise_for_status()

            participant_data = response.json()
            participant_ids = [
                item["participantId"] for item in participant_data.values()
            ]

            LOGGER.debug(f"Retrieved {len(participant_ids)} participant IDs")
            return participant_ids

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                raise AuthenticationError()
            elif e.response.status_code == 403:
                raise ChronicleAPIError(403, "Forbidden")
            elif e.response.status_code == 404:
                raise ChronicleAPIError(404, "Not Found")
            else:
                raise ChronicleAPIError(e.response.status_code, str(e))

    async def get_enrolled_device_ids(self) -> list[str]:
        """
        Get all enrolled device IDs from Chronicle API.

        This is an alias for get_participants() that provides a more descriptive name
        for the pipeline context where we're working with device-level data.

        Returns:
            List of device/participant IDs enrolled in the study

        Raises:
            AuthenticationError: If authentication fails
            ChronicleAPIError: If API request fails
        """
        return await self.get_participants()

    async def fetch_data_type(
        self,
        device_ids: list[str],
        data_type: ChronicleDownloadDataType,
        output_format: OutputFormat = OutputFormat.DATAFRAME,
    ) -> "pl.DataFrame":
        """
        Fetch data for a specific data type for multiple devices, returning a DataFrame.

        This method downloads data directly to memory without writing intermediate files,
        making it suitable for pipeline use where data flows in-memory to Delta Lake.

        Args:
            device_ids: List of device IDs to download data for
            data_type: Type of data to download (RAW, SURVEY, etc.)
            output_format: Output format (currently only DATAFRAME is supported)

        Returns:
            Polars DataFrame containing all downloaded data with a participant_id column

        Raises:
            AuthenticationError: If authentication fails
            ChronicleAPIError: If API request fails
            ValueError: If output_format is not DATAFRAME
        """
        if pl is None:
            raise ImportError("polars is required for DataFrame output. Install with: pip install polars")

        if output_format != OutputFormat.DATAFRAME:
            msg = f"Only DATAFRAME output format is currently supported, got {output_format}"
            raise ValueError(msg)

        if not device_ids:
            LOGGER.debug("No device IDs provided, returning empty DataFrame")
            return pl.DataFrame()

        all_data: list[pl.DataFrame] = []

        for i, device_id in enumerate(device_ids):
            if self._is_cancelled():
                raise DownloadCancelledError()

            try:
                df = await self._fetch_device_data_to_dataframe(device_id, data_type)
                if df is not None and len(df) > 0:
                    all_data.append(df)

                # Update progress
                progress = int(((i + 1) / len(device_ids)) * 100)
                self._update_progress(progress, i + 1, len(device_ids))

            except Exception as e:
                LOGGER.warning(f"Failed to fetch {data_type} for {device_id}: {e}")
                # Continue with next device instead of failing entirely
                continue

        if not all_data:
            LOGGER.debug(f"No {data_type} data found for any devices")
            return pl.DataFrame()

        # Concatenate all DataFrames
        result = pl.concat(all_data, how="diagonal")
        LOGGER.info(f"Fetched {len(result)} total rows for {data_type}")
        return result

    async def _fetch_device_data_to_dataframe(
        self,
        device_id: str,
        data_type: ChronicleDownloadDataType,
        retry_count: int = 0,
    ) -> pl.DataFrame | None:
        """
        Fetch data for a single device and return as DataFrame.

        Args:
            device_id: Device ID to fetch data for
            data_type: Type of data to fetch
            retry_count: Current retry attempt number

        Returns:
            DataFrame containing the fetched data, or None if no data

        Raises:
            ChronicleAPIError: If API request fails after retries
        """
        url, data_type_str, _ = self._build_download_url(
            device_id, data_type, self.config.date_range
        )

        try:
            async with self._semaphore:
                client = await self._get_client()

                if client.is_closed:
                    LOGGER.warning("Client was closed, creating a new one")
                    client = await self._get_client()

                response = await client.get(
                    url,
                    headers={"Authorization": f"Bearer {self.config.auth.auth_token}"},
                    timeout=REQUEST_TIMEOUT,
                )
                response.raise_for_status()

            # Parse CSV content to DataFrame
            csv_content = response.content.decode("utf-8")
            if not csv_content.strip():
                LOGGER.debug(f"No {data_type_str} data for {device_id}")
                return None

            # Read CSV to DataFrame
            from io import StringIO

            df = pl.read_csv(StringIO(csv_content))

            # Add participant_id column if not present
            if "participant_id" not in df.columns:
                df = df.with_columns(pl.lit(device_id).alias("participant_id"))

            LOGGER.debug(f"Fetched {len(df)} rows of {data_type_str} for {device_id}")

            await asyncio.sleep(RATE_LIMIT_DELAY)
            return df

        except httpx.HTTPStatusError as e:
            error_code = e.response.status_code
            if error_code in (429, 502, 503, 504) and retry_count < MAX_RETRIES:
                retry_delay = (2**retry_count) * RATE_LIMIT_DELAY
                LOGGER.warning(
                    f"HTTP {error_code} error, retrying in {retry_delay}s (attempt {retry_count + 1}/{MAX_RETRIES})"
                )
                await asyncio.sleep(retry_delay)
                return await self._fetch_device_data_to_dataframe(
                    device_id, data_type, retry_count + 1
                )
            else:
                LOGGER.error(
                    f"HTTP error {error_code} when fetching {data_type_str} for {device_id}"
                )
                raise ChronicleAPIError(
                    error_code, f"Failed to fetch {data_type_str}"
                )

        except httpx.RequestError as e:
            if retry_count < MAX_RETRIES:
                retry_delay = (2**retry_count) * RATE_LIMIT_DELAY
                LOGGER.warning(
                    f"Request error: {e}, retrying in {retry_delay}s (attempt {retry_count + 1}/{MAX_RETRIES})"
                )
                await self._close_client()
                await asyncio.sleep(retry_delay)
                return await self._fetch_device_data_to_dataframe(
                    device_id, data_type, retry_count + 1
                )
            else:
                LOGGER.error(
                    f"Request error when fetching {data_type_str} for {device_id}: {e}"
                )
                raise ChronicleAPIError(0, f"Network error: {e}")

    def filter_participants(self, participant_ids: list[str]) -> list[str]:
        """
        Filter participant IDs based on configuration.

        Args:
            participant_ids: List of all participant IDs

        Returns:
            Filtered list of participant IDs

        Raises:
            NoParticipantsError: If no participants remain after filtering
        """
        cleaned_participant_ids = [
            pid.strip() for pid in participant_ids if pid.strip()
        ]
        filter_list = [
            pid.strip()
            for pid in self.config.filter_config.participant_ids
            if pid.strip()
        ]

        if not filter_list:
            filtered = cleaned_participant_ids
        elif self.config.filter_config.inclusive:
            LOGGER.debug("Using inclusive filter for participant ID list")
            filtered = self._inclusive_filter(cleaned_participant_ids, filter_list)
        else:
            LOGGER.debug("Using exclusive filter for participant ID list")
            filtered = self._exclusive_filter(cleaned_participant_ids, filter_list)

        filtered.sort()

        if not filtered:
            raise NoParticipantsError(
                "No participant IDs with data available to download were found after filtering. "
                "Please double check your filter and/or participants in your study on the Chronicle website."
            )

        LOGGER.debug(f"Filtered to {len(filtered)} participants")
        return filtered

    def _exclusive_filter(
        self, participant_ids: list[str], exclude_list: list[str]
    ) -> list[str]:
        """
        Filter participant IDs using exclusive filter.

        Args:
            participant_ids: List of all participant IDs
            exclude_list: List of IDs to exclude

        Returns:
            Filtered list
        """
        return [
            pid
            for pid in participant_ids
            if pid is not None
            and not any(excluded.lower() in pid.lower() for excluded in exclude_list)
        ]

    def _inclusive_filter(
        self, participant_ids: list[str], include_list: list[str]
    ) -> list[str]:
        """
        Filter participant IDs using inclusive filter.

        Args:
            participant_ids: List of all participant IDs
            include_list: List of IDs to include

        Returns:
            Filtered list
        """
        return [
            pid
            for pid in participant_ids
            if pid is not None
            and (
                pid in include_list
                or any(pid.lower() == included.lower() for included in include_list)
            )
        ]

    def _build_download_url(
        self,
        participant_id: str,
        data_type: ChronicleDownloadDataType,
        date_range: DateRangeConfig | None = None,
    ) -> tuple[str, str, ChronicleDeviceType | None]:
        """
        Build the download URL for a participant and data type.

        Args:
            participant_id: Participant ID
            data_type: Type of data to download
            date_range: Optional date range for filtering

        Returns:
            Tuple of (url, data_type_str, chronicle_device_type)
        """
        base_study_url = f"https://api.getmethodic.com/chronicle/v3/study/{self.config.auth.study_id}/participants/data"
        base_tud_url = f"https://api.getmethodic.com/chronicle/v3/time-use-diary/{self.config.auth.study_id}/participants/data"

        chronicle_device_type: ChronicleDeviceType | None = None

        match data_type:
            case ChronicleDownloadDataType.RAW:
                data_type_str = "Raw Data"
                base_url = base_study_url
                chronicle_device_type = ChronicleDeviceType.ANDROID
            case ChronicleDownloadDataType.PREPROCESSED:
                data_type_str = "Downloaded Preprocessed Data"
                base_url = base_study_url
                chronicle_device_type = ChronicleDeviceType.ANDROID
            case ChronicleDownloadDataType.SURVEY:
                data_type_str = "Survey Data"
                base_url = base_study_url
                chronicle_device_type = ChronicleDeviceType.ANDROID
            case ChronicleDownloadDataType.IOSSENSOR:
                data_type_str = "IOSSensor Data"
                base_url = base_study_url
                chronicle_device_type = ChronicleDeviceType.IPHONE
            case ChronicleDownloadDataType.TIME_USE_DIARY_DAYTIME:
                data_type_str = "Time Use Diary Daytime Data"
                base_url = base_tud_url
            case ChronicleDownloadDataType.TIME_USE_DIARY_NIGHTTIME:
                data_type_str = "Time Use Diary Nighttime Data"
                base_url = base_tud_url
            case ChronicleDownloadDataType.TIME_USE_DIARY_SUMMARIZED:
                data_type_str = "Time Use Diary Summarized Data"
                base_url = base_tud_url
            case _:
                msg = f"Unrecognized Chronicle data download type {data_type}"
                raise ValueError(msg)

        # Build query parameters
        params = [f"participantId={participant_id}", f"dataType={data_type}"]

        # Add fileType for study data endpoints (not TUD)
        if base_url == base_study_url:
            params.append("fileType=csv")

        # Add date range parameters if provided
        if date_range is not None:
            date_params = date_range.to_api_params()
            for key, value in date_params.items():
                params.append(f"{key}={value}")

        url = f"{base_url}?{'&'.join(params)}"
        return url, data_type_str, chronicle_device_type

    async def _download_participant_data_type(
        self,
        participant_id: str,
        data_type: ChronicleDownloadDataType,
        retry_count: int = 0,
    ) -> bool:
        """
        Download data of a specific type for a participant.

        Args:
            participant_id: Participant ID to download data for
            data_type: Type of data to download
            retry_count: Current retry attempt number

        Returns:
            True if successful, False if cancelled

        Raises:
            DownloadCancelledError: If download is cancelled
            ChronicleAPIError: If API request fails after retries
        """
        if self._is_cancelled():
            LOGGER.debug(f"Download cancelled for {participant_id}, {data_type}")
            raise DownloadCancelledError()

        # Build URL with optional date range parameters from config
        url, data_type_str, chronicle_device_type = self._build_download_url(
            participant_id, data_type, self.config.date_range
        )

        if self.config.date_range is not None:
            LOGGER.debug(
                f"Downloading {data_type_str} for {participant_id} "
                f"(date range: {self.config.date_range.start_date} to {self.config.date_range.end_date})"
            )

        try:
            async with self._semaphore:
                if self._is_cancelled():
                    raise DownloadCancelledError()

                client = await self._get_client()

                if client.is_closed:
                    LOGGER.warning("Client was closed, creating a new one")
                    client = await self._get_client()

                csv_response = await client.get(
                    url,
                    headers={"Authorization": f"Bearer {self.config.auth.auth_token}"},
                    timeout=REQUEST_TIMEOUT,
                )
                csv_response.raise_for_status()

            output_filepath = (
                self.config.download_folder
                / f"{participant_id} Chronicle{f' {chronicle_device_type.value}' if chronicle_device_type is not None else ''} {data_type_str} {datetime.now(get_local_timezone()).strftime('%m-%d-%Y')}.csv"
            )
            output_filepath.parent.mkdir(parents=True, exist_ok=True)

            async with aiofiles.open(output_filepath, "wb") as f:
                await f.write(csv_response.content)

            LOGGER.debug(f"Downloaded {data_type_str} for participant {participant_id}")

            await asyncio.sleep(RATE_LIMIT_DELAY)
            return True

        except httpx.HTTPStatusError as e:
            error_code = e.response.status_code
            if error_code in (429, 502, 503, 504) and retry_count < MAX_RETRIES:
                retry_delay = (2**retry_count) * RATE_LIMIT_DELAY
                LOGGER.warning(
                    f"HTTP {error_code} error, retrying in {retry_delay}s (attempt {retry_count + 1}/{MAX_RETRIES})"
                )
                await asyncio.sleep(retry_delay)
                return await self._download_participant_data_type(
                    participant_id, data_type, retry_count + 1
                )
            else:
                LOGGER.exception(
                    f"HTTP error {error_code} when downloading {data_type_str} for {participant_id}"
                )
                raise ChronicleAPIError(
                    error_code, f"Failed to download {data_type_str}"
                )

        except httpx.RequestError as e:
            if retry_count < MAX_RETRIES:
                retry_delay = (2**retry_count) * RATE_LIMIT_DELAY
                LOGGER.warning(
                    f"Request error: {e}, retrying in {retry_delay}s (attempt {retry_count + 1}/{MAX_RETRIES})"
                )

                await self._close_client()

                await asyncio.sleep(retry_delay)
                return await self._download_participant_data_type(
                    participant_id, data_type, retry_count + 1
                )
            else:
                LOGGER.exception(
                    f"Request error when downloading {data_type_str} for {participant_id}: {e}"
                )
                raise ChronicleAPIError(0, f"Network error: {e}")

    async def download_all(self) -> None:
        """
        Download all configured data types for all participants.

        This is the main orchestration method that coordinates the entire download process.

        Raises:
            DownloadCancelledError: If download is cancelled
            AuthenticationError: If authentication fails
            NoParticipantsError: If no participants found after filtering
            ChronicleAPIError: If API requests fail
        """
        try:
            self._update_progress(5)

            participant_ids = await self.get_participants()
            filtered_participants = self.filter_participants(participant_ids)

            total_data_types = sum(
                [
                    self.config.data_types.download_raw,
                    self.config.data_types.download_preprocessed,
                    self.config.data_types.download_survey,
                    self.config.data_types.download_ios_sensor,
                    self.config.data_types.download_time_use_diary_daytime,
                    self.config.data_types.download_time_use_diary_nighttime,
                    self.config.data_types.download_time_use_diary_summarized,
                ]
            )

            total_downloads = len(filtered_participants) * total_data_types
            downloads_completed = 0
            self._update_progress(10, downloads_completed, total_downloads)

            for i, participant_id in enumerate(filtered_participants):
                if self._is_cancelled():
                    LOGGER.info("Download process cancelled by user")
                    raise DownloadCancelledError()

                if self.config.data_types.download_raw:
                    success = await self._download_participant_data_type(
                        participant_id, ChronicleDownloadDataType.RAW
                    )
                    if success:
                        downloads_completed += 1
                        progress_value = 10 + int(
                            (downloads_completed / total_downloads) * 80
                        )
                        self._update_progress(
                            progress_value, downloads_completed, total_downloads
                        )
                        LOGGER.debug(
                            f"Finished downloading {ChronicleDownloadDataType.RAW} data for device {participant_id} ({i + 1}/{len(filtered_participants)})"
                        )

                if self._is_cancelled():
                    raise DownloadCancelledError()

                if self.config.data_types.download_preprocessed:
                    success = await self._download_participant_data_type(
                        participant_id, ChronicleDownloadDataType.PREPROCESSED
                    )
                    if success:
                        downloads_completed += 1
                        progress_value = 10 + int(
                            (downloads_completed / total_downloads) * 80
                        )
                        self._update_progress(
                            progress_value, downloads_completed, total_downloads
                        )
                        LOGGER.debug(
                            f"Finished downloading {ChronicleDownloadDataType.PREPROCESSED} data for device {participant_id} ({i + 1}/{len(filtered_participants)})"
                        )

                if self._is_cancelled():
                    raise DownloadCancelledError()

                if self.config.data_types.download_survey:
                    success = await self._download_participant_data_type(
                        participant_id, ChronicleDownloadDataType.SURVEY
                    )
                    if success:
                        downloads_completed += 1
                        progress_value = 10 + int(
                            (downloads_completed / total_downloads) * 80
                        )
                        self._update_progress(
                            progress_value, downloads_completed, total_downloads
                        )
                        LOGGER.debug(
                            f"Finished downloading {ChronicleDownloadDataType.SURVEY} data for device {participant_id} ({i + 1}/{len(filtered_participants)})"
                        )

                if self._is_cancelled():
                    raise DownloadCancelledError()

                if self.config.data_types.download_ios_sensor:
                    success = await self._download_participant_data_type(
                        participant_id, ChronicleDownloadDataType.IOSSENSOR
                    )
                    if success:
                        downloads_completed += 1
                        progress_value = 10 + int(
                            (downloads_completed / total_downloads) * 80
                        )
                        self._update_progress(
                            progress_value, downloads_completed, total_downloads
                        )
                        LOGGER.debug(
                            f"Finished downloading {ChronicleDownloadDataType.IOSSENSOR} data for device {participant_id} ({i + 1}/{len(filtered_participants)})"
                        )

                if self._is_cancelled():
                    raise DownloadCancelledError()

                if self.config.data_types.download_time_use_diary_daytime:
                    success = await self._download_participant_data_type(
                        participant_id, ChronicleDownloadDataType.TIME_USE_DIARY_DAYTIME
                    )
                    if success:
                        downloads_completed += 1
                        progress_value = 10 + int(
                            (downloads_completed / total_downloads) * 80
                        )
                        self._update_progress(
                            progress_value, downloads_completed, total_downloads
                        )
                        LOGGER.debug(
                            f"Finished downloading {ChronicleDownloadDataType.TIME_USE_DIARY_DAYTIME} data for device {participant_id} ({i + 1}/{len(filtered_participants)})"
                        )

                if self._is_cancelled():
                    raise DownloadCancelledError()

                if self.config.data_types.download_time_use_diary_nighttime:
                    success = await self._download_participant_data_type(
                        participant_id,
                        ChronicleDownloadDataType.TIME_USE_DIARY_NIGHTTIME,
                    )
                    if success:
                        downloads_completed += 1
                        progress_value = 10 + int(
                            (downloads_completed / total_downloads) * 80
                        )
                        self._update_progress(
                            progress_value, downloads_completed, total_downloads
                        )
                        LOGGER.debug(
                            f"Finished downloading {ChronicleDownloadDataType.TIME_USE_DIARY_NIGHTTIME} data for device {participant_id} ({i + 1}/{len(filtered_participants)})"
                        )

                if self._is_cancelled():
                    raise DownloadCancelledError()

                if self.config.data_types.download_time_use_diary_summarized:
                    success = await self._download_participant_data_type(
                        participant_id,
                        ChronicleDownloadDataType.TIME_USE_DIARY_SUMMARIZED,
                    )
                    if success:
                        downloads_completed += 1
                        progress_value = 10 + int(
                            (downloads_completed / total_downloads) * 80
                        )
                        self._update_progress(
                            progress_value, downloads_completed, total_downloads
                        )
                        LOGGER.debug(
                            f"Finished downloading {ChronicleDownloadDataType.TIME_USE_DIARY_SUMMARIZED} data for device {participant_id} ({i + 1}/{len(filtered_participants)})"
                        )

        finally:
            await self._close_client()

    def organize_data(self) -> None:
        """
        Organize downloaded data into categorized folders.

        Creates separate folders for each data type and moves files accordingly.
        Optionally deletes zero-byte files (before organizing, to avoid moving empty files).
        """
        # Delete zero-byte files BEFORE organizing so we don't waste I/O moving empty files
        if self.config.delete_zero_byte_files:
            LOGGER.debug("Checking for and deleting zero-byte files")
            all_csv_files = get_matching_files_from_folder(
                folder=self.config.download_folder,
                file_matching_pattern=r".*\.csv$",
                ignore_names=["Archive"],
            )
            for file in all_csv_files:
                self._delete_zero_byte_file(file)

        # Define (pattern, folder_name, ignore_name, enabled) tuples to avoid repetition
        organize_tasks: list[tuple[str, str, str, bool]] = [
            (
                self.file_patterns.raw_data,
                "Chronicle Android Raw Data Downloads",
                "Chronicle Android Raw Data Downloads",
                self.config.data_types.download_raw,
            ),
            (
                self.file_patterns.survey_data,
                "Chronicle Android Survey Data Downloads",
                "Chronicle Android Survey Data Downloads",
                self.config.data_types.download_survey,
            ),
            (
                self.file_patterns.ios_sensor_data,
                "Chronicle iOS Sensor Data Downloads",
                "Chronicle iOS Sensor Data Downloads",
                self.config.data_types.download_ios_sensor,
            ),
            (
                self.file_patterns.preprocessed_data,
                "Chronicle Android Preprocessed Data Downloads",
                "Chronicle Android Preprocessed Data Downloads",
                self.config.data_types.download_preprocessed,
            ),
            (
                self.file_patterns.time_use_diary_data,
                "Chronicle Time Use Diary Data Downloads",
                "Chronicle Time Use Diary Data Downloads",
                (
                    self.config.data_types.download_time_use_diary_daytime
                    or self.config.data_types.download_time_use_diary_nighttime
                    or self.config.data_types.download_time_use_diary_summarized
                ),
            ),
        ]

        for pattern, folder_name, ignore_name, enabled in organize_tasks:
            if not enabled:
                continue

            dest_folder = self.config.download_folder / folder_name
            dest_folder.mkdir(parents=True, exist_ok=True)

            unorganized_files = get_matching_files_from_folder(
                folder=self.config.download_folder,
                file_matching_pattern=pattern,
                ignore_names=["Archive", ignore_name],
            )
            for file in unorganized_files:
                dest_path = dest_folder / file.name
                if dest_path.exists():
                    dest_path.unlink()
                shutil.move(src=str(file), dst=str(dest_path))

        LOGGER.debug("Finished organizing downloaded Chronicle data.")

    def archive_data(self) -> None:
        """
        Archive outdated downloaded data.

        Moves files with dates older than today into dated archive folders.
        """
        dated_files = get_matching_files_from_folder(
            folder=self.config.download_folder,
            file_matching_pattern=self.file_patterns.dated_file,
            ignore_names=["Archive", ".png"],
        )

        for file in dated_files:
            re_file_date = re.search(r"(\d{2}[\.|-]\d{2}[\.|-]\d{4})", file.name)
            if not re_file_date:
                LOGGER.warning(f"Could not extract date from filename: {file.name}, skipping")
                continue

            re_file_date_str = re_file_date[0]
            try:
                re_file_date_object = datetime.strptime(
                    re_file_date_str, "%m-%d-%Y"
                ).replace(tzinfo=get_local_timezone())
            except ValueError:
                try:
                    re_file_date_object = datetime.strptime(
                        re_file_date_str, "%m.%d.%Y"
                    ).replace(tzinfo=get_local_timezone())
                except ValueError:
                    LOGGER.warning(f"Could not parse date '{re_file_date_str}' in filename: {file.name}, skipping")
                    continue

            if (
                re_file_date_object.date()
                < datetime.now(tz=get_local_timezone()).date()
            ):
                parent_dir_path = Path(file).parent
                parent_dir_name = Path(file).parent.name
                archive_dir = (
                    parent_dir_path
                    / f"{parent_dir_name} Archive"
                    / f"{parent_dir_name} Archive {re_file_date_str}"
                )
                archive_dir.mkdir(parents=True, exist_ok=True)

                dest_path = archive_dir / file.name
                if dest_path.exists():
                    dest_path.unlink()
                shutil.move(src=str(file), dst=str(dest_path))

        LOGGER.debug("Finished archiving outdated Chronicle data.")

    @staticmethod
    def _delete_zero_byte_file(file: str | Path) -> None:
        """
        Delete a zero-byte file.

        Args:
            file: Path to file to check and delete if empty
        """
        file_path = Path(file)
        if file_path.stat().st_size == 0:
            try:
                file_path.unlink()
                LOGGER.debug(f"Deleted zero-byte file: {file}")
            except PermissionError:
                LOGGER.exception(
                    f"The 0 byte file {file} could not be removed due to already being open, please close it and try again."
                )

    @staticmethod
    def load_config_from_file(config_path: Path) -> dict[str, Any]:
        """
        Load configuration from JSON file.

        Args:
            config_path: Path to configuration file

        Returns:
            Configuration dictionary

        Raises:
            FileNotFoundError: If config file doesn't exist
        """
        with config_path.open("r") as f:
            config = json.load(f)
        LOGGER.debug(f"Loaded configuration from {config_path}")
        return config

    @staticmethod
    def save_config_to_file(config_path: Path, config_data: dict[str, Any]) -> None:
        """
        Save configuration to JSON file.

        Args:
            config_path: Path to save configuration to
            config_data: Configuration data to save
        """
        with config_path.open("w") as f:
            json.dump(config_data, f, indent=2)
        LOGGER.debug(f"Saved configuration to {config_path}")
