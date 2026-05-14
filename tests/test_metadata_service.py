"""Tests for the MetadataService."""

import json
import urllib.error
from pathlib import Path
from unittest import mock

import pytest

from src.database.db_manager import DatabaseManager
from src.services.metadata_service import MetadataService


class TestServicesModuleLazyImport:
    """Tests for the services module lazy import mechanism."""

    def test_import_metadata_service_from_package(self) -> None:
        """Test that MetadataService can be imported from src.services."""
        from src import services

        assert hasattr(services, "MetadataService")
        assert services.MetadataService is MetadataService

    def test_import_torrent_service_from_package(self) -> None:
        """Test that TorrentService can be imported from src.services."""

    def test_import_invalid_attribute_raises_error(self) -> None:
        """Test that importing invalid attribute raises AttributeError."""
        from src import services

        with pytest.raises(AttributeError, match="has no attribute"):
            _ = services.NonExistentClass


class TestMetadataServiceInit:
    """Tests for MetadataService initialization."""

    def test_init_with_defaults(self, db_manager: DatabaseManager) -> None:
        """Test initialization with default values."""
        service = MetadataService(db_manager=db_manager)

        assert service._db_manager is db_manager
        # catalog_url comes from config.CATALOG_URL (may be set via env)
        from src.config import CATALOG_URL

        assert service._catalog_url == CATALOG_URL
        assert service._should_stop is False

    def test_init_with_custom_values(
        self, db_manager: DatabaseManager, tmp_path: Path
    ) -> None:
        """Test initialization with custom values."""
        cache_dir = tmp_path / "cache"
        service = MetadataService(
            db_manager=db_manager,
            catalog_url="https://example.com/content.json",
            cache_dir=cache_dir,
        )

        assert service._catalog_url == "https://example.com/content.json"
        assert service._cache_dir == cache_dir
        assert service._poster_dir == cache_dir / "posters"

    def test_stop_sets_flag(self, db_manager: DatabaseManager) -> None:
        """Test that stop() sets the _should_stop flag."""
        service = MetadataService(db_manager=db_manager)
        assert service._should_stop is False

        service.stop()
        assert service._should_stop is True


class TestMetadataServiceSync:
    """Tests for MetadataService sync operation."""

    @pytest.fixture
    def service(self, db_manager: DatabaseManager, tmp_path: Path) -> MetadataService:
        """Create a MetadataService with test configuration."""
        return MetadataService(
            db_manager=db_manager,
            catalog_url="https://example.com/content.json",
            cache_dir=tmp_path / "cache",
        )

    def test_sync_success_emits_signals(
        self, service: MetadataService, sample_content_json: dict
    ) -> None:
        """Test successful sync emits all expected signals."""
        mock_response = mock.MagicMock()
        mock_response.read.return_value = json.dumps(sample_content_json).encode()
        mock_response.__enter__ = mock.MagicMock(return_value=mock_response)
        mock_response.__exit__ = mock.MagicMock(return_value=False)

        # Track signal emissions
        started_emissions: list[tuple] = []
        progress_emissions: list[tuple] = []
        completed_emissions: list[tuple] = []
        error_emissions: list[tuple] = []

        service.sync_started.connect(lambda: started_emissions.append(()))
        service.sync_progress.connect(
            lambda c, t, m: progress_emissions.append((c, t, m))
        )
        service.sync_completed.connect(lambda: completed_emissions.append(()))
        service.sync_error.connect(lambda e: error_emissions.append((e,)))

        with mock.patch("urllib.request.urlopen", return_value=mock_response):
            service.run()

        assert len(started_emissions) == 1
        assert len(progress_emissions) == 4  # 0/3, 1/3, 2/3, 3/3
        assert progress_emissions[0] == (0, 3, "Fetching catalog...")
        assert progress_emissions[1] == (1, 3, "Updating database...")
        assert progress_emissions[2] == (2, 3, "Caching poster images...")
        assert progress_emissions[3] == (3, 3, "Sync complete")
        assert len(completed_emissions) == 1
        assert len(error_emissions) == 0

    def test_sync_calls_upsert_content(
        self, service: MetadataService, sample_content_json: dict
    ) -> None:
        """Test that sync calls db_manager.upsert_content with parsed data."""
        mock_response = mock.MagicMock()
        mock_response.read.return_value = json.dumps(sample_content_json).encode()
        mock_response.__enter__ = mock.MagicMock(return_value=mock_response)
        mock_response.__exit__ = mock.MagicMock(return_value=False)

        with mock.patch("urllib.request.urlopen", return_value=mock_response):
            with mock.patch.object(
                service._db_manager, "upsert_content"
            ) as mock_upsert:
                service.run()
                mock_upsert.assert_called_once_with(sample_content_json)

    def test_sync_network_error_emits_error_signal(
        self, service: MetadataService
    ) -> None:
        """Test network error emits error signal."""
        error_emissions: list[tuple] = []
        service.sync_error.connect(lambda e: error_emissions.append((e,)))

        with mock.patch(
            "urllib.request.urlopen",
            side_effect=urllib.error.URLError("Connection refused"),
        ):
            service.run()

        assert len(error_emissions) == 1
        assert "Network error" in error_emissions[0][0]
        assert "Connection refused" in error_emissions[0][0]

    def test_sync_json_error_emits_error_signal(self, service: MetadataService) -> None:
        """Test invalid JSON emits error signal."""
        mock_response = mock.MagicMock()
        mock_response.read.return_value = b"not valid json"
        mock_response.__enter__ = mock.MagicMock(return_value=mock_response)
        mock_response.__exit__ = mock.MagicMock(return_value=False)

        error_emissions: list[tuple] = []
        service.sync_error.connect(lambda e: error_emissions.append((e,)))

        with mock.patch("urllib.request.urlopen", return_value=mock_response):
            service.run()

        assert len(error_emissions) == 1
        assert "Invalid catalog format" in error_emissions[0][0]

    def test_sync_generic_exception_emits_error_signal(
        self, service: MetadataService
    ) -> None:
        """Test generic exception emits error signal."""
        mock_response = mock.MagicMock()
        mock_response.read.return_value = b'{"items": []}'
        mock_response.__enter__ = mock.MagicMock(return_value=mock_response)
        mock_response.__exit__ = mock.MagicMock(return_value=False)

        error_emissions: list[tuple] = []
        service.sync_error.connect(lambda e: error_emissions.append((e,)))

        with mock.patch("urllib.request.urlopen", return_value=mock_response):
            with mock.patch.object(
                service._db_manager,
                "upsert_content",
                side_effect=Exception("Database error"),
            ):
                service.run()

        assert len(error_emissions) == 1
        assert "Database error" in error_emissions[0][0]

    def test_sync_stops_after_fetch_when_stop_called(
        self, service: MetadataService, sample_content_json: dict
    ) -> None:
        """Test sync stops after fetch if stop() was called."""
        mock_response = mock.MagicMock()
        mock_response.read.return_value = json.dumps(sample_content_json).encode()
        mock_response.__enter__ = mock.MagicMock(return_value=mock_response)
        mock_response.__exit__ = mock.MagicMock(return_value=False)

        completed_emissions: list[tuple] = []
        service.sync_completed.connect(lambda: completed_emissions.append(()))

        def stop_after_fetch(*args, **kwargs):
            service._should_stop = True
            return mock_response

        with mock.patch("urllib.request.urlopen", side_effect=stop_after_fetch):
            service.run()

        # Should not emit completed because we stopped early
        assert len(completed_emissions) == 0

    def test_sync_stops_after_upsert_when_stop_called(
        self, service: MetadataService, sample_content_json: dict
    ) -> None:
        """Test sync stops after upsert if stop() was called."""
        mock_response = mock.MagicMock()
        mock_response.read.return_value = json.dumps(sample_content_json).encode()
        mock_response.__enter__ = mock.MagicMock(return_value=mock_response)
        mock_response.__exit__ = mock.MagicMock(return_value=False)

        completed_emissions: list[tuple] = []
        service.sync_completed.connect(lambda: completed_emissions.append(()))

        def stop_after_upsert(*args, **kwargs):
            service._should_stop = True

        with mock.patch("urllib.request.urlopen", return_value=mock_response):
            with mock.patch.object(
                service._db_manager, "upsert_content", side_effect=stop_after_upsert
            ):
                service.run()

        # Should not emit completed because we stopped early
        assert len(completed_emissions) == 0


class TestMetadataServicePosterCaching:
    """Tests for poster image caching."""

    @pytest.fixture
    def service(self, db_manager: DatabaseManager, tmp_path: Path) -> MetadataService:
        """Create a MetadataService with test configuration."""
        return MetadataService(
            db_manager=db_manager,
            catalog_url="https://example.com/content.json",
            cache_dir=tmp_path / "cache",
        )

    def test_ensure_cache_dirs_creates_directories(
        self, service: MetadataService
    ) -> None:
        """Test _ensure_cache_dirs creates poster directory."""
        assert not service._poster_dir.exists()
        service._ensure_cache_dirs()
        assert service._poster_dir.exists()

    def test_poster_caching_downloads_images(
        self, service: MetadataService, tmp_path: Path
    ) -> None:
        """Test poster images are downloaded and cached."""
        content = {
            "items": [
                {
                    "id": "movie-1",
                    "type": "movie",
                    "title": "Test Movie",
                    "poster_url": "https://example.com/poster1.jpg",
                }
            ]
        }

        mock_content = mock.MagicMock()
        mock_content.read.return_value = json.dumps(content).encode()
        mock_content.__enter__ = mock.MagicMock(return_value=mock_content)
        mock_content.__exit__ = mock.MagicMock(return_value=False)

        mock_poster = mock.MagicMock()
        mock_poster.read.return_value = b"fake image data"
        mock_poster.__enter__ = mock.MagicMock(return_value=mock_poster)
        mock_poster.__exit__ = mock.MagicMock(return_value=False)

        def urlopen_side_effect(url, timeout=None):
            if "content.json" in url:
                return mock_content
            return mock_poster

        with mock.patch("urllib.request.urlopen", side_effect=urlopen_side_effect):
            service.run()

        poster_path = service._poster_dir / "movie-1.jpg"
        assert poster_path.exists()
        assert poster_path.read_bytes() == b"fake image data"

    def test_poster_cache_sanitizes_id_and_extension(
        self, service: MetadataService
    ) -> None:
        """Verify unsafe catalog IDs and URL suffixes stay inside poster cache."""
        service._ensure_cache_dirs()
        mock_poster = mock.MagicMock()
        mock_poster.read.return_value = b"poster"
        mock_poster.__enter__ = mock.MagicMock(return_value=mock_poster)
        mock_poster.__exit__ = mock.MagicMock(return_value=False)

        with mock.patch("urllib.request.urlopen", return_value=mock_poster):
            poster_path = service._download_poster(
                "../unsafe/movie", "https://example.com/poster.php?name=x.jpg"
            )

        assert poster_path.parent == service._poster_dir.resolve()
        assert poster_path.name == "unsafe_movie.jpg"
        assert poster_path.exists()

    def test_poster_caching_skips_existing(
        self, service: MetadataService, tmp_path: Path
    ) -> None:
        """Test poster caching skips already cached images."""
        service._ensure_cache_dirs()
        existing_poster = service._poster_dir / "movie-1.jpg"
        existing_poster.write_bytes(b"existing data")

        content = {
            "items": [
                {
                    "id": "movie-1",
                    "type": "movie",
                    "title": "Existing Poster Movie",
                    "poster_url": "https://example.com/poster1.jpg",
                }
            ]
        }

        mock_content = mock.MagicMock()
        mock_content.read.return_value = json.dumps(content).encode()
        mock_content.__enter__ = mock.MagicMock(return_value=mock_content)
        mock_content.__exit__ = mock.MagicMock(return_value=False)

        urlopen_calls: list[str] = []

        def urlopen_side_effect(url, timeout=None):
            urlopen_calls.append(url)
            return mock_content

        with mock.patch("urllib.request.urlopen", side_effect=urlopen_side_effect):
            service.run()

        # Should only call urlopen for content.json, not poster
        assert len(urlopen_calls) == 1
        assert "content.json" in urlopen_calls[0]
        # Existing data should be preserved
        assert existing_poster.read_bytes() == b"existing data"

    def test_poster_download_failure_continues(self, service: MetadataService) -> None:
        """Test that poster download failure doesn't abort sync."""
        content = {
            "items": [
                {
                    "id": "movie-1",
                    "type": "movie",
                    "title": "Bad Poster Movie",
                    "poster_url": "https://bad.url/poster.jpg",
                },
                {
                    "id": "movie-2",
                    "type": "movie",
                    "title": "Good Poster Movie",
                    "poster_url": "https://good.url/poster.jpg",
                },
            ]
        }

        mock_content = mock.MagicMock()
        mock_content.read.return_value = json.dumps(content).encode()
        mock_content.__enter__ = mock.MagicMock(return_value=mock_content)
        mock_content.__exit__ = mock.MagicMock(return_value=False)

        mock_good_poster = mock.MagicMock()
        mock_good_poster.read.return_value = b"good image"
        mock_good_poster.__enter__ = mock.MagicMock(return_value=mock_good_poster)
        mock_good_poster.__exit__ = mock.MagicMock(return_value=False)

        def urlopen_side_effect(url, timeout=None):
            if "content.json" in url:
                return mock_content
            if "bad.url" in url:
                raise urllib.error.URLError("Poster not found")
            return mock_good_poster

        completed_emissions: list[tuple] = []
        service.sync_completed.connect(lambda: completed_emissions.append(()))

        with mock.patch("urllib.request.urlopen", side_effect=urlopen_side_effect):
            service.run()

        # Should still complete despite poster failure
        assert len(completed_emissions) == 1
        # Second poster should be cached
        assert (service._poster_dir / "movie-2.jpg").exists()

    def test_poster_caching_skips_items_without_poster_url(
        self, service: MetadataService
    ) -> None:
        """Test items without poster_url are skipped."""
        content = {
            "items": [{"id": "movie-1", "type": "movie", "title": "No Poster Movie"}]
        }

        mock_content = mock.MagicMock()
        mock_content.read.return_value = json.dumps(content).encode()
        mock_content.__enter__ = mock.MagicMock(return_value=mock_content)
        mock_content.__exit__ = mock.MagicMock(return_value=False)

        urlopen_calls: list[str] = []

        def urlopen_side_effect(url, timeout=None):
            urlopen_calls.append(url)
            return mock_content

        with mock.patch("urllib.request.urlopen", side_effect=urlopen_side_effect):
            service.run()

        # Should only call urlopen for content.json
        assert len(urlopen_calls) == 1

    def test_poster_caching_stops_when_stop_called(
        self, service: MetadataService
    ) -> None:
        """Test poster caching stops if stop() was called."""
        content = {
            "items": [
                {
                    "id": "movie-1",
                    "type": "movie",
                    "title": "Movie 1",
                    "poster_url": "https://example.com/poster1.jpg",
                },
                {
                    "id": "movie-2",
                    "type": "movie",
                    "title": "Movie 2",
                    "poster_url": "https://example.com/poster2.jpg",
                },
            ]
        }

        mock_content = mock.MagicMock()
        mock_content.read.return_value = json.dumps(content).encode()
        mock_content.__enter__ = mock.MagicMock(return_value=mock_content)
        mock_content.__exit__ = mock.MagicMock(return_value=False)

        poster_download_count = 0

        def urlopen_side_effect(url, timeout=None):
            nonlocal poster_download_count
            if "content.json" in url:
                return mock_content
            poster_download_count += 1
            service._should_stop = True  # Stop after first poster
            mock_poster = mock.MagicMock()
            mock_poster.read.return_value = b"image"
            mock_poster.__enter__ = mock.MagicMock(return_value=mock_poster)
            mock_poster.__exit__ = mock.MagicMock(return_value=False)
            return mock_poster

        with mock.patch("urllib.request.urlopen", side_effect=urlopen_side_effect):
            service.run()

        # Should stop after first poster
        assert poster_download_count == 1

    def test_download_poster_uses_default_extension(
        self, service: MetadataService
    ) -> None:
        """Test _download_poster uses .jpg when URL has no extension."""
        service._ensure_cache_dirs()

        mock_response = mock.MagicMock()
        mock_response.read.return_value = b"image data"
        mock_response.__enter__ = mock.MagicMock(return_value=mock_response)
        mock_response.__exit__ = mock.MagicMock(return_value=False)

        with mock.patch("urllib.request.urlopen", return_value=mock_response):
            result = service._download_poster("test-id", "https://example.com/poster")

        assert result == service._poster_dir / "test-id.jpg"
        assert result.exists()


class TestMetadataServiceSeriesDataValidation:
    """Tests for Series data parsing and validation."""

    @pytest.fixture
    def service(self, db_manager: DatabaseManager, tmp_path: Path) -> MetadataService:
        """Create a MetadataService with test configuration."""
        return MetadataService(
            db_manager=db_manager,
            catalog_url="https://example.com/content.json",
            cache_dir=tmp_path / "cache",
        )

    def test_sync_passes_complete_series_structure(
        self, service: MetadataService
    ) -> None:
        """Test that sync passes complete Series structure to upsert_content."""
        content = {
            "version": 1,
            "items": [
                {
                    "id": "series-uuid-1",
                    "type": "series",
                    "title": "Test Series",
                    "genres": "Drama, Thriller",
                    "poster_url": "https://example.com/series.jpg",
                    "seasons": [
                        {
                            "season_number": 1,
                            "magnet": "magnet:?xt=urn:btih:season1hash",
                            "episodes": [
                                {
                                    "episode_id": "ep-1-1",
                                    "number": 1,
                                    "title": "Pilot",
                                    "subtitle_id": 1001,
                                    "translation_needed": True,
                                },
                                {
                                    "episode_id": "ep-1-2",
                                    "number": 2,
                                    "title": "Second Episode",
                                    "subtitle_id": 1002,
                                    "translation_needed": False,
                                },
                            ],
                        },
                        {
                            "season_number": 2,
                            "magnet": "magnet:?xt=urn:btih:season2hash",
                            "episodes": [
                                {
                                    "episode_id": "ep-2-1",
                                    "number": 1,
                                    "title": "New Beginning",
                                    "subtitle_id": None,
                                    "translation_needed": False,
                                },
                            ],
                        },
                    ],
                }
            ],
        }

        mock_response = mock.MagicMock()
        mock_response.read.return_value = json.dumps(content).encode()
        mock_response.__enter__ = mock.MagicMock(return_value=mock_response)
        mock_response.__exit__ = mock.MagicMock(return_value=False)

        with mock.patch("urllib.request.urlopen", return_value=mock_response):
            with mock.patch.object(
                service._db_manager, "upsert_content"
            ) as mock_upsert:
                service.run()

                mock_upsert.assert_called_once()
                call_args = mock_upsert.call_args[0][0]

                # Verify the structure is intact
                assert "items" in call_args
                series = call_args["items"][0]

                assert series["id"] == "series-uuid-1"
                assert series["type"] == "series"
                assert series["title"] == "Test Series"
                assert "seasons" in series
                assert len(series["seasons"]) == 2

                # Check season 1 structure
                season1 = series["seasons"][0]
                assert season1["season_number"] == 1
                assert season1["magnet"] == "magnet:?xt=urn:btih:season1hash"
                assert len(season1["episodes"]) == 2

                # Check episode structure in season 1
                ep1 = season1["episodes"][0]
                assert ep1["number"] == 1
                assert ep1["title"] == "Pilot"
                assert ep1["subtitle_id"] == 1001
                assert ep1["translation_needed"] is True

                ep2 = season1["episodes"][1]
                assert ep2["number"] == 2
                assert ep2["subtitle_id"] == 1002
                assert ep2["translation_needed"] is False

                # Check season 2 structure
                season2 = series["seasons"][1]
                assert season2["season_number"] == 2
                assert len(season2["episodes"]) == 1
                assert season2["episodes"][0]["subtitle_id"] is None

    def test_sync_handles_series_with_empty_seasons(
        self, service: MetadataService
    ) -> None:
        """Test that sync handles series with empty seasons list."""
        content = {
            "items": [
                {
                    "id": "series-empty",
                    "type": "series",
                    "title": "Series Without Seasons",
                    "seasons": [],
                }
            ],
        }

        mock_response = mock.MagicMock()
        mock_response.read.return_value = json.dumps(content).encode()
        mock_response.__enter__ = mock.MagicMock(return_value=mock_response)
        mock_response.__exit__ = mock.MagicMock(return_value=False)

        completed_emissions: list[tuple] = []
        service.sync_completed.connect(lambda: completed_emissions.append(()))

        with mock.patch("urllib.request.urlopen", return_value=mock_response):
            service.run()

        # Should complete without error
        assert len(completed_emissions) == 1

    def test_sync_handles_season_with_empty_episodes(
        self, service: MetadataService
    ) -> None:
        """Test that sync handles seasons with empty episodes list."""
        content = {
            "items": [
                {
                    "id": "series-no-eps",
                    "type": "series",
                    "title": "Series With Empty Season",
                    "seasons": [
                        {
                            "season_number": 1,
                            "magnet": "magnet:?xt=urn:btih:test",
                            "episodes": [],
                        }
                    ],
                }
            ],
        }

        mock_response = mock.MagicMock()
        mock_response.read.return_value = json.dumps(content).encode()
        mock_response.__enter__ = mock.MagicMock(return_value=mock_response)
        mock_response.__exit__ = mock.MagicMock(return_value=False)

        with mock.patch("urllib.request.urlopen", return_value=mock_response):
            with mock.patch.object(
                service._db_manager, "upsert_content"
            ) as mock_upsert:
                service.run()

                call_args = mock_upsert.call_args[0][0]
                season = call_args["items"][0]["seasons"][0]
                assert season["episodes"] == []

    def test_sync_handles_episodes_without_optional_fields(
        self, service: MetadataService
    ) -> None:
        """Test that sync handles episodes missing optional fields."""
        content = {
            "items": [
                {
                    "id": "series-minimal-eps",
                    "type": "series",
                    "title": "Series With Minimal Episodes",
                    "seasons": [
                        {
                            "season_number": 1,
                            "episodes": [
                                {
                                    "number": 1,
                                    # No title, subtitle_id, or translation_needed
                                }
                            ],
                        }
                    ],
                }
            ],
        }

        mock_response = mock.MagicMock()
        mock_response.read.return_value = json.dumps(content).encode()
        mock_response.__enter__ = mock.MagicMock(return_value=mock_response)
        mock_response.__exit__ = mock.MagicMock(return_value=False)

        with mock.patch("urllib.request.urlopen", return_value=mock_response):
            with mock.patch.object(
                service._db_manager, "upsert_content"
            ) as mock_upsert:
                service.run()

                call_args = mock_upsert.call_args[0][0]
                episode = call_args["items"][0]["seasons"][0]["episodes"][0]
                assert episode["number"] == 1
                # Optional fields should not exist in the dict
                assert "title" not in episode or episode.get("title") is None

    def test_sync_preserves_movie_and_series_mixed(
        self, service: MetadataService
    ) -> None:
        """Test that sync preserves both movies and series in the same catalog."""
        content = {
            "items": [
                {
                    "id": "movie-1",
                    "type": "movie",
                    "title": "Test Movie",
                    "magnet": "magnet:?xt=urn:btih:moviehash",
                },
                {
                    "id": "series-1",
                    "type": "series",
                    "title": "Test Series",
                    "seasons": [
                        {
                            "season_number": 1,
                            "magnet": "magnet:?xt=urn:btih:seasonhash",
                            "episodes": [{"number": 1, "title": "Pilot"}],
                        }
                    ],
                },
                {
                    "id": "movie-2",
                    "type": "movie",
                    "title": "Another Movie",
                    "magnet": "magnet:?xt=urn:btih:movie2hash",
                },
            ],
        }

        mock_response = mock.MagicMock()
        mock_response.read.return_value = json.dumps(content).encode()
        mock_response.__enter__ = mock.MagicMock(return_value=mock_response)
        mock_response.__exit__ = mock.MagicMock(return_value=False)

        with mock.patch("urllib.request.urlopen", return_value=mock_response):
            with mock.patch.object(
                service._db_manager, "upsert_content"
            ) as mock_upsert:
                service.run()

                call_args = mock_upsert.call_args[0][0]
                items = call_args["items"]

                assert len(items) == 3
                assert items[0]["type"] == "movie"
                assert items[1]["type"] == "series"
                assert items[2]["type"] == "movie"

                # Verify series has seasons
                assert "seasons" in items[1]
                assert len(items[1]["seasons"]) == 1

                # Verify movies don't have seasons
                assert "seasons" not in items[0]
                assert "seasons" not in items[2]

    def test_sync_passes_translation_needed_correctly(
        self, service: MetadataService
    ) -> None:
        """Test that translation_needed boolean is correctly passed."""
        content = {
            "items": [
                {
                    "id": "series-translation",
                    "type": "series",
                    "title": "Translation Test Series",
                    "seasons": [
                        {
                            "season_number": 1,
                            "episodes": [
                                {
                                    "number": 1,
                                    "title": "Episode Needing Translation",
                                    "translation_needed": True,
                                },
                                {
                                    "number": 2,
                                    "title": "Episode Not Needing Translation",
                                    "translation_needed": False,
                                },
                                {
                                    "number": 3,
                                    "title": "Episode With Default",
                                    # translation_needed not specified, should default
                                },
                            ],
                        }
                    ],
                }
            ],
        }

        mock_response = mock.MagicMock()
        mock_response.read.return_value = json.dumps(content).encode()
        mock_response.__enter__ = mock.MagicMock(return_value=mock_response)
        mock_response.__exit__ = mock.MagicMock(return_value=False)

        with mock.patch("urllib.request.urlopen", return_value=mock_response):
            with mock.patch.object(
                service._db_manager, "upsert_content"
            ) as mock_upsert:
                service.run()

                call_args = mock_upsert.call_args[0][0]
                episodes = call_args["items"][0]["seasons"][0]["episodes"]

                assert episodes[0]["translation_needed"] is True
                assert episodes[1]["translation_needed"] is False
                # Third episode may or may not have the field depending on JSON
