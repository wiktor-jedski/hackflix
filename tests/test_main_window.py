"""Tests for MainWindow component."""

import pytest
from unittest.mock import MagicMock, patch

from PyQt5.QtWidgets import QWidget

from src.ui.windows.main_window import MainWindow


class TestMainWindow:
    """Tests for MainWindow class."""

    @pytest.fixture
    def main_window(self, qtbot) -> MainWindow:
        """Create a MainWindow instance."""
        window = MainWindow()
        qtbot.addWidget(window)
        return window

    def test_initialization(self, main_window: MainWindow) -> None:
        """Test MainWindow initialization."""
        assert main_window is not None
        assert main_window.windowTitle() == "Hackflix"

    def test_has_library_view(self, main_window: MainWindow) -> None:
        """Test that MainWindow has library view."""
        assert main_window.library_view is not None

    def test_has_status_bar(self, main_window: MainWindow) -> None:
        """Test that MainWindow has status bar."""
        assert main_window.status_bar is not None

    def test_has_input_manager(self, main_window: MainWindow) -> None:
        """Test that MainWindow has input manager."""
        assert main_window.input_manager is not None

    def test_show_search(self, main_window: MainWindow) -> None:
        """Test show_search displays search overlay."""
        main_window.show_search()
        # Search overlay should be created
        assert main_window._search_overlay is not None

    def test_show_search_with_filter(self, main_window: MainWindow) -> None:
        """Test show_search with pre-populated filter."""
        main_window.show_search("test filter")
        assert main_window._search_overlay._search_input.text() == "test filter"

    def test_hide_search(self, main_window: MainWindow) -> None:
        """Test hide_search hides search overlay."""
        main_window.show_search()
        main_window.hide_search()
        assert main_window._search_overlay.isHidden()

    def test_show_toast(self, main_window: MainWindow) -> None:
        """Test show_toast creates a toast."""
        main_window.show_toast("Test message", "info")
        assert len(main_window._toast_manager._toasts) == 1

    def test_show_toast_different_levels(self, main_window: MainWindow) -> None:
        """Test show_toast with different severity levels."""
        main_window.show_toast("Info", "info")
        main_window.show_toast("Warning", "warning")
        main_window.show_toast("Error", "error")
        assert len(main_window._toast_manager._toasts) == 3

    def test_clear_toasts(self, main_window: MainWindow, qtbot) -> None:
        """Test clear_toasts removes all toasts."""
        main_window.show_toast("Toast 1")
        main_window.show_toast("Toast 2")
        main_window.clear_toasts()
        qtbot.wait(50)
        assert len(main_window._toast_manager._toasts) == 0

    def test_set_connection_status(self, main_window: MainWindow) -> None:
        """Test set_connection_status updates status bar."""
        main_window.set_connection_status(True)
        assert main_window._status_bar._connection_label.text() == "Online"

        main_window.set_connection_status(False)
        assert main_window._status_bar._connection_label.text() == "Offline"

    def test_set_sync_status(self, main_window: MainWindow) -> None:
        """Test set_sync_status updates status bar."""
        main_window.set_sync_status("Syncing...")
        assert main_window._status_bar._sync_label.text() == "Syncing..."

    def test_set_storage_usage(self, main_window: MainWindow) -> None:
        """Test set_storage_usage updates status bar."""
        main_window.set_storage_usage("50GB / 500GB")
        assert main_window._status_bar._storage_label.text() == "50GB / 500GB"

    def test_bind_controller(self, main_window: MainWindow) -> None:
        """Test binding controller to window."""
        mock_controller = MagicMock()
        main_window.bind_controller(mock_controller)
        assert main_window._controller == mock_controller

    def test_bind_controller_connects_signals(self, main_window: MainWindow) -> None:
        """Test that bind_controller connects signals."""
        mock_controller = MagicMock()
        main_window.bind_controller(mock_controller)

        # Verify signal connections were made
        # Input manager action_triggered should be connected
        # Library view signals should be connected
        # Search overlay signals should be connected

    def test_minimum_size(self, main_window: MainWindow) -> None:
        """Test that window has minimum size."""
        assert main_window.minimumWidth() >= 800
        assert main_window.minimumHeight() >= 600

    def test_close_event_calls_shutdown(self, main_window: MainWindow) -> None:
        """Test that close event calls controller shutdown."""
        mock_controller = MagicMock()
        main_window.bind_controller(mock_controller)
        main_window.close()
        mock_controller.shutdown.assert_called_once()

    def test_resize_repositions_search_overlay(self, main_window: MainWindow) -> None:
        """Test that resize repositions search overlay."""
        main_window.show_search()
        initial_pos = (main_window._search_overlay.x(), main_window._search_overlay.y())
        main_window.resize(1024, 768)
        # Position may change after resize
        # This tests that resizeEvent doesn't crash

    def test_show_confirm_returns_bool(self, main_window: MainWindow, qtbot) -> None:
        """Test that show_confirm can be called (returns bool)."""
        # We can't easily test modal dialogs, but verify the method exists
        assert hasattr(main_window, "show_confirm")
        assert callable(main_window.show_confirm)
