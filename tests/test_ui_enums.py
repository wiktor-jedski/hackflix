"""Tests for UI enumerations."""

import pytest

from src.ui.enums import Action, AppState, MediaTab


class TestAction:
    """Tests for Action enum."""

    def test_action_values_exist(self) -> None:
        """Test that all expected action values exist."""
        # Navigation actions
        assert Action.NAVIGATE_UP
        assert Action.NAVIGATE_DOWN
        assert Action.NAVIGATE_LEFT
        assert Action.NAVIGATE_RIGHT

        # Tab actions
        assert Action.SWITCH_TAB

        # Library actions
        assert Action.SEARCH
        assert Action.CLEAR_FILTER
        assert Action.DELETE
        assert Action.SYNC

        # Universal actions
        assert Action.CONFIRM
        assert Action.CANCEL
        assert Action.QUIT
        assert Action.NONE

        # Player actions
        assert Action.TOGGLE_PAUSE
        assert Action.SEEK_FORWARD
        assert Action.SEEK_BACKWARD
        assert Action.VOLUME_UP
        assert Action.VOLUME_DOWN
        assert Action.TOGGLE_MUTE
        assert Action.CYCLE_AUDIO

    def test_action_values_unique(self) -> None:
        """Test that all action values are unique."""
        values = [a.value for a in Action]
        assert len(values) == len(set(values))

    def test_action_is_enum(self) -> None:
        """Test that actions can be compared."""
        assert Action.CONFIRM != Action.CANCEL
        assert Action.NAVIGATE_UP == Action.NAVIGATE_UP


class TestAppState:
    """Tests for AppState enum."""

    def test_app_state_values_exist(self) -> None:
        """Test that all expected app state values exist."""
        assert AppState.LIBRARY_ROOT
        assert AppState.SERIES_DRILLDOWN_SEASONS
        assert AppState.SERIES_DRILLDOWN_EPISODES
        assert AppState.SEARCH_OVERLAY
        assert AppState.DIALOG_CONFIRM
        assert AppState.PLAYER_ACTIVE

    def test_app_state_values_unique(self) -> None:
        """Test that all app state values are unique."""
        values = [s.value for s in AppState]
        assert len(values) == len(set(values))


class TestMediaTab:
    """Tests for MediaTab enum."""

    def test_media_tab_values(self) -> None:
        """Test media tab string values."""
        assert MediaTab.MOVIES.value == "movie"
        assert MediaTab.SERIES.value == "series"

    def test_media_tab_can_be_used_as_string(self) -> None:
        """Test that media tab values work as database type strings."""
        assert MediaTab.MOVIES.value in ["movie", "series"]
        assert MediaTab.SERIES.value in ["movie", "series"]
