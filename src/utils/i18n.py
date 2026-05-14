"""Internationalization support for Hackflix.

This module provides translation loading and helper functions
for multi-language support using Qt's translation system.
"""

import logging
from pathlib import Path

from src.qt import QCoreApplication, QTranslator

logger = logging.getLogger(__name__)

# Default translations directory relative to this file
_DEFAULT_TRANSLATIONS_DIR = (
    Path(__file__).parent.parent.parent / "assets" / "translations"
)

# Global translator instance
_translator: QTranslator | None = None


def setup_translations(
    app: QCoreApplication | None,
    locale: str = "pl",
    translations_dir: Path | None = None,
) -> bool:
    """Set up translations for the application.

    Loads a .qm translation file for the specified locale and installs
    it on the application.

    Args:
        app: The QCoreApplication (or QApplication) instance.
        locale: Language code (e.g., "pl" for Polish, "en" for English).
        translations_dir: Optional path to translations directory.
                         Defaults to assets/translations/.

    Returns:
        True if translation file was loaded successfully, False otherwise.
    """
    global _translator

    if app is None:
        return False

    # Remove existing translator if any
    if _translator is not None:
        app.removeTranslator(_translator)
        _translator = None

    # Determine translations directory
    trans_dir = translations_dir or _DEFAULT_TRANSLATIONS_DIR

    # Try to load the translation file
    qm_file = trans_dir / f"hackflix_{locale}.qm"

    _translator = QTranslator(app)

    if qm_file.exists():
        if _translator.load(str(qm_file)):
            app.installTranslator(_translator)
            logger.info("Loaded translation: %s", qm_file)
            return True
        else:
            logger.warning("Failed to load translation file: %s", qm_file)
    else:
        logger.debug("Translation file not found: %s", qm_file)

    return False


def tr(context: str, text: str) -> str:
    """Translate a text string.

    Convenience function for translating strings. Use this when you
    can't use QObject.tr() directly.

    Args:
        context: Translation context (usually class name).
        text: Text to translate.

    Returns:
        Translated text, or original if no translation found.
    """
    return QCoreApplication.translate(context, text)

