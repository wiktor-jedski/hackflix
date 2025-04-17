#!/usr/bin/env python3
"""
Main entry point for the Raspberry Pi Movie Player App.
This script imports the necessary components from the source directory and runs the application.
"""

import sys
import os
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QFile, QTextStream # Import classes for file handling

# Import directly from the movie_player module
from source.movie_player import MoviePlayerApp
# Import config variables to check placeholders
from source.subtitle_manager import OPENSUBTITLES_API_KEY, OPENSUBTITLES_USERNAME, OPENSUBTITLES_PASSWORD


def load_stylesheet(app, filename="source/dark_theme.qss"):
    """Loads a QSS file and applies it to the application."""
    style_file = QFile(filename)
    if not style_file.exists():
        print(f"Warning: Stylesheet file '{filename}' not found.")
        return False
    if style_file.open(QFile.ReadOnly | QFile.Text):
        stream = QTextStream(style_file)
        stylesheet = stream.readAll()
        app.setStyleSheet(stylesheet)
        print(f"Applied stylesheet from '{filename}'")
        style_file.close()
        return True
    else:
        print(f"Error: Could not open stylesheet file '{filename}'.")
        return False


def main():
    """Initialize and run the application"""
    # Set environment variable for Qt scaling if needed (optional)
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    os.environ["QT_SCALE_FACTOR"] = "2.0" # Adjust if UI elements are too small/large

    app = QApplication(sys.argv)

    load_stylesheet(app)

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
    player.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
