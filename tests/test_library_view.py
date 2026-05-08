"""Tests for LibraryView component."""

import pytest
from PySide6.QtGui import QPixmap

from src.config import DownloadState
from src.ui.components.library_item_delegate import LibraryItemRole
from src.ui.components.library_view import LibraryView
from src.ui.enums import MediaTab


class TestLibraryView:
    """Tests for LibraryView class."""

    @pytest.fixture
    def library_view(self, qtbot) -> LibraryView:
        """Create a LibraryView instance."""
        view = LibraryView()
        qtbot.addWidget(view)
        return view

    @pytest.fixture
    def sample_items(self) -> list[dict]:
        """Create sample items for testing."""
        return [
            {
                "id": "movie-1",
                "type": "movie",
                "title": "Test Movie 1",
                "genres": "Action, Adventure",
                "poster_path": "",
                "state": DownloadState.PENDING.value,
            },
            {
                "id": "movie-2",
                "type": "movie",
                "title": "Test Movie 2",
                "genres": "Comedy",
                "poster_path": "",
                "state": DownloadState.COMPLETED.value,
            },
            {
                "id": "series-1",
                "type": "series",
                "title": "Test Series",
                "genres": "Drama",
                "poster_path": "",
                "season_count": 3,
            },
        ]

    def test_initialization(self, library_view: LibraryView) -> None:
        """Test LibraryView initialization."""
        assert library_view is not None
        assert library_view.objectName() == "LibraryView"

    def test_default_tab_is_movies(self, library_view: LibraryView) -> None:
        """Test that default tab is Movies."""
        assert library_view.get_current_tab() == MediaTab.MOVIES

    def test_switch_tab(self, library_view: LibraryView, qtbot) -> None:
        """Test switching tabs."""
        with qtbot.waitSignal(library_view.tab_changed, timeout=100) as blocker:
            library_view.switch_tab()

        assert library_view.get_current_tab() == MediaTab.SERIES
        assert blocker.args == [MediaTab.SERIES]

    def test_switch_tab_toggles(self, library_view: LibraryView) -> None:
        """Test that switch_tab toggles between Movies and Series."""
        assert library_view.get_current_tab() == MediaTab.MOVIES
        library_view.switch_tab()
        assert library_view.get_current_tab() == MediaTab.SERIES
        library_view.switch_tab()
        assert library_view.get_current_tab() == MediaTab.MOVIES

    def test_set_tab(self, library_view: LibraryView, qtbot) -> None:
        """Test setting tab directly."""
        with qtbot.waitSignal(library_view.tab_changed, timeout=100):
            library_view.set_tab(MediaTab.SERIES)

        assert library_view.get_current_tab() == MediaTab.SERIES

    def test_set_items(
        self, library_view: LibraryView, sample_items: list[dict]
    ) -> None:
        """Test setting items in the view."""
        library_view.set_items(sample_items)
        assert len(library_view.get_items()) == 3

    def test_set_items_formats_status_text(
        self, library_view: LibraryView, sample_items: list[dict]
    ) -> None:
        """Test built-in delegate display text includes status."""
        library_view.set_items(sample_items)

        item = library_view._model.item(0)

        assert item.text().startswith("[Download] Test Movie 1")

    def test_set_items_uses_poster_icon(
        self, library_view: LibraryView, sample_items: list[dict], tmp_path
    ) -> None:
        """Test cached poster paths are exposed as standard item icons."""
        poster_path = tmp_path / "poster.png"
        pixmap = QPixmap(2, 2)
        assert pixmap.save(str(poster_path))
        sample_items[0]["poster_path"] = str(poster_path)

        library_view.set_items(sample_items)

        item = library_view._model.item(0)
        assert not item.icon().isNull()

    def test_get_selected_item_none_when_empty(self, library_view: LibraryView) -> None:
        """Test get_selected_item returns None when list is empty."""
        assert library_view.get_selected_item() is None

    def test_get_selected_item(
        self, library_view: LibraryView, sample_items: list[dict]
    ) -> None:
        """Test get_selected_item returns first item after setting items."""
        library_view.set_items(sample_items)
        selected = library_view.get_selected_item()
        assert selected is not None
        assert selected["id"] == "movie-1"

    def test_select_next(
        self, library_view: LibraryView, sample_items: list[dict]
    ) -> None:
        """Test select_next moves to next item."""
        library_view.set_items(sample_items)
        library_view.select_next()
        selected = library_view.get_selected_item()
        assert selected["id"] == "movie-2"

    def test_select_next_at_end(
        self, library_view: LibraryView, sample_items: list[dict]
    ) -> None:
        """Test select_next returns False at end of list."""
        library_view.set_items(sample_items)
        # Go to last item
        library_view.select_next()
        library_view.select_next()
        # Try to go past end
        result = library_view.select_next()
        assert result is False

    def test_select_prev(
        self, library_view: LibraryView, sample_items: list[dict]
    ) -> None:
        """Test select_prev moves to previous item."""
        library_view.set_items(sample_items)
        library_view.select_next()  # Move to second
        library_view.select_prev()  # Back to first
        selected = library_view.get_selected_item()
        assert selected["id"] == "movie-1"

    def test_select_prev_at_start(
        self, library_view: LibraryView, sample_items: list[dict]
    ) -> None:
        """Test select_prev returns False at start of list."""
        library_view.set_items(sample_items)
        result = library_view.select_prev()
        assert result is False

    def test_select_by_id(
        self, library_view: LibraryView, sample_items: list[dict]
    ) -> None:
        """Test select_by_id selects correct item."""
        library_view.set_items(sample_items)
        result = library_view.select_by_id("series-1")
        assert result is True
        selected = library_view.get_selected_item()
        assert selected["id"] == "series-1"

    def test_select_by_id_not_found(
        self, library_view: LibraryView, sample_items: list[dict]
    ) -> None:
        """Test select_by_id returns False when item not found."""
        library_view.set_items(sample_items)
        result = library_view.select_by_id("nonexistent")
        assert result is False

    def test_get_selected_index(
        self, library_view: LibraryView, sample_items: list[dict]
    ) -> None:
        """Test get_selected_index returns correct index."""
        library_view.set_items(sample_items)
        assert library_view.get_selected_index() == 0
        library_view.select_next()
        assert library_view.get_selected_index() == 1

    def test_get_selected_index_empty(self, library_view: LibraryView) -> None:
        """Test get_selected_index returns -1 when empty."""
        assert library_view.get_selected_index() == -1

    def test_item_activated_signal(
        self, library_view: LibraryView, sample_items: list[dict], qtbot
    ) -> None:
        """Test item_activated signal is emitted."""
        library_view.set_items(sample_items)

        with qtbot.waitSignal(library_view.item_activated, timeout=100) as blocker:
            library_view.activate_selected()

        assert blocker.args[0]["id"] == "movie-1"

    def test_selection_changed_signal(
        self, library_view: LibraryView, sample_items: list[dict], qtbot
    ) -> None:
        """Test selection_changed signal is emitted when selection changes."""
        library_view.set_items(sample_items)

        with qtbot.waitSignal(library_view.selection_changed, timeout=100) as blocker:
            library_view.select_next()

        assert blocker.args[0]["id"] == "movie-2"

    def test_clear(self, library_view: LibraryView, sample_items: list[dict]) -> None:
        """Test clearing the view."""
        library_view.set_items(sample_items)
        library_view.clear()
        assert len(library_view.get_items()) == 0

    def test_update_item(
        self, library_view: LibraryView, sample_items: list[dict]
    ) -> None:
        """Test updating an item's data."""
        library_view.set_items(sample_items)
        library_view.update_item(
            "movie-1",
            {
                "state": DownloadState.DOWNLOADING.value,
                "download_progress": 50,
            },
        )
        # The update should not raise an exception
        # Visual verification would require rendering
        item = library_view._model.item(0)
        assert item.data(LibraryItemRole.DownloadProgressRole) == 50
        assert item.text().startswith("[Downloading 50%]")

    def test_refresh(self, library_view: LibraryView, sample_items: list[dict]) -> None:
        """Test refresh triggers viewport update."""
        library_view.set_items(sample_items)
        library_view.refresh()  # Should not raise

    def test_set_focus(self, library_view: LibraryView) -> None:
        """Test set_focus focuses the list view."""
        library_view.set_focus()
        # Focus behavior depends on widget hierarchy

    def test_select_next_no_current_selection(
        self, library_view: LibraryView, sample_items: list[dict]
    ) -> None:
        """Test select_next when there's no current selection but items exist."""
        library_view.set_items(sample_items)
        # Clear selection manually
        library_view._list_view.clearSelection()
        library_view._list_view.setCurrentIndex(
            library_view._model.index(-1, 0)  # Invalid index
        )

        # select_next should select first item
        result = library_view.select_next()
        assert result is True
        selected = library_view.get_selected_item()
        assert selected["id"] == "movie-1"

    def test_select_next_empty_list(self, library_view: LibraryView) -> None:
        """Test select_next returns False when list is empty."""
        result = library_view.select_next()
        assert result is False

    def test_select_prev_no_current_selection(
        self, library_view: LibraryView, sample_items: list[dict]
    ) -> None:
        """Test select_prev when there's no current selection but items exist."""
        library_view.set_items(sample_items)
        # Clear selection manually
        library_view._list_view.clearSelection()
        library_view._list_view.setCurrentIndex(
            library_view._model.index(-1, 0)  # Invalid index
        )

        # select_prev should select last item
        result = library_view.select_prev()
        assert result is True
        selected = library_view.get_selected_item()
        assert selected["id"] == "series-1"  # Last item

    def test_select_prev_empty_list(self, library_view: LibraryView) -> None:
        """Test select_prev returns False when list is empty."""
        result = library_view.select_prev()
        assert result is False

    def test_selection_changed_emits_empty_dict_for_invalid_index(
        self, library_view: LibraryView, sample_items: list[dict], qtbot
    ) -> None:
        """Test that selection_changed emits empty dict for invalid selection."""
        library_view.set_items(sample_items)

        received = []

        def capture(data):
            received.append(data)

        library_view.selection_changed.connect(capture)

        # Simulate selection change to invalid index
        from PySide6.QtCore import QModelIndex

        library_view._on_selection_changed(QModelIndex(), QModelIndex())

        assert len(received) == 1
        assert received[0] == {}

    def test_update_item_with_pipeline_state(
        self, library_view: LibraryView, sample_items: list[dict]
    ) -> None:
        """Test updating an item's pipeline state."""
        library_view.set_items(sample_items)
        library_view.update_item(
            "movie-1",
            {
                "pipeline_state": "TRANSLATING",
            },
        )
        # The update should not raise an exception

    def test_update_item_nonexistent(
        self, library_view: LibraryView, sample_items: list[dict]
    ) -> None:
        """Test updating a nonexistent item does nothing."""
        library_view.set_items(sample_items)
        # Should not raise
        library_view.update_item("nonexistent-id", {"state": "COMPLETED"})

    def test_activate_selected_empty(self, library_view: LibraryView) -> None:
        """Test activate_selected does nothing when list is empty."""
        # Should not raise or emit signal
        library_view.activate_selected()
