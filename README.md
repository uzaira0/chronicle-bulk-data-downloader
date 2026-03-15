# Chronicle Bulk Data Downloader

A tool for downloading Chronicle data in bulk via GUI, CLI, or as an importable Python package.

Not affiliated with Chronicle or GetMethodic, please visit them here: https://getmethodic.com/

**Please do not lower or remove the rate limiting.**

## Features

- **Multiple Interfaces**: Use via GUI, command-line, or import as a Python package
- **Comprehensive Data Download**: Raw usage events, preprocessed data, surveys, iOS sensor data, time use diaries
- **Flexible Filtering**: Include or exclude specific participant IDs
- **Automated Organization**: Automatically organize and archive downloaded data
- **Progress Tracking**: Real-time progress updates with cancellation support
- **Cross-Platform**: Works on Windows, macOS, and Linux

## Installation

### From Source

```bash
git clone https://github.com/uzaira0/chronicle-bulk-data-downloader.git
cd chronicle-bulk-data-downloader

# Install in editable mode
pip install -e .

# With GUI support
pip install -e ".[gui]"

# With development dependencies
pip install -e ".[dev,gui]"
```

### Direct Install

```bash
pip install .
```

## Usage

### GUI Application

```bash
chronicle-downloader-gui
```

Or run directly:
```bash
python main.py
```

**GUI Steps:**
1. Select the download folder
2. Paste the token you copied from the Chronicle GetMethodic website:

   ![Authorization Token Copy](./authorization_token_copy_location.png)

3. Enter a valid Chronicle study ID
4. Optionally provide participant IDs to filter (separated by commas)
   - Exclusive filtering (default) excludes the IDs you list
   - Inclusive filtering (when checkbox is checked) only downloads the IDs you listed
5. Check which data types to download
6. Optionally check if you want to delete zero byte files
7. Click the "Run" button

### Command-Line Interface

```bash
chronicle-downloader-cli --help
```

**Basic Usage:**
```bash
chronicle-downloader-cli \
  --study-id "your-study-id-here" \
  --auth-token "your-auth-token-here" \
  --download-folder "./data" \
  --raw --preprocessed --survey
```

**With Participant Filtering:**
```bash
# Include only specific participants
chronicle-downloader-cli \
  --study-id "your-study-id" \
  --auth-token "your-token" \
  --download-folder "./data" \
  --raw \
  --include-ids "participant1,participant2,participant3"

# Exclude specific participants
chronicle-downloader-cli \
  --study-id "your-study-id" \
  --auth-token "your-token" \
  --download-folder "./data" \
  --raw \
  --exclude-ids "test_participant,demo_user"
```

**Load Configuration from File:**
```bash
chronicle-downloader-cli --config-file my_config.json
```

### Python Package

```python
from chronicle_bulk_data_downloader import (
    ChronicleDownloader,
    DownloadConfig,
    AuthConfig,
    DataTypeConfig,
    FilterConfig,
)

# Create configuration
config = DownloadConfig(
    auth=AuthConfig(
        study_id="your-study-id",
        auth_token="your-token",
    ),
    data_types=DataTypeConfig(
        download_raw=True,
        download_preprocessed=True,
        download_survey=True,
    ),
    download_folder="./data",
    delete_zero_byte_files=True,
)

# Create downloader with optional callbacks
def on_progress(progress_percent: int, completed_files: int | None = None, total_files: int | None = None) -> None:
    print(f"Progress: {progress_percent}% ({completed_files}/{total_files})")

def should_cancel() -> bool:
    return False

downloader = ChronicleDownloader(
    config=config,
    progress_callback=on_progress,
    cancellation_check=should_cancel,
)

# Run download
import asyncio
asyncio.run(downloader.download_all())
```

## Testing

```bash
# Run tests
pytest tests/ -v

# Type check
basedpyright chronicle_bulk_data_downloader/

# Lint
ruff check chronicle_bulk_data_downloader/ tests/
```

## Pre-built Executables

Pre-built executables for Windows and macOS are available on the [Releases](https://github.com/uzaira0/chronicle-bulk-data-downloader/releases) page.

## License

MIT
