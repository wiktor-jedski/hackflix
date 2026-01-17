"""Database schema definitions for Hackflix.

This module contains SQL table definitions using raw sqlite3.
No ORM - per-operation connections are used.
"""

import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

# =============================================================================
# Schema SQL Definitions
# =============================================================================

SCHEMA_SQL = """
-- Settings table: Key-value store for configuration
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

-- Media items table: Movies and TV series
CREATE TABLE IF NOT EXISTS media_items (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL CHECK(type IN ('movie', 'series')),
    title TEXT NOT NULL,
    genres TEXT,
    poster_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Seasons table: For TV series only
CREATE TABLE IF NOT EXISTS seasons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    media_item_id TEXT NOT NULL,
    season_number INTEGER NOT NULL,
    magnet_link TEXT,
    state TEXT DEFAULT 'PENDING' CHECK(state IN ('PENDING', 'QUEUED', 'DOWNLOADING', 'COMPLETED', 'ERROR')),
    download_progress INTEGER DEFAULT 0,
    FOREIGN KEY (media_item_id) REFERENCES media_items(id) ON DELETE CASCADE,
    UNIQUE(media_item_id, season_number)
);

-- Video files table: Playable assets (movies or episodes)
CREATE TABLE IF NOT EXISTS video_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    media_item_id TEXT NOT NULL,
    season_id INTEGER,
    episode_number INTEGER,
    episode_title TEXT,
    subtitle_id INTEGER,
    needs_translation BOOLEAN DEFAULT 0,
    file_path TEXT,
    magnet_link TEXT,
    state TEXT DEFAULT 'PENDING' CHECK(state IN ('PENDING', 'QUEUED', 'DOWNLOADING', 'COMPLETED', 'ERROR')),
    download_progress INTEGER DEFAULT 0,
    pipeline_state TEXT DEFAULT 'NONE' CHECK(pipeline_state IN ('NONE', 'FETCHING_SUBS', 'TRANSLATING', 'SUBS_READY', 'GENERATING_TTS', 'MIXING_AUDIO', 'VOICEOVER_READY', 'FAILED')),
    resume_position_seconds INTEGER DEFAULT 0,
    FOREIGN KEY (media_item_id) REFERENCES media_items(id) ON DELETE CASCADE,
    FOREIGN KEY (season_id) REFERENCES seasons(id) ON DELETE CASCADE
);

-- Subtitles table: Subtitle files for video files
CREATE TABLE IF NOT EXISTS subtitles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_file_id INTEGER NOT NULL,
    language_code TEXT NOT NULL,
    is_translated BOOLEAN DEFAULT 0,
    file_path TEXT NOT NULL,
    FOREIGN KEY (video_file_id) REFERENCES video_files(id) ON DELETE CASCADE
);

-- Voiceovers table: Generated audio tracks
CREATE TABLE IF NOT EXISTS voiceovers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_file_id INTEGER NOT NULL,
    language_code TEXT NOT NULL,
    file_path TEXT NOT NULL,
    muxed_video_path TEXT,
    FOREIGN KEY (video_file_id) REFERENCES video_files(id) ON DELETE CASCADE
);

-- Translation progress table: Batch tracking for resumable translation
CREATE TABLE IF NOT EXISTS translation_progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_file_id INTEGER NOT NULL UNIQUE,
    last_completed_batch INTEGER DEFAULT 0,
    total_batches INTEGER DEFAULT 0,
    FOREIGN KEY (video_file_id) REFERENCES video_files(id) ON DELETE CASCADE
);

-- Indices for frequently queried columns
CREATE INDEX IF NOT EXISTS idx_media_items_type ON media_items(type);
CREATE INDEX IF NOT EXISTS idx_video_files_media_item ON video_files(media_item_id);
CREATE INDEX IF NOT EXISTS idx_video_files_state ON video_files(state);
CREATE INDEX IF NOT EXISTS idx_video_files_pipeline_state ON video_files(pipeline_state);
CREATE INDEX IF NOT EXISTS idx_seasons_media_item ON seasons(media_item_id);
CREATE INDEX IF NOT EXISTS idx_subtitles_video_file ON subtitles(video_file_id);
CREATE INDEX IF NOT EXISTS idx_voiceovers_video_file ON voiceovers(video_file_id);
"""


def get_schema_sql() -> str:
    """Return the complete SQL schema definition.

    Returns:
        SQL string containing all CREATE TABLE and CREATE INDEX statements.
    """
    return SCHEMA_SQL


def _run_migrations(conn: sqlite3.Connection) -> None:
    """Run database migrations for schema updates.

    Args:
        conn: Active database connection.
    """
    cursor = conn.cursor()

    # Migration: Add muxed_video_path column to voiceovers table
    cursor.execute("PRAGMA table_info(voiceovers)")
    columns = [row[1] for row in cursor.fetchall()]
    if "muxed_video_path" not in columns:
        logger.info("Migrating: Adding muxed_video_path column to voiceovers")
        cursor.execute("ALTER TABLE voiceovers ADD COLUMN muxed_video_path TEXT")


def initialize_database(db_path: str | Path) -> None:
    """Create database tables if they don't exist.

    Opens a connection, executes schema SQL, and closes connection.
    Uses per-operation connection pattern.

    Args:
        db_path: Path to the SQLite database file.

    Raises:
        sqlite3.Error: If database initialization fails.
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Initializing database at %s", db_path)

    try:
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(SCHEMA_SQL)
        _run_migrations(conn)
        conn.commit()
        conn.close()
        logger.info("Database initialized successfully")
    except sqlite3.Error as e:
        logger.error("Failed to initialize database: %s", e)
        raise
