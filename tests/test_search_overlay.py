"""Tests for SearchOverlay component."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from src.ui.components.search_overlay import SearchOverlay, SearchOverlayBackground


class TestSearchOverlay:
    """Tests for SearchOverlay class."""

    @pytest.fixture
    def parent_widget(self, qtbot) -> QWidget:
        """Create a parent widget."""
        widget = QWidget()
        widget.resize(800, 600)
        qtbot.addWidget(widget)
        return widget

    @pytest.fixture
    def overlay(self, parent_widget: QWidget, qtbot) -> SearchOverlay:
        """Create a SearchOverlay instance."""
        overlay = SearchOverlay(parent_widget)
        qtbot.addWidget(overlay)
        return overlay

    def test_initialization(self, overlay: SearchOverlay) -> None:
        """Test SearchOverlay initialization."""
        assert overlay is not None
        assert overlay.objectName() == "SearchOverlay"
        assert not overlay.isVisible()  # Hidden by default

    def test_has_search_input(self, overlay: SearchOverlay) -> None:
        """Test that overlay has search input field."""
        assert overlay._search_input is not None

    def test_show_search(self, overlay: SearchOverlay, parent_widget: QWidget) -> None:
        """Test show_search prepares overlay for display."""
        parent_widget.show()
        overlay.show_search()
        # Widget should have been shown (even if not rendered due to test environment)
        # Verify that show() was called by checking it's not explicitly hidden
        assert not overlay.isHidden() or overlay.isVisible()

    def test_show_search_with_filter(self, overlay: SearchOverlay) -> None:
        """Test show_search pre-populates filter."""
        overlay.show_search("existing filter")
        assert overlay._search_input.text() == "existing filter"

    def test_get_query(self, overlay: SearchOverlay) -> None:
        """Test get_query returns input text."""
        overlay._search_input.setText("  test query  ")
        assert overlay.get_query() == "test query"  # Trimmed

    def test_clear(self, overlay: SearchOverlay) -> None:
        """Test clear empties the input."""
        overlay._search_input.setText("some text")
        overlay.clear()
        assert overlay._search_input.text() == ""

    def test_search_committed_signal_on_enter(
        self, overlay: SearchOverlay, qtbot
    ) -> None:
        """Test that Enter key emits search_committed signal."""
        overlay.show_search()
        overlay._search_input.setText("test query")

        with qtbot.waitSignal(overlay.search_committed, timeout=100) as blocker:
            qtbot.keyClick(overlay, Qt.Key_Return)

        assert blocker.args == ["test query"]

    def test_search_cancelled_signal_on_escape(
        self, overlay: SearchOverlay, qtbot
    ) -> None:
        """Test that Escape key emits search_cancelled signal."""
        overlay.show_search()

        with qtbot.waitSignal(overlay.search_cancelled, timeout=100):
            qtbot.keyClick(overlay, Qt.Key_Escape)

    def test_enter_hides_overlay(self, overlay: SearchOverlay, qtbot) -> None:
        """Test that Enter hides the overlay."""
        overlay.show_search()

        qtbot.keyClick(overlay, Qt.Key_Return)
        # After Enter, overlay should be hidden
        assert overlay.isHidden()

    def test_escape_hides_overlay(self, overlay: SearchOverlay, qtbot) -> None:
        """Test that Escape hides the overlay."""
        overlay.show_search()

        qtbot.keyClick(overlay, Qt.Key_Escape)
        # After Escape, overlay should be hidden
        assert overlay.isHidden()

    def test_fixed_width(self, overlay: SearchOverlay) -> None:
        """Test that overlay has fixed width."""
        from src.ui.styles import SEARCH_WIDTH

        assert overlay.width() == SEARCH_WIDTH


class TestSearchOverlayBackground:
    """Tests for SearchOverlayBackground class."""

    @pytest.fixture
    def parent_widget(self, qtbot) -> QWidget:
        """Create a parent widget."""
        widget = QWidget()
        widget.resize(800, 600)
        qtbot.addWidget(widget)
        return widget

    @pytest.fixture
    def background(self, parent_widget: QWidget, qtbot) -> SearchOverlayBackground:
        """Create a SearchOverlayBackground instance."""
        bg = SearchOverlayBackground(parent_widget)
        qtbot.addWidget(bg)
        return bg

    def test_initialization(self, background: SearchOverlayBackground) -> None:
        """Test SearchOverlayBackground initialization."""
        assert background is not None
        assert not background.isVisible()  # Hidden by default

    def test_show_fullscreen(
        self, background: SearchOverlayBackground, parent_widget: QWidget
    ) -> None:
        """Test show_fullscreen sets geometry to cover parent."""
        background.show_fullscreen()
        # Check geometry was set correctly
        assert background.geometry() == parent_widget.rect()
        # Background should not be explicitly hidden
        assert not background.isHidden()

    def test_clicked_signal(self, background: SearchOverlayBackground, qtbot) -> None:
        """Test that clicking emits clicked signal."""
        background.show()

        with qtbot.waitSignal(background.clicked, timeout=100):
            qtbot.mouseClick(background, Qt.LeftButton)


class TestSearchOverlayKeyHandling:
    """Tests for SearchOverlay key handling edge cases."""

    @pytest.fixture
    def parent_widget(self, qtbot) -> QWidget:
        """Create a parent widget."""
        widget = QWidget()
        widget.resize(800, 600)
        qtbot.addWidget(widget)
        return widget

    @pytest.fixture
    def overlay(self, parent_widget: QWidget, qtbot) -> SearchOverlay:
        """Create a SearchOverlay instance."""
        overlay = SearchOverlay(parent_widget)
        qtbot.addWidget(overlay)
        return overlay

    def test_other_keys_passed_to_super(self, overlay: SearchOverlay, qtbot) -> None:
        """Test that other keys are passed to line edit."""
        overlay.show_search()
        # Type a character directly on the line edit
        qtbot.keyClick(overlay._search_input, Qt.Key_A)
        # The character should be in the input
        assert "a" in overlay._search_input.text().lower()

    def test_non_special_keys_call_super(self, overlay: SearchOverlay, qtbot) -> None:
        """Test that non-special keys call super().keyPressEvent."""
        from PySide6.QtGui import QKeyEvent
        from PySide6.QtCore import QEvent

        overlay.show_search()
        # Create a key event for a regular key (not Enter or Escape)
        event = QKeyEvent(QEvent.KeyPress, Qt.Key_B, Qt.NoModifier, "b")
        # Call keyPressEvent directly to exercise the super() path
        overlay.keyPressEvent(event)
        # Event should be handled (not rejected)

    def test_center_in_parent_without_parent(self, qtbot) -> None:
        """Test _center_in_parent when overlay has no parent."""
        overlay = SearchOverlay(None)
        qtbot.addWidget(overlay)

        # Should not raise
        overlay._center_in_parent()
        # Overlay should still exist
        assert overlay is not None

    def test_center_in_parent_with_non_widget_parent(self, qtbot) -> None:
        """Test _center_in_parent with valid parent."""
        parent = QWidget()
        parent.resize(800, 600)
        qtbot.addWidget(parent)

        overlay = SearchOverlay(parent)
        qtbot.addWidget(overlay)

        # Should not raise
        overlay._center_in_parent()

        # Check that overlay is centered
        expected_x = (parent.rect().width() - overlay.width()) // 2
        expected_y = (parent.rect().height() - overlay.height()) // 2
        assert overlay.x() == expected_x
        assert overlay.y() == expected_y
