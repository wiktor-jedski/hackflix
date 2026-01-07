"""
Error Dialog with Progressive Disclosure

Shows user-friendly error messages with option to view technical details.
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QWidget
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon


class ErrorDialog(QDialog):
    """
    Error dialog with progressive disclosure.

    Shows simple error message by default, with "Show Details" button
    to reveal full technical information.
    """

    def __init__(self, error_message, error_details=None, phase=None, parent=None):
        """
        Initialize error dialog.

        Args:
            error_message: User-friendly error message
            error_details: Full technical details (traceback, etc.)
            phase: Phase where error occurred ('video', 'subtitles', 'translation')
            parent: Parent widget
        """
        super().__init__(parent)
        self.error_message = error_message
        self.error_details = error_details
        self.phase = phase

        self._setup_ui()

    def _setup_ui(self):
        """Setup UI components"""
        # Window configuration
        self.setWindowTitle(self.tr("Download Error"))
        self.setMinimumWidth(500)

        layout = QVBoxLayout(self)

        # Error icon and message
        message_layout = QHBoxLayout()

        # Icon (using standard error icon)
        icon_label = QLabel()
        icon_label.setPixmap(
            self.style().standardIcon(self.style().SP_MessageBoxCritical).pixmap(48, 48)
        )
        icon_label.setAlignment(Qt.AlignTop)
        message_layout.addWidget(icon_label)

        # Message container
        message_container = QVBoxLayout()

        # Title
        if self.phase:
            phase_names = {
                'video': 'Video Download',
                'subtitles': 'Subtitle Download',
                'translation': 'Translation'
            }
            title_text = f"{phase_names.get(self.phase, 'Download')} Failed"
        else:
            title_text = "Download Failed"

        title_label = QLabel(f"<h3>{title_text}</h3>")
        message_container.addWidget(title_label)

        # Error message
        error_label = QLabel(self.error_message)
        error_label.setWordWrap(True)
        error_label.setStyleSheet("color: #ccc;")
        message_container.addWidget(error_label)

        message_layout.addLayout(message_container, 1)
        layout.addLayout(message_layout)

        # Details section (initially hidden)
        self.details_widget = QWidget()
        details_layout = QVBoxLayout(self.details_widget)
        details_layout.setContentsMargins(0, 10, 0, 0)

        details_label = QLabel(self.tr("<b>Technical Details:</b>"))
        details_layout.addWidget(details_label)

        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setMinimumHeight(200)
        self.details_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                font-family: 'Courier New', monospace;
                font-size: 10pt;
                border: 1px solid #444;
            }
        """)
        if self.error_details:
            self.details_text.setPlainText(self.error_details)
        else:
            self.details_text.setPlainText("No additional details available.")

        details_layout.addWidget(self.details_text)
        self.details_widget.setVisible(False)

        layout.addWidget(self.details_widget)

        # Buttons
        button_layout = QHBoxLayout()

        # Show/Hide Details button
        if self.error_details:
            self.details_button = QPushButton(self.tr("Show Details"))
            self.details_button.clicked.connect(self._toggle_details)
            button_layout.addWidget(self.details_button)

        button_layout.addStretch()

        # Retry button
        self.retry_button = QPushButton(self.tr("Retry"))
        self.retry_button.setDefault(False)
        button_layout.addWidget(self.retry_button)

        # Close button
        close_button = QPushButton(self.tr("Close"))
        close_button.setDefault(True)
        close_button.clicked.connect(self.reject)
        button_layout.addWidget(close_button)

        layout.addLayout(button_layout)

    def _toggle_details(self):
        """Toggle visibility of technical details"""
        is_visible = self.details_widget.isVisible()

        if is_visible:
            self.details_widget.setVisible(False)
            self.details_button.setText(self.tr("Show Details"))
            self.adjustSize()
        else:
            self.details_widget.setVisible(True)
            self.details_button.setText(self.tr("Hide Details"))
            # Expand window to show details
            self.resize(self.width(), self.height() + 250)

    def set_retry_handler(self, handler):
        """
        Set handler for retry button.

        Args:
            handler: Callable to invoke when retry is clicked
        """
        self.retry_button.clicked.connect(handler)
        self.retry_button.clicked.connect(self.accept)


def show_error_dialog(error_message, error_details=None, phase=None, parent=None, retry_handler=None):
    """
    Convenience function to show error dialog.

    Args:
        error_message: User-friendly error message
        error_details: Full technical details
        phase: Phase where error occurred
        parent: Parent widget
        retry_handler: Optional callback for retry button

    Returns:
        QDialog.Accepted if retry clicked, QDialog.Rejected otherwise
    """
    dialog = ErrorDialog(error_message, error_details, phase, parent)

    if retry_handler:
        dialog.set_retry_handler(retry_handler)
    else:
        # Hide retry button if no handler provided
        dialog.retry_button.setVisible(False)

    return dialog.exec_()
