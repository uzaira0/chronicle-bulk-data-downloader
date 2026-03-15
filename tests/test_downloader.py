"""Tests for ChronicleDownloader business logic.

Tests URL construction, participant filtering, file organization, archiving,
and zero-byte file deletion without hitting the real API.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from chronicle_bulk_data_downloader.core.config import (
    DataTypeConfig,
    DateRangeConfig,
    DownloadConfig,
    FilterConfig,
)
from chronicle_bulk_data_downloader.core.downloader import ChronicleDownloader
from chronicle_bulk_data_downloader.core.exceptions import (
    NoParticipantsError,
)
from chronicle_bulk_data_downloader.enums import (
    ChronicleDeviceType,
    ChronicleDownloadDataType,
)


@pytest.fixture
def downloader(sample_config: DownloadConfig) -> ChronicleDownloader:
    return ChronicleDownloader(config=sample_config)


# ─── URL Construction ───────────────────────────────────────────────


class TestBuildDownloadUrl:
    def test_raw_data_url_contains_study_id(self, downloader: ChronicleDownloader) -> None:
        url, dtype_str, device_type = downloader._build_download_url(
            "participant1", ChronicleDownloadDataType.RAW
        )
        assert downloader.config.auth.study_id in url
        assert "participantId=participant1" in url
        assert "dataType=UsageEvents" in url
        assert "fileType=csv" in url
        assert device_type == ChronicleDeviceType.ANDROID

    def test_ios_sensor_url(self, downloader: ChronicleDownloader) -> None:
        url, dtype_str, device_type = downloader._build_download_url(
            "p1", ChronicleDownloadDataType.IOSSENSOR
        )
        assert "IOSSensor" in url
        assert device_type == ChronicleDeviceType.IPHONE

    def test_time_use_diary_url_uses_tud_endpoint(self, downloader: ChronicleDownloader) -> None:
        url, _, device_type = downloader._build_download_url(
            "p1", ChronicleDownloadDataType.TIME_USE_DIARY_DAYTIME
        )
        assert "time-use-diary" in url
        assert "fileType" not in url  # TUD endpoints don't use fileType
        assert device_type is None

    def test_date_range_added_to_url(self, downloader: ChronicleDownloader) -> None:
        date_range = DateRangeConfig(
            start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2026, 3, 15, tzinfo=timezone.utc),
        )
        url, _, _ = downloader._build_download_url(
            "p1", ChronicleDownloadDataType.RAW, date_range
        )
        assert "startDate=" in url
        assert "endDate=" in url

    def test_no_date_range_no_date_params(self, downloader: ChronicleDownloader) -> None:
        url, _, _ = downloader._build_download_url(
            "p1", ChronicleDownloadDataType.RAW, None
        )
        assert "startDate" not in url
        assert "endDate" not in url

    def test_invalid_data_type_raises(self, downloader: ChronicleDownloader) -> None:
        with pytest.raises(ValueError, match="Unrecognized"):
            downloader._build_download_url("p1", "INVALID_TYPE")

    @pytest.mark.parametrize(
        "data_type,expected_in_url",
        [
            (ChronicleDownloadDataType.RAW, "UsageEvents"),
            (ChronicleDownloadDataType.PREPROCESSED, "Preprocessed"),
            (ChronicleDownloadDataType.SURVEY, "AppUsageSurvey"),
            (ChronicleDownloadDataType.IOSSENSOR, "IOSSensor"),
            (ChronicleDownloadDataType.TIME_USE_DIARY_DAYTIME, "DayTime"),
            (ChronicleDownloadDataType.TIME_USE_DIARY_NIGHTTIME, "NightTime"),
            (ChronicleDownloadDataType.TIME_USE_DIARY_SUMMARIZED, "Summarized"),
        ],
    )
    def test_all_data_types_produce_valid_url(
        self, downloader: ChronicleDownloader, data_type: str, expected_in_url: str
    ) -> None:
        url, _, _ = downloader._build_download_url("p1", data_type)
        assert expected_in_url in url
        assert "participantId=p1" in url


# ─── Participant Filtering ──────────────────────────────────────────


class TestFilterParticipants:
    def test_no_filter_returns_all_sorted(self, downloader: ChronicleDownloader) -> None:
        result = downloader.filter_participants(["c", "a", "b"])
        assert result == ["a", "b", "c"]

    def test_inclusive_filter(self, sample_config: DownloadConfig) -> None:
        sample_config.filter_config = FilterConfig(
            participant_ids=["p1", "p3"], inclusive=True
        )
        dl = ChronicleDownloader(config=sample_config)
        result = dl.filter_participants(["p1", "p2", "p3", "p4"])
        assert result == ["p1", "p3"]

    def test_exclusive_filter(self, sample_config: DownloadConfig) -> None:
        sample_config.filter_config = FilterConfig(
            participant_ids=["p2"], inclusive=False
        )
        dl = ChronicleDownloader(config=sample_config)
        result = dl.filter_participants(["p1", "p2", "p3"])
        assert result == ["p1", "p3"]

    def test_inclusive_filter_case_insensitive(self, sample_config: DownloadConfig) -> None:
        sample_config.filter_config = FilterConfig(
            participant_ids=["P1"], inclusive=True
        )
        dl = ChronicleDownloader(config=sample_config)
        result = dl.filter_participants(["p1", "p2"])
        assert result == ["p1"]

    def test_exclusive_filter_case_insensitive(self, sample_config: DownloadConfig) -> None:
        sample_config.filter_config = FilterConfig(
            participant_ids=["P2"], inclusive=False
        )
        dl = ChronicleDownloader(config=sample_config)
        result = dl.filter_participants(["p1", "p2", "p3"])
        assert result == ["p1", "p3"]

    def test_empty_participants_raises(self, downloader: ChronicleDownloader) -> None:
        with pytest.raises(NoParticipantsError):
            downloader.filter_participants([])

    def test_all_filtered_out_raises(self, sample_config: DownloadConfig) -> None:
        sample_config.filter_config = FilterConfig(
            participant_ids=["nonexistent"], inclusive=True
        )
        dl = ChronicleDownloader(config=sample_config)
        with pytest.raises(NoParticipantsError):
            dl.filter_participants(["p1", "p2"])

    def test_whitespace_stripped(self, downloader: ChronicleDownloader) -> None:
        result = downloader.filter_participants(["  p1  ", "p2 ", " p3"])
        assert result == ["p1", "p2", "p3"]

    def test_empty_strings_excluded(self, downloader: ChronicleDownloader) -> None:
        result = downloader.filter_participants(["p1", "", "  ", "p2"])
        assert result == ["p1", "p2"]


# ─── File Organization ──────────────────────────────────────────────


class TestOrganizeData:
    def test_raw_files_moved_to_raw_folder(
        self, sample_config: DownloadConfig, populated_download_dir: Path
    ) -> None:
        sample_config.download_folder = populated_download_dir
        sample_config.data_types = DataTypeConfig(
            download_raw=True, download_preprocessed=False, download_survey=False
        )
        dl = ChronicleDownloader(config=sample_config)
        dl.organize_data()

        raw_folder = populated_download_dir / "Chronicle Android Raw Data Downloads"
        assert raw_folder.exists()
        raw_files = list(raw_folder.glob("*.csv"))
        assert len(raw_files) == 2  # participant1 + participant2

    def test_survey_files_moved_to_survey_folder(
        self, sample_config: DownloadConfig, populated_download_dir: Path
    ) -> None:
        sample_config.download_folder = populated_download_dir
        sample_config.data_types = DataTypeConfig(
            download_raw=False, download_preprocessed=False, download_survey=True
        )
        dl = ChronicleDownloader(config=sample_config)
        dl.organize_data()

        survey_folder = populated_download_dir / "Chronicle Android Survey Data Downloads"
        assert survey_folder.exists()
        survey_files = list(survey_folder.glob("*.csv"))
        assert len(survey_files) == 1

    def test_zero_byte_files_deleted(
        self, sample_config: DownloadConfig, populated_download_dir: Path
    ) -> None:
        sample_config.download_folder = populated_download_dir
        sample_config.delete_zero_byte_files = True
        dl = ChronicleDownloader(config=sample_config)
        dl.organize_data()

        zero_file = populated_download_dir / "zero_byte.csv"
        assert not zero_file.exists()

    def test_zero_byte_files_kept_when_option_disabled(
        self, sample_config: DownloadConfig, populated_download_dir: Path
    ) -> None:
        sample_config.download_folder = populated_download_dir
        sample_config.delete_zero_byte_files = False
        dl = ChronicleDownloader(config=sample_config)
        dl.organize_data()

        zero_file = populated_download_dir / "zero_byte.csv"
        assert zero_file.exists()


# ─── Archiving ───────────────────────────────────────────────────────


class TestArchiveData:
    def test_old_dated_files_archived(
        self, sample_config: DownloadConfig, tmp_download_dir: Path
    ) -> None:
        sample_config.download_folder = tmp_download_dir
        # Create a file with yesterday's date
        old_file = tmp_download_dir / "participant1 Chronicle Android Raw Data 01-01-2026.csv"
        old_file.write_text("data")

        dl = ChronicleDownloader(config=sample_config)
        dl.archive_data()

        # Original should be gone
        assert not old_file.exists()
        # Archive folder should exist
        archive_folders = list(tmp_download_dir.rglob("*Archive*"))
        assert len(archive_folders) > 0

    def test_todays_files_not_archived(
        self, sample_config: DownloadConfig, tmp_download_dir: Path
    ) -> None:
        sample_config.download_folder = tmp_download_dir
        today = datetime.now().strftime("%m-%d-%Y")
        today_file = tmp_download_dir / f"participant1 Chronicle Android Raw Data {today}.csv"
        today_file.write_text("data")

        dl = ChronicleDownloader(config=sample_config)
        dl.archive_data()

        # Today's file should still be there
        assert today_file.exists()


# ─── Zero Byte File Deletion ────────────────────────────────────────


class TestDeleteZeroByteFile:
    def test_deletes_empty_file(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.csv"
        f.write_text("")
        ChronicleDownloader._delete_zero_byte_file(f)
        assert not f.exists()

    def test_keeps_non_empty_file(self, tmp_path: Path) -> None:
        f = tmp_path / "data.csv"
        f.write_text("content")
        ChronicleDownloader._delete_zero_byte_file(f)
        assert f.exists()


# ─── Config File I/O ────────────────────────────────────────────────


class TestConfigIO:
    def test_save_and_load_roundtrip(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.json"
        original = {"study_id": "test-123", "download_folder": "/tmp/data"}

        ChronicleDownloader.save_config_to_file(config_path, original)
        loaded = ChronicleDownloader.load_config_from_file(config_path)

        assert loaded == original

    def test_load_nonexistent_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            ChronicleDownloader.load_config_from_file(tmp_path / "missing.json")


# ─── Cancellation ───────────────────────────────────────────────────


class TestCancellation:
    def test_is_cancelled_with_no_check(self, downloader: ChronicleDownloader) -> None:
        downloader.cancellation_check = None
        assert downloader._is_cancelled() is False

    def test_is_cancelled_returns_callback_result(self, downloader: ChronicleDownloader) -> None:
        downloader.cancellation_check = lambda: True
        assert downloader._is_cancelled() is True

    def test_progress_callback_called(self, sample_config: DownloadConfig) -> None:
        progress_values = []
        dl = ChronicleDownloader(
            config=sample_config,
            progress_callback=lambda p, c=None, t=None: progress_values.append(p),
        )
        dl._update_progress(50, 5, 10)
        assert progress_values == [50]

    def test_progress_callback_not_called_when_none(self, downloader: ChronicleDownloader) -> None:
        downloader.progress_callback = None
        downloader._update_progress(50)  # Should not raise


# ─── Polars Optional Import ─────────────────────────────────────────


class TestPolarsOptional:
    @pytest.mark.asyncio
    async def test_fetch_data_type_without_polars_raises_import_error(
        self, sample_config: DownloadConfig
    ) -> None:
        dl = ChronicleDownloader(config=sample_config)
        with patch("chronicle_bulk_data_downloader.core.downloader.pl", None):
            with pytest.raises(ImportError, match="polars"):
                await dl.fetch_data_type(
                    ["device1"], ChronicleDownloadDataType.RAW
                )
