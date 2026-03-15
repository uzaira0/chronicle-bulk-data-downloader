"""Allow running the package directly: python -m chronicle_bulk_data_downloader"""

from __future__ import annotations

import sys

from chronicle_bulk_data_downloader.cli.cli import main

sys.exit(main())
