"""Tests for platform-specific directory logic in constants.py.

These tests mock sys.platform to verify correct behavior on all platforms
without needing to run on actual macOS/Linux/Windows machines.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from chronicle_bulk_data_downloader.constants import (
    APP_NAME,
    CONFIG_FILENAME,
    LOG_FILENAME,
    get_user_dir,
)


class TestGetUserDirMacOS:
    """Verify macOS paths follow Apple conventions."""

    @patch("chronicle_bulk_data_downloader.constants.sys")
    def test_config_uses_application_support(self, mock_sys: object) -> None:
        mock_sys.platform = "darwin"
        result = get_user_dir("config")
        assert "Library" in str(result)
        assert "Application Support" in str(result)
        assert str(result).endswith(APP_NAME)

    @patch("chronicle_bulk_data_downloader.constants.sys")
    def test_logs_uses_library_logs(self, mock_sys: object) -> None:
        mock_sys.platform = "darwin"
        result = get_user_dir("logs")
        assert "Library" in str(result)
        assert "Logs" in str(result)
        assert str(result).endswith(APP_NAME)

    @patch("chronicle_bulk_data_downloader.constants.sys")
    def test_data_uses_application_support(self, mock_sys: object) -> None:
        mock_sys.platform = "darwin"
        result = get_user_dir("data")
        assert "Application Support" in str(result)


class TestGetUserDirWindows:
    """Verify Windows paths use APPDATA."""

    @patch("chronicle_bulk_data_downloader.constants.os")
    @patch("chronicle_bulk_data_downloader.constants.sys")
    def test_uses_appdata_env_var(self, mock_sys: object, mock_os: object) -> None:
        mock_sys.platform = "win32"
        mock_os.environ = {"APPDATA": "C:\\Users\\test\\AppData\\Roaming"}
        result = get_user_dir("config")
        assert str(result).endswith(APP_NAME)

    @patch("chronicle_bulk_data_downloader.constants.os")
    @patch("chronicle_bulk_data_downloader.constants.sys")
    def test_falls_back_to_home_when_no_appdata(self, mock_sys: object, mock_os: object) -> None:
        mock_sys.platform = "win32"
        mock_os.environ = {}  # No APPDATA
        result = get_user_dir("config")
        assert str(result).endswith(APP_NAME)

    @patch("chronicle_bulk_data_downloader.constants.os")
    @patch("chronicle_bulk_data_downloader.constants.sys")
    def test_all_purposes_same_parent_on_windows(self, mock_sys: object, mock_os: object) -> None:
        mock_sys.platform = "win32"
        mock_os.environ = {"APPDATA": "C:\\Users\\test\\AppData\\Roaming"}
        config = get_user_dir("config")
        logs = get_user_dir("logs")
        data = get_user_dir("data")
        assert config == logs == data


class TestGetUserDirLinux:
    """Verify Linux paths follow XDG conventions."""

    @patch("chronicle_bulk_data_downloader.constants.sys")
    def test_config_uses_dot_config(self, mock_sys: object) -> None:
        mock_sys.platform = "linux"
        result = get_user_dir("config")
        assert ".config" in str(result)

    @patch("chronicle_bulk_data_downloader.constants.sys")
    def test_logs_uses_local_share(self, mock_sys: object) -> None:
        mock_sys.platform = "linux"
        result = get_user_dir("logs")
        assert ".local" in str(result)

    @patch("chronicle_bulk_data_downloader.constants.sys")
    def test_data_uses_local_share(self, mock_sys: object) -> None:
        mock_sys.platform = "linux"
        result = get_user_dir("data")
        assert ".local" in str(result)


class TestGetUserDirEdgeCases:
    """Edge cases for get_user_dir."""

    @patch("chronicle_bulk_data_downloader.constants.sys")
    def test_invalid_purpose_raises_key_error_on_macos(self, mock_sys: object) -> None:
        """On macOS/Linux, invalid purpose raises KeyError from the dict lookup."""
        mock_sys.platform = "darwin"
        with pytest.raises(KeyError):
            get_user_dir("invalid_purpose")

    @patch("chronicle_bulk_data_downloader.constants.sys")
    def test_invalid_purpose_raises_key_error_on_linux(self, mock_sys: object) -> None:
        mock_sys.platform = "linux"
        with pytest.raises(KeyError):
            get_user_dir("invalid_purpose")

    def test_result_is_path_object(self) -> None:
        result = get_user_dir("config")
        assert isinstance(result, Path)

    def test_result_ends_with_app_name(self) -> None:
        for purpose in ("config", "logs", "data"):
            result = get_user_dir(purpose)
            assert result.name == APP_NAME


class TestConstants:
    """Verify constant values are sensible."""

    def test_config_filename_has_json_extension(self) -> None:
        assert CONFIG_FILENAME.endswith(".json")

    def test_log_filename_has_log_extension(self) -> None:
        assert LOG_FILENAME.endswith(".log")

    def test_app_name_no_spaces(self) -> None:
        # Spaces in app names cause issues in filesystem paths
        assert " " not in APP_NAME
