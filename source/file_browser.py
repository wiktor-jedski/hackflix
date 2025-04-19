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

        # --- Determine Default Directory ---
        # (Code to find default directory remains the same)
        self.current_directory = os.path.expanduser("~")
        common_media_paths = [
             os.path.expanduser("~/Videos"),
             os.path.expanduser("~/Downloads/HackFlix"),
             os.path.expanduser("~/Movies"),
             "/media",
        ]
        for path in common_media_paths:
            parent_dir = os.path.dirname(path)
            if os.path.isdir(path):
                self.current_directory = path; break
            elif parent_dir == "/media" and os.path.isdir(parent_dir):
                 try:
                     possible_mounts = [os.path.join(parent_dir, d) for d in os.listdir(parent_dir)]
                     user_mounts = [d for d in possible_mounts if os.path.isdir(d)]
                     if user_mounts:
                          found_specific = False
                          for mount in user_mounts:
                               if os.path.isdir(os.path.join(mount, "Movies")): self.current_directory = os.path.join(mount, "Movies"); found_specific = True; break
                               elif os.path.isdir(os.path.join(mount, "Videos")): self.current_directory = os.path.join(mount, "Videos"); found_specific = True; break
                          if not found_specific: self.current_directory = user_mounts[0]
                          break
                 except PermissionError: pass
        # --- End Default Directory ---

        self.video_extensions = ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm']

        # --- UI Layout ---
        self.layout = QVBoxLayout()

        # Directory Selection Area
        dir_layout = QHBoxLayout()
        self.dir_button = QPushButton(self.tr("Select Base Directory")) # Use tr()
        self.dir_button.clicked.connect(self.select_directory)
        # Use tr() for label prefix
        self.path_label = QLabel(f"{self.tr('Scanning')}: {self._shorten_path(self.current_directory)}")
        # Use tr() for tooltip prefix
        self.path_label.setToolTip(f"{self.tr('Base Directory')}: {self.current_directory}")
        dir_layout.addWidget(self.dir_button)
        dir_layout.addWidget(self.path_label, 1)

        # File List
        self.file_list = QListWidget()
        self.file_list.itemDoubleClicked.connect(self.on_file_double_clicked)
        self.file_list.setAlternatingRowColors(True)
        self.file_list.setSortingEnabled(True)

        # Action Buttons
        button_layout = QHBoxLayout()
        self.refresh_button = QPushButton(self.tr("Refresh")) # Use tr()
        self.refresh_button.clicked.connect(self.refresh_files)
        self.play_button = QPushButton(self.tr("Play Selected")) # Use tr()
        self.play_button.clicked.connect(self.play_selected)
        self.find_subs_button = QPushButton(self.tr("Find Subtitles")) # Use tr()
        self.find_subs_button.clicked.connect(self.find_subtitles_for_selected)
        self.delete_button = QPushButton(self.tr("Delete Selected")) # Use tr()
        self.delete_button.clicked.connect(self.delete_selected)

        button_layout.addWidget(self.refresh_button)
        button_layout.addWidget(self.play_button)
        button_layout.addWidget(self.find_subs_button)
        button_layout.addStretch()
        button_layout.addWidget(self.delete_button)

        # Assemble Layout
        self.layout.addLayout(dir_layout)
        self.layout.addWidget(self.file_list)
        self.layout.addLayout(button_layout)
        self.setLayout(self.layout)
        # --- End UI Layout ---

        # Initial population
        self.refresh_files()

    def _shorten_path(self, path, max_len=60):
        """Shortens a path string for display."""
        # (Code remains the same)
        if len(path) <= max_len: return path
        parts = path.split(os.sep);
        if len(parts) > 3: return os.path.join(parts[0], "...", *parts[-2:])
        else: return "..." + path[-(max_len-3):]

    def select_directory(self):
        """Open a dialog to select a base directory"""
        # Use tr() for dialog title
        dir_path = QFileDialog.getExistingDirectory(self, self.tr("Select Base Directory to Scan"),
                                                  self.current_directory)
        if dir_path and dir_path != self.current_directory:
            self.current_directory = dir_path
            # Use tr() for label prefix
            self.path_label.setText(f"{self.tr('Scanning')}: {self._shorten_path(self.current_directory)}")
            # Use tr() for tooltip prefix
            self.path_label.setToolTip(f"{self.tr('Base Directory')}: {self.current_directory}")
            self.refresh_files()

    def refresh_files(self):
        """Scan the current directory AND subdirectories for video files."""
        self.file_list.clear()
        print(f"Refreshing file list for: {self.current_directory}")

        if not os.path.isdir(self.current_directory):
             # Use tr() for message box
             QMessageBox.warning(self,
                 self.tr("Directory Not Found"),
                 self.tr("The base directory '{0}' does not exist or is not accessible.").format(self.current_directory)
             )
             return

        found_files = []
        try:
            for dirpath, dirnames, filenames in os.walk(self.current_directory, topdown=True):
                for filename in filenames:
                    if self.is_video_file(filename):
                        full_path = os.path.join(dirpath, filename)
                        try:
                            if os.path.isfile(full_path):
                                display_path = os.path.relpath(full_path, self.current_directory)
                                has_subtitle = False
                                base, _ = os.path.splitext(full_path)
                                common_sub_exts = ['.srt', '.en.srt', '.pl.srt', '.eng.srt']
                                for ext in common_sub_exts:
                                    if os.path.exists(f"{base}{ext}"): has_subtitle = True; break
                                # Use tr() for the [Sub] suffix marker
                                display_text = f"{display_path}{self.tr(' [Sub]') if has_subtitle else ''}"
                                found_files.append((display_text, full_path))
                        except OSError as os_err:
                             print(f"Skipping file due to OS error: {full_path} - {os_err}")
                             continue
        except PermissionError as pe:
            print(f"Permission error scanning part of '{self.current_directory}': {pe}")
            # Use tr() for message box
            QMessageBox.warning(self,
                self.tr("Partial Scan Error"),
                self.tr("Could not fully scan '{0}' due to permission issues.\nSome files may be missing.").format(self.current_directory)
            )
        except Exception as e:
            print(f"Error during file scan: {e}\n{traceback.format_exc()}")
             # Use tr() for message box
            QMessageBox.critical(self,
                self.tr("Scan Error"),
                self.tr("An unexpected error occurred while scanning:\n{0}").format(str(e))
            )
            return

        found_files.sort()

        if not found_files:
             # Use tr() for message
             item = QListWidgetItem(self.tr("No video files found in this directory or subdirectories."))
             item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
             self.file_list.addItem(item)
        else:
             for display_text, full_path in found_files:
                  item = QListWidgetItem(display_text)
                  item.setData(Qt.UserRole, full_path)
                  item.setToolTip(full_path)
                  self.file_list.addItem(item)

        print(f"Found {len(found_files)} video files.")


    def is_video_file(self, filename):
        """Check if a file is a video file based on its extension"""
        # (Code remains the same)
        name, ext = os.path.splitext(filename);
        if not ext: return False
        if filename.startswith('.'): return False
        return ext.lower() in self.video_extensions

    def on_file_double_clicked(self, item):
        """Handle double-click on a file item"""
        # (Code remains the same)
        full_path = item.data(Qt.UserRole)
        if full_path and isinstance(full_path, str) and os.path.isfile(full_path): self.file_selected.emit(full_path)
        else: print(f"Invalid data or not a file for double-clicked item: {item.text()}")

    def get_selected_file_path(self):
        """Gets the file path of the currently selected item, returns None if none or not a file."""
        # (Code remains the same)
        selected_items = self.file_list.selectedItems()
        if selected_items:
            full_path = selected_items[0].data(Qt.UserRole)
            if full_path and isinstance(full_path, str) and os.path.isfile(full_path): return full_path
        return None

    def play_selected(self):
        """Play the selected file"""
        file_path = self.get_selected_file_path()
        if file_path:
            self.file_selected.emit(file_path)
        else:
            # Use tr() for message box
            QMessageBox.information(self,
                self.tr("No Selection"),
                self.tr("Please select a video file to play.")
            )

    def find_subtitles_for_selected(self):
        """Emit signal to find subtitles for the selected file"""
        file_path = self.get_selected_file_path()
        if file_path:
            print(f"FileBrowser requesting subtitles for: {file_path}")
            self.find_subtitles_requested.emit(file_path)
        else:
            # Use tr() for message box
            QMessageBox.information(self,
                self.tr("No Selection"),
                self.tr("Please select a video file to find subtitles for.")
            )


    def delete_selected(self):
        """Delete the selected file and associated subtitles."""
        file_path = self.get_selected_file_path()
        if not file_path:
            # Use tr() for message box
            QMessageBox.information(self,
                self.tr("No Selection"),
                self.tr("Please select a video file to delete.")
            )
            return

        display_text = "selected file"
        selected_items = self.file_list.selectedItems()
        if selected_items:
            display_text = selected_items[0].text().replace(self.tr(" [Sub]"),"") # Use tr() here too

        # Use tr() for message box
        reply = QMessageBox.question(self,
            self.tr("Confirm Deletion"),
            self.tr("Are you sure you want to delete:\n'{0}'\n(and associated subtitle files)?").format(display_text),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                print(f"Attempting to delete video file: {file_path}")
                os.remove(file_path)
                deleted_subs = []
                base, _ = os.path.splitext(file_path)
                common_sub_exts = ['.srt', '.en.srt', '.pl.srt', '.eng.srt']
                for ext in common_sub_exts:
                     sub_path = base + ext
                     if os.path.exists(sub_path):
                          try:
                               os.remove(sub_path); deleted_subs.append(os.path.basename(sub_path))
                               print(f"Removed associated subtitle: {sub_path}")
                          except Exception as sub_e:
                               print(f"Could not remove subtitle {sub_path}: {sub_e}")
                               # Use tr() for message box
                               QMessageBox.warning(self,
                                   self.tr("Subtitle Deletion Error"),
                                   self.tr("Could not delete subtitle:\n{0}\nError: {1}").format(os.path.basename(sub_path), sub_e)
                               )

                # Use tr() for message box
                msg = self.tr("'{0}' deleted.").format(display_text)
                if deleted_subs:
                    # Use tr() for added text
                    msg += self.tr("\nAlso deleted subtitles: {0}").format(', '.join(deleted_subs))
                QMessageBox.information(self, self.tr("Success"), msg) # Use tr() for title
                self.refresh_files()
            except PermissionError:
                 # Use tr() for message box
                 QMessageBox.warning(self,
                     self.tr("Permission Error"),
                     self.tr("Cannot delete the file due to permission issues.")
                 )
            except Exception as e:
                 # Use tr() for message box
                 QMessageBox.critical(self,
                     self.tr("Error Deleting File"),
                     self.tr("An error occurred while deleting:\n{0}").format(str(e))
                 )

# --- END OF FILE source/file_browser.py ---