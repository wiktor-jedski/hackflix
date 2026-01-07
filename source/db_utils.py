"""
Database utility functions for HackFlix

Provides connection management, transaction handling, and common queries.
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime

from source.db_schema import DEFAULT_DATABASE_FILE, initialize_database


class DatabaseConnection:
    """
    Database connection manager with connection pooling
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize database connection manager

        Args:
            db_path: Path to database file (default: hackflix.db)
        """
        self.db_path = db_path or DEFAULT_DATABASE_FILE
        self._connection = None

        # Ensure database exists
        if not Path(self.db_path).exists():
            initialize_database(self.db_path)

    def get_connection(self) -> sqlite3.Connection:
        """
        Get database connection (reuses existing connection)

        Returns:
            SQLite connection object
        """
        if self._connection is None:
            self._connection = sqlite3.connect(self.db_path)
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("PRAGMA foreign_keys = ON")

        return self._connection

    def close(self):
        """Close database connection"""
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    @contextmanager
    def transaction(self):
        """
        Context manager for database transactions

        Usage:
            with db.transaction() as conn:
                conn.execute("INSERT INTO ...")
        """
        conn = self.get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def execute(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        """
        Execute a query and return cursor

        Args:
            query: SQL query
            params: Query parameters

        Returns:
            Cursor object
        """
        conn = self.get_connection()
        return conn.execute(query, params)

    def execute_many(self, query: str, params_list: List[tuple]) -> None:
        """
        Execute query with multiple parameter sets

        Args:
            query: SQL query
            params_list: List of parameter tuples
        """
        conn = self.get_connection()
        conn.executemany(query, params_list)
        conn.commit()

    def fetch_one(self, query: str, params: tuple = ()) -> Optional[sqlite3.Row]:
        """
        Execute query and fetch single row

        Args:
            query: SQL query
            params: Query parameters

        Returns:
            Row object or None
        """
        cursor = self.execute(query, params)
        return cursor.fetchone()

    def fetch_all(self, query: str, params: tuple = ()) -> List[sqlite3.Row]:
        """
        Execute query and fetch all rows

        Args:
            query: SQL query
            params: Query parameters

        Returns:
            List of Row objects
        """
        cursor = self.execute(query, params)
        return cursor.fetchall()


# ============================================================================
# Catalog Queries
# ============================================================================

def get_all_movies(db: DatabaseConnection) -> List[Dict[str, Any]]:
    """
    Get all movies with genres and subtitle languages

    Args:
        db: Database connection

    Returns:
        List of movie dictionaries
    """
    movies = db.fetch_all("""
        SELECT
            id, title, year, description, magnet_link, file_size,
            poster_url, imdb_id, tmdb_id, runtime,
            video_quality, video_codec, audio_codec
        FROM movies
        ORDER BY year DESC, title ASC
    """)

    result = []
    for movie in movies:
        movie_dict = dict(movie)

        # Get genres
        genres = db.fetch_all(
            "SELECT genre FROM movie_genres WHERE movie_id = ? ORDER BY genre",
            (movie["id"],)
        )
        movie_dict["genres"] = [g["genre"] for g in genres]

        # Get subtitle languages
        langs = db.fetch_all(
            "SELECT language_code FROM movie_subtitle_languages WHERE movie_id = ? ORDER BY language_code",
            (movie["id"],)
        )
        movie_dict["subtitle_languages"] = [l["language_code"] for l in langs]

        result.append(movie_dict)

    return result


def get_all_series(db: DatabaseConnection) -> List[Dict[str, Any]]:
    """
    Get all series with genres and seasons

    Args:
        db: Database connection

    Returns:
        List of series dictionaries
    """
    series_list = db.fetch_all("""
        SELECT
            id, title, year, description, poster_url, imdb_id, tmdb_id
        FROM series
        ORDER BY year DESC, title ASC
    """)

    result = []
    for series in series_list:
        series_dict = dict(series)

        # Get genres
        genres = db.fetch_all(
            "SELECT genre FROM series_genres WHERE series_id = ? ORDER BY genre",
            (series["id"],)
        )
        series_dict["genres"] = [g["genre"] for g in genres]

        # Get seasons
        seasons = db.fetch_all(
            """
            SELECT
                season_number, magnet_link, file_size, episode_count,
                year, video_quality
            FROM seasons
            WHERE series_id = ?
            ORDER BY season_number
            """,
            (series["id"],)
        )
        series_dict["seasons"] = [dict(s) for s in seasons]

        result.append(series_dict)

    return result


def get_movie_by_id(db: DatabaseConnection, movie_id: str) -> Optional[Dict[str, Any]]:
    """
    Get single movie by ID

    Args:
        db: Database connection
        movie_id: Movie ID

    Returns:
        Movie dictionary or None
    """
    movies = get_all_movies(db)
    return next((m for m in movies if m["id"] == movie_id), None)


def get_series_by_id(db: DatabaseConnection, series_id: str) -> Optional[Dict[str, Any]]:
    """
    Get single series by ID

    Args:
        db: Database connection
        series_id: Series ID

    Returns:
        Series dictionary or None
    """
    series_list = get_all_series(db)
    return next((s for s in series_list if s["id"] == series_id), None)


def search_content(
    db: DatabaseConnection,
    query: str,
    content_type: Optional[str] = None
) -> Dict[str, List[Dict]]:
    """
    Search movies and series by title

    Args:
        db: Database connection
        query: Search query
        content_type: Filter by type ('movie', 'series', or None for both)

    Returns:
        Dictionary with 'movies' and 'series' lists
    """
    pattern = f"%{query}%"
    result = {"movies": [], "series": []}

    if content_type is None or content_type == "movie":
        movies = db.fetch_all(
            "SELECT id FROM movies WHERE title LIKE ? COLLATE NOCASE",
            (pattern,)
        )
        result["movies"] = [
            get_movie_by_id(db, m["id"]) for m in movies
        ]

    if content_type is None or content_type == "series":
        series = db.fetch_all(
            "SELECT id FROM series WHERE title LIKE ? COLLATE NOCASE",
            (pattern,)
        )
        result["series"] = [
            get_series_by_id(db, s["id"]) for s in series
        ]

    return result


def get_movies_by_genre(db: DatabaseConnection, genre: str) -> List[Dict[str, Any]]:
    """
    Get all movies in a specific genre

    Args:
        db: Database connection
        genre: Genre name

    Returns:
        List of movie dictionaries
    """
    movie_ids = db.fetch_all(
        "SELECT movie_id FROM movie_genres WHERE genre = ?",
        (genre,)
    )

    return [get_movie_by_id(db, m["movie_id"]) for m in movie_ids]


def get_series_by_genre(db: DatabaseConnection, genre: str) -> List[Dict[str, Any]]:
    """
    Get all series in a specific genre

    Args:
        db: Database connection
        genre: Genre name

    Returns:
        List of series dictionaries
    """
    series_ids = db.fetch_all(
        "SELECT series_id FROM series_genres WHERE genre = ?",
        (genre,)
    )

    return [get_series_by_id(db, s["series_id"]) for s in series_ids]


# ============================================================================
# Download State Queries
# ============================================================================

def get_download_state(
    db: DatabaseConnection,
    item_id: str
) -> Optional[Dict[str, Any]]:
    """
    Get download state for a movie or season

    Args:
        db: Database connection
        item_id: Movie ID or 'series_id_sN' format

    Returns:
        Download state dictionary or None
    """
    state = db.fetch_one(
        "SELECT * FROM download_state WHERE id = ?",
        (item_id,)
    )

    return dict(state) if state else None


def update_download_state(
    db: DatabaseConnection,
    item_id: str,
    **kwargs
) -> None:
    """
    Update download state fields

    Args:
        db: Database connection
        item_id: Movie ID or season ID
        **kwargs: Fields to update (status, progress, phase, etc.)
    """
    if not kwargs:
        return

    # Build UPDATE query
    fields = ", ".join(f"{k} = ?" for k in kwargs.keys())
    values = list(kwargs.values()) + [item_id]

    query = f"""
        UPDATE download_state
        SET {fields}, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """

    with db.transaction() as conn:
        conn.execute(query, values)


def get_downloads_by_status(
    db: DatabaseConnection,
    status: str
) -> List[Dict[str, Any]]:
    """
    Get all downloads with specific status

    Args:
        db: Database connection
        status: Status value ('downloading', 'ready', 'failed', etc.)

    Returns:
        List of download state dictionaries
    """
    states = db.fetch_all(
        "SELECT * FROM download_state WHERE status = ? ORDER BY updated_at DESC",
        (status,)
    )

    return [dict(s) for s in states]


# ============================================================================
# Watch History Queries
# ============================================================================

def get_watch_history(
    db: DatabaseConnection,
    series_id: str
) -> List[Dict[str, Any]]:
    """
    Get watch history for a series

    Args:
        db: Database connection
        series_id: Series ID

    Returns:
        List of watch history records
    """
    history = db.fetch_all(
        """
        SELECT * FROM watch_history
        WHERE series_id = ?
        ORDER BY season_number, episode_number
        """,
        (series_id,)
    )

    return [dict(h) for h in history]


def update_watch_position(
    db: DatabaseConnection,
    series_id: str,
    season_number: int,
    episode_number: int,
    position: int,
    duration: Optional[int] = None
) -> None:
    """
    Update playback position for an episode

    Args:
        db: Database connection
        series_id: Series ID
        season_number: Season number
        episode_number: Episode number
        position: Playback position in milliseconds
        duration: Total duration in milliseconds
    """
    # Check if >90% watched
    completed = False
    if duration and position > 0:
        completed = (position / duration) > 0.9

    with db.transaction() as conn:
        conn.execute(
            """
            INSERT INTO watch_history
                (series_id, season_number, episode_number, last_position, duration, completed)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(series_id, season_number, episode_number)
            DO UPDATE SET
                last_position = excluded.last_position,
                duration = excluded.duration,
                completed = excluded.completed,
                last_watched = CURRENT_TIMESTAMP
            """,
            (series_id, season_number, episode_number, position, duration, completed)
        )


def get_next_episode(
    db: DatabaseConnection,
    series_id: str
) -> Optional[Tuple[int, int]]:
    """
    Get next unwatched episode for a series

    Args:
        db: Database connection
        series_id: Series ID

    Returns:
        (season_number, episode_number) tuple or None
    """
    # Get last watched episode
    last_watched = db.fetch_one(
        """
        SELECT season_number, episode_number
        FROM watch_history
        WHERE series_id = ? AND completed = TRUE
        ORDER BY season_number DESC, episode_number DESC
        LIMIT 1
        """,
        (series_id,)
    )

    if not last_watched:
        # Start from S01E01
        return (1, 1)

    # Get episode count for last watched season
    season = db.fetch_one(
        """
        SELECT episode_count
        FROM seasons
        WHERE series_id = ? AND season_number = ?
        """,
        (series_id, last_watched["season_number"])
    )

    if not season:
        return None

    # Next episode in same season
    if last_watched["episode_number"] < season["episode_count"]:
        return (last_watched["season_number"], last_watched["episode_number"] + 1)

    # Next season
    next_season = db.fetch_one(
        """
        SELECT season_number, episode_count
        FROM seasons
        WHERE series_id = ? AND season_number > ?
        ORDER BY season_number
        LIMIT 1
        """,
        (series_id, last_watched["season_number"])
    )

    if next_season:
        return (next_season["season_number"], 1)

    # Series completed
    return None


# ============================================================================
# API Usage Tracking
# ============================================================================

def log_api_usage(
    db: DatabaseConnection,
    service: str,
    operation: str,
    item_id: Optional[str] = None,
    tokens_used: int = 0,
    requests_count: int = 1,
    estimated_cost: float = 0.0,
    success: bool = True,
    error_message: Optional[str] = None
) -> None:
    """
    Log API usage for cost tracking

    Args:
        db: Database connection
        service: Service name ('gemini', 'opensubtitles', 'tts')
        operation: Operation type ('translate', 'search', 'download', 'generate')
        item_id: Related movie/series ID
        tokens_used: Number of tokens (for token-based APIs)
        requests_count: Number of API requests
        estimated_cost: Estimated cost in USD
        success: Whether operation succeeded
        error_message: Error details if failed
    """
    with db.transaction() as conn:
        conn.execute(
            """
            INSERT INTO api_usage
                (service, operation, item_id, tokens_used, requests_count,
                 estimated_cost, success, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (service, operation, item_id, tokens_used, requests_count,
             estimated_cost, success, error_message)
        )


def get_api_usage_stats(
    db: DatabaseConnection,
    service: Optional[str] = None,
    days: int = 30
) -> Dict[str, Any]:
    """
    Get API usage statistics

    Args:
        db: Database connection
        service: Filter by service (None for all)
        days: Number of days to look back

    Returns:
        Dictionary with usage statistics
    """
    where_clause = "WHERE timestamp >= datetime('now', ?)"
    params = [f"-{days} days"]

    if service:
        where_clause += " AND service = ?"
        params.append(service)

    # Total requests and cost
    totals = db.fetch_one(
        f"""
        SELECT
            COUNT(*) as total_requests,
            SUM(tokens_used) as total_tokens,
            SUM(estimated_cost) as total_cost,
            SUM(CASE WHEN success = TRUE THEN 1 ELSE 0 END) as successful_requests,
            SUM(CASE WHEN success = FALSE THEN 1 ELSE 0 END) as failed_requests
        FROM api_usage
        {where_clause}
        """,
        params
    )

    # By service breakdown
    by_service = db.fetch_all(
        f"""
        SELECT
            service,
            COUNT(*) as requests,
            SUM(tokens_used) as tokens,
            SUM(estimated_cost) as cost
        FROM api_usage
        {where_clause}
        GROUP BY service
        ORDER BY cost DESC
        """,
        params
    )

    return {
        "period_days": days,
        "total_requests": totals["total_requests"] or 0,
        "total_tokens": totals["total_tokens"] or 0,
        "total_cost": round(totals["total_cost"] or 0, 4),
        "successful_requests": totals["successful_requests"] or 0,
        "failed_requests": totals["failed_requests"] or 0,
        "by_service": [dict(s) for s in by_service]
    }


# ============================================================================
# Metadata Queries
# ============================================================================

def get_metadata(db: DatabaseConnection, key: str) -> Optional[str]:
    """
    Get metadata value by key

    Args:
        db: Database connection
        key: Metadata key

    Returns:
        Value or None
    """
    result = db.fetch_one(
        "SELECT value FROM metadata WHERE key = ?",
        (key,)
    )
    return result["value"] if result else None


def set_metadata(db: DatabaseConnection, key: str, value: str) -> None:
    """
    Set metadata value

    Args:
        db: Database connection
        key: Metadata key
        value: Metadata value
    """
    with db.transaction() as conn:
        conn.execute(
            """
            INSERT INTO metadata (key, value)
            VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = CURRENT_TIMESTAMP
            """,
            (key, value)
        )
