"""Integration tests simulating the full post-download pipeline.

These reproduce the exact sequence that caused macOS OSError (read-only
filesystem when saving config after download) and verify it works on
all platforms. The API is mocked — what we're testing is the
download → archive → organize → config-save pipeline.
"""

from __future__ import annotations

import json
import stat
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from chronicle_bulk_data_downloader.core.config import (
    AuthConfig,
    DataTypeConfig,
    DownloadConfig,
    FilterConfig,
)
from chronicle_bulk_data_downloader.core.downloader import ChronicleDownloader


def _make_fake_csv_files(download_dir: Path) -> None:
    """Create fake downloaded CSV files as if download_all() just ran."""
    files = {
        "participant1 Chronicle Android Raw Data 01-01-2025.csv": "ts,val\n1,a\n",
        "participant1 Chronicle Android Downloaded Preprocessed Data 01-01-2025.csv": "ts,val\n1,b\n",
        "participant1 Chronicle Android Survey Data 01-01-2025.csv": "ts,val\n1,c\n",
        "participant2 Chronicle Android Raw Data 01-01-2025.csv": "ts,val\n2,a\n",
        "empty_file.csv": "",
    }
    for name, content in files.items():
        (download_dir / name).write_text(content)


class TestPostDownloadPipeline:
    """Test the archive → organize → config-save sequence on all platforms."""

    def test_full_pipeline_succeeds(self, tmp_path: Path) -> None:
        """Simulate the exact sequence from download_worker._run() after downloads finish."""
        download_dir = tmp_path / "downloads"
        download_dir.mkdir()
        _make_fake_csv_files(download_dir)

        config = DownloadConfig(
            auth=AuthConfig(auth_token="t", study_id="s" * 36),
            download_folder=download_dir,
            data_types=DataTypeConfig(
                download_raw=True,
                download_preprocessed=True,
                download_survey=True,
            ),
            filter_config=FilterConfig(),
            delete_zero_byte_files=True,
        )

        downloader = ChronicleDownloader(config=config)

        # Step 1: archive (moves old-dated files into archive folders)
        downloader.archive_data()

        # Step 2: organize (moves files into categorized subfolders)
        downloader.organize_data()

        # Step 3: config save (this is what crashed on macOS)
        config_path = tmp_path / "config.json"
        config_data = {
            "download_folder": str(download_dir),
            "study_id": "s" * 36,
            "raw_checked": True,
            "preprocessed_checked": True,
            "survey_checked": True,
        }
        ChronicleDownloader.save_config_to_file(config_path, config_data)

        # Verify config was saved correctly
        loaded = ChronicleDownloader.load_config_from_file(config_path)
        assert loaded["study_id"] == "s" * 36
        assert loaded["raw_checked"] is True

        # Verify zero-byte file was deleted
        assert not (download_dir / "empty_file.csv").exists()

        # Verify archive folders were created (files dated 01-01-2025 are in the past)
        archive_dirs = list(download_dir.rglob("*Archive*"))
        assert len(archive_dirs) > 0

    def test_pipeline_with_ios_sensor_data(self, tmp_path: Path) -> None:
        download_dir = tmp_path / "downloads"
        download_dir.mkdir()
        (download_dir / "p1 Chronicle iPhone IOSSensor Data 01-01-2025.csv").write_text("data")

        config = DownloadConfig(
            auth=AuthConfig(auth_token="t", study_id="s" * 36),
            download_folder=download_dir,
            data_types=DataTypeConfig(
                download_raw=False,
                download_preprocessed=False,
                download_survey=False,
                download_ios_sensor=True,
            ),
        )
        downloader = ChronicleDownloader(config=config)
        downloader.archive_data()
        downloader.organize_data()

        ios_folder = download_dir / "Chronicle iOS Sensor Data Downloads"
        assert ios_folder.exists()

    def test_pipeline_with_time_use_diary(self, tmp_path: Path) -> None:
        download_dir = tmp_path / "downloads"
        download_dir.mkdir()
        (download_dir / "p1 Chronicle Time Use Diary Daytime Data 01-01-2025.csv").write_text("data")

        config = DownloadConfig(
            auth=AuthConfig(auth_token="t", study_id="s" * 36),
            download_folder=download_dir,
            data_types=DataTypeConfig(
                download_raw=False,
                download_preprocessed=False,
                download_survey=False,
                download_time_use_diary_daytime=True,
            ),
        )
        downloader = ChronicleDownloader(config=config)
        downloader.archive_data()
        downloader.organize_data()

        tud_folder = download_dir / "Chronicle Time Use Diary Data Downloads"
        assert tud_folder.exists()


class TestFrozenConfigPath:
    """Simulate PyInstaller frozen environment config save on all platforms."""

    def test_frozen_config_save_to_user_dir(self, tmp_path: Path) -> None:
        """Verify config saves to a writable location when frozen, not the app bundle."""
        from chronicle_bulk_data_downloader.constants import CONFIG_FILENAME, get_user_dir

        with patch.object(sys, "frozen", True, create=True):
            config_dir = get_user_dir("config")
            # Simulate the ensure_dir=True path
            config_dir.mkdir(parents=True, exist_ok=True)
            config_path = config_dir / CONFIG_FILENAME

            # This is the exact operation that crashed on macOS
            config_data = {"study_id": "test", "download_folder": "/tmp"}
            with config_path.open("w") as f:
                json.dump(config_data, f)

            # Verify it wrote successfully
            with config_path.open("r") as f:
                loaded = json.load(f)
            assert loaded["study_id"] == "test"

            # Clean up
            config_path.unlink()

    @pytest.mark.skipif(sys.platform == "win32", reason="chmod read-only not enforceable on Windows")
    def test_readonly_dir_would_fail(self, tmp_path: Path) -> None:
        """Prove that writing to a read-only dir raises, confirming the bug scenario."""
        readonly_dir = tmp_path / "readonly_bundle"
        readonly_dir.mkdir()

        # Make it read-only (simulating macOS .app bundle)
        readonly_dir.chmod(stat.S_IRUSR | stat.S_IXUSR)

        try:
            config_path = readonly_dir / "config.json"
            with pytest.raises(PermissionError):
                config_path.open("w")
        finally:
            # Restore permissions for cleanup
            readonly_dir.chmod(stat.S_IRWXU)

    def test_frozen_path_not_inside_cwd(self) -> None:
        """When frozen, config path should NOT be in the current working directory."""

        with patch.object(sys, "frozen", True, create=True):
            from chronicle_bulk_data_downloader.gui.main_window import ChronicleBulkDataDownloader

            config_path = ChronicleBulkDataDownloader.get_config_path()
            # Should be in user's home area, not cwd
            assert not str(config_path).startswith(str(Path.cwd()))


class TestAsyncDownloadWithMockedAPI:
    """Test the full async download flow with mocked HTTP responses."""

    @pytest.mark.asyncio
    async def test_download_all_with_mocked_api(self, tmp_path: Path) -> None:
        """Mock the Chronicle API and run through the full download pipeline."""
        import httpx

        download_dir = tmp_path / "downloads"
        download_dir.mkdir()

        config = DownloadConfig(
            auth=AuthConfig(auth_token="fake-token", study_id="s" * 36),
            download_folder=download_dir,
            data_types=DataTypeConfig(
                download_raw=True,
                download_preprocessed=False,
                download_survey=False,
            ),
        )

        progress_values: list[int] = []
        downloader = ChronicleDownloader(
            config=config,
            progress_callback=lambda p, c=None, t=None: progress_values.append(p),
        )

        # httpx.Response.raise_for_status needs a request object
        fake_request = httpx.Request("GET", "https://fake.api/")

        # Mock get_participants response
        participants_response = httpx.Response(
            200,
            json={"0": {"participantId": "device-001"}, "1": {"participantId": "device-002"}},
            request=fake_request,
        )

        # Mock CSV download responses (one per participant)
        csv_responses = [
            httpx.Response(200, content=b"timestamp,value\n2025-01-01T00:00:00,42\n", request=fake_request),
            httpx.Response(200, content=b"timestamp,value\n2025-01-01T00:00:00,99\n", request=fake_request),
        ]

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=[participants_response, *csv_responses])
        mock_client.is_closed = False

        with patch.object(downloader, "_get_client", return_value=mock_client):
            with patch("chronicle_bulk_data_downloader.core.downloader.asyncio.sleep", new_callable=AsyncMock):
                await downloader.download_all()

        # Verify progress was reported
        assert len(progress_values) > 0
        assert progress_values[0] == 5  # Initial progress

        # Verify files were downloaded
        csv_files = list(download_dir.glob("*.csv"))
        assert len(csv_files) == 2

        # Now run the post-download pipeline
        downloader.archive_data()
        downloader.organize_data()

        # Verify raw data folder was created
        raw_folder = download_dir / "Chronicle Android Raw Data Downloads"
        assert raw_folder.exists()
