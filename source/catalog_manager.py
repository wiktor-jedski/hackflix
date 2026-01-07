"""
Catalog manager for fetching and syncing movie/series catalog.

Handles:
- Fetching catalog.json from GitHub Pages
- Incremental sync based on timestamps
- Movie/series insertion into SQLite database
- Download state initialization
- PyQt5 signals for UI updates
"""

import requests
import json
import traceback
from datetime import datetime
from typing import Dict, List, Optional
from PyQt5.QtCore import QObject, pyqtSignal

from source.config import CATALOG_URL, DATABASE_FILE, SYNC_TIMEOUT
from source.db_utils import DatabaseConnection, get_metadata, set_metadata


class CatalogManager(QObject):
    """Manages catalog fetching and local database synchronization"""

    # Signals for UI updates
    sync_started = pyqtSignal()
    sync_progress = pyqtSignal(str, int)  # (message, percentage)
    sync_completed = pyqtSignal(int, int)  # (movies_count, series_count)
    sync_error = pyqtSignal(str)
    catalog_updated = pyqtSignal()  # Emit when local catalog changes

    def __init__(self, catalog_url: Optional[str] = None, db_path: Optional[str] = None):
        """
        Initialize catalog manager

        Args:
            catalog_url: URL to catalog.json (default: from config)
            db_path: Path to database file (default: from config)
        """
        super().__init__()
        self.catalog_url = catalog_url or str(CATALOG_URL)
        self.db_path = db_path or str(DATABASE_FILE)

    def close(self):
        """Close method for compatibility (no-op since connections are per-operation)"""
        pass

    def _get_db(self) -> DatabaseConnection:
        """
        Get a database connection for this thread

        Returns:
            DatabaseConnection instance (thread-safe)
        """
        return DatabaseConnection(self.db_path)

    def fetch_catalog(self) -> Dict:
        """
        Fetch catalog.json from server

        Returns:
            Parsed catalog dictionary

        Raises:
            Exception: If fetch fails or JSON is invalid
        """
        try:
            response = requests.get(self.catalog_url, timeout=SYNC_TIMEOUT)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            raise Exception(f"Failed to fetch catalog: {str(e)}")
        except json.JSONDecodeError as e:
            raise Exception(f"Invalid catalog JSON: {str(e)}")

    def get_last_sync_timestamp(self) -> str:
        """
        Get timestamp of last successful sync

        Returns:
            ISO timestamp string (default: 1970-01-01T00:00:00Z)
        """
        db = self._get_db()
        try:
            timestamp = get_metadata(db, "last_catalog_sync")
            return timestamp if timestamp else "1970-01-01T00:00:00Z"
        finally:
            db.close()

    def set_last_sync_timestamp(self, timestamp: str):
        """
        Update last sync timestamp

        Args:
            timestamp: ISO timestamp string
        """
        db = self._get_db()
        try:
            set_metadata(db, "last_catalog_sync", timestamp)
        finally:
            db.close()

    def sync_catalog(self):
        """
        Fetch and sync catalog with local database.
        Performs incremental sync based on last_updated timestamp.
        Emits signals for progress tracking.
        """
        try:
            self.sync_started.emit()
            self.sync_progress.emit("Fetching catalog from server...", 10)

            # Fetch remote catalog
            catalog = self.fetch_catalog()
            remote_timestamp = catalog.get("last_updated", "")
            local_timestamp = self.get_last_sync_timestamp()

            self.sync_progress.emit("Comparing versions...", 20)

            # Check if update needed
            if remote_timestamp <= local_timestamp:
                self.sync_progress.emit("Catalog is up to date", 100)

                # Get current counts
                db = self._get_db()
                try:
                    movie_count = db.fetch_one("SELECT COUNT(*) as count FROM movies")["count"]
                    series_count = db.fetch_one("SELECT COUNT(*) as count FROM series")["count"]
                finally:
                    db.close()

                self.sync_completed.emit(movie_count, series_count)
                return

            # Perform sync
            self.sync_progress.emit("Syncing movies...", 40)
            movies_synced = self._sync_movies(catalog.get("movies", []))

            self.sync_progress.emit("Syncing series...", 70)
            series_synced = self._sync_series(catalog.get("series", []))

            # Update last sync timestamp
            self.set_last_sync_timestamp(remote_timestamp)

            self.sync_progress.emit("Sync complete!", 100)
            self.sync_completed.emit(movies_synced, series_synced)
            self.catalog_updated.emit()

        except Exception as e:
            error_msg = f"Sync failed: {str(e)}"
            print(f"ERROR: {error_msg}")
            traceback.print_exc()
            self.sync_error.emit(error_msg)

    def _sync_movies(self, movies: List[Dict]) -> int:
        """
        Sync movies to database

        Args:
            movies: List of movie dictionaries from catalog

        Returns:
            Number of movies synced
        """
        count = 0

        db = self._get_db()
        try:
            with db.transaction() as conn:
                for movie in movies:
                    try:
                        # Insert or update movie
                        conn.execute("""
                        INSERT OR REPLACE INTO movies
                        (id, title, year, description, magnet_link, file_size,
                         poster_url, imdb_id, tmdb_id, runtime, video_quality,
                         video_codec, audio_codec, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """, (
                        movie["id"],
                        movie["title"],
                        movie["year"],
                        movie.get("description", ""),
                        movie["magnet_link"],
                        movie["file_size"],
                        movie.get("poster_url"),
                        movie.get("imdb_id"),
                        movie.get("tmdb_id"),
                        movie.get("runtime"),
                        movie.get("video_quality"),
                        movie.get("video_codec"),
                        movie.get("audio_codec")
                        ))

                        # Clear existing genres
                        conn.execute("DELETE FROM movie_genres WHERE movie_id = ?", (movie["id"],))

                        # Insert genres
                        for genre in movie.get("genre", []):
                            conn.execute(
                                "INSERT INTO movie_genres (movie_id, genre) VALUES (?, ?)",
                                (movie["id"], genre)
                            )

                        # Clear existing subtitle languages
                        conn.execute("DELETE FROM movie_subtitle_languages WHERE movie_id = ?", (movie["id"],))

                        # Insert subtitle languages
                        for lang in movie.get("subtitle_languages", []):
                            conn.execute(
                                "INSERT INTO movie_subtitle_languages (movie_id, language_code) VALUES (?, ?)",
                                (movie["id"], lang)
                            )

                        # Initialize download state if not exists
                        conn.execute("""
                            INSERT OR IGNORE INTO download_state
                            (id, type, status, progress)
                            VALUES (?, 'movie', 'available', 0.0)
                        """, (movie["id"],))

                        count += 1
                    except Exception as e:
                        print(f"Error syncing movie {movie.get('id', 'unknown')}: {e}")
                        traceback.print_exc()
        finally:
            db.close()

        return count

    def _sync_series(self, series_list: List[Dict]) -> int:
        """
        Sync series to database

        Args:
            series_list: List of series dictionaries from catalog

        Returns:
            Number of series synced
        """
        count = 0

        db = self._get_db()
        try:
            with db.transaction() as conn:
                for series in series_list:
                    try:
                        # Insert or update series
                        conn.execute("""
                        INSERT OR REPLACE INTO series
                        (id, title, year, description, poster_url, imdb_id, tmdb_id, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """, (
                        series["id"],
                        series["title"],
                        series["year"],
                        series.get("description", ""),
                        series.get("poster_url"),
                        series.get("imdb_id"),
                        series.get("tmdb_id")
                        ))

                        # Clear existing genres
                        conn.execute("DELETE FROM series_genres WHERE series_id = ?", (series["id"],))

                        # Insert genres
                        for genre in series.get("genre", []):
                            conn.execute(
                                "INSERT INTO series_genres (series_id, genre) VALUES (?, ?)",
                                (series["id"], genre)
                            )

                        # Sync seasons
                        for season in series.get("seasons", []):
                            conn.execute("""
                                INSERT OR REPLACE INTO seasons
                                (series_id, season_number, magnet_link, file_size,
                                 episode_count, year, video_quality)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            """, (
                                series["id"],
                                season["season_number"],
                                season["magnet_link"],
                                season["file_size"],
                                season["episode_count"],
                                season.get("year"),
                                season.get("video_quality")
                            ))

                            # Initialize download state for season
                            season_id = f"{series['id']}_s{season['season_number']}"
                            conn.execute("""
                                INSERT OR IGNORE INTO download_state
                                (id, type, status, progress)
                                VALUES (?, 'season', 'available', 0.0)
                            """, (season_id,))

                        count += 1
                    except Exception as e:
                        print(f"Error syncing series {series.get('id', 'unknown')}: {e}")
                        traceback.print_exc()
        finally:
            db.close()

        return count

    def get_catalog_info(self) -> Dict:
        """
        Get information about local catalog

        Returns:
            Dictionary with catalog statistics
        """
        db = self._get_db()
        try:
            movie_count = db.fetch_one("SELECT COUNT(*) as count FROM movies")["count"]
            series_count = db.fetch_one("SELECT COUNT(*) as count FROM series")["count"]
            season_count = db.fetch_one("SELECT COUNT(*) as count FROM seasons")["count"]
            last_sync = get_metadata(db, "last_catalog_sync")

            return {
                "movies": movie_count,
                "series": series_count,
                "seasons": season_count,
                "last_sync": last_sync,
                "catalog_url": self.catalog_url
            }
        finally:
            db.close()


def main():
    """Command-line interface for testing catalog sync"""
    import sys
    from PyQt5.QtCore import QCoreApplication

    app = QCoreApplication(sys.argv)

    manager = CatalogManager()

    # Connect signals
    manager.sync_started.connect(lambda: print("📥 Sync started..."))
    manager.sync_progress.connect(lambda msg, pct: print(f"  [{pct:3d}%] {msg}"))
    manager.sync_completed.connect(
        lambda movies, series: print(f"✅ Sync completed: {movies} movies, {series} series")
    )
    manager.sync_error.connect(lambda err: print(f"❌ Sync error: {err}"))

    print("=" * 60)
    print("🎬 HackFlix Catalog Sync")
    print("=" * 60)

    # Show current catalog info
    info = manager.get_catalog_info()
    print(f"\nCurrent catalog:")
    print(f"  Movies: {info['movies']}")
    print(f"  Series: {info['series']}")
    print(f"  Seasons: {info['seasons']}")
    print(f"  Last sync: {info['last_sync']}")
    print(f"  Catalog URL: {info['catalog_url']}")

    print(f"\nStarting sync...\n")

    # Start sync
    manager.sync_catalog()

    # Cleanup
    manager.close()

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
