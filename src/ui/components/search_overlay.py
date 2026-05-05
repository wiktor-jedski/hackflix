"""Search overlay component for Hackflix.

This module provides the SearchOverlay widget for text-based
filtering of the media library.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QKeyEvent, QMouseEvent, QPalette
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from src.ui.styles import (
    BACKGROUND_COLOR,
    FONT_SIZE_BODY,
    FONT_SIZE_LARGE,
    FONT_SIZE_SMALL,
    PRIMARY_COLOR,
    SEARCH_INPUT_HEIGHT,
    SEARCH_WIDTH,
    SECONDARY_COLOR,
    SURFACE_COLOR,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class SearchOverlay(QFrame):
    """Modal search overlay for filtering the library.

    The search overlay captures all keyboard input when visible.
    Enter commits the search (filter persists on library).
    Escape cancels the search (clears filter).

    Signals:
        search_committed: Emitted with the search query when Enter is pressed.
        search_cancelled: Emitted when Escape is pressed (search cancelled).
    """

    search_committed = Signal(str)
    search_cancelled = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the SearchOverlay.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the search overlay UI layout and styling."""
        self.setObjectName("SearchOverlay")
        self.setFixedWidth(SEARCH_WIDTH)

        # Required for QFrame to render background-color from stylesheet
        self.setAttribute(Qt.WA_StyledBackground, True)  # type: ignore[attr-defined]

        self.setStyleSheet(f"""
            QFrame#SearchOverlay {{
                background-color: {SURFACE_COLOR};
                border: 1px solid {SECONDARY_COLOR};
                border-radius: 8px;
            }}
            QFrame#SearchOverlay QLabel {{
                background-color: transparent;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Title
        self._title_label = QLabel("Search")
        self._title_label.setStyleSheet(f"""
            font-size: {FONT_SIZE_LARGE}px;
            font-weight: bold;
            color: {TEXT_PRIMARY};
        """)
        self._title_label.setAlignment(Qt.AlignCenter)  # type: ignore[attr-defined]
        layout.addWidget(self._title_label)

        # Search input
        self._search_input = QLineEdit()
        self._search_input.setObjectName("SearchInput")
        self._search_input.setPlaceholderText("Type to search...")
        self._search_input.setFixedHeight(SEARCH_INPUT_HEIGHT)
        self._search_input.setStyleSheet(f"""
            background-color: {BACKGROUND_COLOR};
            border: 2px solid {SECONDARY_COLOR};
            border-radius: 4px;
            padding: 8px 12px;
            font-size: {FONT_SIZE_BODY}px;
            color: {TEXT_PRIMARY};
            selection-background-color: {PRIMARY_COLOR};
            selection-color: {TEXT_PRIMARY};
        """)

        # Set palette colors as fallback for text visibility
        palette = self._search_input.palette()
        palette.setColor(QPalette.ColorRole.Text, QColor(TEXT_PRIMARY))
        palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(TEXT_SECONDARY))
        self._search_input.setPalette(palette)

        # Connect return pressed signal to handle Enter key from the line edit
        self._search_input.returnPressed.connect(self._on_return_pressed)

        layout.addWidget(self._search_input)

        # Hint text
        self._hint_label = QLabel("Press Enter to search, Esc to cancel")
        self._hint_label.setStyleSheet(f"""
            font-size: {FONT_SIZE_SMALL}px;
            color: {TEXT_SECONDARY};
        """)
        self._hint_label.setAlignment(Qt.AlignCenter)  # type: ignore[attr-defined]
        layout.addWidget(self._hint_label)

        # Compute proper size based on contents
        self.adjustSize()

        # Hide by default
        self.hide()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle key press events.

        Args:
            event: The key event.
        """
        key = event.key()

        if key in (Qt.Key_Return, Qt.Key_Enter):  # type: ignore[attr-defined]
            self._on_return_pressed()
            event.accept()
        elif key == Qt.Key_Escape:  # type: ignore[attr-defined]
            # Cancel search
            self.search_cancelled.emit()
            self.hide()
            event.accept()
        else:
            # Forward other keys to the search input for text entry
            self._search_input.setFocus()
            self._search_input.event(event)

    def _on_return_pressed(self) -> None:
        """Handle return key pressed in line edit or widget."""
        query = self._search_input.text().strip()
        self.search_committed.emit(query)
        self.hide()

    def show_search(self, current_filter: str = "") -> None:
        """Show the search overlay.

        Args:
            current_filter: The current search filter to pre-populate.
        """
        self._search_input.setText(current_filter)
        self._search_input.selectAll()
        self.show()
        self._search_input.setFocus()
        self._center_in_parent()

    def _center_in_parent(self) -> None:
        """Center the overlay in its parent widget."""
        if self.parent() is None:
            return

        parent = self.parent()
        if isinstance(parent, QWidget):
            parent_rect = parent.rect()
            x = (parent_rect.width() - self.width()) // 2
            y = (parent_rect.height() - self.height()) // 2
            self.move(x, y)

    def get_query(self) -> str:
        """Get the current search query.

        Returns:
            The text in the search input field.
        """
        return self._search_input.text().strip()

    def clear(self) -> None:
        """Clear the search input."""
        self._search_input.clear()


class SearchOverlayBackground(QWidget):
    """Semi-transparent background for modal search overlay.

    This widget covers the entire parent and darkens the background
    to indicate modal state.
    """

    clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the background overlay.

        Args:
            parent: Parent widget to cover.
        """
        super().__init__(parent)
        self.setStyleSheet("background-color: rgba(0, 0, 0, 0.7);")
        self.hide()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Handle mouse press to close overlay.

        Args:
            event: The mouse event.
        """
        self.clicked.emit()
        event.accept()

    def show_fullscreen(self) -> None:
        """Show the background covering the entire parent."""
        parent = self.parent()
        if parent and isinstance(parent, QWidget):
            self.setGeometry(parent.rect())
        self.show()
        self.raise_()
