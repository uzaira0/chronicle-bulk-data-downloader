"""Tests for utility functions."""

from __future__ import annotations

from pathlib import Path


from chronicle_bulk_data_downloader.utils import (
    get_local_timezone,
    get_matching_files_from_folder,
)


class TestGetMatchingFilesFromFolder:
    def test_matches_csv_files(self, tmp_path: Path) -> None:
        (tmp_path / "data.csv").write_text("data")
        (tmp_path / "data.txt").write_text("data")
        result = get_matching_files_from_folder(tmp_path, r".*\.csv$")
        assert len(result) == 1
        assert result[0].name == "data.csv"

    def test_ignores_specified_names(self, tmp_path: Path) -> None:
        archive = tmp_path / "Archive"
        archive.mkdir()
        (archive / "old.csv").write_text("data")
        (tmp_path / "new.csv").write_text("data")

        result = get_matching_files_from_folder(
            tmp_path, r".*\.csv$", ignore_names=["Archive"]
        )
        assert len(result) == 1
        assert result[0].name == "new.csv"

    def test_recurses_subdirectories(self, tmp_path: Path) -> None:
        sub = tmp_path / "subdir"
        sub.mkdir()
        (sub / "nested.csv").write_text("data")
        result = get_matching_files_from_folder(tmp_path, r".*\.csv$")
        assert len(result) == 1

    def test_empty_folder_returns_empty(self, tmp_path: Path) -> None:
        result = get_matching_files_from_folder(tmp_path, r".*\.csv$")
        assert result == []

    def test_string_folder_path_accepted(self, tmp_path: Path) -> None:
        (tmp_path / "test.csv").write_text("data")
        result = get_matching_files_from_folder(str(tmp_path), r".*\.csv$")
        assert len(result) == 1

    def test_raw_data_pattern_matches(self, tmp_path: Path) -> None:
        (tmp_path / "p1 Chronicle Android Raw Data 03-15-2026.csv").write_text("data")
        result = get_matching_files_from_folder(
            tmp_path, r"[\s\S]*(Raw)[\s\S]*.csv"
        )
        assert len(result) == 1

    def test_multiple_ignore_names(self, tmp_path: Path) -> None:
        (tmp_path / "Archive").mkdir()
        (tmp_path / "Archive" / "a.csv").write_text("data")
        (tmp_path / "icon.png").write_text("data")
        (tmp_path / "good.csv").write_text("data")

        result = get_matching_files_from_folder(
            tmp_path, r".*", ignore_names=["Archive", ".png"]
        )
        assert len(result) == 1
        assert result[0].name == "good.csv"


class TestGetLocalTimezone:
    def test_returns_tzinfo_or_none(self) -> None:
        tz = get_local_timezone()
        # Should return a valid tzinfo on any platform
        assert tz is not None

    def test_timezone_has_name(self) -> None:
        tz = get_local_timezone()
        # tzinfo objects should have a tzname method
        assert hasattr(tz, "tzname")
