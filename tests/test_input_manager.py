"""Tests for InputManager."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QWidget

from src.ui.enums import Action
from src.ui.input_manager import InputManager


class TestInputManager:
    """Tests for InputManager class."""

    @pytest.fixture
    def input_manager(self, qtbot) -> InputManager:
        """Create an InputManager instance."""
        manager = InputManager()
        return manager

    @pytest.fixture
    def widget(self, qtbot) -> QWidget:
        """Create a test widget."""
        widget = QWidget()
        qtbot.addWidget(widget)
        return widget

    def test_initialization(self, input_manager: InputManager) -> None:
        """Test InputManager initialization."""
        assert input_manager is not None
        assert input_manager._last_debounced_key is None

    def test_action_triggered_signal_exists(self, input_manager: InputManager) -> None:
        """Test that action_triggered signal exists."""
        assert hasattr(input_manager, "action_triggered")

    def test_map_navigation_keys(self, input_manager: InputManager) -> None:
        """Test mapping of navigation keys to actions."""
        # Create key events
        up_event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Up, Qt.NoModifier)
        down_event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Down, Qt.NoModifier)
        left_event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Left, Qt.NoModifier)
        right_event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Right, Qt.NoModifier)

        assert input_manager._map_key_to_action(up_event) == Action.NAVIGATE_UP
        assert input_manager._map_key_to_action(down_event) == Action.NAVIGATE_DOWN
        assert input_manager._map_key_to_action(left_event) == Action.NAVIGATE_LEFT
        assert input_manager._map_key_to_action(right_event) == Action.NAVIGATE_RIGHT

    def test_map_action_keys(self, input_manager: InputManager) -> None:
        """Test mapping of action keys."""
        tab_event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Tab, Qt.NoModifier)
        s_event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_S, Qt.NoModifier)
        x_event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_X, Qt.NoModifier)
        d_event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_D, Qt.NoModifier)
        p_event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_P, Qt.NoModifier)

        assert input_manager._map_key_to_action(tab_event) == Action.SWITCH_TAB
        assert input_manager._map_key_to_action(s_event) == Action.SEARCH
        assert input_manager._map_key_to_action(x_event) == Action.CLEAR_FILTER
        assert input_manager._map_key_to_action(d_event) == Action.DELETE
        assert input_manager._map_key_to_action(p_event) == Action.SYNC

    def test_map_universal_keys(self, input_manager: InputManager) -> None:
        """Test mapping of universal keys."""
        enter_event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Return, Qt.NoModifier)
        escape_event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier)

        assert input_manager._map_key_to_action(enter_event) == Action.CONFIRM
        assert input_manager._map_key_to_action(escape_event) == Action.CANCEL

    def test_map_ctrl_q_quit(self, input_manager: InputManager) -> None:
        """Test mapping of Ctrl+Q to quit action."""
        ctrl_q_event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Q, Qt.ControlModifier)
        q_event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Q, Qt.NoModifier)

        assert input_manager._map_key_to_action(ctrl_q_event) == Action.QUIT
        assert input_manager._map_key_to_action(q_event) == Action.NONE

    def test_map_player_keys(self, input_manager: InputManager) -> None:
        """Test mapping of player control keys."""
        space_event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Space, Qt.NoModifier)
        m_event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_M, Qt.NoModifier)
        l_event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_L, Qt.NoModifier)

        assert input_manager._map_key_to_action(space_event) == Action.TOGGLE_PAUSE
        assert input_manager._map_key_to_action(m_event) == Action.TOGGLE_MUTE
        assert input_manager._map_key_to_action(l_event) == Action.CYCLE_AUDIO
        v_event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_V, Qt.NoModifier)
        assert input_manager._map_key_to_action(v_event) == Action.CYCLE_SUBTITLE

    def test_unmapped_key_returns_none(self, input_manager: InputManager) -> None:
        """Test that unmapped keys return Action.NONE."""
        # Random unmapped key
        f1_event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_F1, Qt.NoModifier)
        assert input_manager._map_key_to_action(f1_event) == Action.NONE

    def test_debounce_allows_first_key(self, input_manager: InputManager) -> None:
        """Test that debounce allows the first key press."""
        result = input_manager._check_debounce(Qt.Key_S)
        assert result is True

    def test_debounce_blocks_rapid_same_key(self, input_manager: InputManager) -> None:
        """Test that debounce blocks rapid presses of the same key."""
        # First press
        input_manager._check_debounce(Qt.Key_S)
        # Immediate second press should be blocked
        result = input_manager._check_debounce(Qt.Key_S)
        assert result is False

    def test_debounce_allows_different_key(self, input_manager: InputManager) -> None:
        """Test that debounce allows different keys immediately."""
        input_manager._check_debounce(Qt.Key_S)
        result = input_manager._check_debounce(Qt.Key_D)
        assert result is True

    def test_reset_debounce(self, input_manager: InputManager) -> None:
        """Test that reset_debounce clears debounce state."""
        input_manager._check_debounce(Qt.Key_S)
        input_manager.reset_debounce()

        # After reset, same key should be allowed
        result = input_manager._check_debounce(Qt.Key_S)
        assert result is True

    def test_build_context_empty_for_non_widget(
        self, input_manager: InputManager
    ) -> None:
        """Test that build_context returns empty dict for non-widget."""
        from PySide6.QtCore import QObject

        obj = QObject()
        context = input_manager._build_context(obj)
        assert isinstance(context, dict)

    def test_build_context_for_widget(
        self, input_manager: InputManager, widget: QWidget
    ) -> None:
        """Test that build_context includes widget info."""
        widget.setObjectName("TestWidget")
        context = input_manager._build_context(widget)
        assert isinstance(context, dict)

    def test_event_filter_handles_key_press(
        self, input_manager: InputManager, widget: QWidget, qtbot
    ) -> None:
        """Test that event filter handles key press events."""
        signals_received = []

        def capture_signal(action, context):
            signals_received.append((action, context))

        input_manager.action_triggered.connect(capture_signal)

        # Simulate key press
        event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Up, Qt.NoModifier)
        result = input_manager.eventFilter(widget, event)

        assert result is True  # Event was handled
        assert len(signals_received) == 1
        assert signals_received[0][0] == Action.NAVIGATE_UP

    def test_event_filter_ignores_non_key_events(
        self, input_manager: InputManager, widget: QWidget
    ) -> None:
        """Test that event filter ignores non-key events."""
        from PySide6.QtCore import QEvent

        event = QEvent(QEvent.None_)
        result = input_manager.eventFilter(widget, event)
        assert result is False

    def test_event_filter_ignores_unmapped_keys(
        self, input_manager: InputManager, widget: QWidget
    ) -> None:
        """Test that event filter ignores unmapped keys."""
        signals_received = []
        input_manager.action_triggered.connect(lambda a, c: signals_received.append(a))

        event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_F1, Qt.NoModifier)
        result = input_manager.eventFilter(widget, event)

        assert result is False
        assert len(signals_received) == 0

    def test_navigation_keys_allow_auto_repeat(
        self, input_manager: InputManager, widget: QWidget, qtbot
    ) -> None:
        """Test that navigation keys allow auto-repeat."""
        signals_received = []
        input_manager.action_triggered.connect(lambda a, c: signals_received.append(a))

        # First key press
        event1 = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Up, Qt.NoModifier)
        input_manager.eventFilter(widget, event1)

        # Simulated auto-repeat (isAutoRepeat would be True in real event)
        # Since we can't easily mock isAutoRepeat, we test that navigation
        # keys are in REPEAT_ALLOWED_KEYS
        assert Qt.Key_Up in input_manager._REPEAT_ALLOWED_KEYS
        assert Qt.Key_Down in input_manager._REPEAT_ALLOWED_KEYS
        assert Qt.Key_Left in input_manager._REPEAT_ALLOWED_KEYS
        assert Qt.Key_Right in input_manager._REPEAT_ALLOWED_KEYS

    def test_action_keys_in_debounced_set(self, input_manager: InputManager) -> None:
        """Test that action keys are in the debounced set."""
        debounced = input_manager._DEBOUNCED_KEYS
        assert Qt.Key_Tab in debounced
        assert Qt.Key_S in debounced
        assert Qt.Key_X in debounced
        assert Qt.Key_D in debounced
        assert Qt.Key_P in debounced
        assert Qt.Key_Return in debounced
        assert Qt.Key_Escape in debounced
        assert Qt.Key_Q in debounced

    def test_event_filter_ignores_key_release(
        self, input_manager: InputManager, widget: QWidget
    ) -> None:
        """Test that event filter ignores key release events."""
        event = QKeyEvent(QKeyEvent.KeyRelease, Qt.Key_Up, Qt.NoModifier)
        result = input_manager.eventFilter(widget, event)
        assert result is False

    def test_debounced_key_blocks_auto_repeat(
        self, input_manager: InputManager, widget: QWidget, qtbot
    ) -> None:
        """Test that auto-repeat is blocked for debounced keys."""
        signals_received = []
        input_manager.action_triggered.connect(lambda a, c: signals_received.append(a))

        # First press - should emit
        event1 = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Return, Qt.NoModifier)
        input_manager.eventFilter(widget, event1)
        assert len(signals_received) == 1

        # Simulate auto-repeat by creating event with isAutoRepeat
        # We need to create a mock event since we can't easily set autorepeat
        from unittest.mock import MagicMock, patch

        auto_repeat_event = MagicMock(spec=QKeyEvent)
        auto_repeat_event.type.return_value = QKeyEvent.KeyPress
        auto_repeat_event.key.return_value = Qt.Key_Return
        auto_repeat_event.modifiers.return_value = Qt.NoModifier
        auto_repeat_event.isAutoRepeat.return_value = True

        # Patch isinstance to return True for QKeyEvent
        with patch(
            "src.ui.input_manager.isinstance",
            side_effect=lambda obj, cls: True
            if cls == QKeyEvent
            else isinstance(obj, cls),
        ):
            result = input_manager.eventFilter(widget, auto_repeat_event)

        assert result is True

        # Auto-repeat should be blocked (return True to consume event)
        # Note: Due to the nature of mocking, we primarily test that debounced
        # keys are in the set and auto-repeat flag is checked

    def test_debounce_blocks_rapid_press(
        self, input_manager: InputManager, widget: QWidget, qtbot
    ) -> None:
        """Test that debounce blocks rapid presses of debounced keys."""
        signals_received = []
        input_manager.action_triggered.connect(lambda a, c: signals_received.append(a))

        # First press of a debounced key
        event1 = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Tab, Qt.NoModifier)
        input_manager.eventFilter(widget, event1)

        # Immediate second press should be blocked by debounce
        event2 = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Tab, Qt.NoModifier)
        result = input_manager.eventFilter(widget, event2)

        # Only one signal should have been emitted
        assert len(signals_received) == 1
        # Second event was consumed (handled)
        assert result is True

    def test_build_context_with_focused_widget(
        self, input_manager: InputManager, qtbot
    ) -> None:
        """Test build_context includes focused widget info."""
        from PySide6.QtWidgets import QLineEdit, QVBoxLayout

        # Create a parent widget with a focusable child
        parent = QWidget()
        layout = QVBoxLayout(parent)
        line_edit = QLineEdit()
        line_edit.setObjectName("TestLineEdit")
        layout.addWidget(line_edit)
        qtbot.addWidget(parent)

        parent.show()
        line_edit.setFocus()

        context = input_manager._build_context(parent)
        assert "focused_widget" in context
        assert context["focused_widget"] == "TestLineEdit"

    def test_build_context_focused_widget_no_name(
        self, input_manager: InputManager, qtbot
    ) -> None:
        """Test build_context uses class name when widget has no object name."""
        from PySide6.QtWidgets import QLineEdit, QVBoxLayout

        parent = QWidget()
        layout = QVBoxLayout(parent)
        line_edit = QLineEdit()
        # Don't set object name
        layout.addWidget(line_edit)
        qtbot.addWidget(parent)

        parent.show()
        line_edit.setFocus()

        context = input_manager._build_context(parent)
        assert "focused_widget" in context
        assert context["focused_widget"] == "QLineEdit"
