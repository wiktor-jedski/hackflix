"""Main window for Hackflix.

This module provides the MainWindow class that serves as the
primary container for all UI components.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QCloseEvent, QResizeEvent, QShowEvent
from PyQt5.QtWidgets import QMainWindow, QVBoxLayout, QWidget, QApplication

from src.ui.components.confirm_dialog import ConfirmDialog
from src.ui.components.library_view import LibraryView
from src.ui.components.player_view import PlayerView
from src.ui.components.search_overlay import SearchOverlay, SearchOverlayBackground
from src.ui.components.status_bar import StatusBar
from src.ui.components.toast_notification import ToastLevel, ToastManager
from src.ui.input_manager import InputManager
from src.ui.styles import BACKGROUND_COLOR, get_stylesheet

if TYPE_CHECKING:
    from src.controllers.app_controller import AppController

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Main application window.

    The main window contains:
    - LibraryView (center): The main content area
    - StatusBar (bottom): Connection, sync, and storage status
    - Overlays: ToastNotification stack, SearchOverlay, ConfirmDialog

    The InputManager is installed as an event filter to handle
    keyboard navigation.
    """

    def __init__(self) -> None:
        """Initialize the MainWindow."""
        super().__init__()
        self._controller: "AppController | None" = None
        self._setup_ui()
        self._setup_input_manager()

    def _setup_ui(self) -> None:
        """Set up the main window UI layout."""
        self.setWindowTitle("Hackflix")
        self.setMinimumSize(800, 600)
        self.setStyleSheet(get_stylesheet())

        # Central widget
        central = QWidget()
        central.setObjectName("CentralWidget")
        central.setStyleSheet(f"background-color: {BACKGROUND_COLOR};")
        self.setCentralWidget(central)

        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Library view (main content)
        self._library_view = LibraryView()
        layout.addWidget(self._library_view)

        # Player view (hidden by default, overlays library)
        self._player_view = PlayerView(central)
        self._player_view.hide()

        # Status bar
        self._status_bar = StatusBar()
        layout.addWidget(self._status_bar)

        # Search overlay (hidden by default)
        self._search_background = SearchOverlayBackground(central)
        self._search_overlay = SearchOverlay(central)
        self._search_background.clicked.connect(self._on_search_cancelled)

        # Toast manager
        self._toast_manager = ToastManager(central)

    def _setup_input_manager(self) -> None:
        """Set up the input manager as an event filter."""
        self._input_manager = InputManager(self)
        # Install on the application to catch all events globally
        # This will be moved to bind_controller when QApplication is available
        logger.debug("Input manager created")

    def bind_controller(self, controller: "AppController") -> None:
        """Bind the controller to this window.

        Args:
            controller: The AppController instance.
        """
        self._controller = controller

        # Connect input manager to controller
        self._input_manager.action_triggered.connect(controller.handle_action)

        # Install input manager as global event filter now that QApplication exists
        app = QApplication.instance()
        if app:
            app.installEventFilter(self._input_manager)

        # Also install on library view since it has focus
        self._library_view.installEventFilter(self._input_manager)

        logger.debug("Input manager installed as global and library view event filter")

        # Connect library view signals
        self._library_view.item_activated.connect(controller.on_item_activated)
        self._library_view.selection_changed.connect(controller.on_selection_changed)
        self._library_view.tab_changed.connect(controller.on_tab_changed)

        # Connect search overlay signals
        self._search_overlay.search_committed.connect(controller.on_search_committed)
        self._search_overlay.search_cancelled.connect(controller.on_search_cancelled)

        logger.debug("Controller bound to MainWindow")

    @property
    def library_view(self) -> LibraryView:
        """Get the library view component."""
        return self._library_view

    @property
    def status_bar(self) -> StatusBar:
        """Get the status bar component."""
        return self._status_bar

    @property
    def player_view(self) -> PlayerView:
        """Get the player view component."""
        return self._player_view

    @property
    def input_manager(self) -> InputManager:
        """Get the input manager."""
        return self._input_manager

    def show_player(self) -> None:
        """Show the player view in fullscreen mode."""
        # Hide library and status bar
        self._library_view.hide()
        self._status_bar.hide()

        # Position and show player view to fill the central widget
        central = self.centralWidget()
        if central:
            self._player_view.setGeometry(central.rect())
        self._player_view.enter_fullscreen()
        self._player_view.show()
        self._player_view.raise_()
        self._player_view.set_focus()

        logger.debug("Player view shown")

    def hide_player(self) -> None:
        """Hide the player view and return to library."""
        # Exit fullscreen mode on player view
        self._player_view.exit_fullscreen()
        self._player_view.hide()

        # Show library and status bar
        self._library_view.show()
        self._status_bar.show()
        self._library_view.set_focus()

        logger.debug("Player view hidden")

    def get_player_frame_id(self) -> int:
        """Get the video frame window ID for VLC binding.

        Returns:
            The winId of the player view's video frame.
        """
        return self._player_view.get_video_frame_id()

    def show_search(self, current_filter: str = "") -> None:
        """Show the search overlay.

        Args:
            current_filter: Current search filter to pre-populate.
        """
        # Disable global input manager to allow raw text input in the search field
        app = QApplication.instance()
        if app:
            app.removeEventFilter(self._input_manager)
        self._library_view.removeEventFilter(self._input_manager)

        # Show background
        self._search_background.show_fullscreen()

        # Show and position search overlay
        self._search_overlay.show_search(current_filter)
        self._search_overlay.raise_()

        logger.debug("Search overlay shown and InputManager suspended")

    def hide_search(self) -> None:
        """Hide the search overlay."""
        self._search_overlay.hide()
        self._search_background.hide()

        # Defer re-enabling input manager to avoid the Enter key that closed
        # the search overlay from also triggering an action in LibraryView
        QTimer.singleShot(0, self._restore_input_manager)

        logger.debug("Search overlay hidden, InputManager restore scheduled")

    def _restore_input_manager(self) -> None:
        """Restore the input manager after search overlay is hidden."""
        app = QApplication.instance()
        if app:
            app.installEventFilter(self._input_manager)
        self._library_view.installEventFilter(self._input_manager)
        self._library_view.set_focus()
        logger.debug("InputManager restored")

    def _on_search_cancelled(self) -> None:
        """Handle search cancelled via background click."""
        self._search_overlay.search_cancelled.emit()
        self.hide_search()

    def show_confirm(self, title: str, message: str) -> bool:
        """Show a confirmation dialog.

        Args:
            title: Dialog title.
            message: Dialog message.

        Returns:
            True if confirmed, False if cancelled.
        """
        # Suspend input manager to allow dialog to receive key events
        app = QApplication.instance()
        if app:
            app.removeEventFilter(self._input_manager)
        self._library_view.removeEventFilter(self._input_manager)

        try:
            return ConfirmDialog.confirm(title, message, self)
        finally:
            # Restore input manager after dialog closes
            if app:
                app.installEventFilter(self._input_manager)
            self._library_view.installEventFilter(self._input_manager)

    def show_toast(
        self,
        message: str,
        level: ToastLevel = "info",
        timeout_ms: int | None = None,
    ) -> None:
        """Show a toast notification.

        Args:
            message: The message to display.
            level: Toast severity level.
            timeout_ms: Optional custom timeout.
        """
        self._toast_manager.show_toast(message, level, timeout_ms)

    def clear_toasts(self) -> None:
        """Clear all active toast notifications."""
        self._toast_manager.clear_all()

    def set_connection_status(self, online: bool) -> None:
        """Update the connection status display.

        Args:
            online: True if online, False if offline.
        """
        self._status_bar.set_connection_status(online)

    def set_sync_status(self, message: str) -> None:
        """Update the sync status display.

        Args:
            message: Status message to display.
        """
        self._status_bar.set_sync_status(message)

    def set_storage_usage(self, usage: str) -> None:
        """Update the storage usage display.

        Args:
            usage: Storage usage string.
        """
        self._status_bar.set_storage_usage(usage)

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Handle window resize.

        Args:
            event: The resize event.
        """
        super().resizeEvent(event)

        central = self.centralWidget()

        # Resize player view if visible
        if self._player_view.isVisible() and central:
            self._player_view.setGeometry(central.rect())

        # Reposition search overlay
        if self._search_overlay.isVisible():
            self._search_overlay._center_in_parent()

        # Resize search background
        if self._search_background.isVisible() and central:
            self._search_background.setGeometry(central.rect())

    def showEvent(self, event: QShowEvent) -> None:
        """Handle window show event.

        Args:
            event: The show event.
        """
        super().showEvent(event)
        # Force fullscreen mode per set-top box requirement
        if not self.isFullScreen():
            self.showFullScreen()
        self._library_view.set_focus()

    def closeEvent(self, event: QCloseEvent) -> None:
        """Handle window close event.

        Args:
            event: The close event.
        """
        logger.info("MainWindow closing")
        if self._controller:
            self._controller.shutdown()
        super().closeEvent(event)
