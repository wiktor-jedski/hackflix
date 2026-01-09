"""Torrent download service for Hackflix.

This module provides the TorrentService class for managing torrent downloads
using the embedded libtorrent library.
"""

import logging
import pickle
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import libtorrent as lt
from PyQt5.QtCore import QObject, QThread, QTimer, pyqtSignal

from src.config import (
    DownloadState,
    MEDIA_LIBRARY_PATH,
    TORRENT_POLL_INTERVAL_MS,
    TORRENT_STATE_DIR,
)
from src.database.db_manager import DatabaseManager

logger = logging.getLogger(__name__)

# Video file extensions to identify the main content
VIDEO_EXTENSIONS = frozenset({".mkv", ".mp4", ".avi", ".webm", ".mov", ".wmv", ".flv"})


class DownloadType(Enum):
    """Type of download context."""

    MOVIE = "movie"
    SEASON = "season"


@dataclass
class DownloadContext:
    """Context for a torrent download.

    Attributes:
        download_type: Type of download (movie or season).
        id: Database ID - video_file_id for movies, season_id for seasons.
    """

    download_type: DownloadType
    id: int


class TorrentService(QThread):
    """Background worker for torrent downloads.

    Manages a persistent libtorrent session with DHT, handles magnet links,
    tracks download progress, and saves/loads session state for resume.

    Supports both single-file downloads (movies) and multi-file downloads
    (season packs) with automatic episode file matching.

    Signals:
        download_progress: Emitted with (context_id: int, progress: int,
                          download_rate: float, upload_rate: float).
                          For movies: video_file_id. For seasons: season_id.
        download_completed: Emitted with (video_file_id: int, file_path: str).
                           Emitted once per video file (multiple times for seasons).
        download_error: Emitted with (context_id: int, error_message: str).
                       For movies: video_file_id. For seasons: season_id.
    """

    download_progress = pyqtSignal(int, int, float, float)  # context_id, %, down, up
    download_completed = pyqtSignal(int, str)  # video_file_id, file_path
    download_error = pyqtSignal(int, str)  # context_id, error_message

    # State file names
    SESSION_STATE_FILE = "session_state.lt"
    RESUME_DATA_FILE = "resume_data.pkl"

    def __init__(
        self,
        db_manager: DatabaseManager,
        state_dir: Path | None = None,
        download_dir: Path | None = None,
        poll_interval_ms: int | None = None,
        parent: QObject | None = None,
    ) -> None:
        """Initialize the TorrentService.

        Args:
            db_manager: DatabaseManager instance for database operations.
            state_dir: Directory for session state. Defaults to TORRENT_STATE_DIR.
            download_dir: Directory for downloads. Defaults to MEDIA_LIBRARY_PATH.
            poll_interval_ms: Polling interval. Defaults to TORRENT_POLL_INTERVAL_MS.
            parent: Optional parent QObject.
        """
        super().__init__(parent)
        self._db_manager = db_manager
        self._state_dir = Path(state_dir) if state_dir else TORRENT_STATE_DIR
        self._download_dir = Path(download_dir) if download_dir else MEDIA_LIBRARY_PATH
        self._poll_interval = poll_interval_ms or TORRENT_POLL_INTERVAL_MS

        self._session: lt.session | None = None
        self._contexts: dict[int, DownloadContext] = {}  # context_id -> DownloadContext
        self._handles: dict[int, lt.torrent_handle] = {}  # context_id -> handle
        self._handle_to_context: dict[str, int] = {}  # info_hash hex -> context_id
        self._should_stop = False
        self._poll_timer: QTimer | None = None

    def stop(self) -> None:
        """Request the service to stop gracefully and save state."""
        self._should_stop = True
        if self._poll_timer:
            self._poll_timer.stop()

    def run(self) -> None:
        """Start the torrent service main loop.

        Initializes the libtorrent session, restores state, and begins polling.
        """
        try:
            self._ensure_directories()
            self._init_session()
            self._load_session_state()
            self._load_resume_data()
            self._start_polling()

            # Keep thread alive
            while not self._should_stop:
                self.msleep(100)

            # Cleanup on stop
            self._save_session_state()
            self._save_resume_data()

        except Exception as e:
            logger.error("TorrentService failed: %s", e)

    def _ensure_directories(self) -> None:
        """Create required directories."""
        self._state_dir.mkdir(parents=True, exist_ok=True)
        self._download_dir.mkdir(parents=True, exist_ok=True)

    def _init_session(self) -> None:
        """Initialize the libtorrent session with optimal settings."""
        settings = {
            "user_agent": "Hackflix/1.0",
            "listen_interfaces": "0.0.0.0:6881",
            "enable_dht": True,
            "enable_lsd": True,
            "enable_upnp": True,
            "enable_natpmp": True,
            "alert_mask": (
                lt.alert.category_t.error_notification
                | lt.alert.category_t.status_notification
                | lt.alert.category_t.storage_notification
            ),
        }
        self._session = lt.session(settings)
        logger.info("Libtorrent session initialized")

    def _load_session_state(self) -> None:
        """Load session state (DHT nodes, etc.) from disk."""
        state_file = self._state_dir / self.SESSION_STATE_FILE
        if not state_file.exists():
            return

        try:
            state_data = state_file.read_bytes()
            self._session.load_state(lt.bdecode(state_data))
            logger.info("Session state loaded from %s", state_file)
        except Exception as e:
            logger.warning("Failed to load session state: %s", e)

    def _save_session_state(self) -> None:
        """Save session state to disk."""
        if not self._session:
            return
        state_file = self._state_dir / self.SESSION_STATE_FILE
        try:
            state_data = self._session.save_state()
            state_file.write_bytes(lt.bencode(state_data))
            logger.info("Session state saved to %s", state_file)
        except Exception as e:
            logger.warning("Failed to save session state: %s", e)

    def _load_resume_data(self) -> None:
        """Load resume data for torrents from disk."""
        resume_file = self._state_dir / self.RESUME_DATA_FILE
        if not resume_file.exists():
            return

        try:
            with open(resume_file, "rb") as f:
                resume_data: dict[int, dict[str, Any]] = pickle.load(f)

            for context_id, data in resume_data.items():
                if self._should_stop:
                    return
                try:
                    atp = lt.add_torrent_params()
                    atp.resume_data = data["resume_data"]
                    atp.save_path = data["save_path"]
                    handle = self._session.add_torrent(atp)
                    context = DownloadContext(
                        download_type=DownloadType(data["download_type"]),
                        id=data["context_db_id"],
                    )
                    self._register_handle(context_id, handle, context)
                    logger.info("Resumed torrent for context %d", context_id)
                except Exception as e:
                    logger.warning(
                        "Failed to resume torrent for context %d: %s", context_id, e
                    )

        except Exception as e:
            logger.warning("Failed to load resume data: %s", e)

    def _save_resume_data(self) -> None:
        """Save resume data for all active torrents."""
        if not self._session:
            return

        resume_file = self._state_dir / self.RESUME_DATA_FILE
        resume_data: dict[int, dict[str, Any]] = {}

        for context_id, handle in self._handles.items():
            if not handle.is_valid():
                continue
            try:
                handle.save_resume_data(
                    lt.torrent_handle.save_info_dict
                    | lt.torrent_handle.only_if_modified
                )
            except Exception as e:
                logger.warning(
                    "Failed to request resume data for context %d: %s", context_id, e
                )

        # Process alerts to get resume data
        self._session.wait_for_alert(1000)  # Wait up to 1 second
        alerts = self._session.pop_alerts()
        for alert in alerts:
            if isinstance(alert, lt.save_resume_data_alert):
                info_hash = str(alert.handle.info_hash())
                context_id = self._handle_to_context.get(info_hash)
                if context_id is not None:
                    context = self._contexts.get(context_id)
                    if context:
                        resume_data[context_id] = {
                            "resume_data": lt.write_resume_data_buf(alert),
                            "save_path": alert.handle.status().save_path,
                            "download_type": context.download_type.value,
                            "context_db_id": context.id,
                        }

        try:
            with open(resume_file, "wb") as f:
                pickle.dump(resume_data, f)
            logger.info("Resume data saved to %s", resume_file)
        except Exception as e:
            logger.warning("Failed to write resume data file: %s", e)

    def _start_polling(self) -> None:
        """Start the progress polling timer."""
        self._poll_timer = QTimer()
        self._poll_timer.timeout.connect(self._poll_progress)
        self._poll_timer.start(self._poll_interval)

    def _poll_progress(self) -> None:
        """Poll all active torrents for progress updates."""
        if self._should_stop or not self._session:
            return

        # Process alerts
        alerts = self._session.pop_alerts()
        for alert in alerts:
            self._handle_alert(alert)

        # Update progress for all handles
        for context_id, handle in list(self._handles.items()):
            if not handle.is_valid():
                continue

            context = self._contexts.get(context_id)
            if not context:
                continue

            status = handle.status()

            if status.state == lt.torrent_status.states.seeding:
                # Download complete
                self._on_download_complete(context_id, handle)
            elif status.state == lt.torrent_status.states.downloading:
                # Emit progress
                progress = int(status.progress * 100)
                self.download_progress.emit(
                    context.id,
                    progress,
                    status.download_rate / 1024,  # KB/s
                    status.upload_rate / 1024,
                )
                # Update DB based on context type
                if context.download_type == DownloadType.MOVIE:
                    self._db_manager.update_file_state(
                        context.id, DownloadState.DOWNLOADING, progress
                    )
                else:
                    self._db_manager.update_season_state(
                        context.id, DownloadState.DOWNLOADING, progress
                    )

    def _handle_alert(self, alert: Any) -> None:
        """Process a libtorrent alert.

        Args:
            alert: The alert to process.
        """
        if isinstance(alert, lt.torrent_error_alert):
            context_id = self._get_context_id_from_handle(alert.handle)
            if context_id is not None:
                context = self._contexts.get(context_id)
                if context:
                    error_msg = str(alert.error.message())
                    logger.error(
                        "Torrent error for %s %d: %s",
                        context.download_type.value,
                        context.id,
                        error_msg,
                    )
                    if context.download_type == DownloadType.MOVIE:
                        self._db_manager.update_file_state(context.id, DownloadState.ERROR)
                    else:
                        self._db_manager.update_season_state(context.id, DownloadState.ERROR)
                    self.download_error.emit(context.id, error_msg)
                    self._unregister_handle(context_id)

    def _on_download_complete(self, context_id: int, handle: lt.torrent_handle) -> None:
        """Handle download completion.

        Routes to appropriate handler based on download type (movie or season).

        Args:
            context_id: Internal context ID for tracking.
            handle: Torrent handle.
        """
        context = self._contexts.get(context_id)
        if not context:
            logger.error("No context found for context_id %d", context_id)
            return

        if context.download_type == DownloadType.MOVIE:
            self._complete_movie_download(context, handle)
        else:
            self._complete_season_download(context, handle)

        # Remove from active handles (stop seeding)
        self._session.remove_torrent(handle)
        self._unregister_handle(context_id)

    def _complete_movie_download(
        self, context: DownloadContext, handle: lt.torrent_handle
    ) -> None:
        """Handle movie download completion.

        Finds the largest video file and updates the database.

        Args:
            context: Download context with video_file_id.
            handle: Torrent handle.
        """
        video_path = self._find_largest_video(handle)
        file_id = context.id

        if video_path:
            self._db_manager.update_file_state(file_id, DownloadState.COMPLETED, 100)
            self._db_manager.update_file_path(file_id, str(video_path))
            self.download_completed.emit(file_id, str(video_path))
            logger.info("Movie download completed for file %d: %s", file_id, video_path)
        else:
            error_msg = "No video file found in torrent"
            logger.error("Download error for movie file %d: %s", file_id, error_msg)
            self._db_manager.update_file_state(file_id, DownloadState.ERROR)
            self.download_error.emit(file_id, error_msg)

    def _complete_season_download(
        self, context: DownloadContext, handle: lt.torrent_handle
    ) -> None:
        """Handle season pack download completion.

        Matches video files to episodes and updates all video_files records.

        Args:
            context: Download context with season_id.
            handle: Torrent handle.
        """
        season_id = context.id
        episodes = self._db_manager.get_episodes(season_id)

        if not episodes:
            error_msg = "No episodes found for season"
            logger.error("Download error for season %d: %s", season_id, error_msg)
            self._db_manager.update_season_state(season_id, DownloadState.ERROR)
            self.download_error.emit(season_id, error_msg)
            return

        video_files = self._get_video_files_from_torrent(handle)
        if not video_files:
            error_msg = "No video files found in torrent"
            logger.error("Download error for season %d: %s", season_id, error_msg)
            self._db_manager.update_season_state(season_id, DownloadState.ERROR)
            self.download_error.emit(season_id, error_msg)
            return

        # Match files to episodes
        matches = self._match_episode_files(episodes, video_files)

        if not matches:
            error_msg = "Could not match any video files to episodes"
            logger.error("Download error for season %d: %s", season_id, error_msg)
            self._db_manager.update_season_state(season_id, DownloadState.ERROR)
            self.download_error.emit(season_id, error_msg)
            return

        # Update each matched episode
        for episode_id, video_path in matches.items():
            self._db_manager.update_file_state(episode_id, DownloadState.COMPLETED, 100)
            self._db_manager.update_file_path(episode_id, str(video_path))
            self.download_completed.emit(episode_id, str(video_path))
            logger.info("Episode %d completed: %s", episode_id, video_path)

        # Mark season as completed
        self._db_manager.update_season_state(season_id, DownloadState.COMPLETED, 100)
        logger.info(
            "Season %d download completed: %d/%d episodes matched",
            season_id,
            len(matches),
            len(episodes),
        )

    def _get_video_files_from_torrent(
        self, handle: lt.torrent_handle
    ) -> list[tuple[Path, int]]:
        """Get all video files from a torrent.

        Args:
            handle: Torrent handle.

        Returns:
            List of (file_path, file_size) tuples for video files.
        """
        torrent_info = handle.torrent_file()
        if not torrent_info:
            return []

        save_path = Path(handle.status().save_path)
        video_files: list[tuple[Path, int]] = []

        files = torrent_info.files()
        for i in range(files.num_files()):
            file_path = save_path / files.file_path(i)
            file_size = files.file_size(i)
            ext = file_path.suffix.lower()

            if ext in VIDEO_EXTENSIONS:
                video_files.append((file_path, file_size))

        return video_files

    def _match_episode_files(
        self, episodes: list[dict[str, Any]], video_files: list[tuple[Path, int]]
    ) -> dict[int, Path]:
        """Match video files to episodes based on episode numbers.

        Matches files by looking for episode number patterns in filenames:
        - S01E05 or s01e05
        - 1x05 or 1X05
        - Episode 5 or episode 5
        - E05 or e05
        - .105. (season 1 episode 5)

        Args:
            episodes: List of episode dicts from database with 'id' and 'episode_number'.
            video_files: List of (path, size) tuples for video files in torrent.

        Returns:
            Dictionary mapping video_file_id -> matched video path.
        """
        matches: dict[int, Path] = {}

        for episode in episodes:
            episode_id = episode["id"]
            episode_num = episode["episode_number"]

            best_match: tuple[Path | None, int] = (None, 0)

            for file_path, file_size in video_files:
                filename = file_path.name

                # Extract episode number from filename
                extracted_num = self._extract_episode_number(filename)

                if extracted_num == episode_num and file_size > best_match[1]:
                    best_match = (file_path, file_size)

            if best_match[0]:
                matches[episode_id] = best_match[0]

        return matches

    def _extract_episode_number(self, filename: str) -> int | None:
        """Extract episode number from a filename.

        Args:
            filename: The filename to parse.

        Returns:
            Episode number or None if not found.
        """
        # Patterns in order of specificity
        patterns = [
            # S01E05, s01e05
            r"[Ss]\d{1,2}[Ee](\d{1,3})",
            # 1x05, 1X05
            r"\d{1,2}[xX](\d{1,3})",
            # Episode 5, episode 5, EP5, ep5
            r"[Ee](?:pisode)?[\s._-]*(\d{1,3})",
            # .105. (single digit season, two digit episode)
            r"\.(\d)(\d{2})\.",
        ]

        for i, pattern in enumerate(patterns):
            match = re.search(pattern, filename)
            if match:
                if i == 3:  # Special case for .105. pattern
                    # This matches season+episode concatenated, extract episode part
                    return int(match.group(2))
                return int(match.group(1))

        return None

    def _find_largest_video(self, handle: lt.torrent_handle) -> Path | None:
        """Find the largest video file in a completed torrent.

        Args:
            handle: Torrent handle.

        Returns:
            Path to largest video file or None.
        """
        torrent_info = handle.torrent_file()
        if not torrent_info:
            return None

        save_path = Path(handle.status().save_path)
        largest_video: tuple[Path | None, int] = (None, 0)

        files = torrent_info.files()
        for i in range(files.num_files()):
            file_path = save_path / files.file_path(i)
            file_size = files.file_size(i)
            ext = file_path.suffix.lower()

            if ext in VIDEO_EXTENSIONS and file_size > largest_video[1]:
                largest_video = (file_path, file_size)

        return largest_video[0]

    def add_magnet(
        self,
        context: DownloadContext,
        magnet_link: str,
        sequential: bool = False,
    ) -> bool:
        """Add a magnet link for download.

        Args:
            context: Download context specifying type and ID.
                     For movies: DownloadContext(DownloadType.MOVIE, video_file_id)
                     For seasons: DownloadContext(DownloadType.SEASON, season_id)
            magnet_link: Magnet URI.
            sequential: Enable sequential download (for streaming/series).

        Returns:
            True if torrent was added successfully.
        """
        if not self._session:
            logger.error("Cannot add magnet: session not initialized")
            return False

        # Use context.id as the unique identifier for tracking
        context_id = context.id
        if context_id in self._handles:
            logger.warning(
                "Torrent already exists for %s %d",
                context.download_type.value,
                context_id,
            )
            return False

        try:
            atp = lt.parse_magnet_uri(magnet_link)
            atp.save_path = str(self._download_dir)

            handle = self._session.add_torrent(atp)

            if sequential:
                handle.set_sequential_download(True)

            self._register_handle(context_id, handle, context)

            # Update DB state based on context type
            if context.download_type == DownloadType.MOVIE:
                self._db_manager.update_file_state(context.id, DownloadState.QUEUED)
            else:
                self._db_manager.update_season_state(context.id, DownloadState.QUEUED)

            logger.info(
                "Added magnet for %s %d (sequential=%s)",
                context.download_type.value,
                context.id,
                sequential,
            )
            return True

        except Exception as e:
            logger.error(
                "Failed to add magnet for %s %d: %s",
                context.download_type.value,
                context.id,
                e,
            )
            if context.download_type == DownloadType.MOVIE:
                self._db_manager.update_file_state(context.id, DownloadState.ERROR)
            else:
                self._db_manager.update_season_state(context.id, DownloadState.ERROR)
            self.download_error.emit(context.id, str(e))
            return False

    def cancel_download(self, context: DownloadContext) -> bool:
        """Cancel an active download.

        Args:
            context: Download context to cancel.

        Returns:
            True if download was cancelled.
        """
        context_id = context.id
        if context_id not in self._handles:
            return False

        handle = self._handles[context_id]
        if handle.is_valid() and self._session:
            self._session.remove_torrent(handle)

        self._unregister_handle(context_id)

        # Reset DB state based on context type
        if context.download_type == DownloadType.MOVIE:
            self._db_manager.update_file_state(context.id, DownloadState.PENDING)
        else:
            self._db_manager.update_season_state(context.id, DownloadState.PENDING)

        logger.info(
            "Cancelled download for %s %d", context.download_type.value, context.id
        )
        return True

    def get_active_downloads(self) -> list[DownloadContext]:
        """Get list of active download contexts.

        Returns:
            List of DownloadContext objects for currently active downloads.
        """
        return list(self._contexts.values())

    def _register_handle(
        self, context_id: int, handle: lt.torrent_handle, context: DownloadContext
    ) -> None:
        """Register a torrent handle mapping."""
        self._contexts[context_id] = context
        self._handles[context_id] = handle
        info_hash = str(handle.info_hash())
        self._handle_to_context[info_hash] = context_id

    def _unregister_handle(self, context_id: int) -> None:
        """Unregister a torrent handle mapping."""
        self._contexts.pop(context_id, None)
        if context_id in self._handles:
            handle = self._handles.pop(context_id)
            info_hash = str(handle.info_hash())
            self._handle_to_context.pop(info_hash, None)

    def _get_context_id_from_handle(self, handle: lt.torrent_handle) -> int | None:
        """Get context ID from a torrent handle."""
        info_hash = str(handle.info_hash())
        return self._handle_to_context.get(info_hash)
