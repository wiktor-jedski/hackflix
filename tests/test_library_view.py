"""Tests for LibraryView component."""

import pytest
from src.qt import QPixmap
from src.qt import QStyledItemDelegate

from src.config import DownloadState
from src.ui.components.library_item_delegate import LibraryItemRole
from src.ui.components.library_view import LibraryView
from src.ui.enums import MediaTab
from src.ui.styles import POSTER_HEIGHT, POSTER_WIDTH, SURFACE_COLOR


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

    def test_set_items_stores_duration_role(self, library_view: LibraryView) -> None:
        """Test duration is exposed to the item delegate."""
        item_data = {
            "id": "movie-duration",
            "type": "movie",
            "title": "Duration Movie",
            "state": DownloadState.COMPLETED.value,
            "duration_seconds": 7322,
        }

        library_view.set_items([item_data])

        item = library_view._model.item(0)
        assert item.data(LibraryItemRole.DurationSecondsRole) == 7322

    @pytest.mark.parametrize(
        ("item_data", "expected"),
        [
            (
                {
                    "type": "movie",
                    "state": DownloadState.COMPLETED.value,
                    "resume_position_seconds": 42,
                },
                "[Resume 1 min] Test",
            ),
            (
                {
                    "type": "movie",
                    "state": DownloadState.COMPLETED.value,
                    "resume_position_seconds": 2520,
                },
                "[Resume 42 min] Test",
            ),
            (
                {
                    "type": "movie",
                    "state": DownloadState.COMPLETED.value,
                    "watched_at": "2026-05-08 12:00:00",
                },
                "[Watched] Test",
            ),
            (
                {"type": "movie", "state": DownloadState.COMPLETED.value},
                "[Play] Test",
            ),
        ],
    )
    def test_completed_item_status_text_uses_resume_and_watched_state(
        self, library_view: LibraryView, item_data: dict[str, object], expected: str
    ) -> None:
        """Test completed fallback labels show resume, watched, or play."""
        item_data["title"] = "Test"

        assert library_view._format_item_text(item_data) == expected

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

    @pytest.mark.parametrize(
        ("item_data", "expected_kind"),
        [
            ({"type": "movie", "state": DownloadState.PENDING.value}, "download"),
            ({"type": "movie", "state": DownloadState.QUEUED.value}, "download"),
            (
                {
                    "type": "movie",
                    "state": DownloadState.DOWNLOADING.value,
                    "download_progress": 42,
                },
                "hourglass",
            ),
            ({"type": "movie", "state": DownloadState.COMPLETED.value}, "play"),
            ({"type": "movie", "state": DownloadState.ERROR.value}, "warning"),
            ({"type": "series", "state": None}, "series"),
        ],
    )
    def test_status_indicator_mapping(
        self,
        library_view: LibraryView,
        item_data: dict[str, object],
        expected_kind: str,
    ) -> None:
        """Test poster overlay status symbols use the expected state mapping."""
        indicator = library_view._status_indicator(item_data)

        assert indicator["kind"] == expected_kind

    def test_status_indicator_empty_for_unknown_state(
        self, library_view: LibraryView
    ) -> None:
        """Test unknown states do not draw an overlay."""
        assert library_view._status_indicator({"type": "movie", "state": None}) == {}

    def test_generated_icon_contains_status_overlay(
        self, library_view: LibraryView
    ) -> None:
        """Test generated poster icons include static overlay pixels."""
        icon = library_view._build_item_icon(
            {"type": "movie", "state": DownloadState.COMPLETED.value}
        )
        pixmap = icon.pixmap(POSTER_WIDTH, POSTER_HEIGHT)
        image = pixmap.toImage()
        background = SURFACE_COLOR.lower()

        overlay_pixels = [
            image.pixelColor(x, y).name().lower()
            for x in range(POSTER_WIDTH - 35, POSTER_WIDTH - 5)
            for y in range(POSTER_HEIGHT - 35, POSTER_HEIGHT - 5)
        ]

        assert any(color != background for color in overlay_pixels)

    @pytest.mark.parametrize(
        "item_data",
        [
            {"type": "movie", "state": DownloadState.PENDING.value},
            {"type": "movie", "state": DownloadState.QUEUED.value},
            {
                "type": "movie",
                "state": DownloadState.DOWNLOADING.value,
                "download_progress": 42,
            },
            {"type": "movie", "state": DownloadState.COMPLETED.value},
            {"type": "movie", "state": DownloadState.ERROR.value},
            {"type": "series", "state": None},
        ],
    )
    def test_generated_icon_contains_each_status_overlay(
        self, library_view: LibraryView, item_data: dict[str, object]
    ) -> None:
        """Test each status type draws a static overlay."""
        icon = library_view._build_item_icon(item_data)
        image = icon.pixmap(POSTER_WIDTH, POSTER_HEIGHT).toImage()
        background = SURFACE_COLOR.lower()

        overlay_pixels = [
            image.pixelColor(x, y).name().lower()
            for x in range(POSTER_WIDTH - 35, POSTER_WIDTH - 5)
            for y in range(POSTER_HEIGHT - 35, POSTER_HEIGHT - 5)
        ]

        assert any(color != background for color in overlay_pixels)

    def test_build_item_icon_without_status_overlay(
        self, library_view: LibraryView
    ) -> None:
        """Test icon generation works for items without a status indicator."""
        icon = library_view._build_item_icon({"type": "movie", "state": None})

        assert not icon.isNull()

    def test_placeholder_label_for_season_and_episode(
        self, library_view: LibraryView
    ) -> None:
        """Test generated placeholders show season and episode labels."""
        assert library_view._placeholder_label({"type": "season"}) == "Season"
        assert (
            library_view._placeholder_number({"type": "season", "season_number": 3})
            == "3"
        )
        assert library_view._placeholder_label({"type": "episode"}) == "Episode"
        assert (
            library_view._placeholder_number({"type": "episode", "episode_number": 12})
            == "12"
        )

    def test_placeholder_label_empty_for_movie(self, library_view: LibraryView) -> None:
        """Test movie placeholders do not get season or episode labels."""
        assert library_view._placeholder_label({"type": "movie"}) == ""
        assert library_view._placeholder_number({"type": "movie"}) == ""

    def test_generated_season_icon_contains_number_placeholder(
        self, library_view: LibraryView
    ) -> None:
        """Test generated season placeholders draw visible number pixels."""
        icon = library_view._build_item_icon(
            {"type": "season", "season_number": 2, "state": None}
        )
        image = icon.pixmap(POSTER_WIDTH, POSTER_HEIGHT).toImage()
        background = SURFACE_COLOR.lower()

        center_pixels = [
            image.pixelColor(x, y).name().lower()
            for x in range(POSTER_WIDTH // 4, (POSTER_WIDTH * 3) // 4)
            for y in range(POSTER_HEIGHT // 4, (POSTER_HEIGHT * 3) // 4)
        ]

        assert any(color != background for color in center_pixels)

    def test_build_item_icon_skips_invalid_poster(
        self, library_view: LibraryView, tmp_path
    ) -> None:
        """Test invalid poster files fall back to generated placeholder icons."""
        poster_path = tmp_path / "poster.txt"
        poster_path.write_text("not an image")

        icon = library_view._build_item_icon(
            {
                "type": "movie",
                "state": DownloadState.PENDING.value,
                "poster_path": str(poster_path),
            }
        )

        assert not icon.isNull()

    def test_custom_delegate_can_be_enabled(self, qtbot, monkeypatch) -> None:
        """Test custom delegate remains opt-in through the environment flag."""
        monkeypatch.setenv("HACKFLIX_CUSTOM_LIBRARY_DELEGATE", "1")

        view = LibraryView()
        qtbot.addWidget(view)

        assert isinstance(view._list_view.itemDelegate(), QStyledItemDelegate)

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
        assert library_view.get_items()[0]["download_progress"] == 50
        assert item.text().startswith("[Downloading 50%]")

    def test_set_items_does_not_store_explicit_none_role_values(
        self, library_view: LibraryView
    ) -> None:
        """Test optional empty fields are left unset in Qt item roles."""
        library_view.set_items(
            [
                {
                    "id": 3,
                    "type": "season",
                    "title": "Season 3",
                    "season_number": 3,
                    "state": DownloadState.PENDING.value,
                }
            ]
        )

        item = library_view._model.item(0)
        assert item.data(LibraryItemRole.GenresRole) is None
        assert item.data(LibraryItemRole.PosterPathRole) is None

    def test_update_all_items_handles_rows_with_missing_optional_fields(
        self, library_view: LibraryView
    ) -> None:
        """Test season progress updates work when optional roles are unset."""
        library_view.set_items(
            [
                {
                    "id": 10,
                    "type": "episode",
                    "title": "Episode 1",
                    "episode_number": 1,
                    "state": DownloadState.PENDING.value,
                },
                {
                    "id": 11,
                    "type": "episode",
                    "title": "Episode 2",
                    "episode_number": 2,
                    "state": DownloadState.PENDING.value,
                },
            ]
        )

        library_view.update_all_items(
            {"state": DownloadState.DOWNLOADING.value, "download_progress": 49}
        )

        for row in range(library_view._model.rowCount()):
            item = library_view._model.item(row)
            assert (
                library_view.get_items()[row]["state"]
                == DownloadState.DOWNLOADING.value
            )
            assert library_view.get_items()[row]["download_progress"] == 49
            assert item.text().startswith("[Downloading 49%]")

    def test_progress_update_does_not_rebuild_icon(
        self, library_view: LibraryView, sample_items: list[dict], mocker
    ) -> None:
        """Test progress-only updates avoid repeated Qt icon regeneration."""
        sample_items[0]["state"] = DownloadState.DOWNLOADING.value
        sample_items[0]["download_progress"] = 10
        library_view.set_items(sample_items)
        build_icon = mocker.spy(library_view, "_build_item_icon_from_model_item")

        library_view.update_item("movie-1", {"download_progress": 11})

        build_icon.assert_not_called()

    def test_state_update_rebuilds_icon(
        self, library_view: LibraryView, sample_items: list[dict], mocker
    ) -> None:
        """Test state changes still refresh the status badge icon."""
        library_view.set_items(sample_items)
        build_icon = mocker.spy(library_view, "_build_item_icon")

        library_view.update_item("movie-1", {"state": DownloadState.DOWNLOADING.value})

        build_icon.assert_called_once()

    def test_update_item_by_file_id(
        self, library_view: LibraryView, sample_items: list[dict]
    ) -> None:
        """Test updating an item by its file ID."""
        sample_items[0]["file_id"] = 123
        library_view.set_items(sample_items)

        library_view.update_item_by_file_id(
            123,
            {
                "state": DownloadState.ERROR.value,
                "download_progress": 0,
            },
        )

        item = library_view._model.item(0)
        assert library_view.get_items()[0]["state"] == DownloadState.ERROR.value
        assert item.text().startswith("[Error]")

    def test_update_item_by_file_id_not_found(
        self, library_view: LibraryView, sample_items: list[dict]
    ) -> None:
        """Test updating a nonexistent file ID does nothing."""
        sample_items[0]["file_id"] = 123
        library_view.set_items(sample_items)

        library_view.update_item_by_file_id(
            999,
            {
                "state": DownloadState.ERROR.value,
            },
        )

        item = library_view._model.item(0)
        assert (
            item.data(LibraryItemRole.DownloadStateRole) == DownloadState.PENDING.value
        )

    def test_apply_updates_ignores_unchanged_values(
        self, library_view: LibraryView, sample_items: list[dict]
    ) -> None:
        """Test repeated values do not rewrite display text."""
        library_view.set_items(sample_items)
        item = library_view._model.item(0)
        original_text = item.text()

        library_view.update_item(
            "movie-1",
            {
                "state": DownloadState.PENDING.value,
                "download_progress": None,
                "pipeline_state": None,
            },
        )

        assert item.text() == original_text

    @pytest.mark.parametrize(
        ("state", "expected_prefix"),
        [
            (DownloadState.COMPLETED.value, "[Play]"),
            (DownloadState.DOWNLOADING.value, "[Downloading 77%]"),
            (DownloadState.ERROR.value, "[Error]"),
            (DownloadState.QUEUED.value, "[Queued]"),
            ("PAUSED", "[Paused]"),
            (None, "Format Movie"),
        ],
    )
    def test_format_item_text_state_branches(
        self,
        library_view: LibraryView,
        state: str | None,
        expected_prefix: str,
    ) -> None:
        """Test fallback display text for all download-state branches."""
        text = library_view._format_item_text(
            {
                "title": "Format Movie",
                "type": "movie",
                "state": state,
                "download_progress": 77,
            }
        )

        assert text.startswith(expected_prefix)

    def test_format_item_text_with_episode_title_only(
        self, library_view: LibraryView
    ) -> None:
        """Test episode titles are included as fallback subtitle text."""
        text = library_view._format_item_text(
            {
                "title": "Episode Row",
                "type": "movie",
                "state": None,
                "episode_title": "Pilot",
            }
        )

        assert text == "Episode Row\nPilot"

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
        from src.qt import QModelIndex

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
