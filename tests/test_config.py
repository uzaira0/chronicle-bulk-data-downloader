"""Tests for core configuration dataclasses."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path


from chronicle_bulk_data_downloader.core.config import (
    AuthConfig,
    DataTypeConfig,
    DateRangeConfig,
    DownloadConfig,
    FilePatterns,
    FilterConfig,
)


class TestDateRangeConfig:
    def test_to_api_params_both_dates(self) -> None:
        dr = DateRangeConfig(
            start_date=datetime(2026, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2026, 3, 15, tzinfo=timezone.utc),
        )
        params = dr.to_api_params()
        assert "startDate" in params
        assert "endDate" in params
        assert "2026-01-01" in params["startDate"]

    def test_to_api_params_no_dates(self) -> None:
        dr = DateRangeConfig()
        assert dr.to_api_params() == {}

    def test_to_api_params_only_start(self) -> None:
        dr = DateRangeConfig(start_date=datetime(2026, 1, 1, tzinfo=timezone.utc))
        params = dr.to_api_params()
        assert "startDate" in params
        assert "endDate" not in params


class TestDataTypeConfig:
    def test_defaults(self) -> None:
        dtc = DataTypeConfig()
        assert dtc.download_raw is True
        assert dtc.download_preprocessed is True
        assert dtc.download_survey is True
        assert dtc.download_ios_sensor is False
        assert dtc.download_time_use_diary_daytime is False

    def test_all_false(self) -> None:
        dtc = DataTypeConfig(
            download_raw=False,
            download_preprocessed=False,
            download_survey=False,
        )
        assert not dtc.download_raw


class TestDownloadConfig:
    def test_string_download_folder_coerced_to_path(self) -> None:
        config = DownloadConfig(
            auth=AuthConfig(auth_token="tok", study_id="sid"),
            download_folder="/tmp/test",
            data_types=DataTypeConfig(),
        )
        assert isinstance(config.download_folder, Path)

    def test_path_download_folder_preserved(self, tmp_path: Path) -> None:
        config = DownloadConfig(
            auth=AuthConfig(auth_token="tok", study_id="sid"),
            download_folder=tmp_path,
            data_types=DataTypeConfig(),
        )
        assert config.download_folder == tmp_path

    def test_default_filter_config(self) -> None:
        config = DownloadConfig(
            auth=AuthConfig(auth_token="tok", study_id="sid"),
            download_folder="/tmp",
            data_types=DataTypeConfig(),
        )
        assert config.filter_config.participant_ids == []
        assert config.filter_config.inclusive is False

    def test_default_date_range_is_none(self) -> None:
        config = DownloadConfig(
            auth=AuthConfig(auth_token="tok", study_id="sid"),
            download_folder="/tmp",
            data_types=DataTypeConfig(),
        )
        assert config.date_range is None


class TestFilterConfig:
    def test_defaults(self) -> None:
        fc = FilterConfig()
        assert fc.participant_ids == []
        assert fc.inclusive is False

    def test_with_ids(self) -> None:
        fc = FilterConfig(participant_ids=["p1", "p2"], inclusive=True)
        assert len(fc.participant_ids) == 2
        assert fc.inclusive is True


class TestFilePatterns:
    def test_patterns_are_valid_regex(self) -> None:
        import re

        fp = FilePatterns()
        for field_name in ("temp_download", "dated_file", "raw_data", "survey_data",
                          "ios_sensor_data", "preprocessed_data", "time_use_diary_data"):
            pattern = getattr(fp, field_name)
            re.compile(pattern)  # Should not raise

    def test_raw_pattern_matches_raw_files(self) -> None:
        import re

        fp = FilePatterns()
        assert re.search(fp.raw_data, "participant1 Chronicle Android Raw Data 03-15-2026.csv")

    def test_survey_pattern_matches_survey_files(self) -> None:
        import re

        fp = FilePatterns()
        assert re.search(fp.survey_data, "participant1 Chronicle Android Survey Data 03-15-2026.csv")

    def test_preprocessed_pattern_matches(self) -> None:
        import re

        fp = FilePatterns()
        assert re.search(fp.preprocessed_data, "p1 Chronicle Android Downloaded Preprocessed Data 03-15-2026.csv")

    def test_ios_sensor_pattern_matches(self) -> None:
        import re

        fp = FilePatterns()
        assert re.search(fp.ios_sensor_data, "p1 Chronicle iPhone IOSSensor Data 03-15-2026.csv")

    def test_time_use_diary_pattern_matches(self) -> None:
        import re

        fp = FilePatterns()
        assert re.search(fp.time_use_diary_data, "p1 Chronicle Time Use Diary Daytime Data 03-15-2026.csv")
