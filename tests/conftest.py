"""Pytest fixtures for Hackflix tests."""

from pathlib import Path

import pytest

from src.database.db_manager import DatabaseManager


@pytest.fixture
def db_manager() -> DatabaseManager:
    """Create a DatabaseManager with an in-memory SQLite database.

    Yields:
        Initialized DatabaseManager instance using :memory: database.
    """
    manager = DatabaseManager(":memory:")
    manager.initialize()
    return manager


@pytest.fixture
def tmp_config(tmp_path: Path) -> dict[str, Path]:
    """Create temporary configuration directories.

    Args:
        tmp_path: Pytest's temporary path fixture.

    Returns:
        Dictionary with paths for config_dir, log_dir, cache_dir, torrent_dir.
    """
    config_dir = tmp_path / "config"
    log_dir = config_dir / "logs"
    cache_dir = config_dir / "cache"
    torrent_dir = config_dir / "torrents"

    for directory in [config_dir, log_dir, cache_dir, torrent_dir]:
        directory.mkdir(parents=True, exist_ok=True)

    return {
        "config_dir": config_dir,
        "log_dir": log_dir,
        "cache_dir": cache_dir,
        "torrent_dir": torrent_dir,
        "db_path": config_dir / "test.db",
    }


@pytest.fixture
def sample_content_json() -> dict:
    """Sample content.json for testing upsert operations.

    Returns:
        Dictionary matching the content.json schema.
    """
    return {
        "version": 1,
        "timestamp": "2024-05-20T10:00:00Z",
        "items": [
            {
                "id": "movie-uuid-1",
                "type": "movie",
                "title": "Big Buck Bunny",
                "genres": "Animation, Comedy, Family",
                "magnet": "magnet:?xt=urn:btih:abc123",
                "poster_url": "https://example.com/bbb.jpg",
                "subtitle_id": 123,
                "translation_needed": True,
            },
            {
                "id": "movie-uuid-2",
                "type": "movie",
                "title": "Sintel",
                "genres": "Animation, Fantasy, Action",
                "magnet": "magnet:?xt=urn:btih:def456",
                "poster_url": "https://example.com/sintel.jpg",
                "subtitle_id": None,
                "translation_needed": False,
            },
            {
                "id": "series-uuid-1",
                "type": "series",
                "title": "Open Source Show",
                "genres": "Documentary, Technology",
                "poster_url": "https://example.com/oss.jpg",
                "seasons": [
                    {
                        "season_number": 1,
                        "magnet": "magnet:?xt=urn:btih:season1",
                        "episodes": [
                            {
                                "episode_id": "ep-1-1",
                                "number": 1,
                                "title": "The Beginning",
                                "subtitle_id": 456,
                                "translation_needed": True,
                            },
                            {
                                "episode_id": "ep-1-2",
                                "number": 2,
                                "title": "The Middle",
                                "subtitle_id": 457,
                                "translation_needed": False,
                            },
                        ],
                    },
                    {
                        "season_number": 2,
                        "magnet": "magnet:?xt=urn:btih:season2",
                        "episodes": [
                            {
                                "episode_id": "ep-2-1",
                                "number": 1,
                                "title": "New Start",
                                "subtitle_id": None,
                                "translation_needed": False,
                            },
                        ],
                    },
                ],
            },
        ],
    }
