# Catalog Curation Guide

Guide for building and maintaining the HackFlix catalog with high-quality content.

## Overview

The HackFlix catalog is a curated collection of movies and series chosen for:
- High quality (prefer 1080p)
- Strong ratings (IMDb 7.5+, personal favorites)
- Reliable availability (active torrents with seeders)
- Subtitle availability (English subtitles for translation)

## Current Catalog Status

**Deployment**: https://wiktor-jedski.github.io/hackflix-catalog/catalog.json

**Current Content**:
- 5 Movies: Inception, The Shawshank Redemption, The Matrix, Interstellar, The Dark Knight
- 3 Series: Breaking Bad (S1-2), Game of Thrones (S1), Stranger Things (S1)
- All entries have complete metadata from TMDB
- Magnet links are placeholders (need real torrents)

## Adding Content Workflow

### Step 1: Select Content

Choose movies or series based on:

**Quality Criteria**:
- IMDb rating 7.5+ or personal favorite
- Available in 1080p with good encoding
- English audio available
- Active torrents (5+ seeders)
- English subtitles available on OpenSubtitles

**Content Mix**:
- Variety of genres
- Mix of classic and recent titles
- Balance movies vs series
- Consider Polish audience preferences

### Step 2: Fetch Metadata from TMDB

Use the metadata collection script:

```bash
# Search for content
python scripts/fetch_metadata.py --search "Movie Title"

# Get movie metadata
python scripts/fetch_metadata.py --movie TMDB_ID

# Get series metadata (specific seasons)
python scripts/fetch_metadata.py --series TMDB_ID --seasons 1 2

# Save to file
python scripts/fetch_metadata.py --movie 27205 > temp_movie.json
```

**Requirements**:
1. Get free TMDB API key from https://www.themoviedb.org/settings/api
2. Set environment variable: `export TMDB_API_KEY='your_key'`
3. Or add to `.env`: `TMDB_API_KEY=your_key`

### Step 3: Find Magnet Links

**Recommended Torrent Sites**:
- 1337x.to
- RARBG alternatives
- YTS (for movies, smaller files)
- EZTV (for series)

**Quality Checks**:
1. Verify seeders count (minimum 5, prefer 20+)
2. Check file size (movies: 1-4 GB, season: 3-10 GB)
3. Confirm quality (1080p BluRay or WEB-DL)
4. Test download briefly to verify it works
5. Copy full magnet URI

**Magnet Link Format**:
```
magnet:?xt=urn:btih:[40-char-hex-hash]&dn=[file-name]&tr=[tracker-url]
```

### Step 4: Add to Catalog

Edit `catalog.json` or `hackflix-catalog/catalog.json`:

```bash
# Open catalog
vim catalog.json

# Add your entry to movies[] or series[] array
# Use metadata from Step 2
# Replace magnet_link with real magnet from Step 3
# Set file_size (in bytes)

# Validate
python scripts/validate_catalog.py catalog.json

# Update timestamp
python scripts/update_timestamp.py catalog.json
```

### Step 5: Commit and Deploy

```bash
# For main repository
git add catalog.json
git commit -m "Add: Movie/Series Name (Year)"
git push

# For hackflix-catalog repository
cd hackflix-catalog
git add catalog.json
git commit -m "Add: Movie/Series Name (Year)"
git push

# Wait 2-5 minutes for GitHub Pages deployment
```

## Metadata Collection Examples

### Example 1: Adding a Movie

```bash
# 1. Search for the movie
$ python scripts/fetch_metadata.py --search "The Godfather"

Found 5 result(s):
1. [MOVIE] The Godfather (1972)
   TMDB ID: 238
   Don Vito Corleone, head of a mafia family, decides to hand over his empire to his youngest son...

# 2. Fetch full metadata
$ python scripts/fetch_metadata.py --movie 238

📽️  Fetching movie metadata (TMDB ID: 238)...

✅ Movie metadata retrieved:

{
  "id": "movie_238",
  "title": "The Godfather",
  "year": 1972,
  "genre": ["Drama", "Crime"],
  "description": "Spanning the years 1945 to 1955, a chronicle of the fictional Italian-American Corleone crime family...",
  "magnet_link": "magnet:?xt=urn:btih:REPLACE_WITH_ACTUAL_HASH",
  "file_size": 0,
  "subtitle_languages": ["en"],
  "poster_url": "https://image.tmdb.org/t/p/w500/3bhkrj58Vtu7enYsRolD1fZdja1.jpg",
  "imdb_id": "tt0068646",
  "tmdb_id": 238,
  "runtime": 175,
  "video_quality": "1080p",
  "video_codec": "H.264",
  "audio_codec": "AAC"
}

# 3. Find magnet link (from torrent site)
# Example: magnet:?xt=urn:btih:abc123...

# 4. Edit catalog.json, paste the above JSON, update magnet_link and file_size

# 5. Validate and commit
$ python scripts/validate_catalog.py catalog.json
$ python scripts/update_timestamp.py catalog.json
$ git add catalog.json
$ git commit -m "Add: The Godfather (1972)"
```

### Example 2: Adding a Series

```bash
# 1. Search for series
$ python scripts/fetch_metadata.py --search "The Wire" --type tv

Found 3 result(s):
1. [SERIES] The Wire (2002)
   TMDB ID: 1438
   Told from the points of view of both the Baltimore homicide and narcotics detectives...

# 2. Fetch metadata for specific seasons
$ python scripts/fetch_metadata.py --series 1438 --seasons 1

📺 Fetching series metadata (TMDB ID: 1438)...

✅ Series metadata retrieved:

{
  "id": "series_1438",
  "title": "The Wire",
  "year": 2002,
  "genre": ["Crime", "Drama"],
  "description": "Told from the points of view of both the Baltimore homicide and narcotics detectives...",
  "poster_url": "https://image.tmdb.org/t/p/w500/4lbclFySvugI51fwsyxBTOm4DqK.jpg",
  "imdb_id": "tt0306414",
  "tmdb_id": 1438,
  "seasons": [
    {
      "season_number": 1,
      "magnet_link": "magnet:?xt=urn:btih:REPLACE_WITH_ACTUAL_HASH",
      "file_size": 0,
      "episode_count": 13,
      "year": 2002,
      "video_quality": "1080p"
    }
  ]
}

# 3-5. Same as movie example
```

## File Size Guidelines

### Movies

| Quality | Resolution | Typical Size Range |
|---------|-----------|-------------------|
| 720p    | 1280×720  | 800 MB - 2 GB     |
| 1080p   | 1920×1080 | 1.5 GB - 4 GB     |
| 4K      | 3840×2160 | 8 GB - 20 GB      |

**Recommended**: 1080p, 2-3 GB (good quality/size balance)

### TV Series (Per Season)

| Episodes | Quality | Typical Size Range |
|----------|---------|-------------------|
| 6-8 eps  | 1080p   | 3-6 GB            |
| 10-13 eps| 1080p   | 5-10 GB           |
| 20+ eps  | 1080p   | 10-15 GB          |

**Note**: Prefer complete season packs over individual episodes

## Content Selection Strategy

### Phase 1: Core Catalog (Current - 10 titles)

**Goal**: Establish baseline with highly-rated classics

**Selection**:
- Mix of genres (action, drama, sci-fi, crime)
- IMDb Top 250 movies
- Critically acclaimed series
- Personal favorites

**Current Status**: ✅ Complete
- 5 movies across genres
- 3 series (different types: crime drama, fantasy, mystery)

### Phase 2: Expand to 25-50 Titles

**Goal**: Broader variety, more recent content

**Add**:
- Recent releases (2020-2024)
- More genre diversity (comedy, horror, romance)
- International favorites
- Cult classics

### Phase 3: Mature Catalog (50-200 Titles)

**Goal**: Comprehensive library

**Add**:
- Complete series (all seasons)
- Director-focused collections
- Franchise completions
- Hidden gems

## Quality Control Checklist

Before adding content to catalog:

- [ ] TMDB metadata fetched and verified
- [ ] IMDb rating checked (7.5+ or personal favorite)
- [ ] Magnet link tested (has seeders)
- [ ] File size appropriate for quality
- [ ] English audio confirmed
- [ ] English subtitles available on OpenSubtitles
- [ ] Proper ID format (movie_XXX or series_XXX)
- [ ] Description concise (100-300 chars)
- [ ] Poster URL working
- [ ] Validation script passes
- [ ] Timestamp updated

## Maintenance Tasks

### Weekly

- Check for dead magnet links
- Test random catalog entries
- Monitor GitHub Actions for validation failures

### Monthly

- Review catalog statistics
- Add 2-5 new high-quality titles
- Update any broken magnet links
- Check for TMDB metadata updates

### Quarterly

- Comprehensive magnet link audit
- Remove content with no seeders
- Update file sizes if significantly different
- Review and update documentation

## Troubleshooting

### Issue: TMDB API Rate Limiting

**Solution**:
- Free tier: 40 requests per 10 seconds
- Space out requests or implement delay
- Consider caching TMDB responses

### Issue: Can't Find Good Magnet Links

**Solution**:
1. Try multiple torrent sites
2. Look for "trusted uploader" badges
3. Check comments for feedback
4. Consider older but still-seeded releases
5. Use YTS for movies (smaller but good quality)

### Issue: Subtitle Not Available

**Solution**:
1. Check OpenSubtitles.org directly
2. Try Subscene or other subtitle sites
3. Consider if content is worth adding without subs
4. For series, check if at least S01 has subs

### Issue: File Size Too Large

**Solution**:
1. Look for x264 instead of x265 (smaller)
2. Accept 720p instead of 1080p
3. Find WEB-DL instead of BluRay
4. Check for "YIFY" or "RARBG" releases (optimized)

## Best Practices

### DO

✅ Verify magnet links before adding
✅ Use official TMDB metadata
✅ Keep descriptions concise
✅ Test downloads briefly
✅ Validate before committing
✅ Update timestamp on changes
✅ Document changes in commit messages

### DON'T

❌ Add content without testing magnet
❌ Use unofficial or scraped metadata
❌ Include dead/low-seeded torrents
❌ Add adult/NSFW content
❌ Skip validation step
❌ Forget to update timestamp
❌ Make bulk changes without testing

## Resources

### APIs and Tools

- **TMDB API**: https://www.themoviedb.org/settings/api
- **OMDb API**: http://www.omdbapi.com/ (alternative)
- **IMDb Datasets**: https://www.imdb.com/interfaces/
- **OpenSubtitles API**: https://www.opensubtitles.com/api

### Torrent Resources

- **TorrentGalaxy**: https://torrentgalaxy.to
- **RARBG Mirrors**: Search for current mirrors
- **YTS**: https://yts.mx (movies only, small sizes)
- **EZTV**: https://eztv.re (TV series)

### Quality References

- **IMDb Top 250**: https://www.imdb.com/chart/top
- **TMDB Popular**: https://www.themoviedb.org/movie
- **Rotten Tomatoes**: https://www.rottentomatoes.com
- **Metacritic**: https://www.metacritic.com

## Example Catalog Entry (Complete)

**The Dark Knight (2008)**:

```json
{
  "id": "movie_155",
  "title": "The Dark Knight",
  "year": 2008,
  "genre": ["Action", "Crime", "Drama"],
  "description": "When the menace known as the Joker wreaks havoc and chaos on the people of Gotham, Batman must accept one of the greatest psychological and physical tests.",
  "magnet_link": "magnet:?xt=urn:btih:0123456789abcdef0123456789abcdef01234567&dn=The.Dark.Knight.2008.1080p&tr=...",
  "file_size": 2684354560,
  "subtitle_languages": ["en"],
  "poster_url": "https://image.tmdb.org/t/p/w500/qJ2tW6WMUDux911r6m7haRef0WH.jpg",
  "imdb_id": "tt0468569",
  "tmdb_id": 155,
  "runtime": 152,
  "video_quality": "1080p",
  "video_codec": "H.264",
  "audio_codec": "AC3"
}
```

**Verified**:
- ✅ Metadata from TMDB (ID: 155)
- ✅ IMDb 9.0/10 rating
- ✅ Magnet link tested (50+ seeders)
- ✅ File size: 2.5 GB (reasonable for 152 min 1080p)
- ✅ English subs available
- ✅ Validation passes

---

**Happy Curating!** 🎬
