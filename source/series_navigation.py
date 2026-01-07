"""
Series season/episode selection dialog

Provides navigation for series:
- Season list with availability status
- Episode list with watch history markers
- Download and play actions
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QSplitter, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot


class SeasonSelectionDialog(QDialog):
    """
    Modal dialog for series season and episode selection

    Features:
    - Season list with download status
    - Episode list with watch history markers
    - Download and play actions
    """

    download_requested = pyqtSignal(str)  # season_id
    play_requested = pyqtSignal(str)  # episode file path
    season_selected = pyqtSignal(str, int)  # (series_id, season_number)

    def __init__(self, series_data, catalog_manager=None, parent=None):
        """
        Initialize season selection dialog

        Args:
            series_data: Series dictionary with seasons
            catalog_manager: CatalogManager instance (optional, for watch history)
            parent: Parent widget
        """
        super().__init__(parent)
        self.series = series_data
        self.catalog_manager = catalog_manager
        self.watch_history = {}  # {season_num: {episode_num: {position, completed}}}

        self.setWindowTitle(f"{series_data['title']} ({series_data['year']})")
        self.resize(800, 600)

        self._setup_ui()
        self._load_watch_history()
        self._populate_seasons()

    def _setup_ui(self):
        """Setup UI components"""
        layout = QVBoxLayout(self)

        # Series info header
        header_layout = QVBoxLayout()

        title_label = QLabel(f"<h2>{self.series['title']} ({self.series['year']})</h2>")
        header_layout.addWidget(title_label)

        if self.series.get('description'):
            desc_label = QLabel(self.series['description'])
            desc_label.setWordWrap(True)
            desc_label.setMaximumHeight(80)
            desc_label.setStyleSheet("color: #888;")
            header_layout.addWidget(desc_label)

        # Genres
        genres = self.series.get('genres', [])
        if genres:
            genre_label = QLabel(f"Genres: {', '.join(genres)}")
            genre_label.setStyleSheet("font-style: italic; color: #aaa;")
            header_layout.addWidget(genre_label)

        layout.addLayout(header_layout)

        # Splitter for season and episode lists
        splitter = QSplitter(Qt.Horizontal)

        # Season list on left
        season_widget = QWidget()
        season_layout = QVBoxLayout(season_widget)
        season_layout.setContentsMargins(0, 0, 0, 0)

        season_header = QLabel(self.tr("<b>Seasons:</b>"))
        season_layout.addWidget(season_header)

        self.season_list = QListWidget()
        self.season_list.setAlternatingRowColors(True)
        self.season_list.currentItemChanged.connect(self._on_season_selected)
        season_layout.addWidget(self.season_list)

        splitter.addWidget(season_widget)

        # Episode list on right (initially empty)
        episode_widget = QWidget()
        episode_layout = QVBoxLayout(episode_widget)
        episode_layout.setContentsMargins(0, 0, 0, 0)

        self.episode_header = QLabel(self.tr("<b>Episodes:</b>"))
        episode_layout.addWidget(self.episode_header)

        self.episode_list = QListWidget()
        self.episode_list.setAlternatingRowColors(True)
        self.episode_list.itemDoubleClicked.connect(self._on_episode_activated)
        episode_layout.addWidget(self.episode_list)

        self.episode_info_label = QLabel(self.tr("Select a season to view episodes"))
        self.episode_info_label.setStyleSheet("color: #888; font-style: italic;")
        self.episode_info_label.setAlignment(Qt.AlignCenter)
        episode_layout.addWidget(self.episode_info_label)

        splitter.addWidget(episode_widget)

        # Set splitter sizes (40% seasons, 60% episodes)
        splitter.setSizes([320, 480])

        layout.addWidget(splitter)

        # Action buttons at bottom
        button_layout = QHBoxLayout()

        button_layout.addStretch()

        self.download_button = QPushButton(self.tr("Download Season"))
        self.download_button.setEnabled(False)
        self.download_button.clicked.connect(self._on_download_clicked)
        button_layout.addWidget(self.download_button)

        self.play_button = QPushButton(self.tr("Play Episode"))
        self.play_button.setEnabled(False)
        self.play_button.clicked.connect(self._on_play_clicked)
        button_layout.addWidget(self.play_button)

        close_button = QPushButton(self.tr("Close"))
        close_button.clicked.connect(self.reject)
        button_layout.addWidget(close_button)

        layout.addLayout(button_layout)

    def _load_watch_history(self):
        """Load watch history from database"""
        if not self.catalog_manager:
            return

        try:
            from source.db_utils import get_watch_history

            db = self.catalog_manager._get_db()
            try:
                history = get_watch_history(db, self.series['id'])

                # Organize by season and episode
                for entry in history:
                    season_num = entry['season_number']
                    episode_num = entry['episode_number']

                    if season_num not in self.watch_history:
                        self.watch_history[season_num] = {}

                    self.watch_history[season_num][episode_num] = {
                        'position': entry['last_position'],
                        'duration': entry.get('duration', 0),
                        'completed': entry.get('completed', False)
                    }
            finally:
                db.close()

        except Exception as e:
            print(f"Error loading watch history: {e}")
            import traceback
            traceback.print_exc()

    def _populate_seasons(self):
        """Populate season list"""
        self.season_list.clear()

        seasons = self.series.get('seasons', [])
        if not seasons:
            empty_item = QListWidgetItem(self.tr("No seasons available"))
            empty_item.setFlags(Qt.NoItemFlags)
            self.season_list.addItem(empty_item)
            return

        for season in seasons:
            season_num = season['season_number']
            status = season.get('status', 'available')
            progress = season.get('progress', 0.0)
            episode_count = season.get('episode_count', 0)

            # Format season text
            season_text = f"Season {season_num}"

            if episode_count > 0:
                season_text += f" ({episode_count} episodes)"

            # Add status
            if status == 'downloading':
                season_text += f" [Downloading {progress:.0f}%]"
            elif status == 'ready':
                season_text += " [Ready]"
            elif status == 'failed':
                season_text += " [Failed]"
            elif status == 'translation_failed':
                season_text += " [Translation Failed]"

            # Create list item
            item = QListWidgetItem(season_text)
            item.setData(Qt.UserRole, season)

            # Color code by status
            if status == 'ready':
                item.setForeground(Qt.green)
            elif status == 'downloading':
                item.setForeground(Qt.cyan)
            elif status in ('failed', 'translation_failed'):
                item.setForeground(Qt.red)

            self.season_list.addItem(item)

        # Auto-select first season
        if self.season_list.count() > 0:
            self.season_list.setCurrentRow(0)

    @pyqtSlot(QListWidgetItem, QListWidgetItem)
    def _on_season_selected(self, current, previous):
        """Handle season selection"""
        if not current:
            self.episode_list.clear()
            self.download_button.setEnabled(False)
            self.play_button.setEnabled(False)
            return

        season = current.data(Qt.UserRole)
        if not season:
            return

        season_num = season['season_number']
        status = season.get('status', 'available')

        # Enable download button for available/failed seasons
        self.download_button.setEnabled(status in ('available', 'failed', 'translation_failed'))

        # Emit season selected signal
        self.season_selected.emit(self.series['id'], season_num)

        # Populate episode list
        self._populate_episodes(season)

    def _populate_episodes(self, season):
        """Populate episode list for selected season"""
        self.episode_list.clear()

        season_num = season['season_number']
        episode_count = season.get('episode_count', 0)
        status = season.get('status', 'available')

        if status != 'ready':
            # Season not downloaded yet
            self.episode_info_label.setText(
                self.tr(f"Season {season_num} is not downloaded yet.\n"
                       f"Click 'Download Season' to download.")
            )
            self.episode_info_label.show()
            self.play_button.setEnabled(False)
            return

        self.episode_info_label.hide()

        if episode_count == 0:
            empty_item = QListWidgetItem(self.tr("No episode information available"))
            empty_item.setFlags(Qt.NoItemFlags)
            self.episode_list.addItem(empty_item)
            self.play_button.setEnabled(False)
            return

        # Get watch history for this season
        season_history = self.watch_history.get(season_num, {})

        # Create episode items
        for ep_num in range(1, episode_count + 1):
            ep_text = f"E{ep_num:02d}"

            # Add watch history markers
            if ep_num in season_history:
                history = season_history[ep_num]
                if history['completed']:
                    ep_text += " [✓100%]"
                else:
                    # Calculate percentage watched
                    if history['duration'] > 0:
                        percent = (history['position'] / history['duration']) * 100
                        ep_text += f" [●{percent:.0f}%]"

            item = QListWidgetItem(ep_text)
            item.setData(Qt.UserRole, {'season': season_num, 'episode': ep_num})

            # Color completed episodes green
            if ep_num in season_history and season_history[ep_num]['completed']:
                item.setForeground(Qt.green)

            self.episode_list.addItem(item)

        # Enable play button
        self.play_button.setEnabled(True)

        # Auto-select first unwatched episode or first episode
        first_unwatched = None
        for i in range(self.episode_list.count()):
            item = self.episode_list.item(i)
            ep_data = item.data(Qt.UserRole)
            if ep_data:
                ep_num = ep_data['episode']
                if ep_num not in season_history or not season_history[ep_num]['completed']:
                    first_unwatched = i
                    break

        if first_unwatched is not None:
            self.episode_list.setCurrentRow(first_unwatched)
        else:
            self.episode_list.setCurrentRow(0)

    @pyqtSlot()
    def _on_download_clicked(self):
        """Handle download button click"""
        selected_season = self.season_list.currentItem()
        if not selected_season:
            return

        season = selected_season.data(Qt.UserRole)
        if not season:
            return

        season_id = f"{self.series['id']}_s{season['season_number']}"
        self.download_requested.emit(season_id)

    @pyqtSlot()
    def _on_play_clicked(self):
        """Handle play button click"""
        selected_episode = self.episode_list.currentItem()
        if not selected_episode:
            return

        ep_data = selected_episode.data(Qt.UserRole)
        if not ep_data:
            return

        # Phase 2b: Placeholder - actual file path lookup will be in Phase 3
        episode_path = f"{self.series['id']}_s{ep_data['season']}_e{ep_data['episode']}"
        self.play_requested.emit(episode_path)

    @pyqtSlot(QListWidgetItem)
    def _on_episode_activated(self, item):
        """Handle episode double-click"""
        self._on_play_clicked()


def main():
    """Test the season selection dialog"""
    import sys
    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)

    # Mock series data
    series_data = {
        'id': 'series_001',
        'title': 'Breaking Bad',
        'year': 2008,
        'description': 'A high school chemistry teacher turned methamphetamine producer partners with a former student.',
        'genres': ['Crime', 'Drama', 'Thriller'],
        'seasons': [
            {'season_number': 1, 'episode_count': 7, 'status': 'ready', 'progress': 100.0},
            {'season_number': 2, 'episode_count': 13, 'status': 'downloading', 'progress': 45.0},
            {'season_number': 3, 'episode_count': 13, 'status': 'available', 'progress': 0.0},
        ]
    }

    # Create dialog
    dialog = SeasonSelectionDialog(series_data)

    # Connect signals for testing
    dialog.download_requested.connect(lambda sid: print(f"Download requested: {sid}"))
    dialog.play_requested.connect(lambda path: print(f"Play requested: {path}"))
    dialog.season_selected.connect(lambda sid, snum: print(f"Season selected: {sid} S{snum}"))

    dialog.exec_()

    sys.exit(0)


if __name__ == "__main__":
    main()
