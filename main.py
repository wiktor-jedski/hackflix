#!/usr/bin/env python3
"""
Main entry point for the Raspberry Pi Movie Player App.
This script imports the necessary components from the source directory and runs the application.
"""

import sys
import os
from PyQt5.QtWidgets import QApplication

# Import directly from the movie_player module

from source.movie_player import MoviePlayerApp

def main():
    """Initialize and run the application"""
    app = QApplication(sys.argv)
    player = MoviePlayerApp()
    player.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
