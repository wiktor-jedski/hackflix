"""
Video frame module for the Raspberry Pi Movie Player App.
Provides a widget for displaying video content.
"""

from PyQt5.QtWidgets import QWidget, QSizePolicy, QApplication
from PyQt5.QtGui import QPalette, QColor
from PyQt5.QtCore import Qt, pyqtSignal # Import Qt, pyqtSignal

class VideoFrame(QWidget):
    """Widget for displaying video content"""

    # Signal emitted when the widget is double-clicked
    doubleClicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(QPalette.Window, QColor(0, 0, 0))
        self.setPalette(palette)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        # Crucial: Accept mouse events to detect double-clicks
        self.setMouseTracking(True)

    def mouseDoubleClickEvent(self, event):
        """Override to detect double-clicks."""
        if event.button() == Qt.LeftButton:
            self.doubleClicked.emit()
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

    # Optional: Add visual feedback on hover to indicate interactivity
    def enterEvent(self, event):
        QApplication.setOverrideCursor(Qt.PointingHandCursor)
        super().enterEvent(event)

    def leaveEvent(self, event):
        QApplication.restoreOverrideCursor()
        super().leaveEvent(event)

    