"""
Comprehensive database tests for HackFlix

Tests all tables, relationships, indexes, and utility functions.
"""

import os
import sys
import sqlite3
import tempfile
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from source.db_schema import (
    initialize_database,
    get_database_info,
    verify_schema,
    DATABASE_VERSION
)
from source.db_utils import (
    DatabaseConnection,
    get_all_movies,
    get_all_series,
    get_movie_by_id,
    get_series_by_id,
    search_content,
    get_movies_by_genre,
    get_series_by_genre,
    get_download_state,
    update_download_state,
    get_downloads_by_status,
    get_watch_history,
    update_watch_position,
    get_next_episode,
    log_api_usage,
    get_api_usage_stats,
    get_metadata,
    set_metadata
)


class TestDatabase:
    """Database test suite"""

    def __init__(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test.db")
        self.errors = []
        self.passed = 0
        self.failed = 0

    def assert_true(self, condition: bool, message: str):
        """Assert condition is True"""
        if condition:
            self.passed += 1
            print(f"  ✅ {message}")
        else:
            self.failed += 1
            self.errors.append(message)
            print(f"  ❌ {message}")

    def assert_equal(self, actual, expected, message: str):
        """Assert values are equal"""
        if actual == expected:
            self.passed += 1
            print(f"  ✅ {message}")
        else:
            self.failed += 1
            error = f"{message} (expected: {expected}, got: {actual})"
            self.errors.append(error)
            print(f"  ❌ {error}")

    def test_initialization(self):
        """Test database initialization"""
        print("\n📋 Test: Database Initialization")

        # Initialize database
        initialize_database(self.db_path)

        # Check file exists
        self.assert_true(
            Path(self.db_path).exists(),
            "Database file created"
        )

        # Check version
        info = get_database_info(self.db_path)
        self.assert_equal(
            info["version"],
            str(DATABASE_VERSION),
            f"Database version is {DATABASE_VERSION}"
        )

        # Verify schema
        valid = verify_schema(self.db_path)
        self.assert_true(valid, "Schema validation passed")

    def test_tables_exist(self):
        """Test all tables exist"""
        print("\n📋 Test: Table Existence")

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        expected_tables = [
            "metadata", "movies", "movie_genres", "movie_subtitle_languages",
            "series", "series_genres", "seasons", "episodes",
            "download_state", "watch_history", "subtitle_cache", "api_usage"
        ]

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        actual_tables = [row[0] for row in cursor.fetchall()]

        for table in expected_tables:
            self.assert_true(
                table in actual_tables,
                f"Table '{table}' exists"
            )

        conn.close()

    def test_indexes_exist(self):
        """Test all indexes exist"""
        print("\n📋 Test: Index Existence")

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
        )
        indexes = [row[0] for row in cursor.fetchall()]

        self.assert_true(
            len(indexes) >= 11,
            f"At least 11 indexes created ({len(indexes)} found)"
        )

        conn.close()

    def test_foreign_keys_enabled(self):
        """Test foreign key enforcement"""
        print("\n📋 Test: Foreign Key Enforcement")

        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")

        # Try to insert genre for non-existent movie
        try:
            conn.execute(
                "INSERT INTO movie_genres (movie_id, genre) VALUES (?, ?)",
                ("movie_nonexistent", "Action")
            )
            conn.commit()
            self.assert_true(False, "Foreign key constraint enforced")
        except sqlite3.IntegrityError:
            self.assert_true(True, "Foreign key constraint enforced")

        conn.close()

    def test_movie_insertion(self):
        """Test inserting movies with genres and subtitles"""
        print("\n📋 Test: Movie Insertion")

        db = DatabaseConnection(self.db_path)

        with db.transaction() as conn:
            # Insert movie
            conn.execute(
                """
                INSERT INTO movies
                    (id, title, year, description, magnet_link, file_size, imdb_id, tmdb_id, runtime)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("movie_test1", "Test Movie", 2024, "Test description",
                 "magnet:?xt=urn:btih:1234567890abcdef1234567890abcdef12345678",
                 2000000000, "tt1234567", 12345, 120)
            )

            # Insert genres
            conn.executemany(
                "INSERT INTO movie_genres (movie_id, genre) VALUES (?, ?)",
                [("movie_test1", "Action"), ("movie_test1", "Sci-Fi")]
            )

            # Insert subtitle languages
            conn.executemany(
                "INSERT INTO movie_subtitle_languages (movie_id, language_code) VALUES (?, ?)",
                [("movie_test1", "en"), ("movie_test1", "pl")]
            )

        # Verify
        movie = get_movie_by_id(db, "movie_test1")
        self.assert_true(movie is not None, "Movie retrieved")
        self.assert_equal(movie["title"], "Test Movie", "Movie title correct")
        self.assert_equal(len(movie["genres"]), 2, "2 genres inserted")
        self.assert_equal(len(movie["subtitle_languages"]), 2, "2 subtitle languages inserted")

        db.close()

    def test_series_insertion(self):
        """Test inserting series with seasons"""
        print("\n📋 Test: Series Insertion")

        db = DatabaseConnection(self.db_path)

        with db.transaction() as conn:
            # Insert series
            conn.execute(
                """
                INSERT INTO series
                    (id, title, year, description, imdb_id, tmdb_id)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("series_test1", "Test Series", 2024, "Test description", "tt7654321", 54321)
            )

            # Insert genres
            conn.executemany(
                "INSERT INTO series_genres (series_id, genre) VALUES (?, ?)",
                [("series_test1", "Drama"), ("series_test1", "Crime")]
            )

            # Insert seasons
            conn.executemany(
                """
                INSERT INTO seasons
                    (series_id, season_number, magnet_link, file_size, episode_count, video_quality)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    ("series_test1", 1, "magnet:?xt=urn:btih:abcd1234", 5000000000, 10, "1080p"),
                    ("series_test1", 2, "magnet:?xt=urn:btih:abcd5678", 6000000000, 12, "1080p")
                ]
            )

        # Verify
        series = get_series_by_id(db, "series_test1")
        self.assert_true(series is not None, "Series retrieved")
        self.assert_equal(series["title"], "Test Series", "Series title correct")
        self.assert_equal(len(series["genres"]), 2, "2 genres inserted")
        self.assert_equal(len(series["seasons"]), 2, "2 seasons inserted")
        self.assert_equal(series["seasons"][0]["episode_count"], 10, "Season 1 has 10 episodes")

        db.close()

    def test_cascade_delete(self):
        """Test CASCADE delete for genres when movie is deleted"""
        print("\n📋 Test: CASCADE Delete")

        db = DatabaseConnection(self.db_path)

        with db.transaction() as conn:
            # Insert test movie with genre
            conn.execute(
                """
                INSERT INTO movies
                    (id, title, year, description, magnet_link, file_size, imdb_id, tmdb_id, runtime)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("movie_delete_test", "Delete Test", 2024, "Test", "magnet:?xt=urn:btih:test",
                 1000000000, "tt9999999", 99999, 90)
            )
            conn.execute(
                "INSERT INTO movie_genres (movie_id, genre) VALUES (?, ?)",
                ("movie_delete_test", "Action")
            )

        # Check genre exists
        genre_count = db.fetch_one(
            "SELECT COUNT(*) as count FROM movie_genres WHERE movie_id = ?",
            ("movie_delete_test",)
        )
        self.assert_equal(genre_count["count"], 1, "Genre inserted")

        # Delete movie
        with db.transaction() as conn:
            conn.execute("DELETE FROM movies WHERE id = ?", ("movie_delete_test",))

        # Check genre deleted
        genre_count = db.fetch_one(
            "SELECT COUNT(*) as count FROM movie_genres WHERE movie_id = ?",
            ("movie_delete_test",)
        )
        self.assert_equal(genre_count["count"], 0, "Genre CASCADE deleted")

        db.close()

    def test_search_functionality(self):
        """Test content search"""
        print("\n📋 Test: Search Functionality")

        db = DatabaseConnection(self.db_path)

        # Search for test content
        results = search_content(db, "test")

        self.assert_true(
            len(results["movies"]) > 0,
            f"Found {len(results['movies'])} movie(s)"
        )
        self.assert_true(
            len(results["series"]) > 0,
            f"Found {len(results['series'])} series"
        )

        # Case-insensitive search
        results_lower = search_content(db, "TEST")
        self.assert_equal(
            len(results_lower["movies"]),
            len(results["movies"]),
            "Search is case-insensitive"
        )

        db.close()

    def test_genre_filtering(self):
        """Test filtering by genre"""
        print("\n📋 Test: Genre Filtering")

        db = DatabaseConnection(self.db_path)

        # Get movies by genre
        action_movies = get_movies_by_genre(db, "Action")
        self.assert_true(
            len(action_movies) > 0,
            f"Found {len(action_movies)} Action movie(s)"
        )

        # Get series by genre
        drama_series = get_series_by_genre(db, "Drama")
        self.assert_true(
            len(drama_series) > 0,
            f"Found {len(drama_series)} Drama series"
        )

        db.close()

    def test_download_state_tracking(self):
        """Test download state management"""
        print("\n📋 Test: Download State Tracking")

        db = DatabaseConnection(self.db_path)

        # Insert download state
        with db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO download_state
                    (id, type, status, progress, phase, phase_progress)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                ("movie_test1", "movie", "downloading", 50.0, "video", 75.0)
            )

        # Get state
        state = get_download_state(db, "movie_test1")
        self.assert_true(state is not None, "Download state retrieved")
        self.assert_equal(state["status"], "downloading", "Status is 'downloading'")
        self.assert_equal(state["progress"], 50.0, "Progress is 50%")

        # Update state
        update_download_state(
            db,
            "movie_test1",
            progress=100.0,
            status="ready",
            phase="translation",
            phase_progress=100.0
        )

        # Verify update
        state = get_download_state(db, "movie_test1")
        self.assert_equal(state["status"], "ready", "Status updated to 'ready'")
        self.assert_equal(state["progress"], 100.0, "Progress updated to 100%")

        # Get by status
        ready_downloads = get_downloads_by_status(db, "ready")
        self.assert_true(
            len(ready_downloads) > 0,
            "Found downloads with status 'ready'"
        )

        db.close()

    def test_watch_history(self):
        """Test watch history tracking"""
        print("\n📋 Test: Watch History")

        db = DatabaseConnection(self.db_path)

        # Update watch position
        update_watch_position(
            db,
            series_id="series_test1",
            season_number=1,
            episode_number=1,
            position=120000,  # 2 minutes
            duration=2400000  # 40 minutes
        )

        # Get history
        history = get_watch_history(db, "series_test1")
        self.assert_equal(len(history), 1, "Watch history entry created")
        self.assert_equal(history[0]["last_position"], 120000, "Position saved correctly")

        # Mark episode as completed
        update_watch_position(
            db,
            series_id="series_test1",
            season_number=1,
            episode_number=1,
            position=2300000,  # 38 minutes (>90%)
            duration=2400000
        )

        history = get_watch_history(db, "series_test1")
        self.assert_equal(history[0]["completed"], 1, "Episode marked as completed")

        # Test next episode detection
        next_ep = get_next_episode(db, "series_test1")
        self.assert_equal(next_ep, (1, 2), "Next episode is S01E02")

        db.close()

    def test_api_usage_tracking(self):
        """Test API usage logging"""
        print("\n📋 Test: API Usage Tracking")

        db = DatabaseConnection(self.db_path)

        # Log API usage
        log_api_usage(
            db,
            service="gemini",
            operation="translate",
            item_id="movie_test1",
            tokens_used=5000,
            requests_count=1,
            estimated_cost=0.025,
            success=True
        )

        log_api_usage(
            db,
            service="opensubtitles",
            operation="search",
            item_id="movie_test1",
            requests_count=1,
            estimated_cost=0.0,
            success=True
        )

        # Get stats
        stats = get_api_usage_stats(db, days=30)

        self.assert_equal(stats["total_requests"], 2, "2 API requests logged")
        self.assert_equal(stats["total_tokens"], 5000, "5000 tokens logged")
        self.assert_equal(stats["successful_requests"], 2, "2 successful requests")
        self.assert_true(stats["total_cost"] > 0, "Cost tracked")

        # Service-specific stats
        gemini_stats = get_api_usage_stats(db, service="gemini", days=30)
        self.assert_equal(gemini_stats["total_requests"], 1, "1 Gemini request")

        db.close()

    def test_metadata_operations(self):
        """Test metadata get/set"""
        print("\n📋 Test: Metadata Operations")

        db = DatabaseConnection(self.db_path)

        # Set metadata
        set_metadata(db, "test_key", "test_value")

        # Get metadata
        value = get_metadata(db, "test_key")
        self.assert_equal(value, "test_value", "Metadata stored and retrieved")

        # Update metadata
        set_metadata(db, "test_key", "updated_value")
        value = get_metadata(db, "test_key")
        self.assert_equal(value, "updated_value", "Metadata updated")

        # Check system metadata
        db_version = get_metadata(db, "db_version")
        self.assert_equal(db_version, str(DATABASE_VERSION), "Database version in metadata")

        db.close()

    def test_unique_constraints(self):
        """Test UNIQUE constraints"""
        print("\n📋 Test: UNIQUE Constraints")

        db = DatabaseConnection(self.db_path)

        # Try to insert duplicate movie genre
        try:
            with db.transaction() as conn:
                conn.execute(
                    "INSERT INTO movie_genres (movie_id, genre) VALUES (?, ?)",
                    ("movie_test1", "Action")  # Already exists from earlier test
                )
            self.assert_true(False, "UNIQUE constraint on movie_genres enforced")
        except sqlite3.IntegrityError:
            self.assert_true(True, "UNIQUE constraint on movie_genres enforced")

        # Try to insert duplicate season
        try:
            with db.transaction() as conn:
                conn.execute(
                    """
                    INSERT INTO seasons
                        (series_id, season_number, magnet_link, file_size, episode_count, video_quality)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    ("series_test1", 1, "magnet:?xt=test", 1000000, 10, "720p")
                )
            self.assert_true(False, "UNIQUE constraint on seasons enforced")
        except sqlite3.IntegrityError:
            self.assert_true(True, "UNIQUE constraint on seasons enforced")

        db.close()

    def cleanup(self):
        """Clean up test database"""
        if Path(self.db_path).exists():
            os.remove(self.db_path)
        if Path(self.temp_dir).exists():
            os.rmdir(self.temp_dir)

    def run_all_tests(self):
        """Run all tests"""
        print("=" * 60)
        print("🧪 HackFlix Database Test Suite")
        print("=" * 60)

        self.test_initialization()
        self.test_tables_exist()
        self.test_indexes_exist()
        self.test_foreign_keys_enabled()
        self.test_movie_insertion()
        self.test_series_insertion()
        self.test_cascade_delete()
        self.test_search_functionality()
        self.test_genre_filtering()
        self.test_download_state_tracking()
        self.test_watch_history()
        self.test_api_usage_tracking()
        self.test_metadata_operations()
        self.test_unique_constraints()

        print("\n" + "=" * 60)
        print("📊 Test Results")
        print("=" * 60)
        print(f"✅ Passed: {self.passed}")
        print(f"❌ Failed: {self.failed}")
        print(f"📝 Total:  {self.passed + self.failed}")

        if self.failed > 0:
            print("\n❌ Failed Tests:")
            for error in self.errors:
                print(f"  - {error}")
            return False
        else:
            print("\n✅ All tests passed!")
            return True


def main():
    """Run test suite"""
    tester = TestDatabase()

    try:
        success = tester.run_all_tests()
        exit_code = 0 if success else 1
    finally:
        tester.cleanup()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
