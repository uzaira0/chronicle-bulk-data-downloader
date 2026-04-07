"""Tests for CLI argument parsing and config building."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from chronicle_bulk_data_downloader.cli.cli import build_config_from_args, parse_args


def _make_args(**overrides: object) -> object:
    """Create a namespace with default CLI args, overridden by kwargs."""
    defaults = {
        "study_id": "00000000-0000-0000-0000-000000000000",
        "auth_token": "fake-token-for-testing-00000000000000",
        "download_folder": Path("/tmp/downloads"),
        "raw": True,
        "preprocessed": False,
        "survey": False,
        "ios_sensor": False,
        "time_use_diary_daytime": False,
        "time_use_diary_nighttime": False,
        "time_use_diary_summarized": False,
        "include_ids": None,
        "exclude_ids": None,
        "delete_zero_byte_files": False,
        "config_file": None,
        "verbose": False,
    }
    defaults.update(overrides)

    import argparse

    return argparse.Namespace(**defaults)


class TestBuildConfigFromArgs:
    def test_basic_config(self) -> None:
        args = _make_args()
        config = build_config_from_args(args)
        assert config.auth.study_id == "00000000-0000-0000-0000-000000000000"
        assert config.data_types.download_raw is True
        assert config.data_types.download_preprocessed is False

    def test_short_study_id_raises(self) -> None:
        args = _make_args(study_id="too-short")
        with pytest.raises(ValueError, match="Study ID"):
            build_config_from_args(args)

    def test_empty_auth_token_raises(self) -> None:
        args = _make_args(auth_token="")
        with pytest.raises(ValueError, match="Authorization token"):
            build_config_from_args(args)

    def test_no_data_types_raises(self) -> None:
        args = _make_args(raw=False, preprocessed=False, survey=False)
        with pytest.raises(ValueError, match="At least one data type"):
            build_config_from_args(args)

    def test_include_and_exclude_raises(self) -> None:
        args = _make_args(include_ids="p1", exclude_ids="p2")
        with pytest.raises(ValueError, match="Cannot use both"):
            build_config_from_args(args)

    def test_inclusive_filter(self) -> None:
        args = _make_args(include_ids="p1,p2,p3")
        config = build_config_from_args(args)
        assert config.filter_config.inclusive is True
        assert config.filter_config.participant_ids == ["p1", "p2", "p3"]

    def test_exclusive_filter(self) -> None:
        args = _make_args(exclude_ids="p4,p5")
        config = build_config_from_args(args)
        assert config.filter_config.inclusive is False
        assert config.filter_config.participant_ids == ["p4", "p5"]

    def test_config_file_loading(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.json"
        config_file.write_text(
            json.dumps(
                {
                    "study_id": "00000000-0000-0000-0000-000000000000",
                    "auth_token": "file-token-00000000000000000000000",
                    "download_folder": str(tmp_path),
                    "raw_checked": True,
                }
            )
        )
        args = _make_args(config_file=config_file)
        config = build_config_from_args(args)
        assert config.data_types.download_raw is True

    def test_config_file_not_found_raises(self, tmp_path: Path) -> None:
        args = _make_args(config_file=tmp_path / "missing.json")
        with pytest.raises(FileNotFoundError):
            build_config_from_args(args)

    def test_download_folder_is_path(self) -> None:
        args = _make_args()
        config = build_config_from_args(args)
        assert isinstance(config.download_folder, Path)


class TestParseArgs:
    def test_required_args(self) -> None:
        with patch(
            "sys.argv",
            [
                "prog",
                "--study-id",
                "00000000-0000-0000-0000-000000000000",
                "--auth-token",
                "fake-token",
                "--download-folder",
                "/tmp",
                "--raw",
            ],
        ):
            args = parse_args()
            assert args.study_id == "00000000-0000-0000-0000-000000000000"
            assert args.raw is True

    def test_missing_required_args_exits(self) -> None:
        with patch("sys.argv", ["prog"]):
            with pytest.raises(SystemExit):
                parse_args()
