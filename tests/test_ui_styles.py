"""Tests for UI styles."""

import pytest

from src.ui import styles


class TestStyleConstants:
    """Tests for style constants."""

    def test_color_constants_are_hex(self) -> None:
        """Test that color constants are valid hex colors."""
        color_attrs = [
            "BACKGROUND_COLOR",
            "SURFACE_COLOR",
            "SURFACE_HOVER_COLOR",
            "PRIMARY_COLOR",
            "PRIMARY_HOVER_COLOR",
            "SECONDARY_COLOR",
            "TEXT_PRIMARY",
            "TEXT_SECONDARY",
            "TEXT_DISABLED",
            "SUCCESS_COLOR",
            "WARNING_COLOR",
            "ERROR_COLOR",
            "INFO_COLOR",
            "SELECTION_COLOR",
            "FOCUS_BORDER_COLOR",
        ]

        for attr in color_attrs:
            color = getattr(styles, attr)
            assert isinstance(color, str), f"{attr} should be a string"
            assert color.startswith("#"), f"{attr} should start with #"
            # Remove # and check hex
            hex_part = color[1:]
            assert len(hex_part) in [3, 6, 8], f"{attr} should be 3, 6, or 8 hex chars"
            assert all(c in "0123456789abcdefABCDEF" for c in hex_part), (
                f"{attr} should be valid hex"
            )

    def test_dimension_constants_are_positive(self) -> None:
        """Test that dimension constants are positive integers."""
        dimension_attrs = [
            "ROW_HEIGHT",
            "POSTER_WIDTH",
            "POSTER_HEIGHT",
            "STATUS_ICON_SIZE",
            "ITEM_PADDING",
            "ITEM_SPACING",
            "STATUS_BAR_HEIGHT",
            "TOAST_WIDTH",
            "TOAST_MIN_HEIGHT",
            "TOAST_MARGIN",
            "TOAST_SPACING",
            "SEARCH_WIDTH",
            "SEARCH_INPUT_HEIGHT",
            "DIALOG_WIDTH",
            "DIALOG_PADDING",
        ]

        for attr in dimension_attrs:
            value = getattr(styles, attr)
            assert isinstance(value, int), f"{attr} should be an integer"
            assert value > 0, f"{attr} should be positive"

    def test_font_constants(self) -> None:
        """Test font-related constants."""
        assert isinstance(styles.FONT_FAMILY, str)
        assert len(styles.FONT_FAMILY) > 0

        font_size_attrs = [
            "FONT_SIZE_TITLE",
            "FONT_SIZE_BODY",
            "FONT_SIZE_SMALL",
            "FONT_SIZE_LARGE",
        ]

        for attr in font_size_attrs:
            value = getattr(styles, attr)
            assert isinstance(value, int), f"{attr} should be an integer"
            assert value > 0, f"{attr} should be positive"

    def test_animation_constants(self) -> None:
        """Test animation duration constants."""
        assert styles.ANIMATION_DURATION_FAST > 0
        assert styles.ANIMATION_DURATION_NORMAL > 0
        assert styles.ANIMATION_DURATION_SLOW > 0
        # Durations should be in increasing order
        assert styles.ANIMATION_DURATION_FAST < styles.ANIMATION_DURATION_NORMAL
        assert styles.ANIMATION_DURATION_NORMAL < styles.ANIMATION_DURATION_SLOW

    def test_debounce_constant(self) -> None:
        """Test debounce constant."""
        assert isinstance(styles.DEBOUNCE_MS, int)
        assert styles.DEBOUNCE_MS > 0


class TestStylesheet:
    """Tests for stylesheet generation."""

    def test_get_stylesheet_returns_string(self) -> None:
        """Test that get_stylesheet returns a non-empty string."""
        stylesheet = styles.get_stylesheet()
        assert isinstance(stylesheet, str)
        assert len(stylesheet) > 0

    def test_stylesheet_contains_expected_selectors(self) -> None:
        """Test that stylesheet contains expected CSS selectors."""
        stylesheet = styles.get_stylesheet()

        expected_selectors = [
            "QWidget",
            "QMainWindow",
            "QListView",
            "QScrollBar",
            "QLabel",
            "QLineEdit",
            "QDialog",
            "QPushButton",
        ]

        for selector in expected_selectors:
            assert selector in stylesheet, f"Stylesheet should contain {selector}"

    def test_stylesheet_uses_color_constants(self) -> None:
        """Test that stylesheet uses defined color constants."""
        stylesheet = styles.get_stylesheet()

        # At least some colors should appear in the stylesheet
        assert styles.BACKGROUND_COLOR in stylesheet
        assert styles.SURFACE_COLOR in stylesheet
        assert styles.TEXT_PRIMARY in stylesheet
