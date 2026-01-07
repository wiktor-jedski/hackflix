"""
Download Orchestrator

Central coordinator for the 3-phase download pipeline:
1. Video Download (0-33%)
2. Subtitle Download (34-66%)
3. Translation (67-100%)

Integrates TorrentDownloader, SubtitleManager, and SubtitleTranslator.
"""

import os
import re
import threading
import traceback
from pathlib import Path
from typing import Optional, Dict, Any
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, QTimer

from source.download_state_manager import DownloadStateManager
from source.torrent_manager import TorrentDownloader
from source.subtitle_manager import SubtitleManager
from source.translation_manager import SubtitleTranslator


# Regex for Season/Episode Extraction (copied from movie_player.py)
SEASON_EPISODE_REGEX = re.compile(
    r'[._ \-](?:s|season)?(\d{1,3})[._ \-]?(?:e|ep|episode|x)(\d{1,3})[._ \-]|'
    r'[._ \-](\d{1,3})x(\d{1,3})[._ \-]',
    re.IGNORECASE
)

# Regex to clean up movie/series name before query
CLEAN_QUERY_REGEX = re.compile(
    r'(\b(?:19|20)\d{2}\b)|' r'(\b(?:720p|1080p|2160p|4k)\b)|'
    r'(\b(?:bluray|web.?dl|hdtv|dvd.?rip)\b)|' r'(\[.*?\])|' r'(\(.*?\))',
    re.IGNORECASE
)


class RetryStrategy:
    """
    Exponential backoff retry strategy.

    Implements automatic retry with exponential backoff intervals:
    - Retry 1: 10 seconds
    - Retry 2: 30 seconds
    - Retry 3: 1 minute

    Max 3 retries per phase before marking as failed.
    """

    RETRY_INTERVALS = [10, 30, 60]  # seconds
    MAX_RETRIES = 3

    def __init__(self):
        self.retry_counts = {}  # {item_id: retry_count}
        self.last_error = {}  # {item_id: error_details}

    def should_retry(self, item_id: str) -> bool:
        """Check if retry should be attempted"""
        retry_count = self.retry_counts.get(item_id, 0)
        return retry_count < self.MAX_RETRIES

    def get_retry_delay(self, item_id: str) -> int:
        """Get delay in seconds for next retry"""
        retry_count = self.retry_counts.get(item_id, 0)
        if retry_count >= len(self.RETRY_INTERVALS):
            return self.RETRY_INTERVALS[-1]
        return self.RETRY_INTERVALS[retry_count]

    def increment_retry(self, item_id: str):
        """Increment retry counter"""
        self.retry_counts[item_id] = self.retry_counts.get(item_id, 0) + 1

    def reset_retry(self, item_id: str):
        """Reset retry counter (call on phase change or success)"""
        if item_id in self.retry_counts:
            del self.retry_counts[item_id]
        if item_id in self.last_error:
            del self.last_error[item_id]

    def get_retry_count(self, item_id: str) -> int:
        """Get current retry count"""
        return self.retry_counts.get(item_id, 0)

    def set_error(self, item_id: str, error_message: str, error_details: str):
        """Store error details for later retrieval"""
        self.last_error[item_id] = {
            'message': error_message,
            'details': error_details,
            'retry_count': self.get_retry_count(item_id)
        }

    def get_error(self, item_id: str) -> Optional[Dict[str, Any]]:
        """Get stored error details"""
        return self.last_error.get(item_id)


class DownloadOrchestrator(QObject):
    """
    Coordinates the 3-phase download pipeline.

    Phases:
    1. Video Download: Download torrent, detect video file completion
    2. Subtitle Download: Search and download matching subtitle
    3. Translation: Translate subtitle to Polish

    Emits signals for UI updates and handles state persistence.
    """

    # Signals
    progress_updated = pyqtSignal(str, str, float, float)  # (item_id, phase, overall_progress, phase_progress)
    phase_changed = pyqtSignal(str, str)  # (item_id, phase_name)
    download_complete = pyqtSignal(str, str, str)  # (item_id, video_path, subtitle_path)
    download_failed = pyqtSignal(str, str, str)  # (item_id, phase, error_message)

    # Configuration
    MAX_CONCURRENT_DOWNLOADS = 2
    PROGRESS_UPDATE_INTERVAL_MS = 2000  # Update progress every 2 seconds
    VIDEO_EXTENSIONS = ('.mp4', '.mkv', '.avi', '.mov')

    def __init__(
        self,
        state_manager: DownloadStateManager,
        subtitle_manager: SubtitleManager,
        translator: SubtitleTranslator,
        download_dir: str = "~/Videos/HackFlix"
    ):
        """
        Initialize download orchestrator.

        Args:
            state_manager: DownloadStateManager instance
            subtitle_manager: SubtitleManager instance
            translator: SubtitleTranslator instance
            download_dir: Default download directory
        """
        super().__init__()

        self.state_manager = state_manager
        self.subtitle_manager = subtitle_manager
        self.translator = translator
        self.download_dir = os.path.expanduser(download_dir)

        # Ensure download directory exists
        Path(self.download_dir).mkdir(parents=True, exist_ok=True)

        # Torrent downloader (lazy initialization)
        self.torrent_downloader: Optional[TorrentDownloader] = None

        # Active downloads tracking
        self.active_downloads: Dict[str, Dict[str, Any]] = {}  # item_id -> download_info

        # Retry strategy for error recovery
        self.retry_strategy = RetryStrategy()

        # Retry timers for delayed retries
        self.retry_timers: Dict[str, QTimer] = {}  # item_id -> QTimer

        # Progress update timer
        self.progress_timer = QTimer(self)
        self.progress_timer.setInterval(self.PROGRESS_UPDATE_INTERVAL_MS)
        self.progress_timer.timeout.connect(self._update_all_progress)

        # Connect subtitle manager signals
        self.subtitle_manager.search_results.connect(self._on_subtitle_search_results)
        self.subtitle_manager.search_error.connect(self._on_subtitle_search_error)
        self.subtitle_manager.download_ready.connect(self._on_subtitle_download_ready)
        self.subtitle_manager.download_error.connect(self._on_subtitle_download_error)

        # Connect translator signals
        self.translator.translation_progress.connect(self._on_translation_progress)
        self.translator.translation_complete.connect(self._on_translation_complete)
        self.translator.translation_error.connect(self._on_translation_error)

        print("DownloadOrchestrator initialized")

    def start_download(
        self,
        item_id: str,
        item_type: str,
        magnet_link: str,
        title: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Start a new download.

        Args:
            item_id: Unique item identifier
            item_type: 'movie' or 'season'
            magnet_link: BitTorrent magnet URI
            title: Movie/series title for subtitle search
            metadata: Optional metadata (year, season, episode, etc.)

        Returns:
            True if download started successfully
        """
        # Check if already downloading
        if item_id in self.active_downloads:
            print(f"Download already active for {item_id}")
            return False

        # Check concurrent download limit
        if len(self.active_downloads) >= self.MAX_CONCURRENT_DOWNLOADS:
            print(f"Max concurrent downloads reached ({self.MAX_CONCURRENT_DOWNLOADS})")
            # TODO: Add to queue
            return False

        # Create download state in database
        success = self.state_manager.create_download(
            item_id=item_id,
            item_type=item_type,
            magnet_link=magnet_link,
            download_path=self.download_dir
        )

        if not success:
            print(f"Failed to create download state for {item_id}")
            return False

        # Initialize torrent downloader if needed
        if self.torrent_downloader is None:
            self.torrent_downloader = TorrentDownloader(save_path=self.download_dir)

        # Store download info
        self.active_downloads[item_id] = {
            'item_id': item_id,
            'item_type': item_type,
            'magnet_link': magnet_link,
            'title': title,
            'metadata': metadata or {},
            'phase': 'video',
            'video_path': None,
            'subtitle_path': None,
            'translated_subtitle_path': None,
            'torrent_handle': None,
            'subtitle_search_context': None,
            'translation_source_path': None
        }

        # Start torrent download
        self._start_video_download(item_id, magnet_link)

        # Start progress timer if not already running
        if not self.progress_timer.isActive():
            self.progress_timer.start()

        print(f"Started download for {item_id}")
        return True

    def _start_video_download(self, item_id: str, magnet_link: str):
        """
        Start video download phase.

        Args:
            item_id: Item identifier
            magnet_link: BitTorrent magnet URI
        """
        try:
            print(f"[{item_id}] Starting video download phase")

            # Add torrent
            success, torrent_handle = self.torrent_downloader.add_torrent(magnet_link)

            if not success:
                self._handle_video_download_error(item_id, "Failed to add torrent")
                return

            # Store torrent handle
            self.active_downloads[item_id]['torrent_handle'] = torrent_handle

            # Update phase
            self.state_manager.set_phase(item_id, 'video')
            self.phase_changed.emit(item_id, 'video')

        except Exception as e:
            self._handle_video_download_error(item_id, f"Error starting video download: {e}")

    def _update_all_progress(self):
        """
        Update progress for all active downloads.
        Called periodically by progress timer.
        """
        for item_id in list(self.active_downloads.keys()):
            download_info = self.active_downloads[item_id]
            phase = download_info['phase']

            if phase == 'video':
                self._update_video_progress(item_id)
            # Other phases emit their own progress signals

    def _update_video_progress(self, item_id: str):
        """
        Update progress for video download phase.

        Args:
            item_id: Item identifier
        """
        try:
            download_info = self.active_downloads[item_id]
            torrent_handle = download_info['torrent_handle']

            if torrent_handle is None:
                return

            # Get torrent status
            status = torrent_handle.status()

            # Calculate progress
            if status.total_wanted > 0:
                phase_progress = (status.progress * 100.0)
            else:
                phase_progress = 0.0

            # Update database
            self.state_manager.update_progress(item_id, 'video', phase_progress)

            # Emit signal
            overall_progress = self.state_manager._calculate_overall_progress('video', phase_progress)
            self.progress_updated.emit(item_id, 'video', overall_progress, phase_progress)

            # Check if video download complete
            if status.state == 5:  # seeding state (download complete)
                self._on_video_download_complete(item_id)

        except Exception as e:
            print(f"Error updating video progress for {item_id}: {e}")

    def _on_video_download_complete(self, item_id: str):
        """
        Handle video download completion.

        Args:
            item_id: Item identifier
        """
        try:
            print(f"[{item_id}] Video download complete")

            # Find video file
            video_path = self._find_video_file(item_id)

            if video_path is None:
                self._handle_video_download_error(item_id, "Video file not found after download")
                return

            # Validate video file
            is_valid, error_msg = self._validate_video_file(video_path)
            if not is_valid:
                self._handle_video_download_error(item_id, f"Video validation failed: {error_msg}")
                return

            print(f"  Video file validated successfully: {os.path.basename(video_path)}")

            # Store video path
            self.active_downloads[item_id]['video_path'] = video_path
            self.state_manager.set_video_path(item_id, video_path)

            # Reset retry counter on successful phase completion
            self.retry_strategy.reset_retry(item_id)

            # Move to subtitle phase
            self._start_subtitle_download(item_id, video_path)

        except Exception as e:
            self._handle_video_download_error(item_id, f"Error completing video download: {e}")

    def _find_video_file(self, item_id: str) -> Optional[str]:
        """
        Find downloaded video file in download directory.

        Args:
            item_id: Item identifier

        Returns:
            Path to video file or None if not found
        """
        try:
            download_info = self.active_downloads[item_id]
            torrent_handle = download_info['torrent_handle']

            if torrent_handle is None:
                return None

            # Get torrent info
            torrent_info = torrent_handle.torrent_file()

            if torrent_info is None:
                return None

            # Find largest video file
            files = torrent_info.files()
            video_files = []

            for i in range(files.num_files()):
                file_entry = files.at(i)
                file_path = file_entry.path
                file_size = file_entry.size

                # Check if video file
                if any(file_path.lower().endswith(ext) for ext in self.VIDEO_EXTENSIONS):
                    full_path = os.path.join(self.download_dir, file_path)
                    video_files.append((full_path, file_size))

            if not video_files:
                return None

            # Return largest video file
            video_files.sort(key=lambda x: x[1], reverse=True)
            return video_files[0][0]

        except Exception as e:
            print(f"Error finding video file for {item_id}: {e}")
            return None

    def _validate_video_file(self, video_path: str) -> tuple[bool, Optional[str]]:
        """
        Validate video file.

        Args:
            video_path: Path to video file

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Check file exists
            if not os.path.exists(video_path):
                return False, "Video file not found"

            # Check file size
            file_size = os.path.getsize(video_path)
            if file_size == 0:
                return False, "Video file is empty (0 bytes)"

            # Check minimum size (at least 1 MB)
            if file_size < 1024 * 1024:
                return False, f"Video file too small ({file_size} bytes)"

            # Check extension
            if not any(video_path.lower().endswith(ext) for ext in self.VIDEO_EXTENSIONS):
                return False, f"Invalid video file extension"

            return True, None

        except Exception as e:
            return False, f"Error validating video file: {e}"

    def _validate_subtitle_file(self, subtitle_path: str) -> tuple[bool, Optional[str]]:
        """
        Validate subtitle file.

        Args:
            subtitle_path: Path to subtitle file

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Check file exists
            if not os.path.exists(subtitle_path):
                return False, "Subtitle file not found"

            # Check file size
            file_size = os.path.getsize(subtitle_path)
            if file_size == 0:
                return False, "Subtitle file is empty (0 bytes)"

            # Check extension
            if not subtitle_path.lower().endswith('.srt'):
                return False, "Invalid subtitle file extension (must be .srt)"

            # Basic .srt syntax validation
            try:
                with open(subtitle_path, 'r', encoding='utf-8') as f:
                    content = f.read(1024)  # Read first 1KB

                    # Check for subtitle number (first line should be a number)
                    lines = content.strip().split('\n')
                    if len(lines) < 3:
                        return False, "Subtitle file appears to be corrupted (too short)"

                    # First line should be a number
                    if not lines[0].strip().isdigit():
                        return False, "Subtitle file has invalid format (missing subtitle number)"

                    # Second line should contain timestamp
                    if '-->' not in lines[1]:
                        return False, "Subtitle file has invalid format (missing timestamp)"

            except UnicodeDecodeError:
                # Try with different encoding
                try:
                    with open(subtitle_path, 'r', encoding='latin-1') as f:
                        content = f.read(100)
                except Exception:
                    return False, "Subtitle file has invalid encoding"

            return True, None

        except Exception as e:
            return False, f"Error validating subtitle file: {e}"

    def _start_subtitle_download(self, item_id: str, video_path: str):
        """
        Start subtitle download phase.

        Args:
            item_id: Item identifier
            video_path: Path to downloaded video file
        """
        try:
            print(f"[{item_id}] Starting subtitle download phase")

            # Update phase
            self.state_manager.set_phase(item_id, 'subtitles')
            self.phase_changed.emit(item_id, 'subtitles')

            # Extract filename and metadata
            filename = os.path.basename(video_path)
            base_query = os.path.splitext(filename)[0]

            # Detect season/episode
            season = None
            episode = None
            search_type = 'movie'
            cleaned_query = base_query

            test_name = filename.replace('.', ' ').replace('_', ' ')
            match = SEASON_EPISODE_REGEX.search(test_name)

            if match:
                groups = match.groups()
                if groups[0] is not None and groups[1] is not None:
                    season = int(groups[0])
                    episode = int(groups[1])
                    search_type = 'episode'
                elif groups[2] is not None and groups[3] is not None:
                    season = int(groups[2])
                    episode = int(groups[3])
                    search_type = 'episode'

                if season is not None and episode is not None:
                    pattern_str = match.group(0).strip('._ -')
                    cleaned_query = base_query.replace(pattern_str, '', 1).strip('._ -')
                    cleaned_query = CLEAN_QUERY_REGEX.sub('', cleaned_query).strip('._ -')
                    cleaned_query = re.sub(r'[._\-]+', ' ', cleaned_query).strip()
                else:
                    cleaned_query = CLEAN_QUERY_REGEX.sub('', base_query).strip('._ -')
                    cleaned_query = re.sub(r'[._\-]+', ' ', cleaned_query).strip()
            else:
                cleaned_query = CLEAN_QUERY_REGEX.sub('', base_query).strip('._ -')
                cleaned_query = re.sub(r'[._\-]+', ' ', cleaned_query).strip()

            # Store context for subtitle download
            self.active_downloads[item_id]['subtitle_search_context'] = {
                'video_path': video_path,
                'query': cleaned_query,
                'season': season,
                'episode': episode,
                'type': search_type
            }

            # Search for subtitles (prefer English for translation)
            languages = "en,pl"
            print(f"[{item_id}] Searching subtitles: type={search_type}, query='{cleaned_query}', season={season}, episode={episode}")

            self.subtitle_manager.search_subtitles(
                query=cleaned_query,
                languages=languages,
                season=season,
                episode=episode,
                type=search_type
            )

        except Exception as e:
            self._handle_subtitle_download_error(item_id, f"Error starting subtitle download: {e}")

    @pyqtSlot(list)
    def _on_subtitle_search_results(self, results: list):
        """
        Handle subtitle search results.

        Args:
            results: List of subtitle search results
        """
        # Find which download this belongs to
        item_id = self._find_download_in_subtitle_phase()

        if item_id is None:
            print("Warning: Received subtitle search results but no download in subtitle phase")
            return

        try:
            print(f"[{item_id}] Received {len(results)} subtitle results")

            if not results:
                self._handle_subtitle_download_error(item_id, "No subtitles found")
                return

            # Prefer English subtitles for translation
            results.sort(key=lambda x: (x.get('language') != 'en',))

            # Download best match
            best_match = results[0]
            file_id = best_match.get('file_id')

            if not file_id:
                self._handle_subtitle_download_error(item_id, "No file ID in search results")
                return

            print(f"[{item_id}] Requesting subtitle download for file ID: {file_id}")
            self.subtitle_manager.request_download(file_id)

            # Update progress (50% of subtitle phase = search complete)
            self.state_manager.update_progress(item_id, 'subtitles', 50.0)
            overall_progress = self.state_manager._calculate_overall_progress('subtitles', 50.0)
            self.progress_updated.emit(item_id, 'subtitles', overall_progress, 50.0)

        except Exception as e:
            self._handle_subtitle_download_error(item_id, f"Error processing subtitle results: {e}")

    @pyqtSlot(str)
    def _on_subtitle_search_error(self, error_message: str):
        """
        Handle subtitle search error.

        Args:
            error_message: Error message from SubtitleManager
        """
        item_id = self._find_download_in_subtitle_phase()

        if item_id is None:
            print(f"Warning: Received subtitle search error but no download in subtitle phase")
            return

        self._handle_subtitle_download_error(item_id, f"Subtitle search failed: {error_message}")

    @pyqtSlot(str, str)
    def _on_subtitle_download_ready(self, download_link: str, suggested_filename: str):
        """
        Handle subtitle download link ready.

        Args:
            download_link: URL to download subtitle
            suggested_filename: Suggested filename from API
        """
        item_id = self._find_download_in_subtitle_phase()

        if item_id is None:
            print("Warning: Received subtitle download link but no download in subtitle phase")
            return

        try:
            print(f"[{item_id}] Subtitle download link received")

            # Get context
            context = self.active_downloads[item_id]['subtitle_search_context']
            video_path = context['video_path']

            # Determine save path
            video_dir = os.path.dirname(video_path)
            video_base = os.path.splitext(os.path.basename(video_path))[0]
            subtitle_filename = f"{video_base}.en.srt"
            save_path = os.path.join(video_dir, subtitle_filename)

            # Download subtitle in background thread
            def download_worker():
                success, error = self.subtitle_manager.download_subtitle_file(download_link, save_path)

                if success:
                    # Validate subtitle file
                    is_valid, error_msg = self._validate_subtitle_file(save_path)
                    if not is_valid:
                        self._handle_subtitle_download_error(item_id, f"Subtitle validation failed: {error_msg}")
                        return

                    print(f"  Subtitle file validated successfully: {os.path.basename(save_path)}")

                    # Update progress (100% of subtitle phase)
                    self.state_manager.update_progress(item_id, 'subtitles', 100.0)
                    overall_progress = self.state_manager._calculate_overall_progress('subtitles', 100.0)
                    self.progress_updated.emit(item_id, 'subtitles', overall_progress, 100.0)

                    # Store subtitle path
                    self.active_downloads[item_id]['subtitle_path'] = save_path
                    self.state_manager.set_subtitle_path(item_id, save_path)

                    # Reset retry counter on successful phase completion
                    self.retry_strategy.reset_retry(item_id)

                    # Move to translation phase
                    self._start_translation(item_id, save_path)
                else:
                    self._handle_subtitle_download_error(item_id, f"Subtitle download failed: {error}")

            thread = threading.Thread(target=download_worker, daemon=True)
            thread.start()

        except Exception as e:
            self._handle_subtitle_download_error(item_id, f"Error downloading subtitle: {e}")

    @pyqtSlot(str)
    def _on_subtitle_download_error(self, error_message: str):
        """
        Handle subtitle download error.

        Args:
            error_message: Error message from SubtitleManager
        """
        item_id = self._find_download_in_subtitle_phase()

        if item_id is None:
            print(f"Warning: Received subtitle download error but no download in subtitle phase")
            return

        self._handle_subtitle_download_error(item_id, f"Subtitle download failed: {error_message}")

    def _start_translation(self, item_id: str, subtitle_path: str):
        """
        Start translation phase.

        Args:
            item_id: Item identifier
            subtitle_path: Path to subtitle file to translate
        """
        try:
            print(f"[{item_id}] Starting translation phase")

            # Update phase
            self.state_manager.set_phase(item_id, 'translation')
            self.phase_changed.emit(item_id, 'translation')

            # Store translation source path
            self.active_downloads[item_id]['translation_source_path'] = subtitle_path

            # Start translation
            self.translator.translate_srt_file(subtitle_path)

        except Exception as e:
            self._handle_translation_error(item_id, f"Error starting translation: {e}")

    @pyqtSlot(int, int)
    def _on_translation_progress(self, current_batch: int, total_batches: int):
        """
        Handle translation progress update.

        Args:
            current_batch: Current batch number
            total_batches: Total number of batches
        """
        item_id = self._find_download_in_translation_phase()

        if item_id is None:
            return

        try:
            # Calculate progress
            phase_progress = (current_batch / total_batches) * 100.0

            # Update database
            self.state_manager.update_progress(item_id, 'translation', phase_progress)

            # Emit signal
            overall_progress = self.state_manager._calculate_overall_progress('translation', phase_progress)
            self.progress_updated.emit(item_id, 'translation', overall_progress, phase_progress)

        except Exception as e:
            print(f"Error updating translation progress for {item_id}: {e}")

    @pyqtSlot(str, str)
    def _on_translation_complete(self, original_path: str, translated_path: str):
        """
        Handle translation completion.

        Args:
            original_path: Path to original subtitle file
            translated_path: Path to translated subtitle file
        """
        item_id = self._find_download_in_translation_phase()

        if item_id is None:
            print("Warning: Received translation complete but no download in translation phase")
            return

        try:
            print(f"[{item_id}] Translation complete: {translated_path}")

            # Validate translated subtitle file
            is_valid, error_msg = self._validate_subtitle_file(translated_path)
            if not is_valid:
                self._handle_translation_error(item_id, f"Translated subtitle validation failed: {error_msg}")
                return

            print(f"  Translated subtitle validated successfully: {os.path.basename(translated_path)}")

            # Store translated subtitle path
            self.active_downloads[item_id]['translated_subtitle_path'] = translated_path
            self.state_manager.set_translated_subtitle_path(item_id, translated_path)

            # Update progress to 100%
            self.state_manager.update_progress(item_id, 'translation', 100.0)
            self.progress_updated.emit(item_id, 'translation', 100.0, 100.0)

            # Reset retry counter on successful completion
            self.retry_strategy.reset_retry(item_id)

            # Mark download as complete
            self._complete_download(item_id)

        except Exception as e:
            self._handle_translation_error(item_id, f"Error completing translation: {e}")

    @pyqtSlot(str, str)
    def _on_translation_error(self, original_path: str, error_message: str):
        """
        Handle translation error.

        Args:
            original_path: Path to original subtitle file
            error_message: Error message from translator
        """
        item_id = self._find_download_in_translation_phase()

        if item_id is None:
            print(f"Warning: Received translation error but no download in translation phase")
            return

        self._handle_translation_error(item_id, f"Translation failed: {error_message}")

    def _complete_download(self, item_id: str):
        """
        Mark download as complete.

        Args:
            item_id: Item identifier
        """
        try:
            download_info = self.active_downloads[item_id]

            video_path = download_info['video_path']
            translated_subtitle_path = download_info['translated_subtitle_path']

            # Update database status
            self.state_manager.set_status(item_id, 'ready')

            # Emit completion signal
            self.download_complete.emit(item_id, video_path, translated_subtitle_path)

            # Remove from active downloads
            del self.active_downloads[item_id]

            print(f"[{item_id}] Download complete!")

            # Stop progress timer if no active downloads
            if not self.active_downloads:
                self.progress_timer.stop()

        except Exception as e:
            print(f"Error completing download for {item_id}: {e}")

    def _handle_video_download_error(self, item_id: str, error_message: str):
        """Handle error during video download phase with auto-retry"""
        # Get full traceback for error details
        error_details = traceback.format_exc()

        print(f"[{item_id}] Video download error: {error_message}")
        print(f"  Retry count: {self.retry_strategy.get_retry_count(item_id)}")

        # Store error in retry strategy
        self.retry_strategy.set_error(item_id, error_message, error_details)

        # Check if we should retry
        if self.retry_strategy.should_retry(item_id):
            retry_delay = self.retry_strategy.get_retry_delay(item_id)
            self.retry_strategy.increment_retry(item_id)

            print(f"  Auto-retrying in {retry_delay} seconds (attempt {self.retry_strategy.get_retry_count(item_id)}/{RetryStrategy.MAX_RETRIES})")

            # Schedule retry
            retry_timer = QTimer(self)
            retry_timer.setSingleShot(True)
            retry_timer.timeout.connect(lambda: self._retry_video_download(item_id))
            retry_timer.start(retry_delay * 1000)  # Convert to milliseconds
            self.retry_timers[item_id] = retry_timer

        else:
            # Max retries exceeded - mark as permanently failed
            print(f"  Max retries exceeded - marking as failed")
            self.state_manager.set_status(item_id, 'failed', error_message, error_details)
            self.download_failed.emit(item_id, 'video', error_message)

            # Cleanup partial files (keep video if it exists)
            self._cleanup_failed_download(item_id, keep_video=True)

            # Cleanup
            self.retry_strategy.reset_retry(item_id)
            if item_id in self.active_downloads:
                del self.active_downloads[item_id]
            if not self.active_downloads:
                self.progress_timer.stop()

    def _handle_subtitle_download_error(self, item_id: str, error_message: str):
        """Handle error during subtitle download phase with auto-retry"""
        # Get full traceback for error details
        error_details = traceback.format_exc()

        print(f"[{item_id}] Subtitle download error: {error_message}")
        print(f"  Retry count: {self.retry_strategy.get_retry_count(item_id)}")

        # Store error in retry strategy
        self.retry_strategy.set_error(item_id, error_message, error_details)

        # Check if we should retry
        if self.retry_strategy.should_retry(item_id):
            retry_delay = self.retry_strategy.get_retry_delay(item_id)
            self.retry_strategy.increment_retry(item_id)

            print(f"  Auto-retrying in {retry_delay} seconds (attempt {self.retry_strategy.get_retry_count(item_id)}/{RetryStrategy.MAX_RETRIES})")

            # Schedule retry
            retry_timer = QTimer(self)
            retry_timer.setSingleShot(True)
            retry_timer.timeout.connect(lambda: self._retry_subtitle_download(item_id))
            retry_timer.start(retry_delay * 1000)
            self.retry_timers[item_id] = retry_timer

        else:
            # Max retries exceeded - mark as permanently failed
            print(f"  Max retries exceeded - marking as failed")
            self.state_manager.set_status(item_id, 'failed', error_message, error_details)
            self.download_failed.emit(item_id, 'subtitles', error_message)

            # Cleanup partial files (keep video, remove subtitles)
            self._cleanup_failed_download(item_id, keep_video=True)

            # Cleanup
            self.retry_strategy.reset_retry(item_id)
            if item_id in self.active_downloads:
                del self.active_downloads[item_id]
            if not self.active_downloads:
                self.progress_timer.stop()

    def _handle_translation_error(self, item_id: str, error_message: str):
        """Handle error during translation phase with auto-retry"""
        # Get full traceback for error details
        error_details = traceback.format_exc()

        print(f"[{item_id}] Translation error: {error_message}")
        print(f"  Retry count: {self.retry_strategy.get_retry_count(item_id)}")

        # Store error in retry strategy
        self.retry_strategy.set_error(item_id, error_message, error_details)

        # Check if we should retry
        if self.retry_strategy.should_retry(item_id):
            retry_delay = self.retry_strategy.get_retry_delay(item_id)
            self.retry_strategy.increment_retry(item_id)

            print(f"  Auto-retrying in {retry_delay} seconds (attempt {self.retry_strategy.get_retry_count(item_id)}/{RetryStrategy.MAX_RETRIES})")

            # Schedule retry
            retry_timer = QTimer(self)
            retry_timer.setSingleShot(True)
            retry_timer.timeout.connect(lambda: self._retry_translation(item_id))
            retry_timer.start(retry_delay * 1000)
            self.retry_timers[item_id] = retry_timer

        else:
            # Max retries exceeded - mark as permanently failed
            print(f"  Max retries exceeded - marking as translation_failed")
            self.state_manager.set_status(item_id, 'translation_failed', error_message, error_details)
            self.download_failed.emit(item_id, 'translation', error_message)

            # Cleanup partial files (keep video and original subtitle)
            self._cleanup_failed_download(item_id, keep_video=True)

            # Cleanup
            self.retry_strategy.reset_retry(item_id)
            if item_id in self.active_downloads:
                del self.active_downloads[item_id]
            if not self.active_downloads:
                self.progress_timer.stop()

    def _retry_video_download(self, item_id: str):
        """Retry video download phase after error"""
        print(f"[{item_id}] Retrying video download...")

        # Get download info
        if item_id not in self.active_downloads:
            print(f"  Error: Download info not found for {item_id}")
            return

        download_info = self.active_downloads[item_id]
        magnet_link = download_info.get('magnet_link')

        if not magnet_link:
            print(f"  Error: Magnet link not found for {item_id}")
            return

        # Restart video download
        try:
            if not self.torrent_downloader:
                self.torrent_downloader = TorrentDownloader(download_dir=self.download_dir)

            # Start torrent download
            self.torrent_downloader.add_torrent(magnet_link)

            # Reset state to downloading
            self.state_manager.set_status(item_id, 'downloading')
            self.state_manager.set_phase(item_id, 'video')

            print(f"  Video download restarted successfully")

        except Exception as e:
            self._handle_video_download_error(item_id, f"Error retrying video download: {e}")

    def _retry_subtitle_download(self, item_id: str):
        """Retry subtitle download phase after error"""
        print(f"[{item_id}] Retrying subtitle download...")

        # Get download info
        if item_id not in self.active_downloads:
            print(f"  Error: Download info not found for {item_id}")
            return

        download_info = self.active_downloads[item_id]
        video_path = download_info.get('video_path')

        if not video_path:
            print(f"  Error: Video path not found for {item_id}")
            return

        # Restart subtitle download
        try:
            self._start_subtitle_download(item_id, video_path)
            print(f"  Subtitle download restarted successfully")

        except Exception as e:
            self._handle_subtitle_download_error(item_id, f"Error retrying subtitle download: {e}")

    def _retry_translation(self, item_id: str):
        """Retry translation phase after error"""
        print(f"[{item_id}] Retrying translation...")

        # Get download info
        if item_id not in self.active_downloads:
            print(f"  Error: Download info not found for {item_id}")
            return

        download_info = self.active_downloads[item_id]
        subtitle_path = download_info.get('subtitle_path')

        if not subtitle_path:
            print(f"  Error: Subtitle path not found for {item_id}")
            return

        # Restart translation
        try:
            self._start_translation(item_id, subtitle_path)
            print(f"  Translation restarted successfully")

        except Exception as e:
            self._handle_translation_error(item_id, f"Error retrying translation: {e}")

    def _find_download_in_subtitle_phase(self) -> Optional[str]:
        """Find item_id for download currently in subtitle phase"""
        for item_id, info in self.active_downloads.items():
            if info['phase'] == 'subtitles':
                return item_id
        return None

    def _find_download_in_translation_phase(self) -> Optional[str]:
        """Find item_id for download currently in translation phase"""
        for item_id, info in self.active_downloads.items():
            if info['phase'] == 'translation':
                return item_id
        return None

    def pause_download(self, item_id: str) -> bool:
        """
        Pause active download.

        Args:
            item_id: Item identifier

        Returns:
            True if paused successfully
        """
        # TODO: Implement pause functionality
        print(f"Pause not yet implemented for {item_id}")
        return False

    def resume_download(self, item_id: str) -> bool:
        """
        Resume paused download.

        Args:
            item_id: Item identifier

        Returns:
            True if resumed successfully
        """
        # TODO: Implement resume functionality
        print(f"Resume not yet implemented for {item_id}")
        return False

    def cancel_download(self, item_id: str) -> bool:
        """
        Cancel active download.

        Args:
            item_id: Item identifier

        Returns:
            True if cancelled successfully
        """
        if item_id not in self.active_downloads:
            return False

        try:
            # Remove torrent if in video phase
            download_info = self.active_downloads[item_id]
            if download_info['phase'] == 'video' and download_info['torrent_handle']:
                # TODO: Remove torrent from downloader
                pass

            # Delete from database
            self.state_manager.delete_download(item_id)

            # Remove from active downloads
            del self.active_downloads[item_id]

            print(f"Cancelled download: {item_id}")
            return True

        except Exception as e:
            print(f"Error cancelling download for {item_id}: {e}")
            return False

    def _cleanup_failed_download(self, item_id: str, keep_video: bool = True):
        """
        Cleanup partial files after download failure.

        Args:
            item_id: Item identifier
            keep_video: If True, keep video file (default), otherwise remove all files
        """
        try:
            print(f"[{item_id}] Cleaning up failed download...")

            if item_id not in self.active_downloads:
                print(f"  Warning: Download info not found for cleanup")
                return

            download_info = self.active_downloads[item_id]

            # Get file paths
            video_path = download_info.get('video_path')
            subtitle_path = download_info.get('subtitle_path')
            translated_subtitle_path = download_info.get('translated_subtitle_path')

            # Cleanup subtitle files (always safe to remove and re-download)
            if subtitle_path and os.path.exists(subtitle_path):
                try:
                    os.remove(subtitle_path)
                    print(f"  Removed subtitle file: {os.path.basename(subtitle_path)}")
                except Exception as e:
                    print(f"  Warning: Could not remove subtitle file: {e}")

            if translated_subtitle_path and os.path.exists(translated_subtitle_path):
                try:
                    os.remove(translated_subtitle_path)
                    print(f"  Removed translated subtitle: {os.path.basename(translated_subtitle_path)}")
                except Exception as e:
                    print(f"  Warning: Could not remove translated subtitle: {e}")

            # Cleanup video file (only if keep_video=False)
            if not keep_video and video_path and os.path.exists(video_path):
                try:
                    # Check if file is incomplete (size check)
                    file_size = os.path.getsize(video_path)
                    if file_size < 100 * 1024 * 1024:  # Less than 100 MB = likely incomplete
                        os.remove(video_path)
                        print(f"  Removed incomplete video file: {os.path.basename(video_path)}")
                    else:
                        print(f"  Keeping video file (appears complete): {os.path.basename(video_path)}")
                except Exception as e:
                    print(f"  Warning: Could not remove video file: {e}")

            # Cancel retry timers
            if item_id in self.retry_timers:
                self.retry_timers[item_id].stop()
                del self.retry_timers[item_id]

            print(f"  Cleanup complete")

        except Exception as e:
            print(f"Error during cleanup for {item_id}: {e}")
            traceback.print_exc()

    def shutdown(self):
        """Shutdown orchestrator and cleanup resources"""
        print("Shutting down download orchestrator...")

        # Stop progress timer
        self.progress_timer.stop()

        # Shutdown torrent downloader
        if self.torrent_downloader:
            self.torrent_downloader.shutdown()

        print("Download orchestrator shutdown complete")
