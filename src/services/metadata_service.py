"""Metadata synchronization service for Hackflix.

This module provides the MetadataService class for fetching and syncing
content metadata from a remote catalog.
"""

import json
import logging
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QThread, Signal

from src.config import CACHE_DIR, CATALOG_URL
from src.database.db_manager import DatabaseManager

logger = logging.getLogger(__name__)


class MetadataService(QThread):
    """Background worker for metadata synchronization.

    Fetches content.json from CATALOG_URL, updates database via upsert_content(),
    and caches poster images locally.

    Signals:
        sync_started: Emitted when sync begins.
        sync_progress: Emitted with (current: int, total: int, message: str).
        sync_completed: Emitted when sync finishes successfully.
        sync_error: Emitted with (error_message: str) on failure.
    """

    sync_started = Signal()
    sync_progress = Signal(int, int, str)  # current, total, message
    sync_completed = Signal()
    sync_error = Signal(str)

    def __init__(
        self,
        db_manager: DatabaseManager,
        catalog_url: str | None = None,
        cache_dir: Path | None = None,
        parent: QObject | None = None,
    ) -> None:
        """Initialize the MetadataService.

        Args:
            db_manager: DatabaseManager instance for database operations.
            catalog_url: URL to fetch content.json from. Defaults to CATALOG_URL.
            cache_dir: Directory for caching poster images. Defaults to CACHE_DIR.
            parent: Optional parent QObject.
        """
        super().__init__(parent)
        self._db_manager = db_manager
        self._catalog_url = catalog_url or CATALOG_URL
        self._cache_dir = Path(cache_dir) if cache_dir else CACHE_DIR
        self._poster_dir = self._cache_dir / "posters"
        self._should_stop = False

    def stop(self) -> None:
        """Request the service to stop gracefully."""
        self._should_stop = True

    def run(self) -> None:
        """Execute the metadata sync operation.

        This method runs in a separate thread.
        """
        try:
            self.sync_started.emit()
            self._ensure_cache_dirs()

            # Step 1: Fetch content.json
            self.sync_progress.emit(0, 3, "Fetching catalog...")
            content_data = self._fetch_content_json()

            if self._should_stop:
                return

            # Step 2: Update database
            self.sync_progress.emit(1, 3, "Updating database...")
            self._db_manager.upsert_content(content_data)

            if self._should_stop:
                return

            # Step 3: Cache poster images
            self.sync_progress.emit(2, 3, "Caching poster images...")
            self._cache_posters(content_data)

            self.sync_progress.emit(3, 3, "Sync complete")
            self.sync_completed.emit()

        except urllib.error.URLError as e:
            error_reason = str(e.reason) if hasattr(e, "reason") else str(e)
            logger.error("Network error fetching catalog: %s", error_reason)
            self.sync_error.emit(f"Network error: {error_reason}")
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON in catalog response: %s", e)
            self.sync_error.emit(f"Invalid catalog format: {e}")
        except Exception as e:
            logger.error("Metadata sync failed: %s", e)
            self.sync_error.emit(str(e))

    def _ensure_cache_dirs(self) -> None:
        """Create cache directories if they don't exist."""
        self._poster_dir.mkdir(parents=True, exist_ok=True)

    def _fetch_content_json(self) -> dict[str, Any]:
        """Fetch and parse content.json from catalog URL.

        Returns:
            Parsed content.json dictionary.

        Raises:
            urllib.error.URLError: If network request fails.
            json.JSONDecodeError: If response is not valid JSON.
        """
        logger.info("Fetching catalog from %s", self._catalog_url)
        with urllib.request.urlopen(self._catalog_url, timeout=30) as response:
            data = response.read().decode("utf-8")
            return json.loads(data)

    def _cache_posters(self, content_data: dict[str, Any]) -> None:
        """Download and cache poster images for all items.

        Args:
            content_data: Parsed content.json dictionary.
        """
        items = content_data.get("items", [])

        for item in items:
            if self._should_stop:
                return

            poster_url = item.get("poster_url")
            if not poster_url:
                continue

            item_id = item.get("id", "")
            try:
                self._download_poster(item_id, poster_url)
            except urllib.error.URLError as e:
                logger.warning("Failed to download poster for %s: %s", item_id, e)
                # Continue with other posters

    def _download_poster(self, item_id: str, poster_url: str) -> Path:
        """Download a single poster image.

        Args:
            item_id: Media item ID for filename.
            poster_url: URL of the poster image.

        Returns:
            Path to the cached poster file.

        Raises:
            urllib.error.URLError: If download fails.
        """
        # Determine file extension from URL
        ext = Path(poster_url).suffix or ".jpg"
        poster_path = self._poster_dir / f"{item_id}{ext}"

        # Skip if already cached
        if poster_path.exists():
            return poster_path

        logger.debug("Downloading poster for %s from %s", item_id, poster_url)
        with urllib.request.urlopen(poster_url, timeout=30) as response:
            poster_path.write_bytes(response.read())

        return poster_path

    def get_poster_path(self, item_id: str) -> Path | None:
        """Get the cached poster path for a media item.

        Args:
            item_id: Media item ID.

        Returns:
            Path to cached poster or None if not cached.
        """
        for ext in [".jpg", ".jpeg", ".png", ".webp"]:
            poster_path = self._poster_dir / f"{item_id}{ext}"
            if poster_path.exists():
                return poster_path
        return None
