from __future__ import annotations


class ChronicleDownloaderError(Exception):
    """Base exception for Chronicle Downloader errors."""

    pass


class ChronicleAPIError(ChronicleDownloaderError):
    """Raised when Chronicle API returns an error."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"API Error {status_code}: {message}")


class AuthenticationError(ChronicleAPIError):
    """Raised when authentication fails."""

    def __init__(self, message: str = "Unauthorized. Please check the authorization token."):
        super().__init__(401, message)


class DownloadCancelledError(ChronicleDownloaderError):
    """Raised when download is cancelled by user."""

    pass


class ConfigurationError(ChronicleDownloaderError):
    """Raised when configuration is invalid."""

    pass


class NoParticipantsError(ChronicleDownloaderError):
    """Raised when no participants are found after filtering."""

    pass
