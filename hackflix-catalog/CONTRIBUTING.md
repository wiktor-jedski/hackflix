# Contributing to HackFlix Catalog

Thank you for your interest in contributing to the HackFlix catalog! This document provides guidelines for adding and updating catalog entries.

## How to Contribute

### Prerequisites

1. GitHub account
2. Git installed locally
3. Python 3.7+ (for validation)
4. Basic understanding of JSON format

### Quick Start

1. **Fork** the repository
2. **Clone** your fork locally
3. **Edit** catalog.json
4. **Validate** your changes
5. **Commit** with descriptive message
6. **Push** to your fork
7. **Create** a pull request

## Adding a Movie

### Step 1: Gather Metadata

Use TMDB or IMDb to find:
- Official title
- Release year
- Genres
- Plot summary
- Poster URL
- IMDb ID / TMDB ID
- Runtime

### Step 2: Find Magnet Link

- Use reputable torrent sites
- Verify file quality (prefer 1080p)
- Check for seeders (minimum 5 recommended)
- Test download before submitting

### Step 3: Add to catalog.json

Find the `movies` array and add your entry:

```json
{
  "id": "movie_XXXXX",
  "title": "Your Movie Title",
  "year": 2024,
  "genre": ["Action", "Drama"],
  "description": "Brief plot summary in 1-3 sentences (100-300 characters).",
  "magnet_link": "magnet:?xt=urn:btih:HASH&dn=Movie.Name.2024.1080p&tr=...",
  "file_size": 2147483648,
  "subtitle_languages": ["en"],
  "poster_url": "https://image.tmdb.org/t/p/w500/posterpath.jpg",
  "imdb_id": "tt1234567",
  "tmdb_id": 12345,
  "runtime": 120,
  "video_quality": "1080p",
  "video_codec": "H.264",
  "audio_codec": "AAC"
}
```

**ID Format**: Use `movie_` followed by TMDB ID (preferred) or sequential number.

### Step 4: Validate

```bash
python scripts/validate_catalog.py
```

Fix any errors reported.

### Step 5: Update Timestamp

```bash
python scripts/update_timestamp.py
```

### Step 6: Commit

```bash
git add catalog.json
git commit -m "Add: Your Movie Title (2024)"
git push origin main
```

## Adding a Series

### Step 1: Gather Metadata

Same as movies, plus:
- Number of seasons
- Episodes per season
- Air dates for each season

### Step 2: Find Magnet Links

**Important**: Find **complete season torrents** (not individual episodes).

- One magnet link per season
- Verify all episodes included
- Check file naming conventions

### Step 3: Add to catalog.json

Find the `series` array and add your entry:

```json
{
  "id": "series_XXXXX",
  "title": "Your Series Title",
  "year": 2020,
  "genre": ["Drama", "Thriller"],
  "description": "Brief series summary in 1-3 sentences.",
  "poster_url": "https://image.tmdb.org/t/p/w500/posterpath.jpg",
  "imdb_id": "tt7654321",
  "tmdb_id": 54321,
  "seasons": [
    {
      "season_number": 1,
      "magnet_link": "magnet:?xt=urn:btih:HASH&dn=Series.S01.1080p&tr=...",
      "file_size": 5368709120,
      "episode_count": 10,
      "year": 2020,
      "video_quality": "1080p"
    },
    {
      "season_number": 2,
      "magnet_link": "magnet:?xt=urn:btih:HASH2&dn=Series.S02.1080p&tr=...",
      "file_size": 6442450944,
      "episode_count": 12,
      "year": 2021,
      "video_quality": "1080p"
    }
  ]
}
```

### Step 4-6: Same as Movies

Validate, update timestamp, commit, and push.

## Quality Guidelines

### Content Quality

- ✅ Accurate metadata from official sources
- ✅ Working magnet links with active seeders
- ✅ High-quality video (prefer 1080p)
- ✅ English subtitles available
- ✅ Reasonable file sizes (movies: 1-4 GB, series seasons: 3-10 GB)

### Metadata Quality

- ✅ Descriptions are concise (100-300 characters)
- ✅ Genres match official classifications
- ✅ Correct year (release year, not production year)
- ✅ Valid poster URLs (HTTPS, from TMDB/IMDb)
- ✅ All required fields filled

### Magnet Link Quality

- ✅ Links start with `magnet:?xt=urn:btih:`
- ✅ Hash is 40 hexadecimal characters
- ✅ Includes display name (`dn=`) parameter
- ✅ At least one tracker (`tr=`) parameter
- ✅ Tested and verified working

## Pull Request Guidelines

### PR Title Format

```
Add: Movie/Series Name (Year)
Update: Movie/Series Name - Fix description
Remove: Movie/Series Name - No seeders
```

### PR Description Template

```markdown
## Type of Change
- [ ] Add new movie
- [ ] Add new series
- [ ] Update existing entry
- [ ] Fix metadata
- [ ] Remove dead link

## Details
- **Title**: Movie/Series Name
- **Year**: 2024
- **Source**: TMDB ID 12345 / IMDb tt1234567
- **Quality**: 1080p
- **Seeders**: 50+ (verified on YYYY-MM-DD)

## Checklist
- [ ] Metadata verified on TMDB/IMDb
- [ ] Magnet link tested and working
- [ ] Validation script passes
- [ ] Timestamp updated
- [ ] Description is concise and accurate
- [ ] All required fields present

## Additional Notes
[Any special considerations or context]
```

### Review Process

1. **Automated**: GitHub Actions validates format
2. **Manual**: Maintainer reviews content quality
3. **Approval**: PR approved if quality standards met
4. **Merge**: Changes deployed to GitHub Pages

**Timeline**: Usually reviewed within 2-3 days.

## What NOT to Submit

### Prohibited Content

- ❌ Low-quality encodes (CAM, TS, etc.)
- ❌ Dead magnet links (no seeders)
- ❌ Copyrighted content without verification
- ❌ Malicious or fake torrents
- ❌ Adult/NSFW content
- ❌ Spam or joke entries

### Common Mistakes

- ❌ Missing required fields
- ❌ Invalid JSON syntax
- ❌ Duplicate IDs
- ❌ Wrong magnet link format
- ❌ Incorrect file sizes (wrong unit or typo)
- ❌ Genres not in catalog genres list
- ❌ Descriptions too long or too short

## Testing Your Changes

### Local Validation

```bash
# Validate JSON syntax
python -c "import json; json.load(open('catalog.json'))"

# Run full validation
python scripts/validate_catalog.py

# Check specific entry
python -c "
import json
with open('catalog.json') as f:
    catalog = json.load(f)
    # Find your entry by ID
    movie = next((m for m in catalog['movies'] if m['id'] == 'movie_XXXXX'), None)
    if movie:
        print('Found:', movie['title'])
    else:
        print('Not found')
"
```

### Test Magnet Link

```bash
# Use transmission-cli, qbittorrent, or any torrent client
transmission-cli "magnet:?xt=..." --verify

# Check for peers
# Should see "Seeders: X" where X > 0
```

## Advanced Contributions

### Bulk Updates

For updating multiple entries:

1. Create a script to automate changes
2. Test thoroughly on a copy first
3. Validate entire catalog
4. Submit PR with detailed explanation

Example:
```python
import json

with open('catalog.json', 'r') as f:
    catalog = json.load(f)

# Update all entries from 2020
for movie in catalog['movies']:
    if movie['year'] == 2020:
        # Make your updates
        pass

with open('catalog.json', 'w') as f:
    json.dump(catalog, f, indent=2)
```

### Metadata Collection Scripts

Share scripts that help gather metadata:

```python
# scripts/fetch_tmdb_metadata.py
import requests

def fetch_movie_metadata(tmdb_id, api_key):
    url = f"https://api.themoviedb.org/3/movie/{tmdb_id}"
    response = requests.get(url, params={"api_key": api_key})
    return response.json()
```

## Maintenance Contributions

### Checking Dead Links

Help maintain catalog quality by:

1. Testing random magnet links monthly
2. Reporting dead links via Issues
3. Finding replacement links
4. Submitting PRs to update/remove

### Metadata Corrections

If you find errors:

1. Verify correct information on TMDB/IMDb
2. Update catalog entry
3. Submit PR with "Fix:" prefix
4. Reference source in PR description

## Recognition

Contributors are recognized in:
- Git commit history
- GitHub contributors page
- Release notes
- Special acknowledgments for major contributions

## Questions?

- **General Questions**: Open a Discussion
- **Bug Reports**: Open an Issue
- **Feature Requests**: Open an Issue with [Feature] prefix
- **Quick Help**: Check existing Issues/Discussions

## Code of Conduct

Be respectful, constructive, and collaborative. We're all here to build a better catalog together!

---

**Thank you for contributing!** 🎬
