"""Library item delegate for custom row rendering.

This module provides the LibraryItemDelegate for rendering
media items in the library list view.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QModelIndex, QPersistentModelIndex, QRect, QSize, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPixmap
from PySide6.QtWidgets import QStyle, QStyledItemDelegate, QStyleOptionViewItem, QWidget

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
from src.utils.i18n import tr


# Data roles for model items
class LibraryItemRole:
    """Custom data roles for library items."""

    IdRole = Qt.UserRole + 1  # type: ignore[attr-defined]
    TypeRole = Qt.UserRole + 2  # type: ignore[attr-defined]
    TitleRole = Qt.UserRole + 3  # type: ignore[attr-defined]
    GenresRole = Qt.UserRole + 4  # type: ignore[attr-defined]
    PosterPathRole = Qt.UserRole + 5  # type: ignore[attr-defined]
    DownloadStateRole = Qt.UserRole + 6  # type: ignore[attr-defined]
    PipelineStateRole = Qt.UserRole + 7  # type: ignore[attr-defined]
    DownloadProgressRole = Qt.UserRole + 8  # type: ignore[attr-defined]
    SeasonCountRole = Qt.UserRole + 9  # type: ignore[attr-defined]
    EpisodeCountRole = Qt.UserRole + 10  # type: ignore[attr-defined]
    SeasonNumberRole = Qt.UserRole + 11  # type: ignore[attr-defined]
    EpisodeNumberRole = Qt.UserRole + 12  # type: ignore[attr-defined]
    EpisodeTitleRole = Qt.UserRole + 13  # type: ignore[attr-defined]
    FileIdRole = Qt.UserRole + 14  # type: ignore[attr-defined]


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
        "subs_processing": "\u8bd1",  # 译 Chinese character (processing subtitles)
        "subs_ready": "\u25b6",  # Play button (subtitles ready)
        "pipeline_failed": "\u26a0",  # Warning triangle
    }

    # Status colors
    _STATUS_COLORS = {
        "pending": TEXT_SECONDARY,
        "downloading": WARNING_COLOR,
        "completed": SUCCESS_COLOR,
        "error": ERROR_COLOR,
        "series": TEXT_SECONDARY,
        "subs_processing": WARNING_COLOR,
        "subs_ready": SUCCESS_COLOR,
        "pipeline_failed": ERROR_COLOR,
    }

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the delegate.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self._poster_cache: dict[str, QPixmap] = {}

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        """Paint a library item.

        Args:
            painter: The QPainter to draw with.
            option: Style options for the item.
            index: Model index of the item.
        """
        if painter is None:
            return
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw background
        self._draw_background(painter, option)

        # Calculate areas
        rect = option.rect.adjusted(
            ITEM_PADDING, ITEM_PADDING, -ITEM_PADDING, -ITEM_PADDING
        )

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

    def _draw_background(self, painter: QPainter, option: QStyleOptionViewItem) -> None:
        """Draw the item background.

        Args:
            painter: The QPainter to draw with.
            option: Style options for the item.
        """
        rect = option.rect

        if option.state & QStyle.State_Selected:  # type: ignore[attr-defined]
            color = QColor(SELECTION_COLOR)
        elif option.state & QStyle.State_MouseOver:  # type: ignore[attr-defined]
            color = QColor(SURFACE_HOVER_COLOR)
        else:
            color = QColor(SURFACE_COLOR)

        painter.fillRect(rect, color)

    def _draw_poster(self, painter: QPainter, rect: QRect, index: QModelIndex | QPersistentModelIndex) -> None:
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
                    Qt.KeepAspectRatio,  # type: ignore[attr-defined]
                    Qt.SmoothTransformation,  # type: ignore[attr-defined]
                )
                # Center in rect
                x = rect.x() + (rect.width() - scaled.width()) // 2
                y = rect.y() + (rect.height() - scaled.height()) // 2
                painter.drawPixmap(x, y, scaled)
                return

        # Draw placeholder
        painter.fillRect(rect, QColor(SURFACE_HOVER_COLOR))
        painter.setPen(QColor(TEXT_SECONDARY))
        painter.drawText(rect, Qt.AlignCenter, tr("LibraryItemDelegate", "No\nImage"))  # type: ignore[attr-defined]

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
        self, painter: QPainter, rect: QRect, index: QModelIndex | QPersistentModelIndex
    ) -> None:
        """Draw the metadata section.

        Args:
            painter: The QPainter to draw with.
            rect: Rectangle for metadata.
            index: Model index of the item.
        """
        title = index.data(LibraryItemRole.TitleRole) or tr(
            "LibraryItemDelegate", "Unknown Title"
        )
        genres = index.data(LibraryItemRole.GenresRole) or ""

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
        elided_title = title_metrics.elidedText(
            title,
            Qt.ElideRight,  # type: ignore[attr-defined]
            rect.width(),
        )
        painter.drawText(
            title_rect,
            Qt.AlignLeft | Qt.AlignVCenter,  # type: ignore[attr-defined]
            elided_title,
        )
        y += title_metrics.height() + line_spacing

        # Draw genres
        if genres:
            painter.setFont(body_font)
            painter.setPen(QColor(TEXT_SECONDARY))
            genres_rect = QRect(rect.left(), y, rect.width(), body_metrics.height())
            elided_genres = body_metrics.elidedText(
                genres,
                Qt.ElideRight,  # type: ignore[attr-defined]
                rect.width(),
            )
            painter.drawText(
                genres_rect,
                Qt.AlignLeft | Qt.AlignVCenter,  # type: ignore[attr-defined]
                elided_genres,
            )
            y += body_metrics.height() + line_spacing

        # Draw subtitle
        if subtitle:
            painter.setFont(small_font)
            painter.setPen(QColor(TEXT_SECONDARY))
            subtitle_rect = QRect(rect.left(), y, rect.width(), small_metrics.height())
            elided_subtitle = small_metrics.elidedText(
                subtitle,
                Qt.ElideRight,  # type: ignore[attr-defined]
                rect.width(),
            )
            painter.drawText(
                subtitle_rect,
                Qt.AlignLeft | Qt.AlignVCenter,  # type: ignore[attr-defined]
                elided_subtitle,
            )

    def _build_subtitle(self, index: QModelIndex | QPersistentModelIndex) -> str:
        """Build subtitle text based on item type.

        Args:
            index: Model index of the item.

        Returns:
            Subtitle string.
        """
        item_type = index.data(LibraryItemRole.TypeRole)

        if item_type == "series":
            season_count = index.data(LibraryItemRole.SeasonCountRole) or 0
            if season_count == 1:
                return tr("LibraryItemDelegate", "%n Season").replace(
                    "%n", str(season_count)
                )
            return tr("LibraryItemDelegate", "%n Seasons").replace(
                "%n", str(season_count)
            )
        elif item_type == "season":
            season_num = index.data(LibraryItemRole.SeasonNumberRole) or 0
            episode_count = index.data(LibraryItemRole.EpisodeCountRole) or 0
            season_str = tr("LibraryItemDelegate", "Season %n").replace(
                "%n", str(season_num)
            )
            if episode_count == 1:
                episode_str = tr("LibraryItemDelegate", "%n Episode").replace(
                    "%n", str(episode_count)
                )
            else:
                episode_str = tr("LibraryItemDelegate", "%n Episodes").replace(
                    "%n", str(episode_count)
                )
            return f"{season_str} \u2022 {episode_str}"
        elif item_type == "episode":
            ep_num = index.data(LibraryItemRole.EpisodeNumberRole) or 0
            ep_title = index.data(LibraryItemRole.EpisodeTitleRole) or ""
            if ep_title:
                return (
                    tr("LibraryItemDelegate", "Episode %n: %t")
                    .replace("%n", str(ep_num))
                    .replace("%t", ep_title)
                )
            return tr("LibraryItemDelegate", "Episode %n").replace("%n", str(ep_num))

        return ""

    def _draw_status(self, painter: QPainter, rect: QRect, index: QModelIndex | QPersistentModelIndex) -> None:
        """Draw the status icon.

        Args:
            painter: The QPainter to draw with.
            rect: Rectangle for the status icon.
            index: Model index of the item.
        """
        item_type = index.data(LibraryItemRole.TypeRole)
        download_state = index.data(LibraryItemRole.DownloadStateRole)
        pipeline_state = index.data(LibraryItemRole.PipelineStateRole)
        progress = index.data(LibraryItemRole.DownloadProgressRole) or 0

        # Determine status - pipeline states take precedence over download states
        if item_type == "series":
            status = "series"
        elif pipeline_state in (
            PipelineState.FETCHING_SUBS.value,
            PipelineState.TRANSLATING.value,
        ):
            status = "subs_processing"
        elif pipeline_state == PipelineState.SUBS_READY.value:
            status = "subs_ready"
        elif pipeline_state == PipelineState.FAILED.value:
            status = "pipeline_failed"
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
        painter.drawText(rect, Qt.AlignCenter, icon)  # type: ignore[attr-defined]

        # Draw progress percentage if downloading
        if status == "downloading" and progress > 0:
            small_font = QFont(FONT_FAMILY, FONT_SIZE_SMALL - 2)
            painter.setFont(small_font)
            progress_rect = QRect(
                rect.left(), rect.bottom() + 2, rect.width(), FONT_SIZE_SMALL
            )
            painter.drawText(progress_rect, Qt.AlignCenter, f"{progress}%")  # type: ignore[attr-defined]

    def sizeHint(
        self,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
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
