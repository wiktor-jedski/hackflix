"""Player view component for Hackflix.

This module provides the PlayerView widget for full-screen video playback
with On-Screen Display (OSD) controls.
"""

import logging
from typing import Any

from src.qt import QPropertyAnimation, Qt, QTimer, Signal
from src.qt import QCursor
from src.qt import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from src.config import OSD_FADE_TIMEOUT_MS
from src.ui.styles import (
    BACKGROUND_COLOR,
    FONT_SIZE_LARGE,
    FONT_SIZE_BODY,
    FONT_SIZE_TITLE,
    SURFACE_COLOR,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
    scaled,
)

logger = logging.getLogger(__name__)


class OSDWidget(QFrame):
    """On-Screen Display widget for player controls.

    Displays minimal icons for pause, seek, volume, and audio track status.
    Auto-fades after timeout period of inactivity.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the OSD widget.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self._setup_ui()
        self._setup_animation()

    def _setup_ui(self) -> None:
        """Set up the OSD UI layout."""
        self.setObjectName("OSD")
        self.setStyleSheet("""
            QFrame#OSD {
                background-color: rgba(0, 0, 0, 180);
                border-radius: 8px;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(scaled(24), scaled(12), scaled(24), scaled(12))
        layout.setSpacing(scaled(6))

        icon_layout = QHBoxLayout()
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_layout.setSpacing(scaled(32))

        # Create icon labels
        self._pause_icon = self._create_icon_label("pause_icon")
        self._seek_icon = self._create_icon_label("seek_icon")
        self._volume_icon = self._create_icon_label("volume_icon")
        self._audio_track_icon = self._create_icon_label("audio_track_icon")

        icon_layout.addStretch()
        icon_layout.addWidget(self._pause_icon)
        icon_layout.addWidget(self._seek_icon)
        icon_layout.addWidget(self._volume_icon)
        icon_layout.addWidget(self._audio_track_icon)
        icon_layout.addStretch()
        layout.addLayout(icon_layout)

        self._time_label = QLabel()
        self._time_label.setObjectName("time_label")
        self._time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._time_label.setStyleSheet(f"""
            QLabel {{
                color: {TEXT_SECONDARY};
                font-size: {FONT_SIZE_BODY}px;
                min-height: {scaled(22)}px;
            }}
        """)
        layout.addWidget(self._time_label)

        # Initially hide all icons
        self._pause_icon.hide()
        self._seek_icon.hide()
        self._volume_icon.hide()
        self._audio_track_icon.hide()
        self._time_label.hide()

        self.setFixedHeight(scaled(104))
        self.hide()

    def _create_icon_label(self, name: str) -> QLabel:
        """Create a styled icon label.

        Args:
            name: Object name for the label.

        Returns:
            The created QLabel.
        """
        label = QLabel()
        label.setObjectName(name)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet(f"""
            QLabel {{
                color: {TEXT_PRIMARY};
                font-size: {FONT_SIZE_LARGE}px;
                min-width: {scaled(48)}px;
                min-height: {scaled(48)}px;
            }}
        """)
        return label

    def _setup_animation(self) -> None:
        """Set up the fade animation."""
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_effect)
        self._opacity_effect.setOpacity(1.0)

        self._fade_animation = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._fade_animation.setDuration(scaled(300))
        self._fade_animation.finished.connect(self._on_fade_finished)

    def _on_fade_finished(self) -> None:
        """Handle fade animation completion."""
        if self._opacity_effect.opacity() == 0.0:
            self.hide()
            self._hide_all_icons()

    def _hide_all_icons(self) -> None:
        """Hide all OSD icons."""
        self._pause_icon.hide()
        self._seek_icon.hide()
        self._volume_icon.hide()
        self._audio_track_icon.hide()
        self._time_label.hide()

    def _set_time_text(self, time_text: str | None) -> None:
        """Set or hide the playback time text."""
        if time_text:
            self._time_label.setText(time_text)
            self._time_label.show()
        else:
            self._time_label.clear()
            self._time_label.hide()

    def show_pause(self, is_paused: bool, time_text: str | None = None) -> None:
        """Show pause/play indicator.

        Args:
            is_paused: True to show pause icon, False for play.
            time_text: Optional playback time to show under the icon.
        """
        self._hide_all_icons()
        self._pause_icon.setText("⏸" if is_paused else "▶")
        self._pause_icon.show()
        self._set_time_text(time_text)
        self._show_osd()

    def show_seek(self, forward: bool, time_text: str | None = None) -> None:
        """Show seek indicator.

        Args:
            forward: True for forward seek, False for backward.
            time_text: Optional playback time to show under the icon.
        """
        self._hide_all_icons()
        self._seek_icon.setText("⏩" if forward else "⏪")
        self._seek_icon.show()
        self._set_time_text(time_text)
        self._show_osd()

    def show_volume(self, level: int, is_muted: bool) -> None:
        """Show volume indicator.

        Args:
            level: Volume level 0-100.
            is_muted: True if audio is muted.
        """
        self._hide_all_icons()
        if is_muted or level == 0:
            self._volume_icon.setText("🔇")
        elif level < 33:
            self._volume_icon.setText("🔈")
        elif level < 66:
            self._volume_icon.setText("🔉")
        else:
            self._volume_icon.setText("🔊")
        self._volume_icon.show()
        self._show_osd()

    def show_audio_track(self, track_name: str) -> None:
        """Show audio track indicator.

        Args:
            track_name: Name of the current audio track.
        """
        self._hide_all_icons()
        self._audio_track_icon.setText("🔤")
        self._audio_track_icon.show()
        self._show_osd()

    def show_subtitle_track(self, track_name: str) -> None:
        """Show subtitle track indicator.

        Args:
            track_name: Name of the current subtitle track.
        """
        self._hide_all_icons()
        self._audio_track_icon.setText("🔤")
        self._audio_track_icon.show()
        self._show_osd()

    def _show_osd(self) -> None:
        """Show the OSD with full opacity."""
        self._fade_animation.stop()
        self._opacity_effect.setOpacity(1.0)
        self.show()

    def fade_out(self) -> None:
        """Start the fade-out animation."""
        self._fade_animation.setStartValue(1.0)
        self._fade_animation.setEndValue(0.0)
        self._fade_animation.start()


class AudioTrackOverlay(QFrame):
    """Overlay for displaying available audio tracks.

    Shows a list of audio tracks that the user can select.
    """

    track_selected = Signal(int)  # Track ID

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the audio track overlay.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self._tracks: list[dict[str, Any]] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        """Set up the overlay UI layout."""
        self.setObjectName("AudioTrackOverlay")
        self.setStyleSheet(f"""
            QFrame#AudioTrackOverlay {{
                background-color: rgba(0, 0, 0, 200);
                border-radius: 8px;
                border: 1px solid {SURFACE_COLOR};
            }}
        """)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(scaled(16), scaled(16), scaled(16), scaled(16))
        self._layout.setSpacing(scaled(8))

        self._title_label = QLabel("Audio Tracks")
        self._title_label.setStyleSheet(f"""
            QLabel {{
                color: {TEXT_PRIMARY};
                font-size: {FONT_SIZE_BODY}px;
                font-weight: bold;
            }}
        """)
        self._layout.addWidget(self._title_label)

        self._tracks_container = QWidget()
        self._tracks_layout = QVBoxLayout(self._tracks_container)
        self._tracks_layout.setContentsMargins(0, 0, 0, 0)
        self._tracks_layout.setSpacing(scaled(4))
        self._layout.addWidget(self._tracks_container)

        self.setFixedWidth(scaled(300))
        self.hide()

    def set_tracks(self, tracks: list[dict[str, Any]]) -> None:
        """Set the available audio tracks.

        Args:
            tracks: List of track dicts with 'id', 'name', 'is_current' keys.
        """
        self._tracks = tracks

        # Clear existing track labels
        while self._tracks_layout.count():
            item = self._tracks_layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        # Add new track labels
        for track in tracks:
            label = QLabel(track["name"])
            is_current = track.get("is_current", False)
            label.setStyleSheet(f"""
                QLabel {{
                    color: {TEXT_PRIMARY if is_current else TEXT_SECONDARY};
                    font-size: {FONT_SIZE_BODY}px;
                    padding: {scaled(8)}px;
                    background-color: {"rgba(233, 69, 96, 100)" if is_current else "transparent"};
                    border-radius: 4px;
                }}
            """)
            self._tracks_layout.addWidget(label)

        self.adjustSize()

    def get_tracks(self) -> list[dict[str, Any]]:
        """Get the current list of tracks.

        Returns:
            List of track dictionaries.
        """
        return self._tracks


class PlayerView(QFrame):
    """Full-screen player view for video playback.

    The player view consists of:
    - Black background for video display
    - QFrame widget for VLC video output
    - OSD for minimal playback controls
    - Audio track selection overlay

    This is a "dumb" component - it only displays data and emits signals.
    All business logic is handled by the controller.

    Signals:
        view_ready: Emitted when the view is ready with the video frame ID.
    """

    view_ready = Signal(int)  # Video frame winId

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the PlayerView.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self._cursor_hidden = False
        self._osd_timer: QTimer | None = None
        self._setup_ui()
        self._setup_osd_timer()

    def _setup_ui(self) -> None:
        """Set up the player view UI layout."""
        self.setObjectName("PlayerView")
        self.setStyleSheet(f"background-color: {BACKGROUND_COLOR};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Video frame for VLC output
        self._video_frame = QFrame()
        self._video_frame.setObjectName("VideoFrame")
        self._video_frame.setStyleSheet("background-color: black;")
        self._video_frame.setMinimumSize(scaled(640), scaled(480))
        layout.addWidget(self._video_frame)

        # OSD overlay (positioned at bottom center)
        self._osd = OSDWidget(self)

        # Audio track overlay (positioned at right)
        self._audio_track_overlay = AudioTrackOverlay(self)

        self._subtitle_label = QLabel(self)
        self._subtitle_label.setObjectName("SubtitleOverlay")
        self._subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._subtitle_label.setWordWrap(True)
        self._subtitle_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._subtitle_label.setStyleSheet(f"""
            QLabel#SubtitleOverlay {{
                color: white;
                background-color: transparent;
                padding: 0;
                font-family: Arial, Helvetica, sans-serif;
                font-size: {FONT_SIZE_TITLE}px;
                font-weight: 400;
            }}
        """)
        self._subtitle_label.hide()

        logger.debug("PlayerView UI initialized")

    def _setup_osd_timer(self) -> None:
        """Set up the OSD auto-hide timer."""
        self._osd_timer = QTimer(self)
        self._osd_timer.setSingleShot(True)
        self._osd_timer.timeout.connect(self._on_osd_timeout)

    def _on_osd_timeout(self) -> None:
        """Handle OSD timeout - fade out the OSD."""
        self._osd.fade_out()

    def _reset_osd_timer(self) -> None:
        """Reset the OSD auto-hide timer."""
        if self._osd_timer:
            self._osd_timer.stop()
            self._osd_timer.start(OSD_FADE_TIMEOUT_MS)

    def resizeEvent(self, event: Any) -> None:  # type: ignore[invalid-method-override]
        """Handle resize to reposition OSD overlays.

        Args:
            event: The resize event.
        """
        super().resizeEvent(event)
        self._position_overlays()

    def _position_overlays(self) -> None:
        """Position OSD overlays within the view."""
        # Position OSD at bottom center
        osd_width = min(scaled(400), self.width() - scaled(40))
        self._osd.setFixedWidth(osd_width)
        osd_x = (self.width() - osd_width) // 2
        osd_y = self.height() - self._osd.height() - scaled(40)
        self._osd.move(osd_x, osd_y)

        # Position audio track overlay at right side
        track_x = self.width() - self._audio_track_overlay.width() - scaled(20)
        track_y = (self.height() - self._audio_track_overlay.height()) // 2
        self._audio_track_overlay.move(track_x, track_y)

        subtitle_width = max(scaled(320), int(self.width() * 0.82))
        subtitle_height = scaled(112)
        subtitle_x = (self.width() - subtitle_width) // 2
        subtitle_y = max(scaled(20), self.height() - subtitle_height - scaled(96))
        self._subtitle_label.setGeometry(
            subtitle_x, subtitle_y, subtitle_width, subtitle_height
        )
        self._subtitle_label.raise_()
        self._osd.raise_()
        self._audio_track_overlay.raise_()

    def showEvent(self, event: Any) -> None:  # type: ignore[invalid-method-override]
        """Handle show event to emit view ready signal.

        Args:
            event: The show event.
        """
        super().showEvent(event)
        self._position_overlays()

        # Emit the video frame winId for VLC binding
        frame_id = int(self._video_frame.winId())
        self.view_ready.emit(frame_id)
        logger.debug("PlayerView shown, emitting frame ID: %d", frame_id)

    def get_video_frame_id(self) -> int:
        """Get the video frame window ID for VLC binding.

        Returns:
            The winId of the video frame widget.
        """
        return int(self._video_frame.winId())

    def show_pause_indicator(
        self, is_paused: bool, time_text: str | None = None
    ) -> None:
        """Show the pause/play OSD indicator.

        Args:
            is_paused: True to show paused state, False for playing.
            time_text: Optional playback time to show under the icon.
        """
        self._osd.show_pause(is_paused, time_text)
        self._reset_osd_timer()

    def show_seek_indicator(self, forward: bool, time_text: str | None = None) -> None:
        """Show the seek OSD indicator.

        Args:
            forward: True for forward seek, False for backward.
            time_text: Optional playback time to show under the icon.
        """
        self._osd.show_seek(forward, time_text)
        self._reset_osd_timer()

    def show_volume_indicator(self, level: int, is_muted: bool) -> None:
        """Show the volume OSD indicator.

        Args:
            level: Volume level 0-100.
            is_muted: True if audio is muted.
        """
        self._osd.show_volume(level, is_muted)
        self._reset_osd_timer()

    def show_audio_track_indicator(self, track_name: str) -> None:
        """Show the audio track OSD indicator.

        Args:
            track_name: Name of the current audio track.
        """
        self._osd.show_audio_track(track_name)
        self._reset_osd_timer()

    def show_subtitle_track_indicator(self, track_name: str) -> None:
        """Show the subtitle track OSD indicator.

        Args:
            track_name: Name of the current subtitle track.
        """
        self._osd.show_subtitle_track(track_name)
        self._reset_osd_timer()

    def set_subtitle_text(self, text: str) -> None:
        """Display subtitle text over the player.

        Args:
            text: Subtitle text to render. Empty text hides the overlay.
        """
        if not text:
            self.clear_subtitle_text()
            return

        self._subtitle_label.setText(text)
        self._subtitle_label.show()
        self._subtitle_label.raise_()

    def clear_subtitle_text(self) -> None:
        """Hide the subtitle text overlay."""
        self._subtitle_label.clear()
        self._subtitle_label.hide()

    def show_audio_track_overlay(self, tracks: list[dict[str, Any]]) -> None:
        """Show the audio track selection overlay.

        Args:
            tracks: List of available audio tracks.
        """
        self._audio_track_overlay.set_tracks(tracks)
        self._position_overlays()
        self._audio_track_overlay.show()

    def hide_audio_track_overlay(self) -> None:
        """Hide the audio track selection overlay."""
        self._audio_track_overlay.hide()

    def is_audio_track_overlay_visible(self) -> bool:
        """Check if audio track overlay is visible.

        Returns:
            True if overlay is visible, False otherwise.
        """
        return self._audio_track_overlay.isVisible()

    def hide_cursor(self) -> None:
        """Hide the mouse cursor for full-screen experience."""
        if not self._cursor_hidden:
            self.setCursor(QCursor(Qt.CursorShape.BlankCursor))
            self._cursor_hidden = True
            logger.debug("Mouse cursor hidden")

    def show_cursor(self) -> None:
        """Show the mouse cursor."""
        if self._cursor_hidden:
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
            self._cursor_hidden = False
            logger.debug("Mouse cursor shown")

    def enter_fullscreen(self) -> None:
        """Enter full-screen mode.

        Note: Actual fullscreen is managed by MainWindow.
        This method hides the cursor and prepares the view.
        """
        self.hide_cursor()
        logger.debug("PlayerView entering fullscreen mode")

    def exit_fullscreen(self) -> None:
        """Exit full-screen mode.

        Note: Actual fullscreen is managed by MainWindow.
        This method shows the cursor and cleans up.
        """
        self.show_cursor()
        self.hide_audio_track_overlay()
        self.clear_subtitle_text()
        if self._osd_timer:
            self._osd_timer.stop()
        self._osd.hide()
        logger.debug("PlayerView exiting fullscreen mode")

    def set_focus(self) -> None:
        """Set focus to the player view for keyboard input."""
        self.setFocus()

    def trigger_activity(self) -> None:
        """Trigger activity to reset OSD timer (e.g., on key press)."""
        self._reset_osd_timer()
