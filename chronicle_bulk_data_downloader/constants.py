from __future__ import annotations

import os
import sys
from pathlib import Path

# Application identity
APP_NAME = "ChronicleBulkDataDownloader"
CONFIG_FILENAME = "Chronicle_bulk_data_downloader_config.json"
LOG_FILENAME = "Chronicle_bulk_data_downloader.log"

# HTTP client constants
MAX_RETRIES = 1
CONNECTION_TIMEOUT = 30
REQUEST_TIMEOUT = 300
RATE_LIMIT_DELAY = 1  # seconds between requests (reduced for testing)


def get_user_dir(purpose: str) -> Path:
    """Return a platform-appropriate user-writable directory for the app.

    Args:
        purpose: The type of directory needed. Determines the OS-conventional
                 parent directory:
                 - "config" → ~/Library/Application Support (macOS), %APPDATA% (Win), ~/.config (Linux)
                 - "logs"   → ~/Library/Logs (macOS), %APPDATA% (Win), ~/.local/share (Linux)
                 - "data"   → ~/Library/Application Support (macOS), %APPDATA% (Win), ~/.local/share (Linux)
    """
    if sys.platform.startswith("darwin"):
        parent = {
            "config": Path.home() / "Library" / "Application Support",
            "logs": Path.home() / "Library" / "Logs",
            "data": Path.home() / "Library" / "Application Support",
        }[purpose]
    elif sys.platform.startswith("win"):
        appdata_str = os.environ.get("APPDATA")
        base = Path(appdata_str) if appdata_str else Path.home()
        parent = base
    else:
        parent = {
            "config": Path.home() / ".config",
            "logs": Path.home() / ".local" / "share",
            "data": Path.home() / ".local" / "share",
        }[purpose]

    return parent / APP_NAME
