"""Tests for i18n module."""

from pathlib import Path
from src.qt import QApplication

from src.utils.i18n import (
    create_translation_source,
    get_system_locale,
    setup_translations,
    tr,
)


class TestSetupTranslations:
    """Tests for setup_translations function."""

    def test_returns_false_for_nonexistent_file(self, qtbot) -> None:
        """Test that setup_translations returns False for nonexistent file."""
        app = QApplication.instance()
        result = setup_translations(app, "nonexistent_locale", Path("/nonexistent"))
        assert result is False

    def test_returns_false_for_missing_translations_dir(self, qtbot) -> None:
        """Test returns False when translations directory doesn't exist."""
        app = QApplication.instance()
        result = setup_translations(app, "en", Path("/nonexistent/path"))
        assert result is False

    def test_accepts_valid_locale(self, qtbot, tmp_path: Path) -> None:
        """Test that function accepts valid locale parameter."""
        app = QApplication.instance()
        # Even without a file, should not raise
        result = setup_translations(app, "pl", tmp_path)
        assert result is False  # No file exists


class TestGetSystemLocale:
    """Tests for get_system_locale function."""

    def test_returns_two_letter_code(self, qtbot) -> None:
        """Test that get_system_locale returns a 2-letter code."""
        locale = get_system_locale()
        assert isinstance(locale, str)
        assert len(locale) == 2


class TestTr:
    """Tests for tr function."""

    def test_returns_string(self, qtbot) -> None:
        """Test that tr returns a string."""
        result = tr("TestContext", "Test string")
        assert isinstance(result, str)

    def test_returns_original_without_translation(self, qtbot) -> None:
        """Test that tr returns original string when no translation."""
        result = tr("TestContext", "Untranslated string")
        assert result == "Untranslated string"


class TestCreateTranslationSource:
    """Tests for create_translation_source function."""

    def test_returns_dict(self) -> None:
        """Test that create_translation_source returns a dictionary."""
        source = create_translation_source()
        assert isinstance(source, dict)

    def test_contains_expected_contexts(self) -> None:
        """Test that translation source contains expected contexts."""
        source = create_translation_source()

        expected_contexts = [
            "LibraryView",
            "StatusBar",
            "SearchOverlay",
            "ConfirmDialog",
            "ToastNotification",
            "AppController",
        ]

        for context in expected_contexts:
            assert context in source, f"Missing context: {context}"

    def test_context_values_are_dicts(self) -> None:
        """Test that each context contains a dictionary of strings."""
        source = create_translation_source()

        for context, strings in source.items():
            assert isinstance(strings, dict), f"{context} should be a dict"
            for key, value in strings.items():
                assert isinstance(key, str), f"Key in {context} should be string"
                assert isinstance(value, str), f"Value in {context} should be string"

    def test_library_view_strings(self) -> None:
        """Test LibraryView translation strings exist."""
        source = create_translation_source()
        library_strings = source.get("LibraryView", {})

        assert "Movies" in library_strings
        assert "Series" in library_strings
        assert "Play" in library_strings
        assert "Downloading {progress}%" in library_strings
        assert "Error" in library_strings
        assert "Queued" in library_strings
        assert "Download" in library_strings

    def test_status_bar_strings(self) -> None:
        """Test StatusBar translation strings exist."""
        source = create_translation_source()
        status_strings = source.get("StatusBar", {})

        assert "Online" in status_strings
        assert "Offline" in status_strings

    def test_search_overlay_strings(self) -> None:
        """Test SearchOverlay translation strings exist."""
        source = create_translation_source()
        search_strings = source.get("SearchOverlay", {})

        assert "Search" in search_strings

    def test_library_item_delegate_strings(self) -> None:
        """Test LibraryItemDelegate translation strings exist."""
        source = create_translation_source()
        delegate_strings = source.get("LibraryItemDelegate", {})

        assert "No\nImage" in delegate_strings
        assert "Unknown Title" in delegate_strings


class TestSetupTranslationsWithFile:
    """Tests for setup_translations with actual translation files."""

    def test_loads_valid_translation_file(self, qtbot, tmp_path: Path) -> None:
        """Test that a valid .qm file is loaded successfully."""
        from unittest.mock import MagicMock, patch
        from src.qt import QTranslator
        import src.utils.i18n as i18n_module

        app = QApplication.instance()

        i18n_module._translator = None

        mock_translator = MagicMock(spec=QTranslator)
        mock_translator.load.return_value = True

        with patch.object(i18n_module, "QTranslator", return_value=mock_translator):
            with patch.object(app, "installTranslator") as mock_install:
                qm_file = tmp_path / "hackflix_pl.qm"
                qm_file.touch()

                result = setup_translations(app, "pl", tmp_path)

                assert result is True
                mock_translator.load.assert_called_once()
                mock_translator.load.assert_called_with(str(qm_file))
                mock_install.assert_called_once_with(mock_translator)

    def test_translation_file_exists_but_fails_load(
        self, qtbot, tmp_path: Path
    ) -> None:
        """Test behavior when translation file exists but fails to load."""
        from unittest.mock import MagicMock, patch
        from src.qt import QTranslator
        import src.utils.i18n as i18n_module

        app = QApplication.instance()

        i18n_module._translator = None

        mock_translator = MagicMock(spec=QTranslator)
        mock_translator.load.return_value = False

        with patch.object(i18n_module, "QTranslator", return_value=mock_translator):
            qm_file = tmp_path / "hackflix_test.qm"
            qm_file.touch()

            result = setup_translations(app, "test", tmp_path)

            assert result is False
            mock_translator.load.assert_called_once()

    def test_logs_warning_when_load_fails(self, qtbot, tmp_path: Path, caplog) -> None:
        """Test that warning is logged when load fails."""
        from unittest.mock import MagicMock, patch
        from src.qt import QTranslator
        import src.utils.i18n as i18n_module

        app = QApplication.instance()

        i18n_module._translator = None

        mock_translator = MagicMock(spec=QTranslator)
        mock_translator.load.return_value = False

        with patch.object(i18n_module, "QTranslator", return_value=mock_translator):
            qm_file = tmp_path / "hackflix_test.qm"
            qm_file.touch()

            with caplog.at_level("WARNING"):
                result = setup_translations(app, "test", tmp_path)

            assert result is False
            assert "Failed to load translation file" in caplog.text
