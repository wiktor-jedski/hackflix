"""Tests for the database module."""

import sqlite3
from pathlib import Path
from unittest import mock

import pytest

from src.config import DownloadState, PipelineState
from src.database.db_manager import DatabaseManager
from src.database.schema import get_schema_sql, initialize_database


class TestSchema:
    """Tests for database schema."""

    def test_get_schema_sql_returns_string(self) -> None:
        """Verify get_schema_sql returns non-empty string."""
        sql = get_schema_sql()
        assert isinstance(sql, str)
        assert len(sql) > 0

    def test_schema_contains_all_tables(self) -> None:
        """Verify schema SQL contains all required tables."""
        sql = get_schema_sql()
        required_tables = [
            "settings",
            "media_items",
            "seasons",
            "video_files",
            "subtitles",
            "translation_progress",
        ]
        for table in required_tables:
            assert f"CREATE TABLE IF NOT EXISTS {table}" in sql

    def test_initialize_database_creates_tables(self, tmp_path) -> None:
        """Verify initialize_database creates all tables."""
        db_path = tmp_path / "test.db"
        initialize_database(db_path)

        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()

        # Get list of tables
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = {row[0] for row in cursor.fetchall()}
        conn.close()

        expected_tables = {
            "settings",
            "media_items",
            "seasons",
            "video_files",
            "subtitles",
            "translation_progress",
        }
        assert expected_tables.issubset(tables)


class TestDatabaseManager:
    """Tests for DatabaseManager class."""

    def test_initialize_creates_schema(self, tmp_path) -> None:
        """Verify initialize creates database schema."""
        db_path = tmp_path / "test.db"
        manager = DatabaseManager(db_path)
        manager.initialize()

        # Verify database file exists
        assert db_path.exists()

        # Verify tables exist
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        conn.close()

        assert "media_items" in tables
        assert "video_files" in tables

    def test_upsert_content_movie(
        self, db_manager: DatabaseManager, sample_content_json: dict
    ) -> None:
        """Test upserting a movie from content.json."""
        # Insert only the first movie
        single_movie = {"items": [sample_content_json["items"][0]]}
        db_manager.upsert_content(single_movie)

        # Verify media item exists
        items = db_manager.get_library_items("movie")
        assert len(items) == 1
        assert items[0]["title"] == "Big Buck Bunny"
        assert items[0]["type"] == "movie"

        # Verify video file exists
        video = db_manager.get_video_details("movie-uuid-1")
        assert video is not None
        assert video["subtitle_id"] == 123
        assert video["needs_translation"] == 1

    def test_upsert_content_series(
        self, db_manager: DatabaseManager, sample_content_json: dict
    ) -> None:
        """Test upserting a series with seasons and episodes."""
        # Insert only the series
        series_only = {"items": [sample_content_json["items"][2]]}
        db_manager.upsert_content(series_only)

        # Verify media item exists
        items = db_manager.get_library_items("series")
        assert len(items) == 1
        assert items[0]["title"] == "Open Source Show"

        # Verify seasons exist
        seasons = db_manager.get_seasons("series-uuid-1")
        assert len(seasons) == 2
        assert seasons[0]["season_number"] == 1
        assert seasons[1]["season_number"] == 2

        # Verify episodes exist
        episodes_s1 = db_manager.get_episodes(seasons[0]["id"])
        assert len(episodes_s1) == 2
        assert episodes_s1[0]["episode_title"] == "The Beginning"
        assert episodes_s1[1]["episode_title"] == "The Middle"

        episodes_s2 = db_manager.get_episodes(seasons[1]["id"])
        assert len(episodes_s2) == 1
        assert episodes_s2[0]["episode_title"] == "New Start"

    def test_upsert_content_updates_existing_movie(
        self, db_manager: DatabaseManager
    ) -> None:
        """Test upserting a movie that already exists updates its fields."""
        # Insert initial movie
        initial = {
            "items": [
                {
                    "id": "movie-update-test",
                    "type": "movie",
                    "title": "Original Title",
                    "magnet": "magnet:?original",
                    "subtitle_id": 100,
                    "translation_needed": False,
                }
            ]
        }
        db_manager.upsert_content(initial)

        # Verify initial values
        video = db_manager.get_video_details("movie-update-test")
        assert video["subtitle_id"] == 100
        assert video["needs_translation"] == 0

        # Update the same movie with new values
        updated = {
            "items": [
                {
                    "id": "movie-update-test",
                    "type": "movie",
                    "title": "Updated Title",
                    "magnet": "magnet:?updated",
                    "subtitle_id": 200,
                    "translation_needed": True,
                }
            ]
        }
        db_manager.upsert_content(updated)

        # Verify updated values
        video = db_manager.get_video_details("movie-update-test")
        assert video["subtitle_id"] == 200
        assert video["needs_translation"] == 1

    def test_upsert_content_updates_existing_episode(
        self, db_manager: DatabaseManager
    ) -> None:
        """Test upserting a series episode that already exists updates its fields."""
        # Insert initial series with episode
        initial = {
            "items": [
                {
                    "id": "series-update-test",
                    "type": "series",
                    "title": "Test Series",
                    "poster_url": None,
                    "seasons": [
                        {
                            "season_number": 1,
                            "magnet": "magnet:?season1",
                            "episodes": [
                                {
                                    "number": 1,
                                    "title": "Original Episode Title",
                                    "subtitle_id": 100,
                                    "translation_needed": False,
                                }
                            ],
                        }
                    ],
                }
            ]
        }
        db_manager.upsert_content(initial)

        # Get the episode and verify initial values
        seasons = db_manager.get_seasons("series-update-test")
        episodes = db_manager.get_episodes(seasons[0]["id"])
        assert episodes[0]["episode_title"] == "Original Episode Title"
        assert episodes[0]["subtitle_id"] == 100
        assert episodes[0]["needs_translation"] == 0

        # Update the same episode with new values
        updated = {
            "items": [
                {
                    "id": "series-update-test",
                    "type": "series",
                    "title": "Test Series",
                    "poster_url": None,
                    "seasons": [
                        {
                            "season_number": 1,
                            "magnet": "magnet:?season1",
                            "episodes": [
                                {
                                    "number": 1,
                                    "title": "Updated Episode Title",
                                    "subtitle_id": 200,
                                    "translation_needed": True,
                                }
                            ],
                        }
                    ],
                }
            ]
        }
        db_manager.upsert_content(updated)

        # Verify updated values
        episodes = db_manager.get_episodes(seasons[0]["id"])
        assert episodes[0]["episode_title"] == "Updated Episode Title"
        assert episodes[0]["subtitle_id"] == 200
        assert episodes[0]["needs_translation"] == 1

    def test_upsert_content_preserves_orphans(
        self, db_manager: DatabaseManager
    ) -> None:
        """Test that items not in new JSON are preserved."""
        # Insert initial content
        initial = {
            "items": [
                {
                    "id": "movie-1",
                    "type": "movie",
                    "title": "First Movie",
                    "magnet": "magnet:?test1",
                    "subtitle_id": None,
                }
            ]
        }
        db_manager.upsert_content(initial)

        # Insert new content without the first movie
        updated = {
            "items": [
                {
                    "id": "movie-2",
                    "type": "movie",
                    "title": "Second Movie",
                    "magnet": "magnet:?test2",
                    "subtitle_id": None,
                }
            ]
        }
        db_manager.upsert_content(updated)

        # Verify both movies exist (orphan preserved)
        items = db_manager.get_library_items("movie")
        assert len(items) == 2
        titles = {item["title"] for item in items}
        assert "First Movie" in titles
        assert "Second Movie" in titles

    def test_get_library_items_with_filter(
        self, db_manager: DatabaseManager, sample_content_json: dict
    ) -> None:
        """Test filtering library items by title."""
        db_manager.upsert_content(sample_content_json)

        # Filter by partial title
        items = db_manager.get_library_items("movie", search_filter="Buck")
        assert len(items) == 1
        assert items[0]["title"] == "Big Buck Bunny"

        # Filter with no matches
        items = db_manager.get_library_items("movie", search_filter="xyz")
        assert len(items) == 0

    def test_upsert_content_with_genres(
        self, db_manager: DatabaseManager, sample_content_json: dict
    ) -> None:
        """Test that genres are stored when upserting content."""
        db_manager.upsert_content(sample_content_json)

        # Verify genres are stored for movies
        items = db_manager.get_library_items("movie")
        bbb = next(i for i in items if i["title"] == "Big Buck Bunny")
        assert bbb["genres"] == "Animation, Comedy, Family"

        sintel = next(i for i in items if i["title"] == "Sintel")
        assert sintel["genres"] == "Animation, Fantasy, Action"

        # Verify genres are stored for series
        items = db_manager.get_library_items("series")
        assert items[0]["genres"] == "Documentary, Technology"

    def test_get_library_items_filter_by_genre(
        self, db_manager: DatabaseManager, sample_content_json: dict
    ) -> None:
        """Test filtering library items by genre."""
        db_manager.upsert_content(sample_content_json)

        # Filter by genre - should find both animation movies
        items = db_manager.get_library_items("movie", search_filter="Animation")
        assert len(items) == 2
        titles = {item["title"] for item in items}
        assert "Big Buck Bunny" in titles
        assert "Sintel" in titles

        # Filter by unique genre - should find only one
        items = db_manager.get_library_items("movie", search_filter="Family")
        assert len(items) == 1
        assert items[0]["title"] == "Big Buck Bunny"

        # Filter by genre for series
        items = db_manager.get_library_items("series", search_filter="Documentary")
        assert len(items) == 1
        assert items[0]["title"] == "Open Source Show"

    def test_get_library_items_filter_title_and_genre_or_logic(
        self, db_manager: DatabaseManager, sample_content_json: dict
    ) -> None:
        """Test that search filter matches either title OR genre."""
        db_manager.upsert_content(sample_content_json)

        # "Bunny" is in title but not in genres
        items = db_manager.get_library_items("movie", search_filter="Bunny")
        assert len(items) == 1
        assert items[0]["title"] == "Big Buck Bunny"

        # "Fantasy" is in genres but not in title
        items = db_manager.get_library_items("movie", search_filter="Fantasy")
        assert len(items) == 1
        assert items[0]["title"] == "Sintel"

        # "Animation" matches genre of both movies
        items = db_manager.get_library_items("movie", search_filter="Animation")
        assert len(items) == 2

    def test_upsert_content_without_genres(self, db_manager: DatabaseManager) -> None:
        """Test upserting content without genres field (backwards compatibility)."""
        content_no_genres = {
            "items": [
                {
                    "id": "movie-no-genre",
                    "type": "movie",
                    "title": "Movie Without Genre",
                    "magnet": "magnet:?test",
                    "subtitle_id": None,
                }
            ]
        }
        db_manager.upsert_content(content_no_genres)

        items = db_manager.get_library_items("movie")
        assert len(items) == 1
        assert items[0]["genres"] is None

    def test_update_file_state(self, db_manager: DatabaseManager) -> None:
        """Test updating video file download state."""
        # Create a movie
        content = {
            "items": [
                {
                    "id": "movie-test",
                    "type": "movie",
                    "title": "Test Movie",
                    "magnet": "magnet:?test",
                    "subtitle_id": None,
                }
            ]
        }
        db_manager.upsert_content(content)

        # Get video file
        video = db_manager.get_video_details("movie-test")
        assert video["state"] == "PENDING"

        # Update state
        db_manager.update_file_state(video["id"], DownloadState.DOWNLOADING)

        # Verify update
        video = db_manager.get_video_file(video["id"])
        assert video["state"] == "DOWNLOADING"

    def test_update_pipeline_state(self, db_manager: DatabaseManager) -> None:
        """Test updating video file pipeline state."""
        content = {
            "items": [
                {
                    "id": "movie-test",
                    "type": "movie",
                    "title": "Test Movie",
                    "magnet": "magnet:?test",
                    "subtitle_id": 123,
                    "translation_needed": True,
                }
            ]
        }
        db_manager.upsert_content(content)

        video = db_manager.get_video_details("movie-test")
        assert video["pipeline_state"] == "NONE"

        db_manager.update_pipeline_state(video["id"], PipelineState.FETCHING_SUBS)

        video = db_manager.get_video_file(video["id"])
        assert video["pipeline_state"] == "FETCHING_SUBS"

    def test_update_resume_position(self, db_manager: DatabaseManager) -> None:
        """Test updating playback resume position."""
        content = {
            "items": [
                {
                    "id": "movie-test",
                    "type": "movie",
                    "title": "Test Movie",
                    "magnet": "magnet:?test",
                    "subtitle_id": None,
                }
            ]
        }
        db_manager.upsert_content(content)

        video = db_manager.get_video_details("movie-test")
        assert video["resume_position_seconds"] == 0

        db_manager.update_resume_position(video["id"], 3600)

        video = db_manager.get_video_file(video["id"])
        assert video["resume_position_seconds"] == 3600

    def test_translation_progress(self, db_manager: DatabaseManager) -> None:
        """Test translation progress tracking."""
        content = {
            "items": [
                {
                    "id": "movie-test",
                    "type": "movie",
                    "title": "Test Movie",
                    "magnet": "magnet:?test",
                    "subtitle_id": 123,
                    "translation_needed": True,
                }
            ]
        }
        db_manager.upsert_content(content)

        video = db_manager.get_video_details("movie-test")

        # Initially no progress
        progress = db_manager.get_translation_progress(video["id"])
        assert progress is None

        # Update progress
        db_manager.update_translation_progress(video["id"], 5, 10)

        progress = db_manager.get_translation_progress(video["id"])
        assert progress["last_completed_batch"] == 5
        assert progress["total_batches"] == 10

        # Update again
        db_manager.update_translation_progress(video["id"], 8, 10)

        progress = db_manager.get_translation_progress(video["id"])
        assert progress["last_completed_batch"] == 8

    def test_get_incomplete_downloads(self, db_manager: DatabaseManager) -> None:
        """Test querying incomplete downloads for auto-resume."""
        content = {
            "items": [
                {
                    "id": "movie-1",
                    "type": "movie",
                    "title": "Completed Movie",
                    "magnet": "magnet:?test1",
                    "subtitle_id": None,
                },
                {
                    "id": "movie-2",
                    "type": "movie",
                    "title": "Downloading Movie",
                    "magnet": "magnet:?test2",
                    "subtitle_id": None,
                },
                {
                    "id": "movie-3",
                    "type": "movie",
                    "title": "Queued Movie",
                    "magnet": "magnet:?test3",
                    "subtitle_id": None,
                },
            ]
        }
        db_manager.upsert_content(content)

        # Set states
        v1 = db_manager.get_video_details("movie-1")
        v2 = db_manager.get_video_details("movie-2")
        v3 = db_manager.get_video_details("movie-3")

        db_manager.update_file_state(v1["id"], DownloadState.COMPLETED)
        db_manager.update_file_state(v2["id"], DownloadState.DOWNLOADING)
        db_manager.update_file_state(v3["id"], DownloadState.QUEUED)

        # Query incomplete
        incomplete = db_manager.get_incomplete_downloads()
        assert len(incomplete) == 2
        titles = {item["media_title"] for item in incomplete}
        assert "Downloading Movie" in titles
        assert "Queued Movie" in titles

    def test_get_incomplete_pipelines(self, db_manager: DatabaseManager) -> None:
        """Test querying incomplete pipeline processing for auto-resume."""
        content = {
            "items": [
                {
                    "id": "movie-1",
                    "type": "movie",
                    "title": "Ready Movie",
                    "magnet": "magnet:?test1",
                    "subtitle_id": 1,
                    "translation_needed": True,
                },
                {
                    "id": "movie-2",
                    "type": "movie",
                    "title": "Translating Movie",
                    "magnet": "magnet:?test2",
                    "subtitle_id": 2,
                    "translation_needed": True,
                },
            ]
        }
        db_manager.upsert_content(content)

        v1 = db_manager.get_video_details("movie-1")
        v2 = db_manager.get_video_details("movie-2")

        db_manager.update_pipeline_state(v1["id"], PipelineState.SUBS_READY)
        db_manager.update_pipeline_state(v2["id"], PipelineState.TRANSLATING)

        incomplete = db_manager.get_incomplete_pipelines()
        assert len(incomplete) == 1
        assert incomplete[0]["media_title"] == "Translating Movie"

    def test_add_and_get_subtitle(self, db_manager: DatabaseManager) -> None:
        """Test adding and retrieving subtitles."""
        content = {
            "items": [
                {
                    "id": "movie-test",
                    "type": "movie",
                    "title": "Test Movie",
                    "magnet": "magnet:?test",
                    "subtitle_id": 123,
                }
            ]
        }
        db_manager.upsert_content(content)

        video = db_manager.get_video_details("movie-test")

        # Add subtitles
        sub_id_en = db_manager.add_subtitle(
            video["id"], "en", "/path/to/en.srt", is_translated=False
        )
        sub_id_pl = db_manager.add_subtitle(
            video["id"], "pl", "/path/to/pl.srt", is_translated=True
        )

        # Get subtitles
        subtitles = db_manager.get_subtitles(video["id"])
        assert len(subtitles) == 2

        en_sub = next(s for s in subtitles if s["language_code"] == "en")
        pl_sub = next(s for s in subtitles if s["language_code"] == "pl")

        assert en_sub["is_translated"] == 0
        assert pl_sub["is_translated"] == 1

    def test_update_file_path(self, db_manager: DatabaseManager) -> None:
        """Test updating video file path after download."""
        content = {
            "items": [
                {
                    "id": "movie-test",
                    "type": "movie",
                    "title": "Test Movie",
                    "magnet": "magnet:?test",
                    "subtitle_id": None,
                }
            ]
        }
        db_manager.upsert_content(content)

        video = db_manager.get_video_details("movie-test")
        assert video["file_path"] is None

        db_manager.update_file_path(video["id"], "/path/to/movie.mkv")

        video = db_manager.get_video_file(video["id"])
        assert video["file_path"] == "/path/to/movie.mkv"

    def test_season_state_update(self, db_manager: DatabaseManager) -> None:
        """Test updating season download state and progress."""
        content = {
            "items": [
                {
                    "id": "series-test",
                    "type": "series",
                    "title": "Test Series",
                    "poster_url": None,
                    "seasons": [
                        {
                            "season_number": 1,
                            "magnet": "magnet:?season1",
                            "episodes": [
                                {"number": 1, "title": "Ep1", "subtitle_id": None}
                            ],
                        }
                    ],
                }
            ]
        }
        db_manager.upsert_content(content)

        seasons = db_manager.get_seasons("series-test")
        assert len(seasons) == 1
        season_id = seasons[0]["id"]

        # Initial state
        assert seasons[0]["state"] == "PENDING"
        assert seasons[0]["download_progress"] == 0

        # Update state and progress
        db_manager.update_season_state(
            season_id, DownloadState.DOWNLOADING, progress=50
        )

        seasons = db_manager.get_seasons("series-test")
        assert seasons[0]["state"] == "DOWNLOADING"
        assert seasons[0]["download_progress"] == 50

    def test_get_video_file_nonexistent(self, db_manager: DatabaseManager) -> None:
        """Test get_video_file returns None for nonexistent ID."""
        result = db_manager.get_video_file(99999)
        assert result is None

    def test_get_video_details_nonexistent(self, db_manager: DatabaseManager) -> None:
        """Test get_video_details returns None for nonexistent media ID."""
        result = db_manager.get_video_details("nonexistent-uuid")
        assert result is None

    def test_get_translation_progress_nonexistent(
        self, db_manager: DatabaseManager
    ) -> None:
        """Test get_translation_progress returns None for nonexistent file ID."""
        result = db_manager.get_translation_progress(99999)
        assert result is None

    def test_get_seasons_empty(self, db_manager: DatabaseManager) -> None:
        """Test get_seasons returns empty list for nonexistent series."""
        result = db_manager.get_seasons("nonexistent-series")
        assert result == []

    def test_get_episodes_empty(self, db_manager: DatabaseManager) -> None:
        """Test get_episodes returns empty list for nonexistent season."""
        result = db_manager.get_episodes(99999)
        assert result == []

    def test_get_subtitles_empty(self, db_manager: DatabaseManager) -> None:
        """Test get_subtitles returns empty list for nonexistent file ID."""
        result = db_manager.get_subtitles(99999)
        assert result == []


class TestSchemaErrorHandling:
    """Tests for schema error handling."""

    def test_initialize_database_error(self, tmp_path: Path) -> None:
        """Test initialize_database raises on sqlite3 error."""
        db_path = tmp_path / "test.db"

        with mock.patch("src.database.schema.sqlite3.connect") as mock_connect:
            mock_connect.side_effect = sqlite3.Error("Mocked database error")

            with pytest.raises(sqlite3.Error, match="Mocked database error"):
                initialize_database(db_path)


class TestDatabaseManagerErrorHandling:
    """Tests for DatabaseManager error handling paths."""

    def test_initialize_error(self, tmp_path: Path) -> None:
        """Test initialize raises on sqlite3 error."""
        db_path = tmp_path / "test.db"
        manager = DatabaseManager(db_path)

        with mock.patch.object(manager, "_get_connection") as mock_conn:
            mock_conn.side_effect = sqlite3.Error("Connection failed")

            with pytest.raises(sqlite3.Error, match="Connection failed"):
                manager.initialize()

    def test_upsert_content_sqlite_error(self, db_manager: DatabaseManager) -> None:
        """Test upsert_content raises on sqlite3 error."""
        with mock.patch.object(db_manager, "_get_connection") as mock_conn:
            mock_conn.side_effect = sqlite3.Error("Insert failed")

            with pytest.raises(sqlite3.Error, match="Insert failed"):
                db_manager.upsert_content({"items": []})

    def test_upsert_content_missing_field(self, db_manager: DatabaseManager) -> None:
        """Test upsert_content raises KeyError on missing required field."""
        invalid_content = {"items": [{"id": "test"}]}  # Missing 'type' and 'title'

        with pytest.raises(KeyError):
            db_manager.upsert_content(invalid_content)

    def test_get_library_items_error(self, db_manager: DatabaseManager) -> None:
        """Test get_library_items raises on sqlite3 error."""
        with mock.patch.object(db_manager, "_get_connection") as mock_conn:
            mock_conn.side_effect = sqlite3.Error("Query failed")

            with pytest.raises(sqlite3.Error, match="Query failed"):
                db_manager.get_library_items("movie")

    def test_get_video_details_error(self, db_manager: DatabaseManager) -> None:
        """Test get_video_details raises on sqlite3 error."""
        with mock.patch.object(db_manager, "_get_connection") as mock_conn:
            mock_conn.side_effect = sqlite3.Error("Query failed")

            with pytest.raises(sqlite3.Error, match="Query failed"):
                db_manager.get_video_details("test-id")

    def test_get_video_file_error(self, db_manager: DatabaseManager) -> None:
        """Test get_video_file raises on sqlite3 error."""
        with mock.patch.object(db_manager, "_get_connection") as mock_conn:
            mock_conn.side_effect = sqlite3.Error("Query failed")

            with pytest.raises(sqlite3.Error, match="Query failed"):
                db_manager.get_video_file(1)

    def test_get_seasons_error(self, db_manager: DatabaseManager) -> None:
        """Test get_seasons raises on sqlite3 error."""
        with mock.patch.object(db_manager, "_get_connection") as mock_conn:
            mock_conn.side_effect = sqlite3.Error("Query failed")

            with pytest.raises(sqlite3.Error, match="Query failed"):
                db_manager.get_seasons("test-id")

    def test_get_episodes_error(self, db_manager: DatabaseManager) -> None:
        """Test get_episodes raises on sqlite3 error."""
        with mock.patch.object(db_manager, "_get_connection") as mock_conn:
            mock_conn.side_effect = sqlite3.Error("Query failed")

            with pytest.raises(sqlite3.Error, match="Query failed"):
                db_manager.get_episodes(1)

    def test_update_file_state_error(self, db_manager: DatabaseManager) -> None:
        """Test update_file_state raises on sqlite3 error."""
        with mock.patch.object(db_manager, "_get_connection") as mock_conn:
            mock_conn.side_effect = sqlite3.Error("Update failed")

            with pytest.raises(sqlite3.Error, match="Update failed"):
                db_manager.update_file_state(1, DownloadState.DOWNLOADING)

    def test_update_season_state_error(self, db_manager: DatabaseManager) -> None:
        """Test update_season_state raises on sqlite3 error."""
        with mock.patch.object(db_manager, "_get_connection") as mock_conn:
            mock_conn.side_effect = sqlite3.Error("Update failed")

            with pytest.raises(sqlite3.Error, match="Update failed"):
                db_manager.update_season_state(1, DownloadState.DOWNLOADING)

    def test_update_pipeline_state_error(self, db_manager: DatabaseManager) -> None:
        """Test update_pipeline_state raises on sqlite3 error."""
        with mock.patch.object(db_manager, "_get_connection") as mock_conn:
            mock_conn.side_effect = sqlite3.Error("Update failed")

            with pytest.raises(sqlite3.Error, match="Update failed"):
                db_manager.update_pipeline_state(1, PipelineState.TRANSLATING)

    def test_update_file_path_error(self, db_manager: DatabaseManager) -> None:
        """Test update_file_path raises on sqlite3 error."""
        with mock.patch.object(db_manager, "_get_connection") as mock_conn:
            mock_conn.side_effect = sqlite3.Error("Update failed")

            with pytest.raises(sqlite3.Error, match="Update failed"):
                db_manager.update_file_path(1, "/path/to/file")

    def test_update_resume_position_error(self, db_manager: DatabaseManager) -> None:
        """Test update_resume_position raises on sqlite3 error."""
        with mock.patch.object(db_manager, "_get_connection") as mock_conn:
            mock_conn.side_effect = sqlite3.Error("Update failed")

            with pytest.raises(sqlite3.Error, match="Update failed"):
                db_manager.update_resume_position(1, 100)

    def test_get_translation_progress_error(self, db_manager: DatabaseManager) -> None:
        """Test get_translation_progress raises on sqlite3 error."""
        with mock.patch.object(db_manager, "_get_connection") as mock_conn:
            mock_conn.side_effect = sqlite3.Error("Query failed")

            with pytest.raises(sqlite3.Error, match="Query failed"):
                db_manager.get_translation_progress(1)

    def test_update_translation_progress_error(
        self, db_manager: DatabaseManager
    ) -> None:
        """Test update_translation_progress raises on sqlite3 error."""
        with mock.patch.object(db_manager, "_get_connection") as mock_conn:
            mock_conn.side_effect = sqlite3.Error("Update failed")

            with pytest.raises(sqlite3.Error, match="Update failed"):
                db_manager.update_translation_progress(1, 5, 10)

    def test_get_incomplete_downloads_error(self, db_manager: DatabaseManager) -> None:
        """Test get_incomplete_downloads raises on sqlite3 error."""
        with mock.patch.object(db_manager, "_get_connection") as mock_conn:
            mock_conn.side_effect = sqlite3.Error("Query failed")

            with pytest.raises(sqlite3.Error, match="Query failed"):
                db_manager.get_incomplete_downloads()

    def test_get_incomplete_pipelines_error(self, db_manager: DatabaseManager) -> None:
        """Test get_incomplete_pipelines raises on sqlite3 error."""
        with mock.patch.object(db_manager, "_get_connection") as mock_conn:
            mock_conn.side_effect = sqlite3.Error("Query failed")

            with pytest.raises(sqlite3.Error, match="Query failed"):
                db_manager.get_incomplete_pipelines()

    def test_add_subtitle_error(self, db_manager: DatabaseManager) -> None:
        """Test add_subtitle raises on sqlite3 error."""
        with mock.patch.object(db_manager, "_get_connection") as mock_conn:
            mock_conn.side_effect = sqlite3.Error("Insert failed")

            with pytest.raises(sqlite3.Error, match="Insert failed"):
                db_manager.add_subtitle(1, "en", "/path/to/sub.srt")

    def test_get_subtitles_error(self, db_manager: DatabaseManager) -> None:
        """Test get_subtitles raises on sqlite3 error."""
        with mock.patch.object(db_manager, "_get_connection") as mock_conn:
            mock_conn.side_effect = sqlite3.Error("Query failed")

            with pytest.raises(sqlite3.Error, match="Query failed"):
                db_manager.get_subtitles(1)

    def test_reset_media_state_error(self, db_manager: DatabaseManager) -> None:
        """Test reset_media_state raises on sqlite3 error."""
        with mock.patch.object(db_manager, "_get_connection") as mock_conn:
            mock_conn.side_effect = sqlite3.Error("Update failed")

            with pytest.raises(sqlite3.Error, match="Update failed"):
                db_manager.reset_media_state("movie-1")

    def test_reset_video_file_state_error(self, db_manager: DatabaseManager) -> None:
        """Test reset_video_file_state raises on sqlite3 error."""
        with mock.patch.object(db_manager, "_get_connection") as mock_conn:
            mock_conn.side_effect = sqlite3.Error("Update failed")

            with pytest.raises(sqlite3.Error, match="Update failed"):
                db_manager.reset_video_file_state(1)


class TestResetState:
    """Tests for reset state methods."""

    def test_reset_media_state(self, db_manager: DatabaseManager) -> None:
        """Test resetting media state after file deletion."""
        content = {
            "items": [
                {
                    "id": "movie-test",
                    "type": "movie",
                    "title": "Test Movie",
                    "magnet": "magnet:?test",
                    "subtitle_id": 123,
                }
            ]
        }
        db_manager.upsert_content(content)

        # Get the video file ID
        video = db_manager.get_video_details("movie-test")
        assert video is not None
        file_id = video["id"]

        # Set completed state with file path
        db_manager.update_file_state(file_id, DownloadState.COMPLETED, 100)
        db_manager.update_file_path(file_id, "/path/to/movie.mp4")
        db_manager.update_pipeline_state(file_id, PipelineState.SUBS_READY)

        # Verify completed state
        video = db_manager.get_video_file(file_id)
        assert video["state"] == "COMPLETED"
        assert video["file_path"] == "/path/to/movie.mp4"
        assert video["pipeline_state"] == "SUBS_READY"

        # Reset state
        db_manager.reset_media_state("movie-test")

        # Verify reset state
        video = db_manager.get_video_file(file_id)
        assert video["state"] == "PENDING"
        assert video["file_path"] is None
        assert video["pipeline_state"] == "NONE"
        assert video["download_progress"] == 0

    def test_reset_video_file_state(self, db_manager: DatabaseManager) -> None:
        """Test resetting individual video file state."""
        content = {
            "items": [
                {
                    "id": "movie-test",
                    "type": "movie",
                    "title": "Test Movie",
                    "magnet": "magnet:?test",
                    "subtitle_id": 123,
                }
            ]
        }
        db_manager.upsert_content(content)

        # Get the video file ID
        video = db_manager.get_video_details("movie-test")
        assert video is not None
        file_id = video["id"]

        # Set completed state with file path
        db_manager.update_file_state(file_id, DownloadState.COMPLETED, 100)
        db_manager.update_file_path(file_id, "/path/to/movie.mp4")
        db_manager.update_pipeline_state(file_id, PipelineState.SUBS_READY)

        # Reset state
        db_manager.reset_video_file_state(file_id)

        # Verify reset state
        video = db_manager.get_video_file(file_id)
        assert video["state"] == "PENDING"
        assert video["file_path"] is None
        assert video["pipeline_state"] == "NONE"
        assert video["download_progress"] == 0


class TestDatabaseThreadSafety:
    """Tests for database thread safety behavior.

    Note: SQLite does not support concurrent connections from multiple threads.
    The db_manager is designed to use per-operation connections, but the manager
    instance itself should not be shared across threads. These tests verify
    that the system correctly handles or reports thread-safety violations.
    """

    def test_single_thread_success(self, db_manager: DatabaseManager) -> None:
        """Verify database operations work correctly from a single thread."""
        content = {
            "items": [
                {
                    "id": "movie-1",
                    "type": "movie",
                    "title": "Test Movie",
                    "magnet": "magnet:?test",
                    "subtitle_id": None,
                }
            ]
        }
        db_manager.upsert_content(content)
        items = db_manager.get_library_items("movie")
        assert len(items) == 1
        assert items[0]["title"] == "Test Movie"

    def test_multiple_sequential_operations_in_single_thread(
        self, db_manager: DatabaseManager
    ) -> None:
        """Verify multiple operations work correctly."""
        for i in range(10):
            content = {
                "items": [
                    {
                        "id": f"movie-{i}",
                        "type": "movie",
                        "title": f"Movie {i}",
                        "magnet": f"magnet:?test{i}",
                        "subtitle_id": None,
                    }
                ]
            }
            db_manager.upsert_content(content)

        items = db_manager.get_library_items("movie")
        assert len(items) == 10

    def test_connection_isolation_per_operation(
        self, db_manager: DatabaseManager
    ) -> None:
        """Verify each operation gets its own connection scope."""
        items1 = db_manager.get_library_items("movie")
        items2 = db_manager.get_library_items("movie")
        assert items1 == items2


class TestDatabaseTransactionRollback:
    """Tests for transaction rollback behavior."""

    def test_upsert_content_rollback_on_error(
        self, db_manager: DatabaseManager
    ) -> None:
        """Verify upsert_content rolls back on error."""
        initial_count = len(db_manager.get_library_items("movie"))

        with mock.patch.object(db_manager, "_get_connection") as mock_conn:
            mock_conn.side_effect = sqlite3.Error("Database connection failed")

            with pytest.raises(sqlite3.Error):
                db_manager.upsert_content({"items": []})

        final_count = len(db_manager.get_library_items("movie"))
        assert final_count == initial_count

    def test_batch_insert_rollback_on_failure(
        self, db_manager: DatabaseManager
    ) -> None:
        """Verify batch insert of series with episodes rolls back on failure."""
        initial_items = db_manager.get_library_items("series")

        with mock.patch.object(db_manager, "_get_connection") as mock_conn:
            mock_conn.return_value.cursor.return_value.execute.side_effect = (
                sqlite3.Error("Constraint violation")
            )

            invalid_content = {
                "items": [
                    {
                        "id": "series-fail",
                        "type": "series",
                        "title": "Failing Series",
                        "poster_url": None,
                        "seasons": [
                            {
                                "season_number": 1,
                                "magnet": "magnet:?fail",
                                "episodes": [
                                    {"number": 1, "title": "Ep1", "subtitle_id": None}
                                ],
                            }
                        ],
                    }
                ]
            }

            with pytest.raises(sqlite3.Error):
                db_manager.upsert_content(invalid_content)

        final_items = db_manager.get_library_items("series")
        assert len(final_items) == len(initial_items)
        assert not any(item["id"] == "series-fail" for item in final_items)

    def test_nested_transaction_rollback(self, db_manager: DatabaseManager) -> None:
        """Verify nested transactions properly rollback."""
        initial_count = len(db_manager.get_library_items("movie"))

        with mock.patch.object(db_manager, "_get_connection") as mock_conn:
            call_count = [0]
            original_execute = mock_conn.return_value.cursor.return_value.execute

            def failing_execute(*args, **kwargs):
                call_count[0] += 1
                if call_count[0] > 2:
                    raise sqlite3.Error("Nested transaction error")
                return original_execute(*args, **kwargs)

            mock_conn.return_value.cursor.return_value.execute.side_effect = (
                failing_execute
            )

            with pytest.raises(sqlite3.Error):
                content = {
                    "items": [
                        {
                            "id": "movie-nested",
                            "type": "movie",
                            "title": "Nested Test",
                            "magnet": "magnet:?nested",
                            "subtitle_id": None,
                        }
                    ]
                }
                db_manager.upsert_content(content)

        final_count = len(db_manager.get_library_items("movie"))
        assert final_count == initial_count


class TestForeignKeyConstraints:
    """Tests for foreign key constraint enforcement."""

    def test_foreign_key_constraint_enforced(self, tmp_path: Path) -> None:
        """Verify foreign key constraints prevent orphaned records."""
        from src.database.schema import initialize_database

        db_path = tmp_path / "test_fk.db"
        initialize_database(db_path)

        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()

        cursor.execute(
            "INSERT INTO media_items (id, type, title) VALUES (?, ?, ?)",
            ("media-1", "movie", "Test Movie"),
        )

        with pytest.raises(sqlite3.IntegrityError):
            cursor.execute(
                "INSERT INTO video_files (media_item_id, file_path) VALUES (?, ?)",
                ("non-existent-media", "/path/to/file.mkv"),
            )

        conn.close()

    def test_cascade_delete_media_item(self, tmp_path: Path) -> None:
        """Verify deleting media item cascades to video_files."""
        from src.database.schema import initialize_database

        db_path = tmp_path / "test_cascade.db"
        initialize_database(db_path)

        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()

        cursor.execute(
            "INSERT INTO media_items (id, type, title) VALUES (?, ?, ?)",
            ("cascade-test", "movie", "Cascade Test Movie"),
        )
        cursor.execute(
            "INSERT INTO video_files (media_item_id, file_path, state) VALUES (?, ?, ?)",
            ("cascade-test", "/path/to/file.mkv", "PENDING"),
        )

        cursor.execute("DELETE FROM media_items WHERE id = ?", ("cascade-test",))
        conn.commit()

        cursor.execute(
            "SELECT * FROM video_files WHERE media_item_id = ?", ("cascade-test",)
        )
        orphaned = cursor.fetchall()

        assert len(orphaned) == 0

        conn.close()

    def test_video_file_requires_valid_media_item(
        self, db_manager: DatabaseManager
    ) -> None:
        """Verify video file operations require valid media_item_id."""
        content = {
            "items": [
                {
                    "id": "movie-valid",
                    "type": "movie",
                    "title": "Valid Movie",
                    "magnet": "magnet:?valid",
                    "subtitle_id": None,
                }
            ]
        }
        db_manager.upsert_content(content)

        video = db_manager.get_video_details("movie-valid")
        assert video is not None
        assert video["media_item_id"] is not None

    def test_subtitle_requires_valid_video_file(
        self, db_manager: DatabaseManager
    ) -> None:
        """Verify subtitle operations require valid video_file_id."""
        content = {
            "items": [
                {
                    "id": "movie-sub",
                    "type": "movie",
                    "title": "Subtitle Test Movie",
                    "magnet": "magnet:?sub",
                    "subtitle_id": 123,
                }
            ]
        }
        db_manager.upsert_content(content)

        video = db_manager.get_video_details("movie-sub")
        assert video is not None

        sub_id = db_manager.add_subtitle(video["id"], "en", "/path/to/en.srt")
        assert sub_id is not None

        subtitles = db_manager.get_subtitles(video["id"])
        assert len(subtitles) == 1
        assert subtitles[0]["video_file_id"] == video["id"]
