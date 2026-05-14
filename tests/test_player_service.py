"""Tests for the PlayerService."""

import sys
from pathlib import Path
from typing import Any
from unittest import mock

import pytest


# Mock vlc module before importing PlayerService
@pytest.fixture(autouse=True)
def mock_vlc_module():
    """Mock vlc module for all tests."""
    mock_vlc = mock.MagicMock()

    # Setup VLCException
    class MockVLCException(Exception):
        pass

    mock_vlc.VLCException = MockVLCException

    # Setup EventType enum
    mock_vlc.EventType.MediaPlayerEndReached = "MediaPlayerEndReached"
    mock_vlc.EventType.MediaPlayerEncounteredError = "MediaPlayerEncounteredError"

    # Setup Instance mock
    mock_instance = mock.MagicMock()
    mock_vlc.Instance.return_value = mock_instance

    # Setup MediaPlayer mock
    mock_player = mock.MagicMock()
    mock_player.is_playing.return_value = False
    mock_player.get_time.return_value = 30000  # 30 seconds
    mock_player.get_length.return_value = 120000  # 2 minutes
    mock_player.audio_get_volume.return_value = 50
    mock_player.audio_get_track.return_value = 1
    mock_player.audio_get_track_description.return_value = [
        (-1, b"Disable"),
        (1, b"English"),
        (2, b"Polish (Voiceover)"),
    ]
    mock_player.video_get_spu_description.return_value = [
        (-1, b"Disable"),
        (1, b"Subtitle Track 1"),
    ]
    mock_instance.media_player_new.return_value = mock_player

    # Setup Media mock
    mock_media = mock.MagicMock()
    mock_instance.media_new.return_value = mock_media

    # Setup event manager mock
    mock_event_manager = mock.MagicMock()
    mock_player.event_manager.return_value = mock_event_manager

    # Store references for test access
    mock_vlc._mock_instance = mock_instance
    mock_vlc._mock_player = mock_player
    mock_vlc._mock_media = mock_media
    mock_vlc._mock_event_manager = mock_event_manager

    # Force reload of player_service to ensure it uses the mocked vlc
    if "src.services.player_service" in sys.modules:
        del sys.modules["src.services.player_service"]

    # Remove any existing vlc from sys.modules
    modules_to_remove = [k for k in sys.modules.keys() if "vlc" in k.lower()]
    for module in modules_to_remove:
        del sys.modules[module]

    with mock.patch.dict("sys.modules", {"vlc": mock_vlc}):
        yield mock_vlc


class TestPlayerServiceInit:
    """Tests for PlayerService initialization."""

    def test_init_with_defaults(self, mock_vlc_module: mock.MagicMock) -> None:
        """Test initialization with default values."""
        from src.services.player_service import (
            DEFAULT_SEEK_SECONDS,
            DEFAULT_VOLUME_STEP,
            PlayerService,
        )

        service = PlayerService()

        assert service._volume_step == DEFAULT_VOLUME_STEP
        assert service._seek_seconds == DEFAULT_SEEK_SECONDS
        assert service._instance is None
        assert service._player is None
        assert service._is_muted is False
        assert service._pre_mute_volume == 100

    def test_init_with_custom_values(self, mock_vlc_module: mock.MagicMock) -> None:
        """Test initialization with custom values."""
        from src.services.player_service import PlayerService

        service = PlayerService(volume_step=10, seek_seconds=30)

        assert service._volume_step == 10
        assert service._seek_seconds == 30


class TestPlayerServiceInitialize:
    """Tests for PlayerService.initialize() method."""

    def test_initialize_success(self, mock_vlc_module: mock.MagicMock) -> None:
        """Test successful VLC initialization."""
        from src.services.player_service import (
            DEFAULT_TIME_UPDATE_INTERVAL_MS,
            PlayerService,
            VLC_PLAYBACK_ARGS,
        )

        service = PlayerService()
        service.initialize(12345)

        # Verify VLC instance was created
        mock_vlc_module.Instance.assert_called_once_with(
            ["--no-xlib", *VLC_PLAYBACK_ARGS]
        )
        mock_vlc_module._mock_instance.media_player_new.assert_called_once()

        # Verify window binding
        mock_vlc_module._mock_player.set_xwindow.assert_called_once_with(12345)

        # Verify event handlers attached
        event_manager = mock_vlc_module._mock_event_manager
        assert event_manager.event_attach.call_count == 2

        # Verify timer started
        assert service._time_timer is not None
        assert service._time_timer.interval() == DEFAULT_TIME_UPDATE_INTERVAL_MS

    def test_initialize_instance_fails(self, mock_vlc_module: mock.MagicMock) -> None:
        """Test initialization failure when VLC instance creation fails."""
        from src.services.player_service import PlayerService

        mock_vlc_module.Instance.return_value = None

        service = PlayerService()

        # Connect signal spy
        error_received = []
        service.error_occurred.connect(lambda msg: error_received.append(msg))

        with pytest.raises(mock_vlc_module.VLCException):
            service.initialize(12345)

        assert len(error_received) == 1
        assert "VLC initialization failed" in error_received[0]

    def test_initialize_player_fails(self, mock_vlc_module: mock.MagicMock) -> None:
        """Test initialization failure when media player creation fails."""
        from src.services.player_service import PlayerService

        mock_vlc_module._mock_instance.media_player_new.return_value = None

        service = PlayerService()

        error_received = []
        service.error_occurred.connect(lambda msg: error_received.append(msg))

        with pytest.raises(mock_vlc_module.VLCException):
            service.initialize(12345)

        assert len(error_received) == 1


class TestPlayerServiceLoadVideo:
    """Tests for PlayerService.load_video() method."""

    @pytest.fixture
    def initialized_service(self, mock_vlc_module: mock.MagicMock) -> Any:
        """Create an initialized PlayerService."""
        from src.services.player_service import PlayerService

        service = PlayerService()
        service.initialize(12345)
        return service

    def test_load_video_success(
        self,
        mock_vlc_module: mock.MagicMock,
        initialized_service: Any,
        tmp_path: Path,
    ) -> None:
        """Test successful video loading."""
        video_file = tmp_path / "test.mp4"
        video_file.touch()

        initialized_service.load_video(str(video_file))

        # Verify media was created and set
        mock_vlc_module._mock_instance.media_new.assert_called_with(str(video_file))
        mock_vlc_module._mock_player.set_media.assert_called_once()
        mock_vlc_module._mock_player.play.assert_called_once()

    def test_load_video_with_subtitle(
        self,
        mock_vlc_module: mock.MagicMock,
        initialized_service: Any,
        tmp_path: Path,
    ) -> None:
        """Test subtitle is attached before playback starts."""
        video_file = tmp_path / "test.mp4"
        subtitle_file = tmp_path / "test.srt"
        video_file.touch()
        subtitle_file.touch()

        initialized_service.load_video(str(video_file), str(subtitle_file))

        subtitle_path = str(subtitle_file.resolve())
        mock_vlc_module._mock_media.add_options.assert_called_once_with(
            f"sub-file={subtitle_path}", "avcodec-hw=none", "no-avcodec-dr"
        )
        mock_vlc_module._mock_player.set_media.assert_called_once()
        mock_vlc_module._mock_player.play.assert_called_once()
        mock_vlc_module._mock_player.video_set_subtitle_file.assert_not_called()
        mock_vlc_module._mock_player.video_set_spu.assert_not_called()

    def test_load_video_with_missing_subtitle(
        self,
        mock_vlc_module: mock.MagicMock,
        initialized_service: Any,
        tmp_path: Path,
    ) -> None:
        """Test missing subtitle does not block playback."""
        video_file = tmp_path / "test.mp4"
        video_file.touch()

        initialized_service.load_video(str(video_file), str(tmp_path / "missing.srt"))

        mock_vlc_module._mock_media.add_options.assert_not_called()
        mock_vlc_module._mock_player.play.assert_called_once()

    def test_load_video_file_not_found(
        self,
        mock_vlc_module: mock.MagicMock,
        initialized_service: Any,
    ) -> None:
        """Test video loading failure when file doesn't exist."""
        error_received = []
        initialized_service.error_occurred.connect(
            lambda msg: error_received.append(msg)
        )

        with pytest.raises(FileNotFoundError):
            initialized_service.load_video("/nonexistent/video.mp4")

        assert len(error_received) == 1
        assert "not found" in error_received[0]

    def test_load_video_not_initialized(
        self,
        mock_vlc_module: mock.MagicMock,
    ) -> None:
        """Test video loading when player not initialized."""
        from src.services.player_service import PlayerService

        service = PlayerService()

        error_received = []
        service.error_occurred.connect(lambda msg: error_received.append(msg))

        service.load_video("/some/video.mp4")

        assert len(error_received) == 1
        assert "not initialized" in error_received[0]


class TestPlayerServicePlaybackControls:
    """Tests for playback control methods."""

    @pytest.fixture
    def playing_service(self, mock_vlc_module: mock.MagicMock) -> Any:
        """Create an initialized PlayerService with mock player."""
        from src.services.player_service import PlayerService

        service = PlayerService()
        service.initialize(12345)
        return service

    def test_toggle_pause(
        self,
        mock_vlc_module: mock.MagicMock,
        playing_service: Any,
    ) -> None:
        """Test pause toggle."""
        playing_service.toggle_pause()
        mock_vlc_module._mock_player.pause.assert_called_once()

    def test_toggle_pause_not_initialized(
        self,
        mock_vlc_module: mock.MagicMock,
    ) -> None:
        """Test pause toggle when not initialized."""
        from src.services.player_service import PlayerService

        service = PlayerService()
        service.toggle_pause()  # Should not raise

    def test_seek_forward(
        self,
        mock_vlc_module: mock.MagicMock,
        playing_service: Any,
    ) -> None:
        """Test seek forward."""
        mock_vlc_module._mock_player.get_time.return_value = 30000
        mock_vlc_module._mock_player.get_length.return_value = 120000

        playing_service.seek(10000)  # Seek 10 seconds forward

        mock_vlc_module._mock_player.set_time.assert_called_once_with(40000)

    def test_seek_backward(
        self,
        mock_vlc_module: mock.MagicMock,
        playing_service: Any,
    ) -> None:
        """Test seek backward."""
        mock_vlc_module._mock_player.get_time.return_value = 30000
        mock_vlc_module._mock_player.get_length.return_value = 120000

        playing_service.seek(-10000)  # Seek 10 seconds backward

        mock_vlc_module._mock_player.set_time.assert_called_once_with(20000)

    def test_seek_backward_clamps_to_zero(
        self,
        mock_vlc_module: mock.MagicMock,
        playing_service: Any,
    ) -> None:
        """Test seek backward clamps to 0."""
        mock_vlc_module._mock_player.get_time.return_value = 5000
        mock_vlc_module._mock_player.get_length.return_value = 120000

        playing_service.seek(-10000)  # Seek beyond start

        mock_vlc_module._mock_player.set_time.assert_called_once_with(0)

    def test_seek_forward_clamps_to_end(
        self,
        mock_vlc_module: mock.MagicMock,
        playing_service: Any,
    ) -> None:
        """Test seek forward clamps to media length."""
        mock_vlc_module._mock_player.get_time.return_value = 115000
        mock_vlc_module._mock_player.get_length.return_value = 120000

        playing_service.seek(10000)  # Seek beyond end

        mock_vlc_module._mock_player.set_time.assert_called_once_with(120000)

    def test_seek_forward_method(
        self,
        mock_vlc_module: mock.MagicMock,
        playing_service: Any,
    ) -> None:
        """Test seek_forward helper method."""
        mock_vlc_module._mock_player.get_time.return_value = 30000
        mock_vlc_module._mock_player.get_length.return_value = 120000

        playing_service.seek_forward()

        # Default is 10 seconds = 10000 ms
        mock_vlc_module._mock_player.set_time.assert_called_once_with(40000)

    def test_seek_backward_method(
        self,
        mock_vlc_module: mock.MagicMock,
        playing_service: Any,
    ) -> None:
        """Test seek_backward helper method."""
        mock_vlc_module._mock_player.get_time.return_value = 30000
        mock_vlc_module._mock_player.get_length.return_value = 120000

        playing_service.seek_backward()

        # Default is 10 seconds = 10000 ms
        mock_vlc_module._mock_player.set_time.assert_called_once_with(20000)

    def test_rewind_to_start_method(
        self,
        mock_vlc_module: mock.MagicMock,
        playing_service: Any,
    ) -> None:
        """Test rewind_to_start helper method."""
        mock_vlc_module._mock_player.get_length.return_value = 120000

        playing_service.rewind_to_start()

        mock_vlc_module._mock_player.set_time.assert_called_once_with(0)

    def test_seek_when_get_time_returns_negative(
        self,
        mock_vlc_module: mock.MagicMock,
        playing_service: Any,
    ) -> None:
        """Test seek when no media loaded (get_time returns -1)."""
        mock_vlc_module._mock_player.get_time.return_value = -1

        playing_service.seek(10000)

        mock_vlc_module._mock_player.set_time.assert_not_called()

    def test_get_position_seconds(
        self,
        mock_vlc_module: mock.MagicMock,
        playing_service: Any,
    ) -> None:
        """Test get_position_seconds returns current position."""
        mock_vlc_module._mock_player.get_time.return_value = 45000

        position = playing_service.get_position_seconds()

        assert position == 45

    def test_get_position_seconds_negative_returns_zero(
        self,
        mock_vlc_module: mock.MagicMock,
        playing_service: Any,
    ) -> None:
        """Test get_position_seconds returns 0 when time is negative."""
        mock_vlc_module._mock_player.get_time.return_value = -1

        position = playing_service.get_position_seconds()

        assert position == 0

    def test_get_position_seconds_not_initialized(
        self,
        mock_vlc_module: mock.MagicMock,
    ) -> None:
        """Test get_position_seconds returns 0 when not initialized."""
        from src.services.player_service import PlayerService

        service = PlayerService()
        assert service.get_position_seconds() == 0

    def test_get_duration_seconds(
        self,
        mock_vlc_module: mock.MagicMock,
        playing_service: Any,
    ) -> None:
        """Test get_duration_seconds returns media duration."""
        mock_vlc_module._mock_player.get_length.return_value = 120000

        duration = playing_service.get_duration_seconds()

        assert duration == 120

    def test_get_duration_seconds_negative_returns_zero(
        self,
        mock_vlc_module: mock.MagicMock,
        playing_service: Any,
    ) -> None:
        """Test get_duration_seconds returns 0 when length is negative."""
        mock_vlc_module._mock_player.get_length.return_value = -1

        duration = playing_service.get_duration_seconds()

        assert duration == 0

    def test_get_duration_seconds_not_initialized(
        self,
        mock_vlc_module: mock.MagicMock,
    ) -> None:
        """Test get_duration_seconds returns 0 when not initialized."""
        from src.services.player_service import PlayerService

        service = PlayerService()
        assert service.get_duration_seconds() == 0

    def test_set_position_seconds(
        self,
        mock_vlc_module: mock.MagicMock,
        playing_service: Any,
    ) -> None:
        """Test set_position_seconds sets position correctly."""
        mock_vlc_module._mock_player.get_length.return_value = 120000

        playing_service.set_position_seconds(60)

        mock_vlc_module._mock_player.set_time.assert_called_once_with(60000)

    def test_set_position_seconds_clamps_to_length(
        self,
        mock_vlc_module: mock.MagicMock,
        playing_service: Any,
    ) -> None:
        """Test set_position_seconds clamps to media length."""
        mock_vlc_module._mock_player.get_length.return_value = 120000

        playing_service.set_position_seconds(180)

        mock_vlc_module._mock_player.set_time.assert_called_once_with(120000)

    def test_set_position_seconds_not_initialized(
        self,
        mock_vlc_module: mock.MagicMock,
    ) -> None:
        """Test set_position_seconds when not initialized."""
        from src.services.player_service import PlayerService

        service = PlayerService()
        service.set_position_seconds(60)  # Should not raise


class TestPlayerServiceAudioControls:
    """Tests for audio control methods."""

    @pytest.fixture
    def playing_service(self, mock_vlc_module: mock.MagicMock) -> Any:
        """Create an initialized PlayerService with mock player."""
        from src.services.player_service import PlayerService

        service = PlayerService()
        service.initialize(12345)
        return service

    def test_volume_up(
        self,
        mock_vlc_module: mock.MagicMock,
        playing_service: Any,
    ) -> None:
        """Test volume increase."""
        mock_vlc_module._mock_player.audio_get_volume.return_value = 50

        new_volume = playing_service.volume_up()

        assert new_volume == 55
        mock_vlc_module._mock_player.audio_set_volume.assert_called_once_with(55)

    def test_volume_up_clamps_to_100(
        self,
        mock_vlc_module: mock.MagicMock,
        playing_service: Any,
    ) -> None:
        """Test volume increase clamps at 100."""
        mock_vlc_module._mock_player.audio_get_volume.return_value = 98

        new_volume = playing_service.volume_up()

        assert new_volume == 100
        mock_vlc_module._mock_player.audio_set_volume.assert_called_once_with(100)

    def test_volume_down(
        self,
        mock_vlc_module: mock.MagicMock,
        playing_service: Any,
    ) -> None:
        """Test volume decrease."""
        mock_vlc_module._mock_player.audio_get_volume.return_value = 50

        new_volume = playing_service.volume_down()

        assert new_volume == 45
        mock_vlc_module._mock_player.audio_set_volume.assert_called_once_with(45)

    def test_volume_down_clamps_to_zero(
        self,
        mock_vlc_module: mock.MagicMock,
        playing_service: Any,
    ) -> None:
        """Test volume decrease clamps at 0."""
        mock_vlc_module._mock_player.audio_get_volume.return_value = 3

        new_volume = playing_service.volume_down()

        assert new_volume == 0
        mock_vlc_module._mock_player.audio_set_volume.assert_called_once_with(0)

    def test_volume_up_not_initialized(
        self,
        mock_vlc_module: mock.MagicMock,
    ) -> None:
        """Test volume_up when not initialized."""
        from src.services.player_service import PlayerService

        service = PlayerService()
        new_volume = service.volume_up()
        assert new_volume == 0

    def test_volume_down_not_initialized(
        self,
        mock_vlc_module: mock.MagicMock,
    ) -> None:
        """Test volume_down when not initialized."""
        from src.services.player_service import PlayerService

        service = PlayerService()
        new_volume = service.volume_down()
        assert new_volume == 0

    def test_toggle_mute(
        self,
        mock_vlc_module: mock.MagicMock,
        playing_service: Any,
    ) -> None:
        """Test mute toggle."""
        mock_vlc_module._mock_player.audio_get_volume.return_value = 75

        # Mute
        volume, is_muted = playing_service.toggle_mute()

        assert volume == 0
        assert is_muted is True
        assert playing_service._is_muted is True
        assert playing_service._pre_mute_volume == 75
        mock_vlc_module._mock_player.audio_set_volume.assert_called_with(0)

    def test_toggle_unmute(
        self,
        mock_vlc_module: mock.MagicMock,
        playing_service: Any,
    ) -> None:
        """Test unmute toggle restores volume."""
        playing_service._is_muted = True
        playing_service._pre_mute_volume = 75

        volume, is_muted = playing_service.toggle_mute()

        assert volume == 75
        assert is_muted is False
        assert playing_service._is_muted is False
        mock_vlc_module._mock_player.audio_set_volume.assert_called_with(75)

    def test_toggle_mute_not_initialized(
        self,
        mock_vlc_module: mock.MagicMock,
    ) -> None:
        """Test toggle_mute when not initialized."""
        from src.services.player_service import PlayerService

        service = PlayerService()
        volume, is_muted = service.toggle_mute()
        assert volume == 0
        assert is_muted is False


class TestPlayerServiceAudioTracks:
    """Tests for audio track methods."""

    @pytest.fixture
    def playing_service(self, mock_vlc_module: mock.MagicMock) -> Any:
        """Create an initialized PlayerService with mock player."""
        from src.services.player_service import PlayerService

        service = PlayerService()
        service.initialize(12345)
        return service

    def test_get_audio_tracks(
        self,
        mock_vlc_module: mock.MagicMock,
        playing_service: Any,
    ) -> None:
        """Test get_audio_tracks returns track list."""
        mock_vlc_module._mock_player.audio_get_track.return_value = 1
        mock_vlc_module._mock_player.audio_get_track_description.return_value = [
            (-1, b"Disable"),
            (1, b"English"),
            (2, b"Polish (Voiceover)"),
        ]

        tracks = playing_service.get_audio_tracks()

        assert len(tracks) == 2
        assert tracks[0]["id"] == 1
        assert tracks[0]["name"] == "English"
        assert tracks[0]["is_current"] is True
        assert tracks[1]["id"] == 2
        assert tracks[1]["name"] == "Polish (Voiceover)"
        assert tracks[1]["is_current"] is False

    def test_get_audio_tracks_empty(
        self,
        mock_vlc_module: mock.MagicMock,
        playing_service: Any,
    ) -> None:
        """Test get_audio_tracks when no tracks available."""
        mock_vlc_module._mock_player.audio_get_track_description.return_value = None

        tracks = playing_service.get_audio_tracks()

        assert tracks == []

    def test_get_audio_tracks_not_initialized(
        self,
        mock_vlc_module: mock.MagicMock,
    ) -> None:
        """Test get_audio_tracks when not initialized."""
        from src.services.player_service import PlayerService

        service = PlayerService()
        assert service.get_audio_tracks() == []

    def test_cycle_audio_track(
        self,
        mock_vlc_module: mock.MagicMock,
        playing_service: Any,
    ) -> None:
        """Test cycling audio tracks."""
        mock_vlc_module._mock_player.audio_get_track.return_value = 1
        mock_vlc_module._mock_player.audio_get_track_description.return_value = [
            (-1, b"Disable"),
            (1, b"English"),
            (2, b"Polish (Voiceover)"),
        ]

        playing_service.cycle_audio_track()

        mock_vlc_module._mock_player.audio_set_track.assert_called_once_with(2)

    def test_cycle_audio_track_wraps_around(
        self,
        mock_vlc_module: mock.MagicMock,
        playing_service: Any,
    ) -> None:
        """Test cycling audio tracks wraps to first track."""
        mock_vlc_module._mock_player.audio_get_track.return_value = 2  # Last track
        mock_vlc_module._mock_player.audio_get_track_description.return_value = [
            (-1, b"Disable"),
            (1, b"English"),
            (2, b"Polish (Voiceover)"),
        ]

        playing_service.cycle_audio_track()

        mock_vlc_module._mock_player.audio_set_track.assert_called_once_with(1)

    def test_cycle_audio_track_single_track(
        self,
        mock_vlc_module: mock.MagicMock,
        playing_service: Any,
    ) -> None:
        """Test cycling does nothing with single track."""
        mock_vlc_module._mock_player.audio_get_track.return_value = 1
        mock_vlc_module._mock_player.audio_get_track_description.return_value = [
            (-1, b"Disable"),
            (1, b"English"),
        ]

        playing_service.cycle_audio_track()

        mock_vlc_module._mock_player.audio_set_track.assert_not_called()

    def test_cycle_audio_track_not_initialized(
        self,
        mock_vlc_module: mock.MagicMock,
    ) -> None:
        """Test cycle_audio_track when not initialized."""
        from src.services.player_service import PlayerService

        service = PlayerService()
        service.cycle_audio_track()  # Should not raise

    def test_get_current_audio_track(
        self,
        mock_vlc_module: mock.MagicMock,
        playing_service: Any,
    ) -> None:
        """Test get_current_audio_track returns active track."""
        mock_vlc_module._mock_player.audio_get_track.return_value = 2
        mock_vlc_module._mock_player.audio_get_track_description.return_value = [
            (-1, b"Disable"),
            (1, b"English"),
            (2, b"Polish (Voiceover)"),
        ]

        track = playing_service.get_current_audio_track()

        assert track is not None
        assert track["id"] == 2
        assert track["name"] == "Polish (Voiceover)"

    def test_get_current_audio_track_none(
        self,
        mock_vlc_module: mock.MagicMock,
        playing_service: Any,
    ) -> None:
        """Test get_current_audio_track returns None when no current track."""
        mock_vlc_module._mock_player.audio_get_track.return_value = -1
        mock_vlc_module._mock_player.audio_get_track_description.return_value = [
            (-1, b"Disable"),
        ]

        track = playing_service.get_current_audio_track()

        assert track is None


class TestPlayerServiceSubtitles:
    """Tests for subtitle methods."""

    @pytest.fixture
    def playing_service(self, mock_vlc_module: mock.MagicMock) -> Any:
        """Create an initialized PlayerService with mock player."""
        from src.services.player_service import PlayerService

        service = PlayerService()
        service.initialize(12345)
        return service

    def test_get_subtitle_tracks(
        self,
        mock_vlc_module: mock.MagicMock,
        playing_service: Any,
    ) -> None:
        """Test get_subtitle_tracks returns disable and subtitle tracks."""
        mock_vlc_module._mock_player.video_get_spu.return_value = 1
        mock_vlc_module._mock_player.video_get_spu_description.return_value = [
            (-1, b"Disable"),
            (1, b"Track 1"),
            (2, b"External SRT"),
        ]

        tracks = playing_service.get_subtitle_tracks()

        assert len(tracks) == 3
        assert tracks[0]["id"] == -1
        assert tracks[0]["name"] == "Subtitles Off"
        assert tracks[0]["is_current"] is False
        assert tracks[1]["id"] == 1
        assert tracks[1]["name"] == "Track 1"
        assert tracks[1]["is_current"] is True

    def test_get_subtitle_tracks_empty(
        self,
        mock_vlc_module: mock.MagicMock,
        playing_service: Any,
    ) -> None:
        """Test get_subtitle_tracks when no tracks are available."""
        mock_vlc_module._mock_player.video_get_spu_description.return_value = None

        assert playing_service.get_subtitle_tracks() == []

    def test_get_subtitle_tracks_not_initialized(
        self,
        mock_vlc_module: mock.MagicMock,
    ) -> None:
        """Test get_subtitle_tracks when not initialized."""
        from src.services.player_service import PlayerService

        service = PlayerService()
        assert service.get_subtitle_tracks() == []

    def test_cycle_subtitle_track(
        self,
        mock_vlc_module: mock.MagicMock,
        playing_service: Any,
    ) -> None:
        """Test cycling subtitle tracks."""
        mock_vlc_module._mock_player.video_get_spu.return_value = -1
        mock_vlc_module._mock_player.video_get_spu_description.return_value = [
            (-1, b"Disable"),
            (1, b"Track 1"),
        ]

        playing_service.cycle_subtitle_track()

        mock_vlc_module._mock_player.video_set_spu.assert_called_once_with(1)
        assert playing_service._subtitle_track_user_selected is True

    def test_cycle_subtitle_track_wraps_to_disabled(
        self,
        mock_vlc_module: mock.MagicMock,
        playing_service: Any,
    ) -> None:
        """Test subtitle cycling wraps back to disabled."""
        mock_vlc_module._mock_player.video_get_spu.return_value = 1
        mock_vlc_module._mock_player.video_get_spu_description.return_value = [
            (-1, b"Disable"),
            (1, b"Track 1"),
        ]

        playing_service.cycle_subtitle_track()

        mock_vlc_module._mock_player.video_set_spu.assert_called_once_with(-1)

    def test_cycle_subtitle_track_single_track(
        self,
        mock_vlc_module: mock.MagicMock,
        playing_service: Any,
    ) -> None:
        """Test subtitle cycling does nothing with only disabled track."""
        mock_vlc_module._mock_player.video_get_spu.return_value = -1
        mock_vlc_module._mock_player.video_get_spu_description.return_value = [
            (-1, b"Disable"),
        ]

        playing_service.cycle_subtitle_track()

        mock_vlc_module._mock_player.video_set_spu.assert_not_called()

    def test_cycle_subtitle_track_not_initialized(
        self,
        mock_vlc_module: mock.MagicMock,
    ) -> None:
        """Test cycle_subtitle_track when not initialized."""
        from src.services.player_service import PlayerService

        service = PlayerService()
        service.cycle_subtitle_track()  # Should not raise

    def test_get_current_subtitle_track(
        self,
        mock_vlc_module: mock.MagicMock,
        playing_service: Any,
    ) -> None:
        """Test get_current_subtitle_track returns active track."""
        mock_vlc_module._mock_player.video_get_spu.return_value = 1
        mock_vlc_module._mock_player.video_get_spu_description.return_value = [
            (-1, b"Disable"),
            (1, b"Track 1"),
        ]

        track = playing_service.get_current_subtitle_track()

        assert track is not None
        assert track["id"] == 1
        assert track["name"] == "Track 1"

    def test_get_current_subtitle_track_none(
        self,
        mock_vlc_module: mock.MagicMock,
        playing_service: Any,
    ) -> None:
        """Test get_current_subtitle_track returns None when there are no tracks."""
        mock_vlc_module._mock_player.video_get_spu_description.return_value = None

        assert playing_service.get_current_subtitle_track() is None

    def test_activate_first_subtitle_track(
        self,
        mock_vlc_module: mock.MagicMock,
        playing_service: Any,
    ) -> None:
        """Test selecting the first available subtitle track."""
        playing_service._activate_first_subtitle_track()

        mock_vlc_module._mock_player.video_set_spu.assert_called_once_with(1)

    def test_activate_first_subtitle_track_prefers_external_subtitle(
        self,
        mock_vlc_module: mock.MagicMock,
        playing_service: Any,
    ) -> None:
        """Test external subtitles are preferred over embedded subtitle tracks."""
        mock_vlc_module._mock_player.video_get_spu_description.return_value = [
            (-1, b"Disable"),
            (1, b"English"),
            (2, b"Polish external"),
        ]

        playing_service._activate_first_subtitle_track()

        mock_vlc_module._mock_player.video_set_spu.assert_called_once_with(2)
        assert playing_service._external_subtitle_track_id == 2

    def test_activate_first_subtitle_track_no_tracks(
        self,
        mock_vlc_module: mock.MagicMock,
        playing_service: Any,
    ) -> None:
        """Test subtitle activation when VLC has no selectable subtitle tracks."""
        mock_vlc_module._mock_player.video_get_spu_description.return_value = [
            (-1, b"Disable")
        ]

        playing_service._activate_first_subtitle_track()

        mock_vlc_module._mock_player.video_set_spu.assert_not_called()

    def test_activate_first_subtitle_track_error(
        self,
        mock_vlc_module: mock.MagicMock,
        playing_service: Any,
    ) -> None:
        """Test subtitle activation handles VLC errors."""
        mock_vlc_module._mock_player.video_get_spu_description.side_effect = Exception(
            "SPU error"
        )

        playing_service._activate_first_subtitle_track()

        mock_vlc_module._mock_player.video_set_spu.assert_not_called()

    def test_find_matching_subtitle_exact_stem(
        self,
        playing_service: Any,
        tmp_path: Path,
    ) -> None:
        """Test finding a subtitle with the same video stem."""
        video_file = tmp_path / "movie.mkv"
        subtitle_file = tmp_path / "movie.srt"
        video_file.touch()
        subtitle_file.touch()

        assert playing_service.find_matching_subtitle(str(video_file)) == str(
            subtitle_file
        )

    def test_find_matching_subtitle_language_suffix(
        self,
        playing_service: Any,
        tmp_path: Path,
    ) -> None:
        """Test finding a subtitle with a language suffix."""
        video_file = tmp_path / "movie.mkv"
        subtitle_file = tmp_path / "movie.en.srt"
        video_file.touch()
        subtitle_file.touch()

        assert playing_service.find_matching_subtitle(str(video_file)) == str(
            subtitle_file
        )

    def test_find_matching_subtitle_none(
        self,
        playing_service: Any,
        tmp_path: Path,
    ) -> None:
        """Test no subtitle match returns None."""
        video_file = tmp_path / "movie.mkv"
        video_file.touch()

        assert playing_service.find_matching_subtitle(str(video_file)) is None


class TestPlayerServiceStateAndRelease:
    """Tests for state checking and resource release."""

    @pytest.fixture
    def playing_service(self, mock_vlc_module: mock.MagicMock) -> Any:
        """Create an initialized PlayerService with mock player."""
        from src.services.player_service import PlayerService

        service = PlayerService()
        service.initialize(12345)
        return service

    def test_is_playing_true(
        self,
        mock_vlc_module: mock.MagicMock,
        playing_service: Any,
    ) -> None:
        """Test is_playing returns True when playing."""
        mock_vlc_module._mock_player.is_playing.return_value = 1

        assert playing_service.is_playing() is True

    def test_is_playing_false(
        self,
        mock_vlc_module: mock.MagicMock,
        playing_service: Any,
    ) -> None:
        """Test is_playing returns False when not playing."""
        mock_vlc_module._mock_player.is_playing.return_value = 0

        assert playing_service.is_playing() is False

    def test_is_playing_not_initialized(
        self,
        mock_vlc_module: mock.MagicMock,
    ) -> None:
        """Test is_playing returns False when not initialized."""
        from src.services.player_service import PlayerService

        service = PlayerService()
        assert service.is_playing() is False

    def test_stop(
        self,
        mock_vlc_module: mock.MagicMock,
        playing_service: Any,
    ) -> None:
        """Test stop stops playback."""
        playing_service.stop()

        mock_vlc_module._mock_player.stop.assert_called_once()

    def test_stop_stops_timer(
        self,
        mock_vlc_module: mock.MagicMock,
        playing_service: Any,
    ) -> None:
        """Test stop stops the time update timer."""
        assert playing_service._time_timer is not None

        playing_service.stop()

        assert not playing_service._time_timer.isActive()

    def test_release(
        self,
        mock_vlc_module: mock.MagicMock,
        playing_service: Any,
        tmp_path: Path,
    ) -> None:
        """Test release frees all resources."""
        # Load a video to have media
        video_file = tmp_path / "test.mp4"
        video_file.touch()
        playing_service.load_video(str(video_file))

        playing_service.release()

        mock_vlc_module._mock_player.stop.assert_called()
        mock_vlc_module._mock_player.release.assert_called_once()
        mock_vlc_module._mock_media.release.assert_called_once()
        mock_vlc_module._mock_instance.release.assert_called_once()

        assert playing_service._player is None
        assert playing_service._current_media is None
        assert playing_service._instance is None


class TestPlayerServiceEvents:
    """Tests for event handling and signals."""

    @pytest.fixture
    def playing_service(self, mock_vlc_module: mock.MagicMock) -> Any:
        """Create an initialized PlayerService with mock player."""
        from src.services.player_service import PlayerService

        service = PlayerService()
        service.initialize(12345)
        return service

    def test_on_end_reached_emits_signal(
        self,
        mock_vlc_module: mock.MagicMock,
        playing_service: Any,
    ) -> None:
        """Test _on_end_reached emits playback_finished signal."""
        signals_received = []
        playing_service.playback_finished.connect(lambda: signals_received.append(True))

        playing_service._on_end_reached(None)

        assert len(signals_received) == 1

    def test_on_error_emits_signal(
        self,
        mock_vlc_module: mock.MagicMock,
        playing_service: Any,
    ) -> None:
        """Test _on_error emits error_occurred signal."""
        errors_received = []
        playing_service.error_occurred.connect(lambda msg: errors_received.append(msg))

        playing_service._on_error(None)

        assert len(errors_received) == 1
        assert "error" in errors_received[0].lower()

    def test_emit_time_update(
        self,
        mock_vlc_module: mock.MagicMock,
        playing_service: Any,
    ) -> None:
        """Test _emit_time_update emits time_changed signal."""
        mock_vlc_module._mock_player.is_playing.return_value = 1
        mock_vlc_module._mock_player.get_time.return_value = 30000
        mock_vlc_module._mock_player.get_length.return_value = 120000

        time_updates = []
        playing_service.time_changed.connect(
            lambda current, total: time_updates.append((current, total))
        )

        playing_service._emit_time_update()

        assert len(time_updates) == 1
        assert time_updates[0] == (30000, 120000)

    def test_emit_time_update_not_playing(
        self,
        mock_vlc_module: mock.MagicMock,
        playing_service: Any,
    ) -> None:
        """Test _emit_time_update doesn't emit when not playing."""
        mock_vlc_module._mock_player.is_playing.return_value = 0

        time_updates = []
        playing_service.time_changed.connect(
            lambda current, total: time_updates.append((current, total))
        )

        playing_service._emit_time_update()

        assert len(time_updates) == 0

    def test_emit_time_update_invalid_time(
        self,
        mock_vlc_module: mock.MagicMock,
        playing_service: Any,
    ) -> None:
        """Test _emit_time_update handles invalid time values."""
        mock_vlc_module._mock_player.is_playing.return_value = 1
        mock_vlc_module._mock_player.get_time.return_value = -1
        mock_vlc_module._mock_player.get_length.return_value = 120000

        time_updates = []
        playing_service.time_changed.connect(
            lambda current, total: time_updates.append((current, total))
        )

        playing_service._emit_time_update()

        assert len(time_updates) == 0
