"""
Video frame module for the Raspberry Pi Movie Player App.
Provides a widget for displaying video content.
"""

from PyQt5.QtWidgets import QWidget, QSizePolicy
from PyQt5.QtGui import QPalette, QColor

class VideoFrame(QWidget):
    """Widget for displaying video content"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(QPalette.Window, QColor(0, 0, 0))
        self.setPalette(palette)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
