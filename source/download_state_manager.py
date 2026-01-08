"""
Download State Manager

SQLite interface for managing download state tracking.
Provides CRUD operations for the download_state table.
"""

import sqlite3
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path


class DownloadStateManager:
    """
    Manages download state persistence in SQLite database.

    Provides methods to:
    - Create new download entries
    - Update progress and phase
    - Query download state
    - Handle status transitions
    """

    def __init__(self, db_path: str = "hackflix.db"):
        """
        Initialize download state manager.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self._ensure_database_exists()

    def _ensure_database_exists(self):
        """Ensure database file exists"""
        db_file = Path(self.db_path)
        if not db_file.exists():
            print(f"Warning: Database file not found at {self.db_path}")

    def _get_connection(self) -> sqlite3.Connection:
        """
        Get database connection.

        Returns:
            SQLite connection object
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def create_download(
        self,
        item_id: str,
        item_type: str,
        magnet_link: str,
        download_path: Optional[str] = None
    ) -> bool:
        """
        Create new download entry or update existing one.

        Args:
            item_id: Unique item identifier (movie_id or 'series_id_sN')
            item_type: 'movie' or 'season'
            magnet_link: BitTorrent magnet URI
            download_path: Optional download directory path

        Returns:
            True if created/updated successfully, False if already downloading
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Check if entry exists and its current status
            cursor.execute("SELECT status FROM download_state WHERE id = ?", (item_id,))
            row = cursor.fetchone()

            if row:
                current_status = row['status']
                # Note: We don't check for 'downloading' status here because the database
                # is just persistent state. The orchestrator's active_downloads is the
                # source of truth for what's actually downloading. This allows restarting
                # downloads that were interrupted (e.g., app crash, restart).

                # Update existing entry to start downloading
                cursor.execute("""
                    UPDATE download_state
                    SET status = 'downloading',
                        progress = 0.0,
                        phase = 'video',
                        phase_progress = 0.0,
                        video_progress = 0.0,
                        subtitle_progress = 0.0,
                        translation_progress = 0.0,
                        download_path = ?,
                        started_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (download_path, item_id))
                print(f"Updated download entry: {item_id}")
            else:
                # Create new entry
                cursor.execute("""
                    INSERT INTO download_state (
                        id, type, status, progress, phase,
                        phase_progress, video_progress, subtitle_progress, translation_progress,
                        download_path, started_at, updated_at
                    )
                    VALUES (?, ?, 'downloading', 0.0, 'video', 0.0, 0.0, 0.0, 0.0, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """, (item_id, item_type, download_path))
                print(f"Created download entry: {item_id}")

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            print(f"Error creating/updating download entry: {e}")
            import traceback
            traceback.print_exc()
            return False

    def update_progress(
        self,
        item_id: str,
        phase: str,
        phase_progress: float,
        overall_progress: Optional[float] = None
    ) -> bool:
        """
        Update download progress.

        Args:
            item_id: Item identifier
            phase: Current phase ('video', 'subtitles', 'translation')
            phase_progress: Progress within current phase (0.0-100.0)
            overall_progress: Optional overall progress (0.0-100.0), calculated if not provided

        Returns:
            True if updated successfully
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Calculate overall progress if not provided
            if overall_progress is None:
                overall_progress = self._calculate_overall_progress(phase, phase_progress)

            # Update phase-specific progress field
            phase_field = f"{phase}_progress"

            cursor.execute(f"""
                UPDATE download_state
                SET progress = ?,
                    phase = ?,
                    phase_progress = ?,
                    {phase_field} = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (overall_progress, phase, phase_progress, phase_progress, item_id))

            conn.commit()
            conn.close()

            return True

        except Exception as e:
            print(f"Error updating progress for {item_id}: {e}")
            return False

    def _calculate_overall_progress(self, phase: str, phase_progress: float) -> float:
        """
        Calculate overall progress (0-100) from phase and phase progress.

        Phase breakdown:
        - Video: 0-33%
        - Subtitles: 34-66%
        - Translation: 67-100%

        Args:
            phase: Current phase name
            phase_progress: Progress within phase (0-100)

        Returns:
            Overall progress (0-100)
        """
        phase_ranges = {
            'video': (0.0, 33.0),
            'subtitles': (33.0, 66.0),
            'translation': (66.0, 100.0)
        }

        if phase not in phase_ranges:
            print(f"Warning: Unknown phase '{phase}', defaulting to 0%")
            return 0.0

        start, end = phase_ranges[phase]
        phase_size = end - start

        # Calculate progress within phase range
        progress_in_range = (phase_progress / 100.0) * phase_size
        overall = start + progress_in_range

        # Clamp to 0-100
        return max(0.0, min(100.0, overall))

    def set_phase(self, item_id: str, phase: str) -> bool:
        """
        Change current phase and reset phase progress.

        Args:
            item_id: Item identifier
            phase: New phase ('video', 'subtitles', 'translation')

        Returns:
            True if updated successfully
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Calculate overall progress at phase boundary
            phase_start_progress = self._calculate_overall_progress(phase, 0.0)

            cursor.execute("""
                UPDATE download_state
                SET phase = ?,
                    phase_progress = 0.0,
                    progress = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (phase, phase_start_progress, item_id))

            conn.commit()
            conn.close()

            print(f"Changed phase to '{phase}' for {item_id}")
            return True

        except Exception as e:
            print(f"Error setting phase for {item_id}: {e}")
            return False

    def set_status(
        self,
        item_id: str,
        status: str,
        error_message: Optional[str] = None,
        error_details: Optional[str] = None
    ) -> bool:
        """
        Update download status.

        Args:
            item_id: Item identifier
            status: New status ('downloading', 'ready', 'failed', 'translation_failed')
            error_message: Optional user-friendly error message
            error_details: Optional detailed error information

        Returns:
            True if updated successfully
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Build update query based on status
            if status == 'ready':
                cursor.execute("""
                    UPDATE download_state
                    SET status = ?,
                        progress = 100.0,
                        completed_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (status, item_id))
            elif status in ('failed', 'translation_failed'):
                cursor.execute("""
                    UPDATE download_state
                    SET status = ?,
                        error_message = ?,
                        error_details = ?,
                        failed_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (status, error_message, error_details, item_id))
            else:
                cursor.execute("""
                    UPDATE download_state
                    SET status = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (status, item_id))

            conn.commit()
            conn.close()

            print(f"Set status to '{status}' for {item_id}")
            return True

        except Exception as e:
            print(f"Error setting status for {item_id}: {e}")
            return False

    def set_video_path(self, item_id: str, video_path: str) -> bool:
        """
        Set video file path after download completes.

        Args:
            item_id: Item identifier
            video_path: Path to downloaded video file

        Returns:
            True if updated successfully
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE download_state
                SET download_path = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (video_path, item_id))

            conn.commit()
            conn.close()

            return True

        except Exception as e:
            print(f"Error setting video path for {item_id}: {e}")
            return False

    def set_subtitle_path(self, item_id: str, subtitle_path: str) -> bool:
        """
        Set subtitle file path after download completes.

        Args:
            item_id: Item identifier
            subtitle_path: Path to downloaded subtitle file

        Returns:
            True if updated successfully
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE download_state
                SET subtitle_path = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (subtitle_path, item_id))

            conn.commit()
            conn.close()

            return True

        except Exception as e:
            print(f"Error setting subtitle path for {item_id}: {e}")
            return False

    def set_translated_subtitle_path(self, item_id: str, translated_path: str) -> bool:
        """
        Set translated subtitle file path after translation completes.

        Args:
            item_id: Item identifier
            translated_path: Path to translated subtitle file

        Returns:
            True if updated successfully
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE download_state
                SET translated_subtitle_path = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (translated_path, item_id))

            conn.commit()
            conn.close()

            return True

        except Exception as e:
            print(f"Error setting translated subtitle path for {item_id}: {e}")
            return False

    def get_download_state(self, item_id: str) -> Optional[Dict[str, Any]]:
        """
        Get download state for specific item.

        Args:
            item_id: Item identifier

        Returns:
            Dictionary with download state or None if not found
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM download_state
                WHERE id = ?
            """, (item_id,))

            row = cursor.fetchone()
            conn.close()

            if row:
                return dict(row)
            return None

        except Exception as e:
            print(f"Error getting download state for {item_id}: {e}")
            return None

    def get_all_active_downloads(self) -> List[Dict[str, Any]]:
        """
        Get all active downloads (status='downloading').

        Returns:
            List of download state dictionaries
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM download_state
                WHERE status = 'downloading'
                ORDER BY started_at ASC
            """)

            rows = cursor.fetchall()
            conn.close()

            return [dict(row) for row in rows]

        except Exception as e:
            print(f"Error getting active downloads: {e}")
            return []

    def get_downloads_by_status(self, status: str) -> List[Dict[str, Any]]:
        """
        Get all downloads with specific status.

        Args:
            status: Status to filter by

        Returns:
            List of download state dictionaries
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM download_state
                WHERE status = ?
                ORDER BY updated_at DESC
            """, (status,))

            rows = cursor.fetchall()
            conn.close()

            return [dict(row) for row in rows]

        except Exception as e:
            print(f"Error getting downloads by status '{status}': {e}")
            return []

    def delete_download(self, item_id: str) -> bool:
        """
        Delete download entry from database.

        Args:
            item_id: Item identifier

        Returns:
            True if deleted successfully
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                DELETE FROM download_state
                WHERE id = ?
            """, (item_id,))

            conn.commit()
            conn.close()

            print(f"Deleted download entry: {item_id}")
            return True

        except Exception as e:
            print(f"Error deleting download entry for {item_id}: {e}")
            return False

    def reset_failed_download(self, item_id: str) -> bool:
        """
        Reset failed download to allow retry.

        Args:
            item_id: Item identifier

        Returns:
            True if reset successfully
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE download_state
                SET status = 'downloading',
                    progress = 0.0,
                    phase = 'video',
                    phase_progress = 0.0,
                    video_progress = 0.0,
                    subtitle_progress = 0.0,
                    translation_progress = 0.0,
                    error_message = NULL,
                    error_details = NULL,
                    failed_at = NULL,
                    started_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (item_id,))

            conn.commit()
            conn.close()

            print(f"Reset failed download: {item_id}")
            return True

        except Exception as e:
            print(f"Error resetting download for {item_id}: {e}")
            return False

    def get_watch_history(self, item_id: str) -> Optional[Dict[str, Any]]:
        """
        Get watch history for specific item.

        Args:
            item_id: Item identifier (currently only supports series)

        Returns:
            Dictionary with watch history or None if not found
        """
        try:
            # Watch history only supports series, not movies
            # item_id format for series: "series_123_s1"
            if not item_id or '_s' not in item_id:
                # This is a movie, not a series - no watch history
                return None

            # Parse series_id and season from item_id
            parts = item_id.rsplit('_s', 1)
            if len(parts) != 2:
                return None

            series_id = parts[0]
            season_number = int(parts[1])

            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM watch_history
                WHERE series_id = ? AND season_number = ?
            """, (series_id, season_number))

            row = cursor.fetchone()
            conn.close()

            if row:
                return dict(row)
            return None

        except Exception as e:
            # Silently ignore watch history errors for movies
            return None

    def update_watch_history(
        self,
        item_id: str,
        last_position: int,
        completed: bool = False
    ) -> bool:
        """
        Update or create watch history entry.

        Args:
            item_id: Item identifier
            last_position: Last playback position in milliseconds
            completed: Whether playback completed (>90% watched)

        Returns:
            True if updated successfully
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO watch_history (item_id, last_position, completed, last_watched)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(item_id) DO UPDATE SET
                    last_position = excluded.last_position,
                    completed = excluded.completed,
                    last_watched = CURRENT_TIMESTAMP
            """, (item_id, last_position, completed))

            conn.commit()
            conn.close()

            return True

        except Exception as e:
            print(f"Error updating watch history for {item_id}: {e}")
            return False
