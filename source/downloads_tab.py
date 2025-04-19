# --- START OF FILE source/downloads_tab.py ---

"""
Downloads tab module for the Raspberry Pi Movie Player App.
Provides UI for searching, downloading, and managing torrents.
"""

import os
import math
import time
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                           QLineEdit, QTableWidget, QTableWidgetItem, QLabel,
                           QProgressBar, QHeaderView, QMessageBox, QComboBox,
                           QTabWidget, QSplitter, QFileDialog, QAbstractItemView)
from PyQt5.QtCore import Qt, pyqtSlot, QTimer
from PyQt5.QtGui import QPixmap, QIcon
import traceback # Added for better error printing if needed

from source.torrent_manager import TorrentSearcher, TorrentDownloader

class DownloadsTab(QWidget):
    """
    Tab for searching, downloading, and managing torrents.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # Set the default download directory
        self.download_dir = os.path.expanduser("~/Downloads/HackFlix")

        # Initialize the torrent search and download components
        self.searcher = TorrentSearcher()
        self.downloader = TorrentDownloader(self.download_dir)

        # Connect signals
        self.searcher.search_completed.connect(self.on_search_completed)
        self.searcher.search_error.connect(self.on_search_error)
        self.downloader.torrent_added.connect(self.on_torrent_added)
        self.downloader.torrent_updated.connect(self.on_torrent_updated)
        self.downloader.torrent_completed.connect(self.on_torrent_completed)
        self.downloader.torrent_error.connect(self.on_torrent_error)

        # Create the UI
        self.init_ui()

    def init_ui(self):
        """Initialize the user interface"""
        layout = QVBoxLayout()

        # Create a tab widget to separate search and downloads
        self.tab_widget = QTabWidget()

        # Create the search tab
        self.search_tab = QWidget()
        self.setup_search_tab()

        # Create the active downloads tab
        self.active_tab = QWidget()
        self.setup_active_tab()

        # Add tabs to the tab widget
        self.tab_widget.addTab(self.search_tab, self.tr("Search")) # Use tr()
        self.tab_widget.addTab(self.active_tab, self.tr("Downloads")) # Use tr()

        # Add settings section
        settings_layout = QHBoxLayout()

        # Use tr() for the static part of the label
        self.download_dir_label = QLabel(f"{self.tr('Download Directory')}: {self.download_dir}")
        self.change_dir_button = QPushButton(self.tr("Change Directory")) # Use tr()
        self.change_dir_button.clicked.connect(self.change_download_directory)

        settings_layout.addWidget(self.download_dir_label, 1) # Give label stretch factor
        settings_layout.addWidget(self.change_dir_button)

        # Add widgets to the main layout
        layout.addWidget(self.tab_widget)
        layout.addLayout(settings_layout)

        self.setLayout(layout)

        # Start a timer to update the UI (no text change needed)
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_download_status)
        self.timer.start(1000) # Update every second

    def setup_search_tab(self):
        """Set up the search tab UI"""
        layout = QVBoxLayout()

        # Search controls
        search_layout = QHBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(self.tr("Enter movie title...")) # Use tr()
        self.search_input.returnPressed.connect(self.search_torrents)

        self.search_button = QPushButton(self.tr("Search")) # Use tr()
        self.search_button.clicked.connect(self.search_torrents)

        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.search_button)

        # Search results table
        self.results_table = QTableWidget(0, 7)
        self.results_table.setHorizontalHeaderLabels([
            self.tr("Title"), self.tr("Quality"), self.tr("Size"), self.tr("Seeds"), # Use tr()
            self.tr("Peers"), self.tr("Rating"), self.tr("Download") # Use tr()
        ])
        self.results_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.results_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.results_table.verticalHeader().setVisible(False)

        # Status label
        self.status_label = QLabel(self.tr("Enter a movie title to search for torrents.")) # Use tr()

        # Add widgets to layout
        layout.addLayout(search_layout)
        layout.addWidget(self.results_table)
        layout.addWidget(self.status_label)

        self.search_tab.setLayout(layout)

    def setup_active_tab(self):
        """Set up the active downloads tab UI"""
        layout = QVBoxLayout()

        # Downloads table
        self.downloads_table = QTableWidget(0, 7)
        self.downloads_table.setHorizontalHeaderLabels([
            self.tr("Title"), self.tr("Status"), self.tr("Progress"), self.tr("Speed"), # Use tr()
            self.tr("ETA"), self.tr("Size"), self.tr("Actions") # Use tr()
        ])
        self.downloads_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.downloads_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.downloads_table.verticalHeader().setVisible(False)

        # No downloads message
        self.no_downloads_label = QLabel(self.tr("No active downloads.")) # Use tr()
        layout.addWidget(self.no_downloads_label)
        layout.addWidget(self.downloads_table)

        # Show/hide widgets based on current state
        self.downloads_table.setVisible(False)

        self.active_tab.setLayout(layout)

    def search_torrents(self):
        """Handle search button click"""
        query = self.search_input.text().strip()
        if not query:
            # Use tr() for message box text
            QMessageBox.warning(self, self.tr("Empty Query"), self.tr("Please enter a search term."))
            return

        # Status label update - use tr() for static part
        self.status_label.setText(self.tr("Searching for '{0}'...").format(query))
        self.search_button.setEnabled(False)
        self.results_table.setRowCount(0)

        # Perform the search
        self.searcher.search(query)

    @pyqtSlot(list)
    def on_search_completed(self, results):
        """Handle search results"""
        self.search_button.setEnabled(True)

        if not results:
            self.status_label.setText(self.tr("No results found.")) # Use tr()
            return

        # Update the status - use tr() for static part
        # Note: Qt might handle plurals with %n, but simple format is often sufficient
        self.status_label.setText(self.tr("Found {0} results.").format(len(results)))

        # Clear and populate the results table
        self.results_table.setRowCount(len(results))

        for row, result in enumerate(results):
            # Title - Dynamic, no tr()
            title_item = QTableWidgetItem(f"{result['title']} ({result['year']})")
            title_item.setData(Qt.UserRole, result)
            self.results_table.setItem(row, 0, title_item)

            # Quality - Dynamic, no tr()
            quality_item = QTableWidgetItem(result['quality'])
            self.results_table.setItem(row, 1, quality_item)

            # Size - Dynamic, no tr()
            size_item = QTableWidgetItem(result['size'])
            self.results_table.setItem(row, 2, size_item)

            # Seeds - Dynamic, no tr()
            seeds_item = QTableWidgetItem(str(result['seeds']))
            self.results_table.setItem(row, 3, seeds_item)

            # Peers - Dynamic, no tr()
            peers_item = QTableWidgetItem(str(result['peers']))
            self.results_table.setItem(row, 4, peers_item)

            # Rating - Dynamic, no tr()
            rating_item = QTableWidgetItem(f"{result['rating']}/10")
            self.results_table.setItem(row, 5, rating_item)

            # Download button - Use tr() for button text
            download_button = QPushButton(self.tr("Download"))
            download_button.clicked.connect(lambda checked, r=row: self.download_torrent(r))
            self.results_table.setCellWidget(row, 6, download_button)

    @pyqtSlot(str)
    def on_search_error(self, error_message):
        """Handle search errors"""
        self.search_button.setEnabled(True)
        # Use tr() for status prefix and message box title
        self.status_label.setText(f"{self.tr('Error')}: {error_message}")
        QMessageBox.critical(self, self.tr("Search Error"), error_message)

    def download_torrent(self, row):
        """Handle download button click"""
        item = self.results_table.item(row, 0)
        result = item.data(Qt.UserRole)

        torrent_hash = self.downloader.add_torrent(
            result['url'],
            result['hash'],
            result['title']
        )

        if torrent_hash:
            # Use tr() for message box text
            QMessageBox.information(
                self,
                self.tr("Download Started"), # Title
                # Message - Use tr() for static parts
                self.tr("Started downloading '{0}'\nFiles will be saved to {1}").format(result['title'], self.download_dir)
            )
            self.tab_widget.setCurrentWidget(self.active_tab)
        else:
            # Use tr() for message box text
            QMessageBox.critical(
                self,
                self.tr("Download Failed"), # Title
                 # Message - Use tr() for static parts
                self.tr("Failed to start downloading '{0}'").format(result['title'])
            )

    @pyqtSlot(dict)
    def on_torrent_added(self, torrent):
        """Handle new torrent added"""
        self.no_downloads_label.setVisible(False)
        self.downloads_table.setVisible(True)

        row = self.downloads_table.rowCount()
        self.downloads_table.insertRow(row)

        # Title (dynamic)
        self.downloads_table.setItem(row, 0, QTableWidgetItem(torrent['title']))
        self.downloads_table.item(row, 0).setData(Qt.UserRole, torrent['hash'])

        # Status (dynamic - consider translating common status strings if needed later)
        self.downloads_table.setItem(row, 1, QTableWidgetItem(torrent['status']))

        # Progress bar (visual)
        progress_bar = QProgressBar()
        progress_bar.setRange(0, 100)
        progress_bar.setValue(int(torrent['progress']))
        self.downloads_table.setCellWidget(row, 2, progress_bar)

        # Speed (dynamic)
        speed_text = self._format_speed(torrent['download_rate'])
        self.downloads_table.setItem(row, 3, QTableWidgetItem(speed_text))

        # ETA (dynamic, _format_time needs potential translation if returning strings like 'Unknown')
        eta_text = self._format_time(torrent['eta'])
        self.downloads_table.setItem(row, 4, QTableWidgetItem(eta_text))

        # Size (dynamic)
        size_text = self._format_size(torrent['total_size'])
        self.downloads_table.setItem(row, 5, QTableWidgetItem(size_text))

        # Actions
        actions_widget = QWidget()
        actions_layout = QHBoxLayout(actions_widget)
        actions_layout.setContentsMargins(2, 2, 2, 2)

        # Use tr() for button text
        pause_button = QPushButton(self.tr("Pause"))
        pause_button.clicked.connect(lambda: self.pause_torrent(torrent['hash']))

        remove_button = QPushButton(self.tr("Remove")) # Use tr()
        remove_button.clicked.connect(lambda: self.remove_torrent(torrent['hash']))

        actions_layout.addWidget(pause_button)
        actions_layout.addWidget(remove_button)

        self.downloads_table.setCellWidget(row, 6, actions_widget)

    @pyqtSlot(dict)
    def on_torrent_updated(self, torrent):
        """Handle torrent status update"""
        row = self._find_torrent_row(torrent['hash'])
        if row == -1: return

        # Status (dynamic, could translate specific statuses here if desired)
        status_item = self.downloads_table.item(row, 1)
        if status_item: status_item.setText(torrent['status'])

        # Progress bar
        progress_bar = self.downloads_table.cellWidget(row, 2)
        if progress_bar: progress_bar.setValue(int(torrent['progress']))

        # Speed
        speed_text = self._format_speed(torrent['download_rate'])
        speed_item = self.downloads_table.item(row, 3)
        if speed_item: speed_item.setText(speed_text)

        # ETA
        eta_text = self._format_time(torrent['eta'])
        eta_item = self.downloads_table.item(row, 4)
        if eta_item: eta_item.setText(eta_text)

        # Update actions button text based on status
        actions_widget = self.downloads_table.cellWidget(row, 6)
        if actions_widget:
            pause_button = actions_widget.layout().itemAt(0).widget()
            # Use tr() for button text states
            if torrent['status'] == 'paused':
                pause_button.setText(self.tr("Resume"))
                try: pause_button.clicked.disconnect() # Prevent multiple connections
                except TypeError: pass # Ignore if not connected
                pause_button.clicked.connect(lambda: self.resume_torrent(torrent['hash']))
            elif torrent['status'] == 'downloading':
                pause_button.setText(self.tr("Pause"))
                try: pause_button.clicked.disconnect()
                except TypeError: pass
                pause_button.clicked.connect(lambda: self.pause_torrent(torrent['hash']))
            else: # Handle other states (finished, seeding, error) - maybe disable pause/resume?
                 pause_button.setText(self.tr("Pause")) # Default text
                 pause_button.setEnabled(False) # Disable if not pausable


    @pyqtSlot(dict)
    def on_torrent_completed(self, torrent):
        """Handle torrent download completion"""
        # Use tr() for message box
        QMessageBox.information(
            self,
            self.tr("Download Complete"), # Title
            # Message - Use tr() for static parts
            self.tr("'{0}' has finished downloading.\nFile is available in {1}").format(torrent['title'], self.download_dir)
        )
        # Find row and disable pause/resume button
        row = self._find_torrent_row(torrent['hash'])
        if row != -1:
             actions_widget = self.downloads_table.cellWidget(row, 6)
             if actions_widget:
                 pause_button = actions_widget.layout().itemAt(0).widget()
                 pause_button.setEnabled(False)


    @pyqtSlot(str, str)
    def on_torrent_error(self, torrent_hash, error_message):
        """Handle torrent errors"""
        # Use tr() for title
        QMessageBox.warning(self, self.tr("Torrent Error"), error_message)
        # Find row and potentially update status visually
        row = self._find_torrent_row(torrent_hash)
        if row != -1:
            status_item = self.downloads_table.item(row, 1)
            if status_item: status_item.setText(self.tr("Error")) # Use tr()
            actions_widget = self.downloads_table.cellWidget(row, 6)
            if actions_widget:
                 pause_button = actions_widget.layout().itemAt(0).widget()
                 pause_button.setEnabled(False) # Disable actions on error

    def pause_torrent(self, torrent_hash):
        """Pause a torrent download"""
        self.downloader.pause_torrent(torrent_hash)

    def resume_torrent(self, torrent_hash):
        """Resume a torrent download"""
        self.downloader.resume_torrent(torrent_hash)

    def remove_torrent(self, torrent_hash):
        """Remove a torrent"""
        # Use tr() for message box text
        reply = QMessageBox.question(
            self,
            self.tr("Confirm Removal"), # Title
            self.tr("Do you want to remove the downloaded files as well?"), # Question
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
            # Standard button text (Yes/No/Cancel) should be translated by Qt base translations
        )

        if reply == QMessageBox.Cancel: return

        remove_files = (reply == QMessageBox.Yes)

        if self.downloader.remove_torrent(torrent_hash, remove_files):
            row = self._find_torrent_row(torrent_hash)
            if row != -1: self.downloads_table.removeRow(row)
            if self.downloads_table.rowCount() == 0:
                self.no_downloads_label.setVisible(True)
                self.downloads_table.setVisible(False)
        # No explicit error message here, downloader signal on_torrent_error handles failures

    def change_download_directory(self):
        """Change the download directory"""
        # Use tr() for dialog title
        dir_path = QFileDialog.getExistingDirectory(
            self, self.tr("Select Download Directory"), self.download_dir
        )

        if dir_path:
            self.download_dir = dir_path
            # Need to update downloader instance somehow, or recreate it?
            # For now, just update label. A restart might be needed for downloader change.
            # TODO: Implement dynamic download dir change in TorrentDownloader if needed
            print(f"Download directory selection changed to: {dir_path}")
            print("NOTE: Application restart might be needed for TorrentDownloader to use new directory.")
            # Update the label - use tr() for static part
            self.download_dir_label.setText(f"{self.tr('Download Directory')}: {self.download_dir}")

    def update_download_status(self):
        """Called by timer, actual updates are signal-driven."""
        pass # No direct UI updates needed here anymore

    def _find_torrent_row(self, torrent_hash):
        """Find the row index for a torrent in the downloads table"""
        for row in range(self.downloads_table.rowCount()):
            item = self.downloads_table.item(row, 0)
            if item and item.data(Qt.UserRole) == torrent_hash:
                return row
        return -1

    # --- Formatting functions - Mostly handle numbers, but ETA might need translation ---

    def _format_speed(self, bytes_per_second):
        """Format download speed in human-readable form"""
        # Units (B/s, KB/s, MB/s) could potentially be translated if needed,
        # but often kept standard for technical display.
        if bytes_per_second < 1024:
            return f"{bytes_per_second:.1f} B/s"
        elif bytes_per_second < 1024 * 1024:
            return f"{bytes_per_second / 1024:.1f} KB/s"
        else:
            return f"{bytes_per_second / (1024 * 1024):.1f} MB/s"

    def _format_size(self, bytes_size):
        """Format file size in human-readable form"""
        # Units (B, KB, MB, GB) usually kept standard.
        if bytes_size < 1024: return f"{bytes_size} B"
        elif bytes_size < 1024 * 1024: return f"{bytes_size / 1024:.1f} KB"
        elif bytes_size < 1024 * 1024 * 1024: return f"{bytes_size / (1024 * 1024):.1f} MB"
        else: return f"{bytes_size / (1024 * 1024 * 1024):.1f} GB"

    def _format_time(self, seconds):
        """Format time in human-readable form, handling infinite ETA."""
        if not isinstance(seconds, (int, float)) or seconds <= 0 or not math.isfinite(seconds):
            # Use tr() for the 'Unknown'/'Infinite' state placeholder if desired
            return self.tr("∞") # Or self.tr("Unknown"), self.tr("N/A")

        try:
            total_seconds = int(seconds)
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds_rem = divmod(remainder, 60)

            # Time units (d, h, m, s) could be translated if needed, but often kept short.
            if hours > 99: return f"{hours // 24}d {hours % 24}h"
            elif hours > 0: return f"{hours}h {minutes}m"
            elif minutes > 0: return f"{minutes}m {seconds_rem}s"
            else: return f"{seconds_rem}s"
        except OverflowError: return self.tr("∞") # Use tr()
        except ValueError: return self.tr("N/A") # Use tr()

    # Note: No closeEvent here, main app window handles shutdown signals

# --- END OF FILE source/downloads_tab.py ---