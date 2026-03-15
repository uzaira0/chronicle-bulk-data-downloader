from __future__ import annotations

from typing import Protocol


class ProgressCallback(Protocol):
    """Protocol for progress update callbacks."""

    def __call__(
        self,
        progress_percent: int,
        completed_files: int | None = None,
        total_files: int | None = None,
    ) -> None:
        """
        Called to report download progress.

        Args:
            progress_percent: Progress percentage (0-100)
            completed_files: Number of files completed so far
            total_files: Total number of files to download
        """
        ...


class CancellationCheck(Protocol):
    """Protocol for checking if download should be cancelled."""

    def __call__(self) -> bool:
        """
        Called to check if the download should be cancelled.

        Returns:
            True if download should be cancelled, False otherwise
        """
        ...
