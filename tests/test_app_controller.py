"""Tests for AppController."""

import pytest
from unittest.mock import MagicMock, patch

from src.controllers.app_controller import (
    AppController,
    DialogConfirmHandler,
    LibraryRootHandler,
    NavigationContext,
    PlayerActiveHandler,
    SearchOverlayHandler,
    SeriesDrilldownEpisodesHandler,
    SeriesDrilldownSeasonsHandler,
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

    def test_navigate_up(self, handler: LibraryRootHandler, controller: MagicMock) -> None:
        """Test navigate up action."""
        result = handler.handle_action(Action.NAVIGATE_UP, {})
        assert result is True
        controller.main_window.library_view.select_prev.assert_called_once()

    def test_navigate_down(self, handler: LibraryRootHandler, controller: MagicMock) -> None:
        """Test navigate down action."""
        result = handler.handle_action(Action.NAVIGATE_DOWN, {})
        assert result is True
        controller.main_window.library_view.select_next.assert_called_once()

    def test_switch_tab(self, handler: LibraryRootHandler, controller: MagicMock) -> None:
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

    def test_clear_filter(self, handler: LibraryRootHandler, controller: MagicMock) -> None:
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

    def test_cancel_navigates_back(
        self, handler: PlayerActiveHandler, controller: MagicMock
    ) -> None:
        """Test cancel action navigates back from player."""
        result = handler.handle_action(Action.CANCEL, {})
        assert result is True
        controller.navigate_back.assert_called_once()

    def test_quit_available(
        self, handler: PlayerActiveHandler, controller: MagicMock
    ) -> None:
        """Test quit action is available in player."""
        result = handler.handle_action(Action.QUIT, {})
        assert result is True
        controller.quit_application.assert_called_once()
