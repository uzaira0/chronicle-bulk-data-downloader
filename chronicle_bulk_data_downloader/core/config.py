from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class DateRangeConfig:
    """Configuration for date-based filtering of Chronicle API downloads.

    The Chronicle API supports startDate and endDate query parameters to filter
    data by timestamp. This allows incremental downloads when integrated with
    study date tracking.
    """

    start_date: datetime | None = None
    end_date: datetime | None = None

    def to_api_params(self) -> dict[str, str]:
        """Convert to API query parameters (ISO 8601 format)."""
        params = {}
        if self.start_date:
            params["startDate"] = self.start_date.isoformat()
        if self.end_date:
            params["endDate"] = self.end_date.isoformat()
        return params


@dataclass
class AuthConfig:
    """Configuration for Chronicle API authentication."""

    auth_token: str
    study_id: str


@dataclass
class FilterConfig:
    """Configuration for participant filtering."""

    participant_ids: list[str] = field(default_factory=list)
    inclusive: bool = False


@dataclass
class DataTypeConfig:
    """Configuration for which data types to download."""

    download_raw: bool = True
    download_preprocessed: bool = True
    download_survey: bool = True
    download_ios_sensor: bool = False
    download_time_use_diary_daytime: bool = False
    download_time_use_diary_nighttime: bool = False
    download_time_use_diary_summarized: bool = False


@dataclass
class DownloadConfig:
    """Complete configuration for Chronicle data download."""

    auth: AuthConfig
    download_folder: Path
    data_types: DataTypeConfig
    filter_config: FilterConfig = field(default_factory=FilterConfig)
    date_range: DateRangeConfig | None = None
    delete_zero_byte_files: bool = False

    def __post_init__(self):
        if isinstance(self.download_folder, str):
            self.download_folder = Path(self.download_folder)


@dataclass
class FilePatterns:
    """File patterns for organizing downloaded data."""

    temp_download: str = r"[\s\S]*.csv"
    dated_file: str = r"([\s\S]*(\d{2}[\.|-]\d{2}[\.|-]\d{4})[\s\S]*.csv)"
    raw_data: str = r"[\s\S]*(Raw)[\s\S]*.csv"
    survey_data: str = r"[\s\S]*(Survey)[\s\S]*.csv"
    ios_sensor_data: str = r"[\s\S]*(IOSSensor)[\s\S]*.csv"
    preprocessed_data: str = r"[\s\S]*(Downloaded Preprocessed)[\s\S]*.csv"
    time_use_diary_data: str = r"[\s\S]*(Time Use Diary)[\s\S]*.csv"
