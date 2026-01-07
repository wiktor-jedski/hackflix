"""
Minimal catalog display for Phase 1 testing

Simple list-based UI to verify catalog sync functionality.
Will be replaced with full UI in Phase 2 (grid view, posters, filters).
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QListWidget, QListWidgetItem,
    QLabel, QPushButton, QTabWidget, QHBoxLayout, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSlot


class MinimalCatalogTab(QWidget):
    """Simple catalog viewer for Phase 1"""

    def __init__(self, catalog_manager, parent=None):
        """
        Initialize catalog tab

        Args:
            catalog_manager: CatalogManager instance
            parent: Parent widget (optional)
        """
        super().__init__(parent)
        self.catalog_manager = catalog_manager
        self._setup_ui()
        self._connect_signals()
        self.refresh()

    def _setup_ui(self):
        """Initialize UI components"""
        layout = QVBoxLayout(self)

        # Header
        header_layout = QHBoxLayout()

        header = QLabel(self.tr("Catalog (Phase 1 - Basic View)"))
        header.setStyleSheet("font-size: 14pt; font-weight: bold;")
        header_layout.addWidget(header)

        header_layout.addStretch()

        # Refresh button in header
        refresh_btn = QPushButton(self.tr("Refresh"))
        refresh_btn.clicked.connect(self.refresh)
        header_layout.addWidget(refresh_btn)

        layout.addLayout(header_layout)

        # Info label
        self.info_label = QLabel(self.tr("Loading catalog..."))
        self.info_label.setStyleSheet("color: #888; font-style: italic;")
        layout.addWidget(self.info_label)

        # Tabs for Movies/Series
        self.tabs = QTabWidget()

        # Movies list
        self.movies_list = QListWidget()
        self.movies_list.itemDoubleClicked.connect(self._on_movie_clicked)
        self.movies_list.setAlternatingRowColors(True)
        self.tabs.addTab(self.movies_list, self.tr("Movies"))

        # Series list
        self.series_list = QListWidget()
        self.series_list.itemDoubleClicked.connect(self._on_series_clicked)
        self.series_list.setAlternatingRowColors(True)
        self.tabs.addTab(self.series_list, self.tr("Series"))

        layout.addWidget(self.tabs)

        # Status bar
        self.status_label = QLabel(self.tr("Ready"))
        self.status_label.setStyleSheet("padding: 5px; background: #333; color: #aaa;")
        layout.addWidget(self.status_label)

    def _connect_signals(self):
        """Connect catalog manager signals"""
        self.catalog_manager.catalog_updated.connect(self.refresh)

    @pyqtSlot()
    def refresh(self):
        """Refresh catalog display"""
        try:
            # Clear lists
            self.movies_list.clear()
            self.series_list.clear()

            # Load movies
            movies = self.catalog_manager.get_all_movies()
            for movie in movies:
                status = movie.get('status', 'available')
                progress = movie.get('progress', 0.0)

                # Format display text
                item_text = f"{movie['title']} ({movie['year']})"

                # Add genres
                genres = movie.get('genres', [])
                if genres:
                    item_text += f" - {', '.join(genres[:2])}"  # Show first 2 genres

                # Add status
                if status == 'downloading':
                    item_text += f" [Downloading {progress:.0f}%]"
                elif status == 'ready':
                    item_text += " [Ready]"
                elif status == 'failed':
                    item_text += " [Failed]"
                elif status == 'translation_failed':
                    item_text += " [Translation Failed]"

                item = QListWidgetItem(item_text)
                item.setData(Qt.UserRole, movie)

                # Color code by status
                if status == 'ready':
                    item.setForeground(Qt.green)
                elif status == 'downloading':
                    item.setForeground(Qt.cyan)
                elif status in ('failed', 'translation_failed'):
                    item.setForeground(Qt.red)

                self.movies_list.addItem(item)

            # Load series
            series_list = self.catalog_manager.get_all_series()
            for series in series_list:
                seasons = series.get('seasons', [])
                item_text = f"{series['title']} ({series['year']}) - {len(seasons)} season(s)"

                # Add genres
                genres = series.get('genres', [])
                if genres:
                    item_text += f" - {', '.join(genres[:2])}"

                # Count ready/downloading seasons
                ready_count = sum(1 for s in seasons if s.get('status') == 'ready')
                downloading_count = sum(1 for s in seasons if s.get('status') == 'downloading')

                if ready_count > 0:
                    item_text += f" [{ready_count} ready]"
                if downloading_count > 0:
                    item_text += f" [{downloading_count} downloading]"

                item = QListWidgetItem(item_text)
                item.setData(Qt.UserRole, series)

                # Color code if any season is ready
                if ready_count > 0:
                    item.setForeground(Qt.green)
                elif downloading_count > 0:
                    item.setForeground(Qt.cyan)

                self.series_list.addItem(item)

            # Update info label
            self.info_label.setText(
                self.tr(f"Movies: {len(movies)} | Series: {len(series_list)}")
            )

            # Update status
            self.status_label.setText(self.tr(f"Loaded {len(movies)} movies, {len(series_list)} series"))

        except Exception as e:
            self.status_label.setText(self.tr(f"Error loading catalog: {str(e)}"))
            print(f"Error refreshing catalog: {e}")
            import traceback
            traceback.print_exc()

    @pyqtSlot(QListWidgetItem)
    def _on_movie_clicked(self, item):
        """Handle movie double-click"""
        movie = item.data(Qt.UserRole)
        print(f"\nMovie clicked: {movie['title']}")
        print(f"  Year: {movie['year']}")
        print(f"  Genres: {', '.join(movie.get('genres', []))}")
        print(f"  Status: {movie.get('status', 'available')}")
        print(f"  Progress: {movie.get('progress', 0):.1f}%")
        print(f"  Magnet: {movie.get('magnet_link', 'N/A')[:50]}...")

        # Show info dialog
        QMessageBox.information(
            self,
            movie['title'],
            f"Title: {movie['title']}\n"
            f"Year: {movie['year']}\n"
            f"Genres: {', '.join(movie.get('genres', []))}\n"
            f"Status: {movie.get('status', 'available')}\n"
            f"Progress: {movie.get('progress', 0):.1f}%\n\n"
            f"IMDb: {movie.get('imdb_id', 'N/A')}\n"
            f"Quality: {movie.get('video_quality', 'N/A')}\n\n"
            f"(Download functionality coming in Phase 2)"
        )

    @pyqtSlot(QListWidgetItem)
    def _on_series_clicked(self, item):
        """Handle series double-click"""
        series = item.data(Qt.UserRole)
        print(f"\nSeries clicked: {series['title']}")
        print(f"  Year: {series['year']}")
        print(f"  Genres: {', '.join(series.get('genres', []))}")
        print(f"  Seasons: {len(series.get('seasons', []))}")

        # Build season info
        seasons_info = []
        for season in series.get('seasons', []):
            status = season.get('status', 'available')
            progress = season.get('progress', 0)
            season_text = f"Season {season['season_number']}: {status}"
            if status == 'downloading':
                season_text += f" ({progress:.0f}%)"
            seasons_info.append(season_text)

        # Show info dialog
        QMessageBox.information(
            self,
            series['title'],
            f"Title: {series['title']}\n"
            f"Year: {series['year']}\n"
            f"Genres: {', '.join(series.get('genres', []))}\n\n"
            f"Seasons:\n" + "\n".join(seasons_info) + "\n\n"
            f"IMDb: {series.get('imdb_id', 'N/A')}\n\n"
            f"(Download functionality coming in Phase 2)"
        )


def main():
    """Standalone test for catalog tab"""
    import sys
    from PyQt5.QtWidgets import QApplication, QMainWindow
    from source.catalog_manager import CatalogManager

    app = QApplication(sys.argv)

    # Create catalog manager
    manager = CatalogManager()

    # Create main window
    window = QMainWindow()
    window.setWindowTitle("Catalog Test - Phase 1")
    window.resize(800, 600)

    # Create and set catalog tab
    catalog_tab = MinimalCatalogTab(manager)
    window.setCentralWidget(catalog_tab)

    # Show window
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
