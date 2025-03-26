"""
Main application module for the Raspberry Pi Movie Player App.
Integrates media playback with library management and other features.
"""

import sys
import os
import vlc
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, 
                           QHBoxLayout, QPushButton, QLabel, 
                           QSlider, QStyle, QStackedWidget, 
                           QTabWidget)
from PyQt5.QtCore import Qt, QTimer

# Import local modules
from source.video_frame import VideoFrame
from source.file_browser import FileBrowser
from source.downloads_tab import DownloadsTab
from source.placeholder_tabs import SubtitlesTab, SuggestionsTab

class MoviePlayerApp(QMainWindow):
    """
    Main application window for the Raspberry Pi Movie Player App.
    Integrates media playback with library management and other features.
    """
    
    def __init__(self):
        super().__init__()
        
        # Set window properties
        self.setWindowTitle("Raspberry Pi Movie Player")
        self.setGeometry(100, 100, 1024, 768)
        
        # Create VLC instance and media player
        self.instance = vlc.Instance()
        self.mediaplayer = self.instance.media_player_new()
        
        # Create a central widget and main layout
        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        
        # Create a stacked widget to switch between player and browser views
        self.stacked_widget = QStackedWidget()
        
        # Create the player view
        self.player_widget = QWidget()
        self.player_layout = QVBoxLayout(self.player_widget)
        
        # Create the video frame
        self.video_frame = VideoFrame()
        
        # Create playback controls
        self.control_widget = QWidget()
        self.control_layout = QHBoxLayout(self.control_widget)
        
        self.play_button = QPushButton()
        self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.play_button.clicked.connect(self.play_pause)
        
        self.stop_button = QPushButton()
        self.stop_button.setIcon(self.style().standardIcon(QStyle.SP_MediaStop))
        self.stop_button.clicked.connect(self.stop)
        
        self.position_slider = QSlider(Qt.Horizontal)
        self.position_slider.setMaximum(1000)
        self.position_slider.sliderMoved.connect(self.set_position)
        
        self.time_label = QLabel("00:00 / 00:00")
        self.back_button = QPushButton("Back to Library")
        self.back_button.clicked.connect(self.show_browser)
        
        # Add controls to layout
        self.control_layout.addWidget(self.play_button)
        self.control_layout.addWidget(self.stop_button)
        self.control_layout.addWidget(self.position_slider)
        self.control_layout.addWidget(self.time_label)
        self.control_layout.addWidget(self.back_button)
        
        # Add widgets to player layout
        self.player_layout.addWidget(self.video_frame)
        self.player_layout.addWidget(self.control_widget)
        
        # Create the browser view with tabs
        self.browser_widget = QWidget()
        self.browser_layout = QVBoxLayout(self.browser_widget)
        
        # Create tab widget
        self.tab_widget = QTabWidget()
        
        # Create tabs
        self.library_tab = FileBrowser()
        self.library_tab.file_selected.connect(self.play_file)
        
        self.downloads_tab = DownloadsTab()
        self.subtitles_tab = SubtitlesTab()
        self.suggestions_tab = SuggestionsTab()
        
        # Add tabs to the tab widget
        self.tab_widget.addTab(self.library_tab, "Library")
        self.tab_widget.addTab(self.downloads_tab, "Downloads")
        self.tab_widget.addTab(self.subtitles_tab, "Subtitles")
        self.tab_widget.addTab(self.suggestions_tab, "Suggestions")
        
        # Add tab widget to browser layout
        self.browser_layout.addWidget(self.tab_widget)
        
        # Add widgets to stacked widget
        self.stacked_widget.addWidget(self.browser_widget)
        self.stacked_widget.addWidget(self.player_widget)
        
        # Add stacked widget to main layout
        self.main_layout.addWidget(self.stacked_widget)
        
        # Show the browser view by default
        self.stacked_widget.setCurrentWidget(self.browser_widget)
        
        # Set up the timer for updating the UI
        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.update_ui)
        
        # Initialize playback state
        self.is_playing = False
        self.media = None
    
    def play_file(self, filepath):
        """Play a media file and switch to the player view"""
        if filepath:
            # Create a VLC media object from the file
            self.media = self.instance.media_new(filepath)
            
            # Set the media to the player
            self.mediaplayer.set_media(self.media)
            
            # Pass the window ID to the player
            if sys.platform.startswith('linux'):  # for Linux
                self.mediaplayer.set_xwindow(int(self.video_frame.winId()))
            elif sys.platform == "win32":  # for Windows
                self.mediaplayer.set_hwnd(int(self.video_frame.winId()))
            elif sys.platform == "darwin":  # for MacOS
                self.mediaplayer.set_nsobject(int(self.video_frame.winId()))
            
            # Switch to the player view
            self.stacked_widget.setCurrentWidget(self.player_widget)
            
            # Start playing
            self.mediaplayer.play()
            self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
            self.is_playing = True
            self.timer.start()
            
            # Update window title with the filename
            self.setWindowTitle(f"Raspberry Pi Movie Player - {os.path.basename(filepath)}")
    
    def play_pause(self):
        """Toggle play/pause status"""
        if self.mediaplayer.is_playing():
            self.mediaplayer.pause()
            self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
            self.is_playing = False
            self.timer.stop()
        else:
            if self.media:
                self.mediaplayer.play()
                self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
                self.is_playing = True
                self.timer.start()
    
    def stop(self):
        """Stop player"""
        self.mediaplayer.stop()
        self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.is_playing = False
        self.timer.stop()
    
    def update_ui(self):
        """Update the UI with current playback status"""
        # Update the slider position
        media_position = int(self.mediaplayer.get_position() * 1000)
        self.position_slider.setValue(media_position)
        
        # Update the time display
        if self.mediaplayer.get_length() > 0:
            current_secs = self.mediaplayer.get_time() // 1000
            total_secs = self.mediaplayer.get_length() // 1000
            
            current_time = f"{current_secs // 60:02d}:{current_secs % 60:02d}"
            total_time = f"{total_secs // 60:02d}:{total_secs % 60:02d}"
            
            self.time_label.setText(f"{current_time} / {total_time}")
    
    def set_position(self, position):
        """Set the player position according to the slider value"""
        self.mediaplayer.set_position(position / 1000.0)
    
    def show_browser(self):
        """Switch back to browser view"""
        self.stop()
        self.stacked_widget.setCurrentWidget(self.browser_widget)
        self.setWindowTitle("Raspberry Pi Movie Player")
