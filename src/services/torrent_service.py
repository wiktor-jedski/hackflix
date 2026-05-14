"""Torrent download service for Hackflix.

This module provides the TorrentService class for managing torrent downloads
using the embedded libtorrent library.
"""

import logging
import json
import os
import pickle
import queue
import re
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from src.qt import QObject, QTimer, Signal

from src.config import (
    DownloadState,
    MEDIA_LIBRARY_PATH,
    TORRENT_POLL_INTERVAL_MS,
    TORRENT_STATE_DIR,
)
from src.database.db_manager import DatabaseManager
from src.utils.media_duration import probe_duration_seconds

logger = logging.getLogger(__name__)


class _LazyLibtorrent:
    """Import libtorrent only when the embedded backend is used."""

    def __getattr__(self, name: str) -> Any:
        import libtorrent as libtorrent

        return getattr(libtorrent, name)


lt = _LazyLibtorrent()

# Video file extensions to identify the main content
VIDEO_EXTENSIONS = frozenset({".mkv", ".mp4", ".avi", ".webm", ".mov", ".wmv", ".flv"})
VideoFileMatch = tuple[Path, int, int]


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


@dataclass
class _WorkerQueueItem:
    """Queue item produced by process reader threads."""

    kind: str
    payload: dict[str, Any] | str


class TorrentService(QObject):
    """Torrent download coordinator.

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
        duration_detected: Emitted with (video_file_id: int, duration_seconds: int).
        download_error: Emitted with (context_id: int, error_message: str).
                       For movies: video_file_id. For seasons: season_id.
    """

    download_progress = Signal(int, int, float, float)  # context_id, %, down, up
    download_completed = Signal(int, str)  # video_file_id, file_path
    duration_detected = Signal(int, int)  # video_file_id, duration_seconds
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
        self._contexts: dict[int, DownloadContext] = {}  # worker_id -> DownloadContext
        self._handles: dict[int, Any] = {}
        self._handle_to_context: dict[str, int] = {}  # info_hash hex -> worker_id
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
        self._worker_events: queue.Queue[_WorkerQueueItem] = queue.Queue()
        self._worker_ready = False
        self._worker_stdout_thread: threading.Thread | None = None
        self._stderr_thread: threading.Thread | None = None
        self._embedded_thread: threading.Thread | None = None
        self._running = False

    def start(self) -> None:
        """Start the torrent service."""
        if self._running:
            return

        self._should_stop = False
        self._ready_event.clear()
        self._running = True

        if self._use_process_backend:
            self._start_process_backend()
            return

        self._embedded_thread = threading.Thread(
            target=self.run,
            name="TorrentServiceEmbedded",
            daemon=True,
        )
        self._embedded_thread.start()

    def isRunning(self) -> bool:
        """Return whether the service lifecycle is active."""
        return self._running

    def wait(self, timeout_ms: int | None = None) -> bool:
        """Wait for the service to stop.

        Args:
            timeout_ms: Optional maximum wait in milliseconds.

        Returns:
            True when the service stopped before the timeout.
        """
        timeout = None if timeout_ms is None else timeout_ms / 1000
        deadline = None if timeout is None else time.monotonic() + timeout

        if self._use_process_backend:
            self._wait_for_worker_process(deadline)
            for thread in (self._worker_stdout_thread, self._stderr_thread):
                if thread is None:
                    continue
                remaining = self._remaining_timeout(deadline)
                thread.join(remaining)
            self._mark_process_stopped()
            return not self._running

        if self._embedded_thread is not None:
            self._embedded_thread.join(timeout)
            if self._embedded_thread.is_alive():
                return False
        self._running = False
        return True

    def stop(self) -> None:
        """Request the service to stop gracefully and save state."""
        self._should_stop = True
        if self._poll_timer:
            self._poll_timer.stop()
        if self._use_process_backend:
            self._send_worker_command({"command": "stop"})
            process = self._worker_process
            if process and process.stdin:
                try:
                    process.stdin.close()
                except OSError as e:
                    logger.debug("Failed to close torrent worker stdin: %s", e)

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
            self._start_process_backend()
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
                time.sleep(0.1)
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
        finally:
            self._running = False

    def _start_process_backend(self) -> None:
        """Start the torrent backend in a separate Python process."""
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
            self._worker_ready = False
            self._worker_stdout_thread = threading.Thread(
                target=self._drain_worker_stdout,
                name="TorrentWorkerStdout",
                daemon=True,
            )
            self._stderr_thread = threading.Thread(
                target=self._drain_worker_stderr,
                name="TorrentWorkerStderr",
                daemon=True,
            )
            self._worker_stdout_thread.start()
            self._stderr_thread.start()
            self._start_worker_event_drain()
            logger.info("Torrent worker process started")
        except Exception as e:
            logger.error("Torrent process backend failed: %s", e)
            self._ready_event.set()
            self._running = False

    def _run_process_backend(self) -> None:
        """Compatibility wrapper for older tests and callers."""
        self._start_process_backend()

    def _start_worker_event_drain(self) -> None:
        """Start the GUI-thread timer that drains worker reader events."""
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._drain_worker_events)
        self._poll_timer.start(100)

    def _handle_worker_line(self, line: str) -> None:
        """Parse and enqueue one worker stdout line."""
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            self._worker_events.put(_WorkerQueueItem("malformed", line))
            return
        if not isinstance(event, dict):
            self._worker_events.put(_WorkerQueueItem("malformed", line))
            return
        if event.get("event") == "ready":
            self._ready_event.set()
        self._worker_events.put(_WorkerQueueItem("event", event))

    def _drain_worker_stdout(self) -> None:
        """Read worker stdout in a plain Python thread."""
        process = self._worker_process
        if process is None or process.stdout is None:
            return

        try:
            for line in process.stdout:
                self._handle_worker_line(line)
        except OSError as e:
            self._worker_events.put(_WorkerQueueItem("reader_error", str(e)))

    def _drain_worker_stderr(self) -> None:
        """Continuously read worker stderr so the pipe cannot block the process."""
        process = self._worker_process
        if process is None or process.stderr is None:
            return

        try:
            for line in process.stderr:
                self._worker_events.put(_WorkerQueueItem("stderr", line.rstrip()))
        except OSError as e:
            self._worker_events.put(_WorkerQueueItem("reader_error", str(e)))

    def _drain_worker_events(self) -> None:
        """Drain process worker events on the Qt-owned service thread."""
        while True:
            try:
                item = self._worker_events.get_nowait()
            except queue.Empty:
                break

            if item.kind == "event":
                if isinstance(item.payload, dict):
                    self._handle_worker_event(item.payload)
            elif item.kind == "stderr":
                logger.warning("Torrent worker stderr: %s", item.payload)
            elif item.kind == "reader_error":
                logger.error("Torrent worker reader failed: %s", item.payload)
            elif item.kind == "malformed":
                logger.warning(
                    "Ignoring malformed torrent worker output: %r", item.payload
                )

        process = self._worker_process
        if process is not None and process.poll() is not None:
            logger.error("Torrent worker exited with code %s", process.returncode)
            self._mark_process_stopped()

    def _mark_process_stopped(self) -> None:
        """Mark the process backend stopped and stop its GUI drain timer."""
        if self._poll_timer:
            self._poll_timer.stop()
        self._worker_ready = False
        self._running = False

    def _wait_for_worker_process(self, deadline: float | None) -> None:
        """Wait for the worker process, killing it if a bounded wait expires."""
        process = self._worker_process
        if process is None:
            return
        if process.poll() is not None:
            return

        remaining = self._remaining_timeout(deadline)
        if remaining is None:
            remaining = 5.0
        try:
            process.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)

    def _remaining_timeout(self, deadline: float | None) -> float | None:
        """Return seconds remaining until deadline."""
        if deadline is None:
            return None
        return max(0.0, deadline - time.monotonic())

    def _context_id(self, context: DownloadContext) -> int:
        """Return a process-safe context ID namespaced by download type."""
        if not self._use_process_backend:
            return context.id
        if context.download_type == DownloadType.SEASON:
            return -context.id
        return context.id

    def _context_db_id(self, context_id: int) -> int:
        """Return the database ID encoded in a worker context ID."""
        return abs(context_id)

    def _handle_worker_event(self, event: dict[str, Any]) -> None:
        """Handle one event from the torrent worker process."""
        event_name = event.get("event")
        if event_name == "ready":
            logger.info(
                "Torrent worker ready (listen_interfaces=%s)",
                event.get("listen_interfaces", "unknown"),
            )
            self._ready_event.set()
            self._worker_ready = True
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
            context = self._contexts.get(context_id)
            db_id = context.id if context else self._context_db_id(context_id)
            self.download_progress.emit(
                db_id,
                int(event["progress"]),
                float(event["download_rate"]),
                float(event["upload_rate"]),
            )
        elif event_name == "completed":
            context = self._contexts.get(context_id)
            file_id = context.id if context else self._context_db_id(context_id)
            logger.info(
                "Torrent worker completed context %d: %s", context_id, event["path"]
            )
            self.download_completed.emit(file_id, str(event["path"]))
            duration_seconds = int(event.get("duration_seconds") or 0)
            if duration_seconds > 0:
                self.duration_detected.emit(file_id, duration_seconds)
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
            context = self._contexts.get(context_id)
            self.download_error.emit(
                context.id if context else self._context_db_id(context_id),
                str(event.get("message", "")),
            )
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

    def _should_emit_worker_progress(
        self, context_id: int, event: dict[str, Any]
    ) -> bool:
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
        if (
            previous
            and previous[1:] == (state, peers, seeds)
            and now - previous[0] < 15
        ):
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
        context = self._contexts.get(season_id)
        db_season_id = context.id if context else self._context_db_id(season_id)
        episodes = self._get_download_context_episodes(db_season_id)
        if not episodes:
            error_msg = "No episodes found for download context"
            logger.error("Download error for season %d: %s", db_season_id, error_msg)
            self.download_error.emit(db_season_id, error_msg)
            return

        video_files: list[VideoFileMatch] = [
            (
                Path(str(file_data["path"])),
                int(file_data["size"]),
                int(file_data.get("duration_seconds") or 0),
            )
            for file_data in event.get("files", [])
            if file_data.get("path") and file_data.get("size") is not None
        ]
        if not video_files:
            error_msg = "No video files found in torrent"
            logger.error("Download error for season %d: %s", db_season_id, error_msg)
            self.download_error.emit(db_season_id, error_msg)
            return

        matches = self._match_episode_files(episodes, video_files)
        if not matches:
            error_msg = "Could not match any video files to episodes"
            logger.error("Download error for season %d: %s", db_season_id, error_msg)
            self.download_error.emit(db_season_id, error_msg)
            return

        for episode_id, video_path in matches.items():
            duration_seconds = self._duration_for_path(video_files, video_path)
            self.download_completed.emit(episode_id, str(video_path))
            if duration_seconds > 0:
                self.duration_detected.emit(episode_id, duration_seconds)
            logger.info("Episode %d completed: %s", episode_id, video_path)

        self.season_completed.emit(db_season_id)
        logger.info(
            "Season %d download completed: %d/%d episodes matched",
            db_season_id,
            len(matches),
            len(episodes),
        )

    def _get_download_context_episodes(self, season_id: int) -> list[dict[str, Any]]:
        """Return episodes for a season or its whole-series magnet context."""
        season = self._db_manager.get_season(season_id)
        if not season:
            return self._db_manager.get_episodes(season_id)

        media_item = self._db_manager.get_media_item(str(season["media_item_id"]))
        if (
            media_item
            and media_item.get("magnet_link")
            and not season.get("magnet_link")
        ):
            return self._db_manager.get_series_episodes(str(season["media_item_id"]))

        return self._db_manager.get_episodes(season_id)

    def _send_worker_command(self, command: dict[str, Any]) -> bool:
        """Send a JSON command to the worker process."""
        with self._worker_lock:
            process = self._worker_process
            if process is None or process.stdin is None or process.poll() is not None:
                self._pending_commands.append(command)
                return False
            if not self._worker_ready and command.get("command") != "stop":
                self._pending_commands.append(command)
                return True

            try:
                process.stdin.write(json.dumps(command) + "\n")
                process.stdin.flush()
                return True
            except (BrokenPipeError, OSError):
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
                lt.alert.category_t.error_notification
                | lt.alert.category_t.status_notification
                | lt.alert.category_t.storage_notification
            ),
        }
        with self._session_lock:
            self._session = lt.session(settings)
        logger.info("Libtorrent session initialized")

    def _load_session_state(self) -> None:
        """Load session state (DHT nodes, etc.) from disk."""
        state_file = self._state_dir / self.SESSION_STATE_FILE
        if not state_file.exists():
            return

        try:
            state_data = state_file.read_bytes()
            with self._session_lock:
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
            with self._session_lock:
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
                        lt.torrent_handle.save_info_dict
                        | lt.torrent_handle.only_if_modified
                    )
                except Exception as e:
                    logger.warning(
                        "Failed to request resume data for context %d: %s",
                        context_id,
                        e,
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

                if status.state == lt.torrent_status.states.seeding:
                    # Download complete
                    self._on_download_complete(context_id, handle)
                elif status.state in (
                    lt.torrent_status.states.downloading,
                    lt.torrent_status.states.downloading_metadata,
                    lt.torrent_status.states.checking_files,
                    lt.torrent_status.states.checking_resume_data,
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
            duration_seconds = probe_duration_seconds(video_path)
            if duration_seconds > 0:
                self.duration_detected.emit(file_id, duration_seconds)
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
        episodes = self._get_download_context_episodes(season_id)

        if not episodes:
            error_msg = "No episodes found for download context"
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
            duration_seconds = self._duration_for_path(video_files, video_path)
            self.download_completed.emit(episode_id, str(video_path))
            if duration_seconds > 0:
                self.duration_detected.emit(episode_id, duration_seconds)
            logger.info("Episode %d completed: %s", episode_id, video_path)

        self.season_completed.emit(season_id)
        logger.info(
            "Season %d download completed: %d/%d episodes matched",
            season_id,
            len(matches),
            len(episodes),
        )

    def _get_video_files_from_torrent(self, handle: Any) -> list[tuple[Path, int, int]]:
        """Get all video files from a torrent.

        Args:
            handle: Torrent handle.

        Returns:
            List of (file_path, file_size, duration_seconds) tuples for video files.
        """
        torrent_info = handle.torrent_file()
        if not torrent_info:
            return []

        save_path = Path(handle.status().save_path)
        video_files: list[VideoFileMatch] = []

        files = torrent_info.files()
        for i in range(files.num_files()):
            file_path = save_path / files.file_path(i)
            file_size = files.file_size(i)
            ext = file_path.suffix.lower()

            if ext in VIDEO_EXTENSIONS:
                video_files.append(
                    (file_path, file_size, probe_duration_seconds(file_path))
                )

        return video_files

    def _match_episode_files(
        self,
        episodes: list[dict[str, Any]],
        video_files: list[VideoFileMatch],
    ) -> dict[int, Path]:
        """Match video files to episodes based on season and episode numbers.

        Matches files by looking for episode number patterns in filenames:
        - S01E05 or s01e05
        - 1x05 or 1X05
        - Episode 5 or episode 5
        - E05 or e05
        - .105. (season 1 episode 5)

        Args:
            episodes: Episode dicts with id, episode_number, and optional season_number.
            video_files: List of (path, size, duration_seconds) tuples.

        Returns:
            Dictionary mapping video_file_id -> matched video path.
        """
        matches: dict[int, Path] = {}

        for episode in episodes:
            episode_id = episode["id"]
            episode_num = episode["episode_number"]
            season_num = episode.get("season_number")

            best_match: tuple[Path | None, int, int] = (None, 0, 0)

            for file_path, file_size, duration_seconds in video_files:
                extracted_season, extracted_num = self._extract_season_episode(
                    str(file_path)
                )
                if (
                    season_num is not None
                    and extracted_season is not None
                    and extracted_season != season_num
                ):
                    continue

                if extracted_num == episode_num and file_size > best_match[1]:
                    best_match = (file_path, file_size, duration_seconds)

            if best_match[0]:
                matches[episode_id] = best_match[0]

        return matches

    def _duration_for_path(
        self,
        video_files: list[VideoFileMatch],
        path: Path,
    ) -> int:
        """Return pre-probed duration for a matched path."""
        for video_file_path, _file_size, duration_seconds in video_files:
            if video_file_path == path:
                return duration_seconds
        return 0

    def _extract_season_episode(self, path: str) -> tuple[int | None, int | None]:
        """Extract season and episode numbers from a path or filename.

        Args:
            path: Torrent file path to parse.

        Returns:
            Tuple of (season number, episode number). Either value can be None.
        """
        patterns = [
            # S01E05, s01e05
            r"[Ss](\d{1,2})[Ee](\d{1,3})",
            # 1x05, 1X05
            r"(?:^|[.\s_/-])(\d{1,2})[xX](\d{1,3})(?:[.\s_/-]|$)",
            # .105. (single digit season, two digit episode)
            r"(?:^|[.\s_/-])(\d)(\d{2})(?:[.\s_/-]|$)",
        ]

        for pattern in patterns:
            match = re.search(pattern, path)
            if match:
                return int(match.group(1)), int(match.group(2))

        return None, self._extract_episode_number(Path(path).name)

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
            context_id = self._context_id(context)
            if context_id in self._contexts:
                logger.warning(
                    "Torrent already exists for %s %d (worker context %d)",
                    context.download_type.value,
                    context.id,
                    context_id,
                )
                return False

            self._contexts[context_id] = context
            command = {
                "command": "add",
                "type": context.download_type.value,
                "id": context_id,
                "magnet": magnet_link,
                "download_dir": str(self._download_dir),
                "sequential": sequential,
            }
            if not self._send_worker_command(command):
                self._contexts.pop(context_id, None)
                logger.error(
                    "Cannot add magnet for %s %d: torrent worker unavailable",
                    context.download_type.value,
                    context.id,
                )
                return False

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
        context_id = self._context_id(context)
        if context_id in self._handles:
            logger.warning(
                "Torrent already exists for %s %d",
                context.download_type.value,
                context.id,
            )
            return False

        try:
            atp = lt.parse_magnet_uri(magnet_link)
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

    def cancel_download(
        self, context: DownloadContext, delete_files: bool = False
    ) -> bool:
        """Cancel an active download.

        Args:
            context: Download context to cancel.
            delete_files: Remove downloaded payload files owned by the torrent.

        Returns:
            True if download was cancelled.
        """
        context_id = self._context_id(context)
        if self._use_process_backend:
            if context_id not in self._contexts:
                return False

            self._send_worker_command(
                {
                    "command": "cancel",
                    "id": context_id,
                    "delete_files": delete_files,
                }
            )
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
                if delete_files:
                    self._session.remove_torrent(handle, lt.options_t.delete_files)
                else:
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
