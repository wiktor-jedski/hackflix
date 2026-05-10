"""UI enumerations for Hackflix.

This module defines semantic actions and application states
for the UI state machine.
"""

from enum import Enum, auto


class Action(Enum):
    """Semantic actions emitted by InputManager.

    These actions are mapped from raw Qt key events and represent
    user intentions regardless of the current UI state.
    """

    NONE = auto()

    # Navigation actions (allow key repeat for fast scrolling)
    NAVIGATE_UP = auto()
    NAVIGATE_DOWN = auto()
    NAVIGATE_LEFT = auto()
    NAVIGATE_RIGHT = auto()

    # Tab actions
    SWITCH_TAB = auto()  # Tab key - toggle Movies/Series

    # Library actions (debounced)
    SEARCH = auto()  # S key - open search overlay
    CLEAR_FILTER = auto()  # X key - clear search filter
    DELETE = auto()  # D key - delete confirmation
    SYNC = auto()  # P key - trigger metadata sync

    # Universal actions (debounced)
    CONFIRM = auto()  # Enter key - confirm/activate
    CANCEL = auto()  # Esc key - cancel/back
    QUIT = auto()  # Ctrl+Q - exit application

    # Player actions (Phase 4 stubs)
    TOGGLE_PAUSE = auto()  # Space/Enter in player
    SEEK_FORWARD = auto()  # Right arrow in player
    SEEK_BACKWARD = auto()  # Left arrow in player
    VOLUME_UP = auto()  # Up arrow in player
    VOLUME_DOWN = auto()  # Down arrow in player
    TOGGLE_MUTE = auto()  # M key in player
    CYCLE_AUDIO = auto()  # L key in player
    CYCLE_SUBTITLE = auto()  # V key in player


class AppState(Enum):
    """Application state machine states.

    The application is always in exactly one state. The InputManager
    routes key events differently based on the current state.
    """

    LIBRARY_ROOT = auto()  # Main library view (Movies/Series tabs)
    SERIES_DRILLDOWN_SEASONS = auto()  # Viewing season list for a series
    SERIES_DRILLDOWN_EPISODES = auto()  # Viewing episode list for a season
    SEARCH_OVERLAY = auto()  # Search modal is active
    DIALOG_CONFIRM = auto()  # Confirmation dialog is active
    PLAYER_ACTIVE = auto()  # Video playback (Phase 4)


class MediaTab(Enum):
    """Library tabs for content filtering."""

    MOVIES = "movie"
    SERIES = "series"
