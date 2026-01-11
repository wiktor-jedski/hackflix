"""Tests for StatusBar component."""

import pytest
from PyQt5.QtWidgets import QWidget

from src.ui.components.status_bar import StatusBar


class TestStatusBar:
    """Tests for StatusBar class."""

    @pytest.fixture
    def status_bar(self, qtbot) -> StatusBar:
        """Create a StatusBar instance."""
        bar = StatusBar()
        qtbot.addWidget(bar)
        return bar

    def test_initialization(self, status_bar: StatusBar) -> None:
        """Test StatusBar initialization."""
        assert status_bar is not None
        assert status_bar.objectName() == "StatusBar"

    def test_has_connection_indicator(self, status_bar: StatusBar) -> None:
        """Test that StatusBar has connection indicator."""
        assert status_bar._connection_indicator is not None
        assert status_bar._connection_label is not None

    def test_has_sync_label(self, status_bar: StatusBar) -> None:
        """Test that StatusBar has sync status label."""
        assert status_bar._sync_label is not None

    def test_has_storage_label(self, status_bar: StatusBar) -> None:
        """Test that StatusBar has storage usage label."""
        assert status_bar._storage_label is not None

    def test_set_connection_status_online(self, status_bar: StatusBar) -> None:
        """Test setting connection status to online."""
        status_bar.set_connection_status(True)
        assert status_bar._connection_label.text() == "Online"

    def test_set_connection_status_offline(self, status_bar: StatusBar) -> None:
        """Test setting connection status to offline."""
        status_bar.set_connection_status(False)
        assert status_bar._connection_label.text() == "Offline"

    def test_set_sync_status(self, status_bar: StatusBar) -> None:
        """Test setting sync status message."""
        status_bar.set_sync_status("Last Sync: 10:30")
        assert status_bar._sync_label.text() == "Last Sync: 10:30"

    def test_set_sync_status_empty(self, status_bar: StatusBar) -> None:
        """Test clearing sync status message."""
        status_bar.set_sync_status("Syncing...")
        status_bar.set_sync_status("")
        assert status_bar._sync_label.text() == ""

    def test_set_storage_usage(self, status_bar: StatusBar) -> None:
        """Test setting storage usage display."""
        status_bar.set_storage_usage("50 GB / 500 GB")
        assert status_bar._storage_label.text() == "50 GB / 500 GB"

    def test_set_storage_usage_empty(self, status_bar: StatusBar) -> None:
        """Test clearing storage usage display."""
        status_bar.set_storage_usage("50 GB")
        status_bar.set_storage_usage("")
        assert status_bar._storage_label.text() == ""

    def test_fixed_height(self, status_bar: StatusBar) -> None:
        """Test that StatusBar has fixed height."""
        from src.ui.styles import STATUS_BAR_HEIGHT
        assert status_bar.height() == STATUS_BAR_HEIGHT

    def test_initial_state_is_offline(self, status_bar: StatusBar) -> None:
        """Test that initial connection state is offline."""
        # Initial state set in _setup_ui with set_connection_status(False)
        assert status_bar._connection_label.text() == "Offline"
