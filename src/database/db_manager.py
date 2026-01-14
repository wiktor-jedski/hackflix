"""Database manager for Hackflix.

This module provides the DatabaseManager class for all database operations.
Uses per-operation connections (no connection pooling) with raw sqlite3.
"""

import logging
import sqlite3
from pathlib import Path
from typing import Any

from src.config import DownloadState, PipelineState
from src.database.schema import SCHEMA_SQL

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages database operations with per-operation connections.

    Each operation opens and closes its own connection to avoid
    locking issues and ensure thread safety.

    For in-memory databases (:memory:), a shared connection is used
    since in-memory databases only persist within a single connection.
    """

    def __init__(self, db_path: str | Path) -> None:
        """Initialize the database manager.

        Args:
            db_path: Path to the SQLite database file, or ':memory:' for testing.
        """
        self.db_path = str(db_path)
        self._is_memory = self.db_path == ":memory:"
        self._shared_conn: sqlite3.Connection | None = None

    def _get_connection(self) -> sqlite3.Connection:
        """Create or return a database connection.

        For file-based databases, creates a new connection per operation.
        For in-memory databases, returns a shared connection.

        Returns:
            A sqlite3 connection with foreign keys enabled
            and row_factory set to sqlite3.Row for dict-like access.
        """
        if self._is_memory:
            if self._shared_conn is None:
                self._shared_conn = sqlite3.connect(":memory:")
                self._shared_conn.execute("PRAGMA foreign_keys = ON")
                self._shared_conn.row_factory = sqlite3.Row
            return self._shared_conn

        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        conn.row_factory = sqlite3.Row
        return conn

    def _close_connection(self, conn: sqlite3.Connection) -> None:
        """Close a connection if it's not the shared in-memory connection.

        Args:
            conn: The connection to potentially close.
        """
        if not self._is_memory:
            conn.close()

    def initialize(self) -> None:
        """Create database schema if it doesn't exist.

        Creates parent directories if needed for file-based databases.

        Raises:
            sqlite3.Error: If schema creation fails.
        """
        if not self._is_memory:
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        logger.info("Initializing database at %s", self.db_path)

        try:
            conn = self._get_connection()
            conn.executescript(SCHEMA_SQL)
            conn.commit()
            self._close_connection(conn)
            logger.info("Database initialized successfully")
        except sqlite3.Error as e:
            logger.error("Failed to initialize database: %s", e)
            raise

    def upsert_content(self, json_data: dict[str, Any]) -> None:
        """Parse content.json and update/insert media items.

        Handles movies and series with their seasons and episodes.
        Preserves orphaned items (items in DB but not in JSON).

        Args:
            json_data: Parsed content.json dictionary with 'items' key.

        Raises:
            sqlite3.Error: If database operation fails.
            KeyError: If required fields are missing from JSON.
        """
        items = json_data.get("items", [])
        logger.info("Upserting %d items from content.json", len(items))

        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            for item in items:
                item_id = item["id"]
                item_type = item["type"]
                title = item["title"]
                genres = item.get("genres")
                poster_url = item.get("poster_url")

                # Upsert media_item
                cursor.execute(
                    """
                    INSERT INTO media_items (id, type, title, genres, poster_path, last_updated)
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(id) DO UPDATE SET
                        title = excluded.title,
                        genres = excluded.genres,
                        poster_path = excluded.poster_path,
                        last_updated = CURRENT_TIMESTAMP
                    """,
                    (item_id, item_type, title, genres, poster_url),
                )

                if item_type == "movie":
                    self._upsert_movie(cursor, item)
                elif item_type == "series":
                    self._upsert_series(cursor, item)

            conn.commit()
            self._close_connection(conn)
            logger.info("Content upsert completed successfully")
        except sqlite3.Error as e:
            logger.error("Failed to upsert content: %s", e)
            raise
        except KeyError as e:
            logger.error("Missing required field in content.json: %s", e)
            raise

    def _upsert_movie(self, cursor: sqlite3.Cursor, item: dict[str, Any]) -> None:
        """Upsert a movie video file.

        Args:
            cursor: Active database cursor.
            item: Movie item dictionary from content.json.
        """
        item_id = item["id"]
        magnet = item.get("magnet")
        subtitle_id = item.get("subtitle_id")
        needs_translation = item.get("translation_needed", False)

        # Check if video_file exists for this movie
        cursor.execute(
            "SELECT id FROM video_files WHERE media_item_id = ? AND season_id IS NULL",
            (item_id,),
        )
        existing = cursor.fetchone()

        if existing:
            # Update existing
            cursor.execute(
                """
                UPDATE video_files SET
                    magnet_link = ?,
                    subtitle_id = ?,
                    needs_translation = ?
                WHERE id = ?
                """,
                (magnet, subtitle_id, needs_translation, existing["id"]),
            )
        else:
            # Insert new
            cursor.execute(
                """
                INSERT INTO video_files (media_item_id, magnet_link, subtitle_id, needs_translation)
                VALUES (?, ?, ?, ?)
                """,
                (item_id, magnet, subtitle_id, needs_translation),
            )

    def _upsert_series(self, cursor: sqlite3.Cursor, item: dict[str, Any]) -> None:
        """Upsert a series with its seasons and episodes.

        Args:
            cursor: Active database cursor.
            item: Series item dictionary from content.json.
        """
        item_id = item["id"]
        seasons = item.get("seasons", [])

        for season_data in seasons:
            season_number = season_data["season_number"]
            magnet = season_data.get("magnet")

            # Upsert season
            cursor.execute(
                """
                INSERT INTO seasons (media_item_id, season_number, magnet_link)
                VALUES (?, ?, ?)
                ON CONFLICT(media_item_id, season_number) DO UPDATE SET
                    magnet_link = excluded.magnet_link
                """,
                (item_id, season_number, magnet),
            )

            # Get season id
            cursor.execute(
                "SELECT id FROM seasons WHERE media_item_id = ? AND season_number = ?",
                (item_id, season_number),
            )
            season_row = cursor.fetchone()
            season_id = season_row["id"]

            # Upsert episodes
            episodes = season_data.get("episodes", [])
            for episode in episodes:
                episode_number = episode["number"]
                episode_title = episode.get("title")
                subtitle_id = episode.get("subtitle_id")
                needs_translation = episode.get("translation_needed", False)

                cursor.execute(
                    """
                    SELECT id FROM video_files
                    WHERE media_item_id = ? AND season_id = ? AND episode_number = ?
                    """,
                    (item_id, season_id, episode_number),
                )
                existing = cursor.fetchone()

                if existing:
                    cursor.execute(
                        """
                        UPDATE video_files SET
                            episode_title = ?,
                            subtitle_id = ?,
                            needs_translation = ?
                        WHERE id = ?
                        """,
                        (episode_title, subtitle_id, needs_translation, existing["id"]),
                    )
                else:
                    cursor.execute(
                        """
                        INSERT INTO video_files
                        (media_item_id, season_id, episode_number, episode_title,
                         subtitle_id, needs_translation)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            item_id,
                            season_id,
                            episode_number,
                            episode_title,
                            subtitle_id,
                            needs_translation,
                        ),
                    )

    def get_library_items(
        self, media_type: str, search_filter: str | None = None
    ) -> list[dict[str, Any]]:
        """Get library items for the UI grid.

        Args:
            media_type: Type of media ('movie' or 'series').
            search_filter: Optional search filter (searches title and genres).

        Returns:
            List of media item dictionaries.

        Raises:
            sqlite3.Error: If query fails.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            if search_filter:
                cursor.execute(
                    """
                    SELECT id, type, title, genres, poster_path, created_at, last_updated
                    FROM media_items
                    WHERE type = ? AND (title LIKE ? OR genres LIKE ?)
                    ORDER BY title
                    """,
                    (media_type, f"%{search_filter}%", f"%{search_filter}%"),
                )
            else:
                cursor.execute(
                    """
                    SELECT id, type, title, genres, poster_path, created_at, last_updated
                    FROM media_items
                    WHERE type = ?
                    ORDER BY title
                    """,
                    (media_type,),
                )

            rows = cursor.fetchall()
            self._close_connection(conn)
            return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error("Failed to get library items: %s", e)
            raise

    def get_video_details(self, media_id: str) -> dict[str, Any] | None:
        """Get video file details for a media item.

        For movies, returns the single video file.
        For series, returns None (use get_episodes instead).

        Args:
            media_id: UUID of the media item.

        Returns:
            Video file dictionary or None if not found.

        Raises:
            sqlite3.Error: If query fails.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT vf.*, mi.title as media_title, mi.type as media_type
                FROM video_files vf
                JOIN media_items mi ON vf.media_item_id = mi.id
                WHERE vf.media_item_id = ? AND vf.season_id IS NULL
                """,
                (media_id,),
            )

            row = cursor.fetchone()
            self._close_connection(conn)
            return dict(row) if row else None
        except sqlite3.Error as e:
            logger.error("Failed to get video details: %s", e)
            raise

    def get_video_file(self, video_file_id: int) -> dict[str, Any] | None:
        """Get a single video file record by ID.

        Args:
            video_file_id: ID of the video file.

        Returns:
            Video file dictionary or None if not found.

        Raises:
            sqlite3.Error: If query fails.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT vf.*, mi.title as media_title, mi.type as media_type
                FROM video_files vf
                JOIN media_items mi ON vf.media_item_id = mi.id
                WHERE vf.id = ?
                """,
                (video_file_id,),
            )

            row = cursor.fetchone()
            self._close_connection(conn)
            return dict(row) if row else None
        except sqlite3.Error as e:
            logger.error("Failed to get video file: %s", e)
            raise

    def get_seasons(self, media_id: str) -> list[dict[str, Any]]:
        """Get all seasons for a series.

        Args:
            media_id: UUID of the series media item.

        Returns:
            List of season dictionaries.

        Raises:
            sqlite3.Error: If query fails.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT * FROM seasons
                WHERE media_item_id = ?
                ORDER BY season_number
                """,
                (media_id,),
            )

            rows = cursor.fetchall()
            self._close_connection(conn)
            return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error("Failed to get seasons: %s", e)
            raise

    def get_episodes(self, season_id: int) -> list[dict[str, Any]]:
        """Get all episodes for a season.

        Args:
            season_id: ID of the season.

        Returns:
            List of video file dictionaries for episodes.

        Raises:
            sqlite3.Error: If query fails.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT * FROM video_files
                WHERE season_id = ?
                ORDER BY episode_number
                """,
                (season_id,),
            )

            rows = cursor.fetchall()
            self._close_connection(conn)
            return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error("Failed to get episodes: %s", e)
            raise

    def update_file_state(
        self, file_id: int, state: DownloadState, progress: int = 0
    ) -> None:
        """Update download state for a video file.

        Args:
            file_id: ID of the video file.
            state: New download state.
            progress: Download progress (0-100).

        Raises:
            sqlite3.Error: If update fails.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                "UPDATE video_files SET state = ?, download_progress = ? WHERE id = ?",
                (state.value, progress, file_id),
            )

            conn.commit()
            self._close_connection(conn)
            logger.debug(
                "Updated file %d state to %s (%d%%)", file_id, state.value, progress
            )
        except sqlite3.Error as e:
            logger.error("Failed to update file state: %s", e)
            raise

    def update_season_state(
        self, season_id: int, state: DownloadState, progress: int = 0
    ) -> None:
        """Update download state for a season.

        Args:
            season_id: ID of the season.
            state: New download state.
            progress: Download progress (0-100).

        Raises:
            sqlite3.Error: If update fails.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                "UPDATE seasons SET state = ?, download_progress = ? WHERE id = ?",
                (state.value, progress, season_id),
            )

            conn.commit()
            self._close_connection(conn)
            logger.debug(
                "Updated season %d state to %s (%d%%)", season_id, state.value, progress
            )
        except sqlite3.Error as e:
            logger.error("Failed to update season state: %s", e)
            raise

    def update_pipeline_state(self, file_id: int, state: PipelineState) -> None:
        """Update pipeline state for a video file.

        Args:
            file_id: ID of the video file.
            state: New pipeline state.

        Raises:
            sqlite3.Error: If update fails.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                "UPDATE video_files SET pipeline_state = ? WHERE id = ?",
                (state.value, file_id),
            )

            conn.commit()
            self._close_connection(conn)
            logger.debug("Updated file %d pipeline state to %s", file_id, state.value)
        except sqlite3.Error as e:
            logger.error("Failed to update pipeline state: %s", e)
            raise

    def update_file_path(self, file_id: int, file_path: str) -> None:
        """Update the file path for a video file.

        Args:
            file_id: ID of the video file.
            file_path: Path to the video file on disk.

        Raises:
            sqlite3.Error: If update fails.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                "UPDATE video_files SET file_path = ? WHERE id = ?",
                (file_path, file_id),
            )

            conn.commit()
            self._close_connection(conn)
            logger.debug("Updated file %d path to %s", file_id, file_path)
        except sqlite3.Error as e:
            logger.error("Failed to update file path: %s", e)
            raise

    def update_resume_position(self, file_id: int, position_seconds: int) -> None:
        """Save playback resume position.

        Args:
            file_id: ID of the video file.
            position_seconds: Playback position in seconds.

        Raises:
            sqlite3.Error: If update fails.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                "UPDATE video_files SET resume_position_seconds = ? WHERE id = ?",
                (position_seconds, file_id),
            )

            conn.commit()
            self._close_connection(conn)
            logger.debug(
                "Updated file %d resume position to %ds", file_id, position_seconds
            )
        except sqlite3.Error as e:
            logger.error("Failed to update resume position: %s", e)
            raise

    def get_translation_progress(self, file_id: int) -> dict[str, Any] | None:
        """Get translation batch progress for resumable translation.

        Args:
            file_id: ID of the video file.

        Returns:
            Translation progress dictionary or None if not found.

        Raises:
            sqlite3.Error: If query fails.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT * FROM translation_progress WHERE video_file_id = ?",
                (file_id,),
            )

            row = cursor.fetchone()
            self._close_connection(conn)
            return dict(row) if row else None
        except sqlite3.Error as e:
            logger.error("Failed to get translation progress: %s", e)
            raise

    def update_translation_progress(self, file_id: int, batch: int, total: int) -> None:
        """Save translation progress for resumable translation.

        Args:
            file_id: ID of the video file.
            batch: Last successfully completed batch index.
            total: Total number of batches.

        Raises:
            sqlite3.Error: If update fails.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO translation_progress (video_file_id, last_completed_batch, total_batches)
                VALUES (?, ?, ?)
                ON CONFLICT(video_file_id) DO UPDATE SET
                    last_completed_batch = excluded.last_completed_batch,
                    total_batches = excluded.total_batches
                """,
                (file_id, batch, total),
            )

            conn.commit()
            self._close_connection(conn)
            logger.debug(
                "Updated translation progress for file %d: batch %d/%d",
                file_id,
                batch,
                total,
            )
        except sqlite3.Error as e:
            logger.error("Failed to update translation progress: %s", e)
            raise

    def get_incomplete_downloads(self) -> list[dict[str, Any]]:
        """Get all video files with incomplete downloads for auto-resume.

        Returns:
            List of video files in QUEUED or DOWNLOADING state.

        Raises:
            sqlite3.Error: If query fails.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT vf.*, mi.title as media_title
                FROM video_files vf
                JOIN media_items mi ON vf.media_item_id = mi.id
                WHERE vf.state IN (?, ?)
                """,
                (DownloadState.QUEUED.value, DownloadState.DOWNLOADING.value),
            )

            rows = cursor.fetchall()
            self._close_connection(conn)
            return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error("Failed to get incomplete downloads: %s", e)
            raise

    def get_incomplete_pipelines(self) -> list[dict[str, Any]]:
        """Get all video files with incomplete pipeline processing for auto-resume.

        Returns:
            List of video files in active pipeline states (not NONE, VOICEOVER_READY, or FAILED).

        Raises:
            sqlite3.Error: If query fails.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Get files in active processing states
            active_states = [
                PipelineState.FETCHING_SUBS.value,
                PipelineState.TRANSLATING.value,
                PipelineState.SUBS_READY.value,
                PipelineState.GENERATING_TTS.value,
                PipelineState.MIXING_AUDIO.value,
            ]

            placeholders = ",".join("?" * len(active_states))
            cursor.execute(
                f"""
                SELECT vf.*, mi.title as media_title
                FROM video_files vf
                JOIN media_items mi ON vf.media_item_id = mi.id
                WHERE vf.pipeline_state IN ({placeholders})
                """,
                active_states,
            )

            rows = cursor.fetchall()
            self._close_connection(conn)
            return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error("Failed to get incomplete pipelines: %s", e)
            raise

    def add_subtitle(
        self,
        video_file_id: int,
        language_code: str,
        file_path: str,
        is_translated: bool = False,
    ) -> int:
        """Add a subtitle record.

        Args:
            video_file_id: ID of the video file.
            language_code: Language code (e.g., 'en', 'pl').
            file_path: Path to the subtitle file.
            is_translated: True if translated by AI.

        Returns:
            ID of the new subtitle record.

        Raises:
            sqlite3.Error: If insert fails.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO subtitles (video_file_id, language_code, file_path, is_translated)
                VALUES (?, ?, ?, ?)
                """,
                (video_file_id, language_code, file_path, is_translated),
            )

            subtitle_id = cursor.lastrowid
            conn.commit()
            self._close_connection(conn)
            logger.debug(
                "Added subtitle %d for video file %d", subtitle_id, video_file_id
            )
            return subtitle_id
        except sqlite3.Error as e:
            logger.error("Failed to add subtitle: %s", e)
            raise

    def add_voiceover(
        self, video_file_id: int, language_code: str, file_path: str
    ) -> int:
        """Add a voiceover record.

        Args:
            video_file_id: ID of the video file.
            language_code: Language code (e.g., 'pl').
            file_path: Path to the voiceover audio file.

        Returns:
            ID of the new voiceover record.

        Raises:
            sqlite3.Error: If insert fails.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO voiceovers (video_file_id, language_code, file_path)
                VALUES (?, ?, ?)
                """,
                (video_file_id, language_code, file_path),
            )

            voiceover_id = cursor.lastrowid
            conn.commit()
            self._close_connection(conn)
            logger.debug(
                "Added voiceover %d for video file %d", voiceover_id, video_file_id
            )
            return voiceover_id
        except sqlite3.Error as e:
            logger.error("Failed to add voiceover: %s", e)
            raise

    def get_subtitles(self, video_file_id: int) -> list[dict[str, Any]]:
        """Get all subtitles for a video file.

        Args:
            video_file_id: ID of the video file.

        Returns:
            List of subtitle dictionaries.

        Raises:
            sqlite3.Error: If query fails.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT * FROM subtitles WHERE video_file_id = ?",
                (video_file_id,),
            )

            rows = cursor.fetchall()
            self._close_connection(conn)
            return [dict(row) for row in rows]
        except sqlite3.Error as e:
            logger.error("Failed to get subtitles: %s", e)
            raise

    def get_voiceover(self, video_file_id: int) -> dict[str, Any] | None:
        """Get voiceover for a video file.

        Args:
            video_file_id: ID of the video file.

        Returns:
            Voiceover dictionary or None if not found.

        Raises:
            sqlite3.Error: If query fails.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT * FROM voiceovers WHERE video_file_id = ?",
                (video_file_id,),
            )

            row = cursor.fetchone()
            self._close_connection(conn)
            return dict(row) if row else None
        except sqlite3.Error as e:
            logger.error("Failed to get voiceover: %s", e)
            raise

    def get_media_files(self, media_id: str) -> list[str]:
        """Get all file paths associated with a media item for deletion.

        Args:
            media_id: UUID of the media item.

        Returns:
            List of file paths to delete.
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            file_paths: list[str] = []

            cursor.execute(
                "SELECT poster_path FROM media_items WHERE id = ?", (media_id,)
            )
            row = cursor.fetchone()
            if row and row[0]:
                file_paths.append(row[0])

            cursor.execute(
                "SELECT file_path FROM video_files WHERE media_item_id = ?", (media_id,)
            )
            for row in cursor.fetchall():
                if row[0]:
                    file_paths.append(row[0])

            cursor.execute(
                """
                SELECT s.file_path FROM subtitles s
                JOIN video_files vf ON s.video_file_id = vf.id
                WHERE vf.media_item_id = ?
                """,
                (media_id,),
            )
            for row in cursor.fetchall():
                if row[0]:
                    file_paths.append(row[0])

            cursor.execute(
                """
                SELECT v.file_path FROM voiceovers v
                JOIN video_files vf ON v.video_file_id = vf.id
                WHERE vf.media_item_id = ?
                """,
                (media_id,),
            )
            for row in cursor.fetchall():
                if row[0]:
                    file_paths.append(row[0])

            self._close_connection(conn)
            return file_paths
        except sqlite3.Error as e:
            logger.error("Failed to get media files: %s", e)
            raise
