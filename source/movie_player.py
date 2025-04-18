# --- START OF FILE source/movie_player.py ---

"""
Main application module for the Raspberry Pi Movie Player App.
Integrates media playback with library management and other features.
"""

import sys
import os
import vlc
import threading # For download worker thread
import traceback # For detailed error printing

from PyQt5.QtGui import QCursor # Added QCursor
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout,
                           QHBoxLayout, QPushButton, QLabel,
                           QSlider, QStyle, QStackedWidget,
                           QTabWidget, QMessageBox, QApplication, QDesktopWidget) # Added QDesktopWidget
from PyQt5.QtCore import Qt, QTimer, pyqtSlot, QMetaObject, Q_ARG, pyqtSignal, QPoint, QEvent

# Import local modules
from source.video_frame import VideoFrame
from source.file_browser import FileBrowser
from source.downloads_tab import DownloadsTab
from source.placeholder_tabs import SuggestionsTab # Keep SuggestionsTab for now
from source.subtitle_manager import SubtitleManager # Import the new manager
from source.subtitle_dialog import SubtitleResultsDialog # Import the new dialog

# Constants
CURSOR_HIDE_TIMEOUT_MS = 3000 # Hide cursor after 3 seconds of inactivity

class MoviePlayerApp(QMainWindow):
    """
    Main application window for the Raspberry Pi Movie Player App.
    Integrates media playback with library management and other features.
    """

    def __init__(self):
        super().__init__()

        # --- Internal State ---
        self.current_search_video_path = None # Store path for subtitle context
        self.current_subtitle_to_download = None # Store selected subtitle dict
        self.pending_download_retry_info = None # Store {'file_id': id} for retry

        # Fullscreen state
        self.is_video_layout_fullscreen = False # Tracks if the video layout is active
        self.original_window_flags = self.windowFlags()
        self.mouse_pos_before_hide = None
        self.original_geometry_before_fs = None # Store geometry too

        # Get screen geometry reference
        self.screen_geometry = QApplication.desktop().screenGeometry() # Get primary screen geometry

        # Cursor state
        self.is_cursor_hidden = False

        # Set window properties
        self.setWindowTitle("Raspberry Pi Movie Player")
        self.setGeometry(100, 100, 1024, 768)
        self.setFocusPolicy(Qt.StrongFocus) # Allow the main window to receive key presses

        # Create VLC instance and media player
        self.instance = vlc.Instance()
        self.mediaplayer = self.instance.media_player_new()

        # --- Instantiate Managers ---
        self.subtitle_manager = SubtitleManager()
        if self.subtitle_manager.username and self.subtitle_manager.password:
            print("Attempting OpenSubtitles login...")
            self.subtitle_manager.login()

        # --- Cursor Hide Timer ---
        self.cursor_hide_timer = QTimer(self)
        self.cursor_hide_timer.setInterval(CURSOR_HIDE_TIMEOUT_MS)
        self.cursor_hide_timer.setSingleShot(True)
        self.cursor_hide_timer.timeout.connect(self.hide_cursor_on_inactivity)


        # --- Widgets and Layouts ---
        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)

        self.stacked_widget = QStackedWidget()

        # --- Player View (View 0 in Stack) ---
        self.player_widget = QWidget()
        self.player_layout = QVBoxLayout(self.player_widget)
        self.player_layout.setContentsMargins(0, 0, 0, 0)
        self.player_layout.setSpacing(0)

        self.video_frame = VideoFrame() # Instantiated here
        self.video_frame.doubleClicked.connect(self.toggle_video_fullscreen) # Connect signal
        self.video_frame.mouseMoved.connect(self.on_mouse_moved_over_video) # Connect cursor signal

        self.control_widget = QWidget() # Container for controls
        self.control_layout = QHBoxLayout(self.control_widget)
        self.control_layout.setContentsMargins(5, 5, 5, 5) # Add padding to controls

        self.play_button = QPushButton()
        self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.play_button.clicked.connect(self.play_pause)
        self.stop_button = QPushButton()
        self.stop_button.setIcon(self.style().standardIcon(QStyle.SP_MediaStop))
        self.stop_button.clicked.connect(self.stop)
        self.position_slider = QSlider(Qt.Horizontal)
        self.position_slider.setMaximum(1000)
        self.position_slider.sliderMoved.connect(self.set_position)
        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setStyleSheet("margin-left: 5px; margin-right: 5px;")
        self.back_button = QPushButton("Back to Library")
        self.back_button.clicked.connect(self.show_browser)

        self.control_layout.addWidget(self.play_button)
        self.control_layout.addWidget(self.stop_button)
        self.control_layout.addWidget(self.position_slider)
        self.control_layout.addWidget(self.time_label)
        self.control_layout.addStretch()
        self.control_layout.addWidget(self.back_button)

        self.player_layout.addWidget(self.video_frame, 1)
        self.player_layout.addWidget(self.control_widget)

        # --- Browser View (View 1 in Stack) ---
        self.browser_widget = QWidget()
        self.browser_layout = QVBoxLayout(self.browser_widget)
        self.tab_widget = QTabWidget()
        self.library_tab = FileBrowser()
        self.downloads_tab = DownloadsTab()
        self.suggestions_tab = SuggestionsTab()
        self.tab_widget.addTab(self.library_tab, "Library")
        self.tab_widget.addTab(self.downloads_tab, "Downloads")
        self.tab_widget.addTab(self.suggestions_tab, "Suggestions")
        self.browser_layout.addWidget(self.tab_widget)

        # --- Video Fullscreen View (View 2 in Stack) ---
        self.video_fullscreen_widget = QWidget()
        self.video_fullscreen_widget.setObjectName("VideoFullscreenContainer")
        self.video_fullscreen_layout = QVBoxLayout(self.video_fullscreen_widget)
        self.video_fullscreen_layout.setContentsMargins(0, 0, 0, 0)
        self.video_fullscreen_layout.setSpacing(0)

        # --- Add Views to Stacked Widget ---
        self.stacked_widget.addWidget(self.player_widget)           # Index 0
        self.stacked_widget.addWidget(self.browser_widget)          # Index 1
        self.stacked_widget.addWidget(self.video_fullscreen_widget) # Index 2

        self.main_layout.addWidget(self.stacked_widget)
        self.stacked_widget.setCurrentIndex(1) # Show browser by default

        # --- UI Timer ---
        self.timer = QTimer(self)
        self.timer.setInterval(100) # Update UI ~10 times/sec
        self.timer.timeout.connect(self.update_ui)

        # --- Playback State ---
        self.is_playing = False
        self.media = None

        # --- Connect Signals ---
        self.library_tab.file_selected.connect(self.play_file)
        self.library_tab.find_subtitles_requested.connect(self.on_find_subtitles_requested)
        self.subtitle_manager.search_results.connect(self.on_subtitle_search_results)
        self.subtitle_manager.search_error.connect(self.on_subtitle_search_error)
        self.subtitle_manager.download_ready.connect(self.on_subtitle_download_ready)
        self.subtitle_manager.download_error.connect(self.on_subtitle_download_error)
        self.subtitle_manager.login_status.connect(self.on_subtitle_login_status)
        self.subtitle_manager.quota_info.connect(self.on_subtitle_quota_info)


    # --- Cursor Handling Methods ---

    def hide_cursor_on_inactivity(self):
        """Slot called by timer to hide the cursor."""
        is_player_visible = self.stacked_widget.currentWidget() in [self.player_widget, self.video_fullscreen_widget]
        if not is_player_visible:
            self.cursor_hide_timer.stop()
            return

        if self.isActiveWindow() and not self.is_cursor_hidden:
            print(">>> Hiding cursor due to inactivity.")
            QApplication.setOverrideCursor(Qt.BlankCursor)
            self.is_cursor_hidden = True

    # Corrected show_cursor method signature
    def show_cursor(self, triggered_by_move=False):
        """Shows the cursor and manages the hide timer."""
        if not triggered_by_move:
             self.cursor_hide_timer.stop()

        if self.is_cursor_hidden:
            print(">>> Showing cursor.")
            QApplication.restoreOverrideCursor()
            self.is_cursor_hidden = False

        current_state = self.mediaplayer.get_state()
        is_playback_active = current_state in [vlc.State.Playing, vlc.State.Paused]
        if is_playback_active and not self.is_video_layout_fullscreen:
             self.cursor_hide_timer.start()


    @pyqtSlot()
    def on_mouse_moved_over_video(self):
        """Slot called when mouse moves over the VideoFrame."""
        if not self.is_video_layout_fullscreen:
            current_state = self.mediaplayer.get_state()
            if current_state in [vlc.State.Playing, vlc.State.Paused]:
                 self.show_cursor(triggered_by_move=True)


    # --- Fullscreen Toggling Methods ---

    def enter_video_fullscreen_layout(self):
        """Handles the transition TO video fullscreen layout."""
        if self.stacked_widget.currentWidget() is not self.player_widget:
            current_state = self.mediaplayer.get_state()
            if current_state in [vlc.State.Playing, vlc.State.Paused]:
                print("Switching to player view before entering fullscreen...")
                self.stacked_widget.setCurrentWidget(self.player_widget)
                QTimer.singleShot(50, self.enter_video_fullscreen_layout)
                return
            else:
                print("Cannot enter video fullscreen from current view if not playing.")
                return

        print("Entering Video Fullscreen Layout")
        self.original_geometry_before_fs = self.geometry()
        self.mouse_pos_before_hide = QCursor.pos()

        self.cursor_hide_timer.stop()
        if not self.is_cursor_hidden:
             QApplication.setOverrideCursor(Qt.BlankCursor)
             self.is_cursor_hidden = True

        print("  Making App Window Fullscreen (Standard).")
        self.showFullScreen()
        QTimer.singleShot(50, self._adjust_fullscreen_geometry)

        self.previous_widget_before_video_fs = self.player_widget
        self.control_widget.hide()
        self.player_layout.removeWidget(self.video_frame)
        self.video_fullscreen_layout.addWidget(self.video_frame)
        self.stacked_widget.setCurrentWidget(self.video_fullscreen_widget)
        self.is_video_layout_fullscreen = True

        QTimer.singleShot(100, lambda: self._set_vlc_window(self.video_frame.winId()))

    def _adjust_fullscreen_geometry(self):
        """Attempt to force geometry over decorations after showFullScreen."""
        if self.isFullScreen() and self.is_video_layout_fullscreen:
             print(f"  Adjusting geometry to screen: {self.screen_geometry}")
             self.setGeometry(self.screen_geometry)
             self.activateWindow()
             self.raise_()
             self.update()

    def exit_video_fullscreen_layout(self):
        """Handles the transition FROM video fullscreen layout."""
        if not self.is_video_layout_fullscreen: return
        print("Exiting Video Fullscreen Layout")

        # --- Corrected call to show_cursor ---
        self.show_cursor() # REMOVED force_stop_timer=True argument
        # --- End Correction ---

        if self.mouse_pos_before_hide:
            QCursor.setPos(self.mouse_pos_before_hide)
            self.mouse_pos_before_hide = None

        print("  Restoring App Window to Normal State.")
        self.setWindowFlags(self.original_window_flags)
        self.showNormal()
        if self.original_geometry_before_fs:
             print(f"  Restoring original geometry: {self.original_geometry_before_fs}")
             self.setGeometry(self.original_geometry_before_fs)
             self.original_geometry_before_fs = None
        self.show()

        if self.previous_widget_before_video_fs:
            self.video_fullscreen_layout.removeWidget(self.video_frame)
            self.player_layout.insertWidget(0, self.video_frame, 1)
            self.stacked_widget.setCurrentWidget(self.previous_widget_before_video_fs)
            self.control_widget.show()
        else:
            self.stacked_widget.setCurrentWidget(self.player_widget)
            self.control_widget.show()

        self.is_video_layout_fullscreen = False
        self.previous_widget_before_video_fs = None

        QTimer.singleShot(50, lambda: self._set_vlc_window(self.video_frame.winId()))

        if self.mediaplayer.get_state() == vlc.State.Playing:
             self.cursor_hide_timer.start()

    def toggle_video_fullscreen(self):
        """Toggles the video layout fullscreen state."""
        current_state = self.mediaplayer.get_state()
        can_toggle = current_state in [vlc.State.Playing, vlc.State.Paused, vlc.State.Opening, vlc.State.Buffering]

        if not can_toggle:
             print("Cannot toggle video fullscreen: No media playing or paused.")
             return

        if self.is_video_layout_fullscreen:
            self.exit_video_fullscreen_layout()
        else:
            self.enter_video_fullscreen_layout()

    def _set_vlc_window(self, win_id_obj):
        """Helper function to set the VLC output window, ensuring integer ID."""
        try:
            win_id = int(win_id_obj)
            print(f"Setting VLC output window to ID: {win_id} (converted from {win_id_obj})")
        except (TypeError, ValueError) as e:
             print(f"Error converting winId ({win_id_obj}) to integer: {e}")
             QMessageBox.warning(self, "VLC Error", f"Could not get valid window ID for video output.")
             return
        try:
            if sys.platform.startswith('linux'):
                self.mediaplayer.set_xwindow(win_id)
            elif sys.platform == "win32":
                self.mediaplayer.set_hwnd(win_id)
            elif sys.platform == "darwin":
                self.mediaplayer.set_nsobject(win_id)
        except Exception as e:
            print(f"Error setting VLC window with ID {win_id}: {e}")
            err_msg = f"Could not attach video output:\n{e}"
            if isinstance(e, TypeError):
                 err_msg = f"VLC reported a type error setting the window ID.\nEnsure VLC and Qt versions are compatible."
            QMessageBox.warning(self, "VLC Error", err_msg)


    # --- Event Handling ---
    def keyPressEvent(self, event):
        """Handle key presses for fullscreen toggles."""
        key = event.key()
        if key == Qt.Key_F11:
            print("F11 Pressed")
            if self.is_video_layout_fullscreen:
                 print("  Video layout active. Exiting it first.")
                 self.exit_video_fullscreen_layout() # Puts app in normal mode
                 # QTimer.singleShot(100, self._toggle_app_fullscreen_decorated) # Optional
            else:
                 self._toggle_app_fullscreen_decorated()
            event.accept()
        elif key == Qt.Key_Escape:
            if self.is_video_layout_fullscreen:
                print("Escape pressed: Exiting Video Fullscreen Layout")
                self.exit_video_fullscreen_layout() # Puts app in normal mode
                event.accept()
            else:
                 super().keyPressEvent(event)
        elif key == Qt.Key_Space:
             current_view = self.stacked_widget.currentWidget()
             if current_view is self.player_widget or current_view is self.video_fullscreen_widget:
                 self.play_pause()
                 event.accept()
        else:
            current_view = self.stacked_widget.currentWidget()
            if current_view is self.player_widget or current_view is self.video_fullscreen_widget:
                 self.show_cursor() # Show cursor on any other keypress during playback
            super().keyPressEvent(event)

    def _toggle_app_fullscreen_decorated(self):
        """Toggles app fullscreen WITH standard decorations."""
        if self.windowFlags() & Qt.FramelessWindowHint:
            print("  Restoring standard window flags.")
            self.setWindowFlags(self.original_window_flags)
        if self.isFullScreen():
            self.showNormal()
            print("  Exiting App Fullscreen (Decorated)")
            if self.original_geometry_before_fs:
                 print(f"  Restoring original geometry: {self.original_geometry_before_fs}")
                 self.setGeometry(self.original_geometry_before_fs)
                 self.original_geometry_before_fs = None
        else:
            self.original_geometry_before_fs = self.geometry()
            self.showFullScreen()
            print("  Entering App Fullscreen (Decorated)")
        self.show()

    # --- Playback Methods ---

    def show_browser(self):
        """Switch back to browser view, ensuring exit from video fullscreen."""
        if self.is_video_layout_fullscreen:
             print("show_browser: Exiting video layout first.")
             self.exit_video_fullscreen_layout()
        self.stop()
        self.stacked_widget.setCurrentWidget(self.browser_widget)
        self.setWindowTitle("Raspberry Pi Movie Player")

    def play_file(self, filepath):
        """Play a media file and switch to the player view"""
        print(f"Play_file called with: {filepath}")
        if self.is_video_layout_fullscreen:
             print("play_file: Exiting video layout first.")
             self.exit_video_fullscreen_layout()

        if filepath and os.path.isfile(filepath):
            try:
                if self.video_frame.parentWidget() is not self.player_widget:
                     print("play_file: Reparenting video frame.")
                     parent_widget = self.video_frame.parentWidget()
                     if parent_widget:
                          parent_layout = parent_widget.layout()
                          if parent_layout:
                              parent_layout.removeWidget(self.video_frame)
                     self.player_layout.insertWidget(0, self.video_frame, 1)

                current_state = self.mediaplayer.get_state()
                if current_state in [vlc.State.Playing, vlc.State.Paused]:
                     print("play_file: Stopping previous media.")
                     self.stop()
                     QTimer.singleShot(100, lambda: self._play_file_continue(filepath))
                else:
                     self._play_file_continue(filepath)

            except Exception as e:
                 self.show_cursor()
                 QMessageBox.critical(self, "Playback Error", f"Failed to initiate playback for '{os.path.basename(filepath)}':\n{str(e)}")
                 traceback.print_exc()
                 self.show_browser()
        elif filepath:
             QMessageBox.warning(self, "File Not Found", f"The selected file could not be found:\n{filepath}")
        else:
             print("Play file called with empty path.")

    def _play_file_continue(self, filepath):
         """Continues the play_file logic after potential stop/delay."""
         try:
              print(f"_play_file_continue: Loading media: {filepath}")
              self.media = self.instance.media_new(filepath)
              if not self.media:
                   raise RuntimeError("Failed to create VLC media object.")

              self.mediaplayer.set_media(self.media)
              # self.media.parse() # Optional

              win_id = self.video_frame.winId()
              if not win_id:
                   print("Window ID not immediately available, delaying VLC window set.")
                   QTimer.singleShot(200, lambda: self._set_vlc_window_and_play(win_id))
              else:
                  self._set_vlc_window_and_play(win_id)

         except Exception as e:
              self.show_cursor()
              QMessageBox.critical(self, "Playback Error", f"Failed to load media '{os.path.basename(filepath)}':\n{str(e)}")
              traceback.print_exc()
              self.show_browser()

    def _set_vlc_window_and_play(self, win_id_obj):
         """Sets the VLC window and starts playback."""
         try:
             current_win_id = win_id_obj or self.video_frame.winId()
             if not current_win_id:
                  raise RuntimeError("VideoFrame still has no valid Window ID after delay.")

             print("_set_vlc_window_and_play: Setting window and playing.")
             self._set_vlc_window(current_win_id)

             self.stacked_widget.setCurrentWidget(self.player_widget)
             self.control_widget.show()

             play_result = self.mediaplayer.play()
             if play_result == -1:
                  raise RuntimeError("VLC mediaplayer.play() returned error (-1).")
             print("Playback initiated via play().")

             QTimer.singleShot(150, self._post_play_start_actions)

         except Exception as e:
              self.show_cursor()
              filepath = self.media.get_mrl() if self.media else "Unknown"
              QMessageBox.critical(self, "Playback Error", f"Failed to start playback for '{os.path.basename(filepath)}':\n{str(e)}")
              traceback.print_exc()
              self.show_browser()


    def _post_play_start_actions(self):
         """Actions to perform slightly after play() is called."""
         current_state = self.mediaplayer.get_state()
         print(f"_post_play_start_actions: Current state = {current_state}")
         self._update_play_button_icon()
         if current_state in [vlc.State.Playing, vlc.State.Paused]:
              self.is_playing = self.mediaplayer.is_playing()
              if not self.timer.isActive(): self.timer.start() # Start UI timer only if not active
              if not self.is_video_layout_fullscreen and self.is_playing:
                   print("  Starting cursor hide timer on play start.")
                   # Use timer to hide slightly after start
                   self.cursor_hide_timer.start()
              elif not self.is_playing: # Paused state
                   self.show_cursor()
         else:
              print(f"Warning: Playback state unexpected after play(). State: {current_state}. Stopping UI updates.")
              self.stop()


    def _update_play_button_icon(self):
        """Helper to update icon based on actual player state."""
        if self.mediaplayer.is_playing():
            self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
        else:
            self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))

    def play_pause(self):
        """Toggle play/pause status"""
        if self.mediaplayer.is_playing():
            print("Pausing playback.")
            self.mediaplayer.pause()
            self.is_playing = False
            self.show_cursor()
        else:
            if self.mediaplayer.get_media():
                print("Resuming/Starting playback.")
                play_result = self.mediaplayer.play()
                if play_result == -1:
                     QMessageBox.warning(self, "Playback Error", "Failed to resume/start playback.")
                     return
                self.is_playing = True
                if not self.timer.isActive(): self.timer.start()
                if not self.is_video_layout_fullscreen:
                    self.cursor_hide_timer.start()
            else:
                 print("Play/Pause called but no media loaded.")
        self._update_play_button_icon()


    def stop(self):
        """Stop player"""
        print("Stop called.")
        media_exists = self.mediaplayer.get_media() is not None
        if media_exists:
             self.mediaplayer.stop()
        self._update_play_button_icon()
        self.is_playing = False
        if self.timer.isActive(): self.timer.stop()
        self.time_label.setText("00:00 / 00:00")
        self.position_slider.setValue(0)
        self.show_cursor(triggered_by_move=False) # Pass explicit False here


    def update_ui(self):
        """Update the UI with current playback status"""
        if not self.timer.isActive(): return

        current_state = self.mediaplayer.get_state()

        if current_state in [vlc.State.Playing, vlc.State.Paused]:
            media_length = self.mediaplayer.get_length()
            if media_length > 0:
                media_pos = self.mediaplayer.get_position()
                current_msecs = self.mediaplayer.get_time()
                if media_pos >= 0.0 and media_pos <= 1.01 and current_msecs >= 0:
                     if not self.position_slider.isSliderDown():
                          self.position_slider.setValue(int(media_pos * 1000))
                     current_secs = current_msecs // 1000
                     total_secs = media_length // 1000
                     current_time_str = f"{current_secs // 60:02d}:{current_secs % 60:02d}"
                     total_time_str = f"{total_secs // 60:02d}:{total_secs % 60:02d}"
                     self.time_label.setText(f"{current_time_str} / {total_time_str}")
            else:
                if self.time_label.text() != "00:00 / --:--":
                     self.time_label.setText("00:00 / --:--")
                if not self.position_slider.isSliderDown():
                     self.position_slider.setValue(0)
        elif current_state == vlc.State.Ended:
             print("Playback ended, stopping UI updates.")
             self.stop()
        elif current_state == vlc.State.Error:
             print("VLC Error state detected, stopping UI updates.")
             QMessageBox.warning(self, "Playback Error", "An error occurred during playback.")
             self.show_browser()
        elif current_state == vlc.State.Stopped:
             if self.is_playing or self.timer.isActive():
                  print("VLC Stopped state detected, stopping UI updates.")
                  self.stop()

    def set_position(self, position):
        """Set the player position according to the slider value"""
        if self.mediaplayer.is_seekable():
            self.mediaplayer.set_position(position / 1000.0)
            self.show_cursor() # Show cursor briefly when user seeks
        else:
            print("Media is not seekable.")

    # --- Subtitle Handling Slots ---
    @pyqtSlot(str)
    def on_find_subtitles_requested(self, video_path):
        if not video_path: return
        self.current_search_video_path = video_path
        filename = os.path.basename(video_path)
        query = os.path.splitext(filename)[0]
        imdb_id = None
        languages = "en,pl"
        print(f"Searching subtitles for '{query}' (Languages: {languages})")
        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.subtitle_manager.search_subtitles(query=query, imdb_id=imdb_id, languages=languages)

    @pyqtSlot(list)
    def on_subtitle_search_results(self, results):
        QApplication.restoreOverrideCursor()
        print(f"Received {len(results)} subtitle results.")
        if not self.current_search_video_path:
             print("Warning: Received subtitle results but no video path context.")
             QMessageBox.warning(self, "Subtitle Search", "Search results received, but the original video context was lost.")
             return
        if not results:
            QMessageBox.information(self, "Subtitle Search", f"No subtitles found for '{os.path.basename(self.current_search_video_path)}'.")
            self.current_search_video_path = None
            return
        dialog = SubtitleResultsDialog(results, self)
        dialog.subtitle_selected_for_download.connect(self.on_subtitle_selected)
        dialog.exec_()

    @pyqtSlot(str)
    def on_subtitle_search_error(self, error_message):
        QApplication.restoreOverrideCursor()
        QMessageBox.critical(self, "Subtitle Search Error", f"Failed to search for subtitles:\n{error_message}")
        self.current_search_video_path = None

    @pyqtSlot(dict)
    def on_subtitle_selected(self, subtitle_dict):
        if not self.current_search_video_path:
            print("Warning: Subtitle selected but no video path context.")
            QMessageBox.warning(self, "Subtitle Download", "Subtitle selected, but the original video context was lost.")
            return
        file_id = subtitle_dict.get('file_id')
        if not file_id:
             QMessageBox.critical(self, "Subtitle Download Error", "Selected subtitle has no File ID.")
             self.current_search_video_path = None
             return
        print(f"Requesting download for File ID: {file_id}")
        self.current_subtitle_to_download = subtitle_dict
        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.subtitle_manager.request_download(file_id)

    @pyqtSlot(str, str)
    def on_subtitle_download_ready(self, download_link, suggested_filename):
        QApplication.restoreOverrideCursor()
        print("Subtitle download link received.")
        if not self.current_search_video_path or not self.current_subtitle_to_download:
             print("Warning: Download ready but context missing.")
             QMessageBox.warning(self, "Subtitle Download", "Download link received, but context was lost. Cannot save file.")
             self.current_search_video_path = None
             self.current_subtitle_to_download = None
             return
        try:
            video_dir = os.path.dirname(self.current_search_video_path)
            video_base = os.path.splitext(os.path.basename(self.current_search_video_path))[0]
            language_code = self.current_subtitle_to_download.get('language', 'und')
            srt_filename = f"{video_base}.{language_code}.srt"
            save_path = os.path.join(video_dir, srt_filename)
            print(f"Attempting to download subtitle to: {save_path}")
            threading.Thread(target=self._download_subtitle_worker, args=(download_link, save_path), daemon=True).start()
        except Exception as e:
            QMessageBox.critical(self, "Subtitle Download Error", f"Error determining save path:\n{e}")
            traceback.print_exc()
            self.current_search_video_path = None
            self.current_subtitle_to_download = None

    def _download_subtitle_worker(self, link, path):
        success, error = self.subtitle_manager.download_subtitle_file(link, path)
        QMetaObject.invokeMethod(self, "on_actual_download_finished", Qt.QueuedConnection,
                                 Q_ARG(bool, success), Q_ARG(str, path if success else ""), Q_ARG(str, error or ""))

    @pyqtSlot(bool, str, str)
    def on_actual_download_finished(self, success, save_path, error_message):
        QApplication.restoreOverrideCursor()
        if success:
            QMessageBox.information(self, "Subtitle Downloaded", f"Subtitle saved successfully:\n{save_path}")
            self.library_tab.refresh_files()
        else:
            QMessageBox.warning(self, "Subtitle Download Failed", f"Failed to download subtitle file:\n{error_message}")
        self.current_search_video_path = None
        self.current_subtitle_to_download = None

    @pyqtSlot(dict)
    def on_subtitle_download_error(self, error_details): # Changed parameter name
        QApplication.restoreOverrideCursor()
        error_status = error_details.get('status', -1) # Use the dict directly
        error_msg_text = error_details.get('message', 'Unknown download error')
        can_relogin = (self.subtitle_manager.username and self.subtitle_manager.password)

        if error_status == 401 and can_relogin and self.current_subtitle_to_download:
            file_id_to_retry = self.current_subtitle_to_download.get('file_id')
            if file_id_to_retry and self.pending_download_retry_info is None:
                print(f"Download failed (401 Unauthorized). Attempting re-login for file_id {file_id_to_retry}...")
                self.pending_download_retry_info = {'file_id': file_id_to_retry}
                msgBox = QMessageBox(self); msgBox.setWindowTitle("Re-Login Required")
                msgBox.setText("Login session expired.\nAttempting re-login..."); msgBox.setIcon(QMessageBox.Information)
                msgBox.setStandardButtons(QMessageBox.NoButton); msgBox.show()
                QTimer.singleShot(100, msgBox.accept)
                QApplication.setOverrideCursor(Qt.WaitCursor)
                self.subtitle_manager.login()
                return
            elif self.pending_download_retry_info:
                 print("Download failed (401) but a retry is already pending. Ignoring.")
                 return

        print(f"Subtitle download request failed (Status: {error_status}). Error: {error_msg_text}")
        QMessageBox.critical(self, "Subtitle Download Error", f"Failed to prepare subtitle download (Status: {error_status}):\n{error_msg_text}")
        if not self.pending_download_retry_info:
             self.current_search_video_path = None
             self.current_subtitle_to_download = None

    @pyqtSlot(bool, str)
    def on_subtitle_login_status(self, success, message):
        QApplication.restoreOverrideCursor()
        print(f"Subtitle Login Status Update: {success} - {message}")
        if success and self.pending_download_retry_info:
            file_id_to_retry = self.pending_download_retry_info.get('file_id')
            print(f"Re-login successful. Retrying download request for file_id: {file_id_to_retry}")
            self.pending_download_retry_info = None
            if file_id_to_retry:
                msgBox = QMessageBox(self); msgBox.setWindowTitle("Re-Login Successful")
                msgBox.setText("Login successful.\nRetrying subtitle download..."); msgBox.setIcon(QMessageBox.Information)
                msgBox.setStandardButtons(QMessageBox.NoButton); msgBox.show()
                QTimer.singleShot(100, msgBox.accept)
                QApplication.setOverrideCursor(Qt.WaitCursor)
                self.subtitle_manager.request_download(file_id_to_retry)
            else:
                 print("Error: Pending retry info was invalid.")
                 self.current_search_video_path = None; self.current_subtitle_to_download = None
        elif not success and self.pending_download_retry_info:
            print("Re-login attempt failed. Cannot retry download.")
            QMessageBox.critical(self, "Re-Login Failed", f"Automatic re-login failed:\n{message}\n\nCannot download subtitle.")
            self.pending_download_retry_info = None
            self.current_search_video_path = None; self.current_subtitle_to_download = None

    @pyqtSlot(int, int)
    def on_subtitle_quota_info(self, remaining, limit):
        print(f"Subtitle Quota Update: {remaining}/{limit} remaining.")

    # --- Close Event ---
    def closeEvent(self, event):
        """Ensure clean shutdown."""
        print("Closing application...")
        self.stop()
        if hasattr(self.downloads_tab, 'downloader') and hasattr(self.downloads_tab.downloader, 'shutdown'):
            print("Shutting down torrent manager...")
            self.downloads_tab.downloader.shutdown()
        if hasattr(self, 'subtitle_manager') and self.subtitle_manager.logged_in:
            print("Logging out from OpenSubtitles...")
            self.subtitle_manager.logout()
            QTimer.singleShot(500, event.accept); event.ignore()
        else:
            event.accept()

# --- END OF FILE source/movie_player.py ---