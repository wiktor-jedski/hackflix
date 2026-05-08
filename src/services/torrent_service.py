"""Torrent download service for Hackflix.

This module provides the TorrentService class for managing torrent downloads
using the embedded libtorrent library.
"""

import logging
import json
import os
import pickle
import re
import select
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QThread, QTimer, Signal

from src.config import (
    DownloadState,
    MEDIA_LIBRARY_PATH,
    TORRENT_POLL_INTERVAL_MS,
    TORRENT_STATE_DIR,
)
from src.database.db_manager import DatabaseManager

logger = logging.getLogger(__name__)


class _LazyLibtorrent:
    """Import libtorrent only when the embedded backend is used."""

    def __getattr__(self, name: str) -> Any:
        import libtorrent as libtorrent

        return getattr(libtorrent, name)


lt = _LazyLibtorrent()

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

    download_progress = Signal(int, int, float, float)  # context_id, %, down, up
    download_completed = Signal(int, str)  # video_file_id, file_path
    download_error = Signal(int, str)  # context_id, error_message
    season_completed = Signal(int)  # season_id

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

        self._session: Any | None = None
        self._contexts: dict[int, DownloadContext] = {}  # context_id -> DownloadContext
        self._handles: dict[int, Any] = {}
        self._handle_to_context: dict[str, int] = {}  # info_hash hex -> context_id
        self._should_stop = False
        self._poll_timer: QTimer | None = None
        self._session_lock = threading.RLock()
        self._ready_event = threading.Event()
        self._use_process_backend = (
            os.environ.get("HACKFLIX_TORRENT_BACKEND", "process") == "process"
        )
        self._worker_process: subprocess.Popen[str] | None = None
        self._worker_lock = threading.RLock()
        self._pending_commands: list[dict[str, Any]] = []
        self._last_worker_progress_log: dict[int, tuple[float, str, int, int]] = {}
        self._last_worker_progress_emit: dict[int, tuple[float, int, str, bool]] = {}

    def stop(self) -> None:
        """Request the service to stop gracefully and save state."""
        self._should_stop = True
        if self._poll_timer:
            self._poll_timer.stop()
        if self._use_process_backend:
            self._send_worker_command({"command": "stop"})

    def wait_until_ready(self, timeout_ms: int = 5000) -> bool:
        """Wait for the libtorrent session to be initialized.

        Args:
            timeout_ms: Maximum time to wait in milliseconds.

        Returns:
            True if the session is ready, otherwise False.
        """
        return self._ready_event.wait(timeout_ms / 1000)

    def run(self) -> None:
        """Start the torrent service main loop.

        Initializes the libtorrent session, restores state, and begins polling.
        """
        if self._use_process_backend:
            self._run_process_backend()
            return

        try:
            self._ensure_directories()
            self._init_session()
            self._load_session_state()
            self._load_resume_data()
            self._ready_event.set()

            # Poll manually since QTimer doesn't work without event loop
            poll_counter = 0
            while not self._should_stop:
                self.msleep(100)
                poll_counter += 1
                # Poll every 1 second (10 * 100ms)
                if poll_counter >= 10:
                    poll_counter = 0
                    self._poll_progress()

            # Cleanup on stop
            self._save_session_state()
            self._save_resume_data()

        except Exception as e:
            logger.error("TorrentService failed: %s", e)
            self._ready_event.set()

    def _run_process_backend(self) -> None:
        """Run the torrent backend in a separate Python process."""
        try:
            self._ensure_directories()
            self._worker_process = subprocess.Popen(
                [sys.executable, "-m", "src.services.torrent_worker"],
                cwd=str(Path(__file__).resolve().parents[2]),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
            logger.info("Torrent worker process started")

            while not self._should_stop and self._worker_process.poll() is None:
                if self._worker_process.stdout is None:
                    break
                readable, _, _ = select.select([self._worker_process.stdout], [], [], 0.5)
                if not readable:
                    continue
                line = self._worker_process.stdout.readline()
                if not line:
                    continue
                self._handle_worker_event(json.loads(line))

            if self._worker_process.poll() is not None:
                stderr = ""
                if self._worker_process.stderr is not None:
                    stderr = self._worker_process.stderr.read()
                logger.error("Torrent worker exited: %s", stderr.strip())
        except Exception as e:
            logger.error("Torrent process backend failed: %s", e)
            self._ready_event.set()
        finally:
            process = self._worker_process
            if process and process.poll() is None:
                self._send_worker_command({"command": "stop"})
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)

    def _handle_worker_event(self, event: dict[str, Any]) -> None:
        """Handle one event from the torrent worker process."""
        event_name = event.get("event")
        if event_name == "ready":
            logger.info(
                "Torrent worker ready (listen_interfaces=%s)",
                event.get("listen_interfaces", "unknown"),
            )
            self._ready_event.set()
            with self._worker_lock:
                pending = list(self._pending_commands)
                self._pending_commands.clear()
            for command in pending:
                self._send_worker_command(command)
            return

        context_id = int(event.get("id", 0))
        if event_name == "progress":
            if not self._should_emit_worker_progress(context_id, event):
                return
            self._log_worker_progress(context_id, event)
            self.download_progress.emit(
                context_id,
                int(event["progress"]),
                float(event["download_rate"]),
                float(event["upload_rate"]),
            )
        elif event_name == "completed":
            logger.info("Torrent worker completed context %d: %s", context_id, event["path"])
            self.download_completed.emit(context_id, str(event["path"]))
            self._unregister_handle(context_id)
        elif event_name == "season_completed":
            logger.info("Torrent worker completed season context %d", context_id)
            self._complete_worker_season_download(context_id, event)
            self._unregister_handle(context_id)
        elif event_name == "error":
            logger.error(
                "Torrent worker error for context %d: %s",
                context_id,
                event.get("message", ""),
            )
            self.download_error.emit(context_id, str(event.get("message", "")))
            self._unregister_handle(context_id)
        elif event_name == "added":
            logger.info("Torrent worker added context %d", context_id)
        elif event_name == "tracker_error":
            logger.warning(
                "Torrent tracker error for context %d (%s): %s",
                context_id,
                event.get("url", ""),
                event.get("message", ""),
            )
        elif event_name == "metadata_received":
            logger.info("Torrent metadata received for context %d", context_id)

    def _should_emit_worker_progress(self, context_id: int, event: dict[str, Any]) -> bool:
        """Return true when progress should update the app state."""
        now = time.monotonic()
        progress = int(event.get("progress", 0))
        state = str(event.get("state", "unknown"))
        has_metadata = bool(event.get("has_metadata", False))
        previous = self._last_worker_progress_emit.get(context_id)

        if previous is None:
            self._last_worker_progress_emit[context_id] = (
                now,
                progress,
                state,
                has_metadata,
            )
            return True

        last_time, last_progress, last_state, last_has_metadata = previous
        should_emit = (
            progress != last_progress
            or state != last_state
            or has_metadata != last_has_metadata
            or now - last_time >= 10
        )
        if should_emit:
            self._last_worker_progress_emit[context_id] = (
                now,
                progress,
                state,
                has_metadata,
            )
        return should_emit

    def _log_worker_progress(self, context_id: int, event: dict[str, Any]) -> None:
        """Log worker progress when state changes or enough time has passed."""
        now = time.monotonic()
        state = str(event.get("state", "unknown"))
        peers = int(event.get("peers", 0))
        seeds = int(event.get("seeds", 0))
        previous = self._last_worker_progress_log.get(context_id)
        if previous and previous[1:] == (state, peers, seeds) and now - previous[0] < 15:
            return

        self._last_worker_progress_log[context_id] = (now, state, peers, seeds)
        logger.info(
            (
                "Torrent worker progress context=%d state=%s progress=%d%% "
                "peers=%d seeds=%d metadata=%s down=%.1f KiB/s total=%d/%d"
            ),
            context_id,
            state,
            int(event.get("progress", 0)),
            peers,
            seeds,
            event.get("has_metadata", False),
            float(event.get("download_rate", 0.0)),
            int(event.get("total_wanted_done", 0)),
            int(event.get("total_wanted", 0)),
        )

    def _complete_worker_season_download(
        self, season_id: int, event: dict[str, Any]
    ) -> None:
        """Match worker-reported season files to episode rows."""
        episodes = self._db_manager.get_episodes(season_id)
        if not episodes:
            error_msg = "No episodes found for season"
            logger.error("Download error for season %d: %s", season_id, error_msg)
            self.download_error.emit(season_id, error_msg)
            return

        video_files = [
            (Path(str(file_data["path"])), int(file_data["size"]))
            for file_data in event.get("files", [])
            if file_data.get("path") and file_data.get("size") is not None
        ]
        if not video_files:
            error_msg = "No video files found in torrent"
            logger.error("Download error for season %d: %s", season_id, error_msg)
            self.download_error.emit(season_id, error_msg)
            return

        matches = self._match_episode_files(episodes, video_files)
        if not matches:
            error_msg = "Could not match any video files to episodes"
            logger.error("Download error for season %d: %s", season_id, error_msg)
            self.download_error.emit(season_id, error_msg)
            return

        for episode_id, video_path in matches.items():
            self.download_completed.emit(episode_id, str(video_path))
            logger.info("Episode %d completed: %s", episode_id, video_path)

        self.season_completed.emit(season_id)
        logger.info(
            "Season %d download completed: %d/%d episodes matched",
            season_id,
            len(matches),
            len(episodes),
        )

    def _send_worker_command(self, command: dict[str, Any]) -> bool:
        """Send a JSON command to the worker process."""
        with self._worker_lock:
            process = self._worker_process
            if process is None or process.stdin is None or process.poll() is not None:
                self._pending_commands.append(command)
                return False

            try:
                process.stdin.write(json.dumps(command) + "\n")
                process.stdin.flush()
                return True
            except BrokenPipeError:
                self._pending_commands.append(command)
                return False

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
                lt.alert.category_t.error_notification  # type: ignore[attr-defined]
                | lt.alert.category_t.status_notification  # type: ignore[attr-defined]
                | lt.alert.category_t.storage_notification  # type: ignore[attr-defined]
            ),
        }
        with self._session_lock:
            self._session = lt.session(settings)  # type: ignore[attr-defined]
        logger.info("Libtorrent session initialized")

    def _load_session_state(self) -> None:
        """Load session state (DHT nodes, etc.) from disk."""
        state_file = self._state_dir / self.SESSION_STATE_FILE
        if not state_file.exists():
            return

        try:
            state_data = state_file.read_bytes()
            with self._session_lock:
                self._session.load_state(lt.bdecode(state_data))  # type: ignore[attr-defined]
            logger.info("Session state loaded from %s", state_file)
        except Exception as e:
            logger.warning("Failed to load session state: %s", e)

    def _save_session_state(self) -> None:
        """Save session state to disk."""
        if not self._session:
            return
        state_file = self._state_dir / self.SESSION_STATE_FILE
        try:
            with self._session_lock:
                state_data = self._session.save_state()
            state_file.write_bytes(lt.bencode(state_data))  # type: ignore[attr-defined]
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
                    atp = lt.add_torrent_params()  # type: ignore[attr-defined]
                    atp.resume_data = data["resume_data"]
                    atp.save_path = data["save_path"]
                    context = DownloadContext(
                        download_type=DownloadType(data["download_type"]),
                        id=data["context_db_id"],
                    )
                    with self._session_lock:
                        handle = self._session.add_torrent(atp)  # type: ignore[union-attr]
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

        with self._session_lock:
            for context_id, handle in self._handles.items():
                if not handle.is_valid():
                    continue
                try:
                    handle.save_resume_data(
                        lt.torrent_handle.save_info_dict  # type: ignore[attr-defined]
                        | lt.torrent_handle.only_if_modified  # type: ignore[attr-defined]
                    )
                except Exception as e:
                    logger.warning(
                        "Failed to request resume data for context %d: %s", context_id, e
                    )

            # Process alerts to get resume data
            self._session.wait_for_alert(1000)  # Wait up to 1 second
            alerts = self._session.pop_alerts()
            for alert in alerts:
                if isinstance(alert, lt.save_resume_data_alert):  # type: ignore[attr-defined]
                    info_hash = str(alert.handle.info_hash())
                    context_id = self._handle_to_context.get(info_hash)
                    if context_id is not None:
                        context = self._contexts.get(context_id)
                        if context:
                            resume_data[context_id] = {
                                "resume_data": lt.write_resume_data_buf(alert),  # type: ignore[attr-defined]
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

        with self._session_lock:
            # Process alerts
            alerts = self._session.pop_alerts()
            for alert in alerts:
                self._handle_alert(alert)

            # Update progress for all handles
            for context_id, handle in list(self._handles.items()):
                if not handle.is_valid():
                    logger.debug("Handle for context %d is invalid", context_id)
                    continue

                context = self._contexts.get(context_id)
                if not context:
                    logger.debug("No context for context_id %d", context_id)
                    continue

                status = handle.status()
                state_name = str(status.state)
                progress = int(status.progress * 100)
                logger.debug(
                    "Torrent %d: state=%s, progress=%d%%, peers=%d, seeds=%d",
                    context_id,
                    state_name,
                    progress,
                    status.num_peers,
                    status.num_seeds,
                )

                if status.state == lt.torrent_status.states.seeding:  # type: ignore[attr-defined]
                    # Download complete
                    self._on_download_complete(context_id, handle)
                elif status.state in (
                    lt.torrent_status.states.downloading,  # type: ignore[attr-defined]
                    lt.torrent_status.states.downloading_metadata,  # type: ignore[attr-defined]
                    lt.torrent_status.states.checking_files,  # type: ignore[attr-defined]
                    lt.torrent_status.states.checking_resume_data,  # type: ignore[attr-defined]
                ):
                    # Emit progress for all active download states
                    self.download_progress.emit(
                        context.id,
                        progress,
                        status.download_rate / 1024,  # KB/s
                        status.upload_rate / 1024,
                    )

    def _handle_alert(self, alert: Any) -> None:
        """Process a libtorrent alert.

        Args:
            alert: The alert to process.
        """
        if isinstance(alert, lt.torrent_error_alert):  # type: ignore[attr-defined]
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
                    self.download_error.emit(context.id, error_msg)
                    self._unregister_handle(context_id)

    def _on_download_complete(self, context_id: int, handle: Any) -> None:
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
        self._session.remove_torrent(handle)  # type: ignore[union-attr]
        self._unregister_handle(context_id)

    def _complete_movie_download(self, context: DownloadContext, handle: Any) -> None:
        """Handle movie download completion.

        Finds the largest video file and updates the database.

        Args:
            context: Download context with video_file_id.
            handle: Torrent handle.
        """
        video_path = self._find_largest_video(handle)
        file_id = context.id

        if video_path:
            self.download_completed.emit(file_id, str(video_path))
            logger.info("Movie download completed for file %d: %s", file_id, video_path)
        else:
            error_msg = "No video file found in torrent"
            logger.error("Download error for movie file %d: %s", file_id, error_msg)
            self.download_error.emit(file_id, error_msg)

    def _complete_season_download(self, context: DownloadContext, handle: Any) -> None:
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
            self.download_error.emit(season_id, error_msg)
            return

        video_files = self._get_video_files_from_torrent(handle)
        if not video_files:
            error_msg = "No video files found in torrent"
            logger.error("Download error for season %d: %s", season_id, error_msg)
            self.download_error.emit(season_id, error_msg)
            return

        # Match files to episodes
        matches = self._match_episode_files(episodes, video_files)

        if not matches:
            error_msg = "Could not match any video files to episodes"
            logger.error("Download error for season %d: %s", season_id, error_msg)
            self.download_error.emit(season_id, error_msg)
            return

        # Update each matched episode
        for episode_id, video_path in matches.items():
            self.download_completed.emit(episode_id, str(video_path))
            logger.info("Episode %d completed: %s", episode_id, video_path)

        self.season_completed.emit(season_id)
        logger.info(
            "Season %d download completed: %d/%d episodes matched",
            season_id,
            len(matches),
            len(episodes),
        )

    def _get_video_files_from_torrent(self, handle: Any) -> list[tuple[Path, int]]:
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
            # Episode 5, episode 5 (requires word boundary or separator before)
            r"(?:^|[.\s_-])[Ee]pisode[\s._-]*(\d{1,3})",
            # EP5, ep5, E5, e5 (standalone, requires separator before and after)
            r"(?:^|[.\s_-])[Ee][Pp]?(\d{1,3})(?:[.\s_-]|$)",
            # .105. (single digit season, two digit episode, surrounded by dots)
            r"\.(\d)(\d{2})\.",
        ]

        for i, pattern in enumerate(patterns):
            match = re.search(pattern, filename)
            if match:
                if i == 4:  # Special case for .105. pattern
                    # This matches season+episode concatenated, extract episode part
                    return int(match.group(2))
                return int(match.group(1))

        return None

    def _find_largest_video(self, handle: Any) -> Path | None:
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
        if self._use_process_backend:
            context_id = context.id
            if context_id in self._contexts:
                logger.warning(
                    "Torrent already exists for %s %d",
                    context.download_type.value,
                    context_id,
                )
                return False

            self._contexts[context_id] = context
            command = {
                "command": "add",
                "type": context.download_type.value,
                "id": context.id,
                "magnet": magnet_link,
                "download_dir": str(self._download_dir),
                "sequential": sequential,
            }
            self._send_worker_command(command)

            if context.download_type == DownloadType.MOVIE:
                self._db_manager.update_file_state(context.id, DownloadState.QUEUED)
            else:
                self._db_manager.update_season_state(context.id, DownloadState.QUEUED)

            logger.info(
                "Queued magnet for %s %d in torrent worker (sequential=%s)",
                context.download_type.value,
                context.id,
                sequential,
            )
            return True

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
            atp = lt.parse_magnet_uri(magnet_link)  # type: ignore[attr-defined]
            atp.save_path = str(self._download_dir)

            with self._session_lock:
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
        if self._use_process_backend:
            if context_id not in self._contexts:
                return False

            self._send_worker_command({"command": "cancel", "id": context_id})
            self._contexts.pop(context_id, None)

            if context.download_type == DownloadType.MOVIE:
                self._db_manager.update_file_state(context.id, DownloadState.PENDING)
            else:
                self._db_manager.update_season_state(context.id, DownloadState.PENDING)

            logger.info(
                "Cancelled download for %s %d", context.download_type.value, context.id
            )
            return True

        if context_id not in self._handles:
            return False

        handle = self._handles[context_id]
        with self._session_lock:
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
        self, context_id: int, handle: Any, context: DownloadContext
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

    def _get_context_id_from_handle(self, handle: Any) -> int | None:
        """Get context ID from a torrent handle."""
        info_hash = str(handle.info_hash())
        return self._handle_to_context.get(info_hash)
