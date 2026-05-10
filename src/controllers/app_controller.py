"""Application controller for Hackflix.

This module provides the AppController class that serves as the
central orchestrator connecting the UI to services and database.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot

from src.config import CACHE_DIR, MEDIA_LIBRARY_PATH, DownloadState, PipelineState
from src.database.db_manager import DatabaseManager
from src.ui.enums import Action, AppState, MediaTab

if TYPE_CHECKING:
    from src.services.metadata_service import MetadataService
    from src.services.pipeline_service import PipelineService
    from src.services.player_service import PlayerService
    from src.services.torrent_service import TorrentService
    from src.ui.windows.main_window import MainWindow

logger = logging.getLogger(__name__)

POSTER_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")


class DeleteWorker(QThread):
    """Delete downloaded files away from the UI thread."""

    delete_finished = Signal(str, str, int, int)

    def __init__(
        self,
        db_manager: DatabaseManager,
        item_type: str,
        item_id: str | int,
        title: str,
        current_season_id: int | None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._db_manager = db_manager
        self._item_type = item_type
        self._item_id = item_id
        self._title = title
        self._current_season_id = current_season_id

    def run(self) -> None:
        """Delete approved paths and reset DB state."""
        try:
            if self._item_type == "episode":
                video = self._db_manager.get_video_file(int(self._item_id))
                paths = [video["file_path"]] if video and video.get("file_path") else []
                deleted, failed = self._delete_paths(paths)
                self._db_manager.reset_video_file_state(int(self._item_id))
                view = "episodes" if self._current_season_id else "library"
                self.delete_finished.emit("ok", view, deleted, failed)
                return

            paths = self._db_manager.get_media_files(str(self._item_id))
            deleted, failed = self._delete_paths(paths)
            self._db_manager.reset_media_state(str(self._item_id))
            self.delete_finished.emit("ok", "library", deleted, failed)
        except Exception as e:
            logger.error(
                "Delete failed for %s %s: %s", self._item_type, self._item_id, e
            )
            self.delete_finished.emit(str(e), "library", 0, 1)

    def _delete_paths(self, paths: list[str]) -> tuple[int, int]:
        """Delete paths that are under app-owned roots."""
        deleted = 0
        failed = 0
        roots = [MEDIA_LIBRARY_PATH.resolve(), CACHE_DIR.resolve()]

        for raw_path in paths:
            try:
                file_path = Path(raw_path).resolve()
            except (OSError, RuntimeError):
                logger.warning("Skipping invalid delete path: %s", raw_path)
                failed += 1
                continue

            if not any(
                file_path == root or root in file_path.parents for root in roots
            ):
                logger.warning("Skipping non-app-owned delete path: %s", file_path)
                continue

            if not file_path.exists():
                continue

            try:
                file_path.unlink()
                deleted += 1
            except OSError as e:
                logger.warning("Failed to delete %s: %s", file_path, e)
                failed += 1

        return deleted, failed


@dataclass
class NavigationContext:
    """Tracks navigation state for returning to previous context."""

    state: AppState
    tab: MediaTab
    selected_item_id: str | None = None
    series_id: str | None = None
    season_id: int | None = None


class StateHandler(ABC):
    """Abstract base class for state handlers."""

    def __init__(self, controller: "AppController") -> None:
        """Initialize the state handler.

        Args:
            controller: The AppController instance.
        """
        self._controller = controller

    @abstractmethod
    def handle_action(self, action: Action, context: dict[str, Any]) -> bool:
        """Handle an action in this state.

        Args:
            action: The action to handle.
            context: Context dictionary from InputManager.

        Returns:
            True if the action was handled, False otherwise.
        """
        pass

    def on_enter(self) -> None:
        """Called when entering this state."""
        pass

    def on_exit(self) -> None:
        """Called when exiting this state."""
        pass


class LibraryRootHandler(StateHandler):
    """Handler for LIBRARY_ROOT state."""

    def handle_action(self, action: Action, context: dict[str, Any]) -> bool:
        """Handle actions in library root state."""
        if action == Action.NAVIGATE_UP:
            self._controller.main_window.library_view.select_prev()
            return True

        if action == Action.NAVIGATE_DOWN:
            self._controller.main_window.library_view.select_next()
            return True

        if action == Action.SWITCH_TAB:
            self._controller.main_window.library_view.switch_tab()
            self._controller.refresh_library()
            return True

        if action == Action.CONFIRM:
            self._controller.activate_selected()
            return True

        if action == Action.SEARCH:
            self._controller.show_search()
            return True

        if action == Action.CLEAR_FILTER:
            self._controller.clear_search_filter()
            return True

        if action == Action.DELETE:
            self._controller.delete_selected()
            return True

        if action == Action.SYNC:
            self._controller.trigger_sync()
            return True

        if action == Action.QUIT:
            self._controller.quit_application()
            return True

        return False


class SeriesDrilldownSeasonsHandler(StateHandler):
    """Handler for SERIES_DRILLDOWN_SEASONS state."""

    def handle_action(self, action: Action, context: dict[str, Any]) -> bool:
        """Handle actions in series drilldown (seasons) state."""
        if action == Action.NAVIGATE_UP:
            self._controller.main_window.library_view.select_prev()
            return True

        if action == Action.NAVIGATE_DOWN:
            self._controller.main_window.library_view.select_next()
            return True

        if action == Action.CONFIRM:
            self._controller.activate_selected()
            return True

        if action == Action.CANCEL:
            self._controller.navigate_back()
            return True

        if action == Action.QUIT:
            self._controller.quit_application()
            return True

        return False


class SeriesDrilldownEpisodesHandler(StateHandler):
    """Handler for SERIES_DRILLDOWN_EPISODES state."""

    def handle_action(self, action: Action, context: dict[str, Any]) -> bool:
        """Handle actions in series drilldown (episodes) state."""
        if action == Action.NAVIGATE_UP:
            self._controller.main_window.library_view.select_prev()
            return True

        if action == Action.NAVIGATE_DOWN:
            self._controller.main_window.library_view.select_next()
            return True

        if action == Action.CONFIRM:
            self._controller.activate_selected()
            return True

        if action == Action.CANCEL:
            self._controller.navigate_back()
            return True

        if action == Action.DELETE:
            self._controller.delete_selected()
            return True

        if action == Action.QUIT:
            self._controller.quit_application()
            return True

        return False


class SearchOverlayHandler(StateHandler):
    """Handler for SEARCH_OVERLAY state."""

    def handle_action(self, action: Action, context: dict[str, Any]) -> bool:
        """Handle actions in search overlay state.

        Note: Most keyboard input is captured by the search overlay widget.
        This handler deals with escape via input manager if needed.
        """
        if action == Action.CANCEL:
            self._controller.hide_search()
            return True

        return False


class DialogConfirmHandler(StateHandler):
    """Handler for DIALOG_CONFIRM state."""

    def handle_action(self, action: Action, context: dict[str, Any]) -> bool:
        """Handle actions in dialog confirm state.

        Note: The dialog handles its own keyboard input.
        """
        return False


class PlayerActiveHandler(StateHandler):
    """Handler for PLAYER_ACTIVE state.

    Handles all player-related actions including playback controls,
    volume adjustments, and audio track cycling.
    """

    def handle_action(self, action: Action, context: dict[str, Any]) -> bool:
        """Handle actions in player state.

        Args:
            action: The action to handle.
            context: Context dictionary from InputManager.

        Returns:
            True if the action was handled, False otherwise.
        """
        # Playback controls
        if action == Action.TOGGLE_PAUSE:
            self._controller.player_toggle_pause()
            return True

        if action == Action.CONFIRM:
            # Enter also toggles pause in player mode
            self._controller.player_toggle_pause()
            return True

        # Seek controls (arrows in player mode)
        if action == Action.NAVIGATE_RIGHT or action == Action.SEEK_FORWARD:
            self._controller.player_seek_forward()
            return True

        if action == Action.NAVIGATE_LEFT or action == Action.SEEK_BACKWARD:
            self._controller.player_seek_backward()
            return True

        # Volume controls (arrows in player mode)
        if action == Action.NAVIGATE_UP or action == Action.VOLUME_UP:
            self._controller.player_volume_up()
            return True

        if action == Action.NAVIGATE_DOWN or action == Action.VOLUME_DOWN:
            self._controller.player_volume_down()
            return True

        # Mute toggle
        if action == Action.TOGGLE_MUTE:
            self._controller.player_toggle_mute()
            return True

        # Audio track cycling
        if action == Action.CYCLE_AUDIO:
            self._controller.player_cycle_audio()
            return True

        # Exit player
        if action == Action.CANCEL:
            self._controller.stop_player()
            return True

        if action == Action.QUIT:
            self._controller.stop_player()
            self._controller.quit_application()
            return True

        return False


class AppController(QObject):
    """Central application controller.

    The AppController orchestrates communication between the UI,
    database, and background services. It implements a state machine
    for handling user input based on the current application state.
    """

    def __init__(
        self,
        db_manager: DatabaseManager,
        parent: QObject | None = None,
    ) -> None:
        """Initialize the AppController.

        Args:
            db_manager: DatabaseManager instance.
            parent: Optional parent QObject.
        """
        super().__init__(parent)
        self._db_manager = db_manager
        self._main_window: "MainWindow | None" = None
        self._metadata_service: "MetadataService | None" = None
        self._torrent_service: "TorrentService | None" = None
        self._player_service: "PlayerService | None" = None
        self._pipeline_service: "PipelineService | None" = None

        # State machine
        self._current_state = AppState.LIBRARY_ROOT
        self._state_handlers: dict[AppState, StateHandler] = {
            AppState.LIBRARY_ROOT: LibraryRootHandler(self),
            AppState.SERIES_DRILLDOWN_SEASONS: SeriesDrilldownSeasonsHandler(self),
            AppState.SERIES_DRILLDOWN_EPISODES: SeriesDrilldownEpisodesHandler(self),
            AppState.SEARCH_OVERLAY: SearchOverlayHandler(self),
            AppState.DIALOG_CONFIRM: DialogConfirmHandler(self),
            AppState.PLAYER_ACTIVE: PlayerActiveHandler(self),
        }

        # Navigation state
        self._navigation_stack: list[NavigationContext] = []
        self._current_tab = MediaTab.MOVIES
        self._search_filter: str | None = None

        # Series drilldown context
        self._current_series_id: str | None = None
        self._current_season_id: int | None = None
        self._active_download_types: dict[int, str] = {}
        self._pending_episode_pipeline_by_season: dict[int, int] = {}
        self._pending_pipeline_ids: list[int] = []
        self._delete_worker: DeleteWorker | None = None

        # Player state
        self._current_playing_file_id: int | None = None
        self._playback_start_time: float | None = None
        self._resumed_from_position: int = 0

        logger.info("AppController initialized")

    def bind_main_window(self, main_window: "MainWindow") -> None:
        """Bind the main window to this controller.

        Args:
            main_window: The MainWindow instance.
        """
        self._main_window = main_window
        main_window.bind_controller(self)
        logger.debug("MainWindow bound to controller")

    def bind_services(
        self,
        metadata_service: "MetadataService | None" = None,
        torrent_service: "TorrentService | None" = None,
        player_service: "PlayerService | None" = None,
        pipeline_service: "PipelineService | None" = None,
    ) -> None:
        """Bind background services to this controller.

        Args:
            metadata_service: Optional MetadataService instance.
            torrent_service: Optional TorrentService instance.
            player_service: Optional PlayerService instance.
            pipeline_service: Optional PipelineService instance.
        """
        self._metadata_service = metadata_service
        self._torrent_service = torrent_service
        self._player_service = player_service
        self._pipeline_service = pipeline_service

        # Connect service signals
        if metadata_service:
            metadata_service.sync_started.connect(self._on_sync_started)
            metadata_service.sync_completed.connect(self._on_sync_completed)
            metadata_service.sync_error.connect(self._on_sync_error)

        if torrent_service:
            torrent_service.download_progress.connect(
                self._on_download_progress, Qt.ConnectionType.QueuedConnection
            )
            torrent_service.download_completed.connect(
                self._on_download_completed, Qt.ConnectionType.QueuedConnection
            )
            torrent_service.download_error.connect(
                self._on_download_error, Qt.ConnectionType.QueuedConnection
            )
            torrent_service.season_completed.connect(
                self._on_season_completed, Qt.ConnectionType.QueuedConnection
            )

        if player_service:
            player_service.playback_finished.connect(self._on_playback_finished)
            player_service.time_changed.connect(self._on_time_changed)
            player_service.error_occurred.connect(self._on_player_error)

        if pipeline_service:
            pipeline_service.signals.pipeline_update.connect(self._on_pipeline_update)
            pipeline_service.signals.pipeline_finished.connect(
                self._on_pipeline_finished
            )
            pipeline_service.signals.error_occurred.connect(self._on_pipeline_error)

        logger.debug("Services bound to controller")

    @property
    def main_window(self) -> "MainWindow":
        """Get the main window.

        Raises:
            RuntimeError: If main window not bound.
        """
        if self._main_window is None:
            raise RuntimeError("MainWindow not bound to controller")
        return self._main_window

    @property
    def current_state(self) -> AppState:
        """Get the current application state."""
        return self._current_state

    @property
    def current_tab(self) -> MediaTab:
        """Get the current tab."""
        return self._current_tab

    @property
    def search_filter(self) -> str | None:
        """Get the current search filter."""
        return self._search_filter

    def bootstrap(self) -> None:
        """Initialize the application state.

        Called after main window and services are bound.
        """
        # Set initial connection status (assume online for now)
        if self._main_window:
            self._main_window.set_connection_status(True)
            self._main_window.set_sync_status("")
            self._main_window.set_storage_usage("")

        # Load initial library data
        self.refresh_library()

        # Auto-resume incomplete downloads
        self._resume_incomplete_downloads()

        # Auto-resume incomplete pipelines
        self._resume_incomplete_pipelines()

        logger.info("AppController bootstrap complete")

    def _resume_incomplete_downloads(self) -> None:
        """Resume any incomplete downloads on startup."""
        if not self._torrent_service:
            return

        try:
            incomplete = self._db_manager.get_incomplete_downloads()
            incomplete_seasons = self._db_manager.get_incomplete_season_downloads()
            total = len(incomplete) + len(incomplete_seasons)
            if total:
                logger.info("Resuming %d incomplete downloads", total)
                if self._main_window:
                    self._main_window.show_toast(
                        self.tr("Resuming {count} incomplete downloads").format(
                            count=total
                        ),
                        "info",
                    )
                for video in incomplete:
                    self._resume_download(video)
                for season in incomplete_seasons:
                    self._resume_season_download(season)
        except Exception as e:
            logger.error("Failed to resume incomplete downloads: %s", e)

    def _resume_download(self, video: dict[str, Any]) -> None:
        """Resume a single download from database state.

        Args:
            video: Video file dictionary from database.
        """
        magnet = video.get("magnet_link")
        if not magnet:
            logger.warning("Cannot resume download %d: no magnet link", video.get("id"))
            return

        if not self._torrent_service:
            return

        from src.services.torrent_service import DownloadContext, DownloadType

        file_id = video["id"]
        context = DownloadContext(DownloadType.MOVIE, file_id)

        if self._torrent_service.add_magnet(context, magnet):
            self._active_download_types[file_id] = DownloadType.MOVIE.value
            logger.info("Resumed download for video file %d", file_id)
        else:
            logger.warning("Failed to resume download for video file %d", file_id)

    def _resume_season_download(self, season: dict[str, Any]) -> None:
        """Resume a season download from database state."""
        magnet = season.get("magnet_link")
        if not magnet:
            logger.warning(
                "Cannot resume season download %d: no magnet link", season.get("id")
            )
            return

        if not self._torrent_service:
            return

        from src.services.torrent_service import DownloadContext, DownloadType

        season_id = season["id"]
        context = DownloadContext(DownloadType.SEASON, season_id)

        if self._torrent_service.add_magnet(context, magnet):
            self._active_download_types[season_id] = DownloadType.SEASON.value
            logger.info("Resumed season download for season %d", season_id)
        else:
            logger.warning("Failed to resume season download for season %d", season_id)

    def _resume_incomplete_pipelines(self) -> None:
        """Resume any incomplete pipeline processes on startup."""
        if not self._pipeline_service:
            return

        try:
            incomplete = self._db_manager.get_incomplete_pipelines()
            if incomplete:
                logger.info("Resuming %d incomplete pipelines", len(incomplete))
                if self._main_window:
                    self._main_window.show_toast(
                        self.tr("Resuming {count} incomplete processing tasks").format(
                            count=len(incomplete)
                        ),
                        "info",
                    )
                for video in incomplete:
                    self.start_pipeline(video["id"], show_busy_toast=False)
        except Exception as e:
            logger.error("Failed to resume incomplete pipelines: %s", e)

    def shutdown(self) -> None:
        """Clean shutdown of the controller."""
        logger.info("AppController shutdown")

        # Stop player and save position if playing
        if self._current_state == AppState.PLAYER_ACTIVE:
            self._save_resume_position()

        # Release player resources
        if self._player_service:
            self._player_service.release()

        # Stop any running services
        if self._metadata_service and self._metadata_service.isRunning():
            self._metadata_service.stop()
            self._metadata_service.wait()

        if self._torrent_service and self._torrent_service.isRunning():
            self._torrent_service.stop()
            self._torrent_service.wait()

    # =========================================================================
    # State Machine
    # =========================================================================

    def transition_to(self, new_state: AppState) -> None:
        """Transition to a new application state.

        Args:
            new_state: The state to transition to.
        """
        if new_state == self._current_state:
            return

        old_state = self._current_state
        old_handler = self._state_handlers.get(old_state)
        new_handler = self._state_handlers.get(new_state)

        if old_handler:
            old_handler.on_exit()

        self._current_state = new_state

        if new_handler:
            new_handler.on_enter()

        # Reset input manager debounce on state change
        if self._main_window:
            self._main_window.input_manager.reset_debounce()

        logger.debug("State transition: %s -> %s", old_state.name, new_state.name)

    def push_navigation(self) -> None:
        """Push current navigation context to the stack."""
        selected = (
            self._main_window.library_view.get_selected_item()
            if self._main_window
            else None
        )
        ctx = NavigationContext(
            state=self._current_state,
            tab=self._current_tab,
            selected_item_id=selected.get("id") if selected else None,
            series_id=self._current_series_id,
            season_id=self._current_season_id,
        )
        self._navigation_stack.append(ctx)
        logger.debug("Pushed navigation context: %s", ctx)

    def pop_navigation(self) -> NavigationContext | None:
        """Pop and return the previous navigation context.

        Returns:
            The previous NavigationContext, or None if stack is empty.
        """
        if not self._navigation_stack:
            return None
        ctx = self._navigation_stack.pop()
        logger.debug("Popped navigation context: %s", ctx)
        return ctx

    @Slot(Action, dict)
    def handle_action(self, action: Action, context: dict[str, Any]) -> None:
        """Handle an action from the InputManager.

        Args:
            action: The action to handle.
            context: Context dictionary.
        """
        logger.info(
            "Controller received action: %s in state: %s",
            action.name,
            self._current_state.name,
        )
        handler = self._state_handlers.get(self._current_state)
        if handler:
            logger.debug("Found handler for state: %s", self._current_state.name)
            handled = handler.handle_action(action, context)
            logger.info("Action %s handled: %s", action.name, handled)
            if not handled:
                logger.debug(
                    "Action %s not handled in state %s",
                    action.name,
                    self._current_state.name,
                )
        else:
            logger.warning("No handler found for state: %s", self._current_state.name)

    # =========================================================================
    # Library Actions
    # =========================================================================

    def refresh_library(self) -> None:
        """Refresh the library view with current data."""
        if not self._main_window:
            return

        tab = self._main_window.library_view.get_current_tab()
        self._current_tab = tab

        try:
            items = self._db_manager.get_library_items(tab.value, self._search_filter)

            # Transform items for the view
            view_items = []
            for item in items:
                view_item = {
                    "id": item["id"],
                    "type": item["type"],
                    "title": item["title"],
                    "genres": item.get("genres", ""),
                    "poster_path": self._get_cached_poster_path(
                        item["id"], item.get("poster_path")
                    ),
                }

                if item["type"] == "series":
                    # Get season count
                    seasons = self._db_manager.get_seasons(item["id"])
                    view_item["season_count"] = len(seasons)
                else:
                    # Get video file state for movies
                    video = self._db_manager.get_video_details(item["id"])
                    if video:
                        view_item["file_id"] = video["id"]
                        view_item["state"] = video.get(
                            "state", DownloadState.PENDING.value
                        )
                        view_item["pipeline_state"] = video.get("pipeline_state")
                        view_item["download_progress"] = video.get(
                            "download_progress", 0
                        )
                        view_item["resume_position_seconds"] = video.get(
                            "resume_position_seconds", 0
                        )
                        view_item["watched_at"] = video.get("watched_at")
                    else:
                        view_item["state"] = DownloadState.PENDING.value

                logger.debug("refresh_library view_item: %s", view_item)
                view_items.append(view_item)

            self._main_window.library_view.set_items(view_items)
            logger.debug("Library refreshed: %d items", len(view_items))

        except Exception as e:
            logger.error("Failed to refresh library: %s", e)
            self._main_window.show_toast(
                self.tr("Failed to load library: {error}").format(error=e), "error"
            )

    def _get_cached_poster_path(self, media_id: str, poster_path: str | None) -> str:
        """Return a local poster path when one is cached."""
        poster_dir = CACHE_DIR / "posters"
        poster_root = poster_dir.resolve()
        if poster_path:
            try:
                local_path = Path(poster_path).resolve()
                if local_path.exists():
                    return str(local_path)
                if (
                    local_path == poster_root or poster_root in local_path.parents
                ) and local_path.exists():
                    return str(local_path)
            except (OSError, RuntimeError):
                logger.warning("Ignoring invalid poster path: %s", poster_path)

        safe_media_id = self._safe_cache_name(media_id)
        for ext in POSTER_EXTENSIONS:
            cached = poster_dir / f"{safe_media_id}{ext}"
            if cached.exists():
                return str(cached)

        return poster_path or ""

    def _safe_cache_name(self, item_id: str) -> str:
        """Return the poster cache basename used by MetadataService."""
        safe = "".join(
            char if char.isalnum() or char in "_.-" else "_" for char in item_id
        ).strip("._")
        return safe or "poster"

    def load_seasons(self, series_id: str) -> None:
        """Load seasons for a series.

        Args:
            series_id: The series ID.
        """
        if not self._main_window:
            return

        self._current_series_id = series_id

        try:
            seasons = self._db_manager.get_seasons(series_id)

            view_items = []
            for season in seasons:
                episodes = self._db_manager.get_episodes(season["id"])
                view_items.append(
                    {
                        "id": season["id"],
                        "type": "season",
                        "title": self.tr("Season {n}").format(
                            n=season["season_number"]
                        ),
                        "season_number": season["season_number"],
                        "episode_count": len(episodes),
                        "state": season.get("state", DownloadState.PENDING.value),
                        "download_progress": season.get("download_progress", 0),
                    }
                )

            self._main_window.library_view.set_items(view_items)
            logger.debug("Loaded %d seasons for series %s", len(view_items), series_id)

        except Exception as e:
            logger.error("Failed to load seasons: %s", e)
            self._main_window.show_toast(
                self.tr("Failed to load seasons: {error}").format(error=e), "error"
            )

    def load_episodes(self, season_id: int) -> None:
        """Load episodes for a season.

        Args:
            season_id: The season ID.
        """
        if not self._main_window:
            return

        self._current_season_id = season_id

        try:
            episodes = self._db_manager.get_episodes(season_id)

            view_items = []
            for ep in episodes:
                view_items.append(
                    {
                        "id": ep["id"],
                        "file_id": ep["id"],  # For episodes, id is the video_file id
                        "type": "episode",
                        "title": ep.get("episode_title")
                        or self.tr("Episode {n}").format(n=ep["episode_number"]),
                        "episode_number": ep["episode_number"],
                        "episode_title": ep.get("episode_title", ""),
                        "state": ep.get("state", DownloadState.PENDING.value),
                        "pipeline_state": ep.get("pipeline_state"),
                        "download_progress": ep.get("download_progress", 0),
                        "resume_position_seconds": ep.get("resume_position_seconds", 0),
                        "watched_at": ep.get("watched_at"),
                    }
                )

            self._main_window.library_view.set_items(view_items)
            logger.debug("Loaded %d episodes for season %d", len(view_items), season_id)

        except Exception as e:
            logger.error("Failed to load episodes: %s", e)
            self._main_window.show_toast(
                self.tr("Failed to load episodes: {error}").format(error=e), "error"
            )

    def activate_selected(self) -> None:
        """Activate the currently selected item."""
        if not self._main_window:
            return

        item = self._main_window.library_view.get_selected_item()
        if not item:
            return

        logger.debug("activate_selected item: %s", item)

        item_type = item.get("type")
        item_state = item.get("state")

        if item_type == "series":
            # Drill down into series
            self.push_navigation()
            self.load_seasons(item["id"])
            self.transition_to(AppState.SERIES_DRILLDOWN_SEASONS)

        elif item_type == "season":
            # Drill down into season
            self.push_navigation()
            self.load_episodes(item["id"])
            self.transition_to(AppState.SERIES_DRILLDOWN_EPISODES)

        elif item_state == DownloadState.COMPLETED.value:
            if item_type == "episode" and not self._episode_subtitles_ready(item):
                file_id = item.get("file_id") or item.get("id")
                if file_id is not None:
                    self.start_pipeline(int(file_id))
                return

            # Play the item
            file_id = item.get("file_id") or item.get("id")
            if file_id is not None:
                self.play_media(file_id)

        else:
            # Start download (PENDING, ERROR, QUEUED states)
            if not self._torrent_service:
                self._main_window.show_toast(
                    self.tr("Torrent service not available"), "error"
                )
                return

            item_title = item.get("title")
            item_type = item.get("type")
            file_id_str = item.get("file_id") or item.get("id")

            if not file_id_str:
                self._main_window.show_toast(self.tr("No file ID available"), "error")
                return

            try:
                file_id = int(file_id_str)
            except (ValueError, TypeError):
                self._main_window.show_toast(self.tr("Invalid file ID"), "error")
                return

            if item_type == "movie":
                video = self._db_manager.get_video_file(file_id)
                if not video:
                    self._main_window.show_toast(
                        self.tr("Video file not found"), "error"
                    )
                    return

                magnet = video.get("magnet_link")
                if not magnet:
                    self._main_window.show_toast(
                        self.tr("No magnet link available"), "error"
                    )
                    return

                from src.services.torrent_service import DownloadContext, DownloadType

                context = DownloadContext(DownloadType.MOVIE, file_id)
                if self._torrent_service.add_magnet(context, magnet):
                    self._active_download_types[file_id] = DownloadType.MOVIE.value
                    self._main_window.library_view.update_item_by_file_id(
                        file_id,
                        {"state": DownloadState.QUEUED.value, "download_progress": 0},
                    )
                    self._main_window.show_toast(
                        self.tr("Starting download: {title}").format(title=item_title),
                        "info",
                    )
                else:
                    self._main_window.show_toast(
                        self.tr("Failed to start download: {title}").format(
                            title=item_title
                        ),
                        "error",
                    )

            elif item_type == "episode":
                video = self._db_manager.get_video_file(file_id)
                if not video:
                    self._main_window.show_toast(
                        self.tr("Video file not found"), "error"
                    )
                    return

                # Episodes belong to a season - get magnet from season
                season_id = video.get("season_id")
                if not season_id:
                    self._main_window.show_toast(
                        self.tr("Episode has no season"), "error"
                    )
                    return

                season = self._db_manager.get_season(season_id)
                if not season:
                    self._main_window.show_toast(self.tr("Season not found"), "error")
                    return

                magnet = season.get("magnet_link")
                if not magnet:
                    self._main_window.show_toast(
                        self.tr("No magnet link available"), "error"
                    )
                    return

                from src.services.torrent_service import DownloadContext, DownloadType

                # Download the whole season
                context = DownloadContext(DownloadType.SEASON, season_id)
                if self._torrent_service.add_magnet(context, magnet):
                    self._active_download_types[season_id] = DownloadType.SEASON.value
                    self._pending_episode_pipeline_by_season[season_id] = file_id
                    self._main_window.library_view.update_all_items(
                        {"state": DownloadState.QUEUED.value, "download_progress": 0}
                    )
                    self._main_window.show_toast(
                        self.tr("Starting season download for: {title}").format(
                            title=item_title
                        ),
                        "info",
                    )
                else:
                    self._main_window.show_toast(
                        self.tr("Failed to start download: {title}").format(
                            title=item_title
                        ),
                        "error",
                    )

            elif item_type == "season":
                # For seasons, id is the season_id
                season_id = item.get("id")
                if not season_id:
                    self._main_window.show_toast(
                        self.tr("Invalid season selection"), "error"
                    )
                    return

                season = self._db_manager.get_season(season_id)
                if not season:
                    self._main_window.show_toast(self.tr("Season not found"), "error")
                    return

                magnet = season.get("magnet_link")
                if not magnet:
                    self._main_window.show_toast(
                        self.tr("No magnet link available"), "error"
                    )
                    return

                from src.services.torrent_service import DownloadContext, DownloadType

                context = DownloadContext(DownloadType.SEASON, season_id)
                if self._torrent_service.add_magnet(context, magnet):
                    self._active_download_types[season_id] = DownloadType.SEASON.value
                    # Reload seasons to show updated QUEUED state
                    if self._current_series_id:
                        self.load_seasons(self._current_series_id)
                    self._main_window.show_toast(
                        self.tr("Starting download: {title}").format(title=item_title),
                        "info",
                    )
                else:
                    self._main_window.show_toast(
                        self.tr("Failed to start download: {title}").format(
                            title=item_title
                        ),
                        "error",
                    )

            else:
                self._main_window.show_toast(
                    self.tr("Unknown item type: {type}").format(type=item_type),
                    "error",
                )

    def _episode_subtitles_ready(self, item: dict[str, Any]) -> bool:
        """Return whether an episode has completed subtitle processing."""
        pipeline_state = item.get("pipeline_state")
        return pipeline_state == PipelineState.SUBS_READY.value

    def navigate_back(self) -> None:
        """Navigate back to the previous context."""
        ctx = self.pop_navigation()
        if not ctx:
            return

        self._current_series_id = ctx.series_id
        self._current_season_id = ctx.season_id
        self.transition_to(ctx.state)

        # Restore the view
        if ctx.state == AppState.LIBRARY_ROOT:
            if self._main_window:
                self._main_window.library_view.set_tab(ctx.tab)
            self.refresh_library()
        elif ctx.state == AppState.SERIES_DRILLDOWN_SEASONS and ctx.series_id:
            self.load_seasons(ctx.series_id)
        elif ctx.state == AppState.SERIES_DRILLDOWN_EPISODES and ctx.season_id:
            self.load_episodes(ctx.season_id)

        # Restore selection
        if ctx.selected_item_id and self._main_window:
            self._main_window.library_view.select_by_id(str(ctx.selected_item_id))

    def delete_selected(self) -> None:
        """Delete the currently selected item."""
        if not self._main_window:
            return

        item = self._main_window.library_view.get_selected_item()
        if not item:
            return

        title = item.get("title") or self.tr("this item")
        item_type = item.get("type")

        # Check if item has a downloaded file
        item_state = item.get("state")
        if item_state != DownloadState.COMPLETED.value:
            self._main_window.show_toast(
                self.tr("No downloaded file to delete"), "warning"
            )
            return

        confirmed = self._main_window.show_confirm(
            self.tr("Delete {title}?").format(title=title),
            self.tr("This will remove the file from disk but keep the catalog entry."),
        )

        if confirmed:
            item_id = item.get("id")
            if not item_id:
                self._main_window.show_toast(
                    self.tr("Failed to delete: invalid item"), "error"
                )
                return

            delete_id = item.get("file_id") if item_type == "episode" else item_id
            if delete_id is None:
                self._main_window.show_toast(
                    self.tr("Failed to delete: invalid item"), "error"
                )
                return

            self._delete_worker = DeleteWorker(
                self._db_manager,
                str(item_type),
                delete_id,
                str(title),
                self._current_season_id,
            )
            self._delete_worker.delete_finished.connect(
                lambda status, view, deleted, failed: self._on_delete_finished(
                    status, view, deleted, failed, str(title)
                )
            )
            self._delete_worker.start()
            self._main_window.show_toast(
                self.tr("Deleting: {title}").format(title=title), "info"
            )

    @Slot(str, str, int, int)
    def _on_delete_finished(
        self, status: str, view: str, deleted: int, failed: int, title: str
    ) -> None:
        """Handle completion of a background delete operation."""
        if self._main_window:
            if status == "ok" and failed == 0:
                self._main_window.show_toast(
                    self.tr("Deleted {count} file(s): {title}").format(
                        count=deleted, title=title
                    ),
                    "info",
                )
            elif status == "ok":
                self._main_window.show_toast(
                    self.tr("Deleted {ok}, failed {failed}: {title}").format(
                        ok=deleted, failed=failed, title=title
                    ),
                    "warning",
                )
            else:
                self._main_window.show_toast(
                    self.tr("Failed to delete: {error}").format(error=status),
                    "error",
                )

        if view == "episodes" and self._current_season_id:
            self.load_episodes(self._current_season_id)
        else:
            self.refresh_library()

        self._delete_worker = None

    # =========================================================================
    # Search
    # =========================================================================

    def show_search(self) -> None:
        """Show the search overlay."""
        if not self._main_window:
            return

        self.push_navigation()
        self._main_window.show_search(self._search_filter or "")
        self.transition_to(AppState.SEARCH_OVERLAY)

    def hide_search(self) -> None:
        """Hide the search overlay."""
        if not self._main_window:
            return

        self._main_window.hide_search()
        self.pop_navigation()
        self.transition_to(AppState.LIBRARY_ROOT)

    def apply_search_filter(self, query: str) -> None:
        """Apply a search filter.

        Args:
            query: The search query.
        """
        self._search_filter = query if query else None
        self.refresh_library()
        logger.debug("Search filter applied: %s", self._search_filter)

    def clear_search_filter(self) -> None:
        """Clear the current search filter."""
        if self._search_filter:
            self._search_filter = None
            self.refresh_library()
            if self._main_window:
                self._main_window.show_toast(self.tr("Filter cleared"), "info")

    # =========================================================================
    # Sync
    # =========================================================================

    def trigger_sync(self) -> None:
        """Trigger a metadata sync."""
        if not self._metadata_service:
            if self._main_window:
                self._main_window.show_toast(
                    self.tr("Metadata service not available"), "error"
                )
            return

        if self._metadata_service.isRunning():
            if self._main_window:
                self._main_window.show_toast(
                    self.tr("Sync already in progress"), "warning"
                )
            return

        self._metadata_service.start()

    @Slot()
    def _on_sync_started(self) -> None:
        """Handle sync started."""
        if self._main_window:
            self._main_window.set_sync_status(self.tr("Syncing..."))
            self._main_window.show_toast(self.tr("Sync started"), "info")

    @Slot()
    def _on_sync_completed(self) -> None:
        """Handle sync completed."""
        if self._main_window:
            now = datetime.now().strftime("%H:%M")
            self._main_window.set_sync_status(
                self.tr("Last Sync: {time}").format(time=now)
            )
            self._main_window.show_toast(self.tr("Sync completed"), "info")
        self.refresh_library()

    @Slot(str)
    def _on_sync_error(self, error: str) -> None:
        """Handle sync error.

        Args:
            error: Error message.
        """
        if self._main_window:
            self._main_window.set_sync_status(self.tr("Sync failed"))
            self._main_window.show_toast(
                self.tr("Sync failed: {error}").format(error=error), "error"
            )

    # =========================================================================
    # Download
    # =========================================================================

    @Slot(int, int, float, float)
    def _on_download_progress(
        self,
        context_id: int,
        percentage: int,
        download_speed: float,
        upload_speed: float,
    ) -> None:
        """Handle download progress update.

        Args:
            context_id: Download context ID.
            percentage: Download percentage.
            download_speed: Download speed in KB/s.
            upload_speed: Upload speed in KB/s.
        """
        download_type = self._active_download_types.get(context_id)
        if download_type is None:
            download_type = self._resolve_download_type(context_id)

        updates = {
            "state": DownloadState.DOWNLOADING.value,
            "download_progress": percentage,
        }
        if self._main_window:
            if download_type == "season":
                self._update_visible_season_download(context_id, updates)
            else:
                self._main_window.library_view.update_item_by_file_id(
                    context_id, updates
                )

        try:
            if download_type == "season":
                self._db_manager.update_season_state(
                    context_id, DownloadState.DOWNLOADING, percentage
                )
            elif self._db_manager.get_video_file(context_id):
                self._db_manager.update_file_state(
                    context_id, DownloadState.DOWNLOADING, percentage
                )
        except Exception as e:
            logger.error("Failed to persist download progress: %s", e)

    def _resolve_download_type(self, context_id: int) -> str:
        """Resolve an untracked download context as movie or season."""
        if self._current_season_id == context_id and self._db_manager.get_season(
            context_id
        ):
            self._active_download_types[context_id] = "season"
            return "season"
        if self._db_manager.get_video_file(context_id):
            self._active_download_types[context_id] = "movie"
            return "movie"
        if self._db_manager.get_season(context_id):
            self._active_download_types[context_id] = "season"
            return "season"
        return "movie"

    def _update_visible_season_download(
        self, season_id: int, updates: dict[str, Any]
    ) -> None:
        """Apply season download status to the currently visible drilldown rows."""
        if not self._main_window:
            return

        if self._current_season_id == season_id:
            self._main_window.library_view.update_all_items(updates)
            return

        self._main_window.library_view.update_item(season_id, updates)

    @Slot(int, str)
    def _on_download_completed(self, file_id: int, path: str) -> None:
        """Handle download completed.

        Args:
            file_id: Video file ID.
            path: Path to the downloaded file.
        """
        if self._main_window:
            self._main_window.library_view.update_item_by_file_id(
                file_id,
                {"state": DownloadState.COMPLETED.value, "download_progress": 100},
            )
            self._main_window.show_toast(self.tr("Download completed"), "info")

        try:
            self._db_manager.update_file_state(file_id, DownloadState.COMPLETED, 100)
            self._db_manager.update_file_path(file_id, path)
        except Exception as e:
            logger.error("Failed to persist download completion: %s", e)

        video = self._db_manager.get_video_file(file_id)
        if video and video.get("subtitle_id"):
            season_id = video.get("season_id")
            requested_episode_id = (
                self._pending_episode_pipeline_by_season.get(season_id)
                if season_id
                else None
            )
            if season_id is None or requested_episode_id == file_id:
                if season_id:
                    self._pending_episode_pipeline_by_season.pop(season_id, None)
                self.start_pipeline(file_id)

    @Slot(int, str)
    def _on_download_error(self, file_id: int, error: str) -> None:
        """Handle download error.

        Args:
            file_id: Video file ID.
            error: Error message.
        """
        if self._main_window:
            self._main_window.library_view.update_item_by_file_id(
                file_id,
                {"state": DownloadState.ERROR.value},
            )
            self._main_window.show_toast(
                self.tr("Download failed: {error}").format(error=error), "error"
            )

        try:
            download_type = self._active_download_types.get(file_id)
            if download_type == "season":
                self._db_manager.update_season_state(file_id, DownloadState.ERROR)
            elif self._db_manager.get_video_file(file_id):
                self._db_manager.update_file_state(file_id, DownloadState.ERROR)
            elif self._db_manager.get_season(file_id):
                self._db_manager.update_season_state(file_id, DownloadState.ERROR)
        except Exception as e:
            logger.error("Failed to persist download error: %s", e)

    @Slot(int)
    def _on_season_completed(self, season_id: int) -> None:
        """Handle season pack completion."""
        try:
            self._db_manager.update_season_state(
                season_id, DownloadState.COMPLETED, 100
            )
            self._active_download_types.pop(season_id, None)
        except Exception as e:
            logger.error("Failed to persist season completion: %s", e)

        if self._main_window:
            if self._current_season_id == season_id:
                self.load_episodes(season_id)
            elif self._current_series_id:
                self.load_seasons(self._current_series_id)
            self._main_window.show_toast(self.tr("Season download completed"), "info")

    # =========================================================================
    # Pipeline
    # =========================================================================

    def start_pipeline(self, video_file_id: int, show_busy_toast: bool = True) -> None:
        """Start the voiceover pipeline for a video file.

        Args:
            video_file_id: Database ID of the video file to process.
        """
        if not self._pipeline_service:
            if self._main_window:
                self._main_window.show_toast(
                    self.tr("Pipeline service not available"), "error"
                )
            logger.error("PipelineService not bound")
            return

        if self._pipeline_service.is_busy():
            if video_file_id not in self._pending_pipeline_ids:
                self._pending_pipeline_ids.append(video_file_id)
            if show_busy_toast and self._main_window:
                self._main_window.show_toast(self.tr("Pipeline queued"), "info")
            return

        self._pipeline_service.start_process(video_file_id)
        logger.info("Pipeline started for video_file_id=%d", video_file_id)

    @Slot(int, PipelineState, str)
    def _on_pipeline_update(
        self, file_id: int, state: PipelineState, message: str
    ) -> None:
        """Handle pipeline progress update.

        Args:
            file_id: Video file ID.
            state: Pipeline state (PipelineState enum).
            message: Progress message.
        """
        if self._main_window:
            self._main_window.show_toast(
                self.tr("Processing: {message}").format(message=message), "info"
            )
            self._main_window.library_view.update_item_by_file_id(
                file_id, {"pipeline_state": state.value}
            )

    @Slot(int, bool)
    def _on_pipeline_finished(self, file_id: int, success: bool) -> None:
        """Handle pipeline completion.

        Args:
            file_id: Video file ID.
            success: Whether the pipeline completed successfully.
        """
        if self._main_window:
            if success:
                self._main_window.show_toast(self.tr("Subtitles ready"), "info")
            else:
                self._main_window.show_toast(
                    self.tr("Subtitle processing failed"), "error"
                )
            self._main_window.library_view.update_item_by_file_id(
                file_id,
                {
                    "pipeline_state": (
                        PipelineState.SUBS_READY.value
                        if success
                        else PipelineState.FAILED.value
                    )
                },
            )
        self.refresh_library()
        self._start_next_pending_pipeline()

    @Slot(int, str)
    def _on_pipeline_error(self, file_id: int, error: str) -> None:
        """Handle pipeline error.

        Args:
            file_id: Video file ID.
            error: Error message.
        """
        logger.error("Pipeline error for file %d: %s", file_id, error)
        if self._main_window:
            self._main_window.show_toast(
                self.tr("Pipeline error: {error}").format(error=error), "error"
            )
            self._main_window.library_view.update_item_by_file_id(
                file_id, {"pipeline_state": PipelineState.FAILED.value}
            )

    def _start_next_pending_pipeline(self) -> None:
        """Start the next queued pipeline job if the service is idle."""
        if not self._pipeline_service or self._pipeline_service.is_busy():
            return
        if not self._pending_pipeline_ids:
            return
        next_file_id = self._pending_pipeline_ids.pop(0)
        self.start_pipeline(next_file_id, show_busy_toast=False)

    # =========================================================================
    # Player
    # =========================================================================

    def play_media(self, file_id: int | str) -> None:
        """Start playing a media file.

        Args:
            file_id: ID of the video file to play.
        """
        if not self._main_window:
            return

        if not self._player_service:
            self._main_window.show_toast(
                self.tr("Player service not available"), "error"
            )
            logger.error("PlayerService not bound")
            return

        # Convert to int if needed (from library view item ID)
        try:
            video_file_id = int(file_id)
        except (ValueError, TypeError):
            # For movies, file_id might be the media_item_id (UUID string)
            # Look up the video file for this media item
            video_details = self._db_manager.get_video_details(str(file_id))
            if not video_details:
                self._main_window.show_toast(self.tr("Video file not found"), "error")
                logger.error("No video file found for media_id: %s", file_id)
                return
            video_file_id = video_details["id"]

        # Get video file details
        video = self._db_manager.get_video_file(video_file_id)
        if not video:
            self._main_window.show_toast(self.tr("Video file not found"), "error")
            logger.error("Video file not found: %d", video_file_id)
            return

        file_path = video.get("file_path")
        if not file_path:
            self._main_window.show_toast(self.tr("Video file path not set"), "error")
            logger.error("Video file has no file_path: %d", video_file_id)
            return

        # Check for subtitles (prefer Polish translated, fallback to original)
        subtitles = self._db_manager.get_subtitles(video_file_id)
        subtitle_path = None
        for lang_code in ["polish", "original"]:
            for sub in subtitles:
                if sub.get("language_code") == lang_code:
                    subtitle_path = sub.get("file_path")
                    break
            if subtitle_path:
                break

        if not subtitle_path:
            subtitle_path = self._player_service.find_matching_subtitle(file_path)

        # Store current file ID for resume position saving
        self._current_playing_file_id = video_file_id

        # Push navigation context before playing
        self.push_navigation()

        # Show player view and transition state
        self._main_window.show_player()
        self.transition_to(AppState.PLAYER_ACTIVE)

        try:
            # Initialize player with video frame
            frame_id = self._main_window.get_player_frame_id()
            self._player_service.initialize(frame_id)

            # Load and start playback
            self._player_service.load_video(file_path, subtitle_path)

            # Resume from saved position if available
            resume_position = video.get("resume_position_seconds", 0)
            self._resumed_from_position = resume_position
            self._playback_start_time = time.time()
            if resume_position > 0:
                self._player_service.set_position_seconds(resume_position)
                logger.info("Resuming playback from %d seconds", resume_position)

            logger.info(
                "Started playback: %s (file_id=%d)",
                video.get("media_title", file_path),
                video_file_id,
            )

        except FileNotFoundError as e:
            self._main_window.show_toast(
                self.tr("File not found: {error}").format(error=e), "error"
            )
            logger.error("Failed to load video: %s", e)
            self.stop_player()
        except Exception as e:
            self._main_window.show_toast(
                self.tr("Playback error: {error}").format(error=e), "error"
            )
            logger.error("Playback error: %s", e)
            self.stop_player()

    def stop_player(self, save_position: bool = True) -> None:
        """Stop playback and return to library.

        Args:
            save_position: Whether to save the current position for resume.
        """
        if not self._main_window:
            return

        # Save resume position
        if save_position:
            self._save_resume_position()

        # Stop playback
        if self._player_service:
            self._player_service.stop()

        # Clear current file ID
        self._current_playing_file_id = None

        # Hide player view
        self._main_window.hide_player()

        # Navigate back to previous context
        self.navigate_back()

        logger.info("Player stopped")

    def _save_resume_position(self) -> None:
        """Save the current playback position for resume."""
        if not self._player_service or not self._current_playing_file_id:
            return

        position = self._player_service.get_position_seconds()
        if position > 0:
            try:
                self._db_manager.update_resume_position(
                    self._current_playing_file_id, position
                )
                logger.debug(
                    "Saved resume position: %d seconds for file %d",
                    position,
                    self._current_playing_file_id,
                )
            except Exception as e:
                logger.error("Failed to save resume position: %s", e)

    def player_toggle_pause(self) -> None:
        """Toggle playback pause state."""
        if not self._player_service or not self._main_window:
            return

        self._player_service.toggle_pause()
        is_paused = not self._player_service.is_playing()
        self._main_window.player_view.show_pause_indicator(is_paused)

    def player_seek_forward(self) -> None:
        """Seek forward in playback."""
        if not self._player_service or not self._main_window:
            return

        self._player_service.seek_forward()
        self._main_window.player_view.show_seek_indicator(forward=True)

    def player_seek_backward(self) -> None:
        """Seek backward in playback."""
        if not self._player_service or not self._main_window:
            return

        self._player_service.seek_backward()
        self._main_window.player_view.show_seek_indicator(forward=False)

    def player_volume_up(self) -> None:
        """Increase playback volume."""
        if not self._player_service or not self._main_window:
            return

        new_volume = self._player_service.volume_up()
        self._main_window.player_view.show_volume_indicator(new_volume, is_muted=False)

    def player_volume_down(self) -> None:
        """Decrease playback volume."""
        if not self._player_service or not self._main_window:
            return

        new_volume = self._player_service.volume_down()
        self._main_window.player_view.show_volume_indicator(new_volume, is_muted=False)

    def player_toggle_mute(self) -> None:
        """Toggle audio mute state."""
        if not self._player_service or not self._main_window:
            return

        volume, is_muted = self._player_service.toggle_mute()
        self._main_window.player_view.show_volume_indicator(volume, is_muted=is_muted)

    def player_cycle_audio(self) -> None:
        """Cycle through available audio tracks."""
        if not self._player_service or not self._main_window:
            return

        self._player_service.cycle_audio_track()
        current_track = self._player_service.get_current_audio_track()
        if current_track:
            self._main_window.player_view.show_audio_track_indicator(
                current_track["name"]
            )

    @Slot()
    def _on_playback_finished(self) -> None:
        """Handle playback finished event."""
        logger.info("Playback finished")

        # Detect invalid resume: if playback finished within 3 seconds of starting
        # and we had a non-zero resume position, the position was likely invalid
        elapsed = time.time() - (self._playback_start_time or 0)
        if elapsed < 3.0 and self._resumed_from_position > 0:
            logger.warning(
                "Playback finished too quickly (%.1fs) after resuming from %ds - "
                "likely invalid resume position, clearing it",
                elapsed,
                self._resumed_from_position,
            )

        # Clear resume position when playback completes
        if self._current_playing_file_id:
            try:
                self._db_manager.mark_video_file_watched(self._current_playing_file_id)
            except Exception as e:
                logger.error("Failed to mark playback watched: %s", e)

        # Reset tracking variables
        self._playback_start_time = None
        self._resumed_from_position = 0

        # Stop player and return to library (skip saving position since we just cleared it)
        self.stop_player(save_position=False)

    @Slot(int, int)
    def _on_time_changed(self, current_ms: int, total_ms: int) -> None:
        """Handle playback time update.

        Args:
            current_ms: Current playback position in milliseconds.
            total_ms: Total media duration in milliseconds.
        """
        # Could update status bar or progress indicator here
        pass

    @Slot(str)
    def _on_player_error(self, error: str) -> None:
        """Handle player error event.

        Args:
            error: Error message.
        """
        logger.error("Player error: %s", error)
        if self._main_window:
            self._main_window.show_toast(
                self.tr("Player error: {error}").format(error=error), "error"
            )
        self.stop_player()

    # =========================================================================
    # UI Callbacks
    # =========================================================================

    @Slot(dict)
    def on_item_activated(self, item: dict[str, Any]) -> None:
        """Handle item activation from LibraryView.

        Args:
            item: The activated item data.
        """
        # This is handled by activate_selected via InputManager
        pass

    @Slot(dict)
    def on_selection_changed(self, item: dict[str, Any]) -> None:
        """Handle selection change from LibraryView.

        Args:
            item: The newly selected item data.
        """
        # Could update status bar or other UI elements here
        pass

    @Slot(MediaTab)
    def on_tab_changed(self, tab: MediaTab) -> None:
        """Handle tab change from LibraryView.

        Args:
            tab: The new active tab.
        """
        self._current_tab = tab
        self.refresh_library()

    @Slot(str)
    def on_search_committed(self, query: str) -> None:
        """Handle search commit from SearchOverlay.

        Args:
            query: The search query.
        """
        self.apply_search_filter(query)
        self.hide_search()

    @Slot()
    def on_search_cancelled(self) -> None:
        """Handle search cancel from SearchOverlay."""
        self.clear_search_filter()
        self.hide_search()

    # =========================================================================
    # Application
    # =========================================================================

    def quit_application(self) -> None:
        """Quit the application."""
        logger.info("Quit requested")
        if self._main_window:
            self._main_window.close()
