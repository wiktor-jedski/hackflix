# --- START OF FILE source/file_browser.py ---

"""
File browser module for the Raspberry Pi Movie Player App.
Provides functionality for browsing and managing video files recursively.
"""

import os
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                           QPushButton, QListWidget, QListWidgetItem, QLabel,
                           QFileDialog, QMessageBox)
from PyQt5.QtCore import Qt, pyqtSignal
import traceback

class FileBrowser(QWidget):
    """
    A file browser component for managing video files in a directory and its subdirectories.
    Includes subtitle search functionality.
    """

    file_selected = pyqtSignal(str)
    find_subtitles_requested = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.current_directory = os.path.expanduser("~")
        common_media_paths = [
             os.path.expanduser("~/Videos"),
             os.path.expanduser("~/Downloads/HackFlix"),
             os.path.expanduser("~/Movies"),
             "/media", # Common mount point for external drives
        ]
        for path in common_media_paths:
            # Check parent first if it's /media/user/drive
            parent_dir = os.path.dirname(path)
            if os.path.isdir(path):
                self.current_directory = path
                break
            elif parent_dir == "/media" and os.path.isdir(parent_dir):
                 # If /media exists, look for user mounts inside
                 try:
                     possible_mounts = [os.path.join(parent_dir, d) for d in os.listdir(parent_dir)]
                     user_mounts = [d for d in possible_mounts if os.path.isdir(d)]
                     if user_mounts:
                          # Look for common drive names or just take the first
                          for mount in user_mounts:
                               if os.path.isdir(os.path.join(mount, "Movies")):
                                    self.current_directory = os.path.join(mount, "Movies")
                                    break
                               elif os.path.isdir(os.path.join(mount, "Videos")):
                                     self.current_directory = os.path.join(mount, "Videos")
                                     break
                          if self.current_directory == os.path.expanduser("~"): # If no specific folder found
                               self.current_directory = user_mounts[0] # Default to first mount point
                          break # Exit outer loop once a /media mount is found
                 except PermissionError:
                     pass # Ignore permission errors listing /media contents

        self.video_extensions = ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm']

        self.layout = QVBoxLayout()

        dir_layout = QHBoxLayout()
        self.dir_button = QPushButton("Select Base Directory")
        self.dir_button.clicked.connect(self.select_directory)
        self.path_label = QLabel(f"Scanning: {self._shorten_path(self.current_directory)}")
        self.path_label.setToolTip(f"Base Directory: {self.current_directory}")
        dir_layout.addWidget(self.dir_button)
        dir_layout.addWidget(self.path_label, 1)

        self.file_list = QListWidget()
        self.file_list.itemDoubleClicked.connect(self.on_file_double_clicked)
        self.file_list.setAlternatingRowColors(True)
        self.file_list.setSortingEnabled(True) # Enable sorting

        button_layout = QHBoxLayout()
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_files)
        self.play_button = QPushButton("Play Selected")
        self.play_button.clicked.connect(self.play_selected)
        self.find_subs_button = QPushButton("Find Subtitles")
        self.find_subs_button.clicked.connect(self.find_subtitles_for_selected)
        self.delete_button = QPushButton("Delete Selected")
        self.delete_button.clicked.connect(self.delete_selected)

        button_layout.addWidget(self.refresh_button)
        button_layout.addWidget(self.play_button)
        button_layout.addWidget(self.find_subs_button)
        button_layout.addStretch()
        button_layout.addWidget(self.delete_button)

        self.layout.addLayout(dir_layout)
        self.layout.addWidget(self.file_list)
        self.layout.addLayout(button_layout)
        self.setLayout(self.layout)

        self.refresh_files()

    def _shorten_path(self, path, max_len=60):
        """Shortens a path string for display."""
        if len(path) <= max_len:
            return path
        parts = path.split(os.sep)
        if len(parts) > 3:
             return os.path.join(parts[0], "...", *parts[-2:])
        else:
             return "..." + path[-(max_len-3):]

    def select_directory(self):
        """Open a dialog to select a base directory"""
        dir_path = QFileDialog.getExistingDirectory(self, "Select Base Directory to Scan",
                                                  self.current_directory)
        if dir_path and dir_path != self.current_directory:
            self.current_directory = dir_path
            self.path_label.setText(f"Scanning: {self._shorten_path(self.current_directory)}")
            self.path_label.setToolTip(f"Base Directory: {self.current_directory}")
            self.refresh_files()

    def refresh_files(self):
        """Scan the current directory AND subdirectories for video files."""
        self.file_list.clear()
        print(f"Refreshing file list for: {self.current_directory}")

        if not os.path.isdir(self.current_directory):
             QMessageBox.warning(self, "Directory Not Found",
                              f"The base directory '{self.current_directory}' does not exist or is not accessible.")
             return

        found_files = [] # Store tuples of (display_text, full_path) for sorting later

        try:
            # Use os.walk to traverse the directory tree
            for dirpath, dirnames, filenames in os.walk(self.current_directory, topdown=True):
                # Optional: Skip hidden directories (like .git, .cache)
                # dirnames[:] = [d for d in dirnames if not d.startswith('.')]

                # print(f"Scanning directory: {dirpath}") # Debug print (can be verbose)
                for filename in filenames:
                    # Optional: Skip hidden files
                    # if filename.startswith('.'):
                    #    continue

                    if self.is_video_file(filename):
                        full_path = os.path.join(dirpath, filename)
                        try:
                            # Ensure file is actually accessible before adding
                            if os.path.isfile(full_path):
                                # Calculate path relative to the base directory for display
                                display_path = os.path.relpath(full_path, self.current_directory)

                                # --- Subtitle Check ---
                                has_subtitle = False
                                base, _ = os.path.splitext(full_path)
                                common_sub_exts = ['.srt', '.en.srt', '.pl.srt', '.eng.srt'] # Add more if needed
                                for ext in common_sub_exts:
                                    if os.path.exists(f"{base}{ext}"):
                                        has_subtitle = True
                                        break
                                display_text = f"{display_path}{' [Sub]' if has_subtitle else ''}"
                                # --- End Subtitle Check ---

                                found_files.append((display_text, full_path))

                        except OSError as os_err:
                             print(f"Skipping file due to OS error: {full_path} - {os_err}")
                             continue # Skip this file if path is invalid or unreadable

        except PermissionError as pe:
            # Show warning but continue if possible (might have only partial permissions)
            print(f"Permission error scanning part of '{self.current_directory}': {pe}")
            QMessageBox.warning(self, "Partial Scan Error",
                             f"Could not fully scan '{self.current_directory}' due to permission issues.\nSome files may be missing.")
        except Exception as e:
            print(f"Error during file scan: {e}\n{traceback.format_exc()}")
            QMessageBox.critical(self, "Scan Error", f"An unexpected error occurred while scanning:\n{str(e)}")
            return # Stop processing if a major error occurs

        # Sort files alphabetically by display path before adding to list
        found_files.sort()

        # Populate the list widget
        if not found_files:
             item = QListWidgetItem("No video files found in this directory or subdirectories.")
             item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
             self.file_list.addItem(item)
        else:
             for display_text, full_path in found_files:
                  item = QListWidgetItem(display_text)
                  item.setData(Qt.UserRole, full_path) # Store the FULL path for actions
                  item.setToolTip(full_path) # Show full path on hover
                  self.file_list.addItem(item)

        print(f"Found {len(found_files)} video files.")


    def is_video_file(self, filename):
        """Check if a file is a video file based on its extension"""
        # Added check for empty extension which os.splitext can return
        name, ext = os.path.splitext(filename)
        if not ext: # Skip files with no extension
            return False
        # Optional: Ignore hidden files (already handled in refresh_files, but double check)
        if filename.startswith('.'):
            return False
        return ext.lower() in self.video_extensions

    def on_file_double_clicked(self, item):
        """Handle double-click on a file item"""
        full_path = item.data(Qt.UserRole)
        # Check if data is valid before emitting
        if full_path and isinstance(full_path, str) and os.path.isfile(full_path):
             self.file_selected.emit(full_path)
        else:
             print(f"Invalid data or not a file for double-clicked item: {item.text()}")

    def get_selected_file_path(self):
        """Gets the file path of the currently selected item, returns None if none or not a file."""
        selected_items = self.file_list.selectedItems()
        if selected_items:
            full_path = selected_items[0].data(Qt.UserRole)
            # Check if data is valid before returning
            if full_path and isinstance(full_path, str) and os.path.isfile(full_path):
                return full_path
        return None

    def play_selected(self):
        """Play the selected file"""
        file_path = self.get_selected_file_path()
        if file_path:
            self.file_selected.emit(file_path)
        else:
            QMessageBox.information(self, "No Selection", "Please select a video file to play.")

    def find_subtitles_for_selected(self):
        """Emit signal to find subtitles for the selected file"""
        file_path = self.get_selected_file_path()
        if file_path:
            print(f"FileBrowser requesting subtitles for: {file_path}")
            self.find_subtitles_requested.emit(file_path)
        else:
            QMessageBox.information(self, "No Selection", "Please select a video file to find subtitles for.")


    def delete_selected(self):
        """Delete the selected file and associated subtitles."""
        file_path = self.get_selected_file_path()
        if not file_path:
            QMessageBox.information(self, "No Selection", "Please select a video file to delete.")
            return

        # Use the display text (relative path) for the confirmation message
        display_text = "selected file"
        selected_items = self.file_list.selectedItems()
        if selected_items:
            display_text = selected_items[0].text().replace(" [Sub]","") # Clean display text

        reply = QMessageBox.question(self, "Confirm Deletion",
                                  f"Are you sure you want to delete:\n'{display_text}'\n(and associated subtitle files)?",
                                  QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            try:
                print(f"Attempting to delete video file: {file_path}")
                os.remove(file_path)
                deleted_subs = []
                # Also try removing associated subtitle files
                base, _ = os.path.splitext(file_path)
                common_sub_exts = ['.srt', '.en.srt', '.pl.srt', '.eng.srt'] # Match refresh_files check
                for ext in common_sub_exts:
                     sub_path = base + ext
                     if os.path.exists(sub_path):
                          try:
                               os.remove(sub_path)
                               deleted_subs.append(os.path.basename(sub_path))
                               print(f"Removed associated subtitle: {sub_path}")
                          except Exception as sub_e:
                               print(f"Could not remove subtitle {sub_path}: {sub_e}")
                               QMessageBox.warning(self, "Subtitle Deletion Error", f"Could not delete subtitle:\n{os.path.basename(sub_path)}\nError: {sub_e}")

                msg = f"'{display_text}' deleted."
                if deleted_subs:
                    msg += f"\nAlso deleted subtitles: {', '.join(deleted_subs)}"
                QMessageBox.information(self, "Success", msg)
                self.refresh_files()
            except PermissionError:
                QMessageBox.warning(self, "Permission Error",
                                 "Cannot delete the file due to permission issues.")
            except Exception as e:
                QMessageBox.critical(self, "Error Deleting File", f"An error occurred while deleting:\n{str(e)}")

# --- END OF FILE source/file_browser.py ---