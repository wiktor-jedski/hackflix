"""Confirmation dialog component for Hackflix.

This module provides the ConfirmDialog widget for confirming
destructive actions like file deletion.
"""

from src.qt import QApplication, QFont, QFontMetrics, Qt
from src.qt import QKeyEvent
from src.qt import QDialog, QLabel, QVBoxLayout, QWidget

from src.ui.styles import (
    DIALOG_PADDING,
    DIALOG_WIDTH,
    FONT_SIZE_BODY,
    FONT_SIZE_LARGE,
    FONT_SIZE_SMALL,
    SECONDARY_COLOR,
    SURFACE_COLOR,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    WARNING_COLOR,
    scaled,
)

MAX_DIALOG_SCREEN_WIDTH_RATIO = 0.85


class ConfirmDialog(QDialog):
    """Modal confirmation dialog.

    A simple keyboard-driven dialog for confirming actions.
    Enter accepts the action, Escape cancels.

    This dialog does not use buttons - it relies on keyboard
    navigation as per the application's appliance-style design.
    """

    def __init__(
        self,
        title: str,
        message: str,
        parent: QWidget | None = None,
    ) -> None:
        """Initialize the ConfirmDialog.

        Args:
            title: Dialog title (e.g., "Delete Movie?").
            message: Explanation message.
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self._title = title
        self._message = message
        self._setup_ui()

    def _dialog_width_for_text(self) -> int:
        """Calculate a dialog width that fits the visible text."""
        title_font = QFont(self.font())
        title_font.setPixelSize(FONT_SIZE_LARGE)
        title_font.setBold(True)

        body_font = QFont(self.font())
        body_font.setPixelSize(FONT_SIZE_BODY)

        hint_font = QFont(self.font())
        hint_font.setPixelSize(FONT_SIZE_SMALL)

        widest_text = max(
            QFontMetrics(title_font).horizontalAdvance(self._title),
            QFontMetrics(body_font).horizontalAdvance(self._message),
            QFontMetrics(hint_font).horizontalAdvance(
                self.tr("Press Enter to confirm, Esc to cancel")
            ),
        )
        desired_width = widest_text + (DIALOG_PADDING * 2)

        screen = QApplication.primaryScreen()
        if screen is None:
            return max(DIALOG_WIDTH, desired_width)

        max_width = int(
            screen.availableGeometry().width() * MAX_DIALOG_SCREEN_WIDTH_RATIO
        )
        return min(max(DIALOG_WIDTH, desired_width), max_width)

    def _setup_ui(self) -> None:
        """Set up the dialog UI layout and styling."""
        self.setObjectName("ConfirmDialog")
        self.setWindowTitle(self._title)
        self.setFixedWidth(self._dialog_width_for_text())
        self.setModal(True)

        # Remove window frame for cleaner look
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)

        self.setStyleSheet(f"""
            QDialog#ConfirmDialog {{
                background-color: {SURFACE_COLOR};
                border: 1px solid {SECONDARY_COLOR};
                border-radius: 8px;
            }}
            QLabel {{
                background-color: transparent;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            DIALOG_PADDING, DIALOG_PADDING, DIALOG_PADDING, DIALOG_PADDING
        )
        layout.setSpacing(scaled(16))

        # Warning icon and title
        self._title_label = QLabel(self._title)
        self._title_label.setStyleSheet(f"""
            font-size: {FONT_SIZE_LARGE}px;
            font-weight: bold;
            color: {WARNING_COLOR};
        """)
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title_label.setWordWrap(True)
        layout.addWidget(self._title_label)

        # Message
        self._message_label = QLabel(self._message)
        self._message_label.setStyleSheet(f"""
            font-size: {FONT_SIZE_BODY}px;
            color: {TEXT_PRIMARY};
        """)
        self._message_label.setWordWrap(True)
        self._message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._message_label)

        # Hint text
        self._hint_label = QLabel(self.tr("Press Enter to confirm, Esc to cancel"))
        self._hint_label.setStyleSheet(f"""
            font-size: {FONT_SIZE_SMALL}px;
            color: {TEXT_SECONDARY};
        """)
        self._hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._hint_label)

    def keyPressEvent(self, event: QKeyEvent | None) -> None:  # type: ignore[invalid-method-override]
        """Handle key press events.

        Args:
            event: The key event.
        """
        if event is None:
            return

        key = event.key()

        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.accept()
            event.accept()
        elif key == Qt.Key.Key_Escape:
            self.reject()
            event.accept()
        else:
            super().keyPressEvent(event)

    @staticmethod
    def confirm(
        title: str,
        message: str,
        parent: QWidget | None = None,
    ) -> bool:
        """Show a confirmation dialog and return the result.

        Convenience static method for showing a dialog synchronously.

        Args:
            title: Dialog title.
            message: Explanation message.
            parent: Optional parent widget.

        Returns:
            True if user confirmed (Enter), False if cancelled (Esc).
        """
        dialog = ConfirmDialog(title, message, parent)
        result = dialog.exec()
        return result == QDialog.DialogCode.Accepted
