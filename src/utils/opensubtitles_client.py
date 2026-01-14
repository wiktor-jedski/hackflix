"""OpenSubtitles API client for subtitle downloads.

Provides functionality to download subtitles from OpenSubtitles API
using server-specified subtitle IDs.
"""

import logging
import os
from pathlib import Path
from typing import Optional

import requests

from src.config import OPENSUBTITLES_API_KEY

logger = logging.getLogger(__name__)


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
            }
        )

    def download_subtitle(self, subtitle_id: int, output_path: Path) -> Path:
        """Download a subtitle file by its ID.

        Args:
            subtitle_id: OpenSubtitles numeric ID.
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
            logger.info("Downloading subtitle ID=%d to %s", subtitle_id, output_path)

            response = self.session.get(
                f"{self.BASE_URL}/subtitle/download",
                params={"id": subtitle_id},
                timeout=30,
            )

            if response.status_code == 429:
                raise OpenSubtitlesError("Rate limit exceeded. Please try again later.")

            if response.status_code == 404:
                raise OpenSubtitlesError(f"Subtitle ID {subtitle_id} not found")

            response.raise_for_status()

            content = response.content

            if output_path.suffix == ".srt":
                output_path.write_bytes(content)
            else:
                import gzip
                import io

                decompressed = gzip.decompress(content)
                output_path.write_bytes(decompressed)

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
        try:
            response = self.session.get(
                f"{self.BASE_URL}/subtitles",
                params={
                    "query": query,
                    "languages": language,
                    "limit": limit,
                },
                timeout=30,
            )

            response.raise_for_status()
            data = response.json()

            return data.get("data", [])

        except requests.exceptions.RequestException as e:
            logger.error("Subtitle search failed: %s", e)
            return []
