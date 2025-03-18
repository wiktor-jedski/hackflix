import sys
import os
import vlc
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QPushButton, QFileDialog, QLabel, 
                            QSlider, QStyle, QSizePolicy)
from PyQt5.QtGui import QPalette, QColor
from PyQt5.QtCore import Qt, QTimer

class MediaPlayer(QMainWindow):
    """
    A basic media player implementation using python-vlc and PyQt5.
    This will serve as the core of our Raspberry Pi Movie Player App.
    """
    
    def __init__(self):
        super().__init__()
        
        # Set window properties
        self.setWindowTitle("Raspberry Pi Movie Player")
        self.setGeometry(100, 100, 800, 600)
        
        # Create VLC instance and media player
        self.instance = vlc.Instance()
        self.mediaplayer = self.instance.media_player_new()
        
        # Create a central widget to hold everything
        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        
        # Set the background color to black (better for video playback)
        self.palette = self.palette()
        self.palette.setColor(QPalette.Window, QColor(0, 0, 0))
        self.setPalette(self.palette)
        
        # Create the video widget
        self.video_frame = QWidget(self)
        self.video_frame.setAutoFillBackground(True)
        palette = self.video_frame.palette()
        palette.setColor(QPalette.Window, QColor(0, 0, 0))
        self.video_frame.setPalette(palette)
        
        # Create playback controls
        self.play_button = QPushButton()
        self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.play_button.clicked.connect(self.play_pause)
        
        self.stop_button = QPushButton()
        self.stop_button.setIcon(self.style().standardIcon(QStyle.SP_MediaStop))
        self.stop_button.clicked.connect(self.stop)
        
        self.open_button = QPushButton("Open File")
        self.open_button.clicked.connect(self.open_file)
        
        # Create slider for position
        self.position_slider = QSlider(Qt.Horizontal)
        self.position_slider.setMaximum(1000)
        self.position_slider.sliderMoved.connect(self.set_position)
        
        # Create time label
        self.time_label = QLabel("00:00 / 00:00")
        
        # Create layouts
        self.main_layout = QVBoxLayout()
        self.control_layout = QHBoxLayout()
        
        # Add widgets to layouts
        self.control_layout.addWidget(self.play_button)
        self.control_layout.addWidget(self.stop_button)
        self.control_layout.addWidget(self.open_button)
        self.control_layout.addWidget(self.position_slider)
        self.control_layout.addWidget(self.time_label)
        
        self.main_layout.addWidget(self.video_frame, 1)
        self.main_layout.addLayout(self.control_layout)
        
        # Set the layout
        self.central_widget.setLayout(self.main_layout)
        
        # Set up the timer for updating the UI
        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.update_ui)
        
        # Initialize playback state
        self.is_playing = False
        self.media = None
        
    def open_file(self):
        """Open a media file and start playback"""
        filepath, _ = QFileDialog.getOpenFileName(self, "Open File", os.path.expanduser('~'),
                                                "Video Files (*.mp4 *.avi *.mkv *.mov)")
        
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
            
            # Start playing
            self.play_pause()
            
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

def main():
    app = QApplication(sys.argv)
    player = MediaPlayer()
    player.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
