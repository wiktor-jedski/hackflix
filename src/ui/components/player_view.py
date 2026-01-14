"""Player view component for Hackflix.

This module provides the PlayerView widget for full-screen video playback
with On-Screen Display (OSD) controls.
"""

import logging
from typing import Any

from PyQt5.QtCore import QPropertyAnimation, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QCursor
from PyQt5.QtWidgets import (
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
    SURFACE_COLOR,
    TEXT_PRIMARY,
    TEXT_SECONDARY,
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

        layout = QHBoxLayout(self)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(32)

        # Create icon labels
        self._pause_icon = self._create_icon_label("pause_icon")
        self._seek_icon = self._create_icon_label("seek_icon")
        self._volume_icon = self._create_icon_label("volume_icon")
        self._audio_track_icon = self._create_icon_label("audio_track_icon")

        layout.addStretch()
        layout.addWidget(self._pause_icon)
        layout.addWidget(self._seek_icon)
        layout.addWidget(self._volume_icon)
        layout.addWidget(self._audio_track_icon)
        layout.addStretch()

        # Initially hide all icons
        self._pause_icon.hide()
        self._seek_icon.hide()
        self._volume_icon.hide()
        self._audio_track_icon.hide()

        self.setFixedHeight(80)
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
        label.setAlignment(Qt.AlignCenter)  # type: ignore[attr-defined]
        label.setStyleSheet(f"""
            QLabel {{
                color: {TEXT_PRIMARY};
                font-size: {FONT_SIZE_LARGE}px;
                min-width: 48px;
                min-height: 48px;
            }}
        """)
        return label

    def _setup_animation(self) -> None:
        """Set up the fade animation."""
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_effect)
        self._opacity_effect.setOpacity(1.0)

        self._fade_animation = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._fade_animation.setDuration(300)
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

    def show_pause(self, is_paused: bool) -> None:
        """Show pause/play indicator.

        Args:
            is_paused: True to show pause icon, False for play.
        """
        self._hide_all_icons()
        self._pause_icon.setText("⏸" if is_paused else "▶")
        self._pause_icon.show()
        self._show_osd()

    def show_seek(self, forward: bool) -> None:
        """Show seek indicator.

        Args:
            forward: True for forward seek, False for backward.
        """
        self._hide_all_icons()
        self._seek_icon.setText("⏩" if forward else "⏪")
        self._seek_icon.show()
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

    track_selected = pyqtSignal(int)  # Track ID

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
        self._layout.setContentsMargins(16, 16, 16, 16)
        self._layout.setSpacing(8)

        self._title_label = QLabel("Audio Tracks")
        self._title_label.setStyleSheet(f"""
            QLabel {{
                color: {TEXT_PRIMARY};
                font-size: 16px;
                font-weight: bold;
            }}
        """)
        self._layout.addWidget(self._title_label)

        self._tracks_container = QWidget()
        self._tracks_layout = QVBoxLayout(self._tracks_container)
        self._tracks_layout.setContentsMargins(0, 0, 0, 0)
        self._tracks_layout.setSpacing(4)
        self._layout.addWidget(self._tracks_container)

        self.setFixedWidth(300)
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
            if item.widget():
                item.widget().deleteLater()

        # Add new track labels
        for track in tracks:
            label = QLabel(track["name"])
            is_current = track.get("is_current", False)
            label.setStyleSheet(f"""
                QLabel {{
                    color: {TEXT_PRIMARY if is_current else TEXT_SECONDARY};
                    font-size: 14px;
                    padding: 8px;
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

    view_ready = pyqtSignal(int)  # Video frame winId

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
        self._video_frame.setMinimumSize(640, 480)
        layout.addWidget(self._video_frame)

        # OSD overlay (positioned at bottom center)
        self._osd = OSDWidget(self)

        # Audio track overlay (positioned at right)
        self._audio_track_overlay = AudioTrackOverlay(self)

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

    def resizeEvent(self, event: Any) -> None:
        """Handle resize to reposition OSD overlays.

        Args:
            event: The resize event.
        """
        super().resizeEvent(event)
        self._position_overlays()

    def _position_overlays(self) -> None:
        """Position OSD overlays within the view."""
        # Position OSD at bottom center
        osd_width = min(400, self.width() - 40)
        self._osd.setFixedWidth(osd_width)
        osd_x = (self.width() - osd_width) // 2
        osd_y = self.height() - self._osd.height() - 40
        self._osd.move(osd_x, osd_y)

        # Position audio track overlay at right side
        track_x = self.width() - self._audio_track_overlay.width() - 20
        track_y = (self.height() - self._audio_track_overlay.height()) // 2
        self._audio_track_overlay.move(track_x, track_y)

    def showEvent(self, event: Any) -> None:
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

    def show_pause_indicator(self, is_paused: bool) -> None:
        """Show the pause/play OSD indicator.

        Args:
            is_paused: True to show paused state, False for playing.
        """
        self._osd.show_pause(is_paused)
        self._reset_osd_timer()

    def show_seek_indicator(self, forward: bool) -> None:
        """Show the seek OSD indicator.

        Args:
            forward: True for forward seek, False for backward.
        """
        self._osd.show_seek(forward)
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
            self.setCursor(QCursor(Qt.BlankCursor))  # type: ignore[attr-defined]
            self._cursor_hidden = True
            logger.debug("Mouse cursor hidden")

    def show_cursor(self) -> None:
        """Show the mouse cursor."""
        if self._cursor_hidden:
            self.setCursor(QCursor(Qt.ArrowCursor))  # type: ignore[attr-defined]
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
