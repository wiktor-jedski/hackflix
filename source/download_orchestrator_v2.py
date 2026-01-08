"""
Download Orchestrator V2 - Parallel Download Architecture

Key improvements over V1:
1. Parallel video + subtitle downloads for movies
2. Smart resume logic - checks what's already completed
3. Subtitle queue manager for series (5/day limit)
4. Component-level status tracking (video_status, subtitle_status, translation_status)
5. Dual progress bars (video_progress, subtitle_progress)
6. Fixed threading issues with QTimer
"""

import os
import re
import threading
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import date, datetime
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, QTimer

from source.download_state_manager_v2 import DownloadStateManagerV2
from source.torrent_manager import TorrentDownloader
from source.subtitle_manager import SubtitleManager
from source.translation_manager import SubtitleTranslator


# Regex for Season/Episode Extraction
SEASON_EPISODE_REGEX = re.compile(
    r'[._ \-](?:s|season)?(\d{1,3})[._ \-]?(?:e|ep|episode|x)(\d{1,3})[._ \-]|'
    r'[._ \-](\d{1,3})x(\d{1,3})[._ \-]',
    re.IGNORECASE
)


class SubtitleQueueManager(QObject):
    """
    Manages subtitle download queue for series episodes.
    Respects 5 downloads/day API limit.
    """

    quota_exceeded = pyqtSignal(int)  # Emitted when quota exceeded (remaining_today)

    DAILY_QUOTA = 5

    def __init__(self, state_manager: 'DownloadStateManagerV2'):
        super().__init__()
        self.state_manager = state_manager
        self.queue: List[Dict[str, Any]] = []  # List of {item_id, video_path, file_id, ...}
        self.processing = False

    def get_quota_info(self) -> Dict[str, int]:
        """
        Get quota usage info for today.

        Returns:
            Dict with 'used', 'remaining', 'date'
        """
        today = date.today().isoformat()
        quota_data = self.state_manager.get_quota_info()

        quota_date = quota_data.get('date', '')
        quota_used = quota_data.get('used', 0)

        # Reset quota if new day
        if quota_date != today:
            quota_used = 0

        remaining = max(0, self.DAILY_QUOTA - quota_used)

        return {
            'used': quota_used,
            'remaining': remaining,
            'date': today,
            'total': self.DAILY_QUOTA
        }

    def can_download_subtitle(self) -> bool:
        """Check if subtitle download is allowed (quota not exceeded)"""
        quota_info = self.get_quota_info()
        return quota_info['remaining'] > 0

    def increment_quota(self):
        """Increment daily subtitle download count"""
        today = date.today().isoformat()
        self.state_manager.increment_quota(today)

    def add_to_queue(self, item_id: str, video_path: str, subtitle_config: Dict[str, Any]):
        """
        Add subtitle download to queue.

        Args:
            item_id: Item identifier
            video_path: Path to video file
            subtitle_config: Dict with file_id, language, needs_translation
        """
        self.queue.append({
            'item_id': item_id,
            'video_path': video_path,
            'file_id': subtitle_config.get('file_id'),
            'language': subtitle_config.get('language', 'en'),
            'needs_translation': subtitle_config.get('needs_translation', True)
        })

        print(f"[Queue] Added {item_id} to subtitle queue (queue size: {len(self.queue)})")

    def process_queue(self):
        """Process queued subtitle downloads if quota allows"""
        if self.processing:
            return

        if not self.queue:
            return

        quota_info = self.get_quota_info()
        if quota_info['remaining'] <= 0:
            print(f"[Queue] Quota exceeded - {quota_info['used']}/{quota_info['total']} used today")
            self.quota_exceeded.emit(quota_info['remaining'])
            return

        self.processing = True

        # Process items up to remaining quota
        items_to_process = min(len(self.queue), quota_info['remaining'])

        print(f"[Queue] Processing {items_to_process} subtitle downloads (quota: {quota_info['remaining']} remaining)")

        for i in range(items_to_process):
            if not self.queue:
                break

            item = self.queue.pop(0)
            # TODO: Trigger subtitle download
            # This will be handled by the orchestrator
            print(f"[Queue] Processing subtitle for {item['item_id']}")

        self.processing = False


class DownloadOrchestratorV2(QObject):
    """
    Orchestrates parallel video + subtitle downloads with smart resume.

    Features:
    - Parallel video + subtitle downloads for movies
    - Smart resume (checks what's completed)
    - Subtitle queue for series (respects 5/day limit)
    - Component-level progress tracking
    - Dual progress bars for UI
    """

    # Signals - Dual progress bars
    video_progress_updated = pyqtSignal(str, float)  # (item_id, progress 0-100)
    subtitle_progress_updated = pyqtSignal(str, float)  # (item_id, progress 0-100)

    # Status signals
    video_status_changed = pyqtSignal(str, str)  # (item_id, status)
    subtitle_status_changed = pyqtSignal(str, str)  # (item_id, status)

    # Completion signals
    download_complete = pyqtSignal(str, str, str)  # (item_id, video_path, subtitle_path)
    download_failed = pyqtSignal(str, str, str)  # (item_id, component, error_message)

    # Quota signal
    subtitle_quota_exceeded = pyqtSignal(int)  # (remaining)

    # Configuration
    MAX_CONCURRENT_DOWNLOADS = 2
    PROGRESS_UPDATE_INTERVAL_MS = 2000
    VIDEO_EXTENSIONS = ('.mp4', '.mkv', '.avi', '.mov')
    SUBTITLE_RETRY_DELAY_SECONDS = 10
    MAX_RETRIES = 3

    def __init__(
        self,
        state_manager: DownloadStateManagerV2,
        subtitle_manager: SubtitleManager,
        translator: SubtitleTranslator,
        download_dir: str = "~/Videos/HackFlix"
    ):
        """
        Initialize download orchestrator V2.

        Args:
            state_manager: DownloadStateManagerV2 instance
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

        # Subtitle queue manager
        self.subtitle_queue = SubtitleQueueManager(state_manager)
        self.subtitle_queue.quota_exceeded.connect(self.subtitle_quota_exceeded.emit)

        # Progress update timer
        self.progress_timer = QTimer(self)
        self.progress_timer.setInterval(self.PROGRESS_UPDATE_INTERVAL_MS)
        self.progress_timer.timeout.connect(self._update_all_progress)

        # Retry timers (item_id -> QTimer)
        self.retry_timers: Dict[str, QTimer] = {}

        # Connect subtitle manager signals
        self.subtitle_manager.download_ready.connect(self._on_subtitle_download_ready)
        self.subtitle_manager.download_error.connect(self._on_subtitle_download_error)

        # Connect translator signals
        self.translator.translation_progress.connect(self._on_translation_progress)
        self.translator.translation_complete.connect(self._on_translation_complete)
        self.translator.translation_error.connect(self._on_translation_error)

        print("DownloadOrchestratorV2 initialized")

    def start_download(
        self,
        item_id: str,
        item_type: str,
        magnet_link: str,
        title: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Start or resume a download with smart resume logic.

        Args:
            item_id: Unique item identifier
            item_type: 'movie' or 'season'
            magnet_link: BitTorrent magnet URI
            title: Movie/series title
            metadata: Optional metadata (year, subtitle config, etc.)

        Returns:
            True if download started/resumed successfully
        """
        # Check if already downloading
        if item_id in self.active_downloads:
            print(f"Download already active for {item_id}")
            return False

        # Check concurrent download limit
        if len(self.active_downloads) >= self.MAX_CONCURRENT_DOWNLOADS:
            print(f"Max concurrent downloads reached ({self.MAX_CONCURRENT_DOWNLOADS})")
            return False

        # Get or create download state
        state = self.state_manager.get_download_state(item_id)
        if not state:
            # Create new download entry
            self.state_manager.create_download(item_id, item_type, magnet_link, self.download_dir)
            state = self.state_manager.get_download_state(item_id)

        # Extract subtitle configuration
        subtitle_info = (metadata or {}).get('subtitle', {})
        subtitle_file_id = subtitle_info.get('file_id')
        subtitle_language = subtitle_info.get('language', 'en')
        needs_translation = subtitle_info.get('needs_translation', True)

        print(f"[{item_id}] Starting/resuming download")
        print(f"  Subtitle config: file_id={subtitle_file_id}, lang={subtitle_language}, needs_translation={needs_translation}")

        # Initialize torrent downloader if needed
        if self.torrent_downloader is None:
            self.torrent_downloader = TorrentDownloader(download_dir=self.download_dir)

        # Store download info
        self.active_downloads[item_id] = {
            'item_id': item_id,
            'item_type': item_type,
            'magnet_link': magnet_link,
            'title': title,
            'metadata': metadata or {},
            'subtitle_file_id': subtitle_file_id,
            'subtitle_language': subtitle_language,
            'needs_translation': needs_translation,
            'video_path': None,
            'subtitle_path': None,
            'translated_subtitle_path': None,
            'torrent_handle': None,
            'retry_count': {
                'video': 0,
                'subtitle': 0,
                'translation': 0
            }
        }

        # Smart resume: Check what's already completed
        self._smart_resume(item_id, state, magnet_link)

        # Start progress timer if not already running
        if not self.progress_timer.isActive():
            self.progress_timer.start()

        return True

    def _smart_resume(self, item_id: str, state: Dict[str, Any], magnet_link: str):
        """
        Smart resume logic - check what's completed and resume from there.

        Args:
            item_id: Item identifier
            state: Current download state from database
            magnet_link: Magnet link for torrent
        """
        download_info = self.active_downloads[item_id]

        # Check video status
        video_status = state.get('video_status', 'pending')
        video_path = state.get('download_path')

        if video_status == 'completed' and video_path and os.path.exists(video_path):
            # Video already downloaded and validated
            print(f"[{item_id}] Video already completed: {os.path.basename(video_path)}")
            download_info['video_path'] = video_path
            self.state_manager.set_video_status(item_id, 'completed')
            self.video_status_changed.emit(item_id, 'completed')
            self.video_progress_updated.emit(item_id, 100.0)
        else:
            # Start/resume video download
            print(f"[{item_id}] Starting video download")
            self._start_video_download(item_id, magnet_link)

        # Check subtitle status
        subtitle_status = state.get('subtitle_status', 'pending')
        subtitle_path = state.get('subtitle_path')

        if subtitle_status == 'completed' and subtitle_path and os.path.exists(subtitle_path):
            # Subtitle already downloaded
            print(f"[{item_id}] Subtitle already completed: {os.path.basename(subtitle_path)}")
            download_info['subtitle_path'] = subtitle_path
            self.subtitle_status_changed.emit(item_id, 'completed')
            self.subtitle_progress_updated.emit(item_id, 100.0 if not download_info['needs_translation'] else 50.0)
        else:
            # Start subtitle download (if video is ready or parallel download for movies)
            if download_info['item_type'] == 'movie':
                # For movies, start subtitle download immediately (parallel)
                print(f"[{item_id}] Starting subtitle download (parallel with video)")
                self._start_subtitle_download(item_id, video_path or "")  # Path might not be known yet
            # For series, wait for video to complete

        # Check translation status
        translation_status = state.get('translation_status', 'pending')
        translated_path = state.get('translated_subtitle_path')

        if translation_status == 'completed' and translated_path and os.path.exists(translated_path):
            # Translation already completed
            print(f"[{item_id}] Translation already completed: {os.path.basename(translated_path)}")
            download_info['translated_subtitle_path'] = translated_path
            self.subtitle_progress_updated.emit(item_id, 100.0)

        # Check if everything is complete
        if (video_status == 'completed' and
            subtitle_status == 'completed' and
            (not download_info['needs_translation'] or translation_status == 'completed')):
            print(f"[{item_id}] All components already complete - marking as ready")
            self._complete_download(item_id)

    def _start_video_download(self, item_id: str, magnet_link: str):
        """
        Start video download phase.

        Args:
            item_id: Item identifier
            magnet_link: BitTorrent magnet URI
        """
        try:
            download_info = self.active_downloads[item_id]
            title = download_info['title']

            # Add torrent
            torrent_hash = self.torrent_downloader.add_torrent(magnet_link, title=title)

            if not torrent_hash:
                self._handle_error(item_id, 'video', "Failed to add torrent")
                return

            print(f"[{item_id}] Torrent added: {torrent_hash}")

            # Store torrent hash
            download_info['torrent_handle'] = torrent_hash

            # Update status
            self.state_manager.set_video_status(item_id, 'downloading')
            self.video_status_changed.emit(item_id, 'downloading')

        except Exception as e:
            self._handle_error(item_id, 'video', f"Error starting video download: {e}")

    def _start_subtitle_download(self, item_id: str, video_path: str):
        """
        Start subtitle download phase.

        Args:
            item_id: Item identifier
            video_path: Path to video file (may be empty for parallel downloads)
        """
        try:
            download_info = self.active_downloads[item_id]
            subtitle_file_id = download_info.get('subtitle_file_id')

            if not subtitle_file_id:
                print(f"[{item_id}] No subtitle file_id - skipping subtitle download")
                self.state_manager.set_subtitle_status(item_id, 'not_needed')
                self.subtitle_status_changed.emit(item_id, 'not_needed')
                return

            # Check quota for series
            if download_info['item_type'] == 'season':
                if not self.subtitle_queue.can_download_subtitle():
                    print(f"[{item_id}] Subtitle quota exceeded - adding to queue")
                    self.subtitle_queue.add_to_queue(item_id, video_path, {
                        'file_id': subtitle_file_id,
                        'language': download_info['subtitle_language'],
                        'needs_translation': download_info['needs_translation']
                    })
                    self.subtitle_queue_exceeded.emit(self.subtitle_queue.get_quota_info()['remaining'])
                    return

            print(f"[{item_id}] Requesting subtitle download: file_id={subtitle_file_id}")

            # Update status
            self.state_manager.set_subtitle_status(item_id, 'downloading')
            self.subtitle_status_changed.emit(item_id, 'downloading')

            # Request download
            self.subtitle_manager.request_download(subtitle_file_id)

            # Increment quota for series
            if download_info['item_type'] == 'season':
                self.subtitle_queue.increment_quota()

        except Exception as e:
            self._handle_error(item_id, 'subtitle', f"Error starting subtitle download: {e}")

    def _update_all_progress(self):
        """Update progress for all active downloads"""
        for item_id in list(self.active_downloads.keys()):
            self._update_video_progress(item_id)

    def _update_video_progress(self, item_id: str):
        """Update video download progress"""
        try:
            if item_id not in self.active_downloads:
                return

            download_info = self.active_downloads[item_id]
            torrent_hash = download_info.get('torrent_handle')

            if not torrent_hash or not self.torrent_downloader:
                return

            if torrent_hash not in self.torrent_downloader.torrents:
                return

            torrent_info = self.torrent_downloader.torrents[torrent_hash]
            torrent_handle = torrent_info['handle']
            status = torrent_handle.status()

            # Calculate progress
            if status.total_wanted > 0:
                progress = status.progress * 100.0
            else:
                progress = 0.0

            # Update database and emit signal
            self.state_manager.update_video_progress(item_id, progress)
            self.video_progress_updated.emit(item_id, progress)

            # Check if video download complete
            if status.state == 5:  # seeding state
                video_path = self._find_video_file(item_id)
                if video_path:
                    self._on_video_download_complete(item_id, video_path)

        except Exception as e:
            print(f"Error updating video progress for {item_id}: {e}")

    def _on_video_download_complete(self, item_id: str, video_path: str):
        """Handle video download completion"""
        try:
            print(f"[{item_id}] Video download complete: {os.path.basename(video_path)}")

            # Validate video file
            if not os.path.exists(video_path) or os.path.getsize(video_path) < 1024 * 1024:
                self._handle_error(item_id, 'video', "Video file validation failed")
                return

            # Store video path
            self.active_downloads[item_id]['video_path'] = video_path
            self.state_manager.set_video_path(item_id, video_path)
            self.state_manager.set_video_status(item_id, 'completed')
            self.video_status_changed.emit(item_id, 'completed')
            self.video_progress_updated.emit(item_id, 100.0)

            # For series, now start subtitle download (sequential for quota management)
            if self.active_downloads[item_id]['item_type'] == 'season':
                self._start_subtitle_download(item_id, video_path)

            # Check if everything is complete
            self._check_completion(item_id)

        except Exception as e:
            self._handle_error(item_id, 'video', f"Error completing video download: {e}")

    def _find_video_file(self, item_id: str) -> Optional[str]:
        """Find downloaded video file"""
        try:
            download_info = self.active_downloads[item_id]
            torrent_hash = download_info['torrent_handle']

            if not torrent_hash or torrent_hash not in self.torrent_downloader.torrents:
                return None

            torrent_info_dict = self.torrent_downloader.torrents[torrent_hash]
            torrent_handle = torrent_info_dict['handle']
            torrent_info = torrent_handle.torrent_file()

            if not torrent_info:
                return None

            # Find largest video file
            files = torrent_info.files()
            video_files = []

            for i in range(files.num_files()):
                file_entry = files.at(i)
                file_path = file_entry.path
                file_size = file_entry.size

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

    @pyqtSlot(str, str)
    def _on_subtitle_download_ready(self, download_link: str, suggested_filename: str):
        """Handle subtitle download link ready"""
        # Find which download this belongs to
        item_id = self._find_download_in_subtitle_phase()

        if not item_id:
            print("Warning: Received subtitle download link but no active download")
            return

        try:
            download_info = self.active_downloads[item_id]
            video_path = download_info.get('video_path', '')

            if not video_path:
                # For parallel downloads, we might not have video path yet
                # Use download_dir + title for now
                video_path = os.path.join(self.download_dir, download_info['title'])

            # Determine save path
            video_dir = os.path.dirname(video_path) if video_path else self.download_dir
            video_base = os.path.splitext(os.path.basename(video_path))[0] if video_path else download_info['title']

            subtitle_language = download_info['subtitle_language']
            needs_translation = download_info['needs_translation']

            if not needs_translation and subtitle_language == 'pl':
                subtitle_filename = f"{video_base}-pl.srt"
            else:
                subtitle_filename = f"{video_base}.{subtitle_language}.srt"

            save_path = os.path.join(video_dir, subtitle_filename)

            # Download subtitle in background thread
            def download_worker():
                success, error = self.subtitle_manager.download_subtitle_file(download_link, save_path)

                if success:
                    print(f"[{item_id}] Subtitle downloaded: {os.path.basename(save_path)}")

                    # Store subtitle path
                    self.active_downloads[item_id]['subtitle_path'] = save_path
                    self.state_manager.set_subtitle_path(item_id, save_path)
                    self.state_manager.set_subtitle_status(item_id, 'completed')
                    self.subtitle_status_changed.emit(item_id, 'completed')

                    if needs_translation:
                        # Start translation
                        self.subtitle_progress_updated.emit(item_id, 50.0)  # Subtitle done, translation pending
                        self._start_translation(item_id, save_path)
                    else:
                        # No translation needed - subtitle phase complete
                        self.subtitle_progress_updated.emit(item_id, 100.0)
                        self.state_manager.set_translated_subtitle_path(item_id, save_path)
                        self.active_downloads[item_id]['translated_subtitle_path'] = save_path
                        self._check_completion(item_id)
                else:
                    self._handle_error(item_id, 'subtitle', f"Subtitle download failed: {error}")

            thread = threading.Thread(target=download_worker, daemon=True)
            thread.start()

        except Exception as e:
            self._handle_error(item_id, 'subtitle', f"Error processing subtitle: {e}")

    @pyqtSlot(dict)
    def _on_subtitle_download_error(self, error_dict: dict):
        """Handle subtitle download error"""
        item_id = self._find_download_in_subtitle_phase()

        if not item_id:
            return

        error_message = error_dict.get('message', 'Unknown error')
        self._handle_error(item_id, 'subtitle', f"Subtitle download failed: {error_message}")

    def _start_translation(self, item_id: str, subtitle_path: str):
        """Start translation phase"""
        try:
            print(f"[{item_id}] Starting translation")

            self.state_manager.set_translation_status(item_id, 'translating')
            self.active_downloads[item_id]['translation_source_path'] = subtitle_path

            # Start translation
            self.translator.translate_srt_file(subtitle_path)

        except Exception as e:
            self._handle_error(item_id, 'translation', f"Error starting translation: {e}")

    @pyqtSlot(int, int)
    def _on_translation_progress(self, current_batch: int, total_batches: int):
        """Handle translation progress"""
        item_id = self._find_download_in_translation_phase()

        if not item_id:
            return

        # Calculate progress (50% base from subtitle + 50% for translation)
        translation_progress = (current_batch / total_batches) * 50.0
        overall_subtitle_progress = 50.0 + translation_progress

        self.subtitle_progress_updated.emit(item_id, overall_subtitle_progress)

    @pyqtSlot(str, str)
    def _on_translation_complete(self, original_path: str, translated_path: str):
        """Handle translation completion"""
        item_id = self._find_download_in_translation_phase()

        if not item_id:
            return

        try:
            print(f"[{item_id}] Translation complete: {os.path.basename(translated_path)}")

            # Validate translated file
            if not os.path.exists(translated_path) or os.path.getsize(translated_path) < 100:
                self._handle_error(item_id, 'translation', "Translated file validation failed")
                return

            # Store translated subtitle path
            self.active_downloads[item_id]['translated_subtitle_path'] = translated_path
            self.state_manager.set_translated_subtitle_path(item_id, translated_path)
            self.state_manager.set_translation_status(item_id, 'completed')
            self.subtitle_progress_updated.emit(item_id, 100.0)

            # Check completion
            self._check_completion(item_id)

        except Exception as e:
            self._handle_error(item_id, 'translation', f"Error completing translation: {e}")

    @pyqtSlot(str, str)
    def _on_translation_error(self, original_path: str, error_message: str):
        """Handle translation error"""
        item_id = self._find_download_in_translation_phase()

        if not item_id:
            return

        self._handle_error(item_id, 'translation', f"Translation failed: {error_message}")

    def _check_completion(self, item_id: str):
        """Check if all components are complete"""
        if item_id not in self.active_downloads:
            return

        download_info = self.active_downloads[item_id]

        video_complete = download_info.get('video_path') is not None
        subtitle_complete = download_info.get('subtitle_path') is not None
        translation_complete = (not download_info['needs_translation'] or
                               download_info.get('translated_subtitle_path') is not None)

        if video_complete and subtitle_complete and translation_complete:
            self._complete_download(item_id)

    def _complete_download(self, item_id: str):
        """Mark download as complete"""
        try:
            if item_id not in self.active_downloads:
                return

            download_info = self.active_downloads[item_id]

            video_path = download_info['video_path']
            subtitle_path = download_info.get('translated_subtitle_path') or download_info.get('subtitle_path')

            # Update database status
            self.state_manager.set_status(item_id, 'ready')

            # Emit completion signal
            self.download_complete.emit(item_id, video_path, subtitle_path)

            # Remove from active downloads
            del self.active_downloads[item_id]

            print(f"[{item_id}] Download complete!")

            # Stop progress timer if no active downloads
            if not self.active_downloads:
                self.progress_timer.stop()

        except Exception as e:
            print(f"Error completing download for {item_id}: {e}")

    def _handle_error(self, item_id: str, component: str, error_message: str):
        """Handle error for a specific component"""
        print(f"[{item_id}] {component.upper()} ERROR: {error_message}")

        if item_id not in self.active_downloads:
            return

        download_info = self.active_downloads[item_id]
        retry_count = download_info['retry_count'].get(component, 0)

        # Check if we should retry
        if retry_count < self.MAX_RETRIES:
            download_info['retry_count'][component] = retry_count + 1
            delay = self.SUBTITLE_RETRY_DELAY_SECONDS * (retry_count + 1)

            print(f"  Auto-retrying in {delay} seconds (attempt {retry_count + 1}/{self.MAX_RETRIES})")

            # Schedule retry
            retry_timer = QTimer(self)
            retry_timer.setSingleShot(True)
            retry_timer.timeout.connect(lambda: self._retry_component(item_id, component))
            retry_timer.start(delay * 1000)
            self.retry_timers[f"{item_id}_{component}"] = retry_timer
        else:
            # Max retries exceeded
            print(f"  Max retries exceeded - marking as failed")

            # Update status
            if component == 'video':
                self.state_manager.set_video_status(item_id, 'failed')
            elif component == 'subtitle':
                self.state_manager.set_subtitle_status(item_id, 'failed')
            elif component == 'translation':
                self.state_manager.set_translation_status(item_id, 'failed')

            self.state_manager.set_status(item_id, 'failed', error_message)
            self.download_failed.emit(item_id, component, error_message)

            # Remove from active downloads
            if item_id in self.active_downloads:
                del self.active_downloads[item_id]

            if not self.active_downloads:
                self.progress_timer.stop()

    def _retry_component(self, item_id: str, component: str):
        """Retry failed component"""
        if item_id not in self.active_downloads:
            return

        download_info = self.active_downloads[item_id]

        print(f"[{item_id}] Retrying {component}...")

        if component == 'video':
            self._start_video_download(item_id, download_info['magnet_link'])
        elif component == 'subtitle':
            video_path = download_info.get('video_path', '')
            self._start_subtitle_download(item_id, video_path)
        elif component == 'translation':
            subtitle_path = download_info.get('subtitle_path')
            if subtitle_path:
                self._start_translation(item_id, subtitle_path)

    def _find_download_in_subtitle_phase(self) -> Optional[str]:
        """Find item_id for download currently downloading subtitles"""
        for item_id, info in self.active_downloads.items():
            subtitle_status = self.state_manager.get_download_state(item_id).get('subtitle_status')
            if subtitle_status == 'downloading':
                return item_id
        return None

    def _find_download_in_translation_phase(self) -> Optional[str]:
        """Find item_id for download currently translating"""
        for item_id, info in self.active_downloads.items():
            translation_status = self.state_manager.get_download_state(item_id).get('translation_status')
            if translation_status == 'translating':
                return item_id
        return None

    def shutdown(self):
        """Shutdown orchestrator and cleanup resources"""
        print("Shutting down download orchestrator V2...")

        # Stop progress timer
        self.progress_timer.stop()

        # Stop all retry timers
        for timer in self.retry_timers.values():
            timer.stop()
        self.retry_timers.clear()

        # Shutdown torrent downloader
        if self.torrent_downloader:
            self.torrent_downloader.shutdown()

        print("Download orchestrator V2 shutdown complete")
