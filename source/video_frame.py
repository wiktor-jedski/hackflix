# --- START OF FILE source/video_frame.py ---

"""
Video frame module for the Raspberry Pi Movie Player App.
Provides a widget for displaying video content.
"""

from PyQt5.QtWidgets import QWidget, QSizePolicy, QApplication
from PyQt5.QtGui import QPalette, QColor, QCursor
from PyQt5.QtCore import Qt, pyqtSignal


class VideoFrame(QWidget):
    """Widget for displaying video content"""

    # Signal emitted when the widget is double-clicked
    doubleClicked = pyqtSignal()
    # Signal emitted when the mouse moves over this widget
    mouseMoved = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(QPalette.Window, QColor(0, 0, 0))
        self.setPalette(palette)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # Enable mouse tracking to receive move events even when no button is pressed
        self.setMouseTracking(True)
        # Explicitly set background to black (helps override themes sometimes)
        self.setStyleSheet("background-color: black;")
        print("VideoFrame Initialized and Mouse Tracking Enabled.") # Debug Init

    def mouseDoubleClickEvent(self, event):
        """Override to detect double-clicks."""
        print("VideoFrame Double Click Detected.") # Debug Event
        if event.button() == Qt.LeftButton:
            self.doubleClicked.emit()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

    def mouseMoveEvent(self, event):
        """Emit signal when mouse moves over the frame."""
        # print("VideoFrame Mouse Move Detected.") # Debug Event (can be very verbose)
        self.mouseMoved.emit()
        # Call super just in case event propagation matters for other things
        super().mouseMoveEvent(event)
        # event.accept() # Usually don't accept here if calling super
