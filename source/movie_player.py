# --- START OF FILE source/movie_player.py ---

"""
Main application module for the Raspberry Pi Movie Player App.
Integrates media playback with library management and other features.
"""

import sys
import os
import vlc
import threading
import traceback

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
# Placeholder file no longer needed for SuggestionsTab
from source.subtitle_manager import SubtitleManager
from source.subtitle_dialog import SubtitleResultsDialog
from source.web_browser_tab import WebBrowserTab # Import the new browser tab

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
        self.current_search_video_path = None
        self.current_subtitle_to_download = None
        self.pending_download_retry_info = None
        self.is_video_layout_fullscreen = False
        self.original_window_flags = self.windowFlags()
        self.mouse_pos_before_hide = None
        self.original_geometry_before_fs = None
        self.screen_geometry = QApplication.desktop().screenGeometry()
        self.is_cursor_hidden = False

        # --- Window Properties ---
        self.setWindowTitle("Raspberry Pi Movie Player")
        self.setGeometry(100, 100, 1024, 768)
        self.setFocusPolicy(Qt.StrongFocus)

        # --- VLC ---
        self.instance = vlc.Instance()
        self.mediaplayer = self.instance.media_player_new()

        # --- Managers & Timers ---
        self.subtitle_manager = SubtitleManager()
        if self.subtitle_manager.username and self.subtitle_manager.password:
            print("Attempting OpenSubtitles login...")
            self.subtitle_manager.login()
        self.cursor_hide_timer = QTimer(self)
        self.cursor_hide_timer.setInterval(CURSOR_HIDE_TIMEOUT_MS)
        self.cursor_hide_timer.setSingleShot(True)
        self.cursor_hide_timer.timeout.connect(self.hide_cursor_on_inactivity)
        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.update_ui)

        # --- Widgets and Layouts ---
        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.stacked_widget = QStackedWidget()

        # --- Player View (Index 0) ---
        self.player_widget = QWidget()
        self.player_layout = QVBoxLayout(self.player_widget)
        self.player_layout.setContentsMargins(0, 0, 0, 0); self.player_layout.setSpacing(0)
        self.video_frame = VideoFrame()
        self.control_widget = QWidget()
        self.control_layout = QHBoxLayout(self.control_widget)
        self.control_layout.setContentsMargins(5, 5, 5, 5)
        self.play_button = QPushButton(); self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPlay))
        self.stop_button = QPushButton(); self.stop_button.setIcon(self.style().standardIcon(QStyle.SP_MediaStop))
        self.position_slider = QSlider(Qt.Horizontal); self.position_slider.setMaximum(1000)
        self.time_label = QLabel("00:00 / 00:00"); self.time_label.setStyleSheet("margin-left: 5px; margin-right: 5px;")
        self.back_button = QPushButton("Back to Library")
        self.control_layout.addWidget(self.play_button); self.control_layout.addWidget(self.stop_button)
        self.control_layout.addWidget(self.position_slider); self.control_layout.addWidget(self.time_label)
        self.control_layout.addStretch(); self.control_layout.addWidget(self.back_button)
        self.player_layout.addWidget(self.video_frame, 1); self.player_layout.addWidget(self.control_widget)

        # --- Browser View (Index 1) ---
        self.browser_widget = QWidget()
        self.browser_layout = QVBoxLayout(self.browser_widget)
        self.tab_widget = QTabWidget()
        self.library_tab = FileBrowser()
        self.downloads_tab = DownloadsTab()
        self.filmweb_tab = WebBrowserTab() # <<< Use WebBrowserTab
        self.tab_widget.addTab(self.library_tab, "Library")
        self.tab_widget.addTab(self.downloads_tab, "Downloads")
        self.tab_widget.addTab(self.filmweb_tab, "Filmweb") # <<< Set Tab Name
        self.browser_layout.addWidget(self.tab_widget)

        # --- Video Fullscreen View (Index 2) ---
        self.video_fullscreen_widget = QWidget()
        self.video_fullscreen_widget.setObjectName("VideoFullscreenContainer")
        self.video_fullscreen_layout = QVBoxLayout(self.video_fullscreen_widget)
        self.video_fullscreen_layout.setContentsMargins(0, 0, 0, 0); self.video_fullscreen_layout.setSpacing(0)

        # --- Stack Setup ---
        self.stacked_widget.addWidget(self.player_widget)
        self.stacked_widget.addWidget(self.browser_widget)
        self.stacked_widget.addWidget(self.video_fullscreen_widget)
        self.main_layout.addWidget(self.stacked_widget)
        self.stacked_widget.setCurrentIndex(1) # Start on Browser view

        # --- Playback State ---
        self.is_playing = False
        self.media = None

        # --- Connect Signals ---
        self.library_tab.file_selected.connect(self.play_file)
        self.library_tab.find_subtitles_requested.connect(self.on_find_subtitles_requested)
        self.video_frame.doubleClicked.connect(self.toggle_video_fullscreen)
        self.video_frame.mouseMoved.connect(self.on_mouse_moved_over_video)
        self.play_button.clicked.connect(self.play_pause)
        self.stop_button.clicked.connect(self.stop)
        self.position_slider.sliderMoved.connect(self.set_position)
        self.back_button.clicked.connect(self.show_browser)
        # Subtitle Manager
        self.subtitle_manager.search_results.connect(self.on_subtitle_search_results)
        self.subtitle_manager.search_error.connect(self.on_subtitle_search_error)
        self.subtitle_manager.download_ready.connect(self.on_subtitle_download_ready)
        self.subtitle_manager.download_error.connect(self.on_subtitle_download_error)
        self.subtitle_manager.login_status.connect(self.on_subtitle_login_status)
        self.subtitle_manager.quota_info.connect(self.on_subtitle_quota_info)
        # --- Connect Web Browser Tab Signal ---
        self.filmweb_tab.search_requested.connect(self.on_web_search_requested)


    # --- Cursor Handling Methods ---
    def hide_cursor_on_inactivity(self):
        is_player_visible = self.stacked_widget.currentWidget() in [self.player_widget, self.video_fullscreen_widget]
        if not is_player_visible:
            self.cursor_hide_timer.stop(); return
        if self.isActiveWindow() and not self.is_cursor_hidden:
            print(">>> Hiding cursor due to inactivity.")
            QApplication.setOverrideCursor(Qt.BlankCursor)
            self.is_cursor_hidden = True

    def show_cursor(self, triggered_by_move=False):
        if not triggered_by_move: self.cursor_hide_timer.stop()
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
        if not self.is_video_layout_fullscreen:
            current_state = self.mediaplayer.get_state()
            if current_state in [vlc.State.Playing, vlc.State.Paused]:
                 self.show_cursor(triggered_by_move=True)


    # --- Fullscreen Toggling Methods ---
    def enter_video_fullscreen_layout(self):
        if self.stacked_widget.currentWidget() is not self.player_widget:
            current_state = self.mediaplayer.get_state()
            if current_state in [vlc.State.Playing, vlc.State.Paused]:
                print("Switching to player view before entering fullscreen...")
                self.stacked_widget.setCurrentWidget(self.player_widget)
                QTimer.singleShot(50, self.enter_video_fullscreen_layout); return
            else: print("Cannot enter video fullscreen from current view if not playing."); return
        print("Entering Video Fullscreen Layout")
        self.original_geometry_before_fs = self.geometry()
        self.mouse_pos_before_hide = QCursor.pos()
        self.cursor_hide_timer.stop()
        if not self.is_cursor_hidden: QApplication.setOverrideCursor(Qt.BlankCursor); self.is_cursor_hidden = True
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
        if self.isFullScreen() and self.is_video_layout_fullscreen:
             print(f"  Adjusting geometry to screen: {self.screen_geometry}")
             self.setGeometry(self.screen_geometry); self.activateWindow(); self.raise_(); self.update()

    def exit_video_fullscreen_layout(self):
        if not self.is_video_layout_fullscreen: return
        print("Exiting Video Fullscreen Layout")
        self.show_cursor() # Restore cursor and stop timer
        if self.mouse_pos_before_hide: QCursor.setPos(self.mouse_pos_before_hide); self.mouse_pos_before_hide = None
        print("  Restoring App Window to Normal State.")
        self.setWindowFlags(self.original_window_flags); self.showNormal()
        if self.original_geometry_before_fs:
             print(f"  Restoring original geometry: {self.original_geometry_before_fs}")
             self.setGeometry(self.original_geometry_before_fs); self.original_geometry_before_fs = None
        self.show()
        if self.previous_widget_before_video_fs:
            self.video_fullscreen_layout.removeWidget(self.video_frame)
            self.player_layout.insertWidget(0, self.video_frame, 1)
            self.stacked_widget.setCurrentWidget(self.previous_widget_before_video_fs)
            self.control_widget.show()
        else:
            self.stacked_widget.setCurrentWidget(self.player_widget); self.control_widget.show()
        self.is_video_layout_fullscreen = False; self.previous_widget_before_video_fs = None
        QTimer.singleShot(50, lambda: self._set_vlc_window(self.video_frame.winId()))
        if self.mediaplayer.get_state() == vlc.State.Playing: self.cursor_hide_timer.start()

    def toggle_video_fullscreen(self):
        current_state = self.mediaplayer.get_state()
        can_toggle = current_state in [vlc.State.Playing, vlc.State.Paused, vlc.State.Opening, vlc.State.Buffering]
        if not can_toggle: print("Cannot toggle video fullscreen: No media playing or paused."); return
        if self.is_video_layout_fullscreen: self.exit_video_fullscreen_layout()
        else: self.enter_video_fullscreen_layout()

    def _set_vlc_window(self, win_id_obj):
        try: win_id = int(win_id_obj); print(f"Setting VLC output window to ID: {win_id} (converted from {win_id_obj})")
        except (TypeError, ValueError) as e: print(f"Error converting winId ({win_id_obj}) to integer: {e}"); QMessageBox.warning(self, "VLC Error", f"Could not get valid window ID for video output."); return
        try:
            if sys.platform.startswith('linux'): self.mediaplayer.set_xwindow(win_id)
            elif sys.platform == "win32": self.mediaplayer.set_hwnd(win_id)
            elif sys.platform == "darwin": self.mediaplayer.set_nsobject(win_id)
        except Exception as e:
            print(f"Error setting VLC window with ID {win_id}: {e}"); err_msg = f"Could not attach video output:\n{e}"
            if isinstance(e, TypeError): err_msg = f"VLC reported type error setting window ID.\nCheck VLC/Qt versions."
            QMessageBox.warning(self, "VLC Error", err_msg)

    # --- Event Handling ---
    def keyPressEvent(self, event):
        key = event.key()
        if key == Qt.Key_F11:
            print("F11 Pressed")
            if self.is_video_layout_fullscreen: print("  Video layout active. Exiting it first."); self.exit_video_fullscreen_layout()
            else: self._toggle_app_fullscreen_decorated()
            event.accept()
        elif key == Qt.Key_Escape:
            if self.is_video_layout_fullscreen: print("Escape pressed: Exiting Video Fullscreen Layout"); self.exit_video_fullscreen_layout(); event.accept()
            else: super().keyPressEvent(event)
        elif key == Qt.Key_Space:
             current_view = self.stacked_widget.currentWidget()
             if current_view is self.player_widget or current_view is self.video_fullscreen_widget: self.play_pause(); event.accept()
        else:
            current_view = self.stacked_widget.currentWidget()
            if current_view is self.player_widget or current_view is self.video_fullscreen_widget: self.show_cursor() # Show cursor on other keys
            super().keyPressEvent(event)

    def _toggle_app_fullscreen_decorated(self):
        if self.windowFlags() & Qt.FramelessWindowHint: print("  Restoring standard window flags."); self.setWindowFlags(self.original_window_flags)
        if self.isFullScreen():
            self.showNormal(); print("  Exiting App Fullscreen (Decorated)")
            if self.original_geometry_before_fs: print(f"  Restoring original geometry: {self.original_geometry_before_fs}"); self.setGeometry(self.original_geometry_before_fs); self.original_geometry_before_fs = None
        else:
            self.original_geometry_before_fs = self.geometry(); self.showFullScreen(); print("  Entering App Fullscreen (Decorated)")
        self.show()

    # --- Playback Methods ---
    def show_browser(self):
        if self.is_video_layout_fullscreen: print("show_browser: Exiting video layout first."); self.exit_video_fullscreen_layout()
        self.stop()
        self.stacked_widget.setCurrentWidget(self.browser_widget); self.setWindowTitle("Raspberry Pi Movie Player")

    def play_file(self, filepath):
        print(f"Play_file called with: {filepath}")
        if self.is_video_layout_fullscreen: print("play_file: Exiting video layout first."); self.exit_video_fullscreen_layout()
        if filepath and os.path.isfile(filepath):
            try:
                if self.video_frame.parentWidget() is not self.player_widget:
                     print("play_file: Reparenting video frame.")
                     parent_widget = self.video_frame.parentWidget(); parent_layout = parent_widget.layout() if parent_widget else None
                     if parent_layout: parent_layout.removeWidget(self.video_frame)
                     self.player_layout.insertWidget(0, self.video_frame, 1)
                current_state = self.mediaplayer.get_state()
                if current_state in [vlc.State.Playing, vlc.State.Paused]: print("play_file: Stopping previous media."); self.stop(); QTimer.singleShot(100, lambda: self._play_file_continue(filepath))
                else: self._play_file_continue(filepath)
            except Exception as e: self.show_cursor(); QMessageBox.critical(self, "Playback Error", f"Failed init playback: {e}"); traceback.print_exc(); self.show_browser()
        elif filepath: QMessageBox.warning(self, "File Not Found", f"File not found:\n{filepath}")
        else: print("Play file called with empty path.")

    def _play_file_continue(self, filepath):
         try:
              print(f"_play_file_continue: Loading media: {filepath}")
              self.media = self.instance.media_new(filepath); assert self.media, "Failed to create VLC media object."
              self.mediaplayer.set_media(self.media)
              win_id = self.video_frame.winId()
              if not win_id: print("Window ID not immediate, delaying."); QTimer.singleShot(200, lambda: self._set_vlc_window_and_play(win_id))
              else: self._set_vlc_window_and_play(win_id)
         except Exception as e: self.show_cursor(); QMessageBox.critical(self, "Playback Error", f"Failed load media: {e}"); traceback.print_exc(); self.show_browser()

    def _set_vlc_window_and_play(self, win_id_obj):
         try:
             current_win_id = win_id_obj or self.video_frame.winId(); assert current_win_id, "VideoFrame still has no valid Window ID."
             print("_set_vlc_window_and_play: Setting window and playing.")
             self._set_vlc_window(current_win_id)
             self.stacked_widget.setCurrentWidget(self.player_widget); self.control_widget.show()
             play_result = self.mediaplayer.play(); assert play_result != -1, "VLC mediaplayer.play() returned error (-1)."
             print("Playback initiated via play().")
             QTimer.singleShot(150, self._post_play_start_actions)
         except Exception as e: self.show_cursor(); filepath = self.media.get_mrl() if self.media else "Unknown"; QMessageBox.critical(self, "Playback Error", f"Failed start playback: {e}"); traceback.print_exc(); self.show_browser()

    def _post_play_start_actions(self):
         current_state = self.mediaplayer.get_state(); print(f"_post_play_start_actions: Current state = {current_state}")
         self._update_play_button_icon()
         if current_state in [vlc.State.Playing, vlc.State.Paused]:
              self.is_playing = self.mediaplayer.is_playing()
              if not self.timer.isActive(): self.timer.start()
              if not self.is_video_layout_fullscreen and self.is_playing: print("  Starting cursor hide timer on play start."); self.cursor_hide_timer.start()
              elif not self.is_playing: self.show_cursor()
         else: print(f"Warning: Playback state unexpected: {current_state}. Stopping."); self.stop()

    def _update_play_button_icon(self):
        is_playing = self.mediaplayer.is_playing()
        self.play_button.setIcon(self.style().standardIcon(QStyle.SP_MediaPause if is_playing else QStyle.SP_MediaPlay))

    def play_pause(self):
        if self.mediaplayer.is_playing(): print("Pausing playback."); self.mediaplayer.pause(); self.is_playing = False; self.show_cursor()
        else:
            if self.mediaplayer.get_media():
                print("Resuming/Starting playback."); play_result = self.mediaplayer.play()
                if play_result == -1: QMessageBox.warning(self, "Playback Error", "Failed to resume/start playback."); return
                self.is_playing = True;
                if not self.timer.isActive(): self.timer.start()
                if not self.is_video_layout_fullscreen: self.cursor_hide_timer.start()
            else: print("Play/Pause called but no media loaded.")
        self._update_play_button_icon()

    def stop(self):
        print("Stop called."); media_exists = self.mediaplayer.get_media() is not None
        if media_exists: self.mediaplayer.stop()
        self._update_play_button_icon(); self.is_playing = False
        if self.timer.isActive(): self.timer.stop()
        self.time_label.setText("00:00 / 00:00"); self.position_slider.setValue(0)
        self.show_cursor() # Pass explicit False here - show_cursor signature changed

    def update_ui(self):
        if not self.timer.isActive(): return
        current_state = self.mediaplayer.get_state()
        if current_state in [vlc.State.Playing, vlc.State.Paused]:
            media_length = self.mediaplayer.get_length()
            if media_length > 0:
                media_pos = self.mediaplayer.get_position(); current_msecs = self.mediaplayer.get_time()
                if media_pos >= 0.0 and media_pos <= 1.01 and current_msecs >= 0:
                     if not self.position_slider.isSliderDown(): self.position_slider.setValue(int(media_pos * 1000))
                     current_secs = current_msecs // 1000; total_secs = media_length // 1000
                     current_time_str = f"{current_secs // 60:02d}:{current_secs % 60:02d}"
                     total_time_str = f"{total_secs // 60:02d}:{total_secs % 60:02d}"
                     self.time_label.setText(f"{current_time_str} / {total_time_str}")
            else:
                if self.time_label.text() != "00:00 / --:--": self.time_label.setText("00:00 / --:--")
                if not self.position_slider.isSliderDown(): self.position_slider.setValue(0)
        elif current_state == vlc.State.Ended: print("Playback ended."); self.stop()
        elif current_state == vlc.State.Error: print("VLC Error state detected."); QMessageBox.warning(self, "Playback Error", "Playback error."); self.show_browser()
        elif current_state == vlc.State.Stopped:
             if self.is_playing or self.timer.isActive(): print("VLC Stopped state detected."); self.stop()

    def set_position(self, position):
        if self.mediaplayer.is_seekable(): self.mediaplayer.set_position(position / 1000.0); self.show_cursor()
        else: print("Media is not seekable.")

    # --- Subtitle Handling Slots ---
    @pyqtSlot(str)
    def on_find_subtitles_requested(self, video_path):
        # ... (Implementation unchanged) ...
        if not video_path: return
        self.current_search_video_path = video_path; filename = os.path.basename(video_path)
        query = os.path.splitext(filename)[0]; imdb_id = None; languages = "en,pl"
        print(f"Searching subtitles for '{query}' (Lang: {languages})"); QApplication.setOverrideCursor(Qt.WaitCursor)
        self.subtitle_manager.search_subtitles(query=query, imdb_id=imdb_id, languages=languages)

    @pyqtSlot(list)
    def on_subtitle_search_results(self, results):
        # ... (Implementation unchanged) ...
        QApplication.restoreOverrideCursor(); print(f"Received {len(results)} subtitle results.")
        if not self.current_search_video_path: print("Warn: Sub results w/o context."); QMessageBox.warning(self, "Sub Search", "Results received, context lost."); return
        if not results: QMessageBox.information(self, "Sub Search", f"No subtitles found for '{os.path.basename(self.current_search_video_path)}'."); self.current_search_video_path = None; return
        dialog = SubtitleResultsDialog(results, self); dialog.subtitle_selected_for_download.connect(self.on_subtitle_selected); dialog.exec_()

    @pyqtSlot(str)
    def on_subtitle_search_error(self, error_message):
        # ... (Implementation unchanged) ...
        QApplication.restoreOverrideCursor(); QMessageBox.critical(self, "Sub Search Error", f"Failed search:\n{error_message}"); self.current_search_video_path = None

    @pyqtSlot(dict)
    def on_subtitle_selected(self, subtitle_dict):
        # ... (Implementation unchanged) ...
        if not self.current_search_video_path: print("Warn: Sub selected w/o context."); QMessageBox.warning(self, "Sub Download", "Context lost."); return
        file_id = subtitle_dict.get('file_id');
        if not file_id: QMessageBox.critical(self, "Sub Download Error", "No File ID."); self.current_search_video_path = None; return
        print(f"Requesting download for File ID: {file_id}"); self.current_subtitle_to_download = subtitle_dict; QApplication.setOverrideCursor(Qt.WaitCursor); self.subtitle_manager.request_download(file_id)

    @pyqtSlot(str, str)
    def on_subtitle_download_ready(self, download_link, suggested_filename):
        # ... (Implementation unchanged) ...
        QApplication.restoreOverrideCursor(); print("Sub download link received.")
        if not self.current_search_video_path or not self.current_subtitle_to_download: print("Warn: Download ready but context missing."); QMessageBox.warning(self, "Sub Download", "Context lost."); self.current_search_video_path = None; self.current_subtitle_to_download = None; return
        try:
            video_dir = os.path.dirname(self.current_search_video_path); video_base = os.path.splitext(os.path.basename(self.current_search_video_path))[0]
            language_code = self.current_subtitle_to_download.get('language', 'und'); srt_filename = f"{video_base}.{language_code}.srt"; save_path = os.path.join(video_dir, srt_filename)
            print(f"Attempting download sub to: {save_path}"); threading.Thread(target=self._download_subtitle_worker, args=(download_link, save_path), daemon=True).start()
        except Exception as e: QMessageBox.critical(self, "Sub Download Error", f"Error determining path:\n{e}"); traceback.print_exc(); self.current_search_video_path = None; self.current_subtitle_to_download = None

    def _download_subtitle_worker(self, link, path):
        # ... (Implementation unchanged) ...
        success, error = self.subtitle_manager.download_subtitle_file(link, path)
        QMetaObject.invokeMethod(self, "on_actual_download_finished", Qt.QueuedConnection, Q_ARG(bool, success), Q_ARG(str, path if success else ""), Q_ARG(str, error or ""))

    @pyqtSlot(bool, str, str)
    def on_actual_download_finished(self, success, save_path, error_message):
        # ... (Implementation unchanged) ...
        QApplication.restoreOverrideCursor()
        if success: QMessageBox.information(self, "Sub Downloaded", f"Subtitle saved:\n{save_path}"); self.library_tab.refresh_files()
        else: QMessageBox.warning(self, "Sub Download Failed", f"Failed download:\n{error_message}")
        self.current_search_video_path = None; self.current_subtitle_to_download = None

    @pyqtSlot(dict)
    def on_subtitle_download_error(self, error_details):
        # ... (Implementation unchanged) ...
        QApplication.restoreOverrideCursor()
        error_status = error_details.get('status', -1); error_msg_text = error_details.get('message', 'Unknown download error'); can_relogin = (self.subtitle_manager.username and self.subtitle_manager.password)
        if error_status == 401 and can_relogin and self.current_subtitle_to_download:
            file_id_to_retry = self.current_subtitle_to_download.get('file_id')
            if file_id_to_retry and self.pending_download_retry_info is None: print(f"Download failed (401). Attempting re-login for {file_id_to_retry}..."); self.pending_download_retry_info = {'file_id': file_id_to_retry}; msgBox = QMessageBox(self); msgBox.setWindowTitle("Re-Login Required"); msgBox.setText("Login expired.\nAttempting re-login..."); msgBox.setIcon(QMessageBox.Information); msgBox.setStandardButtons(QMessageBox.NoButton); msgBox.show(); QTimer.singleShot(100, msgBox.accept); QApplication.setOverrideCursor(Qt.WaitCursor); self.subtitle_manager.login(); return
            elif self.pending_download_retry_info: print("Download failed (401) retry pending. Ignoring."); return
        print(f"Sub download request failed (Status: {error_status}). Error: {error_msg_text}"); QMessageBox.critical(self, "Sub Download Error", f"Failed prepare download (Status: {error_status}):\n{error_msg_text}")
        if not self.pending_download_retry_info: self.current_search_video_path = None; self.current_subtitle_to_download = None

    @pyqtSlot(bool, str)
    def on_subtitle_login_status(self, success, message):
        # ... (Implementation unchanged) ...
        QApplication.restoreOverrideCursor(); print(f"Sub Login Status: {success} - {message}")
        if success and self.pending_download_retry_info:
            file_id_to_retry = self.pending_download_retry_info.get('file_id'); print(f"Re-login ok. Retrying download for {file_id_to_retry}"); self.pending_download_retry_info = None
            if file_id_to_retry: msgBox = QMessageBox(self); msgBox.setWindowTitle("Re-Login OK"); msgBox.setText("Retrying download..."); msgBox.setIcon(QMessageBox.Information); msgBox.setStandardButtons(QMessageBox.NoButton); msgBox.show(); QTimer.singleShot(100, msgBox.accept); QApplication.setOverrideCursor(Qt.WaitCursor); self.subtitle_manager.request_download(file_id_to_retry)
            else: print("Error: Pending retry info invalid."); self.current_search_video_path = None; self.current_subtitle_to_download = None
        elif not success and self.pending_download_retry_info: print("Re-login failed."); QMessageBox.critical(self, "Re-Login Failed", f"Auto re-login failed:\n{message}\nCannot download."); self.pending_download_retry_info = None; self.current_search_video_path = None; self.current_subtitle_to_download = None

    @pyqtSlot(int, int)
    def on_subtitle_quota_info(self, remaining, limit):
        # ... (Implementation unchanged) ...
        print(f"Subtitle Quota Update: {remaining}/{limit} remaining.")

    # --- Slot for Web Browser Search Request ---
    @pyqtSlot(str)
    def on_web_search_requested(self, title):
        """ Slot to handle search requests originating from the web browser tab """
        if title:
            print(f"Web Browser requested search for: '{title}'")
            downloads_tab_index = -1
            for i in range(self.tab_widget.count()):
                if self.tab_widget.widget(i) == self.downloads_tab: downloads_tab_index = i; break
            if downloads_tab_index != -1:
                self.tab_widget.setCurrentIndex(downloads_tab_index)
                self.downloads_tab.search_input.setText(title)
                self.downloads_tab.results_table.setRowCount(0) # Clear previous results
                self.downloads_tab.status_label.setText(f"Searching for '{title}'...") # Update status
                self.downloads_tab.search_torrents() # Auto-trigger search
                self.downloads_tab.search_button.setFocus() # Set focus away from input
            else: print("Error: Could not find Downloads tab.")
        else: print("Web Browser requested search with empty title."); QMessageBox.warning(self, "Web Search", "Could not get title.")

    # --- Close Event ---
    def closeEvent(self, event):
        # ... (Implementation unchanged) ...
        print("Closing application..."); self.stop()
        if hasattr(self.downloads_tab, 'downloader') and hasattr(self.downloads_tab.downloader, 'shutdown'): print("Shutting down torrent manager..."); self.downloads_tab.downloader.shutdown()
        if hasattr(self, 'subtitle_manager') and self.subtitle_manager.logged_in: print("Logging out from OpenSubtitles..."); self.subtitle_manager.logout(); QTimer.singleShot(500, event.accept); event.ignore()
        else: event.accept()

# --- END OF FILE source/movie_player.py ---