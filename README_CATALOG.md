# HackFlix Catalog

This directory contains the catalog.json file and related tools for managing the HackFlix movie and series catalog.

## Files

- **catalog.json** - Main catalog file containing movie and series metadata
- **docs/catalog_schema.md** - Complete schema documentation
- **scripts/validate_catalog.py** - Validation script to check catalog integrity

## Quick Start

### Validating the Catalog

Before committing changes to catalog.json, always validate:

```bash
python scripts/validate_catalog.py catalog.json
```

The script will check:
- JSON syntax
- Required fields
- Data types and formats
- Magnet link validity
- Unique IDs
- Genre consistency
- And more...

### Adding a New Movie

1. Fetch metadata from TMDB/IMDb
2. Find a reliable magnet link with seeders
3. Add movie object to the `movies` array in catalog.json
4. Update `last_updated` timestamp to current time (ISO 8601 UTC)
5. Run validation: `python scripts/validate_catalog.py catalog.json`
6. Commit changes

**Example movie entry:**
```json
{
  "id": "movie_001",
  "title": "Movie Title",
  "year": 2024,
  "genre": ["Action", "Drama"],
  "description": "Brief plot summary in 1-3 sentences.",
  "magnet_link": "magnet:?xt=urn:btih:HASH...",
  "file_size": 2147483648,
  "subtitle_languages": ["en"],
  "poster_url": "https://image.tmdb.org/t/p/w500/...",
  "imdb_id": "tt1234567",
  "tmdb_id": 12345,
  "runtime": 120,
  "video_quality": "1080p"
}
```

### Adding a New Series

1. Fetch metadata from TMDB/IMDb
2. Find magnet links for each season (full season torrents)
3. Add series object to the `series` array in catalog.json
4. Update `last_updated` timestamp
5. Run validation
6. Commit changes

**Example series entry:**
```json
{
  "id": "series_001",
  "title": "Series Title",
  "year": 2020,
  "genre": ["Drama"],
  "description": "Brief series summary.",
  "imdb_id": "tt7654321",
  "tmdb_id": 54321,
  "seasons": [
    {
      "season_number": 1,
      "magnet_link": "magnet:?xt=urn:btih:HASH...",
      "file_size": 5368709120,
      "episode_count": 10,
      "year": 2020,
      "video_quality": "1080p"
    }
  ]
}
```

## Schema Documentation

See **docs/catalog_schema.md** for complete documentation of all fields, validation rules, and best practices.

## Validation Rules

### Required Fields

**Movies:**
- id, title, year, genre, description
- magnet_link, file_size, subtitle_languages

**Series:**
- id, title, year, genre, description, seasons

**Seasons:**
- season_number, magnet_link, file_size, episode_count

### Format Requirements

- **IDs**: Unique across catalog, prefer `movie_XXX` or `series_XXX` format
- **Timestamps**: ISO 8601 format (`YYYY-MM-DDTHH:MM:SSZ`)
- **Magnet Links**: Must start with `magnet:?xt=urn:btih:` + 40-char hex hash
- **IMDb IDs**: `tt` followed by 7-10 digits
- **Years**: Between 1900 and current year + 2
- **File Sizes**: In bytes, between 1MB and 100GB

## Maintenance

### Updating last_updated Timestamp

The `last_updated` field should be updated whenever the catalog changes:

```bash
# Manual update
# Edit catalog.json and change:
"last_updated": "2025-01-06T12:00:00Z"
# To current UTC time in ISO 8601 format
```

### Checking for Dead Magnet Links

Periodically verify that magnet links still have seeders:
1. Try downloading a small portion with a BitTorrent client
2. Check for peer availability
3. Update or remove entries with no seeders

### Genre Management

All genres used in movies/series should be listed in the `genres` array at the root level. The validation script will warn about:
- Genres used but not in the list
- Genres defined but never used

## Example Catalog

The included **catalog.json** contains example entries for:
- 5 movies (Inception, The Shawshank Redemption, The Matrix, Interstellar, The Dark Knight)
- 3 series (Breaking Bad, Game of Thrones, Stranger Things)

**Note:** Magnet links in the example are placeholders with example format. Replace with real magnet links for actual use.

## Hosting

The catalog.json file is designed to be hosted on GitHub Pages or any static file server:

1. Create GitHub repository for catalog
2. Enable GitHub Pages in repository settings
3. Upload catalog.json
4. Access via: `https://username.github.io/repo-name/catalog.json`
5. Configure client to fetch from this URL

## Development

### Testing Changes Locally

1. Edit catalog.json
2. Run validation: `python scripts/validate_catalog.py catalog.json`
3. Fix any errors or warnings
4. Test with client app (run catalog sync)
5. Commit when validated

### Best Practices

- Always validate before committing
- Keep descriptions concise (100-300 characters)
- Use TMDB/IMDb IDs when available
- Prefer high-quality sources (1080p)
- Test magnet links before adding
- Update timestamp on every change
- Commit with descriptive messages

## Troubleshooting

### Validation Fails

1. Check error messages from validation script
2. Verify JSON syntax (use online JSON validator if needed)
3. Check for missing required fields
4. Verify data types (strings vs integers)
5. Check magnet link format

### Magnet Link Not Working

1. Verify hash is 40 hexadecimal characters
2. Check that link starts with `magnet:?xt=urn:btih:`
3. Test link in BitTorrent client
4. Find alternative source with more seeders

### File Size Unknown

Use rough estimates based on:
- 720p movie: ~1-2 GB
- 1080p movie: ~2-4 GB
- 1080p series season (10 episodes): ~5-10 GB

Or check torrent client for actual size before adding.

## Contributing

When contributing to the catalog:

1. Fork the repository
2. Add or update entries
3. Run validation script
4. Submit pull request with:
   - Description of changes
   - Validation output (must pass)
   - Source of metadata (TMDB, IMDb, etc.)
   - Verification that magnet links work

## License

See main project LICENSE file.
