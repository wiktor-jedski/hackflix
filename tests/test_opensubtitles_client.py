"""Tests for OpenSubtitles API client.

Tests cover:
- Successful subtitle download
- API authentication
- Network errors
- Invalid subtitle ID
- Rate limits
- File I/O errors
- Gzip decompression handling
"""

import gzip
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.utils.opensubtitles_client import (
    OpenSubtitlesClient,
    OpenSubtitlesError,
)


class TestOpenSubtitlesClientInitialization:
    """Tests for OpenSubtitlesClient initialization."""

    def test_initialization_with_valid_api_key(self):
        """Verify client initializes with valid API key."""
        with patch("src.utils.opensubtitles_client.OPENSUBTITLES_API_KEY", "test-key"):
            client = OpenSubtitlesClient()
            assert client.api_key == "test-key"
            assert client.BASE_URL == "https://api.opensubtitles.com/api/v1"

    def test_initialization_without_api_key(self):
        """Verify error when API key is not configured."""
        with patch("src.utils.opensubtitles_client.OPENSUBTITLES_API_KEY", ""):
            with pytest.raises(OpenSubtitlesError) as exc_info:
                OpenSubtitlesClient()
            assert "not configured" in str(exc_info.value)

    def test_session_headers_are_set(self):
        """Verify session headers include API key and content type."""
        with patch("src.utils.opensubtitles_client.OPENSUBTITLES_API_KEY", "test-key"):
            client = OpenSubtitlesClient()
            assert client.session.headers.get("Api-Key") == "test-key"
            assert client.session.headers.get("Content-Type") == "application/json"


class TestDownloadSubtitle:
    """Tests for download_subtitle method."""

    def test_download_success_srt_file(self, tmp_path: Path):
        """Verify successful download of SRT file."""
        with patch("src.utils.opensubtitles_client.OPENSUBTITLES_API_KEY", "test-key"):
            client = OpenSubtitlesClient()

            output_path = tmp_path / "subtitle.srt"
            subtitle_content = b"1\n00:00:01,000 --> 00:00:04,000\nTest"

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.content = subtitle_content

            with patch.object(client.session, "get", return_value=mock_response):
                result = client.download_subtitle(12345, output_path)

            assert result == output_path
            assert output_path.read_bytes() == subtitle_content

    def test_download_success_gzip_file(self, tmp_path: Path):
        """Verify successful download and decompression of gzip file."""
        with patch("src.utils.opensubtitles_client.OPENSUBTITLES_API_KEY", "test-key"):
            client = OpenSubtitlesClient()

            output_path = tmp_path / "subtitle"  # No .srt extension to trigger gzip
            original_content = b"1\n00:00:01,000 --> 00:00:04,000\nTest"
            compressed_content = gzip.compress(original_content)

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.content = compressed_content

            with patch.object(client.session, "get", return_value=mock_response):
                result = client.download_subtitle(12345, output_path)

            assert result == output_path
            assert output_path.read_bytes() == original_content

    def test_download_rate_limit_error(self, tmp_path: Path):
        """Verify error handling for rate limit (429)."""
        with patch("src.utils.opensubtitles_client.OPENSUBTITLES_API_KEY", "test-key"):
            client = OpenSubtitlesClient()

            output_path = tmp_path / "subtitle.srt"

            mock_response = MagicMock()
            mock_response.status_code = 429

            with patch.object(client.session, "get", return_value=mock_response):
                with pytest.raises(OpenSubtitlesError) as exc_info:
                    client.download_subtitle(12345, output_path)

                assert "Rate limit" in str(exc_info.value)

    def test_download_not_found_error(self, tmp_path: Path):
        """Verify error handling for 404 not found."""
        with patch("src.utils.opensubtitles_client.OPENSUBTITLES_API_KEY", "test-key"):
            client = OpenSubtitlesClient()

            output_path = tmp_path / "subtitle.srt"

            mock_response = MagicMock()
            mock_response.status_code = 404

            with patch.object(client.session, "get", return_value=mock_response):
                with pytest.raises(OpenSubtitlesError) as exc_info:
                    client.download_subtitle(12345, output_path)

                assert "not found" in str(exc_info.value)

    def test_download_timeout_error(self, tmp_path: Path):
        """Verify error handling for request timeout."""
        with patch("src.utils.opensubtitles_client.OPENSUBTITLES_API_KEY", "test-key"):
            import requests

            client = OpenSubtitlesClient()

            output_path = tmp_path / "subtitle.srt"

            with patch.object(client.session, "get") as mock_get:
                mock_get.side_effect = requests.exceptions.Timeout("Connection timeout")

                with pytest.raises(OpenSubtitlesError) as exc_info:
                    client.download_subtitle(12345, output_path)

                assert "timed out" in str(exc_info.value)

    def test_download_connection_error(self, tmp_path: Path):
        """Verify error handling for connection error."""
        with patch("src.utils.opensubtitles_client.OPENSUBTITLES_API_KEY", "test-key"):
            import requests

            client = OpenSubtitlesClient()

            output_path = tmp_path / "subtitle.srt"

            with patch.object(client.session, "get") as mock_get:
                mock_get.side_effect = requests.exceptions.ConnectionError("DNS error")

                with pytest.raises(OpenSubtitlesError) as exc_info:
                    client.download_subtitle(12345, output_path)

                assert "Connection error" in str(exc_info.value)

    def test_download_http_error(self, tmp_path: Path):
        """Verify error handling for generic HTTP errors."""
        with patch("src.utils.opensubtitles_client.OPENSUBTITLES_API_KEY", "test-key"):
            import requests

            client = OpenSubtitlesClient()

            output_path = tmp_path / "subtitle.srt"

            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.raise_for_status.side_effect = requests.HTTPError(
                "500 Server Error"
            )

            with patch.object(client.session, "get", return_value=mock_response):
                with pytest.raises(OpenSubtitlesError) as exc_info:
                    client.download_subtitle(12345, output_path)

                assert "Request failed" in str(exc_info.value)

    def test_download_missing_directory(self, tmp_path: Path):
        """Verify error when output directory doesn't exist."""
        with patch("src.utils.opensubtitles_client.OPENSUBTITLES_API_KEY", "test-key"):
            client = OpenSubtitlesClient()

            output_path = tmp_path / "nonexistent" / "subtitle.srt"

            with pytest.raises(FileNotFoundError) as exc_info:
                client.download_subtitle(12345, output_path)

            assert "Output directory" in str(exc_info.value)

    def test_download_request_parameters(self, tmp_path: Path):
        """Verify correct request parameters are sent."""
        with patch("src.utils.opensubtitles_client.OPENSUBTITLES_API_KEY", "test-key"):
            client = OpenSubtitlesClient()

            output_path = tmp_path / "subtitle.srt"
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.content = b"test content"

            with patch.object(
                client.session, "get", return_value=mock_response
            ) as mock_get:
                client.download_subtitle(12345, output_path)

                mock_get.assert_called_once_with(
                    "https://api.opensubtitles.com/api/v1/subtitle/download",
                    params={"id": 12345},
                    timeout=30,
                )


class TestSearchSubtitles:
    """Tests for search_subtitles method."""

    def test_search_success(self):
        """Verify successful subtitle search."""
        with patch("src.utils.opensubtitles_client.OPENSUBTITLES_API_KEY", "test-key"):
            client = OpenSubtitlesClient()

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "data": [
                    {"id": "123", "attributes": {"title": "Test Movie"}},
                    {"id": "456", "attributes": {"title": "Another Movie"}},
                ]
            }

            with patch.object(client.session, "get", return_value=mock_response):
                result = client.search_subtitles("test query")

            assert len(result) == 2
            assert result[0]["id"] == "123"

    def test_search_empty_results(self):
        """Verify empty list when no results found."""
        with patch("src.utils.opensubtitles_client.OPENSUBTITLES_API_KEY", "test-key"):
            client = OpenSubtitlesClient()

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"data": []}

            with patch.object(client.session, "get", return_value=mock_response):
                result = client.search_subtitles("nonexistent movie")

            assert result == []

    def test_search_with_language_filter(self):
        """Verify search with language filter."""
        with patch("src.utils.opensubtitles_client.OPENSUBTITLES_API_KEY", "test-key"):
            client = OpenSubtitlesClient()

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"data": []}

            with patch.object(
                client.session, "get", return_value=mock_response
            ) as mock_get:
                client.search_subtitles("test", language="pl", limit=5)

                mock_get.assert_called_once()
                call_params = mock_get.call_args[1]["params"]
                assert call_params["languages"] == "pl"
                assert call_params["limit"] == 5

    def test_search_handles_request_error(self):
        """Verify search returns empty list on request error."""
        with patch("src.utils.opensubtitles_client.OPENSUBTITLES_API_KEY", "test-key"):
            import requests

            client = OpenSubtitlesClient()

            with patch.object(client.session, "get") as mock_get:
                mock_get.side_effect = requests.exceptions.RequestException(
                    "Network error"
                )

                result = client.search_subtitles("test")

            assert result == []


class TestOpenSubtitlesError:
    """Tests for OpenSubtitlesError exception."""

    def test_error_is_exception_subclass(self):
        """Verify OpenSubtitlesError is an Exception subclass."""
        error = OpenSubtitlesError("Test error")
        assert isinstance(error, Exception)

    def test_error_message(self):
        """Verify error message is preserved."""
        error = OpenSubtitlesError("Custom error message")
        assert "Custom error message" in str(error)
