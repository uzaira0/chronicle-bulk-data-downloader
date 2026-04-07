"""Tests for exception hierarchy."""

from __future__ import annotations

from chronicle_bulk_data_downloader.core.exceptions import (
    AuthenticationError,
    ChronicleAPIError,
    ChronicleDownloaderError,
    ConfigurationError,
    DownloadCancelledError,
    NoParticipantsError,
)


class TestExceptionHierarchy:
    def test_all_inherit_from_base(self) -> None:
        assert issubclass(ChronicleAPIError, ChronicleDownloaderError)
        assert issubclass(AuthenticationError, ChronicleDownloaderError)
        assert issubclass(DownloadCancelledError, ChronicleDownloaderError)
        assert issubclass(ConfigurationError, ChronicleDownloaderError)
        assert issubclass(NoParticipantsError, ChronicleDownloaderError)

    def test_auth_error_is_api_error(self) -> None:
        assert issubclass(AuthenticationError, ChronicleAPIError)

    def test_base_is_exception(self) -> None:
        assert issubclass(ChronicleDownloaderError, Exception)


class TestChronicleAPIError:
    def test_status_code_and_message(self) -> None:
        err = ChronicleAPIError(404, "Not Found")
        assert err.status_code == 404
        assert err.message == "Not Found"
        assert "404" in str(err)

    def test_catchable_as_base(self) -> None:
        try:
            raise ChronicleAPIError(500, "Server Error")
        except ChronicleDownloaderError as e:
            assert "500" in str(e)


class TestAuthenticationError:
    def test_default_message(self) -> None:
        err = AuthenticationError()
        assert err.status_code == 401
        assert "Unauthorized" in str(err)

    def test_custom_message(self) -> None:
        err = AuthenticationError("Token expired")
        assert "Token expired" in str(err)
        assert err.status_code == 401
