"""
SQLite database schema for HackFlix

Defines tables for:
- Catalog data (movies, series, seasons)
- Download state tracking
- Watch history (series playback position)
- Subtitle cache
- API usage tracking (cost management)
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional

# Database version for migration tracking
DATABASE_VERSION = 1
DEFAULT_DATABASE_FILE = "hackflix.db"

# Complete database schema
SCHEMA = """
-- ============================================================================
-- Metadata and versioning
-- ============================================================================

CREATE TABLE IF NOT EXISTS metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- Movies catalog
-- ============================================================================

CREATE TABLE IF NOT EXISTS movies (
    id TEXT PRIMARY KEY,                    -- Unique ID (e.g., 'movie_27205')
    title TEXT NOT NULL,                    -- Movie title
    year INTEGER NOT NULL,                  -- Release year
    description TEXT,                       -- Plot summary
    magnet_link TEXT NOT NULL,              -- BitTorrent magnet URI
    file_size INTEGER NOT NULL,             -- File size in bytes
    poster_url TEXT,                        -- URL to poster image
    imdb_id TEXT,                          -- IMDb identifier
    tmdb_id INTEGER,                        -- TMDB identifier
    runtime INTEGER,                        -- Runtime in minutes
    video_quality TEXT,                     -- e.g., '1080p', '720p'
    video_codec TEXT,                       -- e.g., 'H.264', 'H.265'
    audio_codec TEXT,                       -- e.g., 'AAC', 'AC3'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Movie genres (many-to-many relationship)
CREATE TABLE IF NOT EXISTS movie_genres (
    movie_id TEXT NOT NULL,
    genre TEXT NOT NULL,
    PRIMARY KEY (movie_id, genre),
    FOREIGN KEY (movie_id) REFERENCES movies(id) ON DELETE CASCADE
);

-- Movie subtitle languages
CREATE TABLE IF NOT EXISTS movie_subtitle_languages (
    movie_id TEXT NOT NULL,
    language_code TEXT NOT NULL,            -- ISO 639-1 code (e.g., 'en', 'pl')
    PRIMARY KEY (movie_id, language_code),
    FOREIGN KEY (movie_id) REFERENCES movies(id) ON DELETE CASCADE
);

-- ============================================================================
-- Series catalog
-- ============================================================================

CREATE TABLE IF NOT EXISTS series (
    id TEXT PRIMARY KEY,                    -- Unique ID (e.g., 'series_1396')
    title TEXT NOT NULL,                    -- Series title
    year INTEGER NOT NULL,                  -- First air year
    description TEXT,                       -- Series summary
    poster_url TEXT,                        -- URL to poster image
    imdb_id TEXT,                          -- IMDb identifier
    tmdb_id INTEGER,                        -- TMDB identifier
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Series genres (many-to-many relationship)
CREATE TABLE IF NOT EXISTS series_genres (
    series_id TEXT NOT NULL,
    genre TEXT NOT NULL,
    PRIMARY KEY (series_id, genre),
    FOREIGN KEY (series_id) REFERENCES series(id) ON DELETE CASCADE
);

-- Seasons
CREATE TABLE IF NOT EXISTS seasons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    series_id TEXT NOT NULL,
    season_number INTEGER NOT NULL,
    magnet_link TEXT NOT NULL,              -- Complete season torrent
    file_size INTEGER NOT NULL,             -- Total season size in bytes
    episode_count INTEGER NOT NULL,
    year INTEGER,                           -- Air year for this season
    video_quality TEXT,                     -- e.g., '1080p'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (series_id, season_number),
    FOREIGN KEY (series_id) REFERENCES series(id) ON DELETE CASCADE
);

-- Episodes (optional, for UI display)
CREATE TABLE IF NOT EXISTS episodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    season_id INTEGER NOT NULL,
    episode_number INTEGER NOT NULL,
    title TEXT,                             -- Episode title
    runtime INTEGER,                        -- Runtime in minutes
    UNIQUE (season_id, episode_number),
    FOREIGN KEY (season_id) REFERENCES seasons(id) ON DELETE CASCADE
);

-- ============================================================================
-- Download state tracking
-- ============================================================================

CREATE TABLE IF NOT EXISTS download_state (
    id TEXT PRIMARY KEY,                    -- movie_id or 'series_id_sN' format
    type TEXT NOT NULL CHECK(type IN ('movie', 'season')),
    status TEXT NOT NULL DEFAULT 'available' CHECK(status IN (
        'available',        -- Not downloaded yet
        'downloading',      -- In progress
        'ready',           -- Fully downloaded and ready
        'failed',          -- Download or processing failed
        'translation_failed' -- Video downloaded but translation failed
    )),

    -- Progress tracking
    progress REAL DEFAULT 0.0,              -- Overall progress 0.0-100.0
    phase TEXT,                             -- Current phase: 'video', 'subtitles', 'translation'
    phase_progress REAL DEFAULT 0.0,        -- Progress within current phase 0.0-100.0

    -- Video download
    video_progress REAL DEFAULT 0.0,        -- Video download progress 0.0-100.0

    -- Subtitle download
    subtitle_progress REAL DEFAULT 0.0,     -- Subtitle download progress 0.0-100.0
    subtitle_path TEXT,                     -- Path to original subtitle file

    -- Translation
    translation_progress REAL DEFAULT 0.0,  -- Translation progress 0.0-100.0
    translated_subtitle_path TEXT,          -- Path to translated subtitle file

    -- Error tracking
    error_message TEXT,
    error_details TEXT,                     -- Full error traceback

    -- File paths
    download_path TEXT,                     -- Local video file path
    torrent_info_hash TEXT,                 -- BitTorrent info hash

    -- Timestamps
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    failed_at TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- Watch history (for series episode tracking)
-- ============================================================================

CREATE TABLE IF NOT EXISTS watch_history (
    series_id TEXT NOT NULL,
    season_number INTEGER NOT NULL,
    episode_number INTEGER NOT NULL,
    file_path TEXT,                         -- Path to video file
    last_position INTEGER DEFAULT 0,        -- Playback position in milliseconds
    duration INTEGER,                       -- Total duration in milliseconds
    last_watched TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed BOOLEAN DEFAULT FALSE,        -- Watched >90%
    PRIMARY KEY (series_id, season_number, episode_number),
    FOREIGN KEY (series_id) REFERENCES series(id) ON DELETE CASCADE
);

-- ============================================================================
-- Subtitle cache
-- ============================================================================

CREATE TABLE IF NOT EXISTS subtitle_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_path TEXT NOT NULL,
    subtitle_path TEXT NOT NULL,
    language TEXT NOT NULL,                 -- Language code: 'en', 'pl', etc.
    source TEXT,                            -- Source: 'opensubtitles', 'manual', etc.
    hash TEXT,                              -- Video file hash for matching
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (video_path, language)
);

-- ============================================================================
-- API usage tracking (for cost management)
-- ============================================================================

CREATE TABLE IF NOT EXISTS api_usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service TEXT NOT NULL,                  -- 'gemini', 'opensubtitles', 'tts'
    operation TEXT NOT NULL,                -- 'translate', 'search', 'download', 'generate'
    item_id TEXT,                           -- Related movie/series ID
    tokens_used INTEGER DEFAULT 0,          -- For token-based APIs (Gemini)
    requests_count INTEGER DEFAULT 1,       -- Number of API requests
    estimated_cost REAL DEFAULT 0.0,        -- Estimated cost in USD
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- Indexes for performance
-- ============================================================================

-- Movies
CREATE INDEX IF NOT EXISTS idx_movies_year ON movies(year);
CREATE INDEX IF NOT EXISTS idx_movies_tmdb_id ON movies(tmdb_id);
CREATE INDEX IF NOT EXISTS idx_movies_imdb_id ON movies(imdb_id);

-- Series
CREATE INDEX IF NOT EXISTS idx_series_year ON series(year);
CREATE INDEX IF NOT EXISTS idx_series_tmdb_id ON series(tmdb_id);
CREATE INDEX IF NOT EXISTS idx_series_imdb_id ON series(imdb_id);

-- Seasons
CREATE INDEX IF NOT EXISTS idx_seasons_series_id ON seasons(series_id);

-- Download state
CREATE INDEX IF NOT EXISTS idx_download_state_status ON download_state(status);
CREATE INDEX IF NOT EXISTS idx_download_state_type ON download_state(type);

-- Watch history
CREATE INDEX IF NOT EXISTS idx_watch_history_series ON watch_history(series_id);
CREATE INDEX IF NOT EXISTS idx_watch_history_last_watched ON watch_history(last_watched DESC);

-- Subtitle cache
CREATE INDEX IF NOT EXISTS idx_subtitle_cache_video_path ON subtitle_cache(video_path);
CREATE INDEX IF NOT EXISTS idx_subtitle_cache_hash ON subtitle_cache(hash);

-- API usage
CREATE INDEX IF NOT EXISTS idx_api_usage_service ON api_usage(service);
CREATE INDEX IF NOT EXISTS idx_api_usage_timestamp ON api_usage(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_api_usage_item_id ON api_usage(item_id);
"""


def initialize_database(db_path: Optional[str] = None) -> None:
    """
    Initialize database with schema

    Args:
        db_path: Path to database file (default: hackflix.db)
    """
    if db_path is None:
        db_path = DEFAULT_DATABASE_FILE

    # Convert to Path object
    db_file = Path(db_path)

    # Create parent directory if needed
    db_file.parent.mkdir(parents=True, exist_ok=True)

    # Connect and create schema
    conn = sqlite3.connect(db_path)

    try:
        # Enable foreign keys
        conn.execute("PRAGMA foreign_keys = ON")

        # Create all tables and indexes
        conn.executescript(SCHEMA)

        # Set database version
        conn.execute(
            "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
            ("db_version", str(DATABASE_VERSION))
        )

        # Set initial catalog sync timestamp
        conn.execute(
            "INSERT OR IGNORE INTO metadata (key, value) VALUES (?, ?)",
            ("last_catalog_sync", "1970-01-01T00:00:00Z")
        )

        # Set creation timestamp
        conn.execute(
            "INSERT OR IGNORE INTO metadata (key, value) VALUES (?, ?)",
            ("created_at", datetime.now().isoformat())
        )

        conn.commit()
        print(f"✅ Database initialized: {db_path}")
        print(f"   Version: {DATABASE_VERSION}")
        print(f"   Tables created: 14")
        print(f"   Indexes created: 11")

    except Exception as e:
        conn.rollback()
        print(f"❌ Error initializing database: {e}")
        raise
    finally:
        conn.close()


def get_database_info(db_path: Optional[str] = None) -> dict:
    """
    Get database information

    Args:
        db_path: Path to database file

    Returns:
        Dictionary with database info
    """
    if db_path is None:
        db_path = DEFAULT_DATABASE_FILE

    if not Path(db_path).exists():
        return {"exists": False}

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # Get metadata
        cursor.execute("SELECT key, value FROM metadata")
        metadata = {row["key"]: row["value"] for row in cursor.fetchall()}

        # Get table counts
        counts = {}
        tables = [
            "movies", "series", "seasons", "download_state",
            "watch_history", "subtitle_cache", "api_usage"
        ]

        for table in tables:
            cursor.execute(f"SELECT COUNT(*) as count FROM {table}")
            counts[table] = cursor.fetchone()["count"]

        # Get database size
        db_size = Path(db_path).stat().st_size

        return {
            "exists": True,
            "path": str(db_path),
            "version": metadata.get("db_version"),
            "created_at": metadata.get("created_at"),
            "last_catalog_sync": metadata.get("last_catalog_sync"),
            "size_bytes": db_size,
            "size_mb": round(db_size / 1024 / 1024, 2),
            "counts": counts
        }

    finally:
        conn.close()


def verify_schema(db_path: Optional[str] = None) -> bool:
    """
    Verify database schema is correct

    Args:
        db_path: Path to database file

    Returns:
        True if schema is valid, False otherwise
    """
    if db_path is None:
        db_path = DEFAULT_DATABASE_FILE

    if not Path(db_path).exists():
        print(f"❌ Database does not exist: {db_path}")
        return False

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Expected tables
        expected_tables = [
            "metadata", "movies", "movie_genres", "movie_subtitle_languages",
            "series", "series_genres", "seasons", "episodes",
            "download_state", "watch_history", "subtitle_cache", "api_usage"
        ]

        # Get actual tables
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        actual_tables = [row[0] for row in cursor.fetchall()]

        # Check all expected tables exist
        missing_tables = set(expected_tables) - set(actual_tables)
        if missing_tables:
            print(f"❌ Missing tables: {missing_tables}")
            return False

        # Check database version
        cursor.execute("SELECT value FROM metadata WHERE key = 'db_version'")
        result = cursor.fetchone()
        if not result:
            print("❌ Database version not set")
            return False

        db_version = int(result[0])
        if db_version != DATABASE_VERSION:
            print(f"⚠️  Database version mismatch: {db_version} != {DATABASE_VERSION}")
            return False

        print(f"✅ Schema verification passed")
        print(f"   Tables: {len(actual_tables)}")
        print(f"   Version: {db_version}")
        return True

    except Exception as e:
        print(f"❌ Schema verification failed: {e}")
        return False
    finally:
        conn.close()


def main():
    """Command-line interface for database operations"""
    import sys
    import argparse

    parser = argparse.ArgumentParser(description="HackFlix Database Schema Management")
    parser.add_argument("--init", action="store_true", help="Initialize database")
    parser.add_argument("--info", action="store_true", help="Show database info")
    parser.add_argument("--verify", action="store_true", help="Verify schema")
    parser.add_argument("--db", default=DEFAULT_DATABASE_FILE, help="Database file path")

    args = parser.parse_args()

    if args.init:
        initialize_database(args.db)
    elif args.info:
        info = get_database_info(args.db)
        if info["exists"]:
            print(f"Database: {info['path']}")
            print(f"Version: {info['version']}")
            print(f"Size: {info['size_mb']} MB")
            print(f"Created: {info['created_at']}")
            print(f"Last Sync: {info['last_catalog_sync']}")
            print(f"\nTable Counts:")
            for table, count in info['counts'].items():
                print(f"  {table}: {count}")
        else:
            print(f"Database does not exist: {args.db}")
    elif args.verify:
        verify_schema(args.db)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
