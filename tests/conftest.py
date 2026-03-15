from __future__ import annotations

from pathlib import Path

import pytest

from chronicle_bulk_data_downloader.core.config import (
    AuthConfig,
    DataTypeConfig,
    DownloadConfig,
    FilterConfig,
)


@pytest.fixture
def tmp_download_dir(tmp_path: Path) -> Path:
    """Provide a temporary download directory."""
    d = tmp_path / "downloads"
    d.mkdir()
    return d


@pytest.fixture
def sample_auth() -> AuthConfig:
    """Provide a sample auth config (tokens are fake)."""
    return AuthConfig(
        auth_token="fake-token-for-testing-00000000000000",
        study_id="00000000-0000-0000-0000-000000000000",
    )


@pytest.fixture
def sample_data_types() -> DataTypeConfig:
    """Provide a sample data type config with raw + preprocessed enabled."""
    return DataTypeConfig(
        download_raw=True,
        download_preprocessed=True,
        download_survey=False,
    )


@pytest.fixture
def sample_config(
    sample_auth: AuthConfig,
    sample_data_types: DataTypeConfig,
    tmp_download_dir: Path,
) -> DownloadConfig:
    """Provide a fully constructed DownloadConfig."""
    return DownloadConfig(
        auth=sample_auth,
        download_folder=tmp_download_dir,
        data_types=sample_data_types,
        filter_config=FilterConfig(),
    )


@pytest.fixture
def populated_download_dir(tmp_download_dir: Path) -> Path:
    """Create a download dir with sample CSV files mimicking real downloads."""
    files = [
        "participant1 Chronicle Android Raw Data 03-15-2026.csv",
        "participant1 Chronicle Android Survey Data 03-15-2026.csv",
        "participant1 Chronicle Android Downloaded Preprocessed Data 03-15-2026.csv",
        "participant2 Chronicle Android Raw Data 03-15-2026.csv",
        "participant1 Chronicle iPhone IOSSensor Data 03-15-2026.csv",
        "participant1 Chronicle Time Use Diary Daytime Data 03-15-2026.csv",
        "zero_byte.csv",
    ]
    for name in files:
        f = tmp_download_dir / name
        if "zero_byte" in name:
            f.write_text("")
        else:
            f.write_text("col1,col2\nval1,val2\n")
    return tmp_download_dir
