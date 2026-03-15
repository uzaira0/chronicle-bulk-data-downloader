from __future__ import annotations

import logging
import sys
from pathlib import Path

from .main_window import ChronicleBulkDataDownloader

__all__ = ["ChronicleBulkDataDownloader", "main"]


def main() -> None:
    """
    Entry point for the Chronicle Bulk Data Downloader GUI application.
    """
    from PyQt6.QtWidgets import QApplication

    from chronicle_bulk_data_downloader import __version__
    from chronicle_bulk_data_downloader.constants import LOG_FILENAME, get_user_dir

    # Set up logging with proper path handling for app bundles
    if getattr(sys, "frozen", False):
        log_dir = get_user_dir("logs")
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / LOG_FILENAME
    else:
        log_file = LOG_FILENAME

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s.%(msecs)03d - %(process)d - %(thread)d - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s - %(message)s",
        handlers=[logging.FileHandler(log_file), logging.StreamHandler()],
    )

    LOGGER = logging.getLogger(__name__)
    LOGGER.info(f"Application starting, version {__version__}")
    LOGGER.info(f"Platform: {sys.platform}, Python: {sys.version}")
    LOGGER.info(f"Working directory: {Path.cwd()}")
    LOGGER.info(f"Log file location: {log_file}")

    # Use OS-specific platform plugin
    if sys.platform.startswith("win"):
        sys.argv += ["-platform", "windows:darkmode=1"]
    elif sys.platform.startswith("darwin"):
        sys.argv += ["-platform", "cocoa"]
        LOGGER.info("Using cocoa platform for macOS")

    app = QApplication(sys.argv)
    ex = ChronicleBulkDataDownloader()
    ex.show()
    sys.exit(app.exec())
