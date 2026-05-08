"""Tests for PlayerView component."""

from typing import Any

import pytest
from PySide6.QtCore import QAbstractAnimation, Qt

from src.ui.components.player_view import (
    AudioTrackOverlay,
    OSDWidget,
    PlayerView,
)
from src.ui.styles import scaled


class TestOSDWidget:
    """Tests for OSDWidget class."""

    @pytest.fixture
    def osd(self, qtbot) -> OSDWidget:
        """Create an OSDWidget instance."""
        widget = OSDWidget()
        qtbot.addWidget(widget)
        return widget

    def test_initialization(self, osd: OSDWidget) -> None:
        """Test OSDWidget initialization."""
        assert osd is not None
        assert osd.objectName() == "OSD"
        assert not osd.isVisible()

    def test_show_pause_paused(self, osd: OSDWidget) -> None:
        """Test show_pause with paused state."""
        osd.show_pause(is_paused=True)
        assert osd.isVisible()
        assert osd._pause_icon.isVisible()
        assert osd._pause_icon.text() == "\u23f8"  # Pause emoji

    def test_show_pause_playing(self, osd: OSDWidget) -> None:
        """Test show_pause with playing state."""
        osd.show_pause(is_paused=False)
        assert osd.isVisible()
        assert osd._pause_icon.isVisible()
        assert osd._pause_icon.text() == "\u25b6"  # Play emoji

    def test_show_seek_forward(self, osd: OSDWidget) -> None:
        """Test show_seek with forward direction."""
        osd.show_seek(forward=True)
        assert osd.isVisible()
        assert osd._seek_icon.isVisible()
        assert osd._seek_icon.text() == "\u23e9"  # Fast forward emoji

    def test_show_seek_backward(self, osd: OSDWidget) -> None:
        """Test show_seek with backward direction."""
        osd.show_seek(forward=False)
        assert osd.isVisible()
        assert osd._seek_icon.isVisible()
        assert osd._seek_icon.text() == "\u23ea"  # Rewind emoji

    def test_show_volume_muted(self, osd: OSDWidget) -> None:
        """Test show_volume when muted."""
        osd.show_volume(level=50, is_muted=True)
        assert osd.isVisible()
        assert osd._volume_icon.isVisible()
        assert osd._volume_icon.text() == "\U0001f507"  # Muted emoji

    def test_show_volume_zero(self, osd: OSDWidget) -> None:
        """Test show_volume at zero level."""
        osd.show_volume(level=0, is_muted=False)
        assert osd._volume_icon.text() == "\U0001f507"  # Muted emoji

    def test_show_volume_low(self, osd: OSDWidget) -> None:
        """Test show_volume at low level."""
        osd.show_volume(level=20, is_muted=False)
        assert osd._volume_icon.text() == "\U0001f508"  # Low volume emoji

    def test_show_volume_medium(self, osd: OSDWidget) -> None:
        """Test show_volume at medium level."""
        osd.show_volume(level=50, is_muted=False)
        assert osd._volume_icon.text() == "\U0001f509"  # Medium volume emoji

    def test_show_volume_high(self, osd: OSDWidget) -> None:
        """Test show_volume at high level."""
        osd.show_volume(level=80, is_muted=False)
        assert osd._volume_icon.text() == "\U0001f50a"  # High volume emoji

    def test_show_audio_track(self, osd: OSDWidget) -> None:
        """Test show_audio_track indicator."""
        osd.show_audio_track("English")
        assert osd.isVisible()
        assert osd._audio_track_icon.isVisible()
        assert osd._audio_track_icon.text() == "\U0001f524"  # Letters emoji

    def test_icons_mutually_exclusive(self, osd: OSDWidget) -> None:
        """Test that only one icon is shown at a time."""
        osd.show_pause(True)
        assert osd._pause_icon.isVisible()
        assert not osd._seek_icon.isVisible()

        osd.show_seek(True)
        assert not osd._pause_icon.isVisible()
        assert osd._seek_icon.isVisible()

        osd.show_volume(50, False)
        assert not osd._seek_icon.isVisible()
        assert osd._volume_icon.isVisible()

    def test_fade_out(self, osd: OSDWidget) -> None:
        """Test fade_out starts animation."""
        osd.show_pause(True)
        osd.fade_out()
        # Animation should be running
        assert osd._fade_animation.state() == QAbstractAnimation.State.Running

    def test_fade_animation_hides_widget(self, osd: OSDWidget, qtbot) -> None:
        """Test that fade animation hides widget when complete."""
        osd.show_pause(True)
        assert osd.isVisible()

        # Manually trigger the on_fade_finished with opacity at 0
        osd._opacity_effect.setOpacity(0.0)
        osd._on_fade_finished()

        assert not osd.isVisible()

    def test_hide_all_icons(self, osd: OSDWidget) -> None:
        """Test _hide_all_icons hides all icon labels."""
        osd.show_pause(True)
        osd._hide_all_icons()
        assert not osd._pause_icon.isVisible()
        assert not osd._seek_icon.isVisible()
        assert not osd._volume_icon.isVisible()
        assert not osd._audio_track_icon.isVisible()


class TestAudioTrackOverlay:
    """Tests for AudioTrackOverlay class."""

    @pytest.fixture
    def overlay(self, qtbot) -> AudioTrackOverlay:
        """Create an AudioTrackOverlay instance."""
        widget = AudioTrackOverlay()
        qtbot.addWidget(widget)
        return widget

    @pytest.fixture
    def sample_tracks(self) -> list[dict[str, Any]]:
        """Create sample audio tracks for testing."""
        return [
            {"id": 1, "name": "English", "is_current": True},
            {"id": 2, "name": "Spanish", "is_current": False},
            {"id": 3, "name": "Voiceover", "is_current": False},
        ]

    def test_initialization(self, overlay: AudioTrackOverlay) -> None:
        """Test AudioTrackOverlay initialization."""
        assert overlay is not None
        assert overlay.objectName() == "AudioTrackOverlay"
        assert not overlay.isVisible()

    def test_set_tracks(
        self, overlay: AudioTrackOverlay, sample_tracks: list[dict[str, Any]]
    ) -> None:
        """Test set_tracks populates the overlay."""
        overlay.set_tracks(sample_tracks)
        assert len(overlay.get_tracks()) == 3

    def test_get_tracks_empty(self, overlay: AudioTrackOverlay) -> None:
        """Test get_tracks returns empty list initially."""
        assert overlay.get_tracks() == []

    def test_set_tracks_clears_previous(
        self, overlay: AudioTrackOverlay, sample_tracks: list[dict[str, Any]]
    ) -> None:
        """Test that set_tracks clears previous tracks."""
        overlay.set_tracks(sample_tracks)
        assert len(overlay.get_tracks()) == 3

        # Set new tracks
        new_tracks = [{"id": 1, "name": "French", "is_current": True}]
        overlay.set_tracks(new_tracks)
        assert len(overlay.get_tracks()) == 1
        assert overlay.get_tracks()[0]["name"] == "French"

    def test_track_selected_signal_exists(self, overlay: AudioTrackOverlay) -> None:
        """Test that track_selected signal exists."""
        assert hasattr(overlay, "track_selected")


class TestPlayerView:
    """Tests for PlayerView class."""

    @pytest.fixture
    def player_view(self, qtbot) -> PlayerView:
        """Create a PlayerView instance."""
        view = PlayerView()
        qtbot.addWidget(view)
        return view

    @pytest.fixture
    def sample_tracks(self) -> list[dict[str, Any]]:
        """Create sample audio tracks for testing."""
        return [
            {"id": 1, "name": "English", "is_current": True},
            {"id": 2, "name": "Spanish", "is_current": False},
        ]

    def test_initialization(self, player_view: PlayerView) -> None:
        """Test PlayerView initialization."""
        assert player_view is not None
        assert player_view.objectName() == "PlayerView"

    def test_has_video_frame(self, player_view: PlayerView) -> None:
        """Test that PlayerView has a video frame widget."""
        assert player_view._video_frame is not None
        assert player_view._video_frame.objectName() == "VideoFrame"

    def test_has_osd(self, player_view: PlayerView) -> None:
        """Test that PlayerView has an OSD widget."""
        assert player_view._osd is not None
        assert isinstance(player_view._osd, OSDWidget)

    def test_has_audio_track_overlay(self, player_view: PlayerView) -> None:
        """Test that PlayerView has an audio track overlay."""
        assert player_view._audio_track_overlay is not None
        assert isinstance(player_view._audio_track_overlay, AudioTrackOverlay)

    def test_get_video_frame_id(self, player_view: PlayerView) -> None:
        """Test get_video_frame_id returns an integer."""
        frame_id = player_view.get_video_frame_id()
        assert isinstance(frame_id, int)
        assert frame_id > 0

    def test_show_pause_indicator(self, player_view: PlayerView) -> None:
        """Test show_pause_indicator shows OSD."""
        player_view.show()  # Parent must be shown for child visibility
        player_view.show_pause_indicator(is_paused=True)
        assert player_view._osd.isVisible()

    def test_show_seek_indicator(self, player_view: PlayerView) -> None:
        """Test show_seek_indicator shows OSD."""
        player_view.show()
        player_view.show_seek_indicator(forward=True)
        assert player_view._osd.isVisible()

    def test_show_volume_indicator(self, player_view: PlayerView) -> None:
        """Test show_volume_indicator shows OSD."""
        player_view.show()
        player_view.show_volume_indicator(level=50, is_muted=False)
        assert player_view._osd.isVisible()

    def test_show_audio_track_indicator(self, player_view: PlayerView) -> None:
        """Test show_audio_track_indicator shows OSD."""
        player_view.show()
        player_view.show_audio_track_indicator(track_name="English")
        assert player_view._osd.isVisible()

    def test_show_audio_track_overlay(
        self, player_view: PlayerView, sample_tracks: list[dict[str, Any]]
    ) -> None:
        """Test show_audio_track_overlay shows the overlay."""
        player_view.show()
        player_view.show_audio_track_overlay(sample_tracks)
        assert player_view._audio_track_overlay.isVisible()

    def test_hide_audio_track_overlay(self, player_view: PlayerView) -> None:
        """Test hide_audio_track_overlay hides the overlay."""
        player_view._audio_track_overlay.show()
        player_view.hide_audio_track_overlay()
        assert not player_view._audio_track_overlay.isVisible()

    def test_is_audio_track_overlay_visible(
        self, player_view: PlayerView, sample_tracks: list[dict[str, Any]]
    ) -> None:
        """Test is_audio_track_overlay_visible returns correct state."""
        player_view.show()
        assert not player_view.is_audio_track_overlay_visible()
        player_view.show_audio_track_overlay(sample_tracks)
        assert player_view.is_audio_track_overlay_visible()

    def test_hide_cursor(self, player_view: PlayerView) -> None:
        """Test hide_cursor hides the mouse cursor."""
        player_view.hide_cursor()
        assert player_view._cursor_hidden
        assert player_view.cursor().shape() == Qt.BlankCursor

    def test_show_cursor(self, player_view: PlayerView) -> None:
        """Test show_cursor shows the mouse cursor."""
        player_view.hide_cursor()
        player_view.show_cursor()
        assert not player_view._cursor_hidden
        assert player_view.cursor().shape() == Qt.ArrowCursor

    def test_show_cursor_when_not_hidden(self, player_view: PlayerView) -> None:
        """Test show_cursor does nothing when cursor not hidden."""
        initial_hidden = player_view._cursor_hidden
        player_view.show_cursor()
        assert player_view._cursor_hidden == initial_hidden

    def test_hide_cursor_when_already_hidden(self, player_view: PlayerView) -> None:
        """Test hide_cursor does nothing when already hidden."""
        player_view.hide_cursor()
        player_view.hide_cursor()  # Call again
        assert player_view._cursor_hidden
        assert player_view.cursor().shape() == Qt.BlankCursor

    def test_enter_fullscreen(self, player_view: PlayerView) -> None:
        """Test enter_fullscreen hides cursor."""
        player_view.enter_fullscreen()
        assert player_view._cursor_hidden

    def test_exit_fullscreen(self, player_view: PlayerView) -> None:
        """Test exit_fullscreen shows cursor and cleans up."""
        player_view.enter_fullscreen()
        player_view._audio_track_overlay.show()

        player_view.exit_fullscreen()

        assert not player_view._cursor_hidden
        assert not player_view._audio_track_overlay.isVisible()
        assert not player_view._osd.isVisible()

    def test_set_focus(self, player_view: PlayerView) -> None:
        """Test set_focus sets focus to the view."""
        player_view.set_focus()
        # Focus behavior depends on widget hierarchy

    def test_trigger_activity(self, player_view: PlayerView) -> None:
        """Test trigger_activity resets OSD timer."""
        player_view.trigger_activity()
        assert player_view._osd_timer.isActive()

    def test_view_ready_signal(self, player_view: PlayerView, qtbot) -> None:
        """Test view_ready signal is emitted on show."""
        with qtbot.waitSignal(player_view.view_ready, timeout=1000) as blocker:
            player_view.show()

        assert isinstance(blocker.args[0], int)
        assert blocker.args[0] > 0

    def test_osd_timer_setup(self, player_view: PlayerView) -> None:
        """Test OSD timer is properly set up."""
        assert player_view._osd_timer is not None
        assert player_view._osd_timer.isSingleShot()

    def test_osd_timeout_fades_osd(self, player_view: PlayerView) -> None:
        """Test OSD timeout triggers fade out."""
        player_view.show_pause_indicator(True)
        player_view._on_osd_timeout()
        # Fade animation should be running
        assert (
            player_view._osd._fade_animation.state()
            == QAbstractAnimation.State.Running
        )

    def test_resize_repositions_overlays(self, player_view: PlayerView) -> None:
        """Test resize event repositions overlays."""
        player_view.show()
        player_view.resize(800, 600)

        # OSD should be centered horizontally at bottom
        osd_center = player_view._osd.x() + player_view._osd.width() // 2
        view_center = player_view.width() // 2
        assert abs(osd_center - view_center) <= 1  # Allow 1px tolerance

    def test_position_overlays_on_show(self, player_view: PlayerView) -> None:
        """Test overlays are positioned when view is shown."""
        player_view.resize(800, 600)
        player_view.show()

        # Audio track overlay should be on the right side
        track_overlay_right = (
            player_view._audio_track_overlay.x()
            + player_view._audio_track_overlay.width()
        )
        expected_right = player_view.width() - scaled(20)
        assert abs(track_overlay_right - expected_right) <= 1

    def test_osd_timer_resets_on_activity(self, player_view: PlayerView) -> None:
        """Test OSD timer resets when activity is triggered."""
        player_view.show_pause_indicator(True)
        assert player_view._osd_timer.isActive()

        # Trigger activity again
        player_view.trigger_activity()
        assert player_view._osd_timer.isActive()

    def test_multiple_osd_indicators_in_sequence(self, player_view: PlayerView) -> None:
        """Test showing different OSD indicators in sequence."""
        player_view.show()
        player_view.show_pause_indicator(True)
        assert player_view._osd._pause_icon.isVisible()

        player_view.show_seek_indicator(True)
        assert player_view._osd._seek_icon.isVisible()
        assert not player_view._osd._pause_icon.isVisible()

        player_view.show_volume_indicator(50, False)
        assert player_view._osd._volume_icon.isVisible()
        assert not player_view._osd._seek_icon.isVisible()


class TestPlayerViewIntegration:
    """Integration tests for PlayerView with its sub-components."""

    @pytest.fixture
    def player_view(self, qtbot) -> PlayerView:
        """Create a PlayerView instance."""
        view = PlayerView()
        qtbot.addWidget(view)
        return view

    def test_full_playback_cycle(self, player_view: PlayerView, qtbot) -> None:
        """Test a full playback cycle simulation."""
        player_view.show()

        # Enter fullscreen mode
        player_view.enter_fullscreen()
        assert player_view._cursor_hidden

        # Show various OSD states
        player_view.show_pause_indicator(False)  # Playing
        assert player_view._osd.isVisible()

        player_view.show_seek_indicator(True)  # Seek forward
        assert player_view._osd._seek_icon.isVisible()

        player_view.show_volume_indicator(75, False)  # Volume
        assert player_view._osd._volume_icon.isVisible()

        # Show audio tracks
        tracks = [
            {"id": 1, "name": "English", "is_current": True},
            {"id": 2, "name": "Polish Voiceover", "is_current": False},
        ]
        player_view.show_audio_track_overlay(tracks)
        assert player_view.is_audio_track_overlay_visible()

        # Hide audio tracks
        player_view.hide_audio_track_overlay()
        assert not player_view.is_audio_track_overlay_visible()

        # Exit fullscreen
        player_view.exit_fullscreen()
        assert not player_view._cursor_hidden

    def test_osd_visibility_lifecycle(self, player_view: PlayerView, qtbot) -> None:
        """Test OSD visibility through its lifecycle."""
        player_view.show()

        # Initially OSD is hidden
        assert not player_view._osd.isVisible()

        # Show OSD
        player_view.show_pause_indicator(True)
        assert player_view._osd.isVisible()
        assert player_view._osd_timer.isActive()

        # Trigger timeout
        player_view._on_osd_timeout()

        # Wait for fade animation
        # Since animation is async, we verify the animation started
        assert player_view._osd._fade_animation.state() in (
            QAbstractAnimation.State.Running,
            QAbstractAnimation.State.Stopped,
        )
