# --- START OF FILE file_browser.py ---

"""
File browser module for the Raspberry Pi Movie Player App.
Provides functionality for browsing and managing video files.
"""

import os
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                           QPushButton, QListWidget, QListWidgetItem, QLabel,
                           QFileDialog, QMessageBox)
# Import QDialog explicitly if needed later, but we handle dialog in main app
from PyQt5.QtCore import Qt, pyqtSignal

class FileBrowser(QWidget):
    """
    A file browser component for managing video files in a directory.
    Includes subtitle search functionality.
    """

    # Signal to notify when a file is selected for playback
    file_selected = pyqtSignal(str)
    # Signal to request subtitle search for a specific file path
    find_subtitles_requested = pyqtSignal(str) # Emit the video file path

    # Removed subtitle_manager from __init__ signature, will be accessed via main app if needed
    # or handled purely via signals/slots connected in the main app. Let's use signals.
    def __init__(self, parent=None):
        super().__init__(parent)

        # Store the current directory path
        self.current_directory = os.path.expanduser("~") # Default to home
        # Try defaulting to a more likely media location if it exists
        common_media_paths = [
             os.path.expanduser("~/Videos"),
             os.path.expanduser("~/Downloads/HackFlix"), # From DownloadsTab
             os.path.expanduser("~/Movies"),
             # Add more potential default paths here if desired
        ]
        for path in common_media_paths:
            if os.path.isdir(path):
                self.current_directory = path
                break

        self.video_extensions = ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm'] # Added more common extensions

        # Create layout
        self.layout = QVBoxLayout()

        # Top layout for directory selection
        dir_layout = QHBoxLayout()
        self.dir_button = QPushButton("Select Directory")
        self.dir_button.clicked.connect(self.select_directory)
        self.path_label = QLabel(f"Current: {self._shorten_path(self.current_directory)}")
        self.path_label.setToolTip(self.current_directory) # Show full path on hover
        dir_layout.addWidget(self.dir_button)
        dir_layout.addWidget(self.path_label, 1) # Give label stretch factor

        # Create file list widget
        self.file_list = QListWidget()
        self.file_list.itemDoubleClicked.connect(self.on_file_double_clicked)
        self.file_list.setAlternatingRowColors(True) # Improve readability

        # Create buttons for actions
        button_layout = QHBoxLayout()
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_files)
        self.play_button = QPushButton("Play Selected")
        self.play_button.clicked.connect(self.play_selected)
        self.find_subs_button = QPushButton("Find Subtitles") # New Button
        self.find_subs_button.clicked.connect(self.find_subtitles_for_selected) # Connect
        self.delete_button = QPushButton("Delete Selected")
        self.delete_button.clicked.connect(self.delete_selected)

        button_layout.addWidget(self.refresh_button)
        button_layout.addWidget(self.play_button)
        button_layout.addWidget(self.find_subs_button) # Add to layout
        button_layout.addStretch() # Push delete button to the right
        button_layout.addWidget(self.delete_button)

        # Add widgets to layout
        self.layout.addLayout(dir_layout)
        self.layout.addWidget(self.file_list)
        self.layout.addLayout(button_layout)

        self.setLayout(self.layout)

        # Populate the file list
        self.refresh_files()

    def _shorten_path(self, path, max_len=50):
        """Shortens a path string for display."""
        if len(path) <= max_len:
            return path
        # Try to shorten by taking head and tail
        parts = path.split(os.sep)
        if len(parts) > 3:
             # e.g., /home/user/.../directory/file -> /home/.../directory
             return os.path.join(parts[0], "...", *parts[-2:])
        else:
             # Fallback: just truncate
             return "..." + path[-(max_len-3):]


    def select_directory(self):
        """Open a dialog to select a directory"""
        dir_path = QFileDialog.getExistingDirectory(self, "Select Directory",
                                                  self.current_directory)
        if dir_path and dir_path != self.current_directory:
            self.current_directory = dir_path
            self.path_label.setText(f"Current: {self._shorten_path(self.current_directory)}")
            self.path_label.setToolTip(self.current_directory)
            self.refresh_files()

    def refresh_files(self):
        """Scan the current directory for video files and populate the list"""
        self.file_list.clear()

        if not os.path.isdir(self.current_directory):
             QMessageBox.warning(self, "Directory Not Found",
                              f"The directory '{self.current_directory}' does not exist.")
             return

        try:
            entries = sorted(os.listdir(self.current_directory)) # Sort entries
            for filename in entries:
                file_path = os.path.join(self.current_directory, filename)
                # List directories first (optional, might clutter)
                # if os.path.isdir(file_path):
                #     item = QListWidgetItem(f"[DIR] {filename}")
                #     item.setData(Qt.UserRole, file_path)
                #     item.setForeground(Qt.blue) # Style directories
                #     self.file_list.addItem(item)
                if os.path.isfile(file_path) and self.is_video_file(filename):
                    item = QListWidgetItem(filename)
                    item.setData(Qt.UserRole, file_path)  # Store the full path
                    # Check if subtitle exists (simple check)
                    base, _ = os.path.splitext(file_path)
                    # Check for common language codes, adjust as needed
                    if os.path.exists(f"{base}.srt") or \
                       os.path.exists(f"{base}.en.srt") or \
                       os.path.exists(f"{base}.pl.srt"):
                        item.setText(f"{filename} [Sub]") # Indicate subtitle presence
                        # Optionally change color or icon
                        # item.setForeground(Qt.darkGreen)

                    self.file_list.addItem(item)
        except PermissionError:
            QMessageBox.warning(self, "Permission Error",
                             f"Cannot access '{self.current_directory}' due to permission issues.")
        except Exception as e:
            QMessageBox.critical(self, "Error Reading Directory", f"An error occurred: {str(e)}")

    def is_video_file(self, filename):
        """Check if a file is a video file based on its extension"""
        # Ignore hidden files
        if filename.startswith('.'):
            return False
        extension = os.path.splitext(filename)[1].lower()
        return extension in self.video_extensions

    def on_file_double_clicked(self, item):
        """Handle double-click on a file item"""
        file_path = item.data(Qt.UserRole)
        if file_path and os.path.isfile(file_path): # Ensure it's a file path
             self.file_selected.emit(file_path)
        # Optional: Handle double-click on directory to navigate
        # elif file_path and os.path.isdir(file_path):
        #     self.current_directory = file_path
        #     self.path_label.setText(f"Current: {self._shorten_path(self.current_directory)}")
        #     self.path_label.setToolTip(self.current_directory)
        #     self.refresh_files()

    def get_selected_file_path(self):
        """Gets the file path of the currently selected item, returns None if none or not a file."""
        selected_items = self.file_list.selectedItems()
        if selected_items:
            file_path = selected_items[0].data(Qt.UserRole)
            # Ensure it's actually a file we stored, not e.g., a directory item if added later
            if file_path and os.path.isfile(file_path):
                return file_path
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
            print(f"FileBrowser requesting subtitles for: {file_path}") # Debug
            self.find_subtitles_requested.emit(file_path) # Emit the signal
        else:
            QMessageBox.information(self, "No Selection", "Please select a video file to find subtitles for.")


    def delete_selected(self):
        """Delete the selected file"""
        file_path = self.get_selected_file_path()
        if not file_path:
            QMessageBox.information(self, "No Selection", "Please select a video file to delete.")
            return

        file_name = os.path.basename(file_path)

        # Confirm deletion
        reply = QMessageBox.question(self, "Confirm Deletion",
                                  f"Are you sure you want to delete '{file_name}'?",
                                  QMessageBox.Yes | QMessageBox.No, QMessageBox.No)

        if reply == QMessageBox.Yes:
            try:
                os.remove(file_path)
                # Also try removing associated subtitle files (simple approach)
                base, _ = os.path.splitext(file_path)
                for ext in ['.srt', '.en.srt', '.pl.srt']: # Add other common lang codes if needed
                     sub_path = base + ext
                     if os.path.exists(sub_path):
                          try:
                               os.remove(sub_path)
                               print(f"Removed associated subtitle: {sub_path}")
                          except Exception as sub_e:
                               print(f"Could not remove subtitle {sub_path}: {sub_e}")

                QMessageBox.information(self, "Success", f"'{file_name}' (and potentially associated subtitles) has been deleted.")
                self.refresh_files() # Refresh the list
            except PermissionError:
                QMessageBox.warning(self, "Permission Error",
                                 "Cannot delete the file due to permission issues.")
            except Exception as e:
                QMessageBox.critical(self, "Error Deleting File", f"An error occurred: {str(e)}")