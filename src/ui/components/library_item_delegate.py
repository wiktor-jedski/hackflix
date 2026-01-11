"""Library item delegate for custom row rendering.

This module provides the LibraryItemDelegate for rendering
media items in the library list view.
"""

from pathlib import Path
from typing import Any

from PyQt5.QtCore import QModelIndex, QRect, QSize, Qt
from PyQt5.QtGui import QColor, QFont, QFontMetrics, QPainter, QPixmap
from PyQt5.QtWidgets import QStyle, QStyledItemDelegate, QStyleOptionViewItem, QWidget

from src.config import DownloadState, PipelineState
from src.ui.styles import (
    ERROR_COLOR,
    FONT_FAMILY,
    FONT_SIZE_BODY,
    FONT_SIZE_SMALL,
    FONT_SIZE_TITLE,
    ITEM_PADDING,
    POSTER_HEIGHT,
    POSTER_WIDTH,
    ROW_HEIGHT,
    SELECTION_COLOR,
    STATUS_ICON_SIZE,
    SUCCESS_COLOR,
    SURFACE_COLOR,
    SURFACE_HOVER_COLOR,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    WARNING_COLOR,
)


# Data roles for model items
class LibraryItemRole:
    """Custom data roles for library items."""

    IdRole = Qt.UserRole + 1
    TypeRole = Qt.UserRole + 2
    TitleRole = Qt.UserRole + 3
    GenresRole = Qt.UserRole + 4
    PosterPathRole = Qt.UserRole + 5
    DownloadStateRole = Qt.UserRole + 6
    PipelineStateRole = Qt.UserRole + 7
    DownloadProgressRole = Qt.UserRole + 8
    SeasonCountRole = Qt.UserRole + 9
    EpisodeCountRole = Qt.UserRole + 10
    SeasonNumberRole = Qt.UserRole + 11
    EpisodeNumberRole = Qt.UserRole + 12
    EpisodeTitleRole = Qt.UserRole + 13


class LibraryItemDelegate(QStyledItemDelegate):
    """Custom delegate for rendering library items.

    Renders each row with:
    - Poster image (left, 80x120px)
    - Metadata (center): title, genres/info, subtitle
    - Status icon (right, 32x32px)
    """

    # Status icon characters (Unicode)
    _STATUS_ICONS = {
        "pending": "\u2b07",  # Down arrow
        "downloading": "\u23f3",  # Hourglass
        "completed": "\u25b6",  # Play button
        "error": "\u26a0",  # Warning triangle
        "series": "\ud83d\udcfa",  # TV icon
    }

    # Status colors
    _STATUS_COLORS = {
        "pending": TEXT_SECONDARY,
        "downloading": WARNING_COLOR,
        "completed": SUCCESS_COLOR,
        "error": ERROR_COLOR,
        "series": TEXT_SECONDARY,
    }

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the delegate.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self._poster_cache: dict[str, QPixmap] = {}

    def paint(
        self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex
    ) -> None:
        """Paint a library item.

        Args:
            painter: The QPainter to draw with.
            option: Style options for the item.
            index: Model index of the item.
        """
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)

        # Draw background
        self._draw_background(painter, option)

        # Calculate areas
        rect = option.rect.adjusted(ITEM_PADDING, ITEM_PADDING, -ITEM_PADDING, -ITEM_PADDING)

        # Poster area (left)
        poster_rect = QRect(rect.left(), rect.top(), POSTER_WIDTH, POSTER_HEIGHT)

        # Status area (right)
        status_rect = QRect(
            rect.right() - STATUS_ICON_SIZE,
            rect.top() + (rect.height() - STATUS_ICON_SIZE) // 2,
            STATUS_ICON_SIZE,
            STATUS_ICON_SIZE,
        )

        # Metadata area (center)
        metadata_rect = QRect(
            poster_rect.right() + ITEM_PADDING,
            rect.top(),
            status_rect.left() - poster_rect.right() - ITEM_PADDING * 2,
            rect.height(),
        )

        # Draw components
        self._draw_poster(painter, poster_rect, index)
        self._draw_metadata(painter, metadata_rect, index)
        self._draw_status(painter, status_rect, index)

        painter.restore()

    def _draw_background(
        self, painter: QPainter, option: QStyleOptionViewItem
    ) -> None:
        """Draw the item background.

        Args:
            painter: The QPainter to draw with.
            option: Style options for the item.
        """
        rect = option.rect

        if option.state & QStyle.State_Selected:
            color = QColor(SELECTION_COLOR)
        elif option.state & QStyle.State_MouseOver:
            color = QColor(SURFACE_HOVER_COLOR)
        else:
            color = QColor(SURFACE_COLOR)

        painter.fillRect(rect, color)

    def _draw_poster(
        self, painter: QPainter, rect: QRect, index: QModelIndex
    ) -> None:
        """Draw the poster image.

        Args:
            painter: The QPainter to draw with.
            rect: Rectangle for the poster.
            index: Model index of the item.
        """
        poster_path = index.data(LibraryItemRole.PosterPathRole)

        if poster_path:
            pixmap = self._get_cached_poster(poster_path)
            if pixmap and not pixmap.isNull():
                # Scale to fit while maintaining aspect ratio
                scaled = pixmap.scaled(
                    rect.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
                # Center in rect
                x = rect.x() + (rect.width() - scaled.width()) // 2
                y = rect.y() + (rect.height() - scaled.height()) // 2
                painter.drawPixmap(x, y, scaled)
                return

        # Draw placeholder
        painter.fillRect(rect, QColor(SURFACE_HOVER_COLOR))
        painter.setPen(QColor(TEXT_SECONDARY))
        painter.drawText(rect, Qt.AlignCenter, "No\nImage")

    def _get_cached_poster(self, path: str) -> QPixmap | None:
        """Get a poster pixmap from cache or load it.

        Args:
            path: Path to the poster image.

        Returns:
            QPixmap or None if not found.
        """
        if path not in self._poster_cache:
            if Path(path).exists():
                self._poster_cache[path] = QPixmap(path)
            else:
                self._poster_cache[path] = QPixmap()

        return self._poster_cache.get(path)

    def _draw_metadata(
        self, painter: QPainter, rect: QRect, index: QModelIndex
    ) -> None:
        """Draw the metadata section.

        Args:
            painter: The QPainter to draw with.
            rect: Rectangle for metadata.
            index: Model index of the item.
        """
        title = index.data(LibraryItemRole.TitleRole) or "Unknown Title"
        genres = index.data(LibraryItemRole.GenresRole) or ""
        item_type = index.data(LibraryItemRole.TypeRole)

        # Build subtitle based on item type
        subtitle = self._build_subtitle(index)

        # Title font
        title_font = QFont(FONT_FAMILY, FONT_SIZE_TITLE)
        title_font.setBold(True)

        # Body font
        body_font = QFont(FONT_FAMILY, FONT_SIZE_BODY)

        # Small font
        small_font = QFont(FONT_FAMILY, FONT_SIZE_SMALL)

        # Calculate line heights
        title_metrics = QFontMetrics(title_font)
        body_metrics = QFontMetrics(body_font)
        small_metrics = QFontMetrics(small_font)

        line_spacing = 4
        y = rect.top()

        # Draw title
        painter.setFont(title_font)
        painter.setPen(QColor(TEXT_PRIMARY))
        title_rect = QRect(rect.left(), y, rect.width(), title_metrics.height())
        elided_title = title_metrics.elidedText(title, Qt.ElideRight, rect.width())
        painter.drawText(title_rect, Qt.AlignLeft | Qt.AlignVCenter, elided_title)
        y += title_metrics.height() + line_spacing

        # Draw genres
        if genres:
            painter.setFont(body_font)
            painter.setPen(QColor(TEXT_SECONDARY))
            genres_rect = QRect(rect.left(), y, rect.width(), body_metrics.height())
            elided_genres = body_metrics.elidedText(genres, Qt.ElideRight, rect.width())
            painter.drawText(genres_rect, Qt.AlignLeft | Qt.AlignVCenter, elided_genres)
            y += body_metrics.height() + line_spacing

        # Draw subtitle
        if subtitle:
            painter.setFont(small_font)
            painter.setPen(QColor(TEXT_SECONDARY))
            subtitle_rect = QRect(rect.left(), y, rect.width(), small_metrics.height())
            elided_subtitle = small_metrics.elidedText(
                subtitle, Qt.ElideRight, rect.width()
            )
            painter.drawText(
                subtitle_rect, Qt.AlignLeft | Qt.AlignVCenter, elided_subtitle
            )

    def _build_subtitle(self, index: QModelIndex) -> str:
        """Build subtitle text based on item type.

        Args:
            index: Model index of the item.

        Returns:
            Subtitle string.
        """
        item_type = index.data(LibraryItemRole.TypeRole)

        if item_type == "series":
            season_count = index.data(LibraryItemRole.SeasonCountRole) or 0
            return f"{season_count} Season{'s' if season_count != 1 else ''}"
        elif item_type == "season":
            season_num = index.data(LibraryItemRole.SeasonNumberRole) or 0
            episode_count = index.data(LibraryItemRole.EpisodeCountRole) or 0
            return f"Season {season_num} \u2022 {episode_count} Episode{'s' if episode_count != 1 else ''}"
        elif item_type == "episode":
            ep_num = index.data(LibraryItemRole.EpisodeNumberRole) or 0
            ep_title = index.data(LibraryItemRole.EpisodeTitleRole) or ""
            if ep_title:
                return f"Episode {ep_num}: {ep_title}"
            return f"Episode {ep_num}"

        return ""

    def _draw_status(
        self, painter: QPainter, rect: QRect, index: QModelIndex
    ) -> None:
        """Draw the status icon.

        Args:
            painter: The QPainter to draw with.
            rect: Rectangle for the status icon.
            index: Model index of the item.
        """
        item_type = index.data(LibraryItemRole.TypeRole)
        download_state = index.data(LibraryItemRole.DownloadStateRole)
        progress = index.data(LibraryItemRole.DownloadProgressRole) or 0

        # Determine status
        if item_type == "series":
            status = "series"
        elif download_state == DownloadState.COMPLETED.value:
            status = "completed"
        elif download_state == DownloadState.DOWNLOADING.value:
            status = "downloading"
        elif download_state == DownloadState.ERROR.value:
            status = "error"
        else:
            status = "pending"

        icon = self._STATUS_ICONS.get(status, "?")
        color = self._STATUS_COLORS.get(status, TEXT_SECONDARY)

        # Draw icon
        font = QFont(FONT_FAMILY, STATUS_ICON_SIZE - 8)
        painter.setFont(font)
        painter.setPen(QColor(color))
        painter.drawText(rect, Qt.AlignCenter, icon)

        # Draw progress percentage if downloading
        if status == "downloading" and progress > 0:
            small_font = QFont(FONT_FAMILY, FONT_SIZE_SMALL - 2)
            painter.setFont(small_font)
            progress_rect = QRect(
                rect.left(), rect.bottom() + 2, rect.width(), FONT_SIZE_SMALL
            )
            painter.drawText(progress_rect, Qt.AlignCenter, f"{progress}%")

    def sizeHint(
        self, option: QStyleOptionViewItem, index: QModelIndex
    ) -> QSize:
        """Return the size hint for an item.

        Args:
            option: Style options for the item.
            index: Model index of the item.

        Returns:
            QSize with the preferred item size.
        """
        return QSize(option.rect.width(), ROW_HEIGHT)

    def clear_poster_cache(self) -> None:
        """Clear the poster image cache."""
        self._poster_cache.clear()
