"""
Download State Manager V2

Adds component-level status tracking:
- video_status: pending, downloading, completed, failed, not_needed
- subtitle_status: pending, downloading, completed, failed, not_needed
- translation_status: pending, translating, completed, failed, not_needed
- subtitle_quota tracking for series downloads
"""

import sqlite3
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from pathlib import Path


class DownloadStateManagerV2:
    """
    Manages download state persistence with component-level tracking.

    New features vs V1:
    - Component status tracking (video_status, subtitle_status, translation_status)
    - Subtitle quota management (5/day limit)
    - Smart resume support
    """

    def __init__(self, db_path: str = "hackflix.db"):
        """
        Initialize download state manager V2.

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
        Create new download entry or reset existing one.

        Args:
            item_id: Unique item identifier
            item_type: 'movie' or 'season'
            magnet_link: BitTorrent magnet URI
            download_path: Optional download directory path

        Returns:
            True if created successfully
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Check if entry exists
            cursor.execute("SELECT id FROM download_state WHERE id = ?", (item_id,))
            row = cursor.fetchone()

            if row:
                # Reset existing entry
                cursor.execute("""
                    UPDATE download_state
                    SET status = 'downloading',
                        progress = 0.0,
                        video_status = 'pending',
                        video_progress = 0.0,
                        subtitle_status = 'pending',
                        subtitle_progress = 0.0,
                        translation_status = 'pending',
                        translation_progress = 0.0,
                        download_path = ?,
                        started_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (download_path, item_id))
                print(f"Reset download entry: {item_id}")
            else:
                # Create new entry
                cursor.execute("""
                    INSERT INTO download_state (
                        id, type, status,
                        progress,
                        video_status, video_progress,
                        subtitle_status, subtitle_progress,
                        translation_status, translation_progress,
                        download_path,
                        started_at, updated_at
                    )
                    VALUES (?, ?, 'downloading', 0.0, 'pending', 0.0, 'pending', 0.0, 'pending', 0.0, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """, (item_id, item_type, download_path))
                print(f"Created download entry: {item_id}")

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            print(f"Error creating download entry: {e}")
            import traceback
            traceback.print_exc()
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

    def update_video_progress(self, item_id: str, progress: float) -> bool:
        """
        Update video download progress.

        Args:
            item_id: Item identifier
            progress: Progress (0.0-100.0)

        Returns:
            True if updated successfully
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE download_state
                SET video_progress = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (progress, item_id))

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            print(f"Error updating video progress for {item_id}: {e}")
            return False

    def update_subtitle_progress(self, item_id: str, progress: float) -> bool:
        """
        Update subtitle download/translation progress.

        Args:
            item_id: Item identifier
            progress: Progress (0.0-100.0)

        Returns:
            True if updated successfully
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE download_state
                SET subtitle_progress = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (progress, item_id))

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            print(f"Error updating subtitle progress for {item_id}: {e}")
            return False

    def set_video_status(self, item_id: str, status: str) -> bool:
        """
        Set video download status.

        Args:
            item_id: Item identifier
            status: Status ('pending', 'downloading', 'completed', 'failed')

        Returns:
            True if updated successfully
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE download_state
                SET video_status = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (status, item_id))

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            print(f"Error setting video status for {item_id}: {e}")
            return False

    def set_subtitle_status(self, item_id: str, status: str) -> bool:
        """
        Set subtitle download status.

        Args:
            item_id: Item identifier
            status: Status ('pending', 'downloading', 'completed', 'failed', 'not_needed')

        Returns:
            True if updated successfully
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE download_state
                SET subtitle_status = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (status, item_id))

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            print(f"Error setting subtitle status for {item_id}: {e}")
            return False

    def set_translation_status(self, item_id: str, status: str) -> bool:
        """
        Set translation status.

        Args:
            item_id: Item identifier
            status: Status ('pending', 'translating', 'completed', 'failed', 'not_needed')

        Returns:
            True if updated successfully
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE download_state
                SET translation_status = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (status, item_id))

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            print(f"Error setting translation status for {item_id}: {e}")
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
            status: New status ('downloading', 'ready', 'failed')
            error_message: Optional user-friendly error message
            error_details: Optional detailed error information

        Returns:
            True if updated successfully
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            if status == 'ready':
                cursor.execute("""
                    UPDATE download_state
                    SET status = ?,
                        completed_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (status, item_id))
            elif status == 'failed':
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
            return True

        except Exception as e:
            print(f"Error setting status for {item_id}: {e}")
            return False

    def get_quota_info(self) -> Dict[str, Any]:
        """
        Get subtitle download quota info.

        Returns:
            Dict with 'date' and 'used'
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Get quota from metadata or first download entry
            cursor.execute("""
                SELECT subtitle_quota_date, subtitle_quota_used
                FROM download_state
                WHERE subtitle_quota_date IS NOT NULL
                ORDER BY updated_at DESC
                LIMIT 1
            """)

            row = cursor.fetchone()
            conn.close()

            if row and row['subtitle_quota_date']:
                return {
                    'date': row['subtitle_quota_date'],
                    'used': row['subtitle_quota_used'] or 0
                }

            return {
                'date': '',
                'used': 0
            }

        except Exception as e:
            print(f"Error getting quota info: {e}")
            return {'date': '', 'used': 0}

    def increment_quota(self, today: str):
        """
        Increment subtitle download quota for today.

        Args:
            today: Today's date in ISO format (YYYY-MM-DD)
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Update all entries to use same quota counter
            cursor.execute("""
                UPDATE download_state
                SET subtitle_quota_date = ?,
                    subtitle_quota_used = COALESCE(
                        CASE WHEN subtitle_quota_date = ? THEN subtitle_quota_used + 1 ELSE 1 END,
                        1
                    )
            """, (today, today))

            conn.commit()
            conn.close()

            print(f"Incremented subtitle quota for {today}")

        except Exception as e:
            print(f"Error incrementing quota: {e}")

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
