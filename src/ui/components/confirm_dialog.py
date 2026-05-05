"""Confirmation dialog component for Hackflix.

This module provides the ConfirmDialog widget for confirming
destructive actions like file deletion.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout, QWidget

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
)


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

    def _setup_ui(self) -> None:
        """Set up the dialog UI layout and styling."""
        self.setObjectName("ConfirmDialog")
        self.setWindowTitle(self._title)
        self.setFixedWidth(DIALOG_WIDTH)
        self.setModal(True)

        # Remove window frame for cleaner look
        self.setWindowFlags(
            Qt.Dialog | Qt.FramelessWindowHint  # type: ignore[attr-defined]
        )

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
        layout.setSpacing(16)

        # Warning icon and title
        self._title_label = QLabel(self._title)
        self._title_label.setStyleSheet(f"""
            font-size: {FONT_SIZE_LARGE}px;
            font-weight: bold;
            color: {WARNING_COLOR};
        """)
        self._title_label.setAlignment(Qt.AlignCenter)  # type: ignore[attr-defined]
        layout.addWidget(self._title_label)

        # Message
        self._message_label = QLabel(self._message)
        self._message_label.setStyleSheet(f"""
            font-size: {FONT_SIZE_BODY}px;
            color: {TEXT_PRIMARY};
        """)
        self._message_label.setWordWrap(True)
        self._message_label.setAlignment(Qt.AlignCenter)  # type: ignore[attr-defined]
        layout.addWidget(self._message_label)

        # Hint text
        self._hint_label = QLabel("Press Enter to confirm, Esc to cancel")
        self._hint_label.setStyleSheet(f"""
            font-size: {FONT_SIZE_SMALL}px;
            color: {TEXT_SECONDARY};
        """)
        self._hint_label.setAlignment(Qt.AlignCenter)  # type: ignore[attr-defined]
        layout.addWidget(self._hint_label)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle key press events.

        Args:
            event: The key event.
        """
        key = event.key()

        if key in (Qt.Key_Return, Qt.Key_Enter):  # type: ignore[attr-defined]
            self.accept()
            event.accept()
        elif key == Qt.Key_Escape:  # type: ignore[attr-defined]
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
