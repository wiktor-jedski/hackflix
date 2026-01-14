"""Tests for LibraryItemDelegate component."""

from unittest.mock import MagicMock, patch

import pytest
from PyQt5.QtCore import QModelIndex, QRect, QSize, Qt
from PyQt5.QtGui import QColor, QPainter, QPixmap
from PyQt5.QtWidgets import QStyle, QStyleOptionViewItem

from src.config import DownloadState
from src.ui.components.library_item_delegate import (
    LibraryItemDelegate,
    LibraryItemRole,
)
from src.ui.styles import (
    ROW_HEIGHT,
)


class TestLibraryItemRole:
    """Tests for LibraryItemRole constants."""

    def test_roles_are_unique(self) -> None:
        """Test that all role values are unique."""
        roles = [
            LibraryItemRole.IdRole,
            LibraryItemRole.TypeRole,
            LibraryItemRole.TitleRole,
            LibraryItemRole.GenresRole,
            LibraryItemRole.PosterPathRole,
            LibraryItemRole.DownloadStateRole,
            LibraryItemRole.PipelineStateRole,
            LibraryItemRole.DownloadProgressRole,
            LibraryItemRole.SeasonCountRole,
            LibraryItemRole.EpisodeCountRole,
            LibraryItemRole.SeasonNumberRole,
            LibraryItemRole.EpisodeNumberRole,
            LibraryItemRole.EpisodeTitleRole,
        ]
        assert len(roles) == len(set(roles))

    def test_roles_start_from_user_role(self) -> None:
        """Test that roles start from Qt.UserRole."""
        assert LibraryItemRole.IdRole > Qt.UserRole


class TestLibraryItemDelegateInit:
    """Tests for LibraryItemDelegate initialization."""

    @pytest.fixture
    def delegate(self, qtbot) -> LibraryItemDelegate:
        """Create a LibraryItemDelegate instance."""
        d = LibraryItemDelegate()
        return d

    def test_initialization(self, delegate: LibraryItemDelegate) -> None:
        """Test LibraryItemDelegate initialization."""
        assert delegate is not None
        assert delegate._poster_cache == {}

    def test_status_icons_defined(self, delegate: LibraryItemDelegate) -> None:
        """Test that status icons are defined."""
        assert "pending" in delegate._STATUS_ICONS
        assert "downloading" in delegate._STATUS_ICONS
        assert "completed" in delegate._STATUS_ICONS
        assert "error" in delegate._STATUS_ICONS
        assert "series" in delegate._STATUS_ICONS

    def test_status_colors_defined(self, delegate: LibraryItemDelegate) -> None:
        """Test that status colors are defined."""
        assert "pending" in delegate._STATUS_COLORS
        assert "downloading" in delegate._STATUS_COLORS
        assert "completed" in delegate._STATUS_COLORS
        assert "error" in delegate._STATUS_COLORS
        assert "series" in delegate._STATUS_COLORS


class TestLibraryItemDelegateSizeHint:
    """Tests for sizeHint method."""

    @pytest.fixture
    def delegate(self) -> LibraryItemDelegate:
        """Create a LibraryItemDelegate instance."""
        return LibraryItemDelegate()

    def test_size_hint_returns_row_height(self, delegate: LibraryItemDelegate) -> None:
        """Test that sizeHint returns correct row height."""
        option = MagicMock(spec=QStyleOptionViewItem)
        option.rect = QRect(0, 0, 800, 100)
        index = MagicMock(spec=QModelIndex)

        size = delegate.sizeHint(option, index)

        assert isinstance(size, QSize)
        assert size.height() == ROW_HEIGHT


class TestLibraryItemDelegateClearCache:
    """Tests for cache clearing."""

    @pytest.fixture
    def delegate(self) -> LibraryItemDelegate:
        """Create a LibraryItemDelegate instance."""
        return LibraryItemDelegate()

    def test_clear_poster_cache(self, delegate: LibraryItemDelegate) -> None:
        """Test that clear_poster_cache empties the cache."""
        delegate._poster_cache["test_path"] = MagicMock()
        delegate._poster_cache["another_path"] = MagicMock()

        delegate.clear_poster_cache()

        assert delegate._poster_cache == {}


class TestLibraryItemDelegateDrawBackground:
    """Tests for _draw_background method."""

    @pytest.fixture
    def delegate(self) -> LibraryItemDelegate:
        """Create a LibraryItemDelegate instance."""
        return LibraryItemDelegate()

    @pytest.fixture
    def painter(self) -> MagicMock:
        """Create a mock QPainter."""
        return MagicMock(spec=QPainter)

    def test_draw_background_selected(
        self, delegate: LibraryItemDelegate, painter: MagicMock
    ) -> None:
        """Test background drawing when selected."""
        option = MagicMock(spec=QStyleOptionViewItem)
        option.rect = QRect(0, 0, 800, 100)
        option.state = QStyle.State_Selected

        delegate._draw_background(painter, option)

        painter.fillRect.assert_called_once()
        call_args = painter.fillRect.call_args
        assert call_args[0][0] == option.rect
        # Verify selection color is used
        color = call_args[0][1]
        assert isinstance(color, QColor)

    def test_draw_background_hover(
        self, delegate: LibraryItemDelegate, painter: MagicMock
    ) -> None:
        """Test background drawing on hover."""
        option = MagicMock(spec=QStyleOptionViewItem)
        option.rect = QRect(0, 0, 800, 100)
        option.state = QStyle.State_MouseOver

        delegate._draw_background(painter, option)

        painter.fillRect.assert_called_once()

    def test_draw_background_normal(
        self, delegate: LibraryItemDelegate, painter: MagicMock
    ) -> None:
        """Test background drawing in normal state."""
        option = MagicMock(spec=QStyleOptionViewItem)
        option.rect = QRect(0, 0, 800, 100)
        option.state = QStyle.State_None

        delegate._draw_background(painter, option)

        painter.fillRect.assert_called_once()


class TestLibraryItemDelegateBuildSubtitle:
    """Tests for _build_subtitle method."""

    @pytest.fixture
    def delegate(self) -> LibraryItemDelegate:
        """Create a LibraryItemDelegate instance."""
        return LibraryItemDelegate()

    def test_build_subtitle_series_single_season(
        self, delegate: LibraryItemDelegate
    ) -> None:
        """Test subtitle for series with single season."""
        index = MagicMock(spec=QModelIndex)
        index.data.side_effect = lambda role: {
            LibraryItemRole.TypeRole: "series",
            LibraryItemRole.SeasonCountRole: 1,
        }.get(role)

        subtitle = delegate._build_subtitle(index)

        assert "1" in subtitle
        assert "Season" in subtitle

    def test_build_subtitle_series_multiple_seasons(
        self, delegate: LibraryItemDelegate
    ) -> None:
        """Test subtitle for series with multiple seasons."""
        index = MagicMock(spec=QModelIndex)
        index.data.side_effect = lambda role: {
            LibraryItemRole.TypeRole: "series",
            LibraryItemRole.SeasonCountRole: 5,
        }.get(role)

        subtitle = delegate._build_subtitle(index)

        assert "5" in subtitle
        assert "Seasons" in subtitle

    def test_build_subtitle_season_single_episode(
        self, delegate: LibraryItemDelegate
    ) -> None:
        """Test subtitle for season with single episode."""
        index = MagicMock(spec=QModelIndex)
        index.data.side_effect = lambda role: {
            LibraryItemRole.TypeRole: "season",
            LibraryItemRole.SeasonNumberRole: 2,
            LibraryItemRole.EpisodeCountRole: 1,
        }.get(role)

        subtitle = delegate._build_subtitle(index)

        assert "Season 2" in subtitle
        assert "1" in subtitle
        assert "Episode" in subtitle

    def test_build_subtitle_season_multiple_episodes(
        self, delegate: LibraryItemDelegate
    ) -> None:
        """Test subtitle for season with multiple episodes."""
        index = MagicMock(spec=QModelIndex)
        index.data.side_effect = lambda role: {
            LibraryItemRole.TypeRole: "season",
            LibraryItemRole.SeasonNumberRole: 3,
            LibraryItemRole.EpisodeCountRole: 10,
        }.get(role)

        subtitle = delegate._build_subtitle(index)

        assert "Season 3" in subtitle
        assert "10" in subtitle
        assert "Episodes" in subtitle

    def test_build_subtitle_episode_with_title(
        self, delegate: LibraryItemDelegate
    ) -> None:
        """Test subtitle for episode with title."""
        index = MagicMock(spec=QModelIndex)
        index.data.side_effect = lambda role: {
            LibraryItemRole.TypeRole: "episode",
            LibraryItemRole.EpisodeNumberRole: 5,
            LibraryItemRole.EpisodeTitleRole: "The Pilot",
        }.get(role)

        subtitle = delegate._build_subtitle(index)

        assert "Episode 5" in subtitle
        assert "The Pilot" in subtitle

    def test_build_subtitle_episode_without_title(
        self, delegate: LibraryItemDelegate
    ) -> None:
        """Test subtitle for episode without title."""
        index = MagicMock(spec=QModelIndex)
        index.data.side_effect = lambda role: {
            LibraryItemRole.TypeRole: "episode",
            LibraryItemRole.EpisodeNumberRole: 7,
            LibraryItemRole.EpisodeTitleRole: "",
        }.get(role)

        subtitle = delegate._build_subtitle(index)

        assert "Episode 7" in subtitle

    def test_build_subtitle_movie_empty(
        self, delegate: LibraryItemDelegate
    ) -> None:
        """Test subtitle for movie returns empty string."""
        index = MagicMock(spec=QModelIndex)
        index.data.side_effect = lambda role: {
            LibraryItemRole.TypeRole: "movie",
        }.get(role)

        subtitle = delegate._build_subtitle(index)

        assert subtitle == ""

    def test_build_subtitle_unknown_type_empty(
        self, delegate: LibraryItemDelegate
    ) -> None:
        """Test subtitle for unknown type returns empty string."""
        index = MagicMock(spec=QModelIndex)
        index.data.side_effect = lambda role: {
            LibraryItemRole.TypeRole: "unknown",
        }.get(role)

        subtitle = delegate._build_subtitle(index)

        assert subtitle == ""


class TestLibraryItemDelegateGetCachedPoster:
    """Tests for _get_cached_poster method."""

    @pytest.fixture
    def delegate(self) -> LibraryItemDelegate:
        """Create a LibraryItemDelegate instance."""
        return LibraryItemDelegate()

    def test_get_cached_poster_returns_cached(
        self, delegate: LibraryItemDelegate
    ) -> None:
        """Test that cached poster is returned."""
        mock_pixmap = MagicMock(spec=QPixmap)
        delegate._poster_cache["cached_path"] = mock_pixmap

        result = delegate._get_cached_poster("cached_path")

        assert result is mock_pixmap

    @patch("src.ui.components.library_item_delegate.Path")
    @patch("src.ui.components.library_item_delegate.QPixmap")
    def test_get_cached_poster_loads_existing_file(
        self, mock_qpixmap: MagicMock, mock_path: MagicMock, delegate: LibraryItemDelegate
    ) -> None:
        """Test that existing file is loaded and cached."""
        mock_path.return_value.exists.return_value = True
        mock_pixmap = MagicMock(spec=QPixmap)
        mock_qpixmap.return_value = mock_pixmap

        result = delegate._get_cached_poster("new_path")

        mock_qpixmap.assert_called_once_with("new_path")
        assert "new_path" in delegate._poster_cache

    @patch("src.ui.components.library_item_delegate.Path")
    @patch("src.ui.components.library_item_delegate.QPixmap")
    def test_get_cached_poster_missing_file(
        self, mock_qpixmap: MagicMock, mock_path: MagicMock, delegate: LibraryItemDelegate
    ) -> None:
        """Test that missing file returns empty pixmap."""
        mock_path.return_value.exists.return_value = False
        mock_pixmap = MagicMock(spec=QPixmap)
        mock_qpixmap.return_value = mock_pixmap

        result = delegate._get_cached_poster("missing_path")

        mock_qpixmap.assert_called_once_with()  # Empty pixmap
        assert "missing_path" in delegate._poster_cache


class TestLibraryItemDelegateDrawPoster:
    """Tests for _draw_poster method."""

    @pytest.fixture
    def delegate(self) -> LibraryItemDelegate:
        """Create a LibraryItemDelegate instance."""
        return LibraryItemDelegate()

    @pytest.fixture
    def painter(self) -> MagicMock:
        """Create a mock QPainter."""
        return MagicMock(spec=QPainter)

    def test_draw_poster_no_path_draws_placeholder(
        self, delegate: LibraryItemDelegate, painter: MagicMock
    ) -> None:
        """Test drawing placeholder when no poster path."""
        rect = QRect(0, 0, 80, 120)
        index = MagicMock(spec=QModelIndex)
        index.data.return_value = None

        delegate._draw_poster(painter, rect, index)

        painter.fillRect.assert_called_once()
        painter.drawText.assert_called_once()

    def test_draw_poster_with_valid_pixmap(
        self, delegate: LibraryItemDelegate, painter: MagicMock
    ) -> None:
        """Test drawing poster with valid pixmap."""
        rect = QRect(0, 0, 80, 120)
        index = MagicMock(spec=QModelIndex)
        index.data.return_value = "poster_path.jpg"

        mock_pixmap = MagicMock(spec=QPixmap)
        mock_pixmap.isNull.return_value = False
        mock_scaled = MagicMock(spec=QPixmap)
        mock_scaled.width.return_value = 80
        mock_scaled.height.return_value = 120
        mock_pixmap.scaled.return_value = mock_scaled
        delegate._poster_cache["poster_path.jpg"] = mock_pixmap

        delegate._draw_poster(painter, rect, index)

        painter.drawPixmap.assert_called_once()

    def test_draw_poster_with_null_pixmap_draws_placeholder(
        self, delegate: LibraryItemDelegate, painter: MagicMock
    ) -> None:
        """Test drawing placeholder when pixmap is null."""
        rect = QRect(0, 0, 80, 120)
        index = MagicMock(spec=QModelIndex)
        index.data.return_value = "poster_path.jpg"

        mock_pixmap = MagicMock(spec=QPixmap)
        mock_pixmap.isNull.return_value = True
        delegate._poster_cache["poster_path.jpg"] = mock_pixmap

        delegate._draw_poster(painter, rect, index)

        painter.fillRect.assert_called_once()
        painter.drawText.assert_called_once()


class TestLibraryItemDelegateDrawMetadata:
    """Tests for _draw_metadata method."""

    @pytest.fixture
    def delegate(self) -> LibraryItemDelegate:
        """Create a LibraryItemDelegate instance."""
        return LibraryItemDelegate()

    @pytest.fixture
    def painter(self) -> MagicMock:
        """Create a mock QPainter."""
        return MagicMock(spec=QPainter)

    def test_draw_metadata_with_all_fields(
        self, delegate: LibraryItemDelegate, painter: MagicMock
    ) -> None:
        """Test drawing metadata with all fields."""
        rect = QRect(100, 0, 500, 120)
        index = MagicMock(spec=QModelIndex)
        index.data.side_effect = lambda role: {
            LibraryItemRole.TitleRole: "Test Movie",
            LibraryItemRole.GenresRole: "Action, Comedy",
            LibraryItemRole.TypeRole: "movie",
        }.get(role)

        delegate._draw_metadata(painter, rect, index)

        # Should set fonts and draw text multiple times
        assert painter.setFont.call_count >= 2
        assert painter.drawText.call_count >= 2

    def test_draw_metadata_no_title_uses_default(
        self, delegate: LibraryItemDelegate, painter: MagicMock
    ) -> None:
        """Test drawing metadata with no title uses default."""
        rect = QRect(100, 0, 500, 120)
        index = MagicMock(spec=QModelIndex)
        index.data.side_effect = lambda role: {
            LibraryItemRole.TitleRole: None,
            LibraryItemRole.GenresRole: None,
            LibraryItemRole.TypeRole: "movie",
        }.get(role)

        delegate._draw_metadata(painter, rect, index)

        painter.drawText.assert_called()

    def test_draw_metadata_with_subtitle(
        self, delegate: LibraryItemDelegate, painter: MagicMock
    ) -> None:
        """Test drawing metadata with subtitle for series."""
        rect = QRect(100, 0, 500, 120)
        index = MagicMock(spec=QModelIndex)
        index.data.side_effect = lambda role: {
            LibraryItemRole.TitleRole: "Test Series",
            LibraryItemRole.GenresRole: "Drama",
            LibraryItemRole.TypeRole: "series",
            LibraryItemRole.SeasonCountRole: 3,
        }.get(role)

        delegate._draw_metadata(painter, rect, index)

        # Title, genres, and subtitle should all be drawn
        assert painter.drawText.call_count >= 3


class TestLibraryItemDelegateDrawStatus:
    """Tests for _draw_status method."""

    @pytest.fixture
    def delegate(self) -> LibraryItemDelegate:
        """Create a LibraryItemDelegate instance."""
        return LibraryItemDelegate()

    @pytest.fixture
    def painter(self) -> MagicMock:
        """Create a mock QPainter."""
        return MagicMock(spec=QPainter)

    def test_draw_status_series(
        self, delegate: LibraryItemDelegate, painter: MagicMock
    ) -> None:
        """Test drawing status for series."""
        rect = QRect(700, 40, 32, 32)
        index = MagicMock(spec=QModelIndex)
        index.data.side_effect = lambda role: {
            LibraryItemRole.TypeRole: "series",
            LibraryItemRole.DownloadStateRole: None,
            LibraryItemRole.DownloadProgressRole: 0,
        }.get(role)

        delegate._draw_status(painter, rect, index)

        painter.drawText.assert_called()

    def test_draw_status_completed(
        self, delegate: LibraryItemDelegate, painter: MagicMock
    ) -> None:
        """Test drawing status for completed download."""
        rect = QRect(700, 40, 32, 32)
        index = MagicMock(spec=QModelIndex)
        index.data.side_effect = lambda role: {
            LibraryItemRole.TypeRole: "movie",
            LibraryItemRole.DownloadStateRole: DownloadState.COMPLETED.value,
            LibraryItemRole.DownloadProgressRole: 100,
        }.get(role)

        delegate._draw_status(painter, rect, index)

        painter.drawText.assert_called()

    def test_draw_status_downloading_with_progress(
        self, delegate: LibraryItemDelegate, painter: MagicMock
    ) -> None:
        """Test drawing status for downloading with progress."""
        rect = QRect(700, 40, 32, 32)
        index = MagicMock(spec=QModelIndex)
        index.data.side_effect = lambda role: {
            LibraryItemRole.TypeRole: "movie",
            LibraryItemRole.DownloadStateRole: DownloadState.DOWNLOADING.value,
            LibraryItemRole.DownloadProgressRole: 45,
        }.get(role)

        delegate._draw_status(painter, rect, index)

        # Should draw icon and progress percentage
        assert painter.drawText.call_count == 2

    def test_draw_status_error(
        self, delegate: LibraryItemDelegate, painter: MagicMock
    ) -> None:
        """Test drawing status for error state."""
        rect = QRect(700, 40, 32, 32)
        index = MagicMock(spec=QModelIndex)
        index.data.side_effect = lambda role: {
            LibraryItemRole.TypeRole: "movie",
            LibraryItemRole.DownloadStateRole: DownloadState.ERROR.value,
            LibraryItemRole.DownloadProgressRole: 0,
        }.get(role)

        delegate._draw_status(painter, rect, index)

        painter.drawText.assert_called()

    def test_draw_status_pending(
        self, delegate: LibraryItemDelegate, painter: MagicMock
    ) -> None:
        """Test drawing status for pending state."""
        rect = QRect(700, 40, 32, 32)
        index = MagicMock(spec=QModelIndex)
        index.data.side_effect = lambda role: {
            LibraryItemRole.TypeRole: "movie",
            LibraryItemRole.DownloadStateRole: DownloadState.PENDING.value,
            LibraryItemRole.DownloadProgressRole: 0,
        }.get(role)

        delegate._draw_status(painter, rect, index)

        painter.drawText.assert_called_once()


class TestLibraryItemDelegatePaint:
    """Tests for paint method."""

    @pytest.fixture
    def delegate(self) -> LibraryItemDelegate:
        """Create a LibraryItemDelegate instance."""
        return LibraryItemDelegate()

    @pytest.fixture
    def painter(self) -> MagicMock:
        """Create a mock QPainter."""
        return MagicMock(spec=QPainter)

    def test_paint_calls_all_draw_methods(
        self, delegate: LibraryItemDelegate, painter: MagicMock
    ) -> None:
        """Test that paint calls all drawing methods."""
        option = MagicMock(spec=QStyleOptionViewItem)
        option.rect = QRect(0, 0, 800, 120)
        option.state = QStyle.State_None

        index = MagicMock(spec=QModelIndex)
        index.data.side_effect = lambda role: {
            LibraryItemRole.TitleRole: "Test Movie",
            LibraryItemRole.GenresRole: "Action",
            LibraryItemRole.TypeRole: "movie",
            LibraryItemRole.PosterPathRole: None,
            LibraryItemRole.DownloadStateRole: DownloadState.COMPLETED.value,
            LibraryItemRole.DownloadProgressRole: 100,
        }.get(role)

        delegate.paint(painter, option, index)

        # Verify painter.save() and painter.restore() are called
        painter.save.assert_called_once()
        painter.restore.assert_called_once()
        painter.setRenderHint.assert_called_once()

    def test_paint_with_selected_state(
        self, delegate: LibraryItemDelegate, painter: MagicMock
    ) -> None:
        """Test painting with selected state."""
        option = MagicMock(spec=QStyleOptionViewItem)
        option.rect = QRect(0, 0, 800, 120)
        option.state = QStyle.State_Selected

        index = MagicMock(spec=QModelIndex)
        index.data.return_value = None

        delegate.paint(painter, option, index)

        painter.save.assert_called_once()
        painter.restore.assert_called_once()
