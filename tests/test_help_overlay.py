"""Tests for HelpOverlay component."""

import pytest

from src.qt import Qt, QWidget

from src.ui.components.help_overlay import HELP_CONTENT_HTML, HelpOverlay


class TestHelpOverlay:
    """Tests for HelpOverlay."""

    @pytest.fixture
    def overlay(self, parent_widget: QWidget, qtbot) -> HelpOverlay:
        """Create a HelpOverlay instance."""
        overlay = HelpOverlay(parent_widget)
        qtbot.addWidget(overlay)
        return overlay

    @pytest.fixture
    def parent_widget(self, qtbot) -> QWidget:
        """Create parent widget."""
        widget = QWidget()
        widget.resize(1000, 760)
        qtbot.addWidget(widget)
        widget.show()
        return widget

    def test_initialization(self, overlay: HelpOverlay) -> None:
        """Test HelpOverlay initialization."""
        assert overlay.objectName() == "HelpOverlay"
        assert overlay._title_label.text() == "Pomoc"
        assert overlay._hint_label.text() == "Naciśnij Esc, aby zamknąć"
        assert overlay._content_browser is not None
        assert overlay.isHidden()

    def test_embedded_content_has_instruction_sections(self) -> None:
        """Test embedded help contains key instruction sections."""
        assert "Poruszanie sie po liscie" in HELP_CONTENT_HTML
        assert "Szukanie filmu na liscie" in HELP_CONTENT_HTML
        assert "Sterowanie odtwarzaczem" in HELP_CONTENT_HTML
        assert "Przewin do poczatku" in HELP_CONTENT_HTML
        assert "Przejscie z <b>Filmow</b> do <b>Seriali</b>" in HELP_CONTENT_HTML
        assert "Przejscie z <b>Seriali</b> do <b>Filmow</b>" in HELP_CONTENT_HTML

    def test_show_help(self, overlay: HelpOverlay) -> None:
        """Test show_help displays and focuses overlay."""
        overlay.show_help()

        assert not overlay.isHidden()
        assert overlay.focusPolicy() == Qt.FocusPolicy.StrongFocus
        assert overlay._content_browser.hasFocus()

    def test_escape_emits_help_closed(
        self, overlay: HelpOverlay, qtbot
    ) -> None:
        """Test Escape emits help_closed."""
        overlay.show_help()

        with qtbot.waitSignal(overlay.help_closed, timeout=100):
            qtbot.keyClick(overlay, Qt.Key.Key_Escape)

    def test_escape_in_content_browser_emits_help_closed(
        self, overlay: HelpOverlay, qtbot
    ) -> None:
        """Test Escape closes help from focused content browser."""
        overlay.show_help()

        with qtbot.waitSignal(overlay.help_closed, timeout=100):
            qtbot.keyClick(overlay._content_browser, Qt.Key.Key_Escape)

    def test_escape_hides_overlay(self, overlay: HelpOverlay, qtbot) -> None:
        """Test Escape hides the overlay."""
        overlay.show_help()

        qtbot.keyClick(overlay, Qt.Key.Key_Escape)

        assert overlay.isHidden()

    def test_non_escape_key_does_not_close(self, overlay: HelpOverlay, qtbot) -> None:
        """Test non-Escape keys do not close help."""
        overlay.show_help()

        qtbot.keyClick(overlay, Qt.Key.Key_A)

        assert not overlay.isHidden()

    def test_center_without_parent_does_not_crash(self, qtbot) -> None:
        """Test centering without parent does not crash."""
        overlay = HelpOverlay(None)
        qtbot.addWidget(overlay)

        overlay._center_in_parent()

        assert overlay is not None
