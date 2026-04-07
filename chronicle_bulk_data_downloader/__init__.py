"""
Chronicle Bulk Data Downloader - A tool for downloading Chronicle data in bulk.

This package provides:
- Core business logic for downloading Chronicle data (chronicle_bulk_data_downloader.core)
- GUI interface using PyQt6 (chronicle_bulk_data_downloader.gui)
- Command-line interface (chronicle_bulk_data_downloader.cli)
"""

from __future__ import annotations

__version__ = "1.0.0"

# Make core classes easily accessible at package level
from .core import (
    AuthConfig,
    CancellationCheck,
    ChronicleDownloader,
    DataTypeConfig,
    DownloadConfig,
    FilePatterns,
    FilterConfig,
    ProgressCallback,
)
from .core.exceptions import (
    AuthenticationError,
    ChronicleAPIError,
    ChronicleDownloaderError,
    ConfigurationError,
    DownloadCancelledError,
    NoParticipantsError,
)
from .enums import (
    ChronicleDeviceType,
    ChronicleDownloadDataType,
    FilterType,
    OutputFormat,
)

__all__ = [
    # Main classes
    "ChronicleDownloader",
    # Configuration
    "AuthConfig",
    "DataTypeConfig",
    "DownloadConfig",
    "FilePatterns",
    "FilterConfig",
    # Enums
    "ChronicleDeviceType",
    "ChronicleDownloadDataType",
    "FilterType",
    "OutputFormat",
    # Protocols
    "CancellationCheck",
    "ProgressCallback",
    # Exceptions
    "AuthenticationError",
    "ChronicleAPIError",
    "ChronicleDownloaderError",
    "ConfigurationError",
    "DownloadCancelledError",
    "NoParticipantsError",
]
