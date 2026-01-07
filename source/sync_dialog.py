"""
Catalog sync progress dialog

Provides UI for catalog synchronization with:
- Real-time progress tracking
- Success/error status display
- Detailed log output (collapsible)
- Background thread execution
- Modal dialog with close prevention during sync
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QProgressBar,
    QPushButton, QTextEdit
)
from PyQt5.QtCore import Qt, QThread, pyqtSlot
import traceback


class SyncWorker(QThread):
    """Worker thread for catalog sync"""

    def __init__(self, catalog_manager):
        """
        Initialize sync worker

        Args:
            catalog_manager: CatalogManager instance to use for syncing
        """
        super().__init__()
        self.catalog_manager = catalog_manager

    def run(self):
        """Execute sync in background thread"""
        try:
            self.catalog_manager.sync_catalog()
        except Exception as e:
            print(f"Sync worker error: {e}")
            traceback.print_exc()


class SyncDialog(QDialog):
    """Progress dialog for catalog synchronization"""

    def __init__(self, catalog_manager, parent=None):
        """
        Initialize sync dialog

        Args:
            catalog_manager: CatalogManager instance
            parent: Parent widget (optional)
        """
        super().__init__(parent)
        self.catalog_manager = catalog_manager
        self.sync_worker = None
        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """Initialize UI components"""
        self.setWindowTitle(self.tr("Update Catalog"))
        self.setModal(True)
        self.setFixedWidth(500)

        layout = QVBoxLayout(self)

        # Status label
        self.status_label = QLabel(self.tr("Preparing to sync..."))
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("font-size: 12pt; padding: 10px;")
        layout.addWidget(self.status_label)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar)

        # Details text (initially hidden)
        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setMaximumHeight(150)
        self.details_text.setVisible(False)
        self.details_text.setStyleSheet("font-family: monospace; font-size: 9pt;")
        layout.addWidget(self.details_text)

        # Show details button
        self.details_button = QPushButton(self.tr("Show Details"))
        self.details_button.clicked.connect(self._toggle_details)
        self.details_button.setVisible(False)
        layout.addWidget(self.details_button)

        # Close button (initially disabled)
        self.close_button = QPushButton(self.tr("Close"))
        self.close_button.clicked.connect(self.accept)
        self.close_button.setEnabled(False)
        layout.addWidget(self.close_button)

        # Set minimum height
        self.setMinimumHeight(200)

    def _connect_signals(self):
        """Connect catalog manager signals"""
        self.catalog_manager.sync_started.connect(self._on_sync_started)
        self.catalog_manager.sync_progress.connect(self._on_sync_progress)
        self.catalog_manager.sync_completed.connect(self._on_sync_completed)
        self.catalog_manager.sync_error.connect(self._on_sync_error)

    def _toggle_details(self):
        """Toggle details text visibility"""
        visible = self.details_text.isVisible()
        self.details_text.setVisible(not visible)
        self.details_button.setText(
            self.tr("Hide Details") if not visible else self.tr("Show Details")
        )

        # Adjust dialog size
        if not visible:
            self.setMinimumHeight(400)
        else:
            self.setMinimumHeight(200)

    def start_sync(self):
        """Start the sync process in background thread"""
        self.sync_worker = SyncWorker(self.catalog_manager)
        self.sync_worker.finished.connect(self._on_worker_finished)
        self.sync_worker.start()

    @pyqtSlot()
    def _on_sync_started(self):
        """Handle sync started signal"""
        self.status_label.setText(self.tr("Synchronizing catalog..."))
        self.progress_bar.setValue(0)
        self.details_text.append("🔄 Sync started...")

    @pyqtSlot(str, int)
    def _on_sync_progress(self, message, percentage):
        """Handle progress updates"""
        self.status_label.setText(message)
        self.progress_bar.setValue(percentage)
        self.details_text.append(f"[{percentage:3d}%] {message}")

        # Auto-scroll to bottom
        cursor = self.details_text.textCursor()
        cursor.movePosition(cursor.End)
        self.details_text.setTextCursor(cursor)

    @pyqtSlot(int, int)
    def _on_sync_completed(self, movies_count, series_count):
        """Handle successful sync completion"""
        message = self.tr(
            f"Sync completed successfully!\n\n"
            f"Movies: {movies_count}\n"
            f"Series: {series_count}"
        )
        self.status_label.setText(message)
        self.progress_bar.setValue(100)
        self.close_button.setEnabled(True)
        self.details_text.append(f"\n✅ Sync completed successfully!")
        self.details_text.append(f"   • {movies_count} movies")
        self.details_text.append(f"   • {series_count} series")

        # Show details button for log review
        self.details_button.setVisible(True)

    @pyqtSlot(str)
    def _on_sync_error(self, error_message):
        """Handle sync errors"""
        self.status_label.setText(self.tr("Sync failed!"))
        self.details_text.append(f"\n❌ ERROR: {error_message}")

        # Force show details on error
        self.details_text.setVisible(True)
        self.details_button.setVisible(True)
        self.details_button.setText(self.tr("Hide Details"))
        self.setMinimumHeight(400)

        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Error")
        self.close_button.setEnabled(True)

    @pyqtSlot()
    def _on_worker_finished(self):
        """Handle worker thread completion"""
        if self.sync_worker:
            self.sync_worker.deleteLater()
            self.sync_worker = None

    def closeEvent(self, event):
        """Handle dialog close"""
        if self.sync_worker and self.sync_worker.isRunning():
            # Don't allow close while syncing
            event.ignore()
            self.status_label.setText(
                self.tr("Cannot close while syncing. Please wait...")
            )
        else:
            event.accept()


def main():
    """Standalone test for sync dialog"""
    import sys
    from PyQt5.QtWidgets import QApplication
    from source.catalog_manager import CatalogManager

    app = QApplication(sys.argv)

    # Create catalog manager
    manager = CatalogManager()

    # Create and show dialog
    dialog = SyncDialog(manager)
    dialog.start_sync()
    result = dialog.exec_()

    # Cleanup
    manager.close()

    sys.exit(0 if result == QDialog.Accepted else 1)


if __name__ == "__main__":
    main()
