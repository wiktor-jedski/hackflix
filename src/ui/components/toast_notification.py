"""Toast notification component for Hackflix.

This module provides the ToastNotification widget for displaying
transient messages to the user.
"""

import logging
from typing import Literal

from PyQt5.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QTimer,
    pyqtSignal,
)
from PyQt5.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget

from src.config import TOAST_TIMEOUT_MS
from src.ui.styles import (
    ANIMATION_DURATION_NORMAL,
    ERROR_COLOR,
    FONT_SIZE_BODY,
    INFO_COLOR,
    SURFACE_COLOR,
    TEXT_PRIMARY,
    TOAST_MARGIN,
    TOAST_MIN_HEIGHT,
    TOAST_WIDTH,
    WARNING_COLOR,
)

logger = logging.getLogger(__name__)

ToastLevel = Literal["info", "warning", "error"]


class ToastNotification(QFrame):
    """A toast notification that auto-dismisses.

    Toast notifications stack visually in the top-right corner
    of their parent widget. Each toast auto-dismisses after
    TOAST_TIMEOUT_MS milliseconds.

    Signals:
        dismissed: Emitted when this toast should be removed from the stack.
    """

    dismissed = pyqtSignal(object)  # Emits self when dismissed

    # Color mapping for toast levels
    _LEVEL_COLORS = {
        "info": INFO_COLOR,
        "warning": WARNING_COLOR,
        "error": ERROR_COLOR,
    }

    def __init__(
        self,
        message: str,
        level: ToastLevel = "info",
        timeout_ms: int | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Initialize the ToastNotification.

        Args:
            message: The message to display.
            level: Toast severity level ("info", "warning", or "error").
            timeout_ms: Auto-dismiss timeout in milliseconds.
                       Defaults to TOAST_TIMEOUT_MS from config.
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self._message = message
        self._level = level
        self._timeout_ms = timeout_ms if timeout_ms is not None else TOAST_TIMEOUT_MS

        self._setup_ui()
        self._setup_auto_dismiss()

    def _setup_ui(self) -> None:
        """Set up the toast UI layout and styling."""
        self.setObjectName("ToastNotification")
        self.setFixedWidth(TOAST_WIDTH)
        self.setMinimumHeight(TOAST_MIN_HEIGHT)

        # Get color for this level
        accent_color = self._LEVEL_COLORS.get(self._level, INFO_COLOR)

        self.setStyleSheet(f"""
            QFrame#ToastNotification {{
                background-color: {SURFACE_COLOR};
                border-left: 4px solid {accent_color};
                border-radius: 4px;
            }}
            QLabel {{
                color: {TEXT_PRIMARY};
                font-size: {FONT_SIZE_BODY}px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        self._message_label = QLabel(self._message)
        self._message_label.setWordWrap(True)
        layout.addWidget(self._message_label)

    def _setup_auto_dismiss(self) -> None:
        """Set up the auto-dismiss timer."""
        self._dismiss_timer = QTimer(self)
        self._dismiss_timer.setSingleShot(True)
        self._dismiss_timer.timeout.connect(self._on_timeout)
        self._dismiss_timer.start(self._timeout_ms)

    def _on_timeout(self) -> None:
        """Handle auto-dismiss timeout."""
        self.dismiss()

    def dismiss(self) -> None:
        """Dismiss this toast notification.

        Emits the dismissed signal and hides the widget.
        """
        self._dismiss_timer.stop()
        self.dismissed.emit(self)
        self.hide()

    def show_animated(self, x: int, y: int) -> None:
        """Show the toast with a fade-in animation.

        Args:
            x: X position for the toast.
            y: Y position for the toast.
        """
        self.move(x, y)
        self.setWindowOpacity(0.0)
        self.show()

        # Fade in animation
        self._fade_animation = QPropertyAnimation(self, b"windowOpacity")
        self._fade_animation.setDuration(ANIMATION_DURATION_NORMAL)
        self._fade_animation.setStartValue(0.0)
        self._fade_animation.setEndValue(1.0)
        self._fade_animation.setEasingCurve(QEasingCurve.OutCubic)
        self._fade_animation.start()

    @property
    def level(self) -> ToastLevel:
        """Get the toast severity level."""
        return self._level

    @property
    def message(self) -> str:
        """Get the toast message."""
        return self._message


class ToastManager:
    """Manages a stack of toast notifications.

    Toasts are displayed in the top-right corner of the parent widget
    and stack vertically. When a toast is dismissed, remaining toasts
    reposition.
    """

    def __init__(self, parent: QWidget) -> None:
        """Initialize the ToastManager.

        Args:
            parent: The parent widget for toast positioning.
        """
        self._parent = parent
        self._toasts: list[ToastNotification] = []

    def show_toast(
        self,
        message: str,
        level: ToastLevel = "info",
        timeout_ms: int | None = None,
    ) -> ToastNotification:
        """Show a new toast notification.

        Args:
            message: The message to display.
            level: Toast severity level.
            timeout_ms: Optional custom timeout.

        Returns:
            The created ToastNotification instance.
        """
        toast = ToastNotification(
            message=message,
            level=level,
            timeout_ms=timeout_ms,
            parent=self._parent,
        )
        toast.dismissed.connect(self._on_toast_dismissed)
        self._toasts.append(toast)

        self._reposition_toasts()
        x, y = self._get_toast_position(len(self._toasts) - 1)
        toast.show_animated(x, y)

        logger.debug("Toast shown: [%s] %s", level, message)
        return toast

    def _on_toast_dismissed(self, toast: ToastNotification) -> None:
        """Handle a toast being dismissed.

        Args:
            toast: The dismissed toast.
        """
        if toast in self._toasts:
            self._toasts.remove(toast)
            toast.deleteLater()
            self._reposition_toasts()

    def _reposition_toasts(self) -> None:
        """Reposition all visible toasts in the stack."""
        for i, toast in enumerate(self._toasts):
            if toast.isVisible():
                x, y = self._get_toast_position(i)
                toast.move(x, y)

    def _get_toast_position(self, index: int) -> tuple[int, int]:
        """Calculate position for a toast at the given stack index.

        Args:
            index: Index in the toast stack (0 = topmost).

        Returns:
            Tuple of (x, y) position.
        """
        parent_rect = self._parent.rect()

        # Position in top-right corner
        x = parent_rect.width() - TOAST_WIDTH - TOAST_MARGIN

        # Stack vertically with spacing
        y = TOAST_MARGIN
        for i in range(index):
            if i < len(self._toasts):
                y += self._toasts[i].height() + 8  # 8px spacing between toasts

        return x, y

    def clear_all(self) -> None:
        """Dismiss all active toasts."""
        for toast in list(self._toasts):
            toast.dismiss()
