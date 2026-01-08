"""
Catalog tab for Phase 2 - Enhanced UI for movies and series browsing

Provides a modern catalog-based interface with:
- Movies and Series tabs
- Status indicators (ready, downloading, failed)
- Genre filtering (Phase 2b)
- Poster thumbnails (Phase 2c)
"""

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QLabel, QPushButton, QTabWidget, QMessageBox, QStyledItemDelegate, QStyle
)
from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot, QRect, QSize
from PyQt5.QtGui import QPainter, QPen, QColor, QFont
from source.poster_cache import PosterCache


class MediaItemDelegate(QStyledItemDelegate):
    """
    Custom delegate for rendering media list items with poster thumbnails

    Layout:
    [Poster 40x60] Title (Year) - Genre1, Genre2 | [Status]
                   Description (if available)
    """

    # Layout constants
    POSTER_WIDTH = 40
    POSTER_HEIGHT = 60
    HORIZONTAL_MARGIN = 8
    VERTICAL_MARGIN = 6
    POSTER_TEXT_GAP = 10

    def __init__(self, poster_cache, media_type='movie', parent=None):
        """
        Initialize delegate

        Args:
            poster_cache: PosterCache instance for loading posters
            media_type: 'movie' or 'series'
            parent: Parent object
        """
        super().__init__(parent)
        self.poster_cache = poster_cache
        self.media_type = media_type

        # Connect poster_ready signal to trigger repaint
        self.poster_cache.poster_ready.connect(self._on_poster_ready)

    def _on_poster_ready(self, item_id, pixmap):
        """
        Handle poster download completion - trigger repaint

        Args:
            item_id: ID of item whose poster is ready
            pixmap: Downloaded poster pixmap
        """
        # Trigger repaint of list widget
        if self.parent():
            self.parent().viewport().update()

    def sizeHint(self, option, index):
        """
        Return size hint for list item

        Args:
            option: Style option
            index: Model index

        Returns:
            QSize with item dimensions
        """
        # Height is poster height + margins
        height = self.POSTER_HEIGHT + (2 * self.VERTICAL_MARGIN)
        return QSize(option.rect.width(), height)

    def paint(self, painter, option, index):
        """
        Paint list item with poster thumbnail and metadata

        Args:
            painter: QPainter instance
            option: Style option
            index: Model index
        """
        painter.save()

        # Get item data
        item_data = index.data(Qt.UserRole)
        if not item_data:
            # Fall back to default painting
            super().paint(painter, option, index)
            painter.restore()
            return

        # Draw selection background if selected
        if option.state & QStyle.State_Selected:
            painter.fillRect(option.rect, option.palette.highlight())
        elif index.row() % 2 == 0:
            # Alternating row colors
            painter.fillRect(option.rect, QColor(30, 30, 30))

        # Calculate layout rectangles
        poster_rect = QRect(
            option.rect.left() + self.HORIZONTAL_MARGIN,
            option.rect.top() + self.VERTICAL_MARGIN,
            self.POSTER_WIDTH,
            self.POSTER_HEIGHT
        )

        text_left = poster_rect.right() + self.POSTER_TEXT_GAP
        text_width = option.rect.width() - text_left - self.HORIZONTAL_MARGIN
        text_rect = QRect(
            text_left,
            option.rect.top() + self.VERTICAL_MARGIN,
            text_width,
            option.rect.height() - (2 * self.VERTICAL_MARGIN)
        )

        # Draw poster thumbnail
        poster_url = item_data.get('poster_url')
        item_id = item_data.get('id')
        poster_pixmap = self.poster_cache.get_poster(poster_url, item_id)

        # Center poster in poster_rect
        poster_x = poster_rect.left() + (self.POSTER_WIDTH - poster_pixmap.width()) // 2
        poster_y = poster_rect.top() + (self.POSTER_HEIGHT - poster_pixmap.height()) // 2
        painter.drawPixmap(poster_x, poster_y, poster_pixmap)

        # Draw text content
        painter.setPen(QPen(option.palette.text().color()))

        # Title and year (bold)
        title = item_data.get('title', 'Unknown')
        year = item_data.get('year', '')
        title_text = f"{title} ({year})"

        font = painter.font()
        font.setBold(True)
        font.setPointSize(10)
        painter.setFont(font)

        title_rect = QRect(text_rect)
        title_rect.setHeight(20)
        painter.drawText(title_rect, Qt.AlignLeft | Qt.AlignVCenter, title_text)

        # Genres and status on same line
        genres = item_data.get('genres', [])[:2]
        genre_text = ', '.join(genres) if genres else 'N/A'

        status = item_data.get('status', 'available')
        video_progress = item_data.get('video_progress', 0.0)
        subtitle_progress = item_data.get('subtitle_progress', 0.0)
        video_status = item_data.get('video_status', 'pending')
        subtitle_status = item_data.get('subtitle_status', 'pending')

        # Status text and color (V2 - dual progress)
        if status == 'downloading':
            # Show dual progress bars for V2
            video_text = f"V:{video_progress:.0f}%"
            subtitle_text = f"S:{subtitle_progress:.0f}%"
            status_text = f"[{video_text} {subtitle_text}]"
            status_color = Qt.cyan
        elif status == 'ready':
            status_text = "[Ready]"
            status_color = Qt.green
        elif status == 'failed':
            status_text = "[Failed]"
            status_color = Qt.red
        elif status == 'translation_failed':
            status_text = "[Translation Failed]"
            status_color = Qt.red
        else:
            status_text = ""
            status_color = option.palette.text().color()

        # For series, show season status
        if self.media_type == 'series':
            seasons = item_data.get('seasons', [])
            ready_count = sum(1 for s in seasons if s.get('status') == 'ready')
            downloading_count = sum(1 for s in seasons if s.get('status') == 'downloading')

            if ready_count > 0:
                status_text = f"[{ready_count} ready]"
                status_color = Qt.green
            if downloading_count > 0:
                if status_text:
                    status_text += " "
                status_text += f"[{downloading_count} downloading]"
                status_color = Qt.cyan

        # Draw genre and status
        font.setBold(False)
        font.setPointSize(9)
        painter.setFont(font)

        meta_rect = QRect(text_rect)
        meta_rect.setTop(title_rect.bottom() + 2)
        meta_rect.setHeight(18)

        # Draw genres in normal color
        painter.setPen(QPen(QColor(180, 180, 180)))
        painter.drawText(meta_rect, Qt.AlignLeft | Qt.AlignVCenter, genre_text)

        # Draw status in status color
        if status_text:
            painter.setPen(QPen(status_color))
            painter.drawText(meta_rect, Qt.AlignRight | Qt.AlignVCenter, status_text)

        # Draw description if available (truncated)
        description = item_data.get('description', '')
        if description:
            desc_rect = QRect(text_rect)
            desc_rect.setTop(meta_rect.bottom() + 2)
            desc_rect.setHeight(18)

            font.setItalic(True)
            font.setPointSize(8)
            painter.setFont(font)
            painter.setPen(QPen(QColor(140, 140, 140)))

            # Truncate description to fit
            metrics = painter.fontMetrics()
            elided_text = metrics.elidedText(description, Qt.ElideRight, desc_rect.width())
            painter.drawText(desc_rect, Qt.AlignLeft | Qt.AlignVCenter, elided_text)

        painter.restore()


class GenreFilterBar(QTabWidget):
    """
    Horizontal genre filter tabs

    Provides genre filtering as horizontal tabs:
    - "All" tab shows all items
    - Individual genre tabs filter by genre
    """

    genre_selected = pyqtSignal(str)  # Selected genre ("All", "Action", etc.)

    def __init__(self, genres=None, parent=None):
        """
        Initialize genre filter bar

        Args:
            genres: List of genre strings
            parent: Parent widget
        """
        super().__init__(parent)
        self.setTabPosition(QTabWidget.North)

        # Add "All" tab first
        all_tab = QWidget()
        self.addTab(all_tab, self.tr("All"))

        # Add genre tabs
        if genres:
            for genre in sorted(genres):
                tab = QWidget()
                self.addTab(tab, genre)

        # Emit signal on tab change
        self.currentChanged.connect(self._on_tab_changed)

    @pyqtSlot(int)
    def _on_tab_changed(self, index):
        """Handle tab change"""
        genre = self.tabText(index)
        self.genre_selected.emit(genre)

    def set_genres(self, genres):
        """
        Update genre tabs

        Args:
            genres: List of genre strings
        """
        # Clear existing tabs except "All"
        while self.count() > 1:
            self.removeTab(1)

        # Add new genre tabs
        for genre in sorted(genres):
            tab = QWidget()
            self.addTab(tab, genre)

        # Reset to "All" tab
        self.setCurrentIndex(0)


class MediaListWidget(QListWidget):
    """
    Reusable list widget for displaying movies or series

    Features:
    - Color-coded status (green=ready, cyan=downloading, red=failed)
    - Full item metadata stored in Qt.UserRole
    - Double-click to play/show details
    """

    download_requested = pyqtSignal(str)  # item_id
    play_requested = pyqtSignal(str)  # item_id
    retry_requested = pyqtSignal(str)  # item_id

    def __init__(self, media_type='movie', poster_cache=None, parent=None):
        """
        Initialize media list widget

        Args:
            media_type: 'movie' or 'series'
            poster_cache: PosterCache instance for loading posters (optional)
            parent: Parent widget
        """
        super().__init__(parent)
        self.media_type = media_type
        self.setAlternatingRowColors(True)

        # Set up poster cache and custom delegate if available
        if poster_cache:
            delegate = MediaItemDelegate(poster_cache, media_type, self)
            self.setItemDelegate(delegate)

        # Connect double-click
        self.itemDoubleClicked.connect(self._on_item_activated)

    def set_items(self, items):
        """
        Update list with movies or series

        Args:
            items: List of movie/series dicts from catalog
        """
        self.clear()

        if not items:
            # Show empty state
            empty_item = QListWidgetItem(
                self.tr("No items found. Click 'Update Catalog' to sync.")
            )
            empty_item.setFlags(Qt.NoItemFlags)  # Make non-selectable
            self.addItem(empty_item)
            return

        for item in items:
            list_item = self._create_list_item(item)
            self.addItem(list_item)

    def _create_list_item(self, item):
        """
        Create a formatted list item from movie/series data

        Args:
            item: Movie or series dict with metadata

        Returns:
            QListWidgetItem configured with display text and colors
        """
        status = item.get('status', 'available')
        progress = item.get('progress', 0.0)

        # Format title line
        title_text = f"{item['title']} ({item['year']})"

        # Add genres (first 2)
        genres = item.get('genres', [])[:2]
        if genres:
            title_text += f" - {', '.join(genres)}"

        # Add status indicator
        if status == 'downloading':
            title_text += f" [Downloading {progress:.0f}%]"
        elif status == 'ready':
            title_text += " [Ready]"
        elif status == 'failed':
            title_text += " [Failed]"
        elif status == 'translation_failed':
            title_text += " [Translation Failed]"

        # For series, add season count
        if self.media_type == 'series':
            seasons = item.get('seasons', [])
            ready_count = sum(1 for s in seasons if s.get('status') == 'ready')
            downloading_count = sum(1 for s in seasons if s.get('status') == 'downloading')

            if ready_count > 0:
                title_text += f" [{ready_count} ready]"
            if downloading_count > 0:
                title_text += f" [{downloading_count} downloading]"

        # Create list item
        list_item = QListWidgetItem(title_text)
        list_item.setData(Qt.UserRole, item)

        # Color code by status
        if status == 'ready' or (self.media_type == 'series' and ready_count > 0):
            list_item.setForeground(Qt.green)
        elif status == 'downloading' or (self.media_type == 'series' and downloading_count > 0):
            list_item.setForeground(Qt.cyan)
        elif status in ('failed', 'translation_failed'):
            list_item.setForeground(Qt.red)

        # Set tooltip with full info
        tooltip_lines = [
            f"Title: {item['title']}",
            f"Year: {item['year']}",
            f"Genres: {', '.join(item.get('genres', []))}",
            f"Status: {status}",
        ]

        if self.media_type == 'movie':
            tooltip_lines.append(f"Quality: {item.get('video_quality', 'N/A')}")
            tooltip_lines.append(f"IMDb: {item.get('imdb_id', 'N/A')}")
        else:
            tooltip_lines.append(f"Seasons: {len(item.get('seasons', []))}")

        list_item.setToolTip("\n".join(tooltip_lines))

        return list_item

    @pyqtSlot(QListWidgetItem)
    def _on_item_activated(self, item):
        """
        Handle double-click on list item

        Args:
            item: QListWidgetItem that was double-clicked
        """
        item_data = item.data(Qt.UserRole)
        if not item_data:
            return

        # For series, open season selection dialog
        if self.media_type == 'series':
            from source.series_navigation import SeasonSelectionDialog

            # Get catalog_manager and download_state_manager from parent if available
            catalog_manager = None
            download_state_manager = None
            parent = self.parent()
            while parent:
                if hasattr(parent, 'catalog_manager'):
                    catalog_manager = parent.catalog_manager
                if hasattr(parent, 'download_orchestrator') and parent.download_orchestrator:
                    download_state_manager = parent.download_orchestrator.state_manager
                if catalog_manager:
                    break
                parent = parent.parent()

            dialog = SeasonSelectionDialog(item_data, catalog_manager, download_state_manager, self)

            # Connect dialog signals
            dialog.download_requested.connect(
                lambda season_id: self.download_requested.emit(season_id)
            )
            dialog.play_requested.connect(
                lambda path: self.play_requested.emit(path)
            )

            dialog.exec_()
            return

        # For movies, handle by status
        status = item_data.get('status', 'available')
        item_id = item_data.get('id')

        if status == 'ready':
            # Ready to play
            self.play_requested.emit(item_id)
        elif status == 'available':
            # Show download option
            self.download_requested.emit(item_id)
        elif status in ('failed', 'translation_failed'):
            # Show retry option
            self.retry_requested.emit(item_id)
        else:
            # Downloading - show info
            progress = item_data.get('progress', 0)
            QMessageBox.information(
                self,
                self.tr("Downloading"),
                f"{item_data['title']}\n\n"
                f"Status: Downloading\n"
                f"Progress: {progress:.0f}%\n\n"
                f"Please wait for download to complete."
            )


class CatalogTab(QWidget):
    """
    Main catalog tab with Movies and Series sub-tabs

    Features:
    - Automatic refresh when catalog updates
    - Manual sync trigger button
    - Status bar showing item counts
    """

    download_requested = pyqtSignal(str, str)  # (type, id)
    play_requested = pyqtSignal(str)  # id
    retry_requested = pyqtSignal(str, str)  # (type, id)
    sync_requested = pyqtSignal()  # Request catalog sync

    def __init__(self, catalog_manager, download_orchestrator=None, parent=None):
        """
        Initialize catalog tab

        Args:
            catalog_manager: CatalogManager instance
            download_orchestrator: DownloadOrchestrator instance (optional)
            parent: Parent widget
        """
        super().__init__(parent)
        self.catalog_manager = catalog_manager
        self.download_orchestrator = download_orchestrator

        # Create poster cache for Phase 2c
        self.poster_cache = PosterCache()

        # Track download progress for UI updates (V2 - dual progress bars)
        self.download_progress = {}  # item_id -> {video_progress, subtitle_progress, video_status, subtitle_status}

        self._setup_ui()
        self._connect_signals()
        self.refresh()

    def _setup_ui(self):
        """Initialize UI components"""
        layout = QVBoxLayout(self)

        # Header with title and sync button
        header_layout = QHBoxLayout()

        header = QLabel(self.tr("Catalog"))
        header.setStyleSheet("font-size: 14pt; font-weight: bold;")
        header_layout.addWidget(header)

        header_layout.addStretch()

        # Update catalog button
        self.sync_button = QPushButton(self.tr("Update Catalog"))
        self.sync_button.clicked.connect(self.sync_requested.emit)
        header_layout.addWidget(self.sync_button)

        layout.addLayout(header_layout)

        # Info label showing counts
        self.info_label = QLabel(self.tr("Loading catalog..."))
        self.info_label.setStyleSheet("color: #888; font-style: italic;")
        layout.addWidget(self.info_label)

        # Tab widget for Movies and Series
        self.tabs = QTabWidget()

        # Movies tab with genre filtering
        movies_widget = QWidget()
        movies_layout = QVBoxLayout(movies_widget)
        movies_layout.setContentsMargins(0, 0, 0, 0)

        self.movies_genre_bar = GenreFilterBar()
        self.movies_genre_bar.genre_selected.connect(self._on_movie_genre_selected)
        movies_layout.addWidget(self.movies_genre_bar)

        self.movies_list = MediaListWidget(media_type='movie', poster_cache=self.poster_cache)
        movies_layout.addWidget(self.movies_list)

        self.tabs.addTab(movies_widget, self.tr("Movies"))

        # Series tab with genre filtering
        series_widget = QWidget()
        series_layout = QVBoxLayout(series_widget)
        series_layout.setContentsMargins(0, 0, 0, 0)

        self.series_genre_bar = GenreFilterBar()
        self.series_genre_bar.genre_selected.connect(self._on_series_genre_selected)
        series_layout.addWidget(self.series_genre_bar)

        self.series_list = MediaListWidget(media_type='series', poster_cache=self.poster_cache)
        series_layout.addWidget(self.series_list)

        self.tabs.addTab(series_widget, self.tr("Series"))

        layout.addWidget(self.tabs)

        # Status bar at bottom
        self.status_label = QLabel(self.tr("Ready"))
        self.status_label.setStyleSheet("padding: 5px; background: #333; color: #aaa;")
        layout.addWidget(self.status_label)

        # Track selected genres
        self.selected_movie_genre = "All"
        self.selected_series_genre = "All"

    def _connect_signals(self):
        """Connect signals between components"""
        # Connect catalog manager signals
        self.catalog_manager.catalog_updated.connect(self.refresh)

        # Connect movie list signals
        self.movies_list.download_requested.connect(
            lambda item_id: self.download_requested.emit('movie', item_id)
        )
        self.movies_list.play_requested.connect(self.play_requested.emit)
        self.movies_list.retry_requested.connect(
            lambda item_id: self.retry_requested.emit('movie', item_id)
        )

        # Connect series list signals
        self.series_list.download_requested.connect(
            lambda item_id: self.download_requested.emit('series', item_id)
        )
        self.series_list.play_requested.connect(self.play_requested.emit)
        self.series_list.retry_requested.connect(
            lambda item_id: self.retry_requested.emit('series', item_id)
        )

    @pyqtSlot(str)
    def _on_movie_genre_selected(self, genre):
        """Handle movie genre selection"""
        self.selected_movie_genre = genre
        self._refresh_movies()

    @pyqtSlot(str)
    def _on_series_genre_selected(self, genre):
        """Handle series genre selection"""
        self.selected_series_genre = genre
        self._refresh_series()

    def _refresh_movies(self):
        """Refresh movies list with current genre filter"""
        try:
            movies = self.catalog_manager.get_movies_by_genre(self.selected_movie_genre)

            # Merge download state if orchestrator available
            if self.download_orchestrator:
                movies = self._merge_download_state(movies, 'movie')

            self.movies_list.set_items(movies)
        except Exception as e:
            print(f"Error refreshing movies: {e}")
            import traceback
            traceback.print_exc()

    def _refresh_series(self):
        """Refresh series list with current genre filter"""
        try:
            series_list = self.catalog_manager.get_series_by_genre(self.selected_series_genre)

            # Merge download state if orchestrator available
            if self.download_orchestrator:
                series_list = self._merge_download_state(series_list, 'series')

            self.series_list.set_items(series_list)
        except Exception as e:
            print(f"Error refreshing series: {e}")
            import traceback
            traceback.print_exc()

    def _merge_download_state(self, items, item_type):
        """
        Merge download state from database with catalog items.

        Args:
            items: List of catalog items (movies or series)
            item_type: 'movie' or 'series'

        Returns:
            List of items with download state merged in
        """
        if not self.download_orchestrator:
            return items

        state_manager = self.download_orchestrator.state_manager

        for item in items:
            item_id = item.get('id')
            if not item_id:
                continue

            # Get download state from database
            download_state = state_manager.get_download_state(item_id)

            if download_state:
                # Merge download state into item (V2 - dual progress)
                item['status'] = download_state.get('status', 'available')
                item['video_progress'] = download_state.get('video_progress', 0.0)
                item['subtitle_progress'] = download_state.get('subtitle_progress', 0.0)
                item['video_status'] = download_state.get('video_status', 'pending')
                item['subtitle_status'] = download_state.get('subtitle_status', 'pending')
                item['download_path'] = download_state.get('download_path')
                item['subtitle_path'] = download_state.get('subtitle_path')
                item['translated_subtitle_path'] = download_state.get('translated_subtitle_path')

                # Use live progress if available (more up-to-date than database)
                if item_id in self.download_progress:
                    live_progress = self.download_progress[item_id]
                    item['video_progress'] = live_progress.get('video_progress', 0.0)
                    item['subtitle_progress'] = live_progress.get('subtitle_progress', 0.0)
                    item['video_status'] = live_progress.get('video_status', 'pending')
                    item['subtitle_status'] = live_progress.get('subtitle_status', 'pending')
            else:
                # No download state - item is available
                item['status'] = 'available'
                item['video_progress'] = 0.0
                item['subtitle_progress'] = 0.0
                item['video_status'] = 'pending'
                item['subtitle_status'] = 'pending'

        return items

    @pyqtSlot()
    def refresh(self):
        """Refresh catalog display from database"""
        try:
            # Load all movies and series to get genres
            all_movies = self.catalog_manager.get_all_movies()
            all_series = self.catalog_manager.get_all_series()

            # Update genre bars
            movie_genres = self.catalog_manager.get_movie_genres()
            self.movies_genre_bar.set_genres(movie_genres)

            series_genres = self.catalog_manager.get_series_genres()
            self.series_genre_bar.set_genres(series_genres)

            # Refresh filtered lists
            self._refresh_movies()
            self._refresh_series()

            # Update info label
            self.info_label.setText(
                self.tr(f"Movies: {len(all_movies)} | Series: {len(all_series)}")
            )

            # Update status
            self.status_label.setText(
                self.tr(f"Loaded {len(all_movies)} movies, {len(all_series)} series")
            )

        except Exception as e:
            self.status_label.setText(self.tr(f"Error loading catalog: {str(e)}"))
            print(f"Error refreshing catalog: {e}")
            import traceback
            traceback.print_exc()

    def get_selected_item(self):
        """
        Get currently selected item from active tab

        Returns:
            dict: Selected item data or None
        """
        # Get the appropriate list widget based on current tab
        current_tab_index = self.tabs.currentIndex()

        if current_tab_index == 0:  # Movies tab
            list_widget = self.movies_list
        elif current_tab_index == 1:  # Series tab
            list_widget = self.series_list
        else:
            return None

        selected_items = list_widget.selectedItems()
        if not selected_items:
            return None

        item_data = selected_items[0].data(Qt.UserRole)
        if item_data:
            # Add type for convenience
            item_data['type'] = 'movie' if current_tab_index == 0 else 'series'
        return item_data

    def focus_genre_filter(self):
        """Focus the genre filter bar of the current tab"""
        current_tab_index = self.tabs.currentIndex()

        if current_tab_index == 0:  # Movies tab
            self.movies_genre_bar.setFocus()
        elif current_tab_index == 1:  # Series tab
            self.series_genre_bar.setFocus()

    # --- Download Progress Handlers (V2 - Dual Progress Bars) ---
    def on_video_progress_updated(self, item_id, progress):
        """
        Handle video download progress update from orchestrator V2.

        Args:
            item_id: Item identifier
            progress: Video progress (0-100)
        """
        # Store progress for UI updates
        if item_id not in self.download_progress:
            self.download_progress[item_id] = {
                'video_progress': 0.0,
                'subtitle_progress': 0.0,
                'video_status': 'pending',
                'subtitle_status': 'pending'
            }

        self.download_progress[item_id]['video_progress'] = progress

        # Trigger UI refresh to update progress display
        self._refresh_movies()
        self._refresh_series()

    def on_subtitle_progress_updated(self, item_id, progress):
        """
        Handle subtitle download/translation progress update from orchestrator V2.

        Args:
            item_id: Item identifier
            progress: Subtitle progress (0-100, includes translation)
        """
        # Store progress for UI updates
        if item_id not in self.download_progress:
            self.download_progress[item_id] = {
                'video_progress': 0.0,
                'subtitle_progress': 0.0,
                'video_status': 'pending',
                'subtitle_status': 'pending'
            }

        self.download_progress[item_id]['subtitle_progress'] = progress

        # Trigger UI refresh to update progress display
        self._refresh_movies()
        self._refresh_series()

    def on_video_status_changed(self, item_id, status):
        """
        Handle video status change from orchestrator V2.

        Args:
            item_id: Item identifier
            status: Video status ('pending', 'downloading', 'completed', 'failed')
        """
        print(f"[UI] Video status changed: {item_id} -> {status}")

        # Update status tracking
        if item_id not in self.download_progress:
            self.download_progress[item_id] = {
                'video_progress': 0.0,
                'subtitle_progress': 0.0,
                'video_status': status,
                'subtitle_status': 'pending'
            }
        else:
            self.download_progress[item_id]['video_status'] = status

        # Refresh UI to show status change
        self._refresh_movies()
        self._refresh_series()

    def on_subtitle_status_changed(self, item_id, status):
        """
        Handle subtitle status change from orchestrator V2.

        Args:
            item_id: Item identifier
            status: Subtitle status ('pending', 'downloading', 'completed', 'failed', 'not_needed')
        """
        print(f"[UI] Subtitle status changed: {item_id} -> {status}")

        # Update status tracking
        if item_id not in self.download_progress:
            self.download_progress[item_id] = {
                'video_progress': 0.0,
                'subtitle_progress': 0.0,
                'video_status': 'pending',
                'subtitle_status': status
            }
        else:
            self.download_progress[item_id]['subtitle_status'] = status

        # Refresh UI to show status change
        self._refresh_movies()
        self._refresh_series()


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
    window.setWindowTitle("Catalog Tab - Phase 2a Test")
    window.resize(900, 700)

    # Create and set catalog tab
    catalog_tab = CatalogTab(manager)
    window.setCentralWidget(catalog_tab)

    # Connect sync signal for testing
    def show_sync_message():
        print("Sync requested - would open SyncDialog here")

    catalog_tab.sync_requested.connect(show_sync_message)

    # Connect download/play signals for testing
    catalog_tab.download_requested.connect(
        lambda type, id: print(f"Download requested: {type} {id}")
    )
    catalog_tab.play_requested.connect(
        lambda id: print(f"Play requested: {id}")
    )

    # Show window
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
