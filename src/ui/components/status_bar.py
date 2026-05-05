"""Status bar component for Hackflix.

This module provides the StatusBar widget that displays connection status,
sync information, and storage usage at the bottom of the main window.
"""

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget

from src.ui.styles import (
    ERROR_COLOR,
    FONT_SIZE_SMALL,
    STATUS_BAR_HEIGHT,
    SUCCESS_COLOR,
    SURFACE_COLOR,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
)


class StatusBar(QFrame):
    """Bottom status bar showing connection, sync, and storage info.

    The status bar has three sections:
    - Left: Connection status (Online/Offline indicator)
    - Center: Sync status (Last sync time or "Syncing...")
    - Right: Storage usage

    This is a "dumb" component - it only displays data and does not
    contain business logic.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the StatusBar.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the status bar UI layout and styling."""
        self.setObjectName("StatusBar")
        self.setFixedHeight(STATUS_BAR_HEIGHT)
        self.setStyleSheet(f"""
            QFrame#StatusBar {{
                background-color: {SURFACE_COLOR};
                border-top: 1px solid #2a2a4a;
            }}
            QLabel {{
                font-size: {FONT_SIZE_SMALL}px;
                padding: 0 8px;
            }}
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(16)

        # Left: Connection status
        self._connection_indicator = QLabel()
        self._connection_indicator.setObjectName("ConnectionIndicator")
        self._connection_label = QLabel()
        self._connection_label.setObjectName("ConnectionLabel")

        connection_container = QWidget()
        connection_layout = QHBoxLayout(connection_container)
        connection_layout.setContentsMargins(0, 0, 0, 0)
        connection_layout.setSpacing(4)
        connection_layout.addWidget(self._connection_indicator)
        connection_layout.addWidget(self._connection_label)
        layout.addWidget(connection_container, alignment=Qt.AlignLeft)  # type: ignore[attr-defined]

        # Center: Sync status
        self._sync_label = QLabel()
        self._sync_label.setObjectName("SyncLabel")
        self._sync_label.setStyleSheet(f"color: {TEXT_SECONDARY};")
        layout.addWidget(self._sync_label, alignment=Qt.AlignCenter)  # type: ignore[attr-defined]

        # Right: Storage usage
        self._storage_label = QLabel()
        self._storage_label.setObjectName("StorageLabel")
        self._storage_label.setStyleSheet(f"color: {TEXT_SECONDARY};")
        layout.addWidget(self._storage_label, alignment=Qt.AlignRight)  # type: ignore[attr-defined]

        # Set initial values
        self.set_connection_status(False)
        self.set_sync_status("")
        self.set_storage_usage("")

    @Slot(bool)
    def set_connection_status(self, online: bool) -> None:
        """Set the connection status indicator.

        Args:
            online: True if connected/online, False if offline.
        """
        if online:
            self._connection_indicator.setText("\u25cf")  # Filled circle
            self._connection_indicator.setStyleSheet(f"color: {SUCCESS_COLOR};")
            self._connection_label.setText("Online")
            self._connection_label.setStyleSheet(f"color: {TEXT_PRIMARY};")
        else:
            self._connection_indicator.setText("\u25cb")  # Empty circle
            self._connection_indicator.setStyleSheet(f"color: {ERROR_COLOR};")
            self._connection_label.setText("Offline")
            self._connection_label.setStyleSheet(f"color: {TEXT_SECONDARY};")

    @Slot(str)
    def set_sync_status(self, message: str) -> None:
        """Set the sync status message.

        Args:
            message: Status message (e.g., "Last Sync: 10:30" or "Syncing...").
                    Empty string clears the message.
        """
        self._sync_label.setText(message)

    @Slot(str)
    def set_storage_usage(self, usage: str) -> None:
        """Set the storage usage display.

        Args:
            usage: Storage usage string (e.g., "50 GB / 500 GB").
                   Empty string clears the display.
        """
        self._storage_label.setText(usage)
