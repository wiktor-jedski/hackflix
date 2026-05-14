"""Tests for i18n module."""

from pathlib import Path
from src.qt import QApplication

from src.utils.i18n import setup_translations, tr


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
