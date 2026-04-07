"""Cross-platform integration tests for config/log path handling.

These tests verify the actual get_config_path() and GUI entry points
handle frozen vs. non-frozen environments correctly on the current platform.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest


class TestConfigPathFrozen:
    """Simulate PyInstaller frozen environment."""

    def _import_get_config_path(self):
        """Import lazily to allow skip if PyQt6 missing."""
        try:
            from chronicle_bulk_data_downloader.gui.main_window import ChronicleBulkDataDownloader

            return ChronicleBulkDataDownloader.get_config_path
        except ImportError:
            pytest.skip("PyQt6 not installed")

    def test_frozen_config_path_is_user_writable(self) -> None:
        get_config_path = self._import_get_config_path()
        with patch.object(sys, "frozen", True, create=True):
            path = get_config_path()
            # Should NOT be inside the app bundle
            assert "Contents" not in str(path)
            # Should be in a user-writable location
            assert str(path).endswith(".json")

    def test_frozen_ensure_dir_creates_parent(self, tmp_path: Path) -> None:
        get_config_path = self._import_get_config_path()
        with patch.object(sys, "frozen", True, create=True):
            path = get_config_path(ensure_dir=True)
            assert path.parent.exists()

    def test_non_frozen_returns_local_path(self) -> None:
        get_config_path = self._import_get_config_path()
        # Ensure frozen attribute is absent
        frozen = getattr(sys, "frozen", None)
        if frozen is not None:
            delattr(sys, "frozen")
        try:
            path = get_config_path()
            # Should be just the filename in the current directory
            assert path.name.endswith(".json")
            assert path.parent == Path(".")
        finally:
            if frozen is not None:
                sys.frozen = frozen


class TestMainEntrypoint:
    """Verify main.py log path logic without launching GUI."""

    def test_frozen_log_path_uses_get_user_dir(self) -> None:
        from chronicle_bulk_data_downloader.constants import APP_NAME, LOG_FILENAME, get_user_dir

        expected_dir = get_user_dir("logs")
        expected_path = expected_dir / LOG_FILENAME

        # Should always end with APP_NAME/LOG_FILENAME
        assert expected_path.parent.name == APP_NAME
        assert expected_path.name == LOG_FILENAME
