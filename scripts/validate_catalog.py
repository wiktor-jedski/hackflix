#!/usr/bin/env python3
"""
Catalog validation script for HackFlix catalog.json

Validates:
- JSON syntax
- Required fields
- Data types
- Format validation (timestamps, magnet links, IMDb IDs)
- Business logic (unique IDs, genre consistency)
"""

import json
import sys
import re
from datetime import datetime
from typing import Dict, List, Set, Tuple
from pathlib import Path


# Validation constants
VALID_VIDEO_QUALITIES = ['480p', '720p', '1080p', '2160p', '4K']
VALID_VIDEO_CODECS = ['H.264', 'H.265', 'HEVC', 'VP9', 'AV1', 'MPEG-4']
VALID_AUDIO_CODECS = ['AAC', 'AC3', 'DTS', 'MP3', 'FLAC', 'Opus']
MIN_YEAR = 1900
MAX_FILE_SIZE = 100 * 1024 * 1024 * 1024  # 100 GB
MIN_FILE_SIZE = 1024 * 1024  # 1 MB

# Regex patterns
MAGNET_PATTERN = re.compile(r'^magnet:\?xt=urn:btih:[a-fA-F0-9]{40}')
IMDB_ID_PATTERN = re.compile(r'^tt\d{7,10}$')
ISO8601_PATTERN = re.compile(
    r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$'
)
VERSION_PATTERN = re.compile(r'^\d+\.\d+\.\d+$')
LANGUAGE_CODE_PATTERN = re.compile(r'^[a-z]{2}$')


class ValidationError(Exception):
    """Custom exception for validation errors"""
    pass


class CatalogValidator:
    """Validator for catalog.json"""

    def __init__(self, catalog_path: str):
        self.catalog_path = Path(catalog_path)
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.catalog: Dict = {}
        self.all_ids: Set[str] = set()
        self.all_genres: Set[str] = set()

    def validate(self) -> bool:
        """
        Run all validation checks.
        Returns True if valid, False otherwise.
        """
        print(f"Validating catalog: {self.catalog_path}")
        print("=" * 60)

        try:
            # Load and parse JSON
            self._load_catalog()

            # Validate root structure
            self._validate_root_structure()

            # Validate genres list
            self._validate_genres()

            # Validate movies
            self._validate_movies()

            # Validate series
            self._validate_series()

            # Cross-validation
            self._validate_cross_references()

            # Print results
            self._print_results()

            return len(self.errors) == 0

        except Exception as e:
            print(f"\n❌ FATAL ERROR: {str(e)}\n")
            return False

    def _load_catalog(self):
        """Load and parse catalog.json"""
        if not self.catalog_path.exists():
            raise ValidationError(f"Catalog file not found: {self.catalog_path}")

        try:
            with open(self.catalog_path, 'r', encoding='utf-8') as f:
                self.catalog = json.load(f)
        except json.JSONDecodeError as e:
            raise ValidationError(f"Invalid JSON syntax: {e}")

        # Check file size
        file_size = self.catalog_path.stat().st_size
        if file_size > 10 * 1024 * 1024:  # 10 MB
            self.warnings.append(
                f"Catalog file is large ({file_size / 1024 / 1024:.2f} MB). "
                "Consider splitting or optimizing."
            )

    def _validate_root_structure(self):
        """Validate root-level fields"""
        required_fields = ['version', 'last_updated', 'movies', 'series', 'genres']

        for field in required_fields:
            if field not in self.catalog:
                self.errors.append(f"Missing required root field: '{field}'")

        # Validate version
        if 'version' in self.catalog:
            version = self.catalog['version']
            if not isinstance(version, str):
                self.errors.append(f"Field 'version' must be string, got {type(version).__name__}")
            elif not VERSION_PATTERN.match(version):
                self.errors.append(f"Field 'version' must be semantic version (e.g., '1.0.0'), got '{version}'")

        # Validate last_updated timestamp
        if 'last_updated' in self.catalog:
            timestamp = self.catalog['last_updated']
            if not isinstance(timestamp, str):
                self.errors.append(f"Field 'last_updated' must be string, got {type(timestamp).__name__}")
            elif not ISO8601_PATTERN.match(timestamp):
                self.errors.append(
                    f"Field 'last_updated' must be ISO 8601 format (YYYY-MM-DDTHH:MM:SSZ), "
                    f"got '{timestamp}'"
                )
            else:
                # Validate timestamp is not in the future
                try:
                    ts = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    if ts > datetime.now().astimezone():
                        self.warnings.append(f"Timestamp 'last_updated' is in the future: {timestamp}")
                except ValueError as e:
                    self.errors.append(f"Invalid timestamp 'last_updated': {e}")

        # Validate movies and series are arrays
        for field in ['movies', 'series', 'genres']:
            if field in self.catalog:
                if not isinstance(self.catalog[field], list):
                    self.errors.append(f"Field '{field}' must be array, got {type(self.catalog[field]).__name__}")

    def _validate_genres(self):
        """Validate genres array"""
        if 'genres' not in self.catalog:
            return

        genres = self.catalog['genres']

        if len(genres) == 0:
            self.warnings.append("Genres array is empty")

        for genre in genres:
            if not isinstance(genre, str):
                self.errors.append(f"Genre must be string, got {type(genre).__name__}: {genre}")
            elif not genre.strip():
                self.errors.append("Genre cannot be empty string")
            else:
                self.all_genres.add(genre)

        # Check for duplicates
        if len(genres) != len(set(genres)):
            duplicates = [g for g in genres if genres.count(g) > 1]
            self.errors.append(f"Duplicate genres found: {set(duplicates)}")

    def _validate_movies(self):
        """Validate all movies"""
        if 'movies' not in self.catalog:
            return

        movies = self.catalog['movies']
        print(f"\nValidating {len(movies)} movies...")

        for idx, movie in enumerate(movies):
            self._validate_movie(movie, idx)

    def _validate_movie(self, movie: Dict, index: int):
        """Validate a single movie"""
        prefix = f"Movie #{index + 1}"

        # Check type
        if not isinstance(movie, dict):
            self.errors.append(f"{prefix}: Must be object, got {type(movie).__name__}")
            return

        # Required fields
        required = ['id', 'title', 'year', 'genre', 'description',
                   'magnet_link', 'file_size', 'subtitle_languages']

        for field in required:
            if field not in movie:
                self.errors.append(f"{prefix}: Missing required field '{field}'")

        # Validate ID
        if 'id' in movie:
            movie_id = movie['id']
            if not isinstance(movie_id, str) or not movie_id.strip():
                self.errors.append(f"{prefix}: Field 'id' must be non-empty string")
            else:
                if movie_id in self.all_ids:
                    self.errors.append(f"{prefix}: Duplicate ID '{movie_id}'")
                self.all_ids.add(movie_id)

                if not movie_id.startswith('movie_'):
                    self.warnings.append(f"{prefix}: ID '{movie_id}' should start with 'movie_'")

        # Validate title
        if 'title' in movie:
            title = movie['title']
            if not isinstance(title, str) or not title.strip():
                self.errors.append(f"{prefix}: Field 'title' must be non-empty string")
            elif len(title) > 200:
                self.warnings.append(f"{prefix}: Title is very long ({len(title)} chars)")

        # Validate year
        if 'year' in movie:
            year = movie['year']
            if not isinstance(year, int):
                self.errors.append(f"{prefix}: Field 'year' must be integer, got {type(year).__name__}")
            elif year < MIN_YEAR or year > datetime.now().year + 2:
                self.errors.append(
                    f"{prefix}: Year {year} out of valid range "
                    f"({MIN_YEAR} to {datetime.now().year + 2})"
                )

        # Validate genre array
        if 'genre' in movie:
            genres = movie['genre']
            if not isinstance(genres, list):
                self.errors.append(f"{prefix}: Field 'genre' must be array")
            elif len(genres) == 0:
                self.errors.append(f"{prefix}: Field 'genre' must have at least one genre")
            else:
                for genre in genres:
                    if not isinstance(genre, str):
                        self.errors.append(f"{prefix}: Genre must be string, got {type(genre).__name__}")
                    elif genre not in self.all_genres and self.all_genres:
                        self.warnings.append(
                            f"{prefix}: Genre '{genre}' not in catalog genres list"
                        )

        # Validate description
        if 'description' in movie:
            desc = movie['description']
            if not isinstance(desc, str) or not desc.strip():
                self.errors.append(f"{prefix}: Field 'description' must be non-empty string")
            elif len(desc) > 500:
                self.warnings.append(f"{prefix}: Description is very long ({len(desc)} chars)")
            elif len(desc) < 50:
                self.warnings.append(f"{prefix}: Description is very short ({len(desc)} chars)")

        # Validate magnet link
        if 'magnet_link' in movie:
            magnet = movie['magnet_link']
            if not isinstance(magnet, str):
                self.errors.append(f"{prefix}: Field 'magnet_link' must be string")
            elif not MAGNET_PATTERN.match(magnet):
                self.errors.append(
                    f"{prefix}: Invalid magnet link format. "
                    "Must start with 'magnet:?xt=urn:btih:' followed by 40-char hex hash"
                )
            elif len(magnet) > 2000:
                self.warnings.append(f"{prefix}: Magnet link is very long ({len(magnet)} chars)")

        # Validate file size
        if 'file_size' in movie:
            size = movie['file_size']
            if not isinstance(size, int):
                self.errors.append(f"{prefix}: Field 'file_size' must be integer")
            elif size < MIN_FILE_SIZE:
                self.warnings.append(
                    f"{prefix}: File size seems too small: "
                    f"{size / 1024 / 1024:.2f} MB"
                )
            elif size > MAX_FILE_SIZE:
                self.errors.append(
                    f"{prefix}: File size exceeds maximum: "
                    f"{size / 1024 / 1024 / 1024:.2f} GB"
                )

        # Validate subtitle languages
        if 'subtitle_languages' in movie:
            langs = movie['subtitle_languages']
            if not isinstance(langs, list):
                self.errors.append(f"{prefix}: Field 'subtitle_languages' must be array")
            elif len(langs) == 0:
                self.errors.append(f"{prefix}: Field 'subtitle_languages' must have at least one language")
            else:
                for lang in langs:
                    if not isinstance(lang, str):
                        self.errors.append(f"{prefix}: Language code must be string")
                    elif not LANGUAGE_CODE_PATTERN.match(lang):
                        self.warnings.append(
                            f"{prefix}: Language code '{lang}' should be 2-letter ISO 639-1 code"
                        )

        # Optional fields validation
        self._validate_optional_movie_fields(movie, prefix)

    def _validate_optional_movie_fields(self, movie: Dict, prefix: str):
        """Validate optional movie fields"""

        # Validate IMDb ID
        if 'imdb_id' in movie:
            imdb_id = movie['imdb_id']
            if imdb_id and not IMDB_ID_PATTERN.match(imdb_id):
                self.errors.append(
                    f"{prefix}: Invalid IMDb ID format. "
                    f"Must be 'tt' followed by 7-10 digits, got '{imdb_id}'"
                )

        # Validate TMDB ID
        if 'tmdb_id' in movie:
            tmdb_id = movie['tmdb_id']
            if not isinstance(tmdb_id, int) or tmdb_id <= 0:
                self.errors.append(f"{prefix}: Field 'tmdb_id' must be positive integer")

        # Validate runtime
        if 'runtime' in movie:
            runtime = movie['runtime']
            if not isinstance(runtime, int) or runtime <= 0:
                self.errors.append(f"{prefix}: Field 'runtime' must be positive integer")
            elif runtime > 600:
                self.warnings.append(f"{prefix}: Runtime seems very long: {runtime} minutes")

        # Validate video quality
        if 'video_quality' in movie:
            quality = movie['video_quality']
            if quality and quality not in VALID_VIDEO_QUALITIES:
                self.warnings.append(
                    f"{prefix}: Video quality '{quality}' not standard. "
                    f"Expected one of: {VALID_VIDEO_QUALITIES}"
                )

        # Validate poster URL
        if 'poster_url' in movie:
            url = movie['poster_url']
            if url and not (url.startswith('http://') or url.startswith('https://')):
                self.errors.append(f"{prefix}: Poster URL must start with http:// or https://")

    def _validate_series(self):
        """Validate all series"""
        if 'series' not in self.catalog:
            return

        series_list = self.catalog['series']
        print(f"\nValidating {len(series_list)} series...")

        for idx, series in enumerate(series_list):
            self._validate_single_series(series, idx)

    def _validate_single_series(self, series: Dict, index: int):
        """Validate a single series"""
        prefix = f"Series #{index + 1}"

        # Check type
        if not isinstance(series, dict):
            self.errors.append(f"{prefix}: Must be object, got {type(series).__name__}")
            return

        # Required fields
        required = ['id', 'title', 'year', 'genre', 'description', 'seasons']

        for field in required:
            if field not in series:
                self.errors.append(f"{prefix}: Missing required field '{field}'")

        # Validate ID
        if 'id' in series:
            series_id = series['id']
            if not isinstance(series_id, str) or not series_id.strip():
                self.errors.append(f"{prefix}: Field 'id' must be non-empty string")
            else:
                if series_id in self.all_ids:
                    self.errors.append(f"{prefix}: Duplicate ID '{series_id}'")
                self.all_ids.add(series_id)

                if not series_id.startswith('series_'):
                    self.warnings.append(f"{prefix}: ID '{series_id}' should start with 'series_'")

        # Validate title
        if 'title' in series:
            title = series['title']
            if not isinstance(title, str) or not title.strip():
                self.errors.append(f"{prefix}: Field 'title' must be non-empty string")
            elif len(title) > 200:
                self.warnings.append(f"{prefix}: Title is very long ({len(title)} chars)")

        # Validate year
        if 'year' in series:
            year = series['year']
            if not isinstance(year, int):
                self.errors.append(f"{prefix}: Field 'year' must be integer, got {type(year).__name__}")
            elif year < MIN_YEAR or year > datetime.now().year + 2:
                self.errors.append(
                    f"{prefix}: Year {year} out of valid range "
                    f"({MIN_YEAR} to {datetime.now().year + 2})"
                )

        # Validate genre array
        if 'genre' in series:
            genres = series['genre']
            if not isinstance(genres, list):
                self.errors.append(f"{prefix}: Field 'genre' must be array")
            elif len(genres) == 0:
                self.errors.append(f"{prefix}: Field 'genre' must have at least one genre")
            else:
                for genre in genres:
                    if not isinstance(genre, str):
                        self.errors.append(f"{prefix}: Genre must be string, got {type(genre).__name__}")
                    elif genre not in self.all_genres and self.all_genres:
                        self.warnings.append(
                            f"{prefix}: Genre '{genre}' not in catalog genres list"
                        )

        # Validate description
        if 'description' in series:
            desc = series['description']
            if not isinstance(desc, str) or not desc.strip():
                self.errors.append(f"{prefix}: Field 'description' must be non-empty string")
            elif len(desc) > 500:
                self.warnings.append(f"{prefix}: Description is very long ({len(desc)} chars)")
            elif len(desc) < 50:
                self.warnings.append(f"{prefix}: Description is very short ({len(desc)} chars)")

        # Optional fields
        if 'imdb_id' in series:
            imdb_id = series['imdb_id']
            if imdb_id and not IMDB_ID_PATTERN.match(imdb_id):
                self.errors.append(
                    f"{prefix}: Invalid IMDb ID format. "
                    f"Must be 'tt' followed by 7-10 digits, got '{imdb_id}'"
                )

        if 'tmdb_id' in series:
            tmdb_id = series['tmdb_id']
            if not isinstance(tmdb_id, int) or tmdb_id <= 0:
                self.errors.append(f"{prefix}: Field 'tmdb_id' must be positive integer")

        if 'poster_url' in series:
            url = series['poster_url']
            if url and not (url.startswith('http://') or url.startswith('https://')):
                self.errors.append(f"{prefix}: Poster URL must start with http:// or https://")

        # Validate seasons
        if 'seasons' in series:
            seasons = series['seasons']
            if not isinstance(seasons, list):
                self.errors.append(f"{prefix}: Field 'seasons' must be array")
            elif len(seasons) == 0:
                self.errors.append(f"{prefix}: Field 'seasons' must have at least one season")
            else:
                self._validate_seasons(seasons, prefix)

    def _validate_seasons(self, seasons: List[Dict], series_prefix: str):
        """Validate seasons array"""
        season_numbers = set()

        for idx, season in enumerate(seasons):
            prefix = f"{series_prefix}, Season #{idx + 1}"

            if not isinstance(season, dict):
                self.errors.append(f"{prefix}: Must be object, got {type(season).__name__}")
                continue

            # Required fields
            required = ['season_number', 'magnet_link', 'file_size', 'episode_count']
            for field in required:
                if field not in season:
                    self.errors.append(f"{prefix}: Missing required field '{field}'")

            # Validate season number
            if 'season_number' in season:
                num = season['season_number']
                if not isinstance(num, int) or num <= 0:
                    self.errors.append(f"{prefix}: Field 'season_number' must be positive integer")
                else:
                    if num in season_numbers:
                        self.errors.append(f"{prefix}: Duplicate season number {num}")
                    season_numbers.add(num)

            # Validate magnet link
            if 'magnet_link' in season:
                magnet = season['magnet_link']
                if not isinstance(magnet, str):
                    self.errors.append(f"{prefix}: Field 'magnet_link' must be string")
                elif not MAGNET_PATTERN.match(magnet):
                    self.errors.append(f"{prefix}: Invalid magnet link format")

            # Validate file size
            if 'file_size' in season:
                size = season['file_size']
                if not isinstance(size, int) or size <= 0:
                    self.errors.append(f"{prefix}: Field 'file_size' must be positive integer")
                elif size > MAX_FILE_SIZE:
                    self.errors.append(f"{prefix}: File size exceeds maximum")

            # Validate episode count
            if 'episode_count' in season:
                count = season['episode_count']
                if not isinstance(count, int) or count <= 0:
                    self.errors.append(f"{prefix}: Field 'episode_count' must be positive integer")
                elif count > 100:
                    self.warnings.append(f"{prefix}: Episode count seems very high: {count}")

                # Validate episodes array if present
                if 'episodes' in season:
                    episodes = season['episodes']
                    if len(episodes) != count:
                        self.warnings.append(
                            f"{prefix}: Episode count ({count}) doesn't match "
                            f"episodes array length ({len(episodes)})"
                        )

        # Check season numbers are sequential
        if season_numbers:
            expected = set(range(1, max(season_numbers) + 1))
            missing = expected - season_numbers
            if missing:
                self.warnings.append(
                    f"{series_prefix}: Missing season numbers: {sorted(missing)}"
                )

    def _validate_cross_references(self):
        """Validate cross-references between entities"""
        print("\nValidating cross-references...")

        # All genres used should be in genres list
        if self.all_genres:
            movies_genres = set()
            series_genres = set()

            for movie in self.catalog.get('movies', []):
                if 'genre' in movie:
                    movies_genres.update(movie['genre'])

            for series in self.catalog.get('series', []):
                if 'genre' in series:
                    series_genres.update(series['genre'])

            all_used_genres = movies_genres | series_genres
            undefined_genres = all_used_genres - self.all_genres

            if undefined_genres:
                self.warnings.append(
                    f"Genres used but not in genres list: {sorted(undefined_genres)}"
                )

            unused_genres = self.all_genres - all_used_genres
            if unused_genres:
                self.warnings.append(
                    f"Genres defined but not used: {sorted(unused_genres)}"
                )

    def _print_results(self):
        """Print validation results"""
        print("\n" + "=" * 60)
        print("VALIDATION RESULTS")
        print("=" * 60)

        if self.warnings:
            print(f"\n⚠️  {len(self.warnings)} Warning(s):")
            for warning in self.warnings:
                print(f"  - {warning}")

        if self.errors:
            print(f"\n❌ {len(self.errors)} Error(s):")
            for error in self.errors:
                print(f"  - {error}")
        else:
            print("\n✅ No errors found!")

        print("\nSummary:")
        print(f"  Movies: {len(self.catalog.get('movies', []))}")
        print(f"  Series: {len(self.catalog.get('series', []))}")
        total_seasons = sum(
            len(s.get('seasons', [])) for s in self.catalog.get('series', [])
        )
        print(f"  Total Seasons: {total_seasons}")
        print(f"  Genres: {len(self.catalog.get('genres', []))}")
        print(f"  Unique IDs: {len(self.all_ids)}")

        print("\n" + "=" * 60)


def main():
    """Main entry point"""
    if len(sys.argv) > 1:
        catalog_path = sys.argv[1]
    else:
        catalog_path = "catalog.json"

    validator = CatalogValidator(catalog_path)
    is_valid = validator.validate()

    sys.exit(0 if is_valid else 1)


if __name__ == "__main__":
    main()
