"""Tests for enum values — ensures API contract strings don't accidentally change."""

from __future__ import annotations

from chronicle_bulk_data_downloader.enums import (
    ChronicleDeviceType,
    ChronicleDownloadDataType,
    OutputFormat,
)


class TestChronicleDownloadDataType:
    """These string values are sent directly to the Chronicle API.
    Changing them would silently break downloads."""

    def test_raw_value(self) -> None:
        assert ChronicleDownloadDataType.RAW == "UsageEvents"

    def test_survey_value(self) -> None:
        assert ChronicleDownloadDataType.SURVEY == "AppUsageSurvey"

    def test_preprocessed_value(self) -> None:
        assert ChronicleDownloadDataType.PREPROCESSED == "Preprocessed"

    def test_ios_sensor_value(self) -> None:
        assert ChronicleDownloadDataType.IOSSENSOR == "IOSSensor"

    def test_tud_daytime_value(self) -> None:
        assert ChronicleDownloadDataType.TIME_USE_DIARY_DAYTIME == "DayTime"

    def test_tud_nighttime_value(self) -> None:
        assert ChronicleDownloadDataType.TIME_USE_DIARY_NIGHTTIME == "NightTime"

    def test_tud_summarized_value(self) -> None:
        assert ChronicleDownloadDataType.TIME_USE_DIARY_SUMMARIZED == "Summarized"


class TestChronicleDeviceType:
    def test_values_are_strings(self) -> None:
        for member in ChronicleDeviceType:
            assert isinstance(member.value, str)


class TestOutputFormat:
    def test_csv_value(self) -> None:
        assert OutputFormat.CSV == "csv"

    def test_dataframe_value(self) -> None:
        assert OutputFormat.DATAFRAME == "dataframe"
