"""Verify all package modules import without errors.

This catches broken imports, missing dependencies, and stale references
(e.g., importing from deleted config.version or old package names).
"""

from __future__ import annotations

import importlib

import pytest

MODULES = [
    "chronicle_bulk_data_downloader",
    "chronicle_bulk_data_downloader.constants",
    "chronicle_bulk_data_downloader.enums",
    "chronicle_bulk_data_downloader.utils",
    "chronicle_bulk_data_downloader.core",
    "chronicle_bulk_data_downloader.core.callbacks",
    "chronicle_bulk_data_downloader.core.config",
    "chronicle_bulk_data_downloader.core.downloader",
    "chronicle_bulk_data_downloader.core.exceptions",
    "chronicle_bulk_data_downloader.download_worker",
    "chronicle_bulk_data_downloader.cli",
    "chronicle_bulk_data_downloader.cli.cli",
]


@pytest.mark.parametrize("module_name", MODULES)
def test_module_imports(module_name: str) -> None:
    """Each module should import without raising."""
    mod = importlib.import_module(module_name)
    assert mod is not None


def test_no_stale_src_references() -> None:
    """Ensure no module tries to import from deleted 'src' or 'config.version' paths."""
    import chronicle_bulk_data_downloader

    # If we got here, the top-level __init__ (which re-exports everything) loaded fine
    assert hasattr(chronicle_bulk_data_downloader, "__version__")
    assert hasattr(chronicle_bulk_data_downloader, "ChronicleDownloader")


def test_version_is_string() -> None:
    from chronicle_bulk_data_downloader import __version__

    assert isinstance(__version__, str)
    assert len(__version__) > 0


def test_gui_module_importable() -> None:
    """GUI module should import even without a display (no QApplication created)."""
    try:
        from chronicle_bulk_data_downloader.gui.main_window import ChronicleBulkDataDownloader

        assert ChronicleBulkDataDownloader is not None
    except ImportError as e:
        if "PyQt6" in str(e):
            pytest.skip("PyQt6 not installed")
        raise
