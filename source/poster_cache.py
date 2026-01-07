"""
Poster Cache System

Handles on-demand downloading and caching of movie/series poster images.
Downloads posters in background threads and stores them in ~/.cache/hackflix/posters/
"""

import os
import hashlib
import threading
from pathlib import Path
from typing import Optional, Dict
import requests
from PyQt5.QtCore import QObject, pyqtSignal, QSize
from PyQt5.QtGui import QPixmap, QPainter, QColor, QFont
from PyQt5.QtCore import Qt


class PosterCache(QObject):
    """
    Manages poster image downloading and caching.

    Features:
    - On-demand background downloading
    - Disk cache at ~/.cache/hackflix/posters/
    - Throttling (max concurrent downloads)
    - Placeholder images while loading
    - Thread-safe operations
    """

    # Signal emitted when a poster download completes
    # Args: item_id (str), pixmap (QPixmap)
    poster_ready = pyqtSignal(str, QPixmap)

    # Signal emitted when a poster download fails
    # Args: item_id (str), error_message (str)
    poster_failed = pyqtSignal(str, str)

    # Maximum concurrent downloads
    MAX_CONCURRENT_DOWNLOADS = 3

    # Poster thumbnail size
    THUMBNAIL_WIDTH = 40
    THUMBNAIL_HEIGHT = 60

    # HTTP timeout in seconds
    DOWNLOAD_TIMEOUT = 10

    def __init__(self, cache_dir: Optional[str] = None):
        """
        Initialize poster cache.

        Args:
            cache_dir: Optional custom cache directory path.
                      Defaults to ~/.cache/hackflix/posters/
        """
        super().__init__()

        # Set up cache directory
        if cache_dir is None:
            cache_dir = os.path.expanduser("~/.cache/hackflix/posters")
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Create placeholder image
        self.placeholder = self._create_placeholder()

        # Track active downloads
        self._active_downloads: Dict[str, threading.Thread] = {}
        self._download_lock = threading.Lock()

        # Track pending downloads (queue)
        self._pending_downloads: list = []

    def _create_placeholder(self) -> QPixmap:
        """
        Create a placeholder image for posters that haven't loaded yet.

        Returns:
            QPixmap with placeholder graphic
        """
        pixmap = QPixmap(self.THUMBNAIL_WIDTH, self.THUMBNAIL_HEIGHT)
        pixmap.fill(QColor(40, 40, 40))  # Dark gray background

        painter = QPainter(pixmap)
        painter.setPen(QColor(100, 100, 100))  # Light gray text

        # Draw border
        painter.drawRect(0, 0, self.THUMBNAIL_WIDTH - 1, self.THUMBNAIL_HEIGHT - 1)

        # Draw "?" in center
        font = QFont("Arial", 16, QFont.Bold)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignCenter, "?")

        painter.end()
        return pixmap

    def _get_cache_filename(self, poster_url: str) -> str:
        """
        Generate cache filename from poster URL using hash.

        Args:
            poster_url: URL of the poster image

        Returns:
            Filename to use for cached image
        """
        # Use SHA256 hash of URL as filename
        url_hash = hashlib.sha256(poster_url.encode()).hexdigest()

        # Try to preserve original extension
        extension = ".jpg"
        if "." in poster_url:
            ext_candidate = poster_url.rsplit(".", 1)[-1].lower()
            if ext_candidate in ("jpg", "jpeg", "png", "webp"):
                extension = f".{ext_candidate}"

        return f"{url_hash}{extension}"

    def get_poster(self, poster_url: Optional[str], item_id: str) -> QPixmap:
        """
        Get poster image, downloading in background if needed.

        Args:
            poster_url: URL of the poster image (or None if no poster available)
            item_id: Unique identifier for the movie/series (used for signal emission)

        Returns:
            QPixmap: Cached poster if available, placeholder otherwise
        """
        # Return placeholder if no URL provided
        if not poster_url:
            return self.placeholder

        # Check if already cached
        cache_filename = self._get_cache_filename(poster_url)
        cache_path = self.cache_dir / cache_filename

        if cache_path.exists():
            # Load from cache
            pixmap = QPixmap(str(cache_path))
            if not pixmap.isNull():
                # Scale to thumbnail size
                return pixmap.scaled(
                    self.THUMBNAIL_WIDTH,
                    self.THUMBNAIL_HEIGHT,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )

        # Not cached - start download in background
        self._start_download(poster_url, item_id, cache_path)

        # Return placeholder for now
        return self.placeholder

    def _start_download(self, poster_url: str, item_id: str, cache_path: Path):
        """
        Start background download of poster image.

        Args:
            poster_url: URL to download from
            item_id: Item identifier for signal emission
            cache_path: Path to save downloaded image
        """
        with self._download_lock:
            # Check if already downloading
            if item_id in self._active_downloads:
                return

            # Check if at max concurrent downloads
            if len(self._active_downloads) >= self.MAX_CONCURRENT_DOWNLOADS:
                # Add to pending queue
                self._pending_downloads.append((poster_url, item_id, cache_path))
                return

            # Start download thread
            thread = threading.Thread(
                target=self._download_poster,
                args=(poster_url, item_id, cache_path),
                daemon=True
            )
            self._active_downloads[item_id] = thread
            thread.start()

    def _download_poster(self, poster_url: str, item_id: str, cache_path: Path):
        """
        Download poster image in background thread.

        Args:
            poster_url: URL to download from
            item_id: Item identifier for signal emission
            cache_path: Path to save downloaded image
        """
        try:
            # Download image
            response = requests.get(
                poster_url,
                timeout=self.DOWNLOAD_TIMEOUT,
                headers={'User-Agent': 'HackFlix/1.0'}
            )
            response.raise_for_status()

            # Save to cache
            with open(cache_path, 'wb') as f:
                f.write(response.content)

            # Load as QPixmap
            pixmap = QPixmap(str(cache_path))
            if pixmap.isNull():
                raise ValueError("Failed to load downloaded image")

            # Scale to thumbnail size
            scaled = pixmap.scaled(
                self.THUMBNAIL_WIDTH,
                self.THUMBNAIL_HEIGHT,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )

            # Emit success signal
            self.poster_ready.emit(item_id, scaled)

        except Exception as e:
            # Emit failure signal
            error_msg = f"Failed to download poster: {str(e)}"
            self.poster_failed.emit(item_id, error_msg)

        finally:
            # Clean up and start next pending download
            with self._download_lock:
                # Remove from active downloads
                if item_id in self._active_downloads:
                    del self._active_downloads[item_id]

                # Start next pending download if any
                if self._pending_downloads:
                    next_url, next_id, next_path = self._pending_downloads.pop(0)
                    thread = threading.Thread(
                        target=self._download_poster,
                        args=(next_url, next_id, next_path),
                        daemon=True
                    )
                    self._active_downloads[next_id] = thread
                    thread.start()

    def clear_cache(self):
        """
        Clear all cached poster images.
        Useful for debugging or freeing disk space.
        """
        for cache_file in self.cache_dir.glob("*"):
            if cache_file.is_file():
                cache_file.unlink()

    def get_cache_size(self) -> int:
        """
        Get total size of cached images in bytes.

        Returns:
            Total cache size in bytes
        """
        total_size = 0
        for cache_file in self.cache_dir.glob("*"):
            if cache_file.is_file():
                total_size += cache_file.stat().st_size
        return total_size

    def get_thumbnail_size(self) -> QSize:
        """
        Get the size of poster thumbnails.

        Returns:
            QSize with thumbnail dimensions
        """
        return QSize(self.THUMBNAIL_WIDTH, self.THUMBNAIL_HEIGHT)
