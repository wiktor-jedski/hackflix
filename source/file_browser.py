"""
File browser module for the Raspberry Pi Movie Player App.
Provides functionality for browsing and managing video files.
"""

import os
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, 
                           QPushButton, QListWidget, QListWidgetItem, QLabel, 
                           QFileDialog, QMessageBox)
from PyQt5.QtCore import Qt, pyqtSignal

class FileBrowser(QWidget):
    """
    A file browser component for managing video files in a directory.
    This will serve as the foundation for the library management feature.
    """
    
    # Signal to notify when a file is selected for playback
    file_selected = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Store the current directory path
        self.current_directory = os.path.expanduser("~")
        self.video_extensions = ['.mp4', '.avi', '.mkv', '.mov', '.wmv']
        
        # Create layout
        self.layout = QVBoxLayout()
        
        # Create directory selection button
        self.dir_button = QPushButton("Select Directory")
        self.dir_button.clicked.connect(self.select_directory)
        
        # Create path label
        self.path_label = QLabel(f"Current Directory: {self.current_directory}")
        
        # Create file list widget
        self.file_list = QListWidget()
        self.file_list.itemDoubleClicked.connect(self.on_file_double_clicked)
        
        # Create buttons for actions
        button_layout = QHBoxLayout()
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_files)
        self.play_button = QPushButton("Play Selected")
        self.play_button.clicked.connect(self.play_selected)
        self.delete_button = QPushButton("Delete Selected")
        self.delete_button.clicked.connect(self.delete_selected)
        
        button_layout.addWidget(self.refresh_button)
        button_layout.addWidget(self.play_button)
        button_layout.addWidget(self.delete_button)
        
        # Add widgets to layout
        self.layout.addWidget(self.dir_button)
        self.layout.addWidget(self.path_label)
        self.layout.addWidget(self.file_list)
        self.layout.addLayout(button_layout)
        
        self.setLayout(self.layout)
        
        # Populate the file list
        self.refresh_files()
    
    def select_directory(self):
        """Open a dialog to select a directory"""
        dir_path = QFileDialog.getExistingDirectory(self, "Select Directory", 
                                                  self.current_directory)
        if dir_path:
            self.current_directory = dir_path
            self.path_label.setText(f"Current Directory: {self.current_directory}")
            self.refresh_files()
    
    def refresh_files(self):
        """Scan the current directory for video files and populate the list"""
        self.file_list.clear()
        
        try:
            for filename in os.listdir(self.current_directory):
                file_path = os.path.join(self.current_directory, filename)
                if os.path.isfile(file_path) and self.is_video_file(filename):
                    item = QListWidgetItem(filename)
                    item.setData(Qt.UserRole, file_path)  # Store the full path
                    self.file_list.addItem(item)
        except PermissionError:
            QMessageBox.warning(self, "Permission Error", 
                             "Cannot access the selected directory due to permission issues.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred: {str(e)}")
    
    def is_video_file(self, filename):
        """Check if a file is a video file based on its extension"""
        extension = os.path.splitext(filename)[1].lower()
        return extension in self.video_extensions
    
    def on_file_double_clicked(self, item):
        """Handle double-click on a file item"""
        file_path = item.data(Qt.UserRole)
        self.file_selected.emit(file_path)
    
    def play_selected(self):
        """Play the selected file"""
        selected_items = self.file_list.selectedItems()
        if selected_items:
            file_path = selected_items[0].data(Qt.UserRole)
            self.file_selected.emit(file_path)
        else:
            QMessageBox.information(self, "No Selection", "Please select a video file first.")
    
    def delete_selected(self):
        """Delete the selected file"""
        selected_items = self.file_list.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "No Selection", "Please select a video file first.")
            return
        
        file_path = selected_items[0].data(Qt.UserRole)
        file_name = selected_items[0].text()
        
        # Confirm deletion
        reply = QMessageBox.question(self, "Confirm Deletion", 
                                  f"Are you sure you want to delete '{file_name}'?",
                                  QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            try:
                os.remove(file_path)
                QMessageBox.information(self, "Success", f"'{file_name}' has been deleted.")
                self.refresh_files()
            except PermissionError:
                QMessageBox.warning(self, "Permission Error", 
                                 "Cannot delete the file due to permission issues.")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"An error occurred: {str(e)}")
