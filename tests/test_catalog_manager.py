"""
Unit tests for CatalogManager

Tests catalog fetching, syncing, and database operations.
"""

import os
import sys
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from PyQt5.QtCore import QCoreApplication
from source.catalog_manager import CatalogManager
from source.db_schema import initialize_database
from source.db_utils import DatabaseConnection


# Sample catalog data for testing
SAMPLE_CATALOG = {
    "version": "1.0.0",
    "last_updated": "2026-01-07T12:00:00Z",
    "movies": [
        {
            "id": "movie_test1",
            "title": "Test Movie 1",
            "year": 2024,
            "genre": ["Action", "Sci-Fi"],
            "description": "A test movie",
            "magnet_link": "magnet:?xt=urn:btih:1234567890abcdef1234567890abcdef12345678",
            "file_size": 2000000000,
            "subtitle_languages": ["en", "pl"],
            "poster_url": "https://example.com/poster1.jpg",
            "imdb_id": "tt1234567",
            "tmdb_id": 12345,
            "runtime": 120,
            "video_quality": "1080p"
        },
        {
            "id": "movie_test2",
            "title": "Test Movie 2",
            "year": 2023,
            "genre": ["Drama"],
            "description": "Another test movie",
            "magnet_link": "magnet:?xt=urn:btih:abcdef1234567890abcdef1234567890abcdef12",
            "file_size": 1500000000,
            "subtitle_languages": ["en"]
        }
    ],
    "series": [
        {
            "id": "series_test1",
            "title": "Test Series 1",
            "year": 2024,
            "genre": ["Drama", "Crime"],
            "description": "A test series",
            "poster_url": "https://example.com/poster_series1.jpg",
            "imdb_id": "tt7654321",
            "tmdb_id": 54321,
            "seasons": [
                {
                    "season_number": 1,
                    "magnet_link": "magnet:?xt=urn:btih:season1hash",
                    "file_size": 5000000000,
                    "episode_count": 10,
                    "video_quality": "1080p"
                },
                {
                    "season_number": 2,
                    "magnet_link": "magnet:?xt=urn:btih:season2hash",
                    "file_size": 6000000000,
                    "episode_count": 12,
                    "video_quality": "1080p"
                }
            ]
        }
    ]
}


class TestCatalogManager:
    """Test suite for CatalogManager"""

    def __init__(self):
        self.temp_dir = tempfile.mkdtemp()
        self.errors = []
        self.passed = 0
        self.failed = 0
        self.app = None

    def setup(self):
        """Set up test environment"""
        # Create Qt application for signals
        if not QCoreApplication.instance():
            self.app = QCoreApplication([])

    def get_test_db_path(self):
        """Get a unique database path for each test"""
        # Create a unique database file for this test
        import uuid
        db_name = f"test_{uuid.uuid4().hex[:8]}.db"
        db_path = os.path.join(self.temp_dir, db_name)
        initialize_database(db_path)
        return db_path

    def cleanup(self):
        """Clean up test files"""
        # Remove all database files in temp dir
        if Path(self.temp_dir).exists():
            for file in Path(self.temp_dir).glob("*.db"):
                file.unlink()
            os.rmdir(self.temp_dir)

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
        """Test CatalogManager initialization"""
        print("\n📋 Test: CatalogManager Initialization")

        db_path = self.get_test_db_path()
        manager = CatalogManager(
            catalog_url="https://test.com/catalog.json",
            db_path=db_path
        )

        self.assert_true(manager.catalog_url == "https://test.com/catalog.json", "Catalog URL set")
        self.assert_true(manager.db_path == db_path, "Database path set")
        self.assert_true(manager._get_db() is not None, "Database connection can be created")

        manager.close()

    @patch('source.catalog_manager.requests.get')
    def test_fetch_catalog_success(self, mock_get):
        """Test successful catalog fetch"""
        print("\n📋 Test: Fetch Catalog Success")

        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = SAMPLE_CATALOG
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        db_path = self.get_test_db_path()
        manager = CatalogManager(db_path=db_path)
        catalog = manager.fetch_catalog()

        self.assert_true(catalog is not None, "Catalog fetched")
        self.assert_equal(len(catalog["movies"]), 2, "2 movies in catalog")
        self.assert_equal(len(catalog["series"]), 1, "1 series in catalog")

        manager.close()

    @patch('source.catalog_manager.requests.get')
    def test_fetch_catalog_network_error(self, mock_get):
        """Test network error handling"""
        print("\n📋 Test: Fetch Catalog Network Error")

        # Mock network error
        import requests
        mock_get.side_effect = requests.RequestException("Network error")

        db_path = self.get_test_db_path()
        manager = CatalogManager(db_path=db_path)

        try:
            catalog = manager.fetch_catalog()
            self.assert_true(False, "Exception raised on network error")
        except Exception as e:
            self.assert_true("Failed to fetch catalog" in str(e), "Network error handled")

        manager.close()

    def test_timestamp_tracking(self):
        """Test timestamp get/set operations"""
        print("\n📋 Test: Timestamp Tracking")

        db_path = self.get_test_db_path()
        manager = CatalogManager(db_path=db_path)

        # Get initial timestamp (should be default)
        initial = manager.get_last_sync_timestamp()
        self.assert_equal(initial, "1970-01-01T00:00:00Z", "Default timestamp is epoch")

        # Set new timestamp
        new_timestamp = "2026-01-07T12:00:00Z"
        manager.set_last_sync_timestamp(new_timestamp)

        # Verify it was saved
        saved = manager.get_last_sync_timestamp()
        self.assert_equal(saved, new_timestamp, "Timestamp saved and retrieved")

        manager.close()

    @patch('source.catalog_manager.requests.get')
    def test_sync_movies(self, mock_get):
        """Test movie synchronization"""
        print("\n📋 Test: Movie Synchronization")

        # Mock catalog response
        mock_response = Mock()
        mock_response.json.return_value = SAMPLE_CATALOG
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        db_path = self.get_test_db_path()
        manager = CatalogManager(db_path=db_path)

        # Track signals
        sync_started = []
        sync_completed = []
        sync_error = []

        manager.sync_started.connect(lambda: sync_started.append(True))
        manager.sync_completed.connect(lambda m, s: sync_completed.append((m, s)))
        manager.sync_error.connect(lambda err: sync_error.append(err))

        # Perform sync
        manager.sync_catalog()

        # Verify signals
        self.assert_equal(len(sync_started), 1, "sync_started signal emitted")
        self.assert_equal(len(sync_completed), 1, "sync_completed signal emitted")
        self.assert_equal(len(sync_error), 0, "No sync errors")

        # Close manager to ensure all transactions are committed
        manager.close()

        # Verify counts (check database directly instead of relying on signal)
        db = DatabaseConnection(db_path)
        movies_count = db.fetch_one("SELECT COUNT(*) as count FROM movies")["count"]
        series_count = db.fetch_one("SELECT COUNT(*) as count FROM series")["count"]

        self.assert_equal(movies_count, 2, "2 movies synced")
        self.assert_equal(series_count, 1, "1 series synced")

        # Verify database

        movies = db.fetch_all("SELECT * FROM movies")
        self.assert_equal(len(movies), 2, "2 movies in database")

        movie = db.fetch_one("SELECT * FROM movies WHERE id = ?", ("movie_test1",))
        self.assert_equal(movie["title"], "Test Movie 1", "Movie title correct")
        self.assert_equal(movie["year"], 2024, "Movie year correct")

        # Verify genres
        genres = db.fetch_all("SELECT genre FROM movie_genres WHERE movie_id = ?", ("movie_test1",))
        self.assert_equal(len(genres), 2, "2 genres for movie")

        # Verify subtitle languages
        langs = db.fetch_all(
            "SELECT language_code FROM movie_subtitle_languages WHERE movie_id = ?",
            ("movie_test1",)
        )
        self.assert_equal(len(langs), 2, "2 subtitle languages for movie")

        # Verify download state
        state = db.fetch_one("SELECT * FROM download_state WHERE id = ?", ("movie_test1",))
        self.assert_equal(state["status"], "available", "Download state initialized")
        self.assert_equal(state["type"], "movie", "Download type is 'movie'")

        db.close()

    @patch('source.catalog_manager.requests.get')
    def test_sync_series(self, mock_get):
        """Test series synchronization"""
        print("\n📋 Test: Series Synchronization")

        # Mock catalog response
        mock_response = Mock()
        mock_response.json.return_value = SAMPLE_CATALOG
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        db_path = self.get_test_db_path()
        manager = CatalogManager(db_path=db_path)
        manager.sync_catalog()

        # Close manager before checking database
        manager.close()

        # Verify database
        db = DatabaseConnection(db_path)

        series = db.fetch_all("SELECT * FROM series")
        self.assert_equal(len(series), 1, "1 series in database")

        show = db.fetch_one("SELECT * FROM series WHERE id = ?", ("series_test1",))
        self.assert_equal(show["title"], "Test Series 1", "Series title correct")

        # Verify genres
        genres = db.fetch_all("SELECT genre FROM series_genres WHERE series_id = ?", ("series_test1",))
        self.assert_equal(len(genres), 2, "2 genres for series")

        # Verify seasons
        seasons = db.fetch_all("SELECT * FROM seasons WHERE series_id = ?", ("series_test1",))
        self.assert_equal(len(seasons), 2, "2 seasons for series")

        season1 = db.fetch_one(
            "SELECT * FROM seasons WHERE series_id = ? AND season_number = ?",
            ("series_test1", 1)
        )
        self.assert_equal(season1["episode_count"], 10, "Season 1 has 10 episodes")

        # Verify download states for seasons
        state1 = db.fetch_one("SELECT * FROM download_state WHERE id = ?", ("series_test1_s1",))
        self.assert_equal(state1["status"], "available", "Season 1 download state initialized")
        self.assert_equal(state1["type"], "season", "Download type is 'season'")

        state2 = db.fetch_one("SELECT * FROM download_state WHERE id = ?", ("series_test1_s2",))
        self.assert_true(state2 is not None, "Season 2 download state initialized")

        db.close()

    @patch('source.catalog_manager.requests.get')
    def test_incremental_sync(self, mock_get):
        """Test incremental sync (no update needed)"""
        print("\n📋 Test: Incremental Sync (Up to Date)")

        # Mock catalog response
        mock_response = Mock()
        mock_response.json.return_value = SAMPLE_CATALOG
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        db_path = self.get_test_db_path()
        manager = CatalogManager(db_path=db_path)

        # First sync
        manager.sync_catalog()

        # Set local timestamp to same as remote
        manager.set_last_sync_timestamp(SAMPLE_CATALOG["last_updated"])

        # Track signals for second sync
        sync_completed = []
        manager.sync_completed.connect(lambda m, s: sync_completed.append((m, s)))

        # Second sync (should detect no changes)
        manager.sync_catalog()

        # Verify sync completed with existing counts
        self.assert_equal(len(sync_completed), 1, "Sync completed")

        # Check database for counts
        db = DatabaseConnection(db_path)
        movies_count = db.fetch_one("SELECT COUNT(*) as count FROM movies")["count"]
        series_count = db.fetch_one("SELECT COUNT(*) as count FROM series")["count"]
        db.close()

        self.assert_equal(movies_count, 2, "Existing movie count in database")
        self.assert_equal(series_count, 1, "Existing series count in database")

        manager.close()

    @patch('source.catalog_manager.requests.get')
    def test_sync_update_existing(self, mock_get):
        """Test updating existing content"""
        print("\n📋 Test: Update Existing Content")

        # Mock initial catalog
        mock_response = Mock()
        mock_response.json.return_value = SAMPLE_CATALOG
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        db_path = self.get_test_db_path()
        manager = CatalogManager(db_path=db_path)
        manager.sync_catalog()

        # Modify catalog
        updated_catalog = json.loads(json.dumps(SAMPLE_CATALOG))
        updated_catalog["last_updated"] = "2026-01-07T13:00:00Z"
        updated_catalog["movies"][0]["title"] = "Updated Test Movie 1"
        updated_catalog["movies"][0]["year"] = 2025

        # Mock updated response
        mock_response.json.return_value = updated_catalog

        # Sync again
        manager.sync_catalog()

        # Verify update
        db = DatabaseConnection(db_path)
        movie = db.fetch_one("SELECT * FROM movies WHERE id = ?", ("movie_test1",))
        self.assert_equal(movie["title"], "Updated Test Movie 1", "Movie title updated")
        self.assert_equal(movie["year"], 2025, "Movie year updated")

        db.close()
        manager.close()

    def test_get_catalog_info(self):
        """Test catalog info retrieval"""
        print("\n📋 Test: Get Catalog Info")

        db_path = self.get_test_db_path()
        manager = CatalogManager(db_path=db_path)

        info = manager.get_catalog_info()

        self.assert_true("movies" in info, "Info contains movies count")
        self.assert_true("series" in info, "Info contains series count")
        self.assert_true("seasons" in info, "Info contains seasons count")
        self.assert_true("last_sync" in info, "Info contains last sync timestamp")
        self.assert_true("catalog_url" in info, "Info contains catalog URL")

        manager.close()

    def run_all_tests(self):
        """Run all tests"""
        print("=" * 60)
        print("🧪 CatalogManager Test Suite")
        print("=" * 60)

        self.setup()

        try:
            self.test_initialization()
            self.test_fetch_catalog_success()
            self.test_fetch_catalog_network_error()
            self.test_timestamp_tracking()
            self.test_sync_movies()
            self.test_sync_series()
            self.test_incremental_sync()
            self.test_sync_update_existing()
            self.test_get_catalog_info()

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

        finally:
            self.cleanup()


def main():
    """Run test suite"""
    tester = TestCatalogManager()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
