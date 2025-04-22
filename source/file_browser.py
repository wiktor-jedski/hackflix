# --- START OF FILE source/file_browser.py ---

"""
File browser module for the Raspberry Pi Movie Player App.
Provides functionality for browsing and managing video files recursively.
"""

import os
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout,
                           QPushButton, QListWidget, QListWidgetItem, QLabel,
                           QFileDialog, QMessageBox, QApplication)
from PyQt5.QtCore import Qt, pyqtSignal
import traceback

class FileBrowser(QWidget):
    """
    A file browser component for managing video files in a directory and its subdirectories.
    Includes subtitle search and translation functionality.
    """

    file_selected = pyqtSignal(str)
    find_subtitles_requested = pyqtSignal(str) # For video file path
    translate_subtitle_requested = pyqtSignal(str) # For SRT file path

    def __init__(self, parent=None):
        super().__init__(parent)
        # --- Determine Default Directory ---
        self.current_directory = os.path.expanduser("~")
        common_media_paths = [ os.path.expanduser("~/Videos"), os.path.expanduser("~/Downloads/HackFlix"), os.path.expanduser("~/Movies"), "/media",]
        for path in common_media_paths:
            parent_dir = os.path.dirname(path)
            if os.path.isdir(path): self.current_directory = path; break
            elif parent_dir == "/media" and os.path.isdir(parent_dir):
                 try:
                     possible_mounts = [os.path.join(parent_dir, d) for d in os.listdir(parent_dir)]; user_mounts = [d for d in possible_mounts if os.path.isdir(d)]
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
        self.subtitle_extensions = ['.srt']

        # --- UI Layout ---
        self.layout = QVBoxLayout()
        dir_layout = QHBoxLayout()
        self.dir_button = QPushButton(self.tr("Select Base Directory"))
        self.dir_button.clicked.connect(self.select_directory)
        self.path_label = QLabel(f"{self.tr('Scanning')}: {self._shorten_path(self.current_directory)}")
        self.path_label.setToolTip(f"{self.tr('Base Directory')}: {self.current_directory}")
        dir_layout.addWidget(self.dir_button); dir_layout.addWidget(self.path_label, 1)

        self.file_list = QListWidget(); self.file_list.itemDoubleClicked.connect(self.on_file_double_clicked)
        self.file_list.currentItemChanged.connect(self.on_selection_changed)
        self.file_list.setAlternatingRowColors(True); self.file_list.setSortingEnabled(True)

        button_layout = QHBoxLayout()
        self.refresh_button = QPushButton(self.tr("Refresh"))
        self.play_button = QPushButton(self.tr("Play Selected"))
        self.find_subs_button = QPushButton(self.tr("Find Subtitles"))
        self.translate_subs_button = QPushButton(self.tr("Translate Subtitle"));
        self.delete_button = QPushButton(self.tr("Delete Selected"))

        self.play_button.setEnabled(False); self.find_subs_button.setEnabled(False)
        self.translate_subs_button.setEnabled(False); self.delete_button.setEnabled(False)

        button_layout.addWidget(self.refresh_button); button_layout.addWidget(self.play_button)
        button_layout.addWidget(self.find_subs_button); button_layout.addWidget(self.translate_subs_button)
        button_layout.addStretch(); button_layout.addWidget(self.delete_button)

        self.layout.addLayout(dir_layout); self.layout.addWidget(self.file_list); self.layout.addLayout(button_layout)
        self.setLayout(self.layout)
        # --- End UI Layout ---

        # Connect button clicks
        self.refresh_button.clicked.connect(self.refresh_files)
        self.play_button.clicked.connect(self.play_selected)
        self.find_subs_button.clicked.connect(self.find_subtitles_for_selected)
        self.translate_subs_button.clicked.connect(self.translate_selected_subtitle)
        self.delete_button.clicked.connect(self.delete_selected)

        self.refresh_files()

    def _shorten_path(self, path, max_len=60):
        if len(path) <= max_len: return path; parts = path.split(os.sep);
        if len(parts) > 3: return os.path.join(parts[0], "...", *parts[-2:])
        else: return "..." + path[-(max_len-3):]

    def select_directory(self):
        dir_path = QFileDialog.getExistingDirectory(self, self.tr("Select Base Directory to Scan"), self.current_directory)
        if dir_path and dir_path != self.current_directory:
            self.current_directory = dir_path
            self.path_label.setText(f"{self.tr('Scanning')}: {self._shorten_path(self.current_directory)}")
            self.path_label.setToolTip(f"{self.tr('Base Directory')}: {self.current_directory}")
            self.refresh_files()

    def refresh_files(self):
        def find_associated_srt(video_full_path, lang_codes=None):
            base, _ = os.path.splitext(video_full_path)
            search_patterns = []
            if lang_codes:
                if isinstance(lang_codes, str): lang_codes = [lang_codes]
                for code in lang_codes: search_patterns.append(f"{base}.{code}.srt")
            else: search_patterns.extend([f"{base}.en.srt", f"{base}.eng.srt", f"{base}.srt"])
            for srt_path in search_patterns:
                if os.path.exists(srt_path): return srt_path
            return None

        current_selection_path = self.get_selected_file_path()
        self.file_list.clear()
        self.play_button.setEnabled(False); self.find_subs_button.setEnabled(False)
        self.translate_subs_button.setEnabled(False); self.delete_button.setEnabled(False)
        QApplication.processEvents()
        print(f"Refreshing file list for: {self.current_directory}")
        if not os.path.isdir(self.current_directory): QMessageBox.warning(self, self.tr("Directory Not Found"), self.tr("Base directory not found.")); return

        found_files = []
        try:
            for dirpath, dirnames, filenames in os.walk(self.current_directory, topdown=True):
                for filename in filenames:
                    if self.is_video_file(filename):
                        full_path = os.path.join(dirpath, filename)
                        try:
                            if os.path.isfile(full_path):
                                display_path = os.path.relpath(full_path, self.current_directory)
                                source_srt_path = find_associated_srt(full_path, lang_codes=None) # Find any source
                                translated_srt_path = find_associated_srt(full_path, lang_codes=['pl']) # Find specific target
                                sub_marker = ""
                                if translated_srt_path: sub_marker = self.tr(" [Translated Sub]")
                                elif source_srt_path: sub_marker = self.tr(" [Sub]")
                                display_text = f"{display_path}{sub_marker}"
                                # Store necessary data for later checks
                                file_data = {'video_path': full_path, 'source_srt': source_srt_path, 'translated_srt': translated_srt_path}
                                found_files.append((display_text, file_data))
                        except OSError as os_err: print(f"Skipping file OS error: {full_path} - {os_err}"); continue
        except PermissionError as pe: print(f"Permission error: {pe}"); QMessageBox.warning(self, self.tr("Partial Scan Error"), self.tr("Permission error during scan."))
        except Exception as e: print(f"Scan Error: {e}\n{traceback.format_exc()}"); QMessageBox.critical(self, self.tr("Scan Error"), self.tr("Scan failed: {0}").format(e)); return

        found_files.sort()
        restored_selection_item = None
        if not found_files:
             item = QListWidgetItem(self.tr("No video files found.")); item.setFlags(item.flags() & ~Qt.ItemIsSelectable); self.file_list.addItem(item)
        else:
             for display_text, file_data in found_files:
                  item = QListWidgetItem(display_text); item.setData(Qt.UserRole, file_data); item.setToolTip(file_data['video_path']); self.file_list.addItem(item)
                  if file_data['video_path'] == current_selection_path: restored_selection_item = item

        print(f"Found {len(found_files)} video files.")

        if restored_selection_item: self.file_list.setCurrentItem(restored_selection_item); print(f"Restored selection: {restored_selection_item.text()}")
        elif self.file_list.count() > 0: self.file_list.setCurrentRow(0); print("Selected first item.")
        # Explicitly call on_selection_changed after potentially setting selection
        self.on_selection_changed()


    def is_video_file(self, filename):
        name, ext = os.path.splitext(filename);
        if not ext: return False
        if filename.startswith('.'): return False
        return ext.lower() in self.video_extensions

    def on_file_double_clicked(self, item):
        file_data = item.data(Qt.UserRole)
        if file_data and isinstance(file_data, dict) and os.path.isfile(file_data.get('video_path')): self.file_selected.emit(file_data['video_path'])
        else: print(f"Invalid data for double-click: {item.text()}")

    def get_selected_file_data(self):
        selected_items = self.file_list.selectedItems()
        file_data = None
        if selected_items: file_data = selected_items[0].data(Qt.UserRole)
        if file_data and isinstance(file_data, dict): return file_data
        return None

    def get_selected_file_path(self):
        file_data = self.get_selected_file_data()
        if file_data and os.path.isfile(file_data.get('video_path')): return file_data.get('video_path')
        return None

    # This slot is connected to currentItemChanged
    def on_selection_changed(self, current=None, previous=None):
        """Update button states based on current selection."""
        file_data = self.get_selected_file_data()
        print(f"Selection Changed. Data: {file_data is not None}")

        can_play = file_data is not None
        can_find_subs = file_data is not None
        # --- Change: Enable translate button simply if a video is selected ---
        can_translate = file_data is not None
        # --- End Change ---
        can_delete = file_data is not None

        self.play_button.setEnabled(can_play)
        self.find_subs_button.setEnabled(can_find_subs)
        self.translate_subs_button.setEnabled(can_translate)
        self.delete_button.setEnabled(can_delete)
        print(f" Buttons updated: Play={can_play}, Find={can_find_subs}, Translate={can_translate}, Delete={can_delete}")


    def play_selected(self):
        file_path = self.get_selected_file_path()
        if file_path: self.file_selected.emit(file_path)
        else: QMessageBox.information(self, self.tr("No Selection"), self.tr("Please select video to play."))

    def find_subtitles_for_selected(self):
        file_path = self.get_selected_file_path()
        if file_path: print(f"Requesting subs for: {file_path}"); self.find_subtitles_requested.emit(file_path)
        else: QMessageBox.information(self, self.tr("No Selection"), self.tr("Please select video to find subtitles for."))

    def translate_selected_subtitle(self):
        """Emit signal to translate the found source subtitle for the selected video."""
        file_data = self.get_selected_file_data()
        if file_data:
            source_srt_path = file_data.get('source_srt') # Get the automatically identified source srt path
            if source_srt_path and os.path.exists(source_srt_path):
                print(f"Requesting translation for automatically found source: {source_srt_path}")
                self.translate_subtitle_requested.emit(source_srt_path) # Emit identified SRT path
            else:
                # --- Add File Dialog Fallback ---
                print("No source subtitle automatically found, prompting user.")
                QMessageBox.information(self,
                    self.tr("Select Source Subtitle"),
                    self.tr("Could not automatically find an English (.en.srt) or generic (.srt) subtitle file to translate.\n\nPlease select the source subtitle file manually.")
                )
                video_path = file_data.get('video_path')
                start_dir = os.path.dirname(video_path) if video_path else self.current_directory
                # Ask user to select an SRT file
                manual_srt_path, _ = QFileDialog.getOpenFileName(
                    self,
                    self.tr("Select Source Subtitle File (.srt)"), # Dialog title
                    start_dir,                                   # Start in video directory
                    self.tr("Subtitle Files (*.srt)")            # Filter
                )
                if manual_srt_path and os.path.exists(manual_srt_path):
                     print(f"Requesting translation for manually selected file: {manual_srt_path}")
                     self.translate_subtitle_requested.emit(manual_srt_path) # Emit manually selected path
                else:
                     print("User did not select a valid manual subtitle file.")
                # --- End File Dialog Fallback ---
        else:
            QMessageBox.information(self, self.tr("No Selection"), self.tr("Please select a video file first."))


    def delete_selected(self):
        # ... (Delete logic remains the same) ...
        file_data = self.get_selected_file_data()
        if not file_data: QMessageBox.information(self, self.tr("No Selection"), self.tr("Select video to delete.")); return
        file_path = file_data.get('video_path')
        if not file_path or not os.path.exists(file_path): QMessageBox.warning(self, self.tr("Error"), self.tr("Selected video file path is invalid.")); return
        display_text = "selected file"; selected_items = self.file_list.selectedItems()
        if selected_items: display_text = selected_items[0].text().replace(self.tr(" [Sub]"), "").replace(self.tr(" [Translated Sub]"), "")
        reply = QMessageBox.question(self, self.tr("Confirm Deletion"), self.tr("Delete '{0}'\n(and ALL .srt files with the same name)?").format(display_text), QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                print(f"Deleting video file: {file_path}"); os.remove(file_path); deleted_subs = []
                base, _ = os.path.splitext(file_path); video_dir = os.path.dirname(file_path)
                for item in os.listdir(video_dir):
                     if item.startswith(os.path.basename(base)) and item.lower().endswith('.srt'):
                          sub_path = os.path.join(video_dir, item)
                          try: os.remove(sub_path); deleted_subs.append(item); print(f"Removed subtitle: {sub_path}")
                          except Exception as sub_e: print(f"Could not remove {sub_path}: {sub_e}"); QMessageBox.warning(self, self.tr("Subtitle Deletion Error"), self.tr("Could not delete:\n{0}\nError: {1}").format(item, sub_e))
                msg = self.tr("'{0}' deleted.").format(display_text);
                if deleted_subs: msg += self.tr("\nAlso deleted: {0}").format(', '.join(deleted_subs))
                QMessageBox.information(self, self.tr("Success"), msg); self.refresh_files()
            except PermissionError: QMessageBox.warning(self, self.tr("Permission Error"), self.tr("Cannot delete due to permissions."))
            except Exception as e: QMessageBox.critical(self, self.tr("Error Deleting File"), self.tr("Deletion error:\n{0}").format(e))

# --- END OF FILE source/file_browser.py ---