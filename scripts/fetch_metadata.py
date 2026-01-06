#!/usr/bin/env python3
"""
Fetch movie and series metadata from TMDB API

This script helps gather metadata for catalog entries from The Movie Database (TMDB).
Requires a TMDB API key (free registration at https://www.themoviedb.org/settings/api)

Usage:
    python scripts/fetch_metadata.py --movie TMDB_ID
    python scripts/fetch_metadata.py --series TMDB_ID
    python scripts/fetch_metadata.py --search "Movie Title"
"""

import os
import sys
import json
import argparse
import requests
from typing import Dict, Optional, List
from datetime import datetime


# TMDB API Configuration
TMDB_API_KEY = os.getenv("TMDB_API_KEY", "")
TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w500"

# Genre mappings (TMDB genre IDs to names)
TMDB_GENRES = {
    28: "Action",
    12: "Adventure",
    16: "Animation",
    35: "Comedy",
    80: "Crime",
    99: "Documentary",
    18: "Drama",
    10751: "Family",
    14: "Fantasy",
    36: "History",
    27: "Horror",
    10402: "Music",
    9648: "Mystery",
    10749: "Romance",
    878: "Sci-Fi",
    10770: "TV Movie",
    53: "Thriller",
    10752: "War",
    37: "Western"
}


def check_api_key():
    """Check if TMDB API key is configured"""
    if not TMDB_API_KEY:
        print("❌ Error: TMDB_API_KEY environment variable not set")
        print("\nTo get an API key:")
        print("1. Register at https://www.themoviedb.org/signup")
        print("2. Go to Settings → API")
        print("3. Request an API key (free)")
        print("4. Set environment variable:")
        print("   export TMDB_API_KEY='your_api_key_here'")
        print("   Or add to .env file: TMDB_API_KEY=your_api_key_here")
        sys.exit(1)


def fetch_movie_metadata(tmdb_id: int) -> Optional[Dict]:
    """
    Fetch movie metadata from TMDB

    Args:
        tmdb_id: TMDB movie ID

    Returns:
        Dictionary with catalog-formatted movie data
    """
    url = f"{TMDB_BASE_URL}/movie/{tmdb_id}"
    params = {"api_key": TMDB_API_KEY}

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        # Convert TMDB data to catalog format
        movie = {
            "id": f"movie_{tmdb_id}",
            "title": data["title"],
            "year": int(data["release_date"][:4]) if data.get("release_date") else None,
            "genre": [TMDB_GENRES.get(g["id"], g["name"]) for g in data.get("genres", [])],
            "description": data["overview"][:300] if len(data.get("overview", "")) > 300 else data.get("overview", ""),
            "magnet_link": "magnet:?xt=urn:btih:REPLACE_WITH_ACTUAL_HASH",
            "file_size": 0,  # Fill in manually
            "subtitle_languages": ["en"],
            "poster_url": f"{TMDB_IMAGE_BASE}{data['poster_path']}" if data.get("poster_path") else None,
            "imdb_id": data.get("imdb_id"),
            "tmdb_id": tmdb_id,
            "runtime": data.get("runtime"),
            "video_quality": "1080p",  # Default, adjust as needed
            "video_codec": "H.264",
            "audio_codec": "AAC"
        }

        return movie

    except requests.RequestException as e:
        print(f"❌ Error fetching movie {tmdb_id}: {e}")
        return None


def fetch_series_metadata(tmdb_id: int, seasons: Optional[List[int]] = None) -> Optional[Dict]:
    """
    Fetch TV series metadata from TMDB

    Args:
        tmdb_id: TMDB TV series ID
        seasons: List of season numbers to include (if None, includes all)

    Returns:
        Dictionary with catalog-formatted series data
    """
    url = f"{TMDB_BASE_URL}/tv/{tmdb_id}"
    params = {"api_key": TMDB_API_KEY}

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        # Get external IDs for IMDb
        external_url = f"{TMDB_BASE_URL}/tv/{tmdb_id}/external_ids"
        external_response = requests.get(external_url, params=params, timeout=10)
        external_data = external_response.json()

        # Convert TMDB data to catalog format
        series = {
            "id": f"series_{tmdb_id}",
            "title": data["name"],
            "year": int(data["first_air_date"][:4]) if data.get("first_air_date") else None,
            "genre": [TMDB_GENRES.get(g["id"], g["name"]) for g in data.get("genres", [])],
            "description": data["overview"][:300] if len(data.get("overview", "")) > 300 else data.get("overview", ""),
            "poster_url": f"{TMDB_IMAGE_BASE}{data['poster_path']}" if data.get("poster_path") else None,
            "imdb_id": external_data.get("imdb_id"),
            "tmdb_id": tmdb_id,
            "seasons": []
        }

        # Get season information
        all_seasons = data.get("seasons", [])
        for season_data in all_seasons:
            season_num = season_data["season_number"]

            # Skip season 0 (specials) unless explicitly requested
            if season_num == 0 and (seasons is None or 0 not in seasons):
                continue

            # If specific seasons requested, only include those
            if seasons is not None and season_num not in seasons:
                continue

            season_info = {
                "season_number": season_num,
                "magnet_link": "magnet:?xt=urn:btih:REPLACE_WITH_ACTUAL_HASH",
                "file_size": 0,  # Fill in manually
                "episode_count": season_data.get("episode_count", 0),
                "year": int(season_data["air_date"][:4]) if season_data.get("air_date") else None,
                "video_quality": "1080p"
            }

            series["seasons"].append(season_info)

        return series

    except requests.RequestException as e:
        print(f"❌ Error fetching series {tmdb_id}: {e}")
        return None


def search_content(query: str, content_type: str = "multi") -> List[Dict]:
    """
    Search for movies or TV series

    Args:
        query: Search query string
        content_type: 'movie', 'tv', or 'multi'

    Returns:
        List of search results
    """
    url = f"{TMDB_BASE_URL}/search/{content_type}"
    params = {
        "api_key": TMDB_API_KEY,
        "query": query,
        "language": "en-US",
        "page": 1
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        results = []
        for item in data.get("results", [])[:10]:  # Limit to top 10 results
            media_type = item.get("media_type", content_type)

            if media_type == "movie":
                result = {
                    "type": "movie",
                    "tmdb_id": item["id"],
                    "title": item["title"],
                    "year": item.get("release_date", "")[:4] if item.get("release_date") else "N/A",
                    "overview": item.get("overview", "")[:100] + "..."
                }
            elif media_type == "tv":
                result = {
                    "type": "series",
                    "tmdb_id": item["id"],
                    "title": item["name"],
                    "year": item.get("first_air_date", "")[:4] if item.get("first_air_date") else "N/A",
                    "overview": item.get("overview", "")[:100] + "..."
                }
            else:
                continue

            results.append(result)

        return results

    except requests.RequestException as e:
        print(f"❌ Error searching for '{query}': {e}")
        return []


def print_json(data: Dict, indent: int = 2):
    """Pretty print JSON data"""
    print(json.dumps(data, indent=indent, ensure_ascii=False))


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Fetch movie/series metadata from TMDB",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Fetch movie by TMDB ID
  python scripts/fetch_metadata.py --movie 27205

  # Fetch series by TMDB ID (all seasons)
  python scripts/fetch_metadata.py --series 1396

  # Fetch specific seasons only
  python scripts/fetch_metadata.py --series 1396 --seasons 1 2 3

  # Search for content
  python scripts/fetch_metadata.py --search "Inception"
  python scripts/fetch_metadata.py --search "Breaking Bad" --type tv

  # Output to file
  python scripts/fetch_metadata.py --movie 27205 > movie.json
        """
    )

    parser.add_argument("--movie", type=int, metavar="TMDB_ID",
                       help="Fetch movie metadata by TMDB ID")
    parser.add_argument("--series", type=int, metavar="TMDB_ID",
                       help="Fetch TV series metadata by TMDB ID")
    parser.add_argument("--seasons", type=int, nargs='+', metavar="N",
                       help="Specific season numbers to include (for series)")
    parser.add_argument("--search", type=str, metavar="QUERY",
                       help="Search for movies or TV series")
    parser.add_argument("--type", choices=['movie', 'tv', 'multi'], default='multi',
                       help="Content type for search (default: multi)")
    parser.add_argument("--no-check", action="store_true",
                       help="Skip API key validation (for testing)")

    args = parser.parse_args()

    # Check API key unless --no-check
    if not args.no_check:
        check_api_key()

    # Execute requested action
    if args.movie:
        print(f"📽️  Fetching movie metadata (TMDB ID: {args.movie})...\n")
        metadata = fetch_movie_metadata(args.movie)
        if metadata:
            print("✅ Movie metadata retrieved:\n")
            print_json(metadata)
            print("\n⚠️  Note: Replace 'magnet_link' and 'file_size' with actual values")

    elif args.series:
        print(f"📺 Fetching series metadata (TMDB ID: {args.series})...\n")
        metadata = fetch_series_metadata(args.series, args.seasons)
        if metadata:
            print("✅ Series metadata retrieved:\n")
            print_json(metadata)
            print("\n⚠️  Note: Replace 'magnet_link' and 'file_size' with actual values for each season")

    elif args.search:
        print(f"🔍 Searching for: {args.search}\n")
        results = search_content(args.search, args.type)

        if results:
            print(f"Found {len(results)} result(s):\n")
            for i, result in enumerate(results, 1):
                print(f"{i}. [{result['type'].upper()}] {result['title']} ({result['year']})")
                print(f"   TMDB ID: {result['tmdb_id']}")
                print(f"   {result['overview']}\n")

            print("💡 Use --movie or --series with TMDB ID to fetch full metadata")
        else:
            print("No results found")

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
