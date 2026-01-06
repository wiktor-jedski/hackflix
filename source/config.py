"""
Application configuration for HackFlix
"""

import os
from pathlib import Path

# Paths
APP_DIR = Path(__file__).parent.parent
DATABASE_FILE = APP_DIR / "hackflix.db"
DOWNLOAD_DIR = Path.home() / "Videos" / "HackFlix"

# Catalog configuration
CATALOG_URL = os.getenv(
    "CATALOG_URL",
    "https://wiktor-jedski.github.io/hackflix-catalog/catalog.json"
)

# Sync configuration
SYNC_TIMEOUT = 30  # seconds
AUTO_SYNC_ON_STARTUP = False  # Manual sync only for now
SYNC_CHECK_INTERVAL = 86400  # 24 hours in seconds

# Download configuration
MAX_CONCURRENT_DOWNLOADS = 3
DOWNLOAD_PAUSE_ON_EXIT = True

# Ensure directories exist
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
