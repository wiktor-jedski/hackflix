"""UI style constants for Hackflix.

This module contains color definitions, dimensions, and style
constants used throughout the UI components.
"""

import os

# =============================================================================
# Color Palette
# =============================================================================

# Background colors
BACKGROUND_COLOR = "#1a1a2e"  # Main background (dark blue)
SURFACE_COLOR = "#16213e"  # Card/item background
SURFACE_HOVER_COLOR = "#1f3460"  # Hovered item

# Accent colors
PRIMARY_COLOR = "#e94560"  # Primary accent (red/pink)
PRIMARY_HOVER_COLOR = "#ff6b8a"  # Hovered primary
SECONDARY_COLOR = "#0f3460"  # Secondary accent (blue)

# Text colors
TEXT_PRIMARY = "#ffffff"  # Main text
TEXT_SECONDARY = "#a0a0a0"  # Subtitle/metadata text
TEXT_DISABLED = "#666666"  # Disabled text

# Status colors
SUCCESS_COLOR = "#4ade80"  # Completed/ready
WARNING_COLOR = "#fbbf24"  # Warning/downloading
ERROR_COLOR = "#ef4444"  # Error state
INFO_COLOR = "#3b82f6"  # Information

# Selection
SELECTION_COLOR = "#e94560"  # Selected item highlight
FOCUS_BORDER_COLOR = "#e94560"  # Focus indicator

# =============================================================================
# Dimensions
# =============================================================================


def _ui_scale() -> float:
    """Return the global UI scale factor."""
    raw_value = os.environ.get("HACKFLIX_UI_SCALE", "1.45")
    try:
        value = float(raw_value)
    except ValueError:
        return 1.45
    return max(1.0, min(value, 2.25))


UI_SCALE = _ui_scale()


def scaled(value: int) -> int:
    """Scale a base pixel value for TV-distance readability."""
    return int(round(value * UI_SCALE))


# Library view
ROW_HEIGHT = scaled(170)  # Height of each library item row
POSTER_WIDTH = scaled(115)  # Poster thumbnail width
POSTER_HEIGHT = scaled(170)  # Poster thumbnail height (matches row height)
STATUS_ICON_SIZE = scaled(32)  # Status icon dimensions
ITEM_PADDING = scaled(12)  # Padding inside items
ITEM_SPACING = scaled(8)  # Spacing between items

# Status bar
STATUS_BAR_HEIGHT = scaled(40)  # Bottom status bar height

# Toast notifications
TOAST_WIDTH = scaled(320)  # Toast notification width
TOAST_MIN_HEIGHT = scaled(60)  # Minimum toast height
TOAST_MARGIN = scaled(16)  # Margin from window edges
TOAST_SPACING = scaled(8)  # Spacing between stacked toasts

# Search overlay
SEARCH_WIDTH = scaled(400)  # Search modal width
SEARCH_INPUT_HEIGHT = scaled(48)  # Search input height

# Dialogs
DIALOG_WIDTH = scaled(400)  # Confirmation dialog width
DIALOG_PADDING = scaled(24)  # Dialog content padding

# =============================================================================
# Typography
# =============================================================================

FONT_FAMILY = "Segoe UI, Roboto, Ubuntu, sans-serif"

# Font sizes
FONT_SIZE_TITLE = scaled(32)  # Item titles
FONT_SIZE_BODY = scaled(20)  # Body text, metadata
FONT_SIZE_SMALL = scaled(16)  # Small labels, hints
FONT_SIZE_LARGE = scaled(38)  # Large headings

# Font weights
FONT_WEIGHT_NORMAL = 400
FONT_WEIGHT_MEDIUM = 500
FONT_WEIGHT_BOLD = 700

# =============================================================================
# Animation
# =============================================================================

ANIMATION_DURATION_FAST = 150  # Quick transitions (ms)
ANIMATION_DURATION_NORMAL = 250  # Standard transitions (ms)
ANIMATION_DURATION_SLOW = 400  # Slow transitions (ms)

# =============================================================================
# Input
# =============================================================================

DEBOUNCE_MS = 300  # Debounce time for action keys


# =============================================================================
# QSS Stylesheet
# =============================================================================


def get_stylesheet() -> str:
    """Generate the main application stylesheet.

    Returns:
        QSS stylesheet string for the application.
    """
    return f"""
        /* Global */
        QWidget {{
            background-color: {BACKGROUND_COLOR};
            color: {TEXT_PRIMARY};
            font-family: {FONT_FAMILY};
            font-size: {FONT_SIZE_BODY}px;
        }}

        /* Main Window */
        QMainWindow {{
            background-color: {BACKGROUND_COLOR};
        }}

        /* List View */
        QListView {{
            background-color: {BACKGROUND_COLOR};
            border: none;
            outline: none;
        }}

        QListView::item {{
            background-color: {SURFACE_COLOR};
            border-radius: 4px;
            margin: {scaled(4)}px {scaled(8)}px;
            padding: {ITEM_PADDING}px;
        }}

        QListView::item:selected {{
            background-color: {SELECTION_COLOR};
        }}

        QListView::item:hover:!selected {{
            background-color: {SURFACE_HOVER_COLOR};
        }}

        /* Scroll Bar */
        QScrollBar:vertical {{
            background-color: {BACKGROUND_COLOR};
            width: {scaled(12)}px;
            margin: 0;
        }}

        QScrollBar::handle:vertical {{
            background-color: {SURFACE_HOVER_COLOR};
            border-radius: 6px;
            min-height: {scaled(40)}px;
            margin: {scaled(2)}px;
        }}

        QScrollBar::handle:vertical:hover {{
            background-color: {PRIMARY_COLOR};
        }}

        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical {{
            height: 0;
        }}

        QScrollBar::add-page:vertical,
        QScrollBar::sub-page:vertical {{
            background: none;
        }}

        /* Labels */
        QLabel {{
            background-color: transparent;
        }}

        /* Line Edit (Search) */
        QLineEdit {{
            background-color: {SURFACE_COLOR};
            border: 2px solid {SECONDARY_COLOR};
            border-radius: 4px;
            padding: {scaled(8)}px {scaled(12)}px;
            font-size: {FONT_SIZE_BODY}px;
            color: {TEXT_PRIMARY};
        }}

        QLineEdit:focus {{
            border-color: {PRIMARY_COLOR};
        }}

        /* Dialog */
        QDialog {{
            background-color: {SURFACE_COLOR};
            border-radius: 8px;
        }}

        /* Push Button */
        QPushButton {{
            background-color: {PRIMARY_COLOR};
            color: {TEXT_PRIMARY};
            border: none;
            border-radius: 4px;
            padding: {scaled(8)}px {scaled(16)}px;
            font-weight: {FONT_WEIGHT_MEDIUM};
        }}

        QPushButton:hover {{
            background-color: {PRIMARY_HOVER_COLOR};
        }}

        QPushButton:pressed {{
            background-color: {SECONDARY_COLOR};
        }}
    """
