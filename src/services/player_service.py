"""Player service for Hackflix.

This module provides the PlayerService class for managing video playback
using the VLC media library.
"""

import logging
from pathlib import Path
from typing import Any

import vlc
from PySide6.QtCore import QObject, QTimer, Signal

logger = logging.getLogger(__name__)

# Default player settings
DEFAULT_VOLUME_STEP = 5
DEFAULT_SEEK_SECONDS = 10
DEFAULT_TIME_UPDATE_INTERVAL_MS = 500


class PlayerService(QObject):
    """VLC-based video player service.

    Manages the VLC instance and media player for video playback.
    Supports audio track cycling.

    Signals:
        playback_finished: Emitted when playback reaches the end.
        time_changed: Emitted with (current_ms: int, total_ms: int).
        error_occurred: Emitted with (error_message: str).
    """

    playback_finished = Signal()
    time_changed = Signal(int, int)  # current_ms, total_ms
    error_occurred = Signal(str)

    def __init__(
        self,
        volume_step: int = DEFAULT_VOLUME_STEP,
        seek_seconds: int = DEFAULT_SEEK_SECONDS,
        parent: QObject | None = None,
    ) -> None:
        """Initialize the PlayerService.

        Args:
            volume_step: Volume change per step (0-100).
            seek_seconds: Seek delta in seconds.
            parent: Optional parent QObject.
        """
        super().__init__(parent)
        self._volume_step = volume_step
        self._seek_seconds = seek_seconds

        self._instance: vlc.Instance | None = None
        self._player: vlc.MediaPlayer | None = None
        self._current_media: vlc.Media | None = None
        self._is_muted = False
        self._pre_mute_volume = 100
        self._current_audio_track_index = 0

        # Timer for time updates
        self._time_timer: QTimer | None = None

    def initialize(self, video_frame_id: int) -> None:
        """Initialize VLC and bind to a Qt widget.

        Creates the VLC instance with hardware acceleration settings
        and binds the video output to the specified widget window ID.

        Args:
            video_frame_id: The winId() of the QFrame widget for video output.

        Raises:
            vlc.VLCException: If VLC initialization fails.
        """
        try:
            # VLC arguments for optimal Pi 5 performance
            vlc_args = [
                "--no-xlib",  # Disable X11 for better performance
                "--quiet",  # Reduce console output
            ]

            self._instance = vlc.Instance(vlc_args)
            if not self._instance:
                raise vlc.VLCException("Failed to create VLC instance")

            self._player = self._instance.media_player_new()
            if not self._player:
                raise vlc.VLCException("Failed to create VLC media player")

            # Bind video output to widget
            self._player.set_xwindow(video_frame_id)

            # Set up event manager for end-of-playback detection
            event_manager = self._player.event_manager()
            event_manager.event_attach(
                vlc.EventType.MediaPlayerEndReached,  # type: ignore[attr-defined]
                self._on_end_reached,
            )
            event_manager.event_attach(
                vlc.EventType.MediaPlayerEncounteredError,  # type: ignore[attr-defined]
                self._on_error,
            )

            # Start time update timer
            self._time_timer = QTimer(self)
            self._time_timer.timeout.connect(self._emit_time_update)
            self._time_timer.start(DEFAULT_TIME_UPDATE_INTERVAL_MS)

            logger.info("PlayerService initialized with widget ID %d", video_frame_id)

        except vlc.VLCException as e:
            logger.error("VLC initialization failed: %s", e)
            self.error_occurred.emit(f"VLC initialization failed: {e}")
            raise

    def load_video(self, file_path: str) -> None:
        """Load a video file.

        Args:
            file_path: Path to the video file.

        Raises:
            vlc.VLCException: If media loading fails.
            FileNotFoundError: If video file doesn't exist.
        """
        if not self._instance or not self._player:
            error_msg = "Player not initialized"
            logger.error(error_msg)
            self.error_occurred.emit(error_msg)
            return

        # Validate file exists
        video_path = Path(file_path)
        if not video_path.exists():
            error_msg = f"Video file not found: {file_path}"
            logger.error(error_msg)
            self.error_occurred.emit(error_msg)
            raise FileNotFoundError(error_msg)

        try:
            # Create media from file path
            self._current_media = self._instance.media_new(file_path)
            if not self._current_media:
                raise vlc.VLCException("Failed to create media from file")

            self._player.set_media(self._current_media)
            self._player.play()

            # Reset audio track index
            self._current_audio_track_index = 0

            logger.info("Loaded video: %s", file_path)

        except vlc.VLCException as e:
            logger.error("Failed to load video: %s", e)
            self.error_occurred.emit(f"Failed to load video: {e}")
            raise

    def load_subtitle(self, path: str) -> None:
        """Load a subtitle file.

        Args:
            path: Path to the subtitle file (SRT format).
        """
        if not self._player:
            logger.error("Player not initialized")
            return

        subtitle_file = Path(path)
        if not subtitle_file.exists():
            logger.warning("Subtitle file not found: %s", path)
            return

        try:
            self._player.video_set_subtitle_file(path)
            logger.info("Loaded subtitle file: %s", path)
        except Exception as e:
            logger.error("Failed to load subtitle: %s", e)

    def toggle_pause(self) -> None:
        """Toggle pause state of playback."""
        if not self._player:
            return

        self._player.pause()
        is_playing = self._player.is_playing()
        logger.debug("Playback %s", "resumed" if is_playing else "paused")

    def seek(self, delta_ms: int) -> None:
        """Seek relative to current position.

        Args:
            delta_ms: Time delta in milliseconds (positive = forward).
        """
        if not self._player:
            return

        current_time = self._player.get_time()
        if current_time < 0:
            return

        new_time = max(0, current_time + delta_ms)
        total_time = self._player.get_length()
        if total_time > 0:
            new_time = min(new_time, total_time)

        self._player.set_time(new_time)
        logger.debug("Seeked to %d ms (delta: %d)", new_time, delta_ms)

    def seek_forward(self) -> None:
        """Seek forward by configured seconds."""
        self.seek(self._seek_seconds * 1000)

    def seek_backward(self) -> None:
        """Seek backward by configured seconds."""
        self.seek(-self._seek_seconds * 1000)

    def get_position_seconds(self) -> int:
        """Get current playback position in seconds.

        Returns:
            Current position in seconds, or 0 if not playing.
        """
        if not self._player:
            return 0

        time_ms = self._player.get_time()
        return max(0, time_ms // 1000) if time_ms >= 0 else 0

    def set_position_seconds(self, seconds: int) -> None:
        """Set playback position in seconds.

        Args:
            seconds: Position to seek to in seconds.
        """
        if not self._player:
            return

        time_ms = max(0, seconds * 1000)
        total_time = self._player.get_length()
        if total_time > 0:
            time_ms = min(time_ms, total_time)

        self._player.set_time(time_ms)
        logger.debug("Set position to %d seconds", seconds)

    def volume_up(self) -> int:
        """Increase volume by configured step.

        Returns:
            The new volume level (0-100).
        """
        if not self._player:
            return 0

        current = self._player.audio_get_volume()
        new_volume = min(100, current + self._volume_step)
        self._player.audio_set_volume(new_volume)
        self._is_muted = False
        logger.debug("Volume up: %d -> %d", current, new_volume)
        return new_volume

    def volume_down(self) -> int:
        """Decrease volume by configured step.

        Returns:
            The new volume level (0-100).
        """
        if not self._player:
            return 0

        current = self._player.audio_get_volume()
        new_volume = max(0, current - self._volume_step)
        self._player.audio_set_volume(new_volume)
        self._is_muted = new_volume == 0
        logger.debug("Volume down: %d -> %d", current, new_volume)
        return new_volume

    def toggle_mute(self) -> tuple[int, bool]:
        """Toggle audio mute state.

        Returns:
            Tuple of (current_volume, is_muted).
        """
        if not self._player:
            return (0, False)

        if self._is_muted:
            # Unmute - restore previous volume
            self._player.audio_set_volume(self._pre_mute_volume)
            self._is_muted = False
            logger.debug("Unmuted, volume restored to %d", self._pre_mute_volume)
            return (self._pre_mute_volume, False)
        else:
            # Mute - save current volume and set to 0
            self._pre_mute_volume = self._player.audio_get_volume()
            self._player.audio_set_volume(0)
            self._is_muted = True
            logger.debug("Muted, saved volume %d", self._pre_mute_volume)
            return (0, True)

    def get_audio_tracks(self) -> list[dict[str, Any]]:
        """Get list of available audio tracks.

        Returns:
            List of dicts with 'id', 'name', and 'is_current' keys.
        """
        if not self._player:
            return []

        tracks: list[dict[str, Any]] = []
        track_description = self._player.audio_get_track_description()

        if track_description:
            current_track_id = self._player.audio_get_track()
            for track_id, track_name in track_description:
                # Skip "Disable" track (id = -1)
                if track_id == -1:
                    continue
                tracks.append(
                    {
                        "id": track_id,
                        "name": track_name.decode("utf-8")
                        if isinstance(track_name, bytes)
                        else track_name,
                        "is_current": track_id == current_track_id,
                    }
                )

        return tracks

    def cycle_audio_track(self) -> None:
        """Cycle through available audio tracks sequentially."""
        if not self._player:
            return

        tracks = self.get_audio_tracks()
        if len(tracks) <= 1:
            logger.debug("Only one audio track available, cannot cycle")
            return

        # Find current track index
        current_index = 0
        for i, track in enumerate(tracks):
            if track["is_current"]:
                current_index = i
                break

        # Cycle to next track
        next_index = (current_index + 1) % len(tracks)
        next_track = tracks[next_index]

        self._player.audio_set_track(next_track["id"])
        self._current_audio_track_index = next_index

        logger.info(
            "Switched audio track: %s -> %s",
            tracks[current_index]["name"],
            next_track["name"],
        )

    def get_current_audio_track(self) -> dict[str, Any] | None:
        """Get the currently active audio track.

        Returns:
            Dict with track info or None if no track is active.
        """
        tracks = self.get_audio_tracks()
        for track in tracks:
            if track["is_current"]:
                return track
        return None

    def is_playing(self) -> bool:
        """Check if media is currently playing.

        Returns:
            True if playing, False otherwise.
        """
        if not self._player:
            return False
        return bool(self._player.is_playing())

    def stop(self) -> None:
        """Stop playback and release resources."""
        if self._time_timer:
            self._time_timer.stop()

        if self._player:
            self._player.stop()

        logger.debug("Playback stopped")

    def release(self) -> None:
        """Release all VLC resources."""
        self.stop()

        if self._player:
            self._player.release()
            self._player = None

        if self._current_media:
            self._current_media.release()
            self._current_media = None

        if self._instance:
            self._instance.release()
            self._instance = None

        logger.info("PlayerService resources released")

    def _on_end_reached(self, event: Any) -> None:
        """Handle media end reached event.

        Args:
            event: VLC event (unused but required by callback signature).
        """
        logger.info("Playback finished")
        self.playback_finished.emit()

    def _on_error(self, event: Any) -> None:
        """Handle media player error event.

        Args:
            event: VLC event (unused but required by callback signature).
        """
        error_msg = "Media playback error occurred"
        logger.error(error_msg)
        self.error_occurred.emit(error_msg)

    def _emit_time_update(self) -> None:
        """Emit current time position update."""
        if not self._player or not self._player.is_playing():
            return

        current_ms = self._player.get_time()
        total_ms = self._player.get_length()

        if current_ms >= 0 and total_ms > 0:
            self.time_changed.emit(current_ms, total_ms)
