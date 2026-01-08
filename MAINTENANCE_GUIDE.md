# HackFlix Maintenance Guide

## Quick Fix for Current Issues

### Issue: Downloads stuck at 0% even though files are downloaded
**Solution:**
```bash
python detect_completed.py
```
This scans the download directory and marks completed downloads as "ready" in the database.

### Issue: Catalog not syncing from GitHub Pages
**Solution:**
```bash
python maintenance.py force-sync
```
Then run catalog sync in the app UI.

### Issue: Download stuck in "downloading" state
**Solution:**
```bash
# Reset specific download
python maintenance.py reset movie_27205

# Or reset all downloads
python maintenance.py reset-all
```

## Maintenance Tools

### maintenance.py
Main maintenance utility for managing downloads and catalog.

**Commands:**
- `list` - Show all downloads and their states
- `reset <item_id>` - Reset specific download (clears state and files)
- `reset-all` - Reset all stuck downloads
- `force-sync` - Force catalog sync by resetting timestamp
- `magnet-links` - Show magnet links for all movies

**Examples:**
```bash
# View all downloads
python maintenance.py list

# Reset Inception download
python maintenance.py reset movie_27205

# Reset all downloads
python maintenance.py reset-all

# Force catalog sync
python maintenance.py force-sync
```

### detect_completed.py
Scans download directory for completed video files and updates database.

**Usage:**
```bash
python detect_completed.py
```

**What it does:**
- Scans `~/Videos/HackFlix` for video files
- Matches files to movies in database
- Marks downloads as "ready" if video > 100MB found
- Updates progress to 100%

**When to use:**
- After app crash during download
- When download completes but UI shows 0%
- After manually moving files to download directory

### test_sync.py
Test catalog synchronization from GitHub Pages.

**Usage:**
```bash
# Normal sync (respects timestamps)
uv run python test_sync.py

# Force sync (ignores timestamps)
uv run python test_sync.py --force
```

**What it does:**
- Fetches catalog.json from GitHub Pages
- Syncs to local database
- Shows updated magnet links
- Useful for testing catalog changes

## Common Workflows

### Workflow 1: Download stuck at 0%
```bash
# Check if files exist
ls -lh ~/Videos/HackFlix/

# Detect completed downloads
python detect_completed.py

# Restart app and check UI
```

### Workflow 2: Reset broken download
```bash
# List all downloads
python maintenance.py list

# Reset specific download
python maintenance.py reset movie_27205

# Restart app and try download again
```

### Workflow 3: Update catalog from GitHub
```bash
# Check current magnet links
python maintenance.py magnet-links

# Force sync
python maintenance.py force-sync

# Run sync in app UI (Catalog tab -> Sync button)

# Verify updates
python maintenance.py magnet-links
```

### Workflow 4: Clean slate (reset everything)
```bash
# Reset all downloads
python maintenance.py reset-all

# Force sync catalog
python maintenance.py force-sync

# Run catalog sync in app

# Restart app
```

## Database Schema Reference

### download_state table
Key columns:
- `id` - Movie/season ID (e.g., "movie_27205")
- `status` - Current state: "available", "downloading", "ready", "failed"
- `progress` - Overall progress 0-100
- `phase` - Current phase: "video", "subtitles", "translation"
- `*_progress` - Phase-specific progress
- `download_path` - Where files are being downloaded
- `torrent_info_hash` - BitTorrent hash

### Direct database queries
```bash
# Check download state
sqlite3 hackflix.db "SELECT id, status, progress, phase FROM download_state WHERE id = 'movie_27205'"

# Check magnet links
sqlite3 hackflix.db "SELECT id, title, magnet_link FROM movies LIMIT 5"

# Reset download manually
sqlite3 hackflix.db "UPDATE download_state SET status = 'available', progress = 0.0 WHERE id = 'movie_27205'"
```

## Known Issues and Solutions

### Issue: Progress bar stuck at 0%
**Root cause:** Download tracking lost when app closed/restarted

**Solutions:**
1. Implement resume functionality (TODO)
2. Use `detect_completed.py` to mark completed downloads
3. Monitor error.log for progress update issues

### Issue: Catalog sync not updating magnet links
**Root cause:** Incremental sync checks timestamps and skips if remote ≤ local

**Solutions:**
1. Use `python maintenance.py force-sync` to reset timestamp
2. Update `last_updated` in catalog.json on GitHub Pages
3. Use `force=True` parameter in sync dialog (TODO)

### Issue: Download won't start (already downloading)
**Root cause:** Database shows "downloading" but no active download in memory

**Solutions:**
1. Use `python maintenance.py reset movie_27205` to reset state
2. Restart app to clear in-memory state
3. Check error.log for actual errors

## Debug Logging

### Enable verbose logging
Check `error.log` for detailed debug output:
```bash
tail -f error.log
```

### Key log messages
- `[movie_id] Starting video download phase` - Download started
- `[movie_id] Torrent added successfully: <hash>` - Torrent added to libtorrent
- `[movie_id] Video progress: X%` - Progress updates (every 10%)
- `[movie_id] Video download complete!` - Download finished
- `Error starting video download: ...` - Download failed to start
- `Torrent hash X not found in downloader` - Tracking lost

## Files and Directories

### Important files
- `hackflix.db` - SQLite database (download states, catalog, metadata)
- `error.log` - Application error and debug log
- `~/Videos/HackFlix/` - Default download directory

### Utility scripts
- `maintenance.py` - Main maintenance utility
- `detect_completed.py` - Detect completed downloads
- `test_sync.py` - Test catalog synchronization

### Configuration
- `.env` - API keys (OpenSubtitles, Gemini, etc.)
- `source/config.py` - App configuration
- Catalog URL: `https://wiktor-jedski.github.io/hackflix-catalog/catalog.json`

## Troubleshooting

### App won't start
1. Check error.log for errors
2. Verify API keys in `.env`
3. Check database integrity: `sqlite3 hackflix.db "PRAGMA integrity_check;"`

### Downloads not working
1. Check internet connection
2. Verify magnet links: `python maintenance.py magnet-links`
3. Check download directory exists: `ls ~/Videos/HackFlix`
4. Look for errors in error.log

### UI not updating
1. Check if progress timer is running (check error.log)
2. Verify signals are connected
3. Try restarting app
4. Use `detect_completed.py` to force UI update

### Catalog sync fails
1. Check internet connection
2. Verify catalog URL is accessible
3. Check error.log for network errors
4. Try force sync: `python maintenance.py force-sync`

## Development Tips

### Testing downloads
Use small test torrents (< 100MB) for faster testing.

### Monitoring progress
Watch both error.log and download directory:
```bash
# Terminal 1: Watch logs
tail -f error.log

# Terminal 2: Watch files
watch -n 1 'du -sh ~/Videos/HackFlix/*'
```

### Database inspection
Use SQLite browser or command-line:
```bash
sqlite3 hackflix.db
.tables
.schema download_state
SELECT * FROM download_state;
.quit
```
