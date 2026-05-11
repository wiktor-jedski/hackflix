"""Tests for the TorrentService."""

import pickle
import sys
from pathlib import Path
from unittest import mock

import pytest

from src.config import DownloadState, TORRENT_POLL_INTERVAL_MS
from src.database.db_manager import DatabaseManager


# Mock libtorrent before importing TorrentService
@pytest.fixture(autouse=True)
def mock_libtorrent_module(monkeypatch: pytest.MonkeyPatch):
    """Mock libtorrent module for all tests."""
    monkeypatch.setenv("HACKFLIX_TORRENT_BACKEND", "embedded")
    mock_lt = mock.MagicMock()

    # Setup session mock with all required methods
    mock_session = mock.MagicMock()
    mock_session.save_state.return_value = {"test": "state"}
    mock_session.load_state.return_value = None
    mock_session.add_torrent.return_value = mock.MagicMock()
    mock_session.remove_torrent.return_value = None
    mock_session.pop_alerts.return_value = []
    mock_session.wait_for_alert.return_value = None
    mock_lt.session.return_value = mock_session

    # Setup bdecode/bencode functions
    mock_lt.bdecode.return_value = {"test": "decoded"}
    mock_lt.bencode.return_value = b"encoded"

    # Setup add_torrent_params mock
    mock_atp = mock.MagicMock()
    mock_lt.add_torrent_params.return_value = mock_atp

    # Setup torrent_handle mock
    mock_handle = mock.MagicMock()
    mock_handle.is_valid.return_value = True
    mock_handle.info_hash.return_value = "test_hash"
    mock_session.add_torrent.return_value = mock_handle

    # Setup alert mocks
    mock_alert = mock.MagicMock()
    mock_alert.handle.info_hash.return_value = "test_hash"
    mock_lt.save_resume_data_alert = mock_alert

    # Setup write_resume_data_buf
    mock_lt.write_resume_data_buf.return_value = b"resume_data"

    # Setup alert category constants
    mock_lt.alert.category_t.error_notification = 1
    mock_lt.alert.category_t.status_notification = 2
    mock_lt.alert.category_t.storage_notification = 4

    # Setup torrent states
    mock_lt.torrent_status.states.seeding = "seeding"
    mock_lt.torrent_status.states.downloading = "downloading"

    # Setup save resume data flags
    mock_lt.torrent_handle.save_info_dict = 1
    mock_lt.torrent_handle.only_if_modified = 2

    # Setup pop_alerts and wait_for_alert
    mock_session.pop_alerts.return_value = []
    mock_session.wait_for_alert.return_value = None

    # Setup parse_magnet_uri - return object with attribute access
    class MagnetInfo:
        def __init__(self):
            self.info_hash = "test_hash"
            self.trackers = []
            self.url_list = []
            self.save_path = ""

    mock_lt.parse_magnet_uri.return_value = MagnetInfo()

    # Force reload of torrent_service to ensure it uses the mocked libtorrent
    if "src.services.torrent_service" in sys.modules:
        del sys.modules["src.services.torrent_service"]

    # Remove any existing libtorrent from sys.modules to force clean import
    modules_to_remove = [k for k in sys.modules.keys() if "libtorrent" in k]
    for module in modules_to_remove:
        del sys.modules[module]

    # Force immediate module patching
    with mock.patch.dict("sys.modules", {"libtorrent": mock_lt}):
        yield mock_lt


class TestDownloadTypeAndContext:
    """Tests for DownloadType and DownloadContext classes."""

    def test_download_type_values(self, mock_libtorrent_module: mock.MagicMock) -> None:
        """Test DownloadType enum values."""
        from src.services.torrent_service import DownloadType

        assert DownloadType.MOVIE.value == "movie"
        assert DownloadType.SEASON.value == "season"

    def test_download_context_creation(
        self, mock_libtorrent_module: mock.MagicMock
    ) -> None:
        """Test DownloadContext dataclass creation."""
        from src.services.torrent_service import DownloadContext, DownloadType

        movie_ctx = DownloadContext(DownloadType.MOVIE, 123)
        assert movie_ctx.download_type == DownloadType.MOVIE
        assert movie_ctx.id == 123

        season_ctx = DownloadContext(DownloadType.SEASON, 456)
        assert season_ctx.download_type == DownloadType.SEASON
        assert season_ctx.id == 456


class TestTorrentServiceInit:
    """Tests for TorrentService initialization."""

    def test_init_with_defaults(
        self, mock_libtorrent_module: mock.MagicMock, db_manager: DatabaseManager
    ) -> None:
        """Test initialization with default values."""
        from src.services.torrent_service import TorrentService

        service = TorrentService(db_manager=db_manager)

        assert service._db_manager is db_manager
        assert service._poll_interval == TORRENT_POLL_INTERVAL_MS
        assert service._session is None
        assert service._handles == {}
        assert service._contexts == {}
        assert service._handle_to_context == {}
        assert service._should_stop is False

    def test_init_with_custom_values(
        self,
        mock_libtorrent_module: mock.MagicMock,
        db_manager: DatabaseManager,
        tmp_path: Path,
    ) -> None:
        """Test initialization with custom values."""
        from src.services.torrent_service import TorrentService

        state_dir = tmp_path / "torrents"
        download_dir = tmp_path / "downloads"

        service = TorrentService(
            db_manager=db_manager,
            state_dir=state_dir,
            download_dir=download_dir,
            poll_interval_ms=500,
        )

        assert service._state_dir == state_dir
        assert service._download_dir == download_dir
        assert service._poll_interval == 500

    def test_stop_sets_flag(
        self, mock_libtorrent_module: mock.MagicMock, db_manager: DatabaseManager
    ) -> None:
        """Test that stop() sets the _should_stop flag."""
        from src.services.torrent_service import TorrentService

        service = TorrentService(db_manager=db_manager)
        assert service._should_stop is False

        service.stop()
        assert service._should_stop is True

    def test_stop_stops_timer(
        self, mock_libtorrent_module: mock.MagicMock, db_manager: DatabaseManager
    ) -> None:
        """Test that stop() stops the poll timer."""
        from src.services.torrent_service import TorrentService

        service = TorrentService(db_manager=db_manager)
        mock_timer = mock.MagicMock()
        service._poll_timer = mock_timer

        service.stop()

        mock_timer.stop.assert_called_once()

    def test_wait_until_ready_returns_false_before_ready(
        self, mock_libtorrent_module: mock.MagicMock, db_manager: DatabaseManager
    ) -> None:
        """Test wait_until_ready times out when the service is not ready."""
        from src.services.torrent_service import TorrentService

        service = TorrentService(db_manager=db_manager)

        assert service.wait_until_ready(timeout_ms=0) is False

    def test_wait_until_ready_returns_true_after_ready(
        self, mock_libtorrent_module: mock.MagicMock, db_manager: DatabaseManager
    ) -> None:
        """Test wait_until_ready returns true after readiness is set."""
        from src.services.torrent_service import TorrentService

        service = TorrentService(db_manager=db_manager)
        service._ready_event.set()

        assert service.wait_until_ready(timeout_ms=0) is True


class TestTorrentServiceDirectories:
    """Tests for directory management."""

    def test_ensure_directories_creates_paths(
        self,
        mock_libtorrent_module: mock.MagicMock,
        db_manager: DatabaseManager,
        tmp_path: Path,
    ) -> None:
        """Test _ensure_directories creates required directories."""
        from src.services.torrent_service import TorrentService

        state_dir = tmp_path / "torrents"
        download_dir = tmp_path / "downloads"

        service = TorrentService(
            db_manager=db_manager,
            state_dir=state_dir,
            download_dir=download_dir,
        )

        assert not state_dir.exists()
        assert not download_dir.exists()

        service._ensure_directories()

        assert state_dir.exists()
        assert download_dir.exists()


class TestTorrentServiceSession:
    """Tests for session initialization and state management."""

    def test_init_session(
        self, mock_libtorrent_module: mock.MagicMock, db_manager: DatabaseManager
    ) -> None:
        """Test _init_session creates libtorrent session."""
        from src.services.torrent_service import TorrentService

        service = TorrentService(db_manager=db_manager)
        service._init_session()

        mock_libtorrent_module.session.assert_called_once()
        assert service._session is not None

    def test_load_session_state_missing_file(
        self,
        mock_libtorrent_module: mock.MagicMock,
        db_manager: DatabaseManager,
        tmp_path: Path,
    ) -> None:
        """Test _load_session_state handles missing state file."""
        from src.services.torrent_service import TorrentService

        service = TorrentService(
            db_manager=db_manager,
            state_dir=tmp_path / "torrents",
        )
        service._ensure_directories()
        service._session = mock.MagicMock()

        # Should not raise
        service._load_session_state()

        # Should not call load_state since file doesn't exist
        service._session.load_state.assert_not_called()

    def test_load_session_state_success(
        self,
        mock_libtorrent_module: mock.MagicMock,
        db_manager: DatabaseManager,
        tmp_path: Path,
    ) -> None:
        """Test _load_session_state loads state from file."""
        from src.services.torrent_service import TorrentService

        state_dir = tmp_path / "torrents"
        state_dir.mkdir(parents=True)
        state_file = state_dir / TorrentService.SESSION_STATE_FILE
        state_file.write_bytes(b"state data")

        service = TorrentService(
            db_manager=db_manager,
            state_dir=state_dir,
        )
        service._session = mock.MagicMock()

        service._load_session_state()

        mock_libtorrent_module.bdecode.assert_called_once_with(b"state data")
        service._session.load_state.assert_called_once()

    def test_load_session_state_corrupted(
        self,
        mock_libtorrent_module: mock.MagicMock,
        db_manager: DatabaseManager,
        tmp_path: Path,
    ) -> None:
        """Test _load_session_state handles corrupted state file."""
        from src.services.torrent_service import TorrentService

        state_dir = tmp_path / "torrents"
        state_dir.mkdir(parents=True)
        state_file = state_dir / TorrentService.SESSION_STATE_FILE
        state_file.write_bytes(b"corrupted")

        service = TorrentService(
            db_manager=db_manager,
            state_dir=state_dir,
        )
        service._session = mock.MagicMock()
        mock_libtorrent_module.bdecode.side_effect = Exception("Decode error")

        # Should not raise, just log warning
        service._load_session_state()

    def test_save_session_state_no_session(
        self, mock_libtorrent_module: mock.MagicMock, db_manager: DatabaseManager
    ) -> None:
        """Test _save_session_state does nothing without session."""
        from src.services.torrent_service import TorrentService

        service = TorrentService(db_manager=db_manager)
        service._session = None

        # Should not raise
        service._save_session_state()

    def test_save_session_state_success(
        self,
        mock_libtorrent_module: mock.MagicMock,
        db_manager: DatabaseManager,
        tmp_path: Path,
    ) -> None:
        """Test _save_session_state saves state to file."""
        from src.services.torrent_service import TorrentService

        state_dir = tmp_path / "torrents"
        state_dir.mkdir(parents=True)

        service = TorrentService(
            db_manager=db_manager,
            state_dir=state_dir,
        )
        service._session = mock.MagicMock()
        service._session.save_state.return_value = {"key": "value"}
        mock_libtorrent_module.bencode.return_value = b"encoded state"

        service._save_session_state()

        state_file = state_dir / TorrentService.SESSION_STATE_FILE
        assert state_file.exists()
        assert state_file.read_bytes() == b"encoded state"

    def test_save_session_state_error(
        self,
        mock_libtorrent_module: mock.MagicMock,
        db_manager: DatabaseManager,
        tmp_path: Path,
    ) -> None:
        """Test _save_session_state handles errors."""
        from src.services.torrent_service import TorrentService

        service = TorrentService(
            db_manager=db_manager,
            state_dir=tmp_path / "torrents",
        )
        service._ensure_directories()
        service._session = mock.MagicMock()
        service._session.save_state.side_effect = Exception("Save error")

        # Should not raise
        service._save_session_state()


class TestTorrentServiceResumeData:
    """Tests for resume data management."""

    def test_load_resume_data_missing_file(
        self,
        mock_libtorrent_module: mock.MagicMock,
        db_manager: DatabaseManager,
        tmp_path: Path,
    ) -> None:
        """Test _load_resume_data handles missing file."""
        from src.services.torrent_service import TorrentService

        service = TorrentService(
            db_manager=db_manager,
            state_dir=tmp_path / "torrents",
        )
        service._ensure_directories()
        service._session = mock.MagicMock()

        # Should not raise
        service._load_resume_data()

    def test_load_resume_data_success(
        self,
        mock_libtorrent_module: mock.MagicMock,
        db_manager: DatabaseManager,
        tmp_path: Path,
    ) -> None:
        """Test _load_resume_data loads and restores torrents."""
        from src.services.torrent_service import TorrentService

        state_dir = tmp_path / "torrents"
        state_dir.mkdir(parents=True)
        resume_file = state_dir / TorrentService.RESUME_DATA_FILE

        resume_data = {
            1: {
                "resume_data": b"data1",
                "save_path": "/path/1",
                "download_type": "movie",
                "context_db_id": 101,
            },
            2: {
                "resume_data": b"data2",
                "save_path": "/path/2",
                "download_type": "season",
                "context_db_id": 202,
            },
        }
        with open(resume_file, "wb") as f:
            pickle.dump(resume_data, f)

        service = TorrentService(
            db_manager=db_manager,
            state_dir=state_dir,
        )
        mock_handle = mock.MagicMock()
        mock_handle.info_hash.return_value = "abc123"
        service._session = mock.MagicMock()
        service._session.add_torrent.return_value = mock_handle

        service._load_resume_data()

        assert service._session.add_torrent.call_count == 2
        assert len(service._handles) == 2
        assert len(service._contexts) == 2

    def test_load_resume_data_stops_when_requested(
        self,
        mock_libtorrent_module: mock.MagicMock,
        db_manager: DatabaseManager,
        tmp_path: Path,
    ) -> None:
        """Test _load_resume_data stops when _should_stop is True."""
        from src.services.torrent_service import TorrentService

        state_dir = tmp_path / "torrents"
        state_dir.mkdir(parents=True)
        resume_file = state_dir / TorrentService.RESUME_DATA_FILE

        resume_data = {
            1: {
                "resume_data": b"data1",
                "save_path": "/path/1",
                "download_type": "movie",
                "context_db_id": 101,
            },
        }
        with open(resume_file, "wb") as f:
            pickle.dump(resume_data, f)

        service = TorrentService(
            db_manager=db_manager,
            state_dir=state_dir,
        )
        service._session = mock.MagicMock()
        service._should_stop = True

        service._load_resume_data()

        # Should not add any torrents
        service._session.add_torrent.assert_not_called()

    def test_load_resume_data_handles_torrent_error(
        self,
        mock_libtorrent_module: mock.MagicMock,
        db_manager: DatabaseManager,
        tmp_path: Path,
    ) -> None:
        """Test _load_resume_data handles individual torrent errors."""
        from src.services.torrent_service import TorrentService

        state_dir = tmp_path / "torrents"
        state_dir.mkdir(parents=True)
        resume_file = state_dir / TorrentService.RESUME_DATA_FILE

        resume_data = {
            1: {
                "resume_data": b"data1",
                "save_path": "/path/1",
                "download_type": "movie",
                "context_db_id": 101,
            },
        }
        with open(resume_file, "wb") as f:
            pickle.dump(resume_data, f)

        service = TorrentService(
            db_manager=db_manager,
            state_dir=state_dir,
        )
        service._session = mock.MagicMock()
        service._session.add_torrent.side_effect = Exception("Add error")

        # Should not raise
        service._load_resume_data()

    def test_load_resume_data_corrupted_file(
        self,
        mock_libtorrent_module: mock.MagicMock,
        db_manager: DatabaseManager,
        tmp_path: Path,
    ) -> None:
        """Test _load_resume_data handles corrupted file."""
        from src.services.torrent_service import TorrentService

        state_dir = tmp_path / "torrents"
        state_dir.mkdir(parents=True)
        resume_file = state_dir / TorrentService.RESUME_DATA_FILE
        resume_file.write_bytes(b"not a pickle")

        service = TorrentService(
            db_manager=db_manager,
            state_dir=state_dir,
        )
        service._session = mock.MagicMock()

        # Should not raise
        service._load_resume_data()

    def test_save_resume_data_no_session(
        self, mock_libtorrent_module: mock.MagicMock, db_manager: DatabaseManager
    ) -> None:
        """Test _save_resume_data does nothing without session."""
        from src.services.torrent_service import TorrentService

        service = TorrentService(db_manager=db_manager)
        service._session = None

        # Should not raise
        service._save_resume_data()

    def test_save_resume_data_success(
        self,
        mock_libtorrent_module: mock.MagicMock,
        db_manager: DatabaseManager,
        tmp_path: Path,
    ) -> None:
        """Test _save_resume_data saves resume data to file."""
        from src.services.torrent_service import (
            DownloadContext,
            DownloadType,
            TorrentService,
        )

        state_dir = tmp_path / "torrents"
        state_dir.mkdir(parents=True)

        service = TorrentService(
            db_manager=db_manager,
            state_dir=state_dir,
        )

        # Setup mock handle
        mock_handle = mock.MagicMock()
        mock_handle.is_valid.return_value = True
        mock_handle.info_hash.return_value = "abc123"
        mock_status = mock.MagicMock()
        mock_status.save_path = "/downloads"
        mock_handle.status.return_value = mock_status

        context = DownloadContext(DownloadType.MOVIE, 101)
        service._handles = {1: mock_handle}
        service._contexts = {1: context}
        service._handle_to_context = {"abc123": 1}

        # Create a mock alert class
        class MockSaveResumeDataAlert:
            pass

        mock_alert = MockSaveResumeDataAlert()
        mock_alert.handle = mock_handle
        mock_libtorrent_module.save_resume_data_alert = MockSaveResumeDataAlert

        service._session = mock.MagicMock()
        service._session.pop_alerts.return_value = [mock_alert]
        mock_libtorrent_module.write_resume_data_buf.return_value = b"resume data"

        service._save_resume_data()

        resume_file = state_dir / TorrentService.RESUME_DATA_FILE
        assert resume_file.exists()

    def test_save_resume_data_skips_invalid_handles(
        self,
        mock_libtorrent_module: mock.MagicMock,
        db_manager: DatabaseManager,
        tmp_path: Path,
    ) -> None:
        """Test _save_resume_data skips invalid handles."""
        from src.services.torrent_service import TorrentService

        state_dir = tmp_path / "torrents"
        state_dir.mkdir(parents=True)

        service = TorrentService(
            db_manager=db_manager,
            state_dir=state_dir,
        )

        mock_handle = mock.MagicMock()
        mock_handle.is_valid.return_value = False

        service._handles = {1: mock_handle}
        service._session = mock.MagicMock()
        service._session.pop_alerts.return_value = []

        service._save_resume_data()

        mock_handle.save_resume_data.assert_not_called()

    def test_save_resume_data_handles_request_error(
        self,
        mock_libtorrent_module: mock.MagicMock,
        db_manager: DatabaseManager,
        tmp_path: Path,
    ) -> None:
        """Test _save_resume_data handles save_resume_data errors."""
        from src.services.torrent_service import TorrentService

        state_dir = tmp_path / "torrents"
        state_dir.mkdir(parents=True)

        service = TorrentService(
            db_manager=db_manager,
            state_dir=state_dir,
        )

        mock_handle = mock.MagicMock()
        mock_handle.is_valid.return_value = True
        mock_handle.save_resume_data.side_effect = Exception("Request error")

        service._handles = {1: mock_handle}
        service._session = mock.MagicMock()
        service._session.pop_alerts.return_value = []

        # Should not raise
        service._save_resume_data()

    def test_save_resume_data_write_error(
        self,
        mock_libtorrent_module: mock.MagicMock,
        db_manager: DatabaseManager,
        tmp_path: Path,
    ) -> None:
        """Test _save_resume_data handles file write errors."""
        from src.services.torrent_service import TorrentService

        # Use a non-existent path that can't be written to
        service = TorrentService(
            db_manager=db_manager,
            state_dir=tmp_path / "torrents",
        )
        service._session = mock.MagicMock()
        service._session.pop_alerts.return_value = []
        service._handles = {}

        # Mock open to raise error
        with mock.patch("builtins.open", side_effect=PermissionError("No access")):
            # Should not raise
            service._save_resume_data()


class TestTorrentServicePolling:
    """Tests for progress polling."""

    def test_start_polling(
        self, mock_libtorrent_module: mock.MagicMock, db_manager: DatabaseManager
    ) -> None:
        """Test _start_polling creates and starts timer."""
        from src.services.torrent_service import TorrentService

        service = TorrentService(db_manager=db_manager, poll_interval_ms=100)

        with mock.patch("src.services.torrent_service.QTimer") as mock_timer_class:
            mock_timer = mock.MagicMock()
            mock_timer_class.return_value = mock_timer

            service._start_polling()

            mock_timer.timeout.connect.assert_called_once_with(service._poll_progress)
            mock_timer.start.assert_called_once_with(100)

    def test_poll_progress_when_stopped(
        self, mock_libtorrent_module: mock.MagicMock, db_manager: DatabaseManager
    ) -> None:
        """Test _poll_progress does nothing when stopped."""
        from src.services.torrent_service import TorrentService

        service = TorrentService(db_manager=db_manager)
        service._should_stop = True
        service._session = mock.MagicMock()

        service._poll_progress()

        service._session.pop_alerts.assert_not_called()

    def test_poll_progress_no_session(
        self, mock_libtorrent_module: mock.MagicMock, db_manager: DatabaseManager
    ) -> None:
        """Test _poll_progress does nothing without session."""
        from src.services.torrent_service import TorrentService

        service = TorrentService(db_manager=db_manager)
        service._session = None

        # Should not raise
        service._poll_progress()

    def test_poll_progress_movie_downloading(
        self, mock_libtorrent_module: mock.MagicMock, db_manager: DatabaseManager
    ) -> None:
        """Test _poll_progress updates progress for downloading movie."""
        from src.services.torrent_service import (
            DownloadContext,
            DownloadType,
            TorrentService,
        )

        service = TorrentService(db_manager=db_manager)

        mock_handle = mock.MagicMock()
        mock_handle.is_valid.return_value = True
        mock_status = mock.MagicMock()
        mock_status.state = mock_libtorrent_module.torrent_status.states.downloading
        mock_status.progress = 0.5
        mock_status.download_rate = 1024000  # 1000 KB/s
        mock_status.upload_rate = 512000  # 500 KB/s
        mock_handle.status.return_value = mock_status

        context = DownloadContext(DownloadType.MOVIE, 101)
        service._handles = {1: mock_handle}
        service._contexts = {1: context}
        service._session = mock.MagicMock()
        service._session.pop_alerts.return_value = []

        progress_emissions: list[tuple] = []
        service.download_progress.connect(
            lambda fid, p, d, u: progress_emissions.append((fid, p, d, u))
        )

        with mock.patch.object(service._db_manager, "update_file_state"):
            service._poll_progress()

        assert len(progress_emissions) == 1
        assert progress_emissions[0][0] == 101  # context.id
        assert progress_emissions[0][1] == 50  # 50%
        assert progress_emissions[0][2] == 1000.0  # KB/s
        assert progress_emissions[0][3] == 500.0  # KB/s

    def test_poll_progress_season_downloading(
        self, mock_libtorrent_module: mock.MagicMock, db_manager: DatabaseManager
    ) -> None:
        """Test _poll_progress updates progress for downloading season."""
        from src.services.torrent_service import (
            DownloadContext,
            DownloadType,
            TorrentService,
        )

        service = TorrentService(db_manager=db_manager)

        mock_handle = mock.MagicMock()
        mock_handle.is_valid.return_value = True
        mock_status = mock.MagicMock()
        mock_status.state = mock_libtorrent_module.torrent_status.states.downloading
        mock_status.progress = 0.75
        mock_status.download_rate = 2048000
        mock_status.upload_rate = 1024000
        mock_handle.status.return_value = mock_status

        context = DownloadContext(DownloadType.SEASON, 201)
        service._handles = {1: mock_handle}
        service._contexts = {1: context}
        service._session = mock.MagicMock()
        service._session.pop_alerts.return_value = []

        progress_emissions: list[tuple] = []
        service.download_progress.connect(
            lambda fid, p, d, u: progress_emissions.append((fid, p, d, u))
        )

        with mock.patch.object(service._db_manager, "update_season_state"):
            service._poll_progress()

        assert len(progress_emissions) == 1
        assert progress_emissions[0][0] == 201  # context.id (season_id)
        assert progress_emissions[0][1] == 75

    def test_poll_progress_movie_seeding(
        self,
        mock_libtorrent_module: mock.MagicMock,
        db_manager: DatabaseManager,
        tmp_path: Path,
    ) -> None:
        """Test _poll_progress handles seeding state (completed movie)."""
        from src.services.torrent_service import (
            DownloadContext,
            DownloadType,
            TorrentService,
        )

        service = TorrentService(
            db_manager=db_manager,
            download_dir=tmp_path / "downloads",
        )
        service._ensure_directories()

        mock_handle = mock.MagicMock()
        mock_handle.is_valid.return_value = True
        mock_handle.info_hash.return_value = "abc123"
        mock_status = mock.MagicMock()
        mock_status.state = mock_libtorrent_module.torrent_status.states.seeding
        mock_status.save_path = str(tmp_path / "downloads")
        mock_handle.status.return_value = mock_status

        # Mock torrent_file for _find_largest_video
        mock_torrent_info = mock.MagicMock()
        mock_files = mock.MagicMock()
        mock_files.num_files.return_value = 1
        mock_files.file_path.return_value = "movie.mkv"
        mock_files.file_size.return_value = 1000000
        mock_torrent_info.files.return_value = mock_files
        mock_handle.torrent_file.return_value = mock_torrent_info

        context = DownloadContext(DownloadType.MOVIE, 101)
        service._handles = {1: mock_handle}
        service._contexts = {1: context}
        service._handle_to_context = {"abc123": 1}
        service._session = mock.MagicMock()
        service._session.pop_alerts.return_value = []

        completed_emissions: list[tuple] = []
        service.download_completed.connect(
            lambda fid, path: completed_emissions.append((fid, path))
        )

        with mock.patch.object(service._db_manager, "update_file_state"):
            with mock.patch.object(service._db_manager, "update_file_path"):
                service._poll_progress()

        assert len(completed_emissions) == 1
        assert completed_emissions[0][0] == 101

    def test_poll_progress_skips_invalid_handles(
        self, mock_libtorrent_module: mock.MagicMock, db_manager: DatabaseManager
    ) -> None:
        """Test _poll_progress skips invalid handles."""
        from src.services.torrent_service import TorrentService

        service = TorrentService(db_manager=db_manager)

        mock_handle = mock.MagicMock()
        mock_handle.is_valid.return_value = False

        service._handles = {1: mock_handle}
        service._session = mock.MagicMock()
        service._session.pop_alerts.return_value = []

        service._poll_progress()

        mock_handle.status.assert_not_called()

    def test_poll_progress_skips_missing_context(
        self, mock_libtorrent_module: mock.MagicMock, db_manager: DatabaseManager
    ) -> None:
        """Test _poll_progress skips handles without context."""
        from src.services.torrent_service import TorrentService

        service = TorrentService(db_manager=db_manager)

        mock_handle = mock.MagicMock()
        mock_handle.is_valid.return_value = True

        service._handles = {1: mock_handle}
        service._contexts = {}  # No context
        service._session = mock.MagicMock()
        service._session.pop_alerts.return_value = []

        service._poll_progress()

        mock_handle.status.assert_not_called()

    def test_poll_progress_processes_alerts(
        self, mock_libtorrent_module: mock.MagicMock, db_manager: DatabaseManager
    ) -> None:
        """Test _poll_progress processes alerts from session."""
        from src.services.torrent_service import TorrentService

        service = TorrentService(db_manager=db_manager)

        # Create a class for a non-error alert type
        class MockOtherAlert:
            pass

        mock_alert = MockOtherAlert()
        # Set torrent_error_alert to a different type so isinstance check fails
        mock_libtorrent_module.torrent_error_alert = type("TorrentErrorAlert", (), {})

        service._handles = {}
        service._session = mock.MagicMock()
        service._session.pop_alerts.return_value = [mock_alert]

        # Should not raise - alerts that aren't torrent_error_alert are ignored
        service._poll_progress()


class TestTorrentServiceAlerts:
    """Tests for alert handling."""

    def test_handle_alert_torrent_error_movie(
        self, mock_libtorrent_module: mock.MagicMock, db_manager: DatabaseManager
    ) -> None:
        """Test _handle_alert handles torrent_error_alert for movie."""
        from src.services.torrent_service import (
            DownloadContext,
            DownloadType,
            TorrentService,
        )

        service = TorrentService(db_manager=db_manager)

        mock_handle = mock.MagicMock()
        mock_handle.info_hash.return_value = "abc123"

        # Create a mock alert class
        class MockTorrentErrorAlert:
            pass

        mock_alert = MockTorrentErrorAlert()
        mock_alert.handle = mock_handle
        mock_alert.error = mock.MagicMock()
        mock_alert.error.message.return_value = "Download failed"
        mock_libtorrent_module.torrent_error_alert = MockTorrentErrorAlert

        context = DownloadContext(DownloadType.MOVIE, 101)
        service._handles = {1: mock_handle}
        service._contexts = {1: context}
        service._handle_to_context = {"abc123": 1}

        error_emissions: list[tuple] = []
        service.download_error.connect(
            lambda fid, msg: error_emissions.append((fid, msg))
        )

        with mock.patch.object(service._db_manager, "update_file_state"):
            service._handle_alert(mock_alert)

        assert len(error_emissions) == 1
        assert error_emissions[0][0] == 101
        assert "Download failed" in error_emissions[0][1]

    def test_handle_alert_torrent_error_season(
        self, mock_libtorrent_module: mock.MagicMock, db_manager: DatabaseManager
    ) -> None:
        """Test _handle_alert handles torrent_error_alert for season."""
        from src.services.torrent_service import (
            DownloadContext,
            DownloadType,
            TorrentService,
        )

        service = TorrentService(db_manager=db_manager)

        mock_handle = mock.MagicMock()
        mock_handle.info_hash.return_value = "abc123"

        class MockTorrentErrorAlert:
            pass

        mock_alert = MockTorrentErrorAlert()
        mock_alert.handle = mock_handle
        mock_alert.error = mock.MagicMock()
        mock_alert.error.message.return_value = "Download failed"
        mock_libtorrent_module.torrent_error_alert = MockTorrentErrorAlert

        context = DownloadContext(DownloadType.SEASON, 201)
        service._handles = {1: mock_handle}
        service._contexts = {1: context}
        service._handle_to_context = {"abc123": 1}

        error_emissions: list[tuple] = []
        service.download_error.connect(
            lambda fid, msg: error_emissions.append((fid, msg))
        )

        with mock.patch.object(service._db_manager, "update_season_state"):
            service._handle_alert(mock_alert)

        assert len(error_emissions) == 1
        assert error_emissions[0][0] == 201

    def test_handle_alert_unknown_handle(
        self, mock_libtorrent_module: mock.MagicMock, db_manager: DatabaseManager
    ) -> None:
        """Test _handle_alert handles unknown handle gracefully."""
        from src.services.torrent_service import TorrentService

        service = TorrentService(db_manager=db_manager)

        mock_handle = mock.MagicMock()
        mock_handle.info_hash.return_value = "unknown"

        # Create a mock alert class
        class MockTorrentErrorAlert:
            pass

        mock_alert = MockTorrentErrorAlert()
        mock_alert.handle = mock_handle
        mock_libtorrent_module.torrent_error_alert = MockTorrentErrorAlert

        service._handle_to_context = {}

        # Should not raise
        service._handle_alert(mock_alert)


class TestTorrentServiceAddMagnet:
    """Tests for add_magnet method."""

    def test_add_magnet_no_session(
        self, mock_libtorrent_module: mock.MagicMock, db_manager: DatabaseManager
    ) -> None:
        """Test add_magnet returns False without session."""
        from src.services.torrent_service import (
            DownloadContext,
            DownloadType,
            TorrentService,
        )

        service = TorrentService(db_manager=db_manager)
        service._session = None

        context = DownloadContext(DownloadType.MOVIE, 101)
        result = service.add_magnet(context, "magnet:?xt=urn:btih:test")
        assert result is False

    def test_add_magnet_duplicate(
        self, mock_libtorrent_module: mock.MagicMock, db_manager: DatabaseManager
    ) -> None:
        """Test add_magnet returns False for duplicate context ID."""
        from src.services.torrent_service import (
            DownloadContext,
            DownloadType,
            TorrentService,
        )

        service = TorrentService(db_manager=db_manager)
        service._session = mock.MagicMock()
        service._handles = {101: mock.MagicMock()}  # context.id as key

        context = DownloadContext(DownloadType.MOVIE, 101)
        result = service.add_magnet(context, "magnet:?xt=urn:btih:test")
        assert result is False

    def test_add_magnet_movie_success(
        self,
        mock_libtorrent_module: mock.MagicMock,
        db_manager: DatabaseManager,
        tmp_path: Path,
    ) -> None:
        """Test add_magnet successfully adds movie torrent."""
        from src.services.torrent_service import (
            DownloadContext,
            DownloadType,
            TorrentService,
        )

        service = TorrentService(
            db_manager=db_manager,
            download_dir=tmp_path / "downloads",
        )
        service._ensure_directories()

        mock_handle = mock.MagicMock()
        mock_handle.info_hash.return_value = "abc123"
        service._session = mock.MagicMock()
        service._session.add_torrent.return_value = mock_handle

        context = DownloadContext(DownloadType.MOVIE, 101)
        with mock.patch.object(service._db_manager, "update_file_state"):
            result = service.add_magnet(context, "magnet:?xt=urn:btih:test")

        assert result is True
        assert 101 in service._handles
        assert 101 in service._contexts
        assert "abc123" in service._handle_to_context

    def test_add_magnet_season_success(
        self,
        mock_libtorrent_module: mock.MagicMock,
        db_manager: DatabaseManager,
        tmp_path: Path,
    ) -> None:
        """Test add_magnet successfully adds season torrent."""
        from src.services.torrent_service import (
            DownloadContext,
            DownloadType,
            TorrentService,
        )

        service = TorrentService(
            db_manager=db_manager,
            download_dir=tmp_path / "downloads",
        )
        service._ensure_directories()

        mock_handle = mock.MagicMock()
        mock_handle.info_hash.return_value = "def456"
        service._session = mock.MagicMock()
        service._session.add_torrent.return_value = mock_handle

        context = DownloadContext(DownloadType.SEASON, 201)
        with mock.patch.object(service._db_manager, "update_season_state"):
            result = service.add_magnet(context, "magnet:?xt=urn:btih:test")

        assert result is True
        assert 201 in service._handles
        assert service._contexts[201].download_type == DownloadType.SEASON

    def test_process_backend_namespaces_movie_and_season_ids(
        self, mock_libtorrent_module: mock.MagicMock, db_manager: DatabaseManager
    ) -> None:
        """Verify process backend can track movie and season with same DB ID."""
        from src.services.torrent_service import (
            DownloadContext,
            DownloadType,
            TorrentService,
        )

        service = TorrentService(db_manager=db_manager)
        service._use_process_backend = True

        with (
            mock.patch.object(
                service, "_send_worker_command", return_value=True
            ) as send,
            mock.patch.object(service._db_manager, "update_file_state"),
            mock.patch.object(service._db_manager, "update_season_state"),
        ):
            assert service.add_magnet(
                DownloadContext(DownloadType.MOVIE, 7), "magnet:?movie"
            )
            assert service.add_magnet(
                DownloadContext(DownloadType.SEASON, 7), "magnet:?season"
            )

        assert set(service._contexts) == {7, -7}
        sent_ids = [call.args[0]["id"] for call in send.call_args_list]
        assert sent_ids == [7, -7]

    def test_process_backend_unavailable_does_not_queue_db_state(
        self, mock_libtorrent_module: mock.MagicMock, db_manager: DatabaseManager
    ) -> None:
        """Verify unavailable worker does not mark a download as queued."""
        from src.services.torrent_service import (
            DownloadContext,
            DownloadType,
            TorrentService,
        )

        service = TorrentService(db_manager=db_manager)
        service._use_process_backend = True

        with (
            mock.patch.object(service, "_send_worker_command", return_value=False),
            mock.patch.object(service._db_manager, "update_file_state") as update,
        ):
            result = service.add_magnet(
                DownloadContext(DownloadType.MOVIE, 8), "magnet:?movie"
            )

        assert result is False
        update.assert_not_called()
        assert service._contexts == {}

    def test_process_backend_season_progress_emits_db_id(
        self, mock_libtorrent_module: mock.MagicMock, db_manager: DatabaseManager
    ) -> None:
        """Verify namespaced worker IDs are converted before progress is emitted."""
        from src.services.torrent_service import (
            DownloadContext,
            DownloadType,
            TorrentService,
        )

        service = TorrentService(db_manager=db_manager)
        service._use_process_backend = True
        context = DownloadContext(DownloadType.SEASON, 7)
        service._contexts[-7] = context
        progress_updates: list[tuple[int, int, float, float]] = []
        service.download_progress.connect(
            lambda context_id, progress, down, up: progress_updates.append(
                (context_id, progress, down, up)
            )
        )

        service._handle_worker_event(
            {
                "event": "progress",
                "id": -7,
                "progress": 42,
                "download_rate": 1500.0,
                "upload_rate": 100.0,
            }
        )

        assert progress_updates == [(7, 42, 1500.0, 100.0)]

    def test_malformed_worker_stdout_is_ignored(
        self, mock_libtorrent_module: mock.MagicMock, db_manager: DatabaseManager
    ) -> None:
        """Verify malformed worker JSON does not crash event handling."""
        from src.services.torrent_service import TorrentService

        service = TorrentService(db_manager=db_manager)

        with mock.patch.object(service, "_handle_worker_event") as handle_event:
            service._handle_worker_line("not json\n")

        handle_event.assert_not_called()

    def test_add_magnet_sequential(
        self,
        mock_libtorrent_module: mock.MagicMock,
        db_manager: DatabaseManager,
        tmp_path: Path,
    ) -> None:
        """Test add_magnet with sequential flag."""
        from src.services.torrent_service import (
            DownloadContext,
            DownloadType,
            TorrentService,
        )

        service = TorrentService(
            db_manager=db_manager,
            download_dir=tmp_path / "downloads",
        )
        service._ensure_directories()

        mock_handle = mock.MagicMock()
        mock_handle.info_hash.return_value = "abc123"
        service._session = mock.MagicMock()
        service._session.add_torrent.return_value = mock_handle

        context = DownloadContext(DownloadType.SEASON, 201)
        with mock.patch.object(service._db_manager, "update_season_state"):
            result = service.add_magnet(
                context, "magnet:?xt=urn:btih:test", sequential=True
            )

        assert result is True
        mock_handle.set_sequential_download.assert_called_once_with(True)

    def test_add_magnet_error_movie(
        self, mock_libtorrent_module: mock.MagicMock, db_manager: DatabaseManager
    ) -> None:
        """Test add_magnet handles errors for movie."""
        from src.services.torrent_service import (
            DownloadContext,
            DownloadType,
            TorrentService,
        )

        service = TorrentService(db_manager=db_manager)
        service._session = mock.MagicMock()
        mock_libtorrent_module.parse_magnet_uri.side_effect = Exception("Parse error")

        error_emissions: list[tuple] = []
        service.download_error.connect(
            lambda fid, msg: error_emissions.append((fid, msg))
        )

        context = DownloadContext(DownloadType.MOVIE, 101)
        with mock.patch.object(service._db_manager, "update_file_state"):
            result = service.add_magnet(context, "invalid magnet")

        assert result is False
        assert len(error_emissions) == 1
        assert error_emissions[0][0] == 101

    def test_add_magnet_error_season(
        self, mock_libtorrent_module: mock.MagicMock, db_manager: DatabaseManager
    ) -> None:
        """Test add_magnet handles errors for season."""
        from src.services.torrent_service import (
            DownloadContext,
            DownloadType,
            TorrentService,
        )

        service = TorrentService(db_manager=db_manager)
        service._session = mock.MagicMock()
        mock_libtorrent_module.parse_magnet_uri.side_effect = Exception("Parse error")

        error_emissions: list[tuple] = []
        service.download_error.connect(
            lambda fid, msg: error_emissions.append((fid, msg))
        )

        context = DownloadContext(DownloadType.SEASON, 201)
        with mock.patch.object(service._db_manager, "update_season_state"):
            result = service.add_magnet(context, "invalid magnet")

        assert result is False
        assert len(error_emissions) == 1
        assert error_emissions[0][0] == 201


class TestTorrentServiceCancelDownload:
    """Tests for cancel_download method."""

    def test_cancel_download_not_found(
        self, mock_libtorrent_module: mock.MagicMock, db_manager: DatabaseManager
    ) -> None:
        """Test cancel_download returns False for unknown context ID."""
        from src.services.torrent_service import (
            DownloadContext,
            DownloadType,
            TorrentService,
        )

        service = TorrentService(db_manager=db_manager)

        context = DownloadContext(DownloadType.MOVIE, 99999)
        result = service.cancel_download(context)
        assert result is False

    def test_cancel_download_movie_success(
        self, mock_libtorrent_module: mock.MagicMock, db_manager: DatabaseManager
    ) -> None:
        """Test cancel_download removes movie torrent."""
        from src.services.torrent_service import (
            DownloadContext,
            DownloadType,
            TorrentService,
        )

        service = TorrentService(db_manager=db_manager)

        mock_handle = mock.MagicMock()
        mock_handle.is_valid.return_value = True
        mock_handle.info_hash.return_value = "abc123"

        context = DownloadContext(DownloadType.MOVIE, 101)
        service._handles = {101: mock_handle}
        service._contexts = {101: context}
        service._handle_to_context = {"abc123": 101}
        service._session = mock.MagicMock()

        with mock.patch.object(service._db_manager, "update_file_state"):
            result = service.cancel_download(context)

        assert result is True
        assert 101 not in service._handles
        assert 101 not in service._contexts
        service._session.remove_torrent.assert_called_once_with(mock_handle)

    def test_cancel_download_season_success(
        self, mock_libtorrent_module: mock.MagicMock, db_manager: DatabaseManager
    ) -> None:
        """Test cancel_download removes season torrent."""
        from src.services.torrent_service import (
            DownloadContext,
            DownloadType,
            TorrentService,
        )

        service = TorrentService(db_manager=db_manager)

        mock_handle = mock.MagicMock()
        mock_handle.is_valid.return_value = True
        mock_handle.info_hash.return_value = "def456"

        context = DownloadContext(DownloadType.SEASON, 201)
        service._handles = {201: mock_handle}
        service._contexts = {201: context}
        service._handle_to_context = {"def456": 201}
        service._session = mock.MagicMock()

        with mock.patch.object(service._db_manager, "update_season_state"):
            result = service.cancel_download(context)

        assert result is True
        assert 201 not in service._handles


class TestTorrentServiceGetActiveDownloads:
    """Tests for get_active_downloads method."""

    def test_get_active_downloads_empty(
        self, mock_libtorrent_module: mock.MagicMock, db_manager: DatabaseManager
    ) -> None:
        """Test get_active_downloads returns empty list initially."""
        from src.services.torrent_service import TorrentService

        service = TorrentService(db_manager=db_manager)

        result = service.get_active_downloads()
        assert result == []

    def test_get_active_downloads_with_contexts(
        self, mock_libtorrent_module: mock.MagicMock, db_manager: DatabaseManager
    ) -> None:
        """Test get_active_downloads returns registered contexts."""
        from src.services.torrent_service import (
            DownloadContext,
            DownloadType,
            TorrentService,
        )

        service = TorrentService(db_manager=db_manager)
        ctx1 = DownloadContext(DownloadType.MOVIE, 101)
        ctx2 = DownloadContext(DownloadType.SEASON, 201)
        service._contexts = {101: ctx1, 201: ctx2}
        service._handles = {101: mock.MagicMock(), 201: mock.MagicMock()}

        result = service.get_active_downloads()
        assert len(result) == 2
        assert ctx1 in result
        assert ctx2 in result


class TestTorrentServiceFindLargestVideo:
    """Tests for _find_largest_video method."""

    def test_find_largest_video_no_torrent_file(
        self, mock_libtorrent_module: mock.MagicMock, db_manager: DatabaseManager
    ) -> None:
        """Test _find_largest_video returns None without torrent_file."""
        from src.services.torrent_service import TorrentService

        service = TorrentService(db_manager=db_manager)

        mock_handle = mock.MagicMock()
        mock_handle.torrent_file.return_value = None

        result = service._find_largest_video(mock_handle)
        assert result is None

    def test_find_largest_video_success(
        self,
        mock_libtorrent_module: mock.MagicMock,
        db_manager: DatabaseManager,
        tmp_path: Path,
    ) -> None:
        """Test _find_largest_video finds largest video."""
        from src.services.torrent_service import TorrentService

        service = TorrentService(db_manager=db_manager)

        mock_handle = mock.MagicMock()
        mock_status = mock.MagicMock()
        mock_status.save_path = str(tmp_path)
        mock_handle.status.return_value = mock_status

        mock_files = mock.MagicMock()
        mock_files.num_files.return_value = 3
        mock_files.file_path.side_effect = ["sample.txt", "small.mkv", "movie.mkv"]
        mock_files.file_size.side_effect = [100, 1000, 5000]

        mock_torrent_info = mock.MagicMock()
        mock_torrent_info.files.return_value = mock_files
        mock_handle.torrent_file.return_value = mock_torrent_info

        result = service._find_largest_video(mock_handle)

        assert result == tmp_path / "movie.mkv"

    def test_find_largest_video_no_video_files(
        self,
        mock_libtorrent_module: mock.MagicMock,
        db_manager: DatabaseManager,
        tmp_path: Path,
    ) -> None:
        """Test _find_largest_video returns None when no video files."""
        from src.services.torrent_service import TorrentService

        service = TorrentService(db_manager=db_manager)

        mock_handle = mock.MagicMock()
        mock_status = mock.MagicMock()
        mock_status.save_path = str(tmp_path)
        mock_handle.status.return_value = mock_status

        mock_files = mock.MagicMock()
        mock_files.num_files.return_value = 2
        mock_files.file_path.side_effect = ["readme.txt", "data.json"]
        mock_files.file_size.side_effect = [100, 200]

        mock_torrent_info = mock.MagicMock()
        mock_torrent_info.files.return_value = mock_files
        mock_handle.torrent_file.return_value = mock_torrent_info

        result = service._find_largest_video(mock_handle)
        assert result is None


class TestDownloadStateTransitions:
    """Tests for complete download state machine flow."""

    def test_complete_movie_flow_pending_to_completed(
        self,
        mock_libtorrent_module: mock.MagicMock,
        db_manager: DatabaseManager,
        tmp_path: Path,
    ) -> None:
        """Verify complete movie download flow: PENDING → QUEUED → DOWNLOADING → COMPLETED."""
        from src.services.torrent_service import (
            DownloadContext,
            DownloadType,
            TorrentService,
        )

        service = TorrentService(
            db_manager=db_manager,
            download_dir=tmp_path / "downloads",
        )
        service._ensure_directories()
        service._session = mock.MagicMock()

        mock_handle = mock.MagicMock()
        mock_handle.is_valid.return_value = True
        mock_handle.info_hash.return_value = "abc123"
        service._session.add_torrent.return_value = mock_handle

        state_transitions: list[tuple[int, DownloadState, int | None]] = []

        def track_state(
            file_id: int, state: DownloadState, progress: int | None = None
        ) -> None:
            state_transitions.append((file_id, state, progress))

        service.download_progress.connect(
            lambda fid, p, d, u: track_state(fid, DownloadState.DOWNLOADING, p)
        )
        service.download_completed.connect(
            lambda fid, path: track_state(fid, DownloadState.COMPLETED, 100)
        )

        context = DownloadContext(DownloadType.MOVIE, 101)

        with mock.patch.object(service._db_manager, "update_file_state") as mock_update:
            with mock.patch.object(service._db_manager, "update_file_path"):
                result = service.add_magnet(context, "magnet:?xt=urn:btih:test")

        assert result is True
        assert 101 in service._handles

        update_calls = mock_update.call_args_list
        assert len(update_calls) >= 1
        first_call_state = update_calls[0][0][1]
        assert first_call_state == DownloadState.QUEUED

        mock_status = mock.MagicMock()
        mock_status.state = mock_libtorrent_module.torrent_status.states.downloading
        mock_status.progress = 0.0
        mock_status.download_rate = 1024000
        mock_status.upload_rate = 512000
        mock_status.save_path = str(tmp_path / "downloads")
        mock_handle.status.return_value = mock_status

        mock_torrent_info = mock.MagicMock()
        mock_files = mock.MagicMock()
        mock_files.num_files.return_value = 1
        mock_files.file_path.return_value = "movie.mkv"
        mock_files.file_size.return_value = 1000000
        mock_torrent_info.files.return_value = mock_files
        mock_handle.torrent_file.return_value = mock_torrent_info

        with mock.patch.object(service._db_manager, "update_file_state"):
            with mock.patch.object(service._db_manager, "update_file_path"):
                service._poll_progress()

        assert len(state_transitions) == 1
        assert state_transitions[0][1] == DownloadState.DOWNLOADING
        assert state_transitions[0][2] == 0

        mock_status.progress = 0.5
        with mock.patch.object(service._db_manager, "update_file_state"):
            with mock.patch.object(service._db_manager, "update_file_path"):
                service._poll_progress()

        progress_emissions = [
            s for s in state_transitions if s[1] == DownloadState.DOWNLOADING
        ]
        assert len(progress_emissions) >= 2

        mock_status.state = mock_libtorrent_module.torrent_status.states.seeding
        mock_status.progress = 1.0
        with mock.patch.object(service._db_manager, "update_file_state"):
            with mock.patch.object(service._db_manager, "update_file_path"):
                service._poll_progress()

        completed_emissions = [
            s for s in state_transitions if s[1] == DownloadState.COMPLETED
        ]
        assert len(completed_emissions) == 1

        assert completed_emissions[0][0] == 101

    def test_complete_season_flow_pending_to_completed(
        self,
        mock_libtorrent_module: mock.MagicMock,
        db_manager: DatabaseManager,
        tmp_path: Path,
    ) -> None:
        """Verify complete season download flow: PENDING → QUEUED → DOWNLOADING → COMPLETED."""
        from src.services.torrent_service import (
            DownloadContext,
            DownloadType,
            TorrentService,
        )

        service = TorrentService(db_manager=db_manager)

        mock_handle = mock.MagicMock()
        mock_status = mock.MagicMock()
        mock_status.save_path = str(tmp_path)
        mock_handle.status.return_value = mock_status

        mock_files = mock.MagicMock()
        mock_files.num_files.return_value = 2
        mock_files.file_path.side_effect = ["Show.S01E01.mkv", "Show.S01E02.mkv"]
        mock_files.file_size.side_effect = [500000, 600000]

        mock_torrent_info = mock.MagicMock()
        mock_torrent_info.files.return_value = mock_files
        mock_handle.torrent_file.return_value = mock_torrent_info

        context = DownloadContext(DownloadType.SEASON, 201)

        completed_emissions: list[tuple] = []
        service.download_completed.connect(
            lambda fid, path: completed_emissions.append((fid, path))
        )

        episodes = [
            {"id": 1001, "episode_number": 1},
            {"id": 1002, "episode_number": 2},
        ]
        with mock.patch.object(
            service._db_manager, "get_episodes", return_value=episodes
        ):
            with mock.patch.object(service._db_manager, "update_file_state"):
                with mock.patch.object(service._db_manager, "update_file_path"):
                    with mock.patch.object(service._db_manager, "update_season_state"):
                        service._complete_season_download(context, mock_handle)

        assert len(completed_emissions) == 2
        episode_ids = [e[0] for e in completed_emissions]
        assert 1001 in episode_ids
        assert 1002 in episode_ids

    def test_download_flow_to_error_state(
        self,
        mock_libtorrent_module: mock.MagicMock,
        db_manager: DatabaseManager,
        tmp_path: Path,
    ) -> None:
        """Verify error flow: DOWNLOADING → ERROR."""
        from src.services.torrent_service import (
            DownloadContext,
            DownloadType,
            TorrentService,
        )

        service = TorrentService(
            db_manager=db_manager,
            download_dir=tmp_path / "downloads",
        )
        service._ensure_directories()
        service._session = mock.MagicMock()

        mock_handle = mock.MagicMock()
        mock_handle.is_valid.return_value = True
        mock_handle.info_hash.return_value = "error123"
        service._session.add_torrent.return_value = mock_handle

        context = DownloadContext(DownloadType.MOVIE, 301)

        with mock.patch.object(service._db_manager, "update_file_state"):
            service.add_magnet(context, "magnet:?xt=urn:btih:testerror")

        mock_status = mock.MagicMock()
        mock_status.state = mock_libtorrent_module.torrent_status.states.downloading
        mock_status.progress = 0.25
        mock_handle.status.return_value = mock_status

        class MockTorrentErrorAlert:
            pass

        mock_alert = MockTorrentErrorAlert()
        mock_alert.handle = mock_handle
        mock_alert.error = mock.MagicMock()
        mock_alert.error.message.return_value = "Connection lost"
        mock_libtorrent_module.torrent_error_alert = MockTorrentErrorAlert

        service._session.pop_alerts.return_value = [mock_alert]

        errors: list[tuple[int, str]] = []
        service.download_error.connect(
            lambda file_id, error: errors.append((file_id, error))
        )

        service._poll_progress()

        assert errors == [(301, "Connection lost")]

    def test_pending_to_queued_state_transition(
        self,
        mock_libtorrent_module: mock.MagicMock,
        db_manager: DatabaseManager,
        tmp_path: Path,
    ) -> None:
        """Verify PENDING → QUEUED transition on add_magnet."""
        from src.services.torrent_service import (
            DownloadContext,
            DownloadType,
            TorrentService,
        )

        service = TorrentService(
            db_manager=db_manager,
            download_dir=tmp_path / "downloads",
        )
        service._ensure_directories()
        service._session = mock.MagicMock()

        mock_handle = mock.MagicMock()
        mock_handle.info_hash.return_value = "hash123"
        service._session.add_torrent.return_value = mock_handle

        context = DownloadContext(DownloadType.MOVIE, 401)

        with mock.patch.object(service._db_manager, "update_file_state") as mock_update:
            result = service.add_magnet(context, "magnet:?xt=urn:btih:new")

        assert result is True
        mock_update.assert_called_with(401, DownloadState.QUEUED)

    def test_queued_to_downloading_state_transition(
        self,
        mock_libtorrent_module: mock.MagicMock,
        db_manager: DatabaseManager,
        tmp_path: Path,
    ) -> None:
        """Verify QUEUED → DOWNLOADING transition when torrent starts downloading."""
        from src.services.torrent_service import (
            DownloadContext,
            DownloadType,
            TorrentService,
        )

        service = TorrentService(
            db_manager=db_manager,
            download_dir=tmp_path / "downloads",
        )
        service._ensure_directories()
        service._session = mock.MagicMock()

        mock_handle = mock.MagicMock()
        mock_handle.is_valid.return_value = True
        mock_handle.info_hash.return_value = "hash456"
        service._session.add_torrent.return_value = mock_handle

        context = DownloadContext(DownloadType.MOVIE, 501)

        with mock.patch.object(service._db_manager, "update_file_state"):
            service.add_magnet(context, "magnet:?xt=urn:btih:downloading")

        mock_status = mock.MagicMock()
        mock_status.state = mock_libtorrent_module.torrent_status.states.downloading
        mock_status.progress = 0.0
        mock_status.download_rate = 500000
        mock_status.upload_rate = 250000
        mock_handle.status.return_value = mock_status

        progress_updates: list[tuple[int, int, float, float]] = []
        service.download_progress.connect(
            lambda file_id, progress, down, up: progress_updates.append(
                (file_id, progress, down, up)
            )
        )

        service._poll_progress()

        assert len(progress_updates) == 1
        assert progress_updates[0][0] == 501
        assert progress_updates[0][1] == 0

    def test_downloading_to_completed_state_transition(
        self,
        mock_libtorrent_module: mock.MagicMock,
        db_manager: DatabaseManager,
        tmp_path: Path,
    ) -> None:
        """Verify DOWNLOADING → COMPLETED transition when torrent seeds."""
        from src.services.torrent_service import (
            DownloadContext,
            DownloadType,
            TorrentService,
        )

        service = TorrentService(
            db_manager=db_manager,
            download_dir=tmp_path / "downloads",
        )
        service._ensure_directories()
        service._session = mock.MagicMock()

        mock_handle = mock.MagicMock()
        mock_handle.is_valid.return_value = True
        mock_handle.info_hash.return_value = "hash789"
        mock_handle.status.return_value = mock.MagicMock()
        mock_handle.torrent_file.return_value = mock.MagicMock()
        service._session.add_torrent.return_value = mock_handle

        context = DownloadContext(DownloadType.MOVIE, 601)

        with mock.patch.object(service._db_manager, "update_file_state"):
            with mock.patch.object(service._db_manager, "update_file_path"):
                service.add_magnet(context, "magnet:?xt=urn:btih:complete")

        mock_status = mock.MagicMock()
        mock_status.state = mock_libtorrent_module.torrent_status.states.seeding
        mock_status.progress = 1.0
        mock_status.save_path = str(tmp_path / "downloads")
        mock_handle.status.return_value = mock_status

        mock_torrent_info = mock.MagicMock()
        mock_files = mock.MagicMock()
        mock_files.num_files.return_value = 1
        mock_files.file_path.return_value = "complete.mkv"
        mock_files.file_size.return_value = 2000000
        mock_torrent_info.files.return_value = mock_files
        mock_handle.torrent_file.return_value = mock_torrent_info

        completions: list[tuple[int, str]] = []
        service.download_completed.connect(
            lambda file_id, path: completions.append((file_id, path))
        )

        service._poll_progress()

        assert len(completions) == 1
        assert completions[0][0] == 601
        assert completions[0][1].endswith("complete.mkv")

    def test_error_state_blocks_further_processing(
        self,
        mock_libtorrent_module: mock.MagicMock,
        db_manager: DatabaseManager,
        tmp_path: Path,
    ) -> None:
        """Verify ERROR state prevents further download progress."""
        from src.services.torrent_service import (
            DownloadContext,
            DownloadType,
            TorrentService,
        )

        service = TorrentService(
            db_manager=db_manager,
            download_dir=tmp_path / "downloads",
        )
        service._ensure_directories()
        service._session = mock.MagicMock()

        mock_handle = mock.MagicMock()
        mock_handle.is_valid.return_value = True
        mock_handle.info_hash.return_value = "errorhash"
        service._session.add_torrent.return_value = mock_handle

        context = DownloadContext(DownloadType.MOVIE, 701)

        with mock.patch.object(service._db_manager, "update_file_state"):
            service.add_magnet(context, "magnet:?xt=urn:btih:willerror")

        class MockTorrentErrorAlert:
            pass

        mock_alert = MockTorrentErrorAlert()
        mock_alert.handle = mock_handle
        mock_alert.error = mock.MagicMock()
        mock_alert.error.message.return_value = "Disk full"
        mock_libtorrent_module.torrent_error_alert = MockTorrentErrorAlert

        service._session.pop_alerts.return_value = [mock_alert]

        with mock.patch.object(service._db_manager, "update_file_state"):
            service._poll_progress()

        assert 701 not in service._handles
        assert 701 not in service._contexts
        mock_handle.status.assert_not_called()

        mock_handle.status.assert_not_called()


class TestDownloadStateCancelAndRetry:
    """Tests for cancel and retry state transitions."""

    def test_cancel_download_resets_to_pending(
        self,
        mock_libtorrent_module: mock.MagicMock,
        db_manager: DatabaseManager,
        tmp_path: Path,
    ) -> None:
        """Verify cancelling a download resets state to PENDING."""
        from src.services.torrent_service import (
            DownloadContext,
            DownloadType,
            TorrentService,
        )

        service = TorrentService(
            db_manager=db_manager,
            download_dir=tmp_path / "downloads",
        )
        service._ensure_directories()
        service._session = mock.MagicMock()

        mock_handle = mock.MagicMock()
        mock_handle.is_valid.return_value = True
        mock_handle.info_hash.return_value = "cancelhash"
        service._session.add_torrent.return_value = mock_handle

        context = DownloadContext(DownloadType.MOVIE, 801)

        with mock.patch.object(service._db_manager, "update_file_state"):
            service.add_magnet(context, "magnet:?xt=urn:btih:cancel")

        with mock.patch.object(service._db_manager, "update_file_state") as mock_update:
            result = service.cancel_download(context)

        assert result is True
        pending_calls = [
            call
            for call in mock_update.call_args_list
            if call[0][1] == DownloadState.PENDING
        ]
        assert len(pending_calls) == 1
        assert pending_calls[0][0][0] == 801
        assert 801 not in service._handles

    def test_retry_from_pending_after_add_magnet(
        self,
        mock_libtorrent_module: mock.MagicMock,
        db_manager: DatabaseManager,
        tmp_path: Path,
    ) -> None:
        """Verify retry from PENDING state succeeds."""
        from src.services.torrent_service import (
            DownloadContext,
            DownloadType,
            TorrentService,
        )

        service = TorrentService(
            db_manager=db_manager,
            download_dir=tmp_path / "downloads",
        )
        service._ensure_directories()
        service._session = mock.MagicMock()

        mock_handle = mock.MagicMock()
        mock_handle.is_valid.return_value = True
        mock_handle.info_hash.return_value = "retryhash"
        service._session.add_torrent.return_value = mock_handle

        context = DownloadContext(DownloadType.MOVIE, 901)

        with mock.patch.object(service._db_manager, "update_file_state") as mock_update:
            result = service.add_magnet(context, "magnet:?xt=urn:btih:retry")

        assert result is True
        queued_calls = [
            call
            for call in mock_update.call_args_list
            if call[0][1] == DownloadState.QUEUED
        ]
        assert len(queued_calls) == 1
        assert queued_calls[0][0][0] == 901

    """Tests for episode file matching methods."""

    def test_extract_episode_number_s01e05_format(
        self, mock_libtorrent_module: mock.MagicMock, db_manager: DatabaseManager
    ) -> None:
        """Test _extract_episode_number with S01E05 format."""
        from src.services.torrent_service import TorrentService

        service = TorrentService(db_manager=db_manager)

        assert service._extract_episode_number("Show.S01E05.720p.mkv") == 5
        assert service._extract_episode_number("Show.s02e12.720p.mkv") == 12
        assert service._extract_episode_number("Show.S1E3.mkv") == 3

    def test_extract_episode_number_x_format(
        self, mock_libtorrent_module: mock.MagicMock, db_manager: DatabaseManager
    ) -> None:
        """Test _extract_episode_number with 1x05 format."""
        from src.services.torrent_service import TorrentService

        service = TorrentService(db_manager=db_manager)

        assert service._extract_episode_number("Show.1x05.720p.mkv") == 5
        assert service._extract_episode_number("Show.2X12.mkv") == 12

    def test_extract_episode_number_episode_format(
        self, mock_libtorrent_module: mock.MagicMock, db_manager: DatabaseManager
    ) -> None:
        """Test _extract_episode_number with Episode 5 format."""
        from src.services.torrent_service import TorrentService

        service = TorrentService(db_manager=db_manager)

        assert service._extract_episode_number("Show.Episode.5.mkv") == 5
        assert service._extract_episode_number("Show.episode_10.mkv") == 10
        assert service._extract_episode_number("Show.EP03.mkv") == 3
        assert service._extract_episode_number("Show.e7.mkv") == 7

    def test_extract_episode_number_dot_format(
        self, mock_libtorrent_module: mock.MagicMock, db_manager: DatabaseManager
    ) -> None:
        """Test _extract_episode_number with .105. format."""
        from src.services.torrent_service import TorrentService

        service = TorrentService(db_manager=db_manager)

        assert service._extract_episode_number("Show.105.720p.mkv") == 5
        assert service._extract_episode_number("Series.212.mkv") == 12

    def test_extract_episode_number_none(
        self, mock_libtorrent_module: mock.MagicMock, db_manager: DatabaseManager
    ) -> None:
        """Test _extract_episode_number returns None for no match."""
        from src.services.torrent_service import TorrentService

        service = TorrentService(db_manager=db_manager)

        assert service._extract_episode_number("random_file.mkv") is None
        assert service._extract_episode_number("movie2024.mkv") is None

    def test_match_episode_files_success(
        self, mock_libtorrent_module: mock.MagicMock, db_manager: DatabaseManager
    ) -> None:
        """Test _match_episode_files matches files to episodes."""
        from src.services.torrent_service import TorrentService

        service = TorrentService(db_manager=db_manager)

        episodes = [
            {"id": 1, "episode_number": 1},
            {"id": 2, "episode_number": 2},
            {"id": 3, "episode_number": 3},
        ]

        video_files = [
            (Path("/downloads/Show.S01E01.mkv"), 1000),
            (Path("/downloads/Show.S01E02.mkv"), 1100),
            (Path("/downloads/Show.S01E03.mkv"), 1200),
        ]

        matches = service._match_episode_files(episodes, video_files)

        assert len(matches) == 3
        assert matches[1] == Path("/downloads/Show.S01E01.mkv")
        assert matches[2] == Path("/downloads/Show.S01E02.mkv")
        assert matches[3] == Path("/downloads/Show.S01E03.mkv")

    def test_match_episode_files_partial_match(
        self, mock_libtorrent_module: mock.MagicMock, db_manager: DatabaseManager
    ) -> None:
        """Test _match_episode_files handles partial matches."""
        from src.services.torrent_service import TorrentService

        service = TorrentService(db_manager=db_manager)

        episodes = [
            {"id": 1, "episode_number": 1},
            {"id": 2, "episode_number": 2},
            {"id": 3, "episode_number": 3},
        ]

        video_files = [
            (Path("/downloads/Show.S01E01.mkv"), 1000),
            (Path("/downloads/Show.S01E03.mkv"), 1200),
            # Episode 2 missing
        ]

        matches = service._match_episode_files(episodes, video_files)

        assert len(matches) == 2
        assert 1 in matches
        assert 2 not in matches
        assert 3 in matches

    def test_match_episode_files_largest_file_wins(
        self, mock_libtorrent_module: mock.MagicMock, db_manager: DatabaseManager
    ) -> None:
        """Test _match_episode_files picks largest file for same episode."""
        from src.services.torrent_service import TorrentService

        service = TorrentService(db_manager=db_manager)

        episodes = [{"id": 1, "episode_number": 1}]

        video_files = [
            (Path("/downloads/Show.S01E01.720p.mkv"), 500),
            (Path("/downloads/Show.S01E01.1080p.mkv"), 1000),
        ]

        matches = service._match_episode_files(episodes, video_files)

        assert len(matches) == 1
        assert matches[1] == Path("/downloads/Show.S01E01.1080p.mkv")

    def test_complete_worker_season_download_emits_episode_completions(
        self, mock_libtorrent_module: mock.MagicMock, db_manager: DatabaseManager
    ) -> None:
        """Test process-backend season completion matches files to episodes."""
        from src.services.torrent_service import TorrentService

        service = TorrentService(db_manager=db_manager)
        episodes = [
            {"id": 1001, "episode_number": 1},
            {"id": 1002, "episode_number": 2},
        ]
        event = {
            "files": [
                {"path": "/downloads/Show.S01E01.mkv", "size": 1000},
                {"path": "/downloads/Show.S01E02.mkv", "size": 1100},
            ]
        }
        completed_emissions: list[tuple[int, str]] = []
        season_emissions: list[int] = []
        service.download_completed.connect(
            lambda fid, path: completed_emissions.append((fid, path))
        )
        service.season_completed.connect(lambda sid: season_emissions.append(sid))

        with mock.patch.object(
            service._db_manager, "get_episodes", return_value=episodes
        ):
            service._complete_worker_season_download(201, event)

        assert completed_emissions == [
            (1001, "/downloads/Show.S01E01.mkv"),
            (1002, "/downloads/Show.S01E02.mkv"),
        ]
        assert season_emissions == [201]

    def test_complete_worker_season_download_errors_without_files(
        self, mock_libtorrent_module: mock.MagicMock, db_manager: DatabaseManager
    ) -> None:
        """Test process-backend season completion reports missing video files."""
        from src.services.torrent_service import TorrentService

        service = TorrentService(db_manager=db_manager)
        error_emissions: list[tuple[int, str]] = []
        service.download_error.connect(
            lambda sid, error: error_emissions.append((sid, error))
        )

        with mock.patch.object(
            service._db_manager,
            "get_episodes",
            return_value=[{"id": 1001, "episode_number": 1}],
        ):
            service._complete_worker_season_download(201, {"files": []})

        assert error_emissions == [(201, "No video files found in torrent")]

    def test_get_video_files_from_torrent(
        self,
        mock_libtorrent_module: mock.MagicMock,
        db_manager: DatabaseManager,
        tmp_path: Path,
    ) -> None:
        """Test _get_video_files_from_torrent extracts video files."""
        from src.services.torrent_service import TorrentService

        service = TorrentService(db_manager=db_manager)

        mock_handle = mock.MagicMock()
        mock_status = mock.MagicMock()
        mock_status.save_path = str(tmp_path)
        mock_handle.status.return_value = mock_status

        mock_files = mock.MagicMock()
        mock_files.num_files.return_value = 4
        mock_files.file_path.side_effect = [
            "readme.txt",
            "ep1.mkv",
            "ep2.mp4",
            "sample.avi",
        ]
        mock_files.file_size.side_effect = [100, 1000, 1100, 500]

        mock_torrent_info = mock.MagicMock()
        mock_torrent_info.files.return_value = mock_files
        mock_handle.torrent_file.return_value = mock_torrent_info

        result = service._get_video_files_from_torrent(mock_handle)

        assert len(result) == 3  # 3 video files
        paths = [p for p, _ in result]
        assert tmp_path / "ep1.mkv" in paths
        assert tmp_path / "ep2.mp4" in paths
        assert tmp_path / "sample.avi" in paths

    def test_get_video_files_from_torrent_no_torrent_info(
        self, mock_libtorrent_module: mock.MagicMock, db_manager: DatabaseManager
    ) -> None:
        """Test _get_video_files_from_torrent returns empty for no torrent info."""
        from src.services.torrent_service import TorrentService

        service = TorrentService(db_manager=db_manager)

        mock_handle = mock.MagicMock()
        mock_handle.torrent_file.return_value = None

        result = service._get_video_files_from_torrent(mock_handle)
        assert result == []


class TestTorrentServiceDownloadComplete:
    """Tests for _on_download_complete method."""

    def test_on_download_complete_no_context(
        self, mock_libtorrent_module: mock.MagicMock, db_manager: DatabaseManager
    ) -> None:
        """Test _on_download_complete handles missing context."""
        from src.services.torrent_service import TorrentService

        service = TorrentService(db_manager=db_manager)
        service._contexts = {}
        service._session = mock.MagicMock()

        mock_handle = mock.MagicMock()

        # Should not raise, just log error
        service._on_download_complete(999, mock_handle)

    def test_complete_movie_download_no_video_found(
        self, mock_libtorrent_module: mock.MagicMock, db_manager: DatabaseManager
    ) -> None:
        """Test _complete_movie_download handles no video file."""
        from src.services.torrent_service import (
            DownloadContext,
            DownloadType,
            TorrentService,
        )

        service = TorrentService(db_manager=db_manager)

        mock_handle = mock.MagicMock()
        mock_handle.torrent_file.return_value = None

        context = DownloadContext(DownloadType.MOVIE, 101)

        error_emissions: list[tuple] = []
        service.download_error.connect(
            lambda fid, msg: error_emissions.append((fid, msg))
        )

        with mock.patch.object(service._db_manager, "update_file_state"):
            service._complete_movie_download(context, mock_handle)

        assert len(error_emissions) == 1
        assert "No video file found" in error_emissions[0][1]

    def test_complete_season_download_no_episodes(
        self, mock_libtorrent_module: mock.MagicMock, db_manager: DatabaseManager
    ) -> None:
        """Test _complete_season_download handles no episodes in DB."""
        from src.services.torrent_service import (
            DownloadContext,
            DownloadType,
            TorrentService,
        )

        service = TorrentService(db_manager=db_manager)

        mock_handle = mock.MagicMock()
        context = DownloadContext(DownloadType.SEASON, 201)

        error_emissions: list[tuple] = []
        service.download_error.connect(
            lambda fid, msg: error_emissions.append((fid, msg))
        )

        with mock.patch.object(service._db_manager, "get_episodes", return_value=[]):
            with mock.patch.object(service._db_manager, "update_season_state"):
                service._complete_season_download(context, mock_handle)

        assert len(error_emissions) == 1
        assert "No episodes found" in error_emissions[0][1]

    def test_complete_season_download_no_video_files(
        self, mock_libtorrent_module: mock.MagicMock, db_manager: DatabaseManager
    ) -> None:
        """Test _complete_season_download handles no video files in torrent."""
        from src.services.torrent_service import (
            DownloadContext,
            DownloadType,
            TorrentService,
        )

        service = TorrentService(db_manager=db_manager)

        mock_handle = mock.MagicMock()
        mock_handle.torrent_file.return_value = None

        context = DownloadContext(DownloadType.SEASON, 201)

        error_emissions: list[tuple] = []
        service.download_error.connect(
            lambda fid, msg: error_emissions.append((fid, msg))
        )

        episodes = [{"id": 1, "episode_number": 1}]
        with mock.patch.object(
            service._db_manager, "get_episodes", return_value=episodes
        ):
            with mock.patch.object(service._db_manager, "update_season_state"):
                service._complete_season_download(context, mock_handle)

        assert len(error_emissions) == 1
        assert "No video files found" in error_emissions[0][1]

    def test_complete_season_download_no_matches(
        self,
        mock_libtorrent_module: mock.MagicMock,
        db_manager: DatabaseManager,
        tmp_path: Path,
    ) -> None:
        """Test _complete_season_download handles no episode matches."""
        from src.services.torrent_service import (
            DownloadContext,
            DownloadType,
            TorrentService,
        )

        service = TorrentService(db_manager=db_manager)

        mock_handle = mock.MagicMock()
        mock_status = mock.MagicMock()
        mock_status.save_path = str(tmp_path)
        mock_handle.status.return_value = mock_status

        # Video files that won't match episode numbers
        mock_files = mock.MagicMock()
        mock_files.num_files.return_value = 1
        mock_files.file_path.return_value = "random_movie.mkv"
        mock_files.file_size.return_value = 1000

        mock_torrent_info = mock.MagicMock()
        mock_torrent_info.files.return_value = mock_files
        mock_handle.torrent_file.return_value = mock_torrent_info

        context = DownloadContext(DownloadType.SEASON, 201)

        error_emissions: list[tuple] = []
        service.download_error.connect(
            lambda fid, msg: error_emissions.append((fid, msg))
        )

        episodes = [{"id": 1, "episode_number": 1}]
        with mock.patch.object(
            service._db_manager, "get_episodes", return_value=episodes
        ):
            with mock.patch.object(service._db_manager, "update_season_state"):
                service._complete_season_download(context, mock_handle)

        assert len(error_emissions) == 1
        assert "Could not match any video files" in error_emissions[0][1]

    def test_complete_season_download_success(
        self,
        mock_libtorrent_module: mock.MagicMock,
        db_manager: DatabaseManager,
        tmp_path: Path,
    ) -> None:
        """Test _complete_season_download successfully matches episodes."""
        from src.services.torrent_service import (
            DownloadContext,
            DownloadType,
            TorrentService,
        )

        service = TorrentService(db_manager=db_manager)

        mock_handle = mock.MagicMock()
        mock_status = mock.MagicMock()
        mock_status.save_path = str(tmp_path)
        mock_handle.status.return_value = mock_status

        mock_files = mock.MagicMock()
        mock_files.num_files.return_value = 2
        mock_files.file_path.side_effect = ["Show.S01E01.mkv", "Show.S01E02.mkv"]
        mock_files.file_size.side_effect = [1000, 1100]

        mock_torrent_info = mock.MagicMock()
        mock_torrent_info.files.return_value = mock_files
        mock_handle.torrent_file.return_value = mock_torrent_info

        context = DownloadContext(DownloadType.SEASON, 201)

        completed_emissions: list[tuple] = []
        service.download_completed.connect(
            lambda fid, path: completed_emissions.append((fid, path))
        )

        episodes = [
            {"id": 1001, "episode_number": 1},
            {"id": 1002, "episode_number": 2},
        ]
        with mock.patch.object(
            service._db_manager, "get_episodes", return_value=episodes
        ):
            with mock.patch.object(service._db_manager, "update_file_state"):
                with mock.patch.object(service._db_manager, "update_file_path"):
                    with mock.patch.object(service._db_manager, "update_season_state"):
                        service._complete_season_download(context, mock_handle)

        assert len(completed_emissions) == 2
        # Verify episodes were matched
        episode_ids = [e[0] for e in completed_emissions]
        assert 1001 in episode_ids
        assert 1002 in episode_ids


class TestTorrentServiceVideoExtensions:
    """Tests for VIDEO_EXTENSIONS constant."""

    def test_video_extensions_defined(
        self, mock_libtorrent_module: mock.MagicMock
    ) -> None:
        """Test VIDEO_EXTENSIONS contains expected formats."""
        from src.services.torrent_service import VIDEO_EXTENSIONS

        assert ".mkv" in VIDEO_EXTENSIONS
        assert ".mp4" in VIDEO_EXTENSIONS
        assert ".avi" in VIDEO_EXTENSIONS
        assert ".webm" in VIDEO_EXTENSIONS
        assert ".mov" in VIDEO_EXTENSIONS
        assert ".wmv" in VIDEO_EXTENSIONS
        assert ".flv" in VIDEO_EXTENSIONS


class TestTorrentServiceRun:
    """Tests for the run() method."""

    def test_run_exception_handling(
        self,
        mock_libtorrent_module: mock.MagicMock,
        db_manager: DatabaseManager,
        tmp_path: Path,
    ) -> None:
        """Test run() handles exceptions gracefully."""
        from src.services.torrent_service import TorrentService

        service = TorrentService(
            db_manager=db_manager,
            state_dir=tmp_path / "torrents",
            download_dir=tmp_path / "downloads",
        )

        # Make _ensure_directories raise an exception
        with mock.patch.object(
            service, "_ensure_directories", side_effect=Exception("Init error")
        ):
            # Should not raise
            service.run()

    def test_run_normal_flow(
        self,
        mock_libtorrent_module: mock.MagicMock,
        db_manager: DatabaseManager,
        tmp_path: Path,
    ) -> None:
        """Test run() executes normal flow until stopped."""
        from src.services.torrent_service import TorrentService

        service = TorrentService(
            db_manager=db_manager,
            state_dir=tmp_path / "torrents",
            download_dir=tmp_path / "downloads",
        )

        # Pre-stop the service so the while loop exits immediately
        service._should_stop = True

        # Use mock.patch.multiple to mock all methods at once
        with (
            mock.patch.object(service, "_ensure_directories") as mock_ensure,
            mock.patch.object(service, "_init_session") as mock_init,
            mock.patch.object(service, "_load_session_state") as mock_load_state,
            mock.patch.object(service, "_load_resume_data") as mock_load_resume,
            mock.patch.object(service, "_save_session_state") as mock_save_state,
            mock.patch.object(service, "_save_resume_data") as mock_save_resume,
        ):
            service.run()

            # Verify all expected methods were called (assertions inside context)
            mock_ensure.assert_called_once()
            mock_init.assert_called_once()
            mock_load_state.assert_called_once()
            mock_load_resume.assert_called_once()
            # Polling now happens inline in the loop, not via _start_polling
            mock_save_state.assert_called_once()
            mock_save_resume.assert_called_once()


class TestServicesModuleLazyImport:
    """Tests for the services module lazy import mechanism."""

    def test_import_download_type_from_package(
        self, mock_libtorrent_module: mock.MagicMock
    ) -> None:
        """Test that DownloadType can be imported from src.services."""
        from src import services

        assert hasattr(services, "DownloadType")
        from src.services.torrent_service import DownloadType

        assert services.DownloadType is DownloadType

    def test_import_download_context_from_package(
        self, mock_libtorrent_module: mock.MagicMock
    ) -> None:
        """Test that DownloadContext can be imported from src.services."""
        from src import services

        assert hasattr(services, "DownloadContext")
        from src.services.torrent_service import DownloadContext

        assert services.DownloadContext is DownloadContext


class TestDownloadRetry:
    """Tests for download retry from ERROR state."""

    def test_retry_download_from_error_state_movie(
        self,
        mock_libtorrent_module: mock.MagicMock,
        db_manager: DatabaseManager,
        tmp_path: Path,
    ) -> None:
        """Verify download can be retried from ERROR state for movies."""
        from src.services.torrent_service import (
            DownloadContext,
            DownloadType,
            TorrentService,
        )

        service = TorrentService(
            db_manager=db_manager,
            download_dir=tmp_path / "downloads",
        )
        service._ensure_directories()
        service._session = mock.MagicMock()

        mock_handle = mock.MagicMock()
        mock_handle.info_hash.return_value = "abc123"
        service._session.add_torrent.return_value = mock_handle

        context = DownloadContext(DownloadType.MOVIE, 101)

        with mock.patch.object(service._db_manager, "update_file_state"):
            result = service.add_magnet(context, "magnet:?xt=urn:btih:test")

        assert result is True
        assert 101 in service._handles

        service._unregister_handle(101)
        service._db_manager.update_file_state(101, DownloadState.ERROR)

        with mock.patch.object(service._db_manager, "update_file_state"):
            retry_result = service.add_magnet(context, "magnet:?xt=urn:btih:test")

        assert retry_result is True
        assert 101 in service._handles

    def test_retry_download_from_error_state_season(
        self,
        mock_libtorrent_module: mock.MagicMock,
        db_manager: DatabaseManager,
        tmp_path: Path,
    ) -> None:
        """Verify download can be retried from ERROR state for seasons."""
        from src.services.torrent_service import (
            DownloadContext,
            DownloadType,
            TorrentService,
        )

        service = TorrentService(
            db_manager=db_manager,
            download_dir=tmp_path / "downloads",
        )
        service._ensure_directories()
        service._session = mock.MagicMock()

        mock_handle = mock.MagicMock()
        mock_handle.info_hash.return_value = "def456"
        service._session.add_torrent.return_value = mock_handle

        context = DownloadContext(DownloadType.SEASON, 201)

        with mock.patch.object(service._db_manager, "update_season_state"):
            result = service.add_magnet(context, "magnet:?xt=urn:btih:test")

        assert result is True
        assert 201 in service._handles

        service._unregister_handle(201)
        service._db_manager.update_season_state(201, DownloadState.ERROR)

        with mock.patch.object(service._db_manager, "update_season_state"):
            retry_result = service.add_magnet(context, "magnet:?xt=urn:btih:test")

        assert retry_result is True
        assert 201 in service._handles

    def test_retry_sets_state_to_queued(
        self,
        mock_libtorrent_module: mock.MagicMock,
        db_manager: DatabaseManager,
        tmp_path: Path,
    ) -> None:
        """Verify retry from ERROR sets state to QUEUED for movies."""
        from src.services.torrent_service import (
            DownloadContext,
            DownloadType,
            TorrentService,
        )

        service = TorrentService(
            db_manager=db_manager,
            download_dir=tmp_path / "downloads",
        )
        service._ensure_directories()
        service._session = mock.MagicMock()

        mock_handle = mock.MagicMock()
        mock_handle.info_hash.return_value = "retry123"
        service._session.add_torrent.return_value = mock_handle

        context = DownloadContext(DownloadType.MOVIE, 301)

        with mock.patch.object(service._db_manager, "update_file_state") as mock_update:
            service.add_magnet(context, "magnet:?xt=urn:btih:test")

        mock_update.assert_called_with(301, DownloadState.QUEUED)

    def test_retry_after_cancel_restarts_download(
        self,
        mock_libtorrent_module: mock.MagicMock,
        db_manager: DatabaseManager,
        tmp_path: Path,
    ) -> None:
        """Verify cancel followed by retry restarts download properly."""
        from src.services.torrent_service import (
            DownloadContext,
            DownloadType,
            TorrentService,
        )

        service = TorrentService(
            db_manager=db_manager,
            download_dir=tmp_path / "downloads",
        )
        service._ensure_directories()
        service._session = mock.MagicMock()

        mock_handle = mock.MagicMock()
        mock_handle.info_hash.return_value = "cancel123"
        service._session.add_torrent.return_value = mock_handle

        context = DownloadContext(DownloadType.MOVIE, 401)

        with mock.patch.object(service._db_manager, "update_file_state"):
            service.add_magnet(context, "magnet:?xt=urn:btih:test")

        with mock.patch.object(service._db_manager, "update_file_state"):
            service.cancel_download(context)

        with mock.patch.object(service._db_manager, "update_file_state"):
            retry_result = service.add_magnet(context, "magnet:?xt=urn:btih:test")

        assert retry_result is True
        assert service._session.add_torrent.call_count == 2


class TestDownloadStatePersistence:
    """Tests for download state persistence across restarts."""

    def test_download_state_persisted_to_disk(
        self,
        mock_libtorrent_module: mock.MagicMock,
        db_manager: DatabaseManager,
        tmp_path: Path,
    ) -> None:
        """Verify download state saved to resume file during shutdown."""
        from src.services.torrent_service import (
            DownloadContext,
            DownloadType,
            TorrentService,
        )

        state_dir = tmp_path / "torrents"
        state_dir.mkdir(parents=True)

        service = TorrentService(
            db_manager=db_manager,
            state_dir=state_dir,
            download_dir=tmp_path / "downloads",
        )
        service._ensure_directories()
        service._session = mock.MagicMock()

        mock_handle = mock.MagicMock()
        mock_handle.is_valid.return_value = True
        mock_handle.info_hash.return_value = "persist123"
        mock_status = mock.MagicMock()
        mock_status.save_path = str(tmp_path / "downloads")
        mock_handle.status.return_value = mock_status

        context = DownloadContext(DownloadType.MOVIE, 101)
        service._handles = {101: mock_handle}
        service._contexts = {101: context}
        service._handle_to_context = {"persist123": 101}

        class MockSaveResumeDataAlert:
            pass

        mock_alert = MockSaveResumeDataAlert()
        mock_alert.handle = mock_handle
        mock_libtorrent_module.save_resume_data_alert = MockSaveResumeDataAlert

        mock_libtorrent_module.write_resume_data_buf.return_value = b"resume_data_bytes"

        service._session.pop_alerts.return_value = [mock_alert]

        service._save_resume_data()

        resume_file = state_dir / TorrentService.RESUME_DATA_FILE
        assert resume_file.exists()

        with open(resume_file, "rb") as f:
            saved_data = pickle.load(f)

        assert 101 in saved_data
        assert saved_data[101]["resume_data"] == b"resume_data_bytes"
        assert saved_data[101]["save_path"] == str(tmp_path / "downloads")
        assert saved_data[101]["download_type"] == "movie"
        assert saved_data[101]["context_db_id"] == 101

    def test_download_state_restored_on_restart(
        self,
        mock_libtorrent_module: mock.MagicMock,
        db_manager: DatabaseManager,
        tmp_path: Path,
    ) -> None:
        """Verify download state restored from resume file on service restart."""
        from src.services.torrent_service import (
            DownloadType,
            TorrentService,
        )

        state_dir = tmp_path / "torrents"
        state_dir.mkdir(parents=True)
        resume_file = state_dir / TorrentService.RESUME_DATA_FILE

        resume_data = {
            201: {
                "resume_data": b"saved_state_1",
                "save_path": "/path/to/downloads",
                "download_type": "movie",
                "context_db_id": 201,
            },
        }
        with open(resume_file, "wb") as f:
            pickle.dump(resume_data, f)

        mock_handle = mock.MagicMock()
        mock_handle.info_hash.return_value = "restore_hash"

        new_service = TorrentService(
            db_manager=db_manager,
            state_dir=state_dir,
        )
        new_service._session = mock.MagicMock()
        new_service._session.add_torrent.return_value = mock_handle

        new_service._load_resume_data()

        new_service._session.add_torrent.assert_called_once()
        assert len(new_service._handles) == 1
        assert len(new_service._contexts) == 1
        assert 201 in new_service._contexts
        assert new_service._contexts[201].download_type == DownloadType.MOVIE
        assert new_service._contexts[201].id == 201

    def test_session_state_persisted_to_disk(
        self,
        mock_libtorrent_module: mock.MagicMock,
        db_manager: DatabaseManager,
        tmp_path: Path,
    ) -> None:
        """Verify libtorrent session state saved to disk."""
        from src.services.torrent_service import TorrentService

        state_dir = tmp_path / "torrents"
        state_dir.mkdir(parents=True)

        service = TorrentService(
            db_manager=db_manager,
            state_dir=state_dir,
        )
        service._session = mock.MagicMock()
        service._session.save_state.return_value = {"dht_nodes": ["node1", "node2"]}
        mock_libtorrent_module.bencode.return_value = b"encoded_session_state"

        service._save_session_state()

        state_file = state_dir / TorrentService.SESSION_STATE_FILE
        assert state_file.exists()
        assert state_file.read_bytes() == b"encoded_session_state"

        service._session.save_state.assert_called_once()

    def test_session_state_restored_on_startup(
        self,
        mock_libtorrent_module: mock.MagicMock,
        db_manager: DatabaseManager,
        tmp_path: Path,
    ) -> None:
        """Verify libtorrent session state restored from disk on startup."""
        from src.services.torrent_service import TorrentService

        state_dir = tmp_path / "torrents"
        state_dir.mkdir(parents=True)
        state_file = state_dir / TorrentService.SESSION_STATE_FILE
        state_file.write_bytes(b"session_data_bytes")

        mock_libtorrent_module.bdecode.return_value = {"dht_routers": ["router1"]}

        service = TorrentService(
            db_manager=db_manager,
            state_dir=state_dir,
        )
        service._session = mock.MagicMock()

        service._load_session_state()

        mock_libtorrent_module.bdecode.assert_called_once_with(b"session_data_bytes")
        service._session.load_state.assert_called_once_with(
            {"dht_routers": ["router1"]}
        )

    def test_resume_data_preserves_download_progress(
        self,
        mock_libtorrent_module: mock.MagicMock,
        db_manager: DatabaseManager,
        tmp_path: Path,
    ) -> None:
        """Verify resume data includes progress information for resuming downloads."""
        from src.services.torrent_service import (
            DownloadType,
            TorrentService,
        )

        state_dir = tmp_path / "torrents"
        state_dir.mkdir(parents=True)
        resume_file = state_dir / TorrentService.RESUME_DATA_FILE

        resume_data = {
            301: {
                "resume_data": b"progress_state",
                "save_path": "/downloads",
                "download_type": "season",
                "context_db_id": 301,
            },
        }
        with open(resume_file, "wb") as f:
            pickle.dump(resume_data, f)

        mock_handle = mock.MagicMock()
        mock_handle.info_hash.return_value = "progress_hash"
        mock_libtorrent_module.session.return_value.add_torrent.return_value = (
            mock_handle
        )

        new_service = TorrentService(
            db_manager=db_manager,
            state_dir=state_dir,
        )
        new_service._session = mock.MagicMock()

        new_service._load_resume_data()

        new_service._session.add_torrent.assert_called_once()
        call_args = new_service._session.add_torrent.call_args
        atp = call_args[0][0]
        assert atp.resume_data == b"progress_state"
        assert atp.save_path == "/downloads"

        assert 301 in new_service._contexts
        assert new_service._contexts[301].download_type == DownloadType.SEASON
        assert new_service._contexts[301].id == 301

    def test_corrupted_resume_file_handled_gracefully(
        self,
        mock_libtorrent_module: mock.MagicMock,
        db_manager: DatabaseManager,
        tmp_path: Path,
    ) -> None:
        """Verify corrupted resume file doesn't crash the service."""
        from src.services.torrent_service import TorrentService

        state_dir = tmp_path / "torrents"
        state_dir.mkdir(parents=True)
        resume_file = state_dir / TorrentService.RESUME_DATA_FILE
        resume_file.write_bytes(b"not valid pickle data")

        service = TorrentService(
            db_manager=db_manager,
            state_dir=state_dir,
        )
        service._session = mock.MagicMock()

        service._load_resume_data()

        service._session.add_torrent.assert_not_called()
        assert len(service._handles) == 0

    def test_missing_resume_file_on_startup(
        self,
        mock_libtorrent_module: mock.MagicMock,
        db_manager: DatabaseManager,
        tmp_path: Path,
    ) -> None:
        """Verify service starts normally when resume file doesn't exist."""
        from src.services.torrent_service import TorrentService

        state_dir = tmp_path / "torrents"
        state_dir.mkdir(parents=True)

        service = TorrentService(
            db_manager=db_manager,
            state_dir=state_dir,
        )
        service._session = mock.MagicMock()

        service._load_resume_data()

        service._session.add_torrent.assert_not_called()
        assert len(service._handles) == 0


class TestTorrentServiceProcessBackendLifecycle:
    """Tests for the process-backed torrent service lifecycle."""

    def test_start_creates_worker_threads_and_gui_drain_timer(
        self,
        mock_libtorrent_module: mock.MagicMock,
        db_manager: DatabaseManager,
        tmp_path: Path,
    ) -> None:
        """Verify process backend start launches the worker and GUI timer."""
        from src.services.torrent_service import TorrentService

        service = TorrentService(
            db_manager=db_manager,
            state_dir=tmp_path / "torrents",
            download_dir=tmp_path / "downloads",
        )
        service._use_process_backend = True
        fake_process = mock.MagicMock()
        fake_process.stdin = mock.MagicMock()
        fake_process.stdout = mock.MagicMock()
        fake_process.stderr = mock.MagicMock()
        fake_process.poll.return_value = None

        with (
            mock.patch(
                "src.services.torrent_service.subprocess.Popen",
                return_value=fake_process,
            ) as popen,
            mock.patch("src.services.torrent_service.threading.Thread") as thread_cls,
            mock.patch("src.services.torrent_service.QTimer") as timer_cls,
        ):
            stdout_thread = mock.MagicMock()
            stderr_thread = mock.MagicMock()
            thread_cls.side_effect = [stdout_thread, stderr_thread]
            timer = mock.MagicMock()
            timer_cls.return_value = timer

            service.start()

        popen.assert_called_once()
        assert thread_cls.call_count == 2
        stdout_thread.start.assert_called_once()
        stderr_thread.start.assert_called_once()
        timer.timeout.connect.assert_called_once_with(service._drain_worker_events)
        timer.start.assert_called_once_with(100)
        assert service.isRunning() is True

    def test_worker_line_enqueues_without_emitting(
        self, mock_libtorrent_module: mock.MagicMock, db_manager: DatabaseManager
    ) -> None:
        """Verify reader-side parsing does not emit Qt signals directly."""
        from src.services.torrent_service import TorrentService

        service = TorrentService(db_manager=db_manager)
        service._use_process_backend = True
        progress_updates: list[tuple[int, int, float, float]] = []
        service.download_progress.connect(
            lambda context_id, progress, down, up: progress_updates.append(
                (context_id, progress, down, up)
            )
        )

        service._handle_worker_line(
            (
                '{"event":"progress","id":7,"progress":50,'
                '"download_rate":10.0,"upload_rate":1.0}\n'
            )
        )

        assert progress_updates == []
        assert service._worker_events.qsize() == 1

    def test_drain_worker_events_emits_progress_from_test_thread(
        self, mock_libtorrent_module: mock.MagicMock, db_manager: DatabaseManager
    ) -> None:
        """Verify queued progress emits only when the GUI drain runs."""
        from src.services.torrent_service import TorrentService

        service = TorrentService(db_manager=db_manager)
        service._use_process_backend = True
        progress_updates: list[tuple[int, int, float, float]] = []
        service.download_progress.connect(
            lambda context_id, progress, down, up: progress_updates.append(
                (context_id, progress, down, up)
            )
        )

        service._handle_worker_line(
            (
                '{"event":"progress","id":7,"progress":50,'
                '"download_rate":10.0,"upload_rate":1.0}\n'
            )
        )
        assert progress_updates == []

        service._drain_worker_events()

        assert progress_updates == [(7, 50, 10.0, 1.0)]

    def test_malformed_worker_output_is_logged_by_gui_drain(
        self, mock_libtorrent_module: mock.MagicMock, db_manager: DatabaseManager
    ) -> None:
        """Verify malformed stdout is queued for the GUI drain to log."""
        from src.services.torrent_service import TorrentService

        service = TorrentService(db_manager=db_manager)
        service._use_process_backend = True

        with mock.patch("src.services.torrent_service.logger") as logger:
            service._handle_worker_line("not json\n")
            service._drain_worker_events()

        logger.warning.assert_called_once()

    def test_ready_event_sets_readiness_and_flushes_pending_commands(
        self, mock_libtorrent_module: mock.MagicMock, db_manager: DatabaseManager
    ) -> None:
        """Verify ready can unblock waiters before the GUI drain flushes commands."""
        from src.services.torrent_service import TorrentService

        service = TorrentService(db_manager=db_manager)
        service._use_process_backend = True
        fake_process = mock.MagicMock()
        fake_process.stdin = mock.MagicMock()
        fake_process.poll.return_value = None
        service._worker_process = fake_process
        service._pending_commands = [{"command": "add", "id": 7}]

        service._handle_worker_line('{"event":"ready"}\n')

        assert service.wait_until_ready(timeout_ms=0) is True
        fake_process.stdin.write.assert_not_called()

        service._drain_worker_events()

        assert service._worker_ready is True
        fake_process.stdin.write.assert_called_once_with('{"command": "add", "id": 7}\n')
        fake_process.stdin.flush.assert_called_once()
        assert service._pending_commands == []

    def test_stop_and_wait_clean_up_process_backend(
        self, mock_libtorrent_module: mock.MagicMock, db_manager: DatabaseManager
    ) -> None:
        """Verify stop and wait stop timer, process, and reader threads."""
        from src.services.torrent_service import TorrentService

        service = TorrentService(db_manager=db_manager)
        service._use_process_backend = True
        service._running = True
        service._worker_ready = True
        timer = mock.MagicMock()
        service._poll_timer = timer
        fake_process = mock.MagicMock()
        fake_process.stdin = mock.MagicMock()
        fake_process.poll.return_value = None
        service._worker_process = fake_process
        stdout_thread = mock.MagicMock()
        stderr_thread = mock.MagicMock()
        service._worker_stdout_thread = stdout_thread
        service._stderr_thread = stderr_thread

        service.stop()
        stopped = service.wait(timeout_ms=1000)

        assert stopped is True
        timer.stop.assert_called()
        fake_process.stdin.write.assert_called_once_with('{"command": "stop"}\n')
        fake_process.stdin.flush.assert_called_once()
        fake_process.stdin.close.assert_called_once()
        fake_process.terminate.assert_not_called()
        fake_process.wait.assert_called_once()
        stdout_thread.join.assert_called_once()
        stderr_thread.join.assert_called_once()
        assert service.isRunning() is False

    def test_wait_terminates_worker_after_timeout(
        self, mock_libtorrent_module: mock.MagicMock, db_manager: DatabaseManager
    ) -> None:
        """Verify wait terminates a worker that ignores graceful shutdown."""
        from subprocess import TimeoutExpired

        from src.services.torrent_service import TorrentService

        service = TorrentService(db_manager=db_manager)
        service._use_process_backend = True
        service._running = True
        fake_process = mock.MagicMock()
        fake_process.poll.return_value = None
        fake_process.wait.side_effect = [TimeoutExpired("worker", 0.01), None]
        service._worker_process = fake_process

        stopped = service.wait(timeout_ms=10)

        assert stopped is True
        fake_process.terminate.assert_called_once()
        assert fake_process.wait.call_count == 2
