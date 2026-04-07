from __future__ import annotations

import argparse
import asyncio
import json
import logging
import signal
import sys
from pathlib import Path
from typing import Any

from chronicle_bulk_data_downloader.core import (
    AuthConfig,
    AuthenticationError,
    ChronicleAPIError,
    ChronicleDownloader,
    DataTypeConfig,
    DownloadCancelledError,
    DownloadConfig,
    FilterConfig,
    NoParticipantsError,
)

LOGGER = logging.getLogger(__name__)


class CLIProgressCallback:
    """Progress callback that prints to stdout."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.last_percent = -1

    def __call__(
        self,
        progress_percent: int,
        completed_files: int | None = None,
        total_files: int | None = None,
    ) -> None:
        if self.last_percent != progress_percent:
            self.last_percent = progress_percent

            if completed_files is not None and total_files is not None:
                print(f"\rProgress: {progress_percent}% - Downloaded {completed_files} of {total_files} files", end="", flush=True)
            else:
                print(f"\rProgress: {progress_percent}%", end="", flush=True)

            if progress_percent == 100:
                print()


class CLICancellationCheck:
    """Cancellation check that responds to Ctrl+C."""

    def __init__(self):
        self.cancelled = False
        signal.signal(signal.SIGINT, self._signal_handler)

    def _signal_handler(self, signum: int, frame: object) -> None:
        print("\n\nReceived interrupt signal. Cancelling download...")
        self.cancelled = True

    def __call__(self) -> bool:
        return self.cancelled


def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments.

    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(
        description="Chronicle Android Bulk Data Downloader - Command Line Interface",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("--study-id", required=True, help="Chronicle study ID (36 characters)")

    parser.add_argument("--auth-token", required=True, help="Authorization token for Chronicle API")

    parser.add_argument("--download-folder", required=True, type=Path, help="Folder to download data to")

    parser.add_argument("--raw", action="store_true", help="Download raw data")

    parser.add_argument("--preprocessed", action="store_true", help="Download preprocessed data")

    parser.add_argument("--survey", action="store_true", help="Download survey data")

    parser.add_argument("--ios-sensor", action="store_true", help="Download iOS sensor data")

    parser.add_argument("--time-use-diary-daytime", action="store_true", help="Download daytime time use diary")

    parser.add_argument("--time-use-diary-nighttime", action="store_true", help="Download nighttime time use diary")

    parser.add_argument("--time-use-diary-summarized", action="store_true", help="Download summarized time use diary")

    parser.add_argument("--include-ids", help="Comma-separated list of participant IDs to include (exclusive with --exclude-ids)")

    parser.add_argument("--exclude-ids", help="Comma-separated list of participant IDs to exclude (exclusive with --include-ids)")

    parser.add_argument("--delete-zero-byte-files", action="store_true", help="Delete zero-byte files after download")

    parser.add_argument("--config-file", type=Path, help="Load settings from JSON configuration file")

    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")

    return parser.parse_args()


def load_config_from_file(config_file: Path) -> dict[str, Any]:
    """
    Load configuration from JSON file.

    Args:
        config_file: Path to configuration file

    Returns:
        Configuration dictionary

    Raises:
        FileNotFoundError: If config file doesn't exist
        json.JSONDecodeError: If config file is invalid JSON
    """
    with config_file.open("r") as f:
        return json.load(f)


def build_config_from_args(args: argparse.Namespace) -> DownloadConfig:
    """
    Build DownloadConfig from command-line arguments.

    Args:
        args: Parsed command-line arguments

    Returns:
        DownloadConfig object

    Raises:
        ValueError: If configuration is invalid
    """
    if args.config_file:
        if not args.config_file.exists():
            raise FileNotFoundError(f"Config file not found: {args.config_file}")

        file_config = load_config_from_file(args.config_file)

        study_id = args.study_id or file_config.get("study_id")
        auth_token = args.auth_token or file_config.get("auth_token")
        download_folder = args.download_folder or Path(file_config.get("download_folder", "."))

        download_raw = args.raw or file_config.get("raw_checked", False)
        download_preprocessed = args.preprocessed or file_config.get("preprocessed_checked", False)
        download_survey = args.survey or file_config.get("survey_checked", False)
        download_ios_sensor = args.ios_sensor or file_config.get("ios_sensor_checked", False)
        download_time_use_diary_daytime = args.time_use_diary_daytime or file_config.get("time_use_diary_daytime_checked", False)
        download_time_use_diary_nighttime = args.time_use_diary_nighttime or file_config.get("time_use_diary_nighttime_checked", False)
        download_time_use_diary_summarized = args.time_use_diary_summarized or file_config.get("time_use_diary_summarized_checked", False)

        include_ids = args.include_ids or file_config.get("participant_ids_to_filter", "")
        exclude_ids = args.exclude_ids
        inclusive = args.include_ids is not None or file_config.get("inclusive_checked", False)

        delete_zero_byte_files = args.delete_zero_byte_files or file_config.get("delete_zero_byte_files_checked", False)
    else:
        study_id = args.study_id
        auth_token = args.auth_token
        download_folder = args.download_folder

        download_raw = args.raw
        download_preprocessed = args.preprocessed
        download_survey = args.survey
        download_ios_sensor = args.ios_sensor
        download_time_use_diary_daytime = args.time_use_diary_daytime
        download_time_use_diary_nighttime = args.time_use_diary_nighttime
        download_time_use_diary_summarized = args.time_use_diary_summarized

        include_ids = args.include_ids
        exclude_ids = args.exclude_ids
        inclusive = args.include_ids is not None

        delete_zero_byte_files = args.delete_zero_byte_files

    if not study_id or len(study_id) < 36:
        raise ValueError("Study ID must be at least 36 characters")

    if not auth_token:
        raise ValueError("Authorization token is required")

    if not download_folder:
        raise ValueError("Download folder is required")

    if include_ids and exclude_ids:
        raise ValueError("Cannot use both --include-ids and --exclude-ids")

    if not any([
        download_raw,
        download_preprocessed,
        download_survey,
        download_ios_sensor,
        download_time_use_diary_daytime,
        download_time_use_diary_nighttime,
        download_time_use_diary_summarized,
    ]):
        raise ValueError("At least one data type must be selected")

    participant_ids_str = include_ids if inclusive else (exclude_ids or "")
    participant_ids = participant_ids_str.split(",") if participant_ids_str else []

    auth = AuthConfig(auth_token=auth_token, study_id=study_id)

    data_types = DataTypeConfig(
        download_raw=download_raw,
        download_preprocessed=download_preprocessed,
        download_survey=download_survey,
        download_ios_sensor=download_ios_sensor,
        download_time_use_diary_daytime=download_time_use_diary_daytime,
        download_time_use_diary_nighttime=download_time_use_diary_nighttime,
        download_time_use_diary_summarized=download_time_use_diary_summarized,
    )

    filter_config = FilterConfig(participant_ids=participant_ids, inclusive=inclusive)

    return DownloadConfig(
        auth=auth,
        download_folder=download_folder,
        data_types=data_types,
        filter_config=filter_config,
        delete_zero_byte_files=delete_zero_byte_files,
    )


async def run_download(config: DownloadConfig, verbose: bool = False) -> int:
    """
    Run the download process.

    Args:
        config: Download configuration
        verbose: Enable verbose output

    Returns:
        Exit code (0 for success, 1 for error, 130 for cancelled)
    """
    progress_callback = CLIProgressCallback(verbose=verbose)
    cancellation_check = CLICancellationCheck()

    downloader = ChronicleDownloader(
        config=config,
        progress_callback=progress_callback,
        cancellation_check=cancellation_check,
    )

    try:
        print("Starting download...")
        await downloader.download_all()

        print("\nOrganizing downloaded data...")
        progress_callback(90)
        downloader.archive_data()

        progress_callback(95)
        downloader.organize_data()

        progress_callback(100)
        print("\nDownload complete!")
        return 0

    except DownloadCancelledError:
        print("\n\nDownload cancelled by user.")
        return 130

    except AuthenticationError as e:
        print(f"\n\nAuthentication error: {e}", file=sys.stderr)
        return 1

    except NoParticipantsError as e:
        print(f"\n\nNo participants found: {e}", file=sys.stderr)
        return 1

    except ChronicleAPIError as e:
        print(f"\n\nAPI error: {e}", file=sys.stderr)
        return 1

    except Exception as e:
        print(f"\n\nUnexpected error: {e}", file=sys.stderr)
        LOGGER.exception("Unexpected error during download")
        return 1


def main() -> int:
    """
    Main entry point for CLI.

    Returns:
        Exit code
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    try:
        args = parse_args()

        if args.verbose:
            logging.getLogger().setLevel(logging.DEBUG)

        config = build_config_from_args(args)

        config.download_folder.mkdir(parents=True, exist_ok=True)

        exit_code = asyncio.run(run_download(config, verbose=args.verbose))
        return exit_code

    except ValueError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        return 1

    except FileNotFoundError as e:
        print(f"File error: {e}", file=sys.stderr)
        return 1

    except KeyboardInterrupt:
        print("\n\nInterrupted by user.")
        return 130

    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        LOGGER.exception("Unexpected error in CLI main")
        return 1


if __name__ == "__main__":
    sys.exit(main())
