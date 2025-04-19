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
        # Use tr() for window title
        self.setWindowTitle(self.tr("Subtitle Search Results"))
        self.setMinimumSize(600, 400) # Set a reasonable minimum size

        self.results_data = results # Store the raw results

        # --- Layout ---
        layout = QVBoxLayout()

        # Use tr() for label text - uses format for number
        self.info_label = QLabel(self.tr("Found {0} subtitles. Select one to download.").format(len(results)))
        layout.addWidget(self.info_label)

        self.results_list = QListWidget()
        self.results_list.itemDoubleClicked.connect(self.download_selected_subtitle) # Allow double-click download
        layout.addWidget(self.results_list)

        button_layout = QHBoxLayout()
        # Use tr() for button text
        self.download_button = QPushButton(self.tr("Download Selected"))
        self.download_button.clicked.connect(self.download_selected_subtitle)
        # Use tr() for button text (though Qt base translation might handle this one)
        self.cancel_button = QPushButton(self.tr("Cancel"))
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
            # Use tr() for message
            item = QListWidgetItem(self.tr("No subtitles found matching your criteria."))
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable) # Make it unselectable
            self.results_list.addItem(item)
            self.download_button.setEnabled(False)
            return

        self.download_button.setEnabled(True)
        for res in self.results_data:
            # Format the display string for the list item
            lang = res.get('language', self.tr('N/A')).upper() # Use tr() for fallback N/A
            release = res.get('release', self.tr('Unknown Release')) # Use tr() for fallback
            filename = res.get('file_name', '')
            rating = res.get('ratings', 0)
            votes = res.get('votes', 0)
            hd = "[HD]" if res.get('hd') else ""
            hi = self.tr("[HI]") if res.get('hearing_impaired') else "" # Use tr() for marker
            trusted = self.tr("[T]") if res.get('from_trusted') else "" # Use tr() for marker

            # Prioritize showing release name, fallback to filename
            display_name = release if release != self.tr('Unknown Release') else filename
            if not display_name: display_name = self.tr("Unnamed Subtitle") # Use tr() for fallback

            # Use tr() for the label parts of the string template
            display_text = f"[{lang}] {display_name} {hd}{hi}{trusted} ({self.tr('Rating')}: {rating:.1f}, {self.tr('Votes')}: {votes})"

            item = QListWidgetItem(display_text)
            item.setData(Qt.UserRole, res) # Store the full result dictionary

            # Tooltip (Use tr() for labels)
            tooltip_text = f"{self.tr('Filename')}: {filename}\n" \
                           f"{self.tr('Language')}: {lang}\n" \
                           f"{self.tr('Release')}: {release}\n" \
                           f"{self.tr('Rating')}: {rating:.1f} ({votes} {self.tr('votes')})\n" \
                           f"{self.tr('HD')}: {res.get('hd', False)}, {self.tr('HI')}: {res.get('hearing_impaired', False)}\n" \
                           f"{self.tr('Uploader')}: {res.get('uploader', self.tr('N/A'))}\n" \
                           f"{self.tr('File ID')}: {res.get('file_id')}"
            item.setToolTip(tooltip_text)

            self.results_list.addItem(item)

        if self.results_list.count() > 0:
            self.results_list.setCurrentRow(0)


    def download_selected_subtitle(self):
        """Gets the selected subtitle and emits the signal."""
        selected_items = self.results_list.selectedItems()
        if not selected_items:
            # Use tr() for message box
            QMessageBox.warning(self,
                self.tr("No Selection"),
                self.tr("Please select a subtitle from the list.")
            )
            return

        selected_result_dict = selected_items[0].data(Qt.UserRole)

        if not selected_result_dict or 'file_id' not in selected_result_dict:
             # Use tr() for message box
             QMessageBox.critical(self,
                 self.tr("Error"),
                 self.tr("Selected item has invalid data. Cannot download.")
             )
             return

        self.subtitle_selected_for_download.emit(selected_result_dict)
        self.accept() # Close the dialog successfully

# --- END OF FILE source/subtitle_dialog.py ---