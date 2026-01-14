"""Tests for AppController."""

import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from src.config import DownloadState
from src.controllers.app_controller import (
    AppController,
    DialogConfirmHandler,
    LibraryRootHandler,
    NavigationContext,
    PlayerActiveHandler,
    SearchOverlayHandler,
    SeriesDrilldownEpisodesHandler,
    SeriesDrilldownSeasonsHandler,
    StateHandler,
)
from src.database.db_manager import DatabaseManager
from src.ui.enums import Action, AppState, MediaTab


class TestNavigationContext:
    """Tests for NavigationContext dataclass."""

    def test_creation(self) -> None:
        """Test NavigationContext creation."""
        ctx = NavigationContext(
            state=AppState.LIBRARY_ROOT,
            tab=MediaTab.MOVIES,
            selected_item_id="test-id",
        )
        assert ctx.state == AppState.LIBRARY_ROOT
        assert ctx.tab == MediaTab.MOVIES
        assert ctx.selected_item_id == "test-id"

    def test_defaults(self) -> None:
        """Test NavigationContext default values."""
        ctx = NavigationContext(
            state=AppState.LIBRARY_ROOT,
            tab=MediaTab.MOVIES,
        )
        assert ctx.selected_item_id is None
        assert ctx.series_id is None
        assert ctx.season_id is None


class TestAppController:
    """Tests for AppController class."""

    @pytest.fixture
    def db_manager(self) -> DatabaseManager:
        """Create a test database manager."""
        manager = DatabaseManager(":memory:")
        manager.initialize()
        return manager

    @pytest.fixture
    def controller(self, db_manager: DatabaseManager) -> AppController:
        """Create an AppController instance."""
        return AppController(db_manager)

    def test_initialization(self, controller: AppController) -> None:
        """Test AppController initialization."""
        assert controller is not None
        assert controller.current_state == AppState.LIBRARY_ROOT
        assert controller.current_tab == MediaTab.MOVIES
        assert controller.search_filter is None

    def test_state_handlers_exist(self, controller: AppController) -> None:
        """Test that all state handlers are registered."""
        assert AppState.LIBRARY_ROOT in controller._state_handlers
        assert AppState.SERIES_DRILLDOWN_SEASONS in controller._state_handlers
        assert AppState.SERIES_DRILLDOWN_EPISODES in controller._state_handlers
        assert AppState.SEARCH_OVERLAY in controller._state_handlers
        assert AppState.DIALOG_CONFIRM in controller._state_handlers
        assert AppState.PLAYER_ACTIVE in controller._state_handlers

    def test_transition_to(self, controller: AppController) -> None:
        """Test state transition."""
        controller.transition_to(AppState.SEARCH_OVERLAY)
        assert controller.current_state == AppState.SEARCH_OVERLAY

    def test_transition_to_same_state(self, controller: AppController) -> None:
        """Test transition to same state is no-op."""
        initial_state = controller.current_state
        controller.transition_to(initial_state)
        assert controller.current_state == initial_state

    def test_push_navigation(self, controller: AppController) -> None:
        """Test pushing navigation context."""
        # Setup mock main window
        mock_window = MagicMock()
        mock_window.library_view.get_selected_item.return_value = {"id": "test-id"}
        controller._main_window = mock_window

        controller.push_navigation()
        assert len(controller._navigation_stack) == 1

    def test_pop_navigation(self, controller: AppController) -> None:
        """Test popping navigation context."""
        # Add a context manually
        ctx = NavigationContext(
            state=AppState.LIBRARY_ROOT,
            tab=MediaTab.MOVIES,
            selected_item_id="test-id",
        )
        controller._navigation_stack.append(ctx)

        popped = controller.pop_navigation()
        assert popped == ctx
        assert len(controller._navigation_stack) == 0

    def test_pop_navigation_empty(self, controller: AppController) -> None:
        """Test popping from empty navigation stack."""
        result = controller.pop_navigation()
        assert result is None

    def test_main_window_property_raises_without_binding(
        self, controller: AppController
    ) -> None:
        """Test that main_window property raises without binding."""
        with pytest.raises(RuntimeError):
            _ = controller.main_window

    def test_bind_main_window(self, controller: AppController) -> None:
        """Test binding main window."""
        mock_window = MagicMock()
        controller.bind_main_window(mock_window)
        assert controller._main_window == mock_window

    def test_apply_search_filter(self, controller: AppController) -> None:
        """Test applying search filter."""
        mock_window = MagicMock()
        mock_window.library_view.get_current_tab.return_value = MediaTab.MOVIES
        controller._main_window = mock_window

        controller.apply_search_filter("test query")
        assert controller.search_filter == "test query"

    def test_apply_search_filter_empty(self, controller: AppController) -> None:
        """Test applying empty search filter clears filter."""
        controller._search_filter = "existing"
        mock_window = MagicMock()
        mock_window.library_view.get_current_tab.return_value = MediaTab.MOVIES
        controller._main_window = mock_window

        controller.apply_search_filter("")
        assert controller.search_filter is None

    def test_clear_search_filter(self, controller: AppController) -> None:
        """Test clearing search filter."""
        controller._search_filter = "test"
        mock_window = MagicMock()
        mock_window.library_view.get_current_tab.return_value = MediaTab.MOVIES
        controller._main_window = mock_window

        controller.clear_search_filter()
        assert controller.search_filter is None

    def test_shutdown(self, controller: AppController) -> None:
        """Test shutdown method."""
        controller.shutdown()  # Should not raise


class TestLibraryRootHandler:
    """Tests for LibraryRootHandler."""

    @pytest.fixture
    def controller(self) -> MagicMock:
        """Create a mock controller."""
        return MagicMock()

    @pytest.fixture
    def handler(self, controller: MagicMock) -> LibraryRootHandler:
        """Create a LibraryRootHandler instance."""
        return LibraryRootHandler(controller)

    def test_navigate_up(
        self, handler: LibraryRootHandler, controller: MagicMock
    ) -> None:
        """Test navigate up action."""
        result = handler.handle_action(Action.NAVIGATE_UP, {})
        assert result is True
        controller.main_window.library_view.select_prev.assert_called_once()

    def test_navigate_down(
        self, handler: LibraryRootHandler, controller: MagicMock
    ) -> None:
        """Test navigate down action."""
        result = handler.handle_action(Action.NAVIGATE_DOWN, {})
        assert result is True
        controller.main_window.library_view.select_next.assert_called_once()

    def test_switch_tab(
        self, handler: LibraryRootHandler, controller: MagicMock
    ) -> None:
        """Test switch tab action."""
        result = handler.handle_action(Action.SWITCH_TAB, {})
        assert result is True
        controller.main_window.library_view.switch_tab.assert_called_once()
        controller.refresh_library.assert_called_once()

    def test_confirm(self, handler: LibraryRootHandler, controller: MagicMock) -> None:
        """Test confirm action."""
        result = handler.handle_action(Action.CONFIRM, {})
        assert result is True
        controller.activate_selected.assert_called_once()

    def test_search(self, handler: LibraryRootHandler, controller: MagicMock) -> None:
        """Test search action."""
        result = handler.handle_action(Action.SEARCH, {})
        assert result is True
        controller.show_search.assert_called_once()

    def test_clear_filter(
        self, handler: LibraryRootHandler, controller: MagicMock
    ) -> None:
        """Test clear filter action."""
        result = handler.handle_action(Action.CLEAR_FILTER, {})
        assert result is True
        controller.clear_search_filter.assert_called_once()

    def test_delete(self, handler: LibraryRootHandler, controller: MagicMock) -> None:
        """Test delete action."""
        result = handler.handle_action(Action.DELETE, {})
        assert result is True
        controller.delete_selected.assert_called_once()

    def test_sync(self, handler: LibraryRootHandler, controller: MagicMock) -> None:
        """Test sync action."""
        result = handler.handle_action(Action.SYNC, {})
        assert result is True
        controller.trigger_sync.assert_called_once()

    def test_quit(self, handler: LibraryRootHandler, controller: MagicMock) -> None:
        """Test quit action."""
        result = handler.handle_action(Action.QUIT, {})
        assert result is True
        controller.quit_application.assert_called_once()

    def test_unhandled_action(self, handler: LibraryRootHandler) -> None:
        """Test unhandled action returns False."""
        result = handler.handle_action(Action.TOGGLE_PAUSE, {})
        assert result is False


class TestSeriesDrilldownSeasonsHandler:
    """Tests for SeriesDrilldownSeasonsHandler."""

    @pytest.fixture
    def controller(self) -> MagicMock:
        """Create a mock controller."""
        return MagicMock()

    @pytest.fixture
    def handler(self, controller: MagicMock) -> SeriesDrilldownSeasonsHandler:
        """Create handler instance."""
        return SeriesDrilldownSeasonsHandler(controller)

    def test_cancel_navigates_back(
        self, handler: SeriesDrilldownSeasonsHandler, controller: MagicMock
    ) -> None:
        """Test cancel action navigates back."""
        result = handler.handle_action(Action.CANCEL, {})
        assert result is True
        controller.navigate_back.assert_called_once()


class TestSeriesDrilldownEpisodesHandler:
    """Tests for SeriesDrilldownEpisodesHandler."""

    @pytest.fixture
    def controller(self) -> MagicMock:
        """Create a mock controller."""
        return MagicMock()

    @pytest.fixture
    def handler(self, controller: MagicMock) -> SeriesDrilldownEpisodesHandler:
        """Create handler instance."""
        return SeriesDrilldownEpisodesHandler(controller)

    def test_delete_available(
        self, handler: SeriesDrilldownEpisodesHandler, controller: MagicMock
    ) -> None:
        """Test delete action is available in episodes view."""
        result = handler.handle_action(Action.DELETE, {})
        assert result is True
        controller.delete_selected.assert_called_once()


class TestSearchOverlayHandler:
    """Tests for SearchOverlayHandler."""

    @pytest.fixture
    def controller(self) -> MagicMock:
        """Create a mock controller."""
        return MagicMock()

    @pytest.fixture
    def handler(self, controller: MagicMock) -> SearchOverlayHandler:
        """Create handler instance."""
        return SearchOverlayHandler(controller)

    def test_cancel_hides_search(
        self, handler: SearchOverlayHandler, controller: MagicMock
    ) -> None:
        """Test cancel action hides search overlay."""
        result = handler.handle_action(Action.CANCEL, {})
        assert result is True
        controller.hide_search.assert_called_once()


class TestDialogConfirmHandler:
    """Tests for DialogConfirmHandler."""

    @pytest.fixture
    def handler(self) -> DialogConfirmHandler:
        """Create handler instance."""
        return DialogConfirmHandler(MagicMock())

    def test_returns_false(self, handler: DialogConfirmHandler) -> None:
        """Test handler returns False (dialog handles input)."""
        result = handler.handle_action(Action.CONFIRM, {})
        assert result is False


class TestPlayerActiveHandler:
    """Tests for PlayerActiveHandler."""

    @pytest.fixture
    def controller(self) -> MagicMock:
        """Create a mock controller."""
        return MagicMock()

    @pytest.fixture
    def handler(self, controller: MagicMock) -> PlayerActiveHandler:
        """Create handler instance."""
        return PlayerActiveHandler(controller)

    def test_cancel_stops_player(
        self, handler: PlayerActiveHandler, controller: MagicMock
    ) -> None:
        """Test cancel action stops player."""
        result = handler.handle_action(Action.CANCEL, {})
        assert result is True
        controller.stop_player.assert_called_once()

    def test_quit_stops_player_first(
        self, handler: PlayerActiveHandler, controller: MagicMock
    ) -> None:
        """Test quit action stops player before quitting."""
        result = handler.handle_action(Action.QUIT, {})
        assert result is True
        controller.stop_player.assert_called_once()
        controller.quit_application.assert_called_once()

    def test_toggle_pause(
        self, handler: PlayerActiveHandler, controller: MagicMock
    ) -> None:
        """Test toggle pause action."""
        result = handler.handle_action(Action.TOGGLE_PAUSE, {})
        assert result is True
        controller.player_toggle_pause.assert_called_once()

    def test_confirm_toggles_pause(
        self, handler: PlayerActiveHandler, controller: MagicMock
    ) -> None:
        """Test confirm (Enter) toggles pause in player."""
        result = handler.handle_action(Action.CONFIRM, {})
        assert result is True
        controller.player_toggle_pause.assert_called_once()

    def test_seek_forward(
        self, handler: PlayerActiveHandler, controller: MagicMock
    ) -> None:
        """Test seek forward action."""
        result = handler.handle_action(Action.NAVIGATE_RIGHT, {})
        assert result is True
        controller.player_seek_forward.assert_called_once()

    def test_seek_backward(
        self, handler: PlayerActiveHandler, controller: MagicMock
    ) -> None:
        """Test seek backward action."""
        result = handler.handle_action(Action.NAVIGATE_LEFT, {})
        assert result is True
        controller.player_seek_backward.assert_called_once()

    def test_volume_up(
        self, handler: PlayerActiveHandler, controller: MagicMock
    ) -> None:
        """Test volume up action."""
        result = handler.handle_action(Action.NAVIGATE_UP, {})
        assert result is True
        controller.player_volume_up.assert_called_once()

    def test_volume_down(
        self, handler: PlayerActiveHandler, controller: MagicMock
    ) -> None:
        """Test volume down action."""
        result = handler.handle_action(Action.NAVIGATE_DOWN, {})
        assert result is True
        controller.player_volume_down.assert_called_once()

    def test_toggle_mute(
        self, handler: PlayerActiveHandler, controller: MagicMock
    ) -> None:
        """Test toggle mute action."""
        result = handler.handle_action(Action.TOGGLE_MUTE, {})
        assert result is True
        controller.player_toggle_mute.assert_called_once()

    def test_cycle_audio(
        self, handler: PlayerActiveHandler, controller: MagicMock
    ) -> None:
        """Test cycle audio action."""
        result = handler.handle_action(Action.CYCLE_AUDIO, {})
        assert result is True
        controller.player_cycle_audio.assert_called_once()

    def test_unhandled_action(
        self, handler: PlayerActiveHandler, controller: MagicMock
    ) -> None:
        """Test unhandled action returns False."""
        result = handler.handle_action(Action.SEARCH, {})
        assert result is False


class TestStateHandlerBase:
    """Tests for StateHandler base class."""

    def test_on_enter_default(self) -> None:
        """Test default on_enter does nothing."""
        controller = MagicMock()
        handler = LibraryRootHandler(controller)
        # Should not raise
        handler.on_enter()

    def test_on_exit_default(self) -> None:
        """Test default on_exit does nothing."""
        controller = MagicMock()
        handler = LibraryRootHandler(controller)
        # Should not raise
        handler.on_exit()


class TestAppControllerAdvanced:
    """Advanced tests for AppController to achieve >80% coverage."""

    @pytest.fixture
    def db_manager(self) -> DatabaseManager:
        """Create a test database manager."""
        manager = DatabaseManager(":memory:")
        manager.initialize()
        return manager

    @pytest.fixture
    def controller(self, db_manager: DatabaseManager) -> AppController:
        """Create an AppController instance."""
        return AppController(db_manager)

    @pytest.fixture
    def mock_main_window(self) -> MagicMock:
        """Create a mock main window."""
        window = MagicMock()
        window.library_view.get_current_tab.return_value = MediaTab.MOVIES
        window.library_view.get_selected_item.return_value = None
        window.input_manager = MagicMock()
        return window

    def test_bind_services_with_metadata_service(
        self, controller: AppController
    ) -> None:
        """Test binding metadata service."""
        mock_metadata = MagicMock()
        controller.bind_services(metadata_service=mock_metadata)
        assert controller._metadata_service == mock_metadata
        mock_metadata.sync_started.connect.assert_called_once()
        mock_metadata.sync_completed.connect.assert_called_once()
        mock_metadata.sync_error.connect.assert_called_once()

    def test_bind_services_with_torrent_service(
        self, controller: AppController
    ) -> None:
        """Test binding torrent service."""
        mock_torrent = MagicMock()
        controller.bind_services(torrent_service=mock_torrent)
        assert controller._torrent_service == mock_torrent
        mock_torrent.download_progress.connect.assert_called_once()
        mock_torrent.download_completed.connect.assert_called_once()
        mock_torrent.download_error.connect.assert_called_once()

    def test_bind_services_with_pipeline_service(
        self, controller: AppController
    ) -> None:
        """Test binding pipeline service."""
        mock_pipeline = MagicMock()
        controller.bind_services(pipeline_service=mock_pipeline)
        assert controller._pipeline_service == mock_pipeline
        mock_pipeline.signals.pipeline_update.connect.assert_called_once()
        mock_pipeline.signals.pipeline_finished.connect.assert_called_once()
        mock_pipeline.signals.error_occurred.connect.assert_called_once()

    def test_start_pipeline_calls_service(self, controller: AppController) -> None:
        """Test start_pipeline dispatches to pipeline service."""
        mock_pipeline = MagicMock()
        mock_pipeline.is_busy.return_value = False
        controller._pipeline_service = mock_pipeline

        controller.start_pipeline(video_file_id=42)

        mock_pipeline.start_process.assert_called_once_with(42)

    def test_start_pipeline_without_service(self, controller: AppController) -> None:
        """Test start_pipeline does nothing when service not bound."""
        controller._pipeline_service = None
        controller.start_pipeline(video_file_id=42)

    def test_bootstrap_calls_get_incomplete_pipelines(
        self, controller: AppController, mock_main_window: MagicMock
    ) -> None:
        """Test bootstrap retrieves incomplete pipelines from database."""
        controller._main_window = mock_main_window
        mock_pipeline = MagicMock()
        mock_pipeline.is_busy.return_value = False
        controller._pipeline_service = mock_pipeline
        controller._db_manager.get_incomplete_pipelines = MagicMock(
            return_value=[
                {"id": 1, "file_path": "/video1.mp4"},
                {"id": 2, "file_path": "/video2.mp4"},
            ]
        )

        controller.bootstrap()

        controller._db_manager.get_incomplete_pipelines.assert_called_once()
        mock_pipeline.start_process.assert_any_call(1)
        mock_pipeline.start_process.assert_any_call(2)
        assert mock_pipeline.start_process.call_count == 2

    def test_bootstrap_handles_no_incomplete_pipelines(
        self, controller: AppController, mock_main_window: MagicMock
    ) -> None:
        """Test bootstrap handles empty incomplete pipelines list."""
        controller._main_window = mock_main_window
        mock_pipeline = MagicMock()
        controller._pipeline_service = mock_pipeline
        controller._db_manager.get_incomplete_pipelines = MagicMock(return_value=[])

        controller.bootstrap()

        controller._db_manager.get_incomplete_pipelines.assert_called_once()
        mock_pipeline.start_process.assert_not_called()

    def test_on_download_completed_triggers_pipeline(
        self, controller: AppController
    ) -> None:
        """Test download completion triggers pipeline for video with subtitle_id."""
        mock_pipeline = MagicMock()
        mock_pipeline.is_busy.return_value = False
        controller._pipeline_service = mock_pipeline
        controller._db_manager.get_video_file = MagicMock(
            return_value={
                "id": 1,
                "subtitle_id": 12345,
                "needs_translation": True,
                "pipeline_state": "NONE",
            }
        )

        controller._on_download_completed(file_id=1, path="/video.mp4")

        mock_pipeline.start_process.assert_called_once_with(1)

    def test_on_download_completed_skips_without_subtitle(
        self, controller: AppController
    ) -> None:
        """Test download completion skips pipeline when subtitle_id is null."""
        mock_pipeline = MagicMock()
        controller._pipeline_service = mock_pipeline
        controller._db_manager.get_video_file = MagicMock(
            return_value={
                "id": 1,
                "subtitle_id": None,
                "needs_translation": False,
                "pipeline_state": "NONE",
            }
        )

        controller._on_download_completed(file_id=1, path="/video.mp4")

        mock_pipeline.start_process.assert_not_called()

    def test_on_pipeline_error_shows_toast(
        self, controller: AppController, mock_main_window: MagicMock
    ) -> None:
        """Test pipeline error displays toast notification."""
        controller._main_window = mock_main_window

        controller._on_pipeline_error(file_id=42, error="Translation failed")

        mock_main_window.show_toast.assert_called_once()
        call_args = mock_main_window.show_toast.call_args
        assert "Translation failed" in call_args[0][0]
        assert call_args[0][1] == "error"

    def test_on_pipeline_finished_updates_ui(
        self, controller: AppController, mock_main_window: MagicMock
    ) -> None:
        """Test pipeline completion refreshes library view."""
        controller._main_window = mock_main_window

        controller._on_pipeline_finished(file_id=42, success=True)

        mock_main_window.library_view.set_items.assert_called()

    def test_bind_services_preserves_existing_services(
        self, controller: AppController
    ) -> None:
        """Test binding one service doesn't unbind others."""
        mock_metadata = MagicMock()
        mock_torrent = MagicMock()
        mock_pipeline = MagicMock()

        controller.bind_services(
            metadata_service=mock_metadata,
            torrent_service=mock_torrent,
            pipeline_service=mock_pipeline,
        )

        assert controller._metadata_service == mock_metadata
        assert controller._torrent_service == mock_torrent
        assert controller._pipeline_service == mock_pipeline

    def test_bootstrap_without_main_window(self, controller: AppController) -> None:
        """Test bootstrap without main window bound."""
        # Should not raise, just skip window operations
        controller.bootstrap()

    def test_bootstrap_with_main_window(
        self, controller: AppController, mock_main_window: MagicMock
    ) -> None:
        """Test bootstrap with main window bound."""
        controller._main_window = mock_main_window
        controller.bootstrap()
        mock_main_window.set_connection_status.assert_called_once_with(True)
        mock_main_window.set_sync_status.assert_called_once()
        mock_main_window.set_storage_usage.assert_called_once()

    def test_transition_to_calls_handlers(
        self, controller: AppController, mock_main_window: MagicMock
    ) -> None:
        """Test state transition calls on_exit and on_enter."""
        controller._main_window = mock_main_window

        # Spy on handlers
        old_handler = controller._state_handlers[AppState.LIBRARY_ROOT]
        new_handler = controller._state_handlers[AppState.SEARCH_OVERLAY]
        old_handler.on_exit = MagicMock()
        new_handler.on_enter = MagicMock()

        controller.transition_to(AppState.SEARCH_OVERLAY)

        old_handler.on_exit.assert_called_once()
        new_handler.on_enter.assert_called_once()
        mock_main_window.input_manager.reset_debounce.assert_called_once()

    def test_handle_action_with_handler(
        self, controller: AppController, mock_main_window: MagicMock
    ) -> None:
        """Test handle_action dispatches to state handler."""
        controller._main_window = mock_main_window
        mock_main_window.library_view.select_next = MagicMock()

        controller.handle_action(Action.NAVIGATE_DOWN, {})
        mock_main_window.library_view.select_next.assert_called_once()

    def test_handle_action_unhandled(self, controller: AppController) -> None:
        """Test handle_action with unhandled action logs but doesn't raise."""
        # Should not raise
        controller.handle_action(Action.TOGGLE_PAUSE, {})

    def test_refresh_library_movies(
        self, controller: AppController, mock_main_window: MagicMock
    ) -> None:
        """Test refresh_library with movies tab."""
        controller._main_window = mock_main_window
        mock_main_window.library_view.get_current_tab.return_value = MediaTab.MOVIES

        controller.refresh_library()

        mock_main_window.library_view.set_items.assert_called_once()

    def test_refresh_library_with_movie_video_details(
        self, controller: AppController, mock_main_window: MagicMock
    ) -> None:
        """Test refresh_library includes video details for movies."""
        controller._main_window = mock_main_window
        mock_main_window.library_view.get_current_tab.return_value = MediaTab.MOVIES

        # Mock database methods
        controller._db_manager.get_library_items = MagicMock(
            return_value=[
                {
                    "id": "movie-1",
                    "type": "movie",
                    "title": "Test Movie",
                    "genres": "Action",
                }
            ]
        )
        controller._db_manager.get_video_details = MagicMock(
            return_value={
                "state": DownloadState.COMPLETED.value,
                "pipeline_state": None,
                "download_progress": 100,
            }
        )

        controller.refresh_library()

        mock_main_window.library_view.set_items.assert_called_once()
        items = mock_main_window.library_view.set_items.call_args[0][0]
        assert len(items) == 1
        assert items[0]["state"] == DownloadState.COMPLETED.value

    def test_refresh_library_with_series(
        self, controller: AppController, mock_main_window: MagicMock
    ) -> None:
        """Test refresh_library with series includes season count."""
        controller._main_window = mock_main_window
        mock_main_window.library_view.get_current_tab.return_value = MediaTab.SERIES

        # Mock database methods
        controller._db_manager.get_library_items = MagicMock(
            return_value=[
                {
                    "id": "series-1",
                    "type": "series",
                    "title": "Test Series",
                    "genres": "Drama",
                }
            ]
        )
        controller._db_manager.get_seasons = MagicMock(
            return_value=[
                {"id": 1, "season_number": 1},
                {"id": 2, "season_number": 2},
            ]
        )

        controller.refresh_library()

        mock_main_window.library_view.set_items.assert_called_once()
        items = mock_main_window.library_view.set_items.call_args[0][0]
        assert len(items) == 1
        assert items[0]["season_count"] == 2

    def test_refresh_library_error(
        self, controller: AppController, mock_main_window: MagicMock
    ) -> None:
        """Test refresh_library handles errors."""
        controller._main_window = mock_main_window
        controller._db_manager.get_library_items = MagicMock(
            side_effect=Exception("DB Error")
        )

        controller.refresh_library()

        mock_main_window.show_toast.assert_called_once()
        assert "Failed to load library" in mock_main_window.show_toast.call_args[0][0]

    def test_load_seasons(
        self, controller: AppController, mock_main_window: MagicMock
    ) -> None:
        """Test load_seasons loads season data."""
        controller._main_window = mock_main_window

        # Mock database methods
        controller._db_manager.get_seasons = MagicMock(
            return_value=[
                {"id": 1, "season_number": 1, "state": DownloadState.PENDING.value}
            ]
        )
        controller._db_manager.get_episodes = MagicMock(
            return_value=[
                {"id": 1, "episode_number": 1},
                {"id": 2, "episode_number": 2},
            ]
        )

        controller.load_seasons("series-1")

        assert controller._current_series_id == "series-1"
        mock_main_window.library_view.set_items.assert_called_once()

    def test_load_seasons_without_window(self, controller: AppController) -> None:
        """Test load_seasons does nothing without main window."""
        controller.load_seasons("series-1")
        # Should not raise

    def test_load_seasons_error(
        self, controller: AppController, mock_main_window: MagicMock
    ) -> None:
        """Test load_seasons handles errors."""
        controller._main_window = mock_main_window
        controller._db_manager.get_seasons = MagicMock(
            side_effect=Exception("DB Error")
        )

        controller.load_seasons("series-1")

        mock_main_window.show_toast.assert_called_once()
        assert "Failed to load seasons" in mock_main_window.show_toast.call_args[0][0]

    def test_load_episodes(
        self, controller: AppController, mock_main_window: MagicMock
    ) -> None:
        """Test load_episodes loads episode data."""
        controller._main_window = mock_main_window

        # Mock database methods
        controller._db_manager.get_episodes = MagicMock(
            return_value=[
                {
                    "id": 1,
                    "episode_number": 1,
                    "episode_title": "Pilot",
                    "state": DownloadState.PENDING.value,
                }
            ]
        )

        controller.load_episodes(1)

        assert controller._current_season_id == 1
        mock_main_window.library_view.set_items.assert_called_once()

    def test_load_episodes_without_window(self, controller: AppController) -> None:
        """Test load_episodes does nothing without main window."""
        controller.load_episodes(1)
        # Should not raise

    def test_load_episodes_error(
        self, controller: AppController, mock_main_window: MagicMock
    ) -> None:
        """Test load_episodes handles errors."""
        controller._main_window = mock_main_window
        controller._db_manager.get_episodes = MagicMock(
            side_effect=Exception("DB Error")
        )

        controller.load_episodes(1)

        mock_main_window.show_toast.assert_called_once()
        assert "Failed to load episodes" in mock_main_window.show_toast.call_args[0][0]

    def test_activate_selected_series(
        self, controller: AppController, mock_main_window: MagicMock
    ) -> None:
        """Test activate_selected drills into series."""
        controller._main_window = mock_main_window
        mock_main_window.library_view.get_selected_item.return_value = {
            "id": "series-1",
            "type": "series",
            "title": "Test Series",
        }

        controller.activate_selected()

        assert controller.current_state == AppState.SERIES_DRILLDOWN_SEASONS

    def test_activate_selected_season(
        self, controller: AppController, mock_main_window: MagicMock
    ) -> None:
        """Test activate_selected drills into season."""
        controller._main_window = mock_main_window
        controller._current_state = AppState.SERIES_DRILLDOWN_SEASONS
        mock_main_window.library_view.get_selected_item.return_value = {
            "id": 1,
            "type": "season",
            "title": "Season 1",
        }

        controller.activate_selected()

        assert controller.current_state == AppState.SERIES_DRILLDOWN_EPISODES

    def test_activate_selected_completed_movie_no_player(
        self, controller: AppController, mock_main_window: MagicMock
    ) -> None:
        """Test activate_selected with completed movie shows error when player not bound."""
        controller._main_window = mock_main_window
        mock_main_window.library_view.get_selected_item.return_value = {
            "id": "movie-1",
            "type": "movie",
            "title": "Test Movie",
            "state": DownloadState.COMPLETED.value,
        }

        controller.activate_selected()

        mock_main_window.show_toast.assert_called_once()
        assert (
            "Player service not available"
            in mock_main_window.show_toast.call_args[0][0]
        )

    def test_activate_selected_pending_movie(
        self, controller: AppController, mock_main_window: MagicMock
    ) -> None:
        """Test activate_selected with pending movie starts download."""
        controller._main_window = mock_main_window
        mock_main_window.library_view.get_selected_item.return_value = {
            "id": "movie-1",
            "type": "movie",
            "title": "Test Movie",
            "state": DownloadState.PENDING.value,
        }

        controller.activate_selected()

        mock_main_window.show_toast.assert_called_once()
        assert "Starting download" in mock_main_window.show_toast.call_args[0][0]

    def test_activate_selected_no_selection(
        self, controller: AppController, mock_main_window: MagicMock
    ) -> None:
        """Test activate_selected with no selection does nothing."""
        controller._main_window = mock_main_window
        mock_main_window.library_view.get_selected_item.return_value = None

        controller.activate_selected()
        # Should not raise or show toast

    def test_activate_selected_without_window(self, controller: AppController) -> None:
        """Test activate_selected without main window does nothing."""
        controller.activate_selected()
        # Should not raise

    def test_navigate_back_to_library_root(
        self, controller: AppController, mock_main_window: MagicMock
    ) -> None:
        """Test navigate_back to library root."""
        controller._main_window = mock_main_window
        controller._current_state = AppState.SERIES_DRILLDOWN_SEASONS

        # Push context for library root
        ctx = NavigationContext(
            state=AppState.LIBRARY_ROOT,
            tab=MediaTab.SERIES,
            selected_item_id="series-1",
        )
        controller._navigation_stack.append(ctx)

        controller.navigate_back()

        assert controller.current_state == AppState.LIBRARY_ROOT
        mock_main_window.library_view.set_tab.assert_called_with(MediaTab.SERIES)

    def test_navigate_back_to_seasons(
        self, controller: AppController, mock_main_window: MagicMock
    ) -> None:
        """Test navigate_back to seasons view."""
        controller._main_window = mock_main_window
        controller._current_state = AppState.SERIES_DRILLDOWN_EPISODES

        # Push context for seasons
        ctx = NavigationContext(
            state=AppState.SERIES_DRILLDOWN_SEASONS,
            tab=MediaTab.SERIES,
            series_id="series-1",
        )
        controller._navigation_stack.append(ctx)

        controller.navigate_back()

        assert controller.current_state == AppState.SERIES_DRILLDOWN_SEASONS

    def test_navigate_back_to_episodes(
        self, controller: AppController, mock_main_window: MagicMock
    ) -> None:
        """Test navigate_back to episodes view."""
        controller._main_window = mock_main_window

        # Push context for episodes
        ctx = NavigationContext(
            state=AppState.SERIES_DRILLDOWN_EPISODES,
            tab=MediaTab.SERIES,
            season_id=1,
        )
        controller._navigation_stack.append(ctx)

        controller.navigate_back()

        assert controller.current_state == AppState.SERIES_DRILLDOWN_EPISODES

    def test_navigate_back_empty_stack(self, controller: AppController) -> None:
        """Test navigate_back with empty stack does nothing."""
        controller.navigate_back()
        # Should not raise

    def test_delete_selected_confirmed(
        self, controller: AppController, mock_main_window: MagicMock
    ) -> None:
        """Test delete_selected with confirmation."""
        controller._main_window = mock_main_window
        mock_main_window.library_view.get_selected_item.return_value = {
            "id": "movie-1",
            "type": "movie",
            "title": "Test Movie",
        }
        mock_main_window.show_confirm.return_value = True

        controller.delete_selected()

        mock_main_window.show_confirm.assert_called_once()
        mock_main_window.show_toast.assert_called()

    def test_delete_selected_cancelled(
        self, controller: AppController, mock_main_window: MagicMock
    ) -> None:
        """Test delete_selected when cancelled."""
        controller._main_window = mock_main_window
        mock_main_window.library_view.get_selected_item.return_value = {
            "id": "movie-1",
            "type": "movie",
            "title": "Test Movie",
        }
        mock_main_window.show_confirm.return_value = False

        controller.delete_selected()

        mock_main_window.show_confirm.assert_called_once()
        mock_main_window.show_toast.assert_not_called()

    def test_delete_selected_no_selection(
        self, controller: AppController, mock_main_window: MagicMock
    ) -> None:
        """Test delete_selected with no selection."""
        controller._main_window = mock_main_window
        mock_main_window.library_view.get_selected_item.return_value = None

        controller.delete_selected()

        mock_main_window.show_confirm.assert_not_called()

    def test_delete_selected_without_window(self, controller: AppController) -> None:
        """Test delete_selected without main window."""
        controller.delete_selected()
        # Should not raise

    def test_show_search(
        self, controller: AppController, mock_main_window: MagicMock
    ) -> None:
        """Test show_search."""
        controller._main_window = mock_main_window
        controller._search_filter = "test"

        controller.show_search()

        assert controller.current_state == AppState.SEARCH_OVERLAY
        mock_main_window.show_search.assert_called_once_with("test")

    def test_show_search_without_window(self, controller: AppController) -> None:
        """Test show_search without main window."""
        controller.show_search()
        # Should not raise

    def test_hide_search(
        self, controller: AppController, mock_main_window: MagicMock
    ) -> None:
        """Test hide_search."""
        controller._main_window = mock_main_window
        controller._current_state = AppState.SEARCH_OVERLAY

        # Push navigation context
        ctx = NavigationContext(state=AppState.LIBRARY_ROOT, tab=MediaTab.MOVIES)
        controller._navigation_stack.append(ctx)

        controller.hide_search()

        mock_main_window.hide_search.assert_called_once()
        assert controller.current_state == AppState.LIBRARY_ROOT

    def test_hide_search_without_window(self, controller: AppController) -> None:
        """Test hide_search without main window."""
        controller.hide_search()
        # Should not raise

    def test_clear_search_filter_no_filter(
        self, controller: AppController, mock_main_window: MagicMock
    ) -> None:
        """Test clear_search_filter when no filter is set."""
        controller._main_window = mock_main_window
        controller._search_filter = None

        controller.clear_search_filter()

        mock_main_window.show_toast.assert_not_called()

    def test_trigger_sync_no_service(
        self, controller: AppController, mock_main_window: MagicMock
    ) -> None:
        """Test trigger_sync without metadata service."""
        controller._main_window = mock_main_window

        controller.trigger_sync()

        mock_main_window.show_toast.assert_called_once()
        assert "not available" in mock_main_window.show_toast.call_args[0][0]

    def test_trigger_sync_already_running(
        self, controller: AppController, mock_main_window: MagicMock
    ) -> None:
        """Test trigger_sync when sync is already running."""
        controller._main_window = mock_main_window
        mock_service = MagicMock()
        mock_service.isRunning.return_value = True
        controller._metadata_service = mock_service

        controller.trigger_sync()

        mock_main_window.show_toast.assert_called_once()
        assert "already in progress" in mock_main_window.show_toast.call_args[0][0]

    def test_trigger_sync_starts_service(self, controller: AppController) -> None:
        """Test trigger_sync starts metadata service."""
        mock_service = MagicMock()
        mock_service.isRunning.return_value = False
        controller._metadata_service = mock_service

        controller.trigger_sync()

        mock_service.start.assert_called_once()

    def test_on_sync_started(
        self, controller: AppController, mock_main_window: MagicMock
    ) -> None:
        """Test _on_sync_started handler."""
        controller._main_window = mock_main_window

        controller._on_sync_started()

        mock_main_window.set_sync_status.assert_called_with("Syncing...")
        mock_main_window.show_toast.assert_called()

    def test_on_sync_completed(
        self, controller: AppController, mock_main_window: MagicMock
    ) -> None:
        """Test _on_sync_completed handler."""
        controller._main_window = mock_main_window
        mock_main_window.library_view.get_current_tab.return_value = MediaTab.MOVIES

        controller._on_sync_completed()

        mock_main_window.set_sync_status.assert_called()
        mock_main_window.show_toast.assert_called()

    def test_on_sync_error(
        self, controller: AppController, mock_main_window: MagicMock
    ) -> None:
        """Test _on_sync_error handler."""
        controller._main_window = mock_main_window

        controller._on_sync_error("Network error")

        mock_main_window.set_sync_status.assert_called_with("Sync failed")
        assert "Network error" in mock_main_window.show_toast.call_args[0][0]

    def test_on_download_progress(
        self, controller: AppController, mock_main_window: MagicMock
    ) -> None:
        """Test _on_download_progress handler."""
        controller._main_window = mock_main_window

        controller._on_download_progress(1, 50, 1500.0, 100.0)

        mock_main_window.library_view.update_item.assert_called_once()
        call_args = mock_main_window.library_view.update_item.call_args
        assert call_args[0][0] == "1"
        assert call_args[0][1]["download_progress"] == 50

    def test_on_download_completed(
        self, controller: AppController, mock_main_window: MagicMock
    ) -> None:
        """Test _on_download_completed handler."""
        controller._main_window = mock_main_window

        controller._on_download_completed(1, "/path/to/file.mp4")

        mock_main_window.library_view.update_item.assert_called_once()
        mock_main_window.show_toast.assert_called()

    def test_on_download_error(
        self, controller: AppController, mock_main_window: MagicMock
    ) -> None:
        """Test _on_download_error handler."""
        controller._main_window = mock_main_window

        controller._on_download_error(1, "Connection failed")

        mock_main_window.library_view.update_item.assert_called_once()
        assert "Connection failed" in mock_main_window.show_toast.call_args[0][0]

    def test_on_item_activated(self, controller: AppController) -> None:
        """Test on_item_activated callback."""
        # This is a pass-through, should not raise
        controller.on_item_activated({"id": "test"})

    def test_on_selection_changed(self, controller: AppController) -> None:
        """Test on_selection_changed callback."""
        # This is a pass-through, should not raise
        controller.on_selection_changed({"id": "test"})

    def test_on_tab_changed(
        self, controller: AppController, mock_main_window: MagicMock
    ) -> None:
        """Test on_tab_changed callback."""
        controller._main_window = mock_main_window
        mock_main_window.library_view.get_current_tab.return_value = MediaTab.SERIES

        controller.on_tab_changed(MediaTab.SERIES)

        assert controller._current_tab == MediaTab.SERIES

    def test_on_search_committed(
        self, controller: AppController, mock_main_window: MagicMock
    ) -> None:
        """Test on_search_committed callback."""
        controller._main_window = mock_main_window
        controller._current_state = AppState.SEARCH_OVERLAY
        ctx = NavigationContext(state=AppState.LIBRARY_ROOT, tab=MediaTab.MOVIES)
        controller._navigation_stack.append(ctx)

        controller.on_search_committed("test query")

        assert controller.search_filter == "test query"

    def test_on_search_cancelled(
        self, controller: AppController, mock_main_window: MagicMock
    ) -> None:
        """Test on_search_cancelled callback."""
        controller._main_window = mock_main_window
        controller._current_state = AppState.SEARCH_OVERLAY
        controller._search_filter = "test"
        ctx = NavigationContext(state=AppState.LIBRARY_ROOT, tab=MediaTab.MOVIES)
        controller._navigation_stack.append(ctx)

        controller.on_search_cancelled()

        assert controller.search_filter is None

    def test_quit_application(
        self, controller: AppController, mock_main_window: MagicMock
    ) -> None:
        """Test quit_application."""
        controller._main_window = mock_main_window

        controller.quit_application()

        mock_main_window.close.assert_called_once()

    def test_shutdown_with_running_services(self, controller: AppController) -> None:
        """Test shutdown stops running services."""
        mock_metadata = MagicMock()
        mock_metadata.isRunning.return_value = True
        mock_torrent = MagicMock()
        mock_torrent.is_running = True

        controller._metadata_service = mock_metadata
        controller._torrent_service = mock_torrent

        controller.shutdown()

        mock_metadata.stop.assert_called_once()
        mock_metadata.wait.assert_called_once()
        mock_torrent.stop.assert_called_once()

    def test_push_navigation_no_window(self, controller: AppController) -> None:
        """Test push_navigation with no main window."""
        controller._main_window = None
        controller.push_navigation()
        assert len(controller._navigation_stack) == 1
        assert controller._navigation_stack[0].selected_item_id is None


class TestSeriesDrilldownSeasonsHandlerFull:
    """Full tests for SeriesDrilldownSeasonsHandler."""

    @pytest.fixture
    def controller(self) -> MagicMock:
        """Create a mock controller."""
        return MagicMock()

    @pytest.fixture
    def handler(self, controller: MagicMock) -> SeriesDrilldownSeasonsHandler:
        """Create handler instance."""
        return SeriesDrilldownSeasonsHandler(controller)

    def test_navigate_up(
        self, handler: SeriesDrilldownSeasonsHandler, controller: MagicMock
    ) -> None:
        """Test navigate up."""
        result = handler.handle_action(Action.NAVIGATE_UP, {})
        assert result is True
        controller.main_window.library_view.select_prev.assert_called_once()

    def test_navigate_down(
        self, handler: SeriesDrilldownSeasonsHandler, controller: MagicMock
    ) -> None:
        """Test navigate down."""
        result = handler.handle_action(Action.NAVIGATE_DOWN, {})
        assert result is True
        controller.main_window.library_view.select_next.assert_called_once()

    def test_confirm(
        self, handler: SeriesDrilldownSeasonsHandler, controller: MagicMock
    ) -> None:
        """Test confirm action."""
        result = handler.handle_action(Action.CONFIRM, {})
        assert result is True
        controller.activate_selected.assert_called_once()

    def test_quit(
        self, handler: SeriesDrilldownSeasonsHandler, controller: MagicMock
    ) -> None:
        """Test quit action."""
        result = handler.handle_action(Action.QUIT, {})
        assert result is True
        controller.quit_application.assert_called_once()

    def test_unhandled(self, handler: SeriesDrilldownSeasonsHandler) -> None:
        """Test unhandled action."""
        result = handler.handle_action(Action.SEARCH, {})
        assert result is False


class TestSeriesDrilldownEpisodesHandlerFull:
    """Full tests for SeriesDrilldownEpisodesHandler."""

    @pytest.fixture
    def controller(self) -> MagicMock:
        """Create a mock controller."""
        return MagicMock()

    @pytest.fixture
    def handler(self, controller: MagicMock) -> SeriesDrilldownEpisodesHandler:
        """Create handler instance."""
        return SeriesDrilldownEpisodesHandler(controller)

    def test_navigate_up(
        self, handler: SeriesDrilldownEpisodesHandler, controller: MagicMock
    ) -> None:
        """Test navigate up."""
        result = handler.handle_action(Action.NAVIGATE_UP, {})
        assert result is True
        controller.main_window.library_view.select_prev.assert_called_once()

    def test_navigate_down(
        self, handler: SeriesDrilldownEpisodesHandler, controller: MagicMock
    ) -> None:
        """Test navigate down."""
        result = handler.handle_action(Action.NAVIGATE_DOWN, {})
        assert result is True
        controller.main_window.library_view.select_next.assert_called_once()

    def test_confirm(
        self, handler: SeriesDrilldownEpisodesHandler, controller: MagicMock
    ) -> None:
        """Test confirm action."""
        result = handler.handle_action(Action.CONFIRM, {})
        assert result is True
        controller.activate_selected.assert_called_once()

    def test_cancel(
        self, handler: SeriesDrilldownEpisodesHandler, controller: MagicMock
    ) -> None:
        """Test cancel action."""
        result = handler.handle_action(Action.CANCEL, {})
        assert result is True
        controller.navigate_back.assert_called_once()

    def test_quit(
        self, handler: SeriesDrilldownEpisodesHandler, controller: MagicMock
    ) -> None:
        """Test quit action."""
        result = handler.handle_action(Action.QUIT, {})
        assert result is True
        controller.quit_application.assert_called_once()

    def test_unhandled(self, handler: SeriesDrilldownEpisodesHandler) -> None:
        """Test unhandled action."""
        result = handler.handle_action(Action.SEARCH, {})
        assert result is False


class TestAppControllerPlayerMethods:
    """Tests for AppController player-related methods."""

    @pytest.fixture
    def db_manager(self) -> DatabaseManager:
        """Create a test database manager."""
        manager = DatabaseManager(":memory:")
        manager.initialize()
        return manager

    @pytest.fixture
    def controller(self, db_manager: DatabaseManager) -> AppController:
        """Create an AppController instance."""
        return AppController(db_manager)

    @pytest.fixture
    def mock_main_window(self) -> MagicMock:
        """Create a mock main window."""
        window = MagicMock()
        window.library_view.get_current_tab.return_value = MediaTab.MOVIES
        window.library_view.get_selected_item.return_value = None
        window.player_view = MagicMock()
        window.get_player_frame_id.return_value = 12345
        return window

    @pytest.fixture
    def mock_player_service(self) -> MagicMock:
        """Create a mock player service."""
        service = MagicMock()
        service.is_playing.return_value = True
        service.get_position_seconds.return_value = 120
        service.get_current_audio_track.return_value = {"name": "English"}
        return service

    # =========================================================================
    # play_media() tests
    # =========================================================================

    def test_play_media_no_main_window(self, controller: AppController) -> None:
        """Test play_media returns early without main window."""
        controller.play_media(1)
        # Should not raise

    def test_play_media_no_player_service(
        self, controller: AppController, mock_main_window: MagicMock
    ) -> None:
        """Test play_media shows error without player service."""
        controller._main_window = mock_main_window
        controller.play_media(1)
        mock_main_window.show_toast.assert_called_with(
            "Player service not available", "error"
        )

    def test_play_media_invalid_media_id_not_found(
        self,
        controller: AppController,
        mock_main_window: MagicMock,
        mock_player_service: MagicMock,
    ) -> None:
        """Test play_media with invalid media ID that's not found."""
        controller._main_window = mock_main_window
        controller._player_service = mock_player_service
        controller.play_media("nonexistent-uuid")
        mock_main_window.show_toast.assert_called_with("Video file not found", "error")

    def test_play_media_video_file_not_found(
        self,
        controller: AppController,
        mock_main_window: MagicMock,
        mock_player_service: MagicMock,
        db_manager: DatabaseManager,
    ) -> None:
        """Test play_media with video file ID not in database."""
        controller._main_window = mock_main_window
        controller._player_service = mock_player_service
        controller.play_media(99999)
        mock_main_window.show_toast.assert_called_with("Video file not found", "error")

    def test_play_media_video_no_file_path(
        self,
        controller: AppController,
        mock_main_window: MagicMock,
        mock_player_service: MagicMock,
        db_manager: DatabaseManager,
    ) -> None:
        """Test play_media when video file has no file_path."""
        # Insert media and video file without file_path
        db_manager.upsert_content(
            {
                "items": [
                    {
                        "id": "test-movie",
                        "type": "movie",
                        "title": "Test Movie",
                        "magnet": "magnet:?test",
                        "subtitle_id": None,
                    }
                ]
            }
        )
        # Get video and verify it has no file_path
        video = db_manager.get_video_details("test-movie")
        controller._main_window = mock_main_window
        controller._player_service = mock_player_service
        controller.play_media(video["id"])
        mock_main_window.show_toast.assert_called_with(
            "Video file path not set", "error"
        )

    def test_play_media_success_without_voiceover(
        self,
        controller: AppController,
        mock_main_window: MagicMock,
        mock_player_service: MagicMock,
        db_manager: DatabaseManager,
    ) -> None:
        """Test successful play_media without voiceover."""
        # Insert media and video file
        db_manager.upsert_content(
            {
                "items": [
                    {
                        "id": "test-movie",
                        "type": "movie",
                        "title": "Test Movie",
                        "magnet": "magnet:?test",
                        "subtitle_id": None,
                    }
                ]
            }
        )
        video = db_manager.get_video_details("test-movie")
        db_manager.update_file_path(video["id"], "/path/to/video.mp4")

        controller._main_window = mock_main_window
        controller._player_service = mock_player_service
        controller.play_media(video["id"])

        mock_main_window.show_player.assert_called_once()
        mock_player_service.initialize.assert_called_once_with(12345)
        mock_player_service.load_video.assert_called_once_with(
            "/path/to/video.mp4", None
        )

    def test_play_media_with_resume_position(
        self,
        controller: AppController,
        mock_main_window: MagicMock,
        mock_player_service: MagicMock,
        db_manager: DatabaseManager,
    ) -> None:
        """Test play_media resumes from saved position."""
        # Insert media and video file with resume position
        db_manager.upsert_content(
            {
                "items": [
                    {
                        "id": "test-movie",
                        "type": "movie",
                        "title": "Test Movie",
                        "magnet": "magnet:?test",
                        "subtitle_id": None,
                    }
                ]
            }
        )
        video = db_manager.get_video_details("test-movie")
        db_manager.update_file_path(video["id"], "/path/to/video.mp4")
        db_manager.update_resume_position(video["id"], 300)

        controller._main_window = mock_main_window
        controller._player_service = mock_player_service
        controller.play_media(video["id"])

        mock_player_service.set_position_seconds.assert_called_once_with(300)

    def test_play_media_with_subtitles(
        self,
        controller: AppController,
        mock_main_window: MagicMock,
        mock_player_service: MagicMock,
        db_manager: DatabaseManager,
    ) -> None:
        """Test play_media loads subtitles (Polish priority)."""
        # Insert media and video file
        db_manager.upsert_content(
            {
                "items": [
                    {
                        "id": "test-movie",
                        "type": "movie",
                        "title": "Test Movie",
                        "magnet": "magnet:?test",
                        "subtitle_id": None,
                    }
                ]
            }
        )
        video = db_manager.get_video_details("test-movie")
        db_manager.update_file_path(video["id"], "/path/to/video.mp4")
        # Add Polish and English subtitles
        db_manager.add_subtitle(video["id"], "en", "/path/to/en.srt")
        db_manager.add_subtitle(video["id"], "pl", "/path/to/pl.srt")

        controller._main_window = mock_main_window
        controller._player_service = mock_player_service
        controller.play_media(video["id"])

        # Should load Polish subtitle (priority over English)
        mock_player_service.load_subtitle.assert_called_once_with("/path/to/pl.srt")

    def test_play_media_with_english_subtitle(
        self,
        controller: AppController,
        mock_main_window: MagicMock,
        mock_player_service: MagicMock,
        db_manager: DatabaseManager,
    ) -> None:
        """Test play_media loads English subtitle when Polish not available."""
        # Insert media and video file
        db_manager.upsert_content(
            {
                "items": [
                    {
                        "id": "test-movie",
                        "type": "movie",
                        "title": "Test Movie",
                        "magnet": "magnet:?test",
                        "subtitle_id": None,
                    }
                ]
            }
        )
        video = db_manager.get_video_details("test-movie")
        db_manager.update_file_path(video["id"], "/path/to/video.mp4")
        # Add only English subtitle
        db_manager.add_subtitle(video["id"], "en", "/path/to/en.srt")

        controller._main_window = mock_main_window
        controller._player_service = mock_player_service
        controller.play_media(video["id"])

        # Should load English subtitle
        mock_player_service.load_subtitle.assert_called_once_with("/path/to/en.srt")

    def test_play_media_without_subtitles(
        self,
        controller: AppController,
        mock_main_window: MagicMock,
        mock_player_service: MagicMock,
        db_manager: DatabaseManager,
    ) -> None:
        """Test play_media works without subtitles."""
        # Insert media and video file
        db_manager.upsert_content(
            {
                "items": [
                    {
                        "id": "test-movie",
                        "type": "movie",
                        "title": "Test Movie",
                        "magnet": "magnet:?test",
                        "subtitle_id": None,
                    }
                ]
            }
        )
        video = db_manager.get_video_details("test-movie")
        db_manager.update_file_path(video["id"], "/path/to/video.mp4")

        controller._main_window = mock_main_window
        controller._player_service = mock_player_service
        controller.play_media(video["id"])

        # Should not call load_subtitle
        mock_player_service.load_subtitle.assert_not_called()

    def test_play_media_file_not_found_error(
        self,
        controller: AppController,
        mock_main_window: MagicMock,
        mock_player_service: MagicMock,
        db_manager: DatabaseManager,
    ) -> None:
        """Test play_media handles FileNotFoundError."""
        db_manager.upsert_content(
            {
                "items": [
                    {
                        "id": "test-movie",
                        "type": "movie",
                        "title": "Test Movie",
                        "magnet": "magnet:?test",
                        "subtitle_id": None,
                    }
                ]
            }
        )
        video = db_manager.get_video_details("test-movie")
        db_manager.update_file_path(video["id"], "/path/to/video.mp4")
        mock_player_service.load_video.side_effect = FileNotFoundError("File missing")

        controller._main_window = mock_main_window
        controller._player_service = mock_player_service
        controller.play_media(video["id"])

        assert "File not found" in mock_main_window.show_toast.call_args[0][0]

    def test_play_media_generic_exception(
        self,
        controller: AppController,
        mock_main_window: MagicMock,
        mock_player_service: MagicMock,
        db_manager: DatabaseManager,
    ) -> None:
        """Test play_media handles generic exception."""
        db_manager.upsert_content(
            {
                "items": [
                    {
                        "id": "test-movie",
                        "type": "movie",
                        "title": "Test Movie",
                        "magnet": "magnet:?test",
                        "subtitle_id": None,
                    }
                ]
            }
        )
        video = db_manager.get_video_details("test-movie")
        db_manager.update_file_path(video["id"], "/path/to/video.mp4")
        mock_player_service.load_video.side_effect = Exception("VLC error")

        controller._main_window = mock_main_window
        controller._player_service = mock_player_service
        controller.play_media(video["id"])

        assert "Playback error" in mock_main_window.show_toast.call_args[0][0]

    # =========================================================================
    # stop_player() tests
    # =========================================================================

    def test_stop_player_no_main_window(self, controller: AppController) -> None:
        """Test stop_player returns early without main window."""
        controller.stop_player()
        # Should not raise

    def test_stop_player_success(
        self,
        controller: AppController,
        mock_main_window: MagicMock,
        mock_player_service: MagicMock,
    ) -> None:
        """Test stop_player stops playback and hides player."""
        controller._main_window = mock_main_window
        controller._player_service = mock_player_service
        controller._current_playing_file_id = 1
        controller.transition_to(AppState.PLAYER_ACTIVE)

        # Push initial context
        controller.push_navigation()

        controller.stop_player()

        mock_player_service.stop.assert_called_once()
        mock_main_window.hide_player.assert_called_once()
        assert controller._current_playing_file_id is None

    # =========================================================================
    # _save_resume_position() tests
    # =========================================================================

    def test_save_resume_position_no_player_service(
        self, controller: AppController
    ) -> None:
        """Test _save_resume_position returns early without player service."""
        controller._save_resume_position()
        # Should not raise

    def test_save_resume_position_no_file_id(
        self,
        controller: AppController,
        mock_player_service: MagicMock,
    ) -> None:
        """Test _save_resume_position returns early without file ID."""
        controller._player_service = mock_player_service
        controller._current_playing_file_id = None
        controller._save_resume_position()
        mock_player_service.get_position_seconds.assert_not_called()

    def test_save_resume_position_success(
        self,
        controller: AppController,
        mock_player_service: MagicMock,
        db_manager: DatabaseManager,
    ) -> None:
        """Test _save_resume_position saves position to database."""
        db_manager.upsert_content(
            {
                "items": [
                    {
                        "id": "test-movie",
                        "type": "movie",
                        "title": "Test Movie",
                        "magnet": "magnet:?test",
                        "subtitle_id": None,
                    }
                ]
            }
        )
        video = db_manager.get_video_details("test-movie")
        db_manager.update_file_path(video["id"], "/path/to/video.mp4")

        controller._player_service = mock_player_service
        controller._current_playing_file_id = video["id"]
        mock_player_service.get_position_seconds.return_value = 150

        controller._save_resume_position()

        video = db_manager.get_video_file(video["id"])
        assert video["resume_position_seconds"] == 150

    def test_save_resume_position_zero_position(
        self,
        controller: AppController,
        mock_player_service: MagicMock,
        db_manager: DatabaseManager,
    ) -> None:
        """Test _save_resume_position does not save zero position."""
        controller._player_service = mock_player_service
        controller._current_playing_file_id = 1
        mock_player_service.get_position_seconds.return_value = 0

        controller._save_resume_position()
        # Should not save anything

    def test_save_resume_position_db_error(
        self,
        controller: AppController,
        mock_player_service: MagicMock,
    ) -> None:
        """Test _save_resume_position handles database error."""
        controller._player_service = mock_player_service
        controller._current_playing_file_id = 99999
        mock_player_service.get_position_seconds.return_value = 100
        # Database error will occur since video file doesn't exist
        # Should not raise
        controller._save_resume_position()

    # =========================================================================
    # Player control methods tests
    # =========================================================================

    def test_player_toggle_pause_no_services(self, controller: AppController) -> None:
        """Test player_toggle_pause returns early without services."""
        controller.player_toggle_pause()
        # Should not raise

    def test_player_toggle_pause_success(
        self,
        controller: AppController,
        mock_main_window: MagicMock,
        mock_player_service: MagicMock,
    ) -> None:
        """Test player_toggle_pause toggles pause and shows indicator."""
        controller._main_window = mock_main_window
        controller._player_service = mock_player_service
        mock_player_service.is_playing.return_value = False  # After toggle, paused

        controller.player_toggle_pause()

        mock_player_service.toggle_pause.assert_called_once()
        mock_main_window.player_view.show_pause_indicator.assert_called_once_with(True)

    def test_player_seek_forward_no_services(self, controller: AppController) -> None:
        """Test player_seek_forward returns early without services."""
        controller.player_seek_forward()
        # Should not raise

    def test_player_seek_forward_success(
        self,
        controller: AppController,
        mock_main_window: MagicMock,
        mock_player_service: MagicMock,
    ) -> None:
        """Test player_seek_forward seeks and shows indicator."""
        controller._main_window = mock_main_window
        controller._player_service = mock_player_service

        controller.player_seek_forward()

        mock_player_service.seek_forward.assert_called_once()
        mock_main_window.player_view.show_seek_indicator.assert_called_once_with(
            forward=True
        )

    def test_player_seek_backward_no_services(self, controller: AppController) -> None:
        """Test player_seek_backward returns early without services."""
        controller.player_seek_backward()
        # Should not raise

    def test_player_seek_backward_success(
        self,
        controller: AppController,
        mock_main_window: MagicMock,
        mock_player_service: MagicMock,
    ) -> None:
        """Test player_seek_backward seeks and shows indicator."""
        controller._main_window = mock_main_window
        controller._player_service = mock_player_service

        controller.player_seek_backward()

        mock_player_service.seek_backward.assert_called_once()
        mock_main_window.player_view.show_seek_indicator.assert_called_once_with(
            forward=False
        )

    def test_player_volume_up_no_services(self, controller: AppController) -> None:
        """Test player_volume_up returns early without services."""
        controller.player_volume_up()
        # Should not raise

    def test_player_volume_up_success(
        self,
        controller: AppController,
        mock_main_window: MagicMock,
        mock_player_service: MagicMock,
    ) -> None:
        """Test player_volume_up changes volume and shows indicator."""
        controller._main_window = mock_main_window
        controller._player_service = mock_player_service
        mock_player_service.volume_up.return_value = 75

        controller.player_volume_up()

        mock_player_service.volume_up.assert_called_once()
        mock_main_window.player_view.show_volume_indicator.assert_called_once_with(
            75, is_muted=False
        )

    def test_player_volume_down_no_services(self, controller: AppController) -> None:
        """Test player_volume_down returns early without services."""
        controller.player_volume_down()
        # Should not raise

    def test_player_volume_down_success(
        self,
        controller: AppController,
        mock_main_window: MagicMock,
        mock_player_service: MagicMock,
    ) -> None:
        """Test player_volume_down changes volume and shows indicator."""
        controller._main_window = mock_main_window
        controller._player_service = mock_player_service
        mock_player_service.volume_down.return_value = 45

        controller.player_volume_down()

        mock_player_service.volume_down.assert_called_once()
        mock_main_window.player_view.show_volume_indicator.assert_called_once_with(
            45, is_muted=False
        )

    def test_player_toggle_mute_no_services(self, controller: AppController) -> None:
        """Test player_toggle_mute returns early without services."""
        controller.player_toggle_mute()
        # Should not raise

    def test_player_toggle_mute_success(
        self,
        controller: AppController,
        mock_main_window: MagicMock,
        mock_player_service: MagicMock,
    ) -> None:
        """Test player_toggle_mute toggles mute and shows indicator."""
        controller._main_window = mock_main_window
        controller._player_service = mock_player_service
        mock_player_service.toggle_mute.return_value = (0, True)

        controller.player_toggle_mute()

        mock_player_service.toggle_mute.assert_called_once()
        mock_main_window.player_view.show_volume_indicator.assert_called_once_with(
            0, is_muted=True
        )

    def test_player_cycle_audio_no_services(self, controller: AppController) -> None:
        """Test player_cycle_audio returns early without services."""
        controller.player_cycle_audio()
        # Should not raise

    def test_player_cycle_audio_success(
        self,
        controller: AppController,
        mock_main_window: MagicMock,
        mock_player_service: MagicMock,
    ) -> None:
        """Test player_cycle_audio cycles track and shows indicator."""
        controller._main_window = mock_main_window
        controller._player_service = mock_player_service

        controller.player_cycle_audio()

        mock_player_service.cycle_audio_track.assert_called_once()
        mock_main_window.player_view.show_audio_track_indicator.assert_called_once_with(
            "English"
        )

    def test_player_cycle_audio_no_track(
        self,
        controller: AppController,
        mock_main_window: MagicMock,
        mock_player_service: MagicMock,
    ) -> None:
        """Test player_cycle_audio when no track info available."""
        controller._main_window = mock_main_window
        controller._player_service = mock_player_service
        mock_player_service.get_current_audio_track.return_value = None

        controller.player_cycle_audio()

        mock_player_service.cycle_audio_track.assert_called_once()
        mock_main_window.player_view.show_audio_track_indicator.assert_not_called()

    # =========================================================================
    # Player event handler tests
    # =========================================================================

    def test_on_playback_finished(
        self,
        controller: AppController,
        mock_main_window: MagicMock,
        mock_player_service: MagicMock,
        db_manager: DatabaseManager,
    ) -> None:
        """Test _on_playback_finished clears resume and stops player."""
        db_manager.upsert_content(
            {
                "items": [
                    {
                        "id": "test-movie",
                        "type": "movie",
                        "title": "Test Movie",
                        "magnet": "magnet:?test",
                        "subtitle_id": None,
                    }
                ]
            }
        )
        video = db_manager.get_video_details("test-movie")
        db_manager.update_file_path(video["id"], "/path/to/video.mp4")
        db_manager.update_resume_position(video["id"], 300)

        controller._main_window = mock_main_window
        controller._player_service = mock_player_service
        controller._current_playing_file_id = video["id"]
        # Return 0 from get_position_seconds so stop_player doesn't overwrite the clear
        mock_player_service.get_position_seconds.return_value = 0

        controller._on_playback_finished()

        # Resume position should be cleared (set to 0 by _on_playback_finished)
        video = db_manager.get_video_file(video["id"])
        assert video["resume_position_seconds"] == 0

    def test_on_playback_finished_db_error(
        self,
        controller: AppController,
        mock_main_window: MagicMock,
        mock_player_service: MagicMock,
    ) -> None:
        """Test _on_playback_finished handles database error."""
        controller._main_window = mock_main_window
        controller._player_service = mock_player_service
        controller._current_playing_file_id = 99999  # Non-existent

        # Should not raise
        controller._on_playback_finished()

    def test_on_time_changed(self, controller: AppController) -> None:
        """Test _on_time_changed does nothing (placeholder)."""
        # Should not raise
        controller._on_time_changed(5000, 120000)

    def test_on_player_error(
        self,
        controller: AppController,
        mock_main_window: MagicMock,
        mock_player_service: MagicMock,
    ) -> None:
        """Test _on_player_error shows toast and stops player."""
        controller._main_window = mock_main_window
        controller._player_service = mock_player_service

        controller._on_player_error("VLC crashed")

        mock_main_window.show_toast.assert_called_once()
        assert "VLC crashed" in mock_main_window.show_toast.call_args[0][0]

    def test_on_player_error_no_main_window(self, controller: AppController) -> None:
        """Test _on_player_error without main window."""
        controller._on_player_error("error")
        # Should not raise
