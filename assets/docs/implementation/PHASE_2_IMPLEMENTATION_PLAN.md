# Phase 2 Implementation: Services Layer

**Status:** Complete
**Date:** 2024-12-15

## Overview

Phase 2 implements the background worker services for Hackflix:
- **MetadataService** - Fetches and syncs content catalog from remote server
- **TorrentService** - Manages torrent downloads with libtorrent

Both services are QThread-based to avoid blocking the UI thread.

---

## Files Created

| File | Lines | Purpose |
|------|-------|---------|
| `src/services/metadata_service.py` | 177 | MetadataService implementation |
| `src/services/torrent_service.py` | 430 | TorrentService implementation |
| `tests/test_metadata_service.py` | 471 | 25 tests for MetadataService |
| `tests/test_torrent_service.py` | 1153 | 47 tests for TorrentService |
| `assets/docs/architecture/sample_content.json` | 108 | Sample catalog schema |

## Files Modified

| File | Changes |
|------|---------|
| `src/services/__init__.py` | Added lazy imports for both services |

---

## MetadataService

### Purpose
Fetches `content.json` from a remote catalog URL, syncs the database via `upsert_content()`, and caches poster images locally.

### Class Definition

```python
class MetadataService(QThread):
    # Signals
    sync_started = pyqtSignal()
    sync_progress = pyqtSignal(int, int, str)  # current, total, message
    sync_completed = pyqtSignal()
    sync_error = pyqtSignal(str)

    def __init__(
        self,
        db_manager: DatabaseManager,
        catalog_url: str | None = None,
        cache_dir: Path | None = None,
        parent: QObject | None = None,
    ) -> None: ...

    def stop(self) -> None: ...
    def run(self) -> None: ...
    def get_poster_path(self, item_id: str) -> Path | None: ...
```

### Usage Example

```python
from src.database.db_manager import DatabaseManager
from src.services.metadata_service import MetadataService

db = DatabaseManager("/path/to/db.sqlite")
db.initialize()

service = MetadataService(db_manager=db)
service.sync_completed.connect(on_sync_done)
service.sync_error.connect(on_sync_error)
service.start()  # Runs in background thread
```

### Sync Flow

1. **Fetch Catalog** - Downloads `content.json` from `CATALOG_URL`
2. **Update Database** - Calls `db_manager.upsert_content()` with parsed JSON
3. **Cache Posters** - Downloads poster images to `CACHE_DIR/posters/`

### Error Handling

| Error | Signal Emitted | Behavior |
|-------|----------------|----------|
| Network error | `sync_error("Network error: ...")` | Logged, sync aborted |
| Invalid JSON | `sync_error("Invalid catalog format: ...")` | Logged, sync aborted |
| Poster download fail | None | Logged as warning, continues |
| Database error | `sync_error(str(e))` | Logged, sync aborted |

### Configuration

Uses from `src/config.py`:
- `CATALOG_URL` - Remote catalog URL
- `CACHE_DIR` - Local cache directory for posters

---

## TorrentService

### Purpose
Manages torrent downloads using embedded libtorrent with persistent session state, progress tracking, and automatic video file detection.

### Class Definition

```python
class TorrentService(QThread):
    # Signals
    download_progress = pyqtSignal(int, int, float, float)  # file_id, %, down_rate, up_rate
    download_completed = pyqtSignal(int, str)  # file_id, file_path
    download_error = pyqtSignal(int, str)  # file_id, error_message

    def __init__(
        self,
        db_manager: DatabaseManager,
        state_dir: Path | None = None,
        download_dir: Path | None = None,
        poll_interval_ms: int | None = None,
        parent: QObject | None = None,
    ) -> None: ...

    def stop(self) -> None: ...
    def run(self) -> None: ...
    def add_magnet(
        self,
        video_file_id: int,
        magnet_link: str,
        sequential: bool = False,
    ) -> bool: ...
    def cancel_download(self, video_file_id: int) -> bool: ...
    def get_active_downloads(self) -> list[int]: ...
```

### Usage Example

```python
from src.database.db_manager import DatabaseManager
from src.services.torrent_service import TorrentService

db = DatabaseManager("/path/to/db.sqlite")
db.initialize()

service = TorrentService(db_manager=db)
service.download_progress.connect(on_progress)
service.download_completed.connect(on_complete)
service.download_error.connect(on_error)
service.start()  # Runs in background thread

# Add a download
service.add_magnet(
    video_file_id=123,
    magnet_link="magnet:?xt=urn:btih:...",
    sequential=True  # For series episodes
)
```

### State Persistence

Session state and resume data are saved to `TORRENT_STATE_DIR`:

```
~/.config/hackflix/torrents/
├── session_state.lt    # DHT nodes, routing table
└── resume_data.pkl     # Per-torrent resume data
```

On startup, the service:
1. Loads session state (DHT nodes, etc.)
2. Loads resume data and re-adds incomplete torrents
3. Starts progress polling

On shutdown:
1. Saves session state
2. Saves resume data for all active torrents

### Download State Machine

```
add_magnet() ──► QUEUED
                   │
                   ▼
              DOWNLOADING ◄─── (polling detects activity)
                   │
          ┌───────┴───────┐
          ▼               ▼
      COMPLETED        ERROR
     (seeding)      (torrent_error_alert)
          │
          ▼
    (removed from session)
```

### Video File Detection

When a torrent completes (enters seeding state), the service:
1. Scans all files in the torrent
2. Filters by video extensions: `.mkv`, `.mp4`, `.avi`, `.webm`, `.mov`, `.wmv`, `.flv`
3. Selects the largest video file
4. Updates database with `file_path`

### Error Handling

| Error | Signal Emitted | DB State |
|-------|----------------|----------|
| Magnet parse error | `download_error(file_id, msg)` | `ERROR` |
| Torrent error alert | `download_error(file_id, msg)` | `ERROR` |
| No video file found | `download_error(file_id, msg)` | `ERROR` |
| Session state corrupt | None | Continues without state |

### Configuration

Uses from `src/config.py`:
- `TORRENT_STATE_DIR` - Directory for session/resume data
- `MEDIA_LIBRARY_PATH` - Download destination
- `TORRENT_POLL_INTERVAL_MS` - Progress polling interval (2000ms)
- `DownloadState` - State enum for database updates

---

## Lazy Imports

The `src/services/__init__.py` uses lazy imports to avoid requiring libtorrent at module import time:

```python
def __getattr__(name: str):
    if name == "MetadataService":
        from src.services.metadata_service import MetadataService
        return MetadataService
    if name == "TorrentService":
        from src.services.torrent_service import TorrentService
        return TorrentService
    raise AttributeError(...)
```

This allows tests to mock libtorrent before the actual import occurs.

---

## Test Coverage

### Summary

| File | Coverage | Notes |
|------|----------|-------|
| `metadata_service.py` | 100% | All paths covered |
| `torrent_service.py` | 99% | Only `msleep` in while loop uncovered |
| `services/__init__.py` | 100% | Lazy imports tested |

### Test Categories

**MetadataService (25 tests):**
- Initialization with defaults and custom values
- Successful sync with signal emissions
- Network error handling
- JSON parse error handling
- Poster caching (download, skip existing, failure continues)
- Stop/cancel behavior
- `get_poster_path()` for various extensions

**TorrentService (47 tests):**
- Initialization with defaults and custom values
- Directory creation
- Session state load/save (success, missing, corrupted)
- Resume data load/save (success, missing, corrupted, errors)
- Progress polling (downloading, seeding, stopped, no session)
- Alert handling (torrent errors, unknown handles)
- `add_magnet()` (success, no session, duplicate, sequential, errors)
- `cancel_download()` (success, not found)
- `get_active_downloads()`
- `_find_largest_video()` (success, no torrent file, no video files)
- `run()` method (normal flow, exception handling)

---

## Integration with Phase 1

### Database Methods Used

**MetadataService:**
- `db_manager.upsert_content(json_data)` - Sync catalog to database

**TorrentService:**
- `db_manager.update_file_state(file_id, state, progress)` - Update download state
- `db_manager.update_file_path(file_id, path)` - Set video file path on completion

### Config Constants Used

```python
# MetadataService
CATALOG_URL          # Remote catalog URL
CACHE_DIR            # Poster cache directory

# TorrentService
TORRENT_STATE_DIR    # Session persistence directory
MEDIA_LIBRARY_PATH   # Download destination
TORRENT_POLL_INTERVAL_MS  # Polling frequency (2000ms)
DownloadState        # Enum: PENDING, QUEUED, DOWNLOADING, COMPLETED, ERROR
```

---

## Future Integration (Phase 3+)

### AppController Integration

The AppController will:
1. Instantiate both services on startup
2. Connect service signals to UI updates
3. Call `add_magnet()` when user initiates download
4. Handle `download_completed` to trigger PipelineService (Phase 5)

### Auto-Resume on Startup

```python
# In AppController.__init__()
incomplete = db_manager.get_incomplete_downloads()
for file in incomplete:
    torrent_service.add_magnet(
        video_file_id=file["id"],
        magnet_link=file["magnet_link"],
        sequential=file["season_id"] is not None
    )
```

### UI Signal Connections

```python
# Progress updates
torrent_service.download_progress.connect(
    lambda fid, pct, down, up: ui.update_download_progress(fid, pct)
)

# Completion
torrent_service.download_completed.connect(
    lambda fid, path: ui.show_toast(f"Download complete: {path}")
)

# Errors
torrent_service.download_error.connect(
    lambda fid, msg: ui.show_toast(f"Download failed: {msg}", error=True)
)
```

---

## Running Tests

```bash
# Run all Phase 2 tests
uv run pytest tests/test_metadata_service.py tests/test_torrent_service.py -v

# Run with coverage
uv run pytest tests/test_metadata_service.py tests/test_torrent_service.py \
    --cov=src.services --cov-report=term-missing

# Run full test suite
uv run pytest tests/ --cov=src --cov-report=term-missing
```

---

## Acceptance Criteria

- [x] MetadataService fetches and parses content.json
- [x] MetadataService calls upsert_content() to sync database
- [x] MetadataService caches poster images locally
- [x] MetadataService emits appropriate signals for progress/completion/errors
- [x] TorrentService manages libtorrent session with DHT
- [x] TorrentService persists session state and resume data
- [x] TorrentService supports sequential downloads for series
- [x] TorrentService polls progress and emits signals
- [x] TorrentService detects largest video file on completion
- [x] TorrentService updates database state throughout lifecycle
- [x] Both services handle errors gracefully without crashing
- [x] 100% test coverage on MetadataService
- [x] 99% test coverage on TorrentService
- [x] All 138 tests pass
