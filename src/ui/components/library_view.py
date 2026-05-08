"""Library view component for Hackflix.

This module provides the LibraryView widget for displaying
media items in a navigable list.
"""

import logging
import os
from pathlib import Path
from typing import Any

from PySide6.QtCore import QModelIndex, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListView,
    QVBoxLayout,
    QWidget,
)

from src.ui.components.library_item_delegate import (
    LibraryItemDelegate,
    LibraryItemRole,
)
from src.ui.enums import MediaTab
from src.ui.styles import (
    BACKGROUND_COLOR,
    FONT_SIZE_TITLE,
    POSTER_HEIGHT,
    POSTER_WIDTH,
    PRIMARY_COLOR,
    ROW_HEIGHT,
    SECONDARY_COLOR,
    SURFACE_COLOR,
    TEXT_SECONDARY,
)

logger = logging.getLogger(__name__)


class LibraryView(QFrame):
    """Main library view displaying media items.

    The library view consists of:
    - Tab header (Movies / Series)
    - Scrollable list of media items
    - Custom delegate for row rendering

    This is a "dumb" component - it only displays data and emits signals.
    All business logic is handled by the controller.

    Signals:
        item_activated: Emitted when Enter is pressed on an item.
        selection_changed: Emitted when the selected item changes.
        tab_changed: Emitted when the active tab changes.
    """

    item_activated = Signal(dict)  # Item data dict
    selection_changed = Signal(dict)  # Item data dict (empty if none)
    tab_changed = Signal(MediaTab)  # New active tab

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the LibraryView.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self._current_tab = MediaTab.MOVIES
        self._items: list[dict[str, Any]] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the library view UI layout."""
        self.setObjectName("LibraryView")
        self.setStyleSheet(f"background-color: {BACKGROUND_COLOR};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Tab header
        self._header = self._create_header()
        layout.addWidget(self._header)

        # List view
        self._list_view = QListView()
        self._list_view.setObjectName("MediaList")
        self._list_view.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self._list_view.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff  # type: ignore[attr-defined]
        )
        self._list_view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._list_view.setFocusPolicy(Qt.StrongFocus)  # type: ignore[attr-defined]
        self._list_view.setUniformItemSizes(True)
        self._list_view.setSpacing(4)
        self._list_view.setIconSize(QSize(POSTER_WIDTH, POSTER_HEIGHT))

        # Model and delegate
        self._model = QStandardItemModel(self)
        self._delegate = LibraryItemDelegate(self)
        self._list_view.setModel(self._model)
        if os.environ.get("HACKFLIX_CUSTOM_LIBRARY_DELEGATE") == "1":
            self._list_view.setItemDelegate(self._delegate)

        # Connect selection changed
        selection_model = self._list_view.selectionModel()
        if selection_model:
            selection_model.currentChanged.connect(self._on_selection_changed)

        layout.addWidget(self._list_view)

    def _create_header(self) -> QWidget:
        """Create the tab header widget.

        Returns:
            The header widget.
        """
        header = QFrame()
        header.setObjectName("LibraryHeader")
        header.setFixedHeight(60)
        header.setStyleSheet(f"""
            QFrame#LibraryHeader {{
                background-color: {SURFACE_COLOR};
                border-bottom: 1px solid {SECONDARY_COLOR};
            }}
        """)

        layout = QHBoxLayout(header)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(32)

        # Movies tab
        self._movies_tab = QLabel(self.tr("Movies"))
        self._movies_tab.setObjectName("MoviesTab")
        self._movies_tab.setCursor(Qt.PointingHandCursor)  # type: ignore[attr-defined]
        layout.addWidget(self._movies_tab)

        # Series tab
        self._series_tab = QLabel(self.tr("Series"))
        self._series_tab.setObjectName("SeriesTab")
        self._series_tab.setCursor(Qt.PointingHandCursor)  # type: ignore[attr-defined]
        layout.addWidget(self._series_tab)

        layout.addStretch()

        self._update_tab_styles()
        return header

    def _update_tab_styles(self) -> None:
        """Update tab label styles based on current selection."""
        active_style = f"""
            font-size: {FONT_SIZE_TITLE}px;
            font-weight: bold;
            color: {PRIMARY_COLOR};
            border-bottom: 3px solid {PRIMARY_COLOR};
            padding-bottom: 8px;
        """
        inactive_style = f"""
            font-size: {FONT_SIZE_TITLE}px;
            font-weight: normal;
            color: {TEXT_SECONDARY};
            border-bottom: 3px solid transparent;
            padding-bottom: 8px;
        """

        if self._current_tab == MediaTab.MOVIES:
            self._movies_tab.setStyleSheet(active_style)
            self._series_tab.setStyleSheet(inactive_style)
        else:
            self._movies_tab.setStyleSheet(inactive_style)
            self._series_tab.setStyleSheet(active_style)

    def switch_tab(self) -> None:
        """Switch between Movies and Series tabs."""
        if self._current_tab == MediaTab.MOVIES:
            self._current_tab = MediaTab.SERIES
        else:
            self._current_tab = MediaTab.MOVIES

        self._update_tab_styles()
        self.tab_changed.emit(self._current_tab)
        logger.debug("Tab switched to: %s", self._current_tab.name)

    def set_tab(self, tab: MediaTab) -> None:
        """Set the active tab.

        Args:
            tab: The tab to activate.
        """
        if self._current_tab != tab:
            self._current_tab = tab
            self._update_tab_styles()
            self.tab_changed.emit(self._current_tab)

    def get_current_tab(self) -> MediaTab:
        """Get the currently active tab.

        Returns:
            The active MediaTab.
        """
        return self._current_tab

    def set_items(self, items: list[dict[str, Any]]) -> None:
        """Set the items to display in the list.

        Args:
            items: List of item dictionaries with keys matching LibraryItemRole.
        """
        self._items = items
        self._model.clear()

        for item_data in items:
            model_item = QStandardItem()
            model_item.setText(self._format_item_text(item_data))
            model_item.setIcon(self._build_item_icon(item_data))
            model_item.setData(item_data.get("id"), LibraryItemRole.IdRole)
            model_item.setData(item_data.get("type"), LibraryItemRole.TypeRole)
            model_item.setData(item_data.get("title"), LibraryItemRole.TitleRole)
            model_item.setData(item_data.get("genres"), LibraryItemRole.GenresRole)
            model_item.setData(
                item_data.get("poster_path"), LibraryItemRole.PosterPathRole
            )
            model_item.setData(
                item_data.get("state"), LibraryItemRole.DownloadStateRole
            )
            model_item.setData(
                item_data.get("pipeline_state"), LibraryItemRole.PipelineStateRole
            )
            model_item.setData(
                item_data.get("download_progress"), LibraryItemRole.DownloadProgressRole
            )
            model_item.setData(
                item_data.get("season_count"), LibraryItemRole.SeasonCountRole
            )
            model_item.setData(
                item_data.get("episode_count"), LibraryItemRole.EpisodeCountRole
            )
            model_item.setData(
                item_data.get("season_number"), LibraryItemRole.SeasonNumberRole
            )
            model_item.setData(
                item_data.get("episode_number"), LibraryItemRole.EpisodeNumberRole
            )
            model_item.setData(
                item_data.get("episode_title"), LibraryItemRole.EpisodeTitleRole
            )
            model_item.setData(item_data.get("file_id"), LibraryItemRole.FileIdRole)
            model_item.setSizeHint(QSize(-1, ROW_HEIGHT))

            self._model.appendRow(model_item)

        # Select first item if available
        if self._model.rowCount() > 0:
            self._list_view.setCurrentIndex(self._model.index(0, 0))

        logger.debug("LibraryView set %d items", len(items))

    def get_items(self) -> list[dict[str, Any]]:
        """Get the current items.

        Returns:
            List of item dictionaries.
        """
        return self._items

    def select_next(self) -> bool:
        """Select the next item in the list.

        Returns:
            True if selection moved, False if already at end.
        """
        current = self._list_view.currentIndex()
        if not current.isValid():
            if self._model.rowCount() > 0:
                self._list_view.setCurrentIndex(self._model.index(0, 0))
                return True
            return False

        next_row = current.row() + 1
        if next_row < self._model.rowCount():
            self._list_view.setCurrentIndex(self._model.index(next_row, 0))
            return True
        return False

    def select_prev(self) -> bool:
        """Select the previous item in the list.

        Returns:
            True if selection moved, False if already at start.
        """
        current = self._list_view.currentIndex()
        if not current.isValid():
            if self._model.rowCount() > 0:
                last_row = self._model.rowCount() - 1
                self._list_view.setCurrentIndex(self._model.index(last_row, 0))
                return True
            return False

        prev_row = current.row() - 1
        if prev_row >= 0:
            self._list_view.setCurrentIndex(self._model.index(prev_row, 0))
            return True
        return False

    def select_by_id(self, item_id: str) -> bool:
        """Select an item by its ID.

        Args:
            item_id: The item ID to select.

        Returns:
            True if item found and selected, False otherwise.
        """
        for row in range(self._model.rowCount()):
            index = self._model.index(row, 0)
            if index.data(LibraryItemRole.IdRole) == item_id:
                self._list_view.setCurrentIndex(index)
                return True
        return False

    def get_selected_item(self) -> dict[str, Any] | None:
        """Get the currently selected item.

        Returns:
            Item data dictionary, or None if nothing selected.
        """
        current = self._list_view.currentIndex()
        if not current.isValid():
            return None

        return self._get_item_data(current)

    def get_selected_index(self) -> int:
        """Get the index of the currently selected item.

        Returns:
            Row index, or -1 if nothing selected.
        """
        current = self._list_view.currentIndex()
        if not current.isValid():
            return -1
        return current.row()

    def _get_item_data(self, index: QModelIndex) -> dict[str, Any]:
        """Extract item data from a model index.

        Args:
            index: The model index.

        Returns:
            Dictionary with item data.
        """
        return {
            "id": index.data(LibraryItemRole.IdRole),
            "type": index.data(LibraryItemRole.TypeRole),
            "title": index.data(LibraryItemRole.TitleRole),
            "genres": index.data(LibraryItemRole.GenresRole),
            "poster_path": index.data(LibraryItemRole.PosterPathRole),
            "state": index.data(LibraryItemRole.DownloadStateRole),
            "pipeline_state": index.data(LibraryItemRole.PipelineStateRole),
            "download_progress": index.data(LibraryItemRole.DownloadProgressRole),
            "season_count": index.data(LibraryItemRole.SeasonCountRole),
            "episode_count": index.data(LibraryItemRole.EpisodeCountRole),
            "season_number": index.data(LibraryItemRole.SeasonNumberRole),
            "episode_number": index.data(LibraryItemRole.EpisodeNumberRole),
            "episode_title": index.data(LibraryItemRole.EpisodeTitleRole),
            "file_id": index.data(LibraryItemRole.FileIdRole),
        }

    def _on_selection_changed(
        self, current: QModelIndex, previous: QModelIndex
    ) -> None:
        """Handle selection change.

        Args:
            current: New selected index.
            previous: Previously selected index.
        """
        if current.isValid():
            item_data = self._get_item_data(current)
            self.selection_changed.emit(item_data)
        else:
            self.selection_changed.emit({})

    def activate_selected(self) -> None:
        """Activate (trigger action on) the currently selected item."""
        item = self.get_selected_item()
        if item:
            self.item_activated.emit(item)

    def set_focus(self) -> None:
        """Set focus to the list view."""
        self._list_view.setFocus()

    def update_item(self, item_id: str, updates: dict[str, Any]) -> None:
        """Update a specific item's data.

        Args:
            item_id: ID of the item to update.
            updates: Dictionary of field updates.
        """
        for row in range(self._model.rowCount()):
            index = self._model.index(row, 0)
            if index.data(LibraryItemRole.IdRole) == item_id:
                self._apply_updates(index, updates)
                break

    def update_item_by_file_id(self, file_id: int, updates: dict[str, Any]) -> None:
        """Update a specific item's data by file_id.

        Args:
            file_id: File ID of the item to update.
            updates: Dictionary of field updates.
        """
        for row in range(self._model.rowCount()):
            index = self._model.index(row, 0)
            if index.data(LibraryItemRole.FileIdRole) == file_id:
                self._apply_updates(index, updates)
                break

    def _apply_updates(self, index: QModelIndex, updates: dict[str, Any]) -> None:
        """Apply updates to an item at the given index.

        Args:
            index: Model index of the item.
            updates: Dictionary of field updates.
        """
        item = self._model.itemFromIndex(index)
        if item:
            changed = False
            if "state" in updates:
                if item.data(LibraryItemRole.DownloadStateRole) != updates["state"]:
                    item.setData(updates["state"], LibraryItemRole.DownloadStateRole)
                    changed = True
            if "download_progress" in updates:
                if (
                    item.data(LibraryItemRole.DownloadProgressRole)
                    != updates["download_progress"]
                ):
                    item.setData(
                        updates["download_progress"],
                        LibraryItemRole.DownloadProgressRole,
                    )
                    changed = True
            if "pipeline_state" in updates:
                if (
                    item.data(LibraryItemRole.PipelineStateRole)
                    != updates["pipeline_state"]
                ):
                    item.setData(
                        updates["pipeline_state"], LibraryItemRole.PipelineStateRole
                    )
                    changed = True
            if changed:
                item.setText(self._format_item_text_from_model_item(item))
                item.setIcon(self._build_item_icon_from_model_item(item))
                self._list_view.viewport().update()

    def _format_item_text(self, item_data: dict[str, Any]) -> str:
        """Format stable fallback text for Qt's built-in delegate."""
        title = str(item_data.get("title") or "")
        item_type = item_data.get("type")
        state = item_data.get("state")
        progress = item_data.get("download_progress") or 0

        status = ""
        if item_type == "series":
            status = "[Series]"
        elif state == "COMPLETED":
            status = "[Play]"
        elif state == "DOWNLOADING":
            status = f"[Downloading {progress}%]"
        elif state == "ERROR":
            status = "[Error]"
        elif state == "QUEUED":
            status = "[Queued]"
        elif state == "PENDING":
            status = "[Download]"
        elif state:
            status = f"[{state.title()}]"

        subtitle_parts = []
        genres = item_data.get("genres")
        if genres:
            subtitle_parts.append(str(genres))
        episode_title = item_data.get("episode_title")
        if episode_title:
            subtitle_parts.append(str(episode_title))

        first_line = f"{status} {title}".strip()
        if subtitle_parts:
            return f"{first_line}\n{' | '.join(subtitle_parts)}"
        return first_line

    def _format_item_text_from_model_item(self, item: QStandardItem) -> str:
        """Build display text from model roles after an incremental update."""
        return self._format_item_text(self._item_data_from_model_item(item))

    def _build_item_icon_from_model_item(self, item: QStandardItem) -> QIcon:
        """Build an icon from model roles after an incremental update."""
        return self._build_item_icon(self._item_data_from_model_item(item))

    def _item_data_from_model_item(self, item: QStandardItem) -> dict[str, Any]:
        """Return item data represented by a model item."""
        return {
            "title": item.data(LibraryItemRole.TitleRole),
            "type": item.data(LibraryItemRole.TypeRole),
            "state": item.data(LibraryItemRole.DownloadStateRole),
            "download_progress": item.data(LibraryItemRole.DownloadProgressRole),
            "genres": item.data(LibraryItemRole.GenresRole),
            "episode_title": item.data(LibraryItemRole.EpisodeTitleRole),
            "poster_path": item.data(LibraryItemRole.PosterPathRole),
        }

    def _build_item_icon(self, item_data: dict[str, Any]) -> QIcon:
        """Build a poster icon with a small status badge."""
        icon_pixmap = QPixmap(POSTER_WIDTH, POSTER_HEIGHT)
        icon_pixmap.fill(QColor(SURFACE_COLOR))

        poster_path = item_data.get("poster_path")
        if poster_path and Path(str(poster_path)).exists():
            poster = QPixmap(str(poster_path))
            if not poster.isNull():
                scaled = poster.scaled(
                    icon_pixmap.size(),
                    Qt.KeepAspectRatioByExpanding,  # type: ignore[attr-defined]
                    Qt.SmoothTransformation,  # type: ignore[attr-defined]
                )
                x = (scaled.width() - POSTER_WIDTH) // 2
                y = (scaled.height() - POSTER_HEIGHT) // 2
                icon_pixmap = scaled.copy(x, y, POSTER_WIDTH, POSTER_HEIGHT)

        painter = QPainter(icon_pixmap)
        try:
            status_text = self._status_badge_text(item_data)
            if status_text:
                badge_height = 22
                badge_rect = icon_pixmap.rect().adjusted(
                    0, POSTER_HEIGHT - badge_height, 0, 0
                )
                painter.fillRect(badge_rect, QColor(0, 0, 0, 190))
                painter.setPen(QColor("white"))
                font = QFont()
                font.setPointSize(8)
                font.setBold(True)
                painter.setFont(font)
                painter.drawText(
                    badge_rect,
                    Qt.AlignCenter,  # type: ignore[attr-defined]
                    status_text,
                )
        finally:
            painter.end()

        return QIcon(icon_pixmap)

    def _status_badge_text(self, item_data: dict[str, Any]) -> str:
        """Return compact status text for the poster badge."""
        item_type = item_data.get("type")
        state = item_data.get("state")
        progress = item_data.get("download_progress") or 0

        if item_type == "series":
            return "SERIES"
        if state == "COMPLETED":
            return "PLAY"
        if state == "DOWNLOADING":
            return f"{progress}%"
        if state == "QUEUED":
            return "QUEUED"
        if state == "ERROR":
            return "ERROR"
        if state == "PENDING":
            return "GET"
        return ""

    def clear(self) -> None:
        """Clear all items from the view."""
        self._model.clear()
        self._items = []

    def refresh(self) -> None:
        """Refresh the view to trigger repainting."""
        self._list_view.viewport().update()
