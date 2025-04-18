# --- START OF FILE movie_player.py ---

"""
Main application module for the Raspberry Pi Movie Player App.
Integrates media playback with library management and other features.
"""

import sys
import os
import vlc
import threading # For download worker thread
import traceback # For detailed error printing

from PyQt5.QtGui import QCursor
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout,
                           QHBoxLayout, QPushButton, QLabel,
                           QSlider, QStyle, QStackedWidget,
                           QTabWidget, QMessageBox, QApplication, QDesktopWidget)
from PyQt5.QtCore import Qt, QTimer, pyqtSlot, QMetaObject, Q_ARG, pyqtSignal, QPoint, QEvent

# Import local modules
from source.video_frame import VideoFrame
from source.file_browser import FileBrowser
from source.downloads_tab import DownloadsTab
from source.placeholder_tabs import SuggestionsTab # Keep SuggestionsTab for now
from source.subtitle_manager import SubtitleManager, OPENSUBTITLES_USERNAME  # Import the new manager
from source.subtitle_dialog import SubtitleResultsDialog # Import the new dialog

class MoviePlayerApp(QMainWindow):
    """
    Main application window for the Raspberry Pi Movie Player App.
    Integrates media playback with library management and other features.
    """

    def __init__(self):
        super().__init__()

        # --- Internal State ---
        self.previous_widget_before_video_fs = None
        self.current_search_video_path = None # Store path for subtitle context
        self.current_subtitle_to_download = None # Store selected subtitle dict
        self.pending_download_retry_info = None # Store {'file_id': id} for retry

        # Fullscreen state flags
        self.is_video_layout_fullscreen = False
        self.original_window_flags = self.windowFlags()
        self.mouse_pos_before_hide = None
        self.original_geometry_before_fs = None # Store geometry too

        # Get screen geometry reference
        self.screen_geometry = QApplication.desktop().screenGeometry() # Get primary screen geometry

        # Set window properties
        self.setWindowTitle("Raspberry Pi Movie Player")
        self.setGeometry(100, 100, 1024, 768)
        # Allow the main window to receive key presses
        self.setFocusPolicy(Qt.StrongFocus)

        # Create VLC instance and media player
        self.instance = vlc.Instance()
        self.mediaplayer = self.instance.media_player_new()

        # --- Instantiate Managers ---
        self.subtitle_manager = SubtitleManager()
        # Optional: Auto-login if credentials configured
        if self.subtitle_manager.username and self.subtitle_manager.password:
            print("Attempting OpenSubtitles login...")
            self.subtitle_manager.login()

        # Create a central widget and main layout
        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)

        # Create a stacked widget to switch between player and browser views
        self.stacked_widget = QStackedWidget()

        # Create the player view (Code unchanged)
        self.player_widget = QWidget()
        self.player_layout = QVBoxLayout(self.player_widget)
        self.video_frame = VideoFrame()
        self.video_frame.doubleClicked.connect(self.toggle_video_fullscreen)  # Connect signal
        self.control_widget = QWidget()
        self.control_layout = QHBoxLayout(self.control_widget)
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
        self.back_button = QPushButton("Back to Library")
        self.back_button.clicked.connect(self.show_browser)
        self.control_layout.addWidget(self.play_button)
        self.control_layout.addWidget(self.stop_button)
        self.control_layout.addWidget(self.position_slider)
        self.control_layout.addWidget(self.time_label)
        self.control_layout.addWidget(self.back_button)
        self.player_layout.addWidget(self.video_frame, 1)
        self.player_layout.addWidget(self.control_widget)


        # Create the browser view with tabs
        self.browser_widget = QWidget()
        self.browser_layout = QVBoxLayout(self.browser_widget)

        # Create tab widget
        self.tab_widget = QTabWidget()

        # Create tabs
        self.library_tab = FileBrowser() # Don't pass manager here, connect signals below
        self.downloads_tab = DownloadsTab()
        # self.subtitles_tab = SubtitlesTab() # REMOVED
        self.suggestions_tab = SuggestionsTab()

        # Add tabs to the tab widget
        self.tab_widget.addTab(self.library_tab, "Library")
        self.tab_widget.addTab(self.downloads_tab, "Downloads")
        self.tab_widget.addTab(self.suggestions_tab, "Suggestions")

        # Add tab widget to browser layout
        self.browser_layout.addWidget(self.tab_widget)

        # --- Video Fullscreen View (View 2 in Stack) ---
        self.video_fullscreen_widget = QWidget()
        # Use a basic layout that allows the video frame to expand fully
        self.video_fullscreen_layout = QVBoxLayout(self.video_fullscreen_widget)
        self.video_fullscreen_layout.setContentsMargins(0, 0, 0, 0) # No margins
        # self.video_frame will be *moved* here when fullscreen is active

        # Add widgets to stacked widget
        self.stacked_widget.addWidget(self.player_widget)
        self.stacked_widget.addWidget(self.browser_widget)
        self.stacked_widget.addWidget(self.video_fullscreen_widget)  # Index 2

        # Add stacked widget to main layout
        self.main_layout.addWidget(self.stacked_widget)

        # Show the browser view by default
        self.stacked_widget.setCurrentWidget(self.browser_widget)

        # Set up the timer for updating the UI
        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.update_ui)

        # Initialize playback state
        self.is_playing = False
        self.media = None

        # --- Connect Signals ---
        # Player/Browser related
        self.library_tab.file_selected.connect(self.play_file)
        self.library_tab.find_subtitles_requested.connect(self.on_find_subtitles_requested) # Connect new signal

        # Subtitle Manager related
        self.subtitle_manager.search_results.connect(self.on_subtitle_search_results)
        self.subtitle_manager.search_error.connect(self.on_subtitle_search_error)
        self.subtitle_manager.download_ready.connect(self.on_subtitle_download_ready)
        self.subtitle_manager.download_error.connect(self.on_subtitle_download_error)
        # Optional: Connect login status or quota signals if needed for UI feedback
        self.subtitle_manager.login_status.connect(self.on_subtitle_login_status)
        self.subtitle_manager.quota_info.connect(self.on_subtitle_quota_info)

    # --- Fullscreen Toggling Methods ---

    def enter_video_fullscreen_layout(self):
        """Handles the transition TO video fullscreen layout."""
        # ... (Check if in player view) ...
        if self.stacked_widget.currentWidget() is not self.player_widget:
             # ... (Switch to player view logic) ...
             return

        print("Entering Video Fullscreen Layout")

        # Store original geometry and flags BEFORE changing anything
        self.original_geometry_before_fs = self.geometry()
        # Using original flags here, NO FramelessWindowHint yet
        # self.setWindowFlags(self.original_window_flags) # Ensure standard flags

        # Store mouse pos and hide cursor
        self.mouse_pos_before_hide = QCursor.pos()
        QApplication.setOverrideCursor(Qt.BlankCursor)

        # --- Go Fullscreen FIRST ---
        print("  Making App Window Fullscreen (Standard).")
        self.showFullScreen()
        # Give it a moment to potentially settle
        QTimer.singleShot(50, self._adjust_fullscreen_geometry)

        # --- Continue with layout switching ---
        self.previous_widget_before_video_fs = self.player_widget
        self.control_widget.hide()
        self.player_layout.removeWidget(self.video_frame)
        self.video_fullscreen_layout.addWidget(self.video_frame)
        self.stacked_widget.setCurrentWidget(self.video_fullscreen_widget)
        self.is_video_layout_fullscreen = True

        # Set VLC window ID - Delay slightly more after geometry adjustment attempt
        QTimer.singleShot(100, lambda: self._set_vlc_window(self.video_frame.winId()))

    def _adjust_fullscreen_geometry(self):
        """Attempt to force geometry over decorations after showFullScreen."""
        if self.isFullScreen(): # Only if still fullscreen
             print(f"  Adjusting geometry to screen: {self.screen_geometry}")
             self.setGeometry(self.screen_geometry)
             self.activateWindow() # Try bringing it to the front
             self.raise_()        # Try raising it above others
             # Forcing an update might help sometimes
             self.update()

    def exit_video_fullscreen_layout(self):
        """Handles the transition FROM video fullscreen layout."""
        if not self.is_video_layout_fullscreen:
            return

        print("Exiting Video Fullscreen Layout")

        # Restore cursor and mouse position first
        QApplication.restoreOverrideCursor()
        if self.mouse_pos_before_hide:
            QCursor.setPos(self.mouse_pos_before_hide)
            self.mouse_pos_before_hide = None

        # --- Restore App Window State to NORMAL ---
        print("  Restoring App Window to Normal State.")
        # Restore flags first (removes potential Frameless hint if added elsewhere)
        self.setWindowFlags(self.original_window_flags)
        self.showNormal() # Go back to normal windowed mode

        # Restore original geometry if stored
        if self.original_geometry_before_fs:
             print(f"  Restoring original geometry: {self.original_geometry_before_fs}")
             self.setGeometry(self.original_geometry_before_fs)
             self.original_geometry_before_fs = None # Clear stored geometry

        self.show() # Ensure visibility
        # --- End App Restore ---

        # Reparent video frame
        if self.previous_widget_before_video_fs:
            self.video_fullscreen_layout.removeWidget(self.video_frame)
            self.player_layout.insertWidget(0, self.video_frame, 1)

            # Switch back stacked widget view
            self.stacked_widget.setCurrentWidget(self.previous_widget_before_video_fs)
            self.control_widget.show()
        else:
            self.stacked_widget.setCurrentWidget(self.player_widget)
            self.control_widget.show()

        self.is_video_layout_fullscreen = False
        self.previous_widget_before_video_fs = None

        # Set VLC window ID after layout settles
        QTimer.singleShot(50, lambda: self._set_vlc_window(self.video_frame.winId()))

    # Simplified toggle method
    def toggle_video_fullscreen(self):
        """Toggles the video layout fullscreen state."""
        if not self.mediaplayer.get_media():
            print("Cannot toggle video fullscreen: No media loaded.")
            return

        if self.is_video_layout_fullscreen:
            self.exit_video_fullscreen_layout()
        else:
            self.enter_video_fullscreen_layout()


    def _set_vlc_window(self, win_id_obj):
        """Helper function to set the VLC output window, ensuring integer ID."""
        # --- Convert winId object to integer ---
        try:
            # winId() can return different types, ensure it's an int
            win_id = int(win_id_obj)
            print(f"Setting VLC output window to ID: {win_id} (converted from {win_id_obj})")
        except (TypeError, ValueError) as e:
             print(f"Error converting winId ({win_id_obj}) to integer: {e}")
             QMessageBox.warning(self, "VLC Error", f"Could not get valid window ID for video output.")
             return # Cannot proceed without a valid integer ID
        # --- End Conversion ---

        try:
            if sys.platform.startswith('linux'):
                self.mediaplayer.set_xwindow(win_id) # Pass integer ID
            elif sys.platform == "win32":
                self.mediaplayer.set_hwnd(win_id) # Pass integer ID
            elif sys.platform == "darwin":
                # Casting to int should also work for the nsobject method on macOS
                self.mediaplayer.set_nsobject(win_id) # Pass integer ID
            # No need for the complex QMacCocoaViewContainer workaround for now

        except Exception as e:
            print(f"Error setting VLC window with ID {win_id}: {e}")
            # Display a more specific error if possible
            if isinstance(e, TypeError):
                 err_msg = f"VLC reported a type error setting the window ID.\nEnsure VLC and Qt versions are compatible."
            else:
                 err_msg = f"Could not attach video output:\n{e}"
            QMessageBox.warning(self, "VLC Error", err_msg)

    # --- Event Handling ---
    def keyPressEvent(self, event):
        """Handle key presses for fullscreen toggles."""
        key = event.key()

        if key == Qt.Key_F11:
            # F11 toggles the main window fullscreen state WITH decorations
            print("F11 Pressed")
            if self.is_video_layout_fullscreen:
                 # If video layout is active, F11 should exit it first
                 print("  Video layout active. Exiting it first.")
                 self.exit_video_fullscreen_layout() # Puts app in normal mode
                 # Optionally trigger decorated fullscreen after exit:
                 # QTimer.singleShot(100, self._toggle_app_fullscreen_decorated)
            else:
                 self._toggle_app_fullscreen_decorated()
            event.accept()

        elif key == Qt.Key_Escape:
            # Escape *only* exits the internal video fullscreen layout
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
            super().keyPressEvent(event)

    def _toggle_app_fullscreen_decorated(self):
        """Toggles app fullscreen WITH standard decorations."""
        # Ensure standard flags
        if self.windowFlags() != self.original_window_flags:
             print("  Restoring standard window flags.")
             self.setWindowFlags(self.original_window_flags)

        if self.isFullScreen():
            self.showNormal()
            print("  Exiting App Fullscreen (Decorated)")
            # Restore original geometry if stored and currently fullscreen
            if self.original_geometry_before_fs:
                 print(f"  Restoring original geometry: {self.original_geometry_before_fs}")
                 self.setGeometry(self.original_geometry_before_fs)
                 self.original_geometry_before_fs = None # Clear stored geometry
        else:
            # Store geometry before going fullscreen
            self.original_geometry_before_fs = self.geometry()
            self.showFullScreen()
            print("  Entering App Fullscreen (Decorated)")
        self.show()

    def show_browser(self):
        """Switch back to browser view, ensuring exit from video fullscreen."""
        if self.is_video_layout_fullscreen:
             print("show_browser: Exiting video layout first.")
             self.exit_video_fullscreen_layout() # Exit video fullscreen layout

        self.stop()
        self.stacked_widget.setCurrentWidget(self.browser_widget)
        self.setWindowTitle("Raspberry Pi Movie Player")

    def play_file(self, filepath):
        """Play a media file and switch to the player view"""
        if self.is_video_layout_fullscreen:
             print("play_file: Exiting video layout first.")
             self.exit_video_fullscreen_layout() # Exit video fullscreen first

        if filepath and os.path.isfile(filepath):
            try:
                # Ensure video frame is in the correct layout before starting
                if self.video_frame.parentWidget() is not self.player_widget:
                     # If it was left in fullscreen layout somehow, move it back
                     current_layout = self.video_frame.layout()
                     if current_layout:
                         current_layout.removeWidget(self.video_frame)
                     self.player_layout.insertWidget(0, self.video_frame, 1)

                self.media = self.instance.media_new(filepath)
                self.mediaplayer.set_media(self.media)

                # Set the output window *before* switching view might be safer
                self._set_vlc_window(self.video_frame.winId())

                # Switch to the player view (Index 0)
                self.stacked_widget.setCurrentWidget(self.player_widget)
                self.control_widget.show() # Ensure controls are visible

                self.mediaplayer.play()
                QTimer.singleShot(100, self._update_play_button_icon)

                self.is_playing = True
                self.timer.start()
                self.setWindowTitle(f"Playing - {os.path.basename(filepath)}")

            except Exception as e:
                 QMessageBox.critical(self, "Playback Error", f"Failed to play file '{os.path.basename(filepath)}':\n{str(e)}")
                 self.show_browser()
        elif filepath:
             QMessageBox.warning(self, "File Not Found", f"The selected file could not be found:\n{filepath}")
        else:
             print("Play file called with empty path.")


    def _update_play_button_icon(self):
        """Helper to update icon based on actual player state."""
        if self.mediaplayer.is_playing():
            self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
            self.is_playing = True
            if not self.timer.isActive(): self.timer.start()
        else:
            self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
            self.is_playing = False
            # Don't stop timer here, might be paused or stopped

    def play_pause(self):
        """Toggle play/pause status"""
        if self.mediaplayer.is_playing():
            self.mediaplayer.pause()
            self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
            self.is_playing = False
            # Keep timer running for paused state to update time/slider
        else:
            # Check if we have media loaded, otherwise play does nothing
            if self.mediaplayer.get_media():
                self.mediaplayer.play()
                self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPause))
                self.is_playing = True
                if not self.timer.isActive():
                    self.timer.start()
            else:
                 print("Play/Pause called but no media loaded.")


    def stop(self):
        """Stop player"""
        if self.mediaplayer.get_media():
             self.mediaplayer.stop()
        self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.is_playing = False
        self.timer.stop()
        # Reset time label and slider
        self.time_label.setText("00:00 / 00:00")
        self.position_slider.setValue(0)

    def update_ui(self):
        """Update the UI with current playback status"""
        if not self.is_playing and not self.mediaplayer.is_playing() and self.mediaplayer.get_state() != vlc.State.Paused:
            # If stopped or finished, ensure timer stops and UI reflects it
            if self.timer.isActive():
                 self.stop() # Call stop logic to reset UI elements
            return

        # Update the slider position
        # Check if media is loaded and has duration
        media_length = self.mediaplayer.get_length()
        if media_length > 0:
            media_pos = self.mediaplayer.get_position()
            self.position_slider.setValue(int(media_pos * 1000))

            # Update the time display
            current_msecs = self.mediaplayer.get_time()
            total_msecs = media_length

            current_secs = current_msecs // 1000
            total_secs = total_msecs // 1000

            current_time_str = f"{current_secs // 60:02d}:{current_secs % 60:02d}"
            total_time_str = f"{total_secs // 60:02d}:{total_secs % 60:02d}"

            self.time_label.setText(f"{current_time_str} / {total_time_str}")
        else:
             # No media loaded or duration unknown
             self.time_label.setText("00:00 / 00:00")
             self.position_slider.setValue(0)

        # Check for end of media
        if self.mediaplayer.get_state() == vlc.State.Ended:
            self.stop() # Reset UI when playback finishes


    def set_position(self, position):
        """Set the player position according to the slider value"""
        # Only set position if media is loaded
        if self.mediaplayer.get_media():
            self.mediaplayer.set_position(position / 1000.0)

    # def changeEvent(self, event):
    #     """Handle window state changes."""
    #     if event.type() == QEvent.WindowStateChange:
    #         old_state = event.oldState()
    #         new_state = self.windowState()
    #
    #         # Check if we were externally forced out of fullscreen
    #         if (old_state & Qt.WindowFullScreen) and not (new_state & Qt.WindowFullScreen):
    #             print("Detected external exit from App Fullscreen.")
    #             # If we were in video layout fullscreen, exit that too
    #             if self.is_video_layout_fullscreen:
    #                 print("  Also exiting video layout.")
    #                 self.exit_video_fullscreen_layout() # Call our exit logic
    #
    #     super().changeEvent(event)


    # --- Subtitle Handling Slots ---

    @pyqtSlot(str)
    def on_find_subtitles_requested(self, video_path):
        """Slot called when the FileBrowser requests subtitle search."""
        if not video_path:
            return

        self.current_search_video_path = video_path # Store path for later use
        filename = os.path.basename(video_path)
        query = os.path.splitext(filename)[0] # Use filename without extension as query

        # TODO: Future enhancement - try to extract IMDB ID from filename or metadata
        imdb_id = None

        # Define desired languages (adjust as needed)
        languages = "en,pl"

        print(f"Searching subtitles for '{query}' (Languages: {languages})")
        QApplication.setOverrideCursor(Qt.WaitCursor) # Show busy cursor
        # Call the manager's search function
        self.subtitle_manager.search_subtitles(query=query, imdb_id=imdb_id, languages=languages)

    @pyqtSlot(list)
    def on_subtitle_search_results(self, results):
        """Slot called when subtitle search results are received."""
        QApplication.restoreOverrideCursor() # Restore cursor
        print(f"Received {len(results)} subtitle results.")

        if not self.current_search_video_path:
             print("Warning: Received subtitle results but no video path context.")
             QMessageBox.warning(self, "Subtitle Search", "Search results received, but the original video context was lost.")
             return

        if not results:
            QMessageBox.information(self, "Subtitle Search", f"No subtitles found for '{os.path.basename(self.current_search_video_path)}'.")
            self.current_search_video_path = None # Clear context
            return

        # Create and show the results dialog
        dialog = SubtitleResultsDialog(results, self)
        # Connect the dialog's signal to our slot that requests the download
        dialog.subtitle_selected_for_download.connect(self.on_subtitle_selected)

        # Execute the dialog modally
        dialog.exec_() # This blocks until the dialog is closed

        # Dialog is closed, context is cleared here *unless* download was initiated
        # Let on_subtitle_selected handle clearing context if needed

    @pyqtSlot(str)
    def on_subtitle_search_error(self, error_message):
        """Slot called when subtitle search fails."""
        QApplication.restoreOverrideCursor() # Restore cursor
        QMessageBox.critical(self, "Subtitle Search Error", f"Failed to search for subtitles:\n{error_message}")
        self.current_search_video_path = None # Clear context

    @pyqtSlot(dict)
    def on_subtitle_selected(self, subtitle_dict):
        """Slot called when a subtitle is selected from the results dialog."""
        if not self.current_search_video_path:
            print("Warning: Subtitle selected but no video path context.")
            QMessageBox.warning(self, "Subtitle Download", "Subtitle selected, but the original video context was lost.")
            return

        file_id = subtitle_dict.get('file_id')
        if not file_id:
             QMessageBox.critical(self, "Subtitle Download Error", "Selected subtitle has no File ID.")
             self.current_search_video_path = None # Clear context
             return

        print(f"Requesting download for File ID: {file_id}")
        self.current_subtitle_to_download = subtitle_dict # Store for filename generation
        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.subtitle_manager.request_download(file_id)
        # Do NOT clear current_search_video_path here, needed for download ready


    @pyqtSlot(str, str)
    def on_subtitle_download_ready(self, download_link, suggested_filename):
        """Slot called when the download link is ready."""
        QApplication.restoreOverrideCursor()
        print("Subtitle download link received.")

        if not self.current_search_video_path or not self.current_subtitle_to_download:
             print("Warning: Download ready but context (video path or subtitle data) is missing.")
             QMessageBox.warning(self, "Subtitle Download", "Download link received, but the context was lost. Cannot save file.")
             self.current_search_video_path = None
             self.current_subtitle_to_download = None
             return

        # --- Determine Save Path ---
        try:
            video_dir = os.path.dirname(self.current_search_video_path)
            video_base = os.path.splitext(os.path.basename(self.current_search_video_path))[0]
            language_code = self.current_subtitle_to_download.get('language', 'und') # Default to 'und' (undetermined) if missing

            # Create the standard filename (e.g., MyMovie.en.srt)
            srt_filename = f"{video_base}.{language_code}.srt"
            save_path = os.path.join(video_dir, srt_filename)

            print(f"Attempting to download subtitle to: {save_path}")

            # Run the actual download in a background thread
            threading.Thread(
                target=self._download_subtitle_worker,
                args=(download_link, save_path),
                daemon=True
            ).start()

        except Exception as e:
            QMessageBox.critical(self, "Subtitle Download Error", f"Error determining save path:\n{e}")
            traceback.print_exc() # Print full traceback to console
            self.current_search_video_path = None
            self.current_subtitle_to_download = None


    def _download_subtitle_worker(self, link, path):
        """Worker thread function to download the subtitle file."""
        success, error = self.subtitle_manager.download_subtitle_file(link, path)
        # Use invokeMethod to safely call the final slot from this worker thread
        QMetaObject.invokeMethod(
            self,
            "on_actual_download_finished",
            Qt.QueuedConnection,
            Q_ARG(bool, success),
            Q_ARG(str, path if success else ""),
            Q_ARG(str, error if not success else "")
        )

    @pyqtSlot(bool, str, str)
    def on_actual_download_finished(self, success, save_path, error_message):
        """Slot called after the subtitle file download attempt is finished."""
        QApplication.restoreOverrideCursor() # Ensure cursor is restored
        if success:
            QMessageBox.information(self, "Subtitle Downloaded", f"Subtitle saved successfully:\n{save_path}")
            # Refresh file browser to show the [Sub] tag
            self.library_tab.refresh_files()
        else:
            QMessageBox.warning(self, "Subtitle Download Failed", f"Failed to download subtitle file:\n{error_message}")

        # Clear context now that the operation is fully complete
        self.current_search_video_path = None
        self.current_subtitle_to_download = None

    @pyqtSlot(dict)
    def on_subtitle_download_error(self, error_message_json):
        """Slot called if requesting the download link fails. Handles auto-relogin."""
        QApplication.restoreOverrideCursor()

        # Now 'error_details' is the actual dictionary emitted by the signal
        error_status = error_message_json.get('status', -1)
        error_msg_text = error_message_json.get('message', 'Unknown download error')
        try:
            # The error message is often JSON containing status and message
            # Let's try parsing it if the SubtitleManager passed JSON string
            # Note: SubtitleManager._make_request currently returns a dict,
            # so this parsing might not be needed if the signal emitted a dict.
            # Let's assume for now the signal might emit a string representation.
            # A better approach would be for the signal to emit the error dict.
            # *** Let's refactor SubtitleManager to emit the dict ***
            # (See modification to SubtitleManager below)

            # Assuming error_message is now the error dictionary:
            error_details = error_message_json  # Rename for clarity
            error_status = error_details.get('status', -1)
            error_msg_text = error_details.get('message', 'Unknown download error')

        except Exception:
            # If parsing fails, use the raw string
            print(f"Could not parse error details: {error_message_json}")
            pass  # Keep default error_msg_text

        # --- Check for Auto-Retry Condition ---
        can_relogin = (self.subtitle_manager.username and
                       self.subtitle_manager.password)

        if error_status == 401 and can_relogin and self.current_subtitle_to_download:
            # Unauthorized, credentials available, and context exists
            file_id_to_retry = self.current_subtitle_to_download.get('file_id')

            if file_id_to_retry and self.pending_download_retry_info is None:  # Avoid retry loops
                print(
                    f"Download failed (401 Unauthorized). Credentials found. Attempting re-login for file_id {file_id_to_retry}...")
                self.pending_download_retry_info = {'file_id': file_id_to_retry}
                # Show transient status
                # TODO: Update a status bar instead of QMessageBox?
                msgBox = QMessageBox(self)
                msgBox.setWindowTitle("Re-Login Required")
                msgBox.setText("Your login session may have expired.\nAttempting to log in again...")
                msgBox.setIcon(QMessageBox.Information)
                msgBox.setStandardButtons(QMessageBox.NoButton)  # No buttons needed
                msgBox.show()
                QTimer.singleShot(100, msgBox.accept)  # Show briefly

                QApplication.setOverrideCursor(Qt.WaitCursor)
                self.subtitle_manager.login()
                # IMPORTANT: Do NOT clear context here, wait for login result
                return  # Exit the slot, wait for on_login_status

            elif self.pending_download_retry_info:
                print("Download failed (401) but a retry is already pending. Ignoring.")
                # Avoid showing another error if retry was already initiated.
                return  # Should not happen often but prevents loops

        # --- Handle Non-Retryable Errors or Failed Retry ---
        print(f"Subtitle download request failed (Status: {error_status}). Error: {error_msg_text}")
        QMessageBox.critical(self, "Subtitle Download Error",
                             f"Failed to prepare subtitle download (Status: {error_status}):\n{error_msg_text}")

        # Clear context only if not attempting a retry
        if not self.pending_download_retry_info:
            self.current_search_video_path = None
            self.current_subtitle_to_download = None


    # --- Optional Slots for Manager Status ---
    @pyqtSlot(bool, str)
    def on_subtitle_login_status(self, success, message):
        """Handle subtitle manager login status, potentially triggering download retry."""
        QApplication.restoreOverrideCursor() # Restore cursor after login attempt
        print(f"Subtitle Login Status Update: {success} - {message}")

        if success and self.pending_download_retry_info:
            # Re-login was successful AND we need to retry a download
            file_id_to_retry = self.pending_download_retry_info.get('file_id')
            print(f"Re-login successful. Retrying download request for file_id: {file_id_to_retry}")

            # Clear the retry flag *before* making the request
            self.pending_download_retry_info = None

            if file_id_to_retry:
                # Show transient status
                 msgBox = QMessageBox(self)
                 msgBox.setWindowTitle("Re-Login Successful")
                 msgBox.setText("Login successful.\nRetrying subtitle download...")
                 msgBox.setIcon(QMessageBox.Information)
                 msgBox.setStandardButtons(QMessageBox.NoButton)
                 msgBox.show()
                 QTimer.singleShot(100, msgBox.accept)

                 QApplication.setOverrideCursor(Qt.WaitCursor)
                 # Re-trigger the download request
                 self.subtitle_manager.request_download(file_id_to_retry)
            else:
                 print("Error: Pending retry info was invalid.")
                 # Clear context as retry cannot proceed
                 self.current_search_video_path = None
                 self.current_subtitle_to_download = None

        elif not success and self.pending_download_retry_info:
            # Re-login attempt failed after a download error
            print("Re-login attempt failed. Cannot retry download.")
            QMessageBox.critical(self, "Re-Login Failed",
                                 f"Automatic re-login failed:\n{message}\n\nCannot download the selected subtitle.")
            # Clear the retry flag and the main context
            self.pending_download_retry_info = None
            self.current_search_video_path = None
            self.current_subtitle_to_download = None
        else:
            # Normal login status update (not related to a download retry)
            # Could update a status bar here if desired
            pass

    @pyqtSlot(int, int)
    def on_subtitle_quota_info(self, remaining, limit):
        """Handle subtitle quota updates (optional UI feedback)."""
        print(f"Subtitle Quota Update: {remaining}/{limit} remaining.")
        # Could update a status bar label, etc.


    # Override closeEvent to handle manager logout
    def closeEvent(self, event):
        """Ensure clean shutdown."""
        print("Closing application...")
        # Stop media player
        self.stop()

        # Logout subtitle manager if logged in
        if hasattr(self, 'subtitle_manager') and self.subtitle_manager.logged_in:
            print("Logging out from OpenSubtitles...")
            self.subtitle_manager.logout()
            # Give logout a moment - ideally, wait for a signal, but sleep is simpler here
            QTimer.singleShot(500, event.accept) # Accept after slight delay
            event.ignore() # Ignore initial close event
        else:
            event.accept() # Accept immediately if no logout needed

# --- Main Execution --- (Should be in main.py)
# def main():
#     app = QApplication(sys.argv)
#     # Check for API Key placeholder (copied from subtitle_manager example)
#     from source.subtitle_manager import OPENSUBTITLES_API_KEY, OPENSUBTITLES_USERNAME, OPENSUBTITLES_PASSWORD
#     if OPENSUBTITLES_API_KEY == "YOUR_API_KEY_HERE":
#          print("\n" + "*"*60)
#          print(" WARNING: OpenSubtitles API Key placeholder not replaced!")
#          # ... (rest of the warning)
#     elif OPENSUBTITLES_USERNAME != "YOUR_USERNAME_HERE" and OPENSUBTITLES_PASSWORD == "YOUR_PASSWORD_HERE":
#          print("\n" + "*"*60)
#          print(" WARNING: OpenSubtitles username is set, but password is not!")
#          # ... (rest of the warning)

#     player = MoviePlayerApp()
#     player.show()
#     sys.exit(app.exec_())

# if __name__ == "__main__":
#     main()