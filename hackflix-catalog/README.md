# HackFlix Catalog

Official catalog repository for HackFlix - a curated collection of movies and series with metadata and magnet links.

**Catalog URL**: `https://YOUR_USERNAME.github.io/hackflix-catalog/catalog.json`

## Overview

This repository hosts the `catalog.json` file that HackFlix clients use to discover and download movies and series. The catalog is automatically validated on every commit using GitHub Actions.

## Catalog Stats

- **Version**: 1.0.0
- **Last Updated**: 2025-01-06
- **Movies**: 5
- **Series**: 3
- **Total Seasons**: 4

## Files

- **catalog.json** - Main catalog file (served via GitHub Pages)
- **catalog-schema.json** - JSON Schema definition for validation
- **scripts/validate_catalog.py** - Python validation script
- **scripts/update_timestamp.py** - Auto-update last_updated timestamp
- **.github/workflows/validate.yml** - CI/CD for automatic validation

## Usage

### For HackFlix Clients

Configure your client to fetch the catalog from:

```
https://YOUR_USERNAME.github.io/hackflix-catalog/catalog.json
```

The catalog is served as static JSON via GitHub Pages with HTTPS and CORS enabled.

### For Contributors

#### Adding a Movie

1. Fork this repository
2. Edit `catalog.json` and add your movie to the `movies` array
3. Run validation: `python scripts/validate_catalog.py`
4. Update timestamp: `python scripts/update_timestamp.py`
5. Commit and create a pull request

**Movie Template:**
```json
{
  "id": "movie_XXX",
  "title": "Movie Title",
  "year": 2024,
  "genre": ["Genre1", "Genre2"],
  "description": "Short plot summary (100-300 chars).",
  "magnet_link": "magnet:?xt=urn:btih:[40-char-hash]&dn=...",
  "file_size": 2147483648,
  "subtitle_languages": ["en"],
  "poster_url": "https://image.tmdb.org/t/p/w500/...",
  "imdb_id": "tt1234567",
  "tmdb_id": 12345,
  "runtime": 120,
  "video_quality": "1080p"
}
```

#### Adding a Series

1. Follow same fork/edit workflow
2. Add series to `series` array with all seasons
3. Each season needs its own magnet link (full season torrent)
4. Validate and submit PR

**Series Template:**
```json
{
  "id": "series_XXX",
  "title": "Series Title",
  "year": 2020,
  "genre": ["Genre1"],
  "description": "Brief series summary.",
  "imdb_id": "tt7654321",
  "tmdb_id": 54321,
  "seasons": [
    {
      "season_number": 1,
      "magnet_link": "magnet:?xt=urn:btih:[40-char-hash]&dn=...",
      "file_size": 5368709120,
      "episode_count": 10,
      "year": 2020,
      "video_quality": "1080p"
    }
  ]
}
```

## Validation

All changes are automatically validated via GitHub Actions. The validation checks:

- ✅ JSON syntax
- ✅ Required fields present
- ✅ Correct data types
- ✅ Valid magnet link format
- ✅ Unique IDs
- ✅ Genre consistency
- ✅ File size sanity checks
- ✅ Year ranges
- ✅ IMDb ID format

### Local Validation

Before committing, run validation locally:

```bash
# Install Python 3.7+ if not already installed
python --version

# Run validation
python scripts/validate_catalog.py

# Auto-update timestamp
python scripts/update_timestamp.py

# Check status
git status
```

## GitHub Pages Setup

### Initial Setup (Repository Owner)

1. **Create Repository**:
   - Go to GitHub and create new repository: `hackflix-catalog`
   - Make it public (required for GitHub Pages)
   - Don't initialize with README (we'll push our own)

2. **Enable GitHub Pages**:
   - Go to repository Settings → Pages
   - Source: Deploy from branch `main`
   - Folder: `/ (root)`
   - Click Save

3. **Push Initial Content**:
   ```bash
   cd hackflix-catalog
   git init
   git add .
   git commit -m "Initial catalog setup"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/hackflix-catalog.git
   git push -u origin main
   ```

4. **Verify Deployment**:
   - Go to repository Actions tab
   - Wait for validation workflow to complete
   - Visit: `https://YOUR_USERNAME.github.io/hackflix-catalog/catalog.json`
   - Should see JSON catalog

5. **Configure Client**:
   - Update HackFlix client configuration
   - Set `CATALOG_URL` to your GitHub Pages URL

### Custom Domain (Optional)

1. Add CNAME file with your domain:
   ```bash
   echo "catalog.yourdomain.com" > CNAME
   git add CNAME
   git commit -m "Add custom domain"
   git push
   ```

2. Configure DNS:
   - Add CNAME record pointing to `YOUR_USERNAME.github.io`
   - Wait for DNS propagation

3. Enable HTTPS in GitHub Pages settings

## Maintenance

### Updating Catalog

When adding/modifying entries:

1. Edit `catalog.json`
2. Run `python scripts/validate_catalog.py`
3. Run `python scripts/update_timestamp.py` (auto-updates `last_updated`)
4. Commit with descriptive message
5. Push to trigger auto-deployment

### Checking for Dead Magnets

Periodically verify magnet links:

```bash
# Use a torrent client to check for seeders
# Remove or update entries with no peers
```

### Monitoring

- **GitHub Actions**: Check validation status on every commit
- **GitHub Pages**: Monitor deployment status in repository settings
- **Traffic**: View analytics in repository Insights → Traffic

## Schema

See [SCHEMA.md](SCHEMA.md) for complete field documentation.

## Contributing

We welcome contributions! Please:

1. Fork the repository
2. Create a feature branch
3. Add/update catalog entries
4. Ensure validation passes
5. Submit pull request with description

### Contribution Guidelines

- **Quality**: Only add high-quality sources (prefer 1080p)
- **Availability**: Test magnet links before submitting
- **Metadata**: Use accurate information from TMDB/IMDb
- **Format**: Follow existing entry structure
- **Validation**: All PRs must pass validation

### Code of Conduct

- Be respectful and constructive
- Focus on content quality
- Respect copyright and legal considerations
- No spam or low-quality submissions

## API

### Endpoint

```
GET https://YOUR_USERNAME.github.io/hackflix-catalog/catalog.json
```

**Response**: JSON object with movies, series, and metadata

**Headers**:
- `Content-Type: application/json`
- `Access-Control-Allow-Origin: *` (CORS enabled by GitHub Pages)

### Rate Limiting

GitHub Pages has generous bandwidth:
- 100 GB/month soft limit
- Requests are cached via CDN
- No authentication required for public repos

For high-traffic scenarios, consider:
- Implementing client-side caching
- Using `If-Modified-Since` headers
- Fetching only when `last_updated` timestamp changes

## Versioning

Catalog schema follows semantic versioning:

- **Major** (1.x.x): Breaking changes to structure
- **Minor** (x.1.x): New optional fields
- **Patch** (x.x.1): Documentation/clarification only

Current version: **1.0.0**

## Support

- **Issues**: Report bugs or request features via GitHub Issues
- **Discussions**: Use GitHub Discussions for questions
- **Pull Requests**: Contribute improvements via PRs

## License

Content metadata is sourced from public APIs (TMDB, IMDb) and is used for informational purposes. Magnet links point to publicly available torrents.

See [LICENSE](LICENSE) for details.

## Acknowledgments

- **TMDB**: Movie and series metadata
- **IMDb**: Ratings and identifiers
- **GitHub Pages**: Free hosting and CDN
- **Contributors**: Thanks to all catalog contributors!

---

**Maintained by**: HackFlix Team
**Last Validated**: Automated via GitHub Actions
**Catalog URL**: `https://YOUR_USERNAME.github.io/hackflix-catalog/catalog.json`
