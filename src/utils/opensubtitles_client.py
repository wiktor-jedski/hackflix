"""OpenSubtitles API client for subtitle downloads.

Provides functionality to download subtitles from OpenSubtitles API
using server-specified subtitle IDs.
"""

import logging
from pathlib import Path

import requests

from src.config import OPENSUBTITLES_API_KEY

logger = logging.getLogger(__name__)

# User-Agent is required by OpenSubtitles API
APP_USER_AGENT = "Hackflix v1.0.0"


class OpenSubtitlesError(Exception):
    """Raised when OpenSubtitles API operations fail."""

    pass


class OpenSubtitlesClient:
    """Client for OpenSubtitles API interactions."""

    BASE_URL = "https://api.opensubtitles.com/api/v1"

    def __init__(self) -> None:
        """Initialize the client with API key from config."""
        self.api_key = OPENSUBTITLES_API_KEY
        if not self.api_key:
            raise OpenSubtitlesError("OPENSUBTITLES_API_KEY not configured")

        self.session = requests.Session()
        self.session.headers.update(
            {
                "Api-Key": self.api_key,
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": APP_USER_AGENT,
            }
        )

    def download_subtitle(self, file_id: int, output_path: Path) -> Path:
        """Download a subtitle file by its file ID.

        The OpenSubtitles API uses a two-step download process:
        1. POST to /download with file_id to get a temporary download URL
        2. GET the actual subtitle content from that temporary URL

        Args:
            file_id: OpenSubtitles file ID (from search results attributes.files[].file_id).
            output_path: Destination path for the SRT file.

        Returns:
            Path to the downloaded subtitle file.

        Raises:
            OpenSubtitlesError: On API failure or network errors.
            FileNotFoundError: If output directory doesn't exist.
        """
        if not output_path.parent.exists():
            raise FileNotFoundError(
                f"Output directory does not exist: {output_path.parent}"
            )

        try:
            logger.info("Requesting download URL for file_id=%d", file_id)

            # Step 1: POST to /download to get temporary download URL
            response = self.session.post(
                f"{self.BASE_URL}/download",
                json={"file_id": file_id},
                timeout=30,
            )

            if response.status_code == 429:
                raise OpenSubtitlesError("Rate limit exceeded. Please try again later.")

            if response.status_code == 404:
                raise OpenSubtitlesError(f"Subtitle file_id {file_id} not found")

            response.raise_for_status()

            data = response.json()
            download_url = data.get("link")

            if not download_url:
                raise OpenSubtitlesError("No download link in API response")

            logger.info(
                "Got download URL, remaining downloads: %s", data.get("remaining")
            )

            # Step 2: GET the actual subtitle file from temporary URL
            file_response = requests.get(download_url, timeout=30)
            file_response.raise_for_status()

            content = file_response.content
            output_path.write_bytes(content)

            logger.info("Successfully downloaded subtitle to %s", output_path)
            return output_path

        except requests.exceptions.Timeout as e:
            raise OpenSubtitlesError(f"Request timed out: {e}") from e
        except requests.exceptions.ConnectionError as e:
            raise OpenSubtitlesError(f"Connection error: {e}") from e
        except requests.exceptions.RequestException as e:
            raise OpenSubtitlesError(f"Request failed: {e}") from e

    def search_subtitles(
        self,
        query: str,
        language: str = "en",
        limit: int = 10,
    ) -> list[dict]:
        """Search for subtitles by query.

        Args:
            query: Search query string.
            language: Language filter code (e.g., "en", "pl").
            limit: Maximum number of results.

        Returns:
            List of subtitle metadata dictionaries.
        """
        return self.search_subtitles_with_params(
            params={
                "query": query,
                "languages": language,
            },
            limit=limit,
        )

    def search_subtitles_with_params(
        self,
        params: dict,
        limit: int = 10,
    ) -> list[dict]:
        """Search for subtitles with raw OpenSubtitles query parameters.

        Args:
            params: OpenSubtitles /subtitles query parameters.
            limit: Maximum number of results.

        Returns:
            List of subtitle metadata dictionaries.
        """
        request_params = dict(params)
        request_params["limit"] = limit

        try:
            response = self.session.get(
                f"{self.BASE_URL}/subtitles",
                params=request_params,
                timeout=30,
            )

            response.raise_for_status()
            data = response.json()

            return data.get("data", [])

        except requests.exceptions.RequestException as e:
            logger.error("Subtitle search failed: %s", e)
            return []
