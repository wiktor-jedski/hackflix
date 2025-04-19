#!/usr/bin/env python3
"""
Main entry point for the Raspberry Pi Movie Player App.
This script imports the necessary components from the source directory,
sets up translation, and runs the application.
"""

import sys
import os
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QFile, QTextStream, QTranslator, QLocale, QLibraryInfo # Added QTranslator, QLocale, QLibraryInfo

# Import directly from the movie_player module
from source.movie_player import MoviePlayerApp
# Import config variables to check placeholders
from source.subtitle_manager import OPENSUBTITLES_API_KEY, OPENSUBTITLES_USERNAME, OPENSUBTITLES_PASSWORD

# --- Function to load and apply stylesheet ---
def load_stylesheet(app, filename="source/dark_theme.qss"):
    # ... (load_stylesheet function remains the same) ...
    style_file = QFile(filename)
    if not style_file.exists(): print(f"Warning: Stylesheet file '{filename}' not found."); return False
    if style_file.open(QFile.ReadOnly | QFile.Text):
        stream = QTextStream(style_file); stylesheet = stream.readAll()
        app.setStyleSheet(stylesheet); print(f"Applied stylesheet from '{filename}'"); style_file.close(); return True
    else: print(f"Error: Could not open stylesheet file '{filename}'."); return False

def main():
    """Initialize and run the application"""
    app = QApplication(sys.argv)

    # --- Setup Translation ---
    translator = QTranslator()
    # Determine locale (e.g., 'pl_PL') - use system default
    locale = QLocale.system().name() # e.g., "pl_PL", "en_US"
    print(f"System locale detected: {locale}")

    # Construct filename (assuming .qm files are in a 'translations' subdir)
    # Adjust path if needed
    translation_filename = f"translations/{locale}.qm"
    translation_path_app = os.path.join(os.path.dirname(__file__), translation_filename) # App specific translations

    # Load application-specific translations
    if os.path.exists(translation_path_app):
        if translator.load(translation_path_app):
            app.installTranslator(translator)
            print(f"Loaded application translation: {translation_path_app}")
        else:
            print(f"Warning: Failed to load application translation file: {translation_path_app}")
    else:
         print(f"Info: Application translation file not found: {translation_path_app}")
         # Optionally try loading just the language part (e.g., 'pl.qm') as fallback
         base_locale = locale.split('_')[0]
         fallback_filename = f"translations/{base_locale}.qm"
         fallback_path_app = os.path.join(os.path.dirname(__file__), fallback_filename)
         if os.path.exists(fallback_path_app):
              if translator.load(fallback_path_app):
                  app.installTranslator(translator)
                  print(f"Loaded fallback application translation: {fallback_path_app}")
              else:
                   print(f"Warning: Failed to load fallback application translation: {fallback_path_app}")


    # Load standard Qt translations (for default dialog buttons like OK, Cancel)
    qt_translator = QTranslator()
    # Find the path to standard Qt translations
    qt_translation_path = QLibraryInfo.location(QLibraryInfo.TranslationsPath)
    qt_translation_file = f"qtbase_{locale.split('_')[0]}.qm" # Use base language code (e.g., qtbase_pl.qm)
    qt_full_path = os.path.join(qt_translation_path, qt_translation_file)

    if os.path.exists(qt_full_path):
        if qt_translator.load(qt_full_path):
            app.installTranslator(qt_translator)
            print(f"Loaded Qt base translation: {qt_full_path}")
        else:
            print(f"Warning: Failed to load Qt base translation: {qt_full_path}")
    else:
        print(f"Info: Qt base translation file not found: {qt_full_path} (Standard buttons might be in English)")
    # --- End Translation Setup ---


    # --- Apply the Dark Theme ---
    load_stylesheet(app)
    # --- End Apply Theme ---

    # --- Check Configuration Placeholders ---
    if OPENSUBTITLES_API_KEY == "YOUR_API_KEY_HERE":
         print("\n" + "*"*60)
         print(" WARNING: OpenSubtitles API Key placeholder not replaced!")
         print("          Subtitle functionality will likely fail.")
         print("          Edit source/subtitle_manager.py and replace YOUR_API_KEY_HERE")
         print("*"*60 + "\n")
    elif OPENSUBTITLES_USERNAME != "YOUR_USERNAME_HERE" and OPENSUBTITLES_PASSWORD == "YOUR_PASSWORD_HERE":
         print("\n" + "*"*60)
         print(" WARNING: OpenSubtitles username is set, but password placeholder is not replaced!")
         print("          Login for extended download limits will fail.")
         print("          Edit source/subtitle_manager.py and replace YOUR_PASSWORD_HERE")
         print("*"*60 + "\n")
    # --- End Check ---

    player = MoviePlayerApp()
    player.showMaximized()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
