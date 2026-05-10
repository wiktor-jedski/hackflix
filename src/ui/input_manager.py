"""Input manager for Hackflix.

This module provides the InputManager class that intercepts keyboard
events and maps them to semantic application actions.
"""

import logging
from typing import Any, Optional

from PySide6.QtCore import QElapsedTimer, QEvent, QObject, Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QWidget

from src.ui.enums import Action
from src.ui.styles import DEBOUNCE_MS

logger = logging.getLogger(__name__)


class InputManager(QObject):
    """Intercepts keyboard events and emits semantic actions.

    The InputManager is installed as an event filter on the main window.
    It maps raw Qt key events to semantic Action enums and applies
    debouncing to prevent accidental double-triggers on action keys.

    Navigation keys (arrows) allow key repeat for fast scrolling.
    Action keys (Enter, Esc, S, D, P, X, Tab) are debounced.

    Signals:
        action_triggered: Emitted with (Action, context_dict) when
            a key is pressed and debounce allows it.
    """

    action_triggered = Signal(Action, dict)

    # Keys that should be debounced (prevent accidental double-triggers)
    _DEBOUNCED_KEYS = {
        Qt.Key_Tab,  # type: ignore[attr-defined]
        Qt.Key_S,  # type: ignore[attr-defined]
        Qt.Key_X,  # type: ignore[attr-defined]
        Qt.Key_D,  # type: ignore[attr-defined]
        Qt.Key_P,  # type: ignore[attr-defined]
        Qt.Key_Return,  # type: ignore[attr-defined]
        Qt.Key_Enter,  # type: ignore[attr-defined]
        Qt.Key_Escape,  # type: ignore[attr-defined]
        Qt.Key_Q,  # type: ignore[attr-defined]  # For Ctrl+Q
        Qt.Key_Space,  # type: ignore[attr-defined]
        Qt.Key_M,  # type: ignore[attr-defined]
        Qt.Key_L,  # type: ignore[attr-defined]
        Qt.Key_V,  # type: ignore[attr-defined]
    }

    # Keys that allow auto-repeat for fast scrolling
    _REPEAT_ALLOWED_KEYS = {
        Qt.Key_Up,  # type: ignore[attr-defined]
        Qt.Key_Down,  # type: ignore[attr-defined]
        Qt.Key_Left,  # type: ignore[attr-defined]
        Qt.Key_Right,  # type: ignore[attr-defined]
    }

    def __init__(self, parent: QObject | None = None) -> None:
        """Initialize the InputManager.

        Args:
            parent: Optional parent QObject.
        """
        super().__init__(parent)
        self._debounce_timer = QElapsedTimer()
        self._debounce_timer.start()
        self._last_debounced_key: int | None = None

    def eventFilter(
        self, watched: Optional[QObject], event: Optional[QEvent]
    ) -> bool:
        """Filter and process keyboard events.

        This method is called for all events on the watched object.
        Only KeyPress events are processed; others are passed through.

        Args:
            watched: The object being watched (typically MainWindow).
            event: The Qt event to filter.

        Returns:
            True if the event was handled and should not propagate.
            False to allow normal event processing.
        """
        if event is None or not isinstance(event, QKeyEvent):
            return False

        if event.type() != QEvent.KeyPress:  # type: ignore[attr-defined]
            return False

        action = self._map_key_to_action(event)
        if action == Action.NONE:
            return False

        key = event.key()

        # Check if this is a debounced key
        if key in self._DEBOUNCED_KEYS:
            # Block auto-repeat for debounced keys
            if event.isAutoRepeat():
                return True

            # Check debounce timing
            if not self._check_debounce(key):
                return True

        # Navigation keys: allow auto-repeat for fast scrolling
        elif key in self._REPEAT_ALLOWED_KEYS:
            pass  # Always allow

        # Build context dictionary
        context = self._build_context(watched)

        # Emit the action
        logger.debug("Action triggered: %s, context: %s", action.name, context)
        self.action_triggered.emit(action, context)

        return True

    def _map_key_to_action(self, event: QKeyEvent) -> Action:
        """Map a Qt key event to a semantic Action.

        Args:
            event: The Qt key event.

        Returns:
            The corresponding Action enum value, or Action.NONE if not mapped.
        """
        key = event.key()
        modifiers = event.modifiers()

        # Check for Ctrl+Q (quit)
        if key == Qt.Key_Q and modifiers & Qt.ControlModifier:  # type: ignore[attr-defined]
            return Action.QUIT

        # Navigation keys
        if key == Qt.Key_Up:  # type: ignore[attr-defined]
            return Action.NAVIGATE_UP
        if key == Qt.Key_Down:  # type: ignore[attr-defined]
            return Action.NAVIGATE_DOWN
        if key == Qt.Key_Left:  # type: ignore[attr-defined]
            return Action.NAVIGATE_LEFT
        if key == Qt.Key_Right:  # type: ignore[attr-defined]
            return Action.NAVIGATE_RIGHT

        # Tab key
        if key == Qt.Key_Tab:  # type: ignore[attr-defined]
            return Action.SWITCH_TAB

        # Action keys
        if key == Qt.Key_S:  # type: ignore[attr-defined]
            return Action.SEARCH
        if key == Qt.Key_X:  # type: ignore[attr-defined]
            return Action.CLEAR_FILTER
        if key == Qt.Key_D:  # type: ignore[attr-defined]
            return Action.DELETE
        if key == Qt.Key_P:  # type: ignore[attr-defined]
            return Action.SYNC

        # Universal keys
        if key in (Qt.Key_Return, Qt.Key_Enter):  # type: ignore[attr-defined]
            return Action.CONFIRM
        if key == Qt.Key_Escape:  # type: ignore[attr-defined]
            return Action.CANCEL

        # Player keys (Phase 4)
        if key == Qt.Key_Space:  # type: ignore[attr-defined]
            return Action.TOGGLE_PAUSE
        if key == Qt.Key_M:  # type: ignore[attr-defined]
            return Action.TOGGLE_MUTE
        if key == Qt.Key_L:  # type: ignore[attr-defined]
            return Action.CYCLE_AUDIO
        if key == Qt.Key_V:  # type: ignore[attr-defined]
            return Action.CYCLE_SUBTITLE
        return Action.NONE

    def _check_debounce(self, key: int) -> bool:
        """Check if a debounced key press should be allowed.

        Args:
            key: The Qt key code.

        Returns:
            True if the key press should be allowed (enough time has passed).
            False if the key should be blocked (too soon after last press).
        """
        elapsed = self._debounce_timer.elapsed()

        # Allow if different key or enough time has passed
        if self._last_debounced_key != key or elapsed >= DEBOUNCE_MS:
            self._last_debounced_key = key
            self._debounce_timer.restart()
            return True

        return False

    def _build_context(self, watched: QObject | None) -> dict[str, Any]:
        """Build context dictionary for the action signal.

        Args:
            watched: The watched object (typically MainWindow).

        Returns:
            Dictionary with context information.
        """
        context: dict[str, Any] = {}

        # Get focused widget if watched is a QWidget
        if watched is not None and isinstance(watched, QWidget):
            focused = watched.focusWidget()
            if focused is not None:
                context["focused_widget"] = (
                    focused.objectName() or type(focused).__name__
                )

        return context

    def reset_debounce(self) -> None:
        """Reset the debounce timer.

        Call this when state changes to allow immediate key response.
        """
        self._last_debounced_key = None
        self._debounce_timer.restart()
