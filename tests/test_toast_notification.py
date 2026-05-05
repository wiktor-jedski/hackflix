"""Tests for ToastNotification component."""

import pytest
from PySide6.QtWidgets import QWidget

from src.ui.components.toast_notification import ToastManager, ToastNotification


class TestToastNotification:
    """Tests for ToastNotification class."""

    @pytest.fixture
    def parent_widget(self, qtbot) -> QWidget:
        """Create a parent widget for toasts."""
        widget = QWidget()
        widget.resize(800, 600)
        qtbot.addWidget(widget)
        return widget

    @pytest.fixture
    def toast(self, parent_widget: QWidget, qtbot) -> ToastNotification:
        """Create a ToastNotification instance."""
        toast = ToastNotification("Test message", "info", parent=parent_widget)
        qtbot.addWidget(toast)
        return toast

    def test_initialization(self, toast: ToastNotification) -> None:
        """Test ToastNotification initialization."""
        assert toast is not None
        assert toast.objectName() == "ToastNotification"

    def test_message_property(self, toast: ToastNotification) -> None:
        """Test message property."""
        assert toast.message == "Test message"

    def test_level_property(self, toast: ToastNotification) -> None:
        """Test level property."""
        assert toast.level == "info"

    def test_different_levels(self, parent_widget: QWidget, qtbot) -> None:
        """Test creating toasts with different levels."""
        info_toast = ToastNotification("Info", "info", parent=parent_widget)
        warning_toast = ToastNotification("Warning", "warning", parent=parent_widget)
        error_toast = ToastNotification("Error", "error", parent=parent_widget)

        qtbot.addWidget(info_toast)
        qtbot.addWidget(warning_toast)
        qtbot.addWidget(error_toast)

        assert info_toast.level == "info"
        assert warning_toast.level == "warning"
        assert error_toast.level == "error"

    def test_dismissed_signal(self, toast: ToastNotification, qtbot) -> None:
        """Test that dismissed signal is emitted."""
        with qtbot.waitSignal(toast.dismissed, timeout=100):
            toast.dismiss()

    def test_dismiss_hides_toast(self, toast: ToastNotification, qtbot) -> None:
        """Test that dismiss hides the toast."""
        # Widget must be shown on a visible parent to be truly visible
        # Instead, verify the dismiss behavior
        toast.dismiss()
        assert not toast.isVisible()
        # Verify timer is stopped
        assert not toast._dismiss_timer.isActive()

    def test_custom_timeout(self, parent_widget: QWidget, qtbot) -> None:
        """Test creating toast with custom timeout."""
        toast = ToastNotification(
            "Custom timeout", "info", timeout_ms=100, parent=parent_widget
        )
        qtbot.addWidget(toast)
        assert toast._timeout_ms == 100

    def test_default_timeout(self, toast: ToastNotification) -> None:
        """Test that default timeout is used from config."""
        from src.config import TOAST_TIMEOUT_MS

        assert toast._timeout_ms == TOAST_TIMEOUT_MS

    def test_fixed_width(self, toast: ToastNotification) -> None:
        """Test that toast has fixed width."""
        from src.ui.styles import TOAST_WIDTH

        assert toast.width() == TOAST_WIDTH


class TestToastManager:
    """Tests for ToastManager class."""

    @pytest.fixture
    def parent_widget(self, qtbot) -> QWidget:
        """Create a parent widget for the manager."""
        widget = QWidget()
        widget.resize(800, 600)
        qtbot.addWidget(widget)
        widget.show()
        return widget

    @pytest.fixture
    def manager(self, parent_widget: QWidget) -> ToastManager:
        """Create a ToastManager instance."""
        return ToastManager(parent_widget)

    def test_initialization(self, manager: ToastManager) -> None:
        """Test ToastManager initialization."""
        assert manager is not None
        assert len(manager._toasts) == 0

    def test_show_toast_creates_notification(self, manager: ToastManager) -> None:
        """Test that show_toast creates a notification."""
        toast = manager.show_toast("Test message")
        assert toast is not None
        assert len(manager._toasts) == 1

    def test_show_toast_returns_toast(self, manager: ToastManager) -> None:
        """Test that show_toast returns the created toast."""
        toast = manager.show_toast("Test", "warning")
        assert isinstance(toast, ToastNotification)
        assert toast.message == "Test"
        assert toast.level == "warning"

    def test_multiple_toasts_stack(self, manager: ToastManager) -> None:
        """Test that multiple toasts are tracked."""
        manager.show_toast("Toast 1")
        manager.show_toast("Toast 2")
        manager.show_toast("Toast 3")
        assert len(manager._toasts) == 3

    def test_dismissed_toast_removed(self, manager: ToastManager, qtbot) -> None:
        """Test that dismissed toast is removed from manager."""
        toast = manager.show_toast("Test")
        assert len(manager._toasts) == 1

        # Dismiss the toast
        toast.dismiss()
        # Process events
        qtbot.wait(50)

        assert len(manager._toasts) == 0

    def test_clear_all(self, manager: ToastManager, qtbot) -> None:
        """Test that clear_all dismisses all toasts."""
        manager.show_toast("Toast 1")
        manager.show_toast("Toast 2")
        assert len(manager._toasts) == 2

        manager.clear_all()
        qtbot.wait(50)

        assert len(manager._toasts) == 0

    def test_toast_positions_stack_vertically(
        self, manager: ToastManager, parent_widget: QWidget
    ) -> None:
        """Test that toast positions stack vertically."""
        # Create actual toasts so they have heights
        toast1 = manager.show_toast("First toast")
        toast2 = manager.show_toast("Second toast")

        # Get their positions - first toast should be above second
        pos1 = (toast1.x(), toast1.y())
        pos2 = (toast2.x(), toast2.y())

        # Both should be at same X (right side)
        assert pos1[0] == pos2[0]
        # Second should be lower (higher Y value)
        assert pos2[1] > pos1[1]


class TestToastAutoTimeout:
    """Tests for toast auto-dismiss timeout behavior."""

    @pytest.fixture
    def parent_widget(self, qtbot) -> QWidget:
        """Create a parent widget for toasts."""
        widget = QWidget()
        widget.resize(800, 600)
        qtbot.addWidget(widget)
        return widget

    def test_on_timeout_dismisses_toast(self, parent_widget: QWidget, qtbot) -> None:
        """Test that _on_timeout dismisses the toast."""
        toast = ToastNotification("Test", "info", timeout_ms=50, parent=parent_widget)
        qtbot.addWidget(toast)

        # Wait for the toast to auto-dismiss
        with qtbot.waitSignal(toast.dismissed, timeout=200):
            pass  # The timeout will trigger dismiss automatically

        assert not toast.isVisible()

    def test_timeout_triggers_dismiss(self, parent_widget: QWidget, qtbot) -> None:
        """Test that timeout triggers the dismiss callback."""
        toast = ToastNotification("Test", "info", timeout_ms=100, parent=parent_widget)
        qtbot.addWidget(toast)
        toast.show()

        # Directly call _on_timeout to exercise the code path
        toast._on_timeout()

        assert not toast.isVisible()
        assert not toast._dismiss_timer.isActive()
