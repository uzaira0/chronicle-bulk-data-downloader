from __future__ import annotations

import asyncio
import json
import logging
import traceback
from typing import TYPE_CHECKING

from PyQt6.QtCore import QThread, pyqtSignal

from chronicle_bulk_data_downloader.core import (
    AuthenticationError,
    ChronicleAPIError,
    ChronicleDownloader,
    DownloadCancelledError,
)

if TYPE_CHECKING:
    from chronicle_bulk_data_downloader.gui.main_window import ChronicleBulkDataDownloader


LOGGER = logging.getLogger(__name__)


class DownloadThreadWorker(QThread):
    """
    A worker thread for downloading Chronicle bulk data.
    """

    finished = pyqtSignal()
    error = pyqtSignal(str)
    progress = pyqtSignal(int)
    progress_text = pyqtSignal(str)
    cancelled = pyqtSignal()

    def __init__(self, parent_: ChronicleBulkDataDownloader) -> None:
        super().__init__(parent_)
        self.parent_ = parent_
        self.current_progress = 0
        self.total_progress = 100
        self.files_completed = 0
        self.total_files = 0
        self.is_cancelled = False
        self._client_lock = asyncio.Lock()

    def run(self) -> None:
        """
        Runs the download process in a separate thread.
        """
        try:
            self._run()
        except Exception:
            self.error.emit(f"An error occurred while downloading the data: {traceback.format_exc()}")

    def cancel(self) -> None:
        """
        Signals the worker to cancel the download process.
        """
        self.is_cancelled = True
        self.cancelled.emit()
        LOGGER.info("Download cancellation requested")

    def _run(self):
        """
        The main logic for downloading the data.
        """
        if not self.parent_.download_folder:
            self.error.emit("Please select a download folder.")
            LOGGER.warning("No download folder selected")
            return

        expected_study_id_length = 36
        if len(self.parent_.study_id_entry.text().strip()) < expected_study_id_length:
            self.error.emit("Please enter a valid Chronicle study ID.")
            LOGGER.warning("Invalid study ID entered")
            return

        if self.parent_.inclusive_filter_checkbox.isChecked() and not self.parent_.participant_ids_to_filter_list_entry.toPlainText().strip():
            self.error.emit("Please enter a valid list of participant IDs to *include* when the *inclusive* list checkbox is checked.")
            LOGGER.warning("Invalid participant IDs list entered for inclusive filter")
            return

        self.progress.emit(0)

        config = self.parent_._build_download_config()

        downloader = ChronicleDownloader(
            config=config,
            progress_callback=self.update_progress,
            cancellation_check=lambda: self.is_cancelled,
        )

        try:
            asyncio.run(downloader.download_all())
        except AuthenticationError:
            LOGGER.exception("Authentication failed")
            self.error.emit(
                "An HTTP error occurred while attempting to download the data:\n\n401 Unauthorized. Please check the authorization token and try again."
            )
            return
        except ChronicleAPIError as e:
            description = {
                403: "Forbidden",
                404: "Not Found",
            }.get(e.status_code, "Unknown")

            LOGGER.exception(f"HTTP error occurred: {e.status_code} {description}")
            self.error.emit(
                f"An HTTP error occurred while attempting to download the data:\n\n{e.status_code} {description}. Please ensure that the study and data type you chose correspond."
            )
            return
        except DownloadCancelledError:
            LOGGER.info("Download process was cancelled by user")
            return
        except Exception:
            LOGGER.exception("An error occurred while downloading the data")
            self.error.emit(f"An error occurred while downloading the data: {traceback.format_exc()}")
            return

        if self.is_cancelled:
            LOGGER.info("Download process was cancelled by user")
            return

        try:
            self.update_progress(90)
            downloader.archive_data()
            self.update_progress(95)
            downloader.organize_data()
            self.update_progress(100)

            with self.parent_.get_config_path(ensure_dir=True).open("w") as f:
                f.write(
                    json.dumps(
                        {
                            "download_folder": str(self.parent_.download_folder),
                            "study_id": self.parent_.study_id_entry.text().strip(),
                            "participant_ids_to_filter": self.parent_.participant_ids_to_filter_list_entry.toPlainText(),
                            "inclusive_checked": self.parent_.inclusive_filter_checkbox.isChecked(),
                            "raw_checked": self.parent_.download_raw_data_checkbox.isChecked(),
                            "preprocessed_checked": self.parent_.download_preprocessed_data_checkbox.isChecked(),
                            "survey_checked": self.parent_.download_survey_data_checkbox.isChecked(),
                            "ios_sensor_checked": self.parent_.download_ios_sensor_checkbox.isChecked(),
                            "time_use_diary_daytime_checked": self.parent_.download_time_use_diary_daytime_checkbox.isChecked(),
                            "time_use_diary_nighttime_checked": self.parent_.download_time_use_diary_nighttime_checkbox.isChecked(),
                            "time_use_diary_summarized_checked": self.parent_.download_time_use_diary_summarized_checkbox.isChecked(),
                            "delete_zero_byte_files_checked": self.parent_.delete_zero_byte_files_checkbox.isChecked(),
                        }
                    )
                )
            LOGGER.debug("Data download complete")
            self.finished.emit()
        except Exception:
            LOGGER.exception("An error occurred while organizing or archiving the data")
            self.error.emit(f"An error occurred while organizing or archiving the data: {traceback.format_exc()}")
            return

    def update_progress(self, progress_percent: int, completed_files: int | None = None, total_files: int | None = None) -> None:
        """
        Updates the progress value and emits the progress signal.
        """
        self.current_progress = progress_percent
        self.progress.emit(progress_percent)

        # Update file counts if provided
        if completed_files is not None and total_files is not None:
            self.completed_downloads = completed_files
            self.total_downloads = total_files

            # Format the progress text differently based on progress state
            progress_text = f"Downloaded {completed_files} of {total_files} files" if progress_percent < 100 else f"Complete! Downloaded {total_files} files"

            self.progress_text.emit(progress_text)
