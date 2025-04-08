# --- START OF FILE source/subtitle_dialog.py ---

"""
Dialog for displaying subtitle search results and selecting one for download.
"""

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QListWidget,
                           QListWidgetItem, QPushButton, QLabel, QMessageBox)
from PyQt5.QtCore import Qt, pyqtSignal

class SubtitleResultsDialog(QDialog):
    """
    Dialog to show subtitle search results from OpenSubtitles.
    Emits a signal when a subtitle is selected for download.
    """
    # Signal carries the dictionary of the selected subtitle result
    subtitle_selected_for_download = pyqtSignal(dict)

    def __init__(self, results, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Subtitle Search Results")
        self.setMinimumSize(600, 400) # Set a reasonable minimum size

        self.results_data = results # Store the raw results

        # --- Layout ---
        layout = QVBoxLayout()

        self.info_label = QLabel(f"Found {len(results)} subtitles. Select one to download.")
        layout.addWidget(self.info_label)

        self.results_list = QListWidget()
        self.results_list.itemDoubleClicked.connect(self.download_selected_subtitle) # Allow double-click download
        layout.addWidget(self.results_list)

        button_layout = QHBoxLayout()
        self.download_button = QPushButton("Download Selected")
        self.download_button.clicked.connect(self.download_selected_subtitle)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject) # Close dialog without action

        button_layout.addStretch()
        button_layout.addWidget(self.download_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)

        self.setLayout(layout)

        # Populate the list widget
        self.populate_results()

    def populate_results(self):
        """Fills the list widget with formatted subtitle results."""
        self.results_list.clear()
        if not self.results_data:
            item = QListWidgetItem("No subtitles found matching your criteria.")
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable) # Make it unselectable
            self.results_list.addItem(item)
            self.download_button.setEnabled(False)
            return

        self.download_button.setEnabled(True)
        for res in self.results_data:
            # Format the display string for the list item
            lang = res.get('language', 'N/A').upper()
            release = res.get('release', 'Unknown Release')
            filename = res.get('file_name', '')
            rating = res.get('ratings', 0)
            votes = res.get('votes', 0)
            hd = "[HD]" if res.get('hd') else ""
            hi = "[HI]" if res.get('hearing_impaired') else "" # Hearing Impaired
            trusted = "[T]" if res.get('from_trusted') else "" # Trusted source

            # Prioritize showing release name, fallback to filename
            display_name = release if release != 'Unknown Release' else filename
            if not display_name: display_name = "Unnamed Subtitle" # Further fallback

            display_text = f"[{lang}] {display_name} {hd}{hi}{trusted} (Rating: {rating:.1f}, Votes: {votes})"

            item = QListWidgetItem(display_text)
            # Store the full result dictionary with the item
            item.setData(Qt.UserRole, res)
            # Add tooltip for more details?
            tooltip_text = f"Filename: {filename}\n" \
                           f"Language: {lang}\n" \
                           f"Release: {release}\n" \
                           f"Rating: {rating:.1f} ({votes} votes)\n" \
                           f"HD: {res.get('hd', False)}, HI: {res.get('hearing_impaired', False)}\n" \
                           f"Uploader: {res.get('uploader', 'N/A')}\n" \
                           f"File ID: {res.get('file_id')}"
            item.setToolTip(tooltip_text)

            self.results_list.addItem(item)

        # Select the first item by default
        if self.results_list.count() > 0:
            self.results_list.setCurrentRow(0)


    def download_selected_subtitle(self):
        """Gets the selected subtitle and emits the signal."""
        selected_items = self.results_list.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select a subtitle from the list.")
            return

        selected_result_dict = selected_items[0].data(Qt.UserRole)

        if not selected_result_dict or 'file_id' not in selected_result_dict:
             QMessageBox.critical(self, "Error", "Selected item has invalid data. Cannot download.")
             return

        # Emit the signal with the data
        self.subtitle_selected_for_download.emit(selected_result_dict)
        self.accept() # Close the dialog successfully