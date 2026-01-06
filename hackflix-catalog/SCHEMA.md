# Catalog Schema Documentation

**Version**: 1.0.0
**Last Updated**: 2025-01-06

## Overview

The catalog schema defines the structure for `catalog.json`, which contains metadata for all movies and series available in the HackFlix catalog. The catalog is hosted on GitHub Pages and synced to the client's local SQLite database.

## Root Structure

```json
{
  "version": "1.0.0",
  "last_updated": "2025-01-06T12:00:00Z",
  "movies": [...],
  "series": [...],
  "genres": [...]
}
```

### Root Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `version` | string | Yes | Schema version (semantic versioning) |
| `last_updated` | string | Yes | ISO 8601 timestamp of last catalog update |
| `movies` | array | Yes | Array of movie objects |
| `series` | array | Yes | Array of series objects |
| `genres` | array | Yes | List of available genres for filtering |

## Movie Object Schema

```json
{
  "id": "movie_001",
  "title": "Inception",
  "year": 2010,
  "genre": ["Action", "Sci-Fi", "Thriller"],
  "description": "A thief who steals corporate secrets through dream-sharing technology is given the inverse task of planting an idea.",
  "magnet_link": "magnet:?xt=urn:btih:...",
  "file_size": 2147483648,
  "subtitle_languages": ["en"],
  "poster_url": "https://image.tmdb.org/t/p/w500/...",
  "imdb_id": "tt1375666",
  "tmdb_id": 27205,
  "runtime": 148,
  "video_quality": "1080p",
  "video_codec": "H.264",
  "audio_codec": "AAC"
}
```

### Movie Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Unique identifier (format: `movie_XXX`) |
| `title` | string | Yes | Movie title (original or localized) |
| `year` | integer | Yes | Release year (4 digits) |
| `genre` | array[string] | Yes | List of genres (at least 1) |
| `description` | string | Yes | Plot summary (1-3 sentences, 100-300 chars) |
| `magnet_link` | string | Yes | BitTorrent magnet URI (must start with `magnet:?xt=`) |
| `file_size` | integer | Yes | File size in bytes |
| `subtitle_languages` | array[string] | Yes | Available subtitle language codes (ISO 639-1) |
| `poster_url` | string | No | URL to movie poster image (prefer TMDB/IMDb) |
| `imdb_id` | string | No | IMDb identifier (format: `ttXXXXXXX`) |
| `tmdb_id` | integer | No | The Movie Database ID |
| `runtime` | integer | No | Runtime in minutes |
| `video_quality` | string | No | Resolution indicator (e.g., `720p`, `1080p`, `2160p`) |
| `video_codec` | string | No | Video codec (e.g., `H.264`, `H.265`, `VP9`) |
| `audio_codec` | string | No | Audio codec (e.g., `AAC`, `AC3`, `DTS`) |

### Movie ID Format

Movie IDs should follow the pattern `movie_{tmdb_id}` or `movie_{sequential_number}` with zero-padding to 3-4 digits.

**Examples**:
- `movie_27205` (using TMDB ID)
- `movie_001`, `movie_002`, etc. (sequential)

## Series Object Schema

```json
{
  "id": "series_001",
  "title": "Breaking Bad",
  "year": 2008,
  "genre": ["Crime", "Drama", "Thriller"],
  "description": "A chemistry teacher diagnosed with cancer turns to manufacturing meth to secure his family's future.",
  "poster_url": "https://image.tmdb.org/t/p/w500/...",
  "imdb_id": "tt0903747",
  "tmdb_id": 1396,
  "seasons": [
    {
      "season_number": 1,
      "magnet_link": "magnet:?xt=urn:btih:...",
      "file_size": 5368709120,
      "episode_count": 7,
      "year": 2008,
      "video_quality": "1080p",
      "episodes": [
        {
          "episode_number": 1,
          "title": "Pilot",
          "runtime": 58
        }
      ]
    }
  ]
}
```

### Series Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Unique identifier (format: `series_XXX`) |
| `title` | string | Yes | Series title (original or localized) |
| `year` | integer | Yes | First air year (4 digits) |
| `genre` | array[string] | Yes | List of genres (at least 1) |
| `description` | string | Yes | Series summary (1-3 sentences, 100-300 chars) |
| `seasons` | array[object] | Yes | Array of season objects (at least 1) |
| `poster_url` | string | No | URL to series poster image |
| `imdb_id` | string | No | IMDb identifier (format: `ttXXXXXXX`) |
| `tmdb_id` | integer | No | The Movie Database ID |

### Season Object Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `season_number` | integer | Yes | Season number (1-indexed) |
| `magnet_link` | string | Yes | BitTorrent magnet URI for complete season |
| `file_size` | integer | Yes | Total season file size in bytes |
| `episode_count` | integer | Yes | Number of episodes in season |
| `year` | integer | No | Air year for this season |
| `video_quality` | string | No | Resolution indicator |
| `episodes` | array[object] | No | Episode metadata for UI display |

### Episode Object Fields (Optional)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `episode_number` | integer | Yes | Episode number within season |
| `title` | string | No | Episode title |
| `runtime` | integer | No | Episode runtime in minutes |

### Series ID Format

Series IDs should follow the pattern `series_{tmdb_id}` or `series_{sequential_number}`.

**Examples**:
- `series_1396` (using TMDB ID)
- `series_001`, `series_002`, etc. (sequential)

## Genre List

The `genres` array defines all available genres for filtering. This should match the genres used in movie and series objects.

**Standard Genres**:
```json
[
  "Action",
  "Adventure",
  "Animation",
  "Comedy",
  "Crime",
  "Documentary",
  "Drama",
  "Family",
  "Fantasy",
  "History",
  "Horror",
  "Music",
  "Mystery",
  "Romance",
  "Sci-Fi",
  "Thriller",
  "War",
  "Western"
]
```

## Validation Rules

### Required Field Validation

1. All required fields must be present
2. Required fields cannot be `null` or empty strings
3. Arrays marked as required must have at least one element

### Type Validation

1. **Strings**: Non-empty, trimmed
2. **Integers**: Positive numbers (except for year which must be >= 1900)
3. **Arrays**: Must be valid JSON arrays
4. **URLs**: Must be valid HTTP/HTTPS URLs
5. **Magnet Links**: Must start with `magnet:?xt=urn:btih:`

### Format Validation

1. **ISO 8601 Timestamps**: `YYYY-MM-DDTHH:MM:SSZ`
2. **IMDb IDs**: `tt` followed by 7-10 digits
3. **Language Codes**: 2-letter ISO 639-1 codes (e.g., `en`, `pl`)
4. **Version**: Semantic versioning format (e.g., `1.0.0`)

### Business Logic Validation

1. **Unique IDs**: All movie and series IDs must be unique across the entire catalog
2. **Genre Consistency**: All genres used in movies/series must exist in the `genres` array
3. **File Size**: Must be > 0 and < 100GB (sanity check)
4. **Year**: Must be between 1900 and current year + 2
5. **Season Numbers**: Must be sequential starting from 1
6. **Episode Count**: Must match number of episodes in `episodes` array (if provided)

### Magnet Link Validation

Valid magnet link format:
```
magnet:?xt=urn:btih:[40-character hex hash]&dn=[name]&tr=[tracker]
```

Minimum required: `magnet:?xt=urn:btih:` followed by a 40-character hexadecimal hash.

## Size Limits

| Field | Maximum Size |
|-------|--------------|
| `title` | 200 characters |
| `description` | 500 characters |
| `magnet_link` | 2000 characters |
| `poster_url` | 500 characters |
| Total catalog file | 10 MB (recommended) |
| Movies array | 1000 items (recommended) |
| Series array | 500 items (recommended) |

## Update Strategy

### Incrementing `last_updated`

The `last_updated` timestamp should be updated whenever:
- New movies or series are added
- Existing metadata is modified (title, description, etc.)
- Magnet links are updated
- Items are removed from the catalog

### Best Practices

1. **Always validate** before committing changes to catalog.json
2. **Update timestamp** using ISO 8601 format in UTC timezone
3. **Increment version** when schema structure changes (not for content updates)
4. **Test magnet links** before adding to ensure seeders are available
5. **Use consistent IDs** - prefer TMDB IDs when available
6. **Keep descriptions concise** - 1-3 sentences maximum
7. **Verify file sizes** - approximate is fine, but should be reasonably accurate

## Migration Guidelines

### Version 1.0.0 → Future Versions

When the schema needs to change:

1. Increment the `version` field appropriately:
   - **Major**: Breaking changes (remove required fields, change types)
   - **Minor**: Non-breaking additions (new optional fields)
   - **Patch**: Documentation/clarification only

2. Update this documentation

3. Update validation script to support new schema

4. Consider backward compatibility - clients may have old schema

5. Provide migration guide for existing catalogs

## Examples

See `catalog.json` in the repository root for a complete working example with:
- Multiple movies across different genres
- Series with multiple seasons
- Proper field formatting
- Valid magnet links (example format)

## Tools

- **Validation**: Run `python scripts/validate_catalog.py` to validate catalog.json
- **Update Timestamp**: Run `python scripts/update_catalog.py` to auto-update `last_updated`
- **Metadata Fetcher**: Use `scripts/fetch_metadata.py` to fetch movie/series metadata from TMDB

## References

- **ISO 8601**: https://en.wikipedia.org/wiki/ISO_8601
- **ISO 639-1**: https://en.wikipedia.org/wiki/List_of_ISO_639-1_codes
- **TMDB API**: https://developers.themoviedb.org/3
- **IMDb Datasets**: https://www.imdb.com/interfaces/
- **Magnet URI Scheme**: https://en.wikipedia.org/wiki/Magnet_URI_scheme
