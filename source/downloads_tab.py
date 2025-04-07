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
        self.tab_widget.addTab(self.search_tab, "Search")
        self.tab_widget.addTab(self.active_tab, "Downloads")
        
        # Add settings section
        settings_layout = QHBoxLayout()
        
        self.download_dir_label = QLabel(f"Download Directory: {self.download_dir}")
        self.change_dir_button = QPushButton("Change Directory")
        self.change_dir_button.clicked.connect(self.change_download_directory)
        
        settings_layout.addWidget(self.download_dir_label)
        settings_layout.addWidget(self.change_dir_button)
        
        # Add widgets to the main layout
        layout.addWidget(self.tab_widget)
        layout.addLayout(settings_layout)
        
        self.setLayout(layout)
        
        # Start a timer to update the UI
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_download_status)
        self.timer.start(1000)  # Update every second
    
    def setup_search_tab(self):
        """Set up the search tab UI"""
        layout = QVBoxLayout()
        
        # Search controls
        search_layout = QHBoxLayout()
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Enter movie title...")
        self.search_input.returnPressed.connect(self.search_torrents)
        
        self.search_button = QPushButton("Search")
        self.search_button.clicked.connect(self.search_torrents)
        
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(self.search_button)
        
        # Search results table
        self.results_table = QTableWidget(0, 7)
        self.results_table.setHorizontalHeaderLabels([
            "Title", "Quality", "Size", "Seeds", "Peers", "Rating", "Download"
        ])
        self.results_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.results_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.results_table.verticalHeader().setVisible(False)
        
        # Status label
        self.status_label = QLabel("Enter a movie title to search for torrents.")
        
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
            "Title", "Status", "Progress", "Speed", "ETA", "Size", "Actions"
        ])
        self.downloads_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.downloads_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.downloads_table.verticalHeader().setVisible(False)
        
        # No downloads message
        self.no_downloads_label = QLabel("No active downloads.")
        layout.addWidget(self.no_downloads_label)
        layout.addWidget(self.downloads_table)
        
        # Show/hide widgets based on current state
        self.downloads_table.setVisible(False)
        
        self.active_tab.setLayout(layout)
    
    def search_torrents(self):
        """Handle search button click"""
        query = self.search_input.text().strip()
        if not query:
            QMessageBox.warning(self, "Empty Query", "Please enter a search term.")
            return
        
        # Show searching status
        self.status_label.setText(f"Searching for '{query}'...")
        self.search_button.setEnabled(False)
        self.results_table.setRowCount(0)
        
        # Perform the search
        self.searcher.search(query)
    
    @pyqtSlot(list)
    def on_search_completed(self, results):
        """Handle search results"""
        self.search_button.setEnabled(True)
        
        if not results:
            self.status_label.setText("No results found.")
            return
        
        # Update the status
        self.status_label.setText(f"Found {len(results)} results.")
        
        # Clear and populate the results table
        self.results_table.setRowCount(len(results))
        
        for row, result in enumerate(results):
            # Title
            title_item = QTableWidgetItem(f"{result['title']} ({result['year']})")
            title_item.setData(Qt.UserRole, result)  # Store the full result data
            self.results_table.setItem(row, 0, title_item)
            
            # Quality
            quality_item = QTableWidgetItem(result['quality'])
            self.results_table.setItem(row, 1, quality_item)
            
            # Size
            size_item = QTableWidgetItem(result['size'])
            self.results_table.setItem(row, 2, size_item)
            
            # Seeds
            seeds_item = QTableWidgetItem(str(result['seeds']))
            self.results_table.setItem(row, 3, seeds_item)
            
            # Peers
            peers_item = QTableWidgetItem(str(result['peers']))
            self.results_table.setItem(row, 4, peers_item)
            
            # Rating
            rating_item = QTableWidgetItem(f"{result['rating']}/10")
            self.results_table.setItem(row, 5, rating_item)
            
            # Download button
            download_button = QPushButton("Download")
            download_button.clicked.connect(lambda checked, r=row: self.download_torrent(r))
            self.results_table.setCellWidget(row, 6, download_button)
    
    @pyqtSlot(str)
    def on_search_error(self, error_message):
        """Handle search errors"""
        self.search_button.setEnabled(True)
        self.status_label.setText(f"Error: {error_message}")
        QMessageBox.critical(self, "Search Error", error_message)
    
    def download_torrent(self, row):
        """Handle download button click"""
        # Get the torrent data
        item = self.results_table.item(row, 0)
        result = item.data(Qt.UserRole)
        
        # Add the torrent to the downloader
        torrent_hash = self.downloader.add_torrent(
            result['url'],
            result['hash'],
            result['title']
        )
        
        if torrent_hash:
            QMessageBox.information(
                self, "Download Started", 
                f"Started downloading '{result['title']}'\nFiles will be saved to {self.download_dir}"
            )
            
            # Switch to the active downloads tab
            self.tab_widget.setCurrentWidget(self.active_tab)
        else:
            QMessageBox.critical(
                self, "Download Failed", 
                f"Failed to start downloading '{result['title']}'"
            )
    
    @pyqtSlot(dict)
    def on_torrent_added(self, torrent):
        """Handle new torrent added"""
        # Hide the no downloads label and show the table
        self.no_downloads_label.setVisible(False)
        self.downloads_table.setVisible(True)
        
        # Add the torrent to the downloads table
        row = self.downloads_table.rowCount()
        self.downloads_table.insertRow(row)
        
        # Set the torrent hash as row identifier
        self.downloads_table.setItem(row, 0, QTableWidgetItem(torrent['title']))
        self.downloads_table.item(row, 0).setData(Qt.UserRole, torrent['hash'])
        
        # Add remaining columns
        self.downloads_table.setItem(row, 1, QTableWidgetItem(torrent['status']))
        
        # Progress bar
        progress_bar = QProgressBar()
        progress_bar.setRange(0, 100)
        progress_bar.setValue(int(torrent['progress']))
        self.downloads_table.setCellWidget(row, 2, progress_bar)
        
        # Speed
        speed_text = self._format_speed(torrent['download_rate'])
        self.downloads_table.setItem(row, 3, QTableWidgetItem(speed_text))
        
        # ETA
        eta_text = self._format_time(torrent['eta'])
        self.downloads_table.setItem(row, 4, QTableWidgetItem(eta_text))
        
        # Size
        size_text = self._format_size(torrent['total_size'])
        self.downloads_table.setItem(row, 5, QTableWidgetItem(size_text))
        
        # Actions
        actions_widget = QWidget()
        actions_layout = QHBoxLayout(actions_widget)
        actions_layout.setContentsMargins(2, 2, 2, 2)
        
        pause_button = QPushButton("Pause")
        pause_button.clicked.connect(lambda: self.pause_torrent(torrent['hash']))
        
        remove_button = QPushButton("Remove")
        remove_button.clicked.connect(lambda: self.remove_torrent(torrent['hash']))
        
        actions_layout.addWidget(pause_button)
        actions_layout.addWidget(remove_button)
        
        self.downloads_table.setCellWidget(row, 6, actions_widget)
    
    @pyqtSlot(dict)
    def on_torrent_updated(self, torrent):
        """Handle torrent status update"""
        # Find the row for this torrent
        row = self._find_torrent_row(torrent['hash'])
        if row == -1:
            return
        
        # Update the status
        status_item = self.downloads_table.item(row, 1)
        if status_item:
            status_item.setText(torrent['status'])
        
        # Update the progress bar
        progress_bar = self.downloads_table.cellWidget(row, 2)
        if progress_bar:
            progress_bar.setValue(int(torrent['progress']))
        
        # Update the speed
        speed_text = self._format_speed(torrent['download_rate'])
        speed_item = self.downloads_table.item(row, 3)
        if speed_item:
            speed_item.setText(speed_text)
        
        # Update the ETA
        eta_text = self._format_time(torrent['eta'])
        eta_item = self.downloads_table.item(row, 4)
        if eta_item:
            eta_item.setText(eta_text)
        
        # Update actions based on status
        actions_widget = self.downloads_table.cellWidget(row, 6)
        if actions_widget:
            pause_button = actions_widget.layout().itemAt(0).widget()
            if torrent['status'] == 'paused':
                pause_button.setText("Resume")
                pause_button.clicked.disconnect()
                pause_button.clicked.connect(lambda: self.resume_torrent(torrent['hash']))
            elif torrent['status'] == 'downloading':
                pause_button.setText("Pause")
                pause_button.clicked.disconnect()
                pause_button.clicked.connect(lambda: self.pause_torrent(torrent['hash']))
    
    @pyqtSlot(dict)
    def on_torrent_completed(self, torrent):
        """Handle torrent download completion"""
        # Show notification
        QMessageBox.information(
            self, "Download Complete", 
            f"'{torrent['title']}' has finished downloading.\nFile is available in {self.download_dir}"
        )
    
    @pyqtSlot(str, str)
    def on_torrent_error(self, torrent_hash, error_message):
        """Handle torrent errors"""
        QMessageBox.warning(self, "Torrent Error", error_message)
    
    def pause_torrent(self, torrent_hash):
        """Pause a torrent download"""
        self.downloader.pause_torrent(torrent_hash)
    
    def resume_torrent(self, torrent_hash):
        """Resume a torrent download"""
        self.downloader.resume_torrent(torrent_hash)
    
    def remove_torrent(self, torrent_hash):
        """Remove a torrent"""
        # Ask for confirmation
        reply = QMessageBox.question(
            self, "Confirm Removal", 
            "Do you want to remove the downloaded files as well?",
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
        )
        
        if reply == QMessageBox.Cancel:
            return
        
        remove_files = (reply == QMessageBox.Yes)
        
        # Remove the torrent
        if self.downloader.remove_torrent(torrent_hash, remove_files):
            # Find and remove from the table
            row = self._find_torrent_row(torrent_hash)
            if row != -1:
                self.downloads_table.removeRow(row)
            
            # Show the no downloads label if there are no more downloads
            if self.downloads_table.rowCount() == 0:
                self.no_downloads_label.setVisible(True)
                self.downloads_table.setVisible(False)
    
    def change_download_directory(self):
        """Change the download directory"""
        dir_path = QFileDialog.getExistingDirectory(
            self, "Select Download Directory", self.download_dir
        )
        
        if dir_path:
            # Update the downloader's directory
            self.download_dir = dir_path
            self.downloader.download_dir = dir_path
            
            # Update the label
            self.download_dir_label.setText(f"Download Directory: {self.download_dir}")
    
    def update_download_status(self):
        """Update the download status in the UI"""
        # This method is called by the timer
        # The actual updates are handled by the signals from the downloader
        pass
    
    def _find_torrent_row(self, torrent_hash):
        """Find the row index for a torrent in the downloads table"""
        for row in range(self.downloads_table.rowCount()):
            item = self.downloads_table.item(row, 0)
            if item and item.data(Qt.UserRole) == torrent_hash:
                return row
        return -1
    
    def _format_speed(self, bytes_per_second):
        """Format download speed in human-readable form"""
        if bytes_per_second < 1024:
            return f"{bytes_per_second:.1f} B/s"
        elif bytes_per_second < 1024 * 1024:
            return f"{bytes_per_second / 1024:.1f} KB/s"
        else:
            return f"{bytes_per_second / (1024 * 1024):.1f} MB/s"
    
    def _format_size(self, bytes_size):
        """Format file size in human-readable form"""
        if bytes_size < 1024:
            return f"{bytes_size} B"
        elif bytes_size < 1024 * 1024:
            return f"{bytes_size / 1024:.1f} KB"
        elif bytes_size < 1024 * 1024 * 1024:
            return f"{bytes_size / (1024 * 1024):.1f} MB"
        else:
            return f"{bytes_size / (1024 * 1024 * 1024):.1f} GB"
    
    def _format_time(self, seconds):
        """Format time in human-readable form, handling infinite ETA."""
        # Check for invalid, zero, negative, or infinite values first
        if not isinstance(seconds, (int, float)) or seconds <= 0 or not math.isfinite(seconds):
            # Return a suitable placeholder for unknown/infinite ETA
            # '∞' is the infinity symbol, looks good if font supports it.
            # Alternatives: "-", "N/A", "Unknown", "Stalled"
            return "∞"

        # If we reach here, seconds is a positive finite number
        try:
            total_seconds = int(seconds) # Safe to convert now
            hours, remainder = divmod(total_seconds, 3600)
            minutes, seconds_rem = divmod(remainder, 60) # Use a different var name

            if hours > 99: # Avoid excessively long strings for very long ETAs
                return f"{hours // 24}d {hours % 24}h" # Example: Show days/hours
            elif hours > 0:
                return f"{hours}h {minutes}m"
            elif minutes > 0:
                return f"{minutes}m {seconds_rem}s"
            else:
                return f"{seconds_rem}s"
        except OverflowError:
            # Catch overflow for extremely large, but finite, numbers
            return "∞" # Or ">99d" or similar indicator
        except ValueError:
             # Catch unexpected errors during calculation
             return "N/A"
    
    def closeEvent(self, event):
        """Handle the tab close event"""
        # Shutdown the downloader gracefully
        self.downloader.shutdown()
        self.timer.stop()
        event.accept()
