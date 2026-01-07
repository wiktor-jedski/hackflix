# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

HackFlix is a PyQt5-based movie player application designed for Raspberry Pi 5 that provides a streamlined workflow for Polish-speaking users to watch movies and series with translated subtitles and voice-over.

**Current Architecture**: Legacy implementation with manual workflow (torrent search, subtitle download, translation)

**Target Architecture**: Server-based curated catalog with automated download pipeline (video + subtitles + translation + voiceover)

**Core Features**:
- Local video playback (VLC backend)
- Torrent downloading (libtorrent)
- Subtitle search and download (OpenSubtitles API)
- Subtitle translation (Google Gemini API)
- TTS voice-over generation (planned, in research phase)
- Server-based catalog with offline-first local database (in development)

**Design Goals**:
- 3-click workflow: Select → Download → Play
- Polish-only UI and content
- Wireless keyboard navigation optimized
- Small curated catalog (50-200 titles, starting with 5-10)
- Minimize API costs through aggressive caching

## Development Setup

### Python Environment

Uses Python 3.13+ with uv package manager:

```bash
# Install dependencies
uv sync

# Activate virtual environment
source .venv/bin/activate
```

### Environment Variables

Create a `.env` file in the project root with the following keys:

```
OPENSUBTITLES_API_KEY=your_api_key_here
OPENSUBTITLES_USERNAME=your_username  # Optional, for >5 downloads/day
OPENSUBTITLES_PASSWORD=your_password  # Optional
GEMINI_API_KEY=your_gemini_api_key
# TTS_API_KEY=your_tts_api_key  # When voiceover feature implemented
```

These are loaded via `python-dotenv` in `source/subtitle_manager.py` and `source/translation_manager.py`.

**Critical**: App blocks launch if required API keys are missing (shows error dialog and exits).

### Running the Application

```bash
# Run the main application
python main.py
```

The application will:
- Auto-scale UI by 1.5x (configured in main.py:30)
- Load Polish translations from `translations/pl_PL.qm`
- Apply dark theme from `source/dark_theme.qss`
- Start in maximized window mode

## Current Architecture (Legacy)

### Core Application Structure

**main.py** - Entry point that:
- Sets up Qt application and translations
- Applies dark theme stylesheet
- Validates API key configuration (blocks launch if missing)
- Instantiates and displays MoviePlayerApp

**source/movie_player.py** - Main window (MoviePlayerApp) that manages:
- Three-view stacked widget: player view, browser view, fullscreen video
- VLC media player instance
- Tab widget containing Library, Downloads, and Filmweb tabs
- Signal routing between all components

### Key Components

**Video Playback Stack:**
- `source/video_frame.py` - Custom QFrame that hosts VLC video output and handles mouse events for fullscreen toggle
- `source/movie_player.py` - Controls playback, UI updates, timeline slider, and fullscreen transitions
- Uses `python-vlc` bindings with native VLC instance

**File Management:**
- `source/file_browser.py` (FileBrowser) - Library tab showing local video files with context menu for subtitle/translation operations
- Handles .mp4, .mkv, .avi, .mov file types
- Provides "Find Subtitles" and "Translate Subtitle" context actions
- Recursive directory search (no need for auto-extraction of torrent folders)

**Torrent Subsystem:**
- `source/torrent_manager.py` - TorrentSearcher scrapes 1337x.to, TorrentDownloader uses libtorrent
- `source/downloads_tab.py` (DownloadsTab) - UI for searching torrents, starting downloads, monitoring progress
- Downloads are saved to user-selected directory
- 2-3 concurrent downloads supported
- Pause on app close, resume on reopen

**Subtitle Subsystem:**
- `source/subtitle_manager.py` (SubtitleManager) - OpenSubtitles.com REST API v1 client
  - Supports login for extended quota
  - Searches by video filename with season/episode extraction
  - Downloads .srt files to video directory
  - Use best match score from API for subtitle selection
- `source/subtitle_dialog.py` (SubtitleResultsDialog) - Shows search results with download buttons
- Auto-loads .srt files matching video basename when playback starts
- Priority: prefer -pl (Polish translated) subtitles first

**Translation Subsystem:**
- `source/translation_manager.py` (SubtitleTranslator) - Google Gemini API client
  - Batch translates subtitle entries (default: 10 per batch)
  - **Known issue**: Uses '|' delimiter which conflicts with .srt formatting
  - **TODO**: Switch to JSON array format for prompts
  - Uses pysrt for parsing .srt files
  - Target language: Polish (hardcoded, configurable via TARGET_LANGUAGE constant)
  - Retries on count mismatch, falls back to single-entry translation on batch failure
  - 3 retry attempts then mark as failed
  - Trust Gemini's line break formatting (don't force original breaks)
- Saves translated .srt with `-pl` suffix
- Cache translations permanently (never re-translate)

**Web Browser:**
- `source/web_browser_tab.py` (WebBrowserTab) - PyQt5 WebEngine browser for Filmweb
- **TODO**: Remove this tab in favor of catalog-based workflow

### Signal Flow

All components communicate via PyQt signals:
- FileBrowser emits `file_selected`, `find_subtitles_requested`, `translate_subtitle_requested`
- SubtitleManager emits `search_results`, `download_ready`, `download_error`, `login_status`
- SubtitleTranslator emits `translation_progress`, `translation_complete`, `translation_error`
- MoviePlayerApp connects all signals and coordinates responses

**Known issue**: Signal complexity is high - too many signals connecting too many components, making flow hard to follow. Consider refactoring.

### UI Theming & Translation

- Dark theme applied via QSS stylesheet: `source/dark_theme.qss`
- Polish translations: `translations/pl_PL.qm` (compiled from .ts file)
- All UI strings use `self.tr()` for translation support
- Locale hardcoded to `pl_PL` in main.py:37 (intentional, Polish-only focus)

## Target Architecture (In Development)

### Server-Based Catalog System

**Priority**: This is the current development focus (Phase 1).

**Catalog Server**:
- Static `catalog.json` file hosted on GitHub Pages
- Built on top of existing metadata APIs (TMDB/IMDb/OMDb)
- Schema: `{title, year, genre, description, magnet_link, file_size, subtitle_languages, last_updated}`
- Series: separate magnet link entry per season
- Small curated selection (start with 5-10 favorites, expand to 50-200)
- Curation criteria: personal favorites + high IMDb/TMDB ratings

**Local SQLite Database**:
- Offline-first operation (app works after initial sync)
- Stores: catalog data, download state, watch history
- Manual sync: user triggers "Update catalog" → progress dialog shown
- Incremental smart sync: fetch new titles + changed entries since last `last_updated` timestamp
- Watch history: track series episode + timestamp for resume
- Download state: track progress for pause/resume across app restarts

**catalog.json Example Structure**:
```json
{
  "last_updated": "2025-01-06T12:00:00Z",
  "movies": [
    {
      "id": "movie_001",
      "title": "Movie Title",
      "year": 2024,
      "genre": ["Action", "Sci-Fi"],
      "description": "Short description",
      "magnet_link": "magnet:?xt=...",
      "file_size": 2147483648,
      "poster_url": "https://image.tmdb.org/t/p/w500/...",
      "subtitle": {
        "file_id": "12345678",
        "language": "en",
        "needs_translation": true
      }
    },
    {
      "id": "movie_002",
      "title": "Polish Movie",
      "year": 2024,
      "genre": ["Drama"],
      "description": "Movie with Polish subtitles",
      "magnet_link": "magnet:?xt=...",
      "file_size": 2147483648,
      "poster_url": "https://image.tmdb.org/t/p/w500/...",
      "subtitle": {
        "file_id": "87654321",
        "language": "pl",
        "needs_translation": false
      }
    }
  ],
  "series": [
    {
      "id": "series_001",
      "title": "Series Title",
      "year": 2024,
      "genre": ["Drama"],
      "description": "Short description",
      "poster_url": "https://image.tmdb.org/t/p/w500/...",
      "seasons": [
        {
          "season_number": 1,
          "magnet_link": "magnet:?xt=...",
          "file_size": 5368709120,
          "episode_count": 8,
          "subtitle": {
            "file_id": "98765432",
            "language": "en",
            "needs_translation": true
          }
        }
      ]
    }
  ]
}
```

**Subtitle Specification**:
- `file_id`: OpenSubtitles file ID for direct download (no search needed)
- `language`: Subtitle language code (e.g., "en", "pl")
- `needs_translation`: Boolean flag indicating if translation is required
  - `true`: Download English subtitle, translate to Polish (2 phases)
  - `false`: Download Polish subtitle directly (1 phase, faster)

### New UI Design (Phase 2)

**Tab Structure**:
- Remove: Downloads tab, Filmweb tab
- Keep: Movies tab, Series tab
- Add: Genre filtering (horizontal tabs within each main tab)

**Catalog Layout** (List View):
- Each row: poster thumbnail + title + genre + year + availability status
- Poster images: URLs from TMDB/IMDb, cached on-demand by client
- Genre tabs: Action, Comedy, Drama, Sci-Fi, etc.

**Availability Status**:
- **Download available**: Green icon, "Download" button
- **Downloading**: Progress bar with detailed sub-progress (see below)
- **Ready**: Green checkmark, "Play" button
- **Translation failed**: Warning icon, "Retry" button
- **Download failed**: Error icon, "Retry" button
- **Unavailable**: Hidden from catalog entirely

**Progress Display** (3 equal phases):
- Video download: 0-33%
- Subtitle download: 34-66%
- Translation: 67-100%
- Show detailed sub-progress: "Video: 15% (of its 33%), Subtitles: 0%, Translation: 0%"
- Remain "Downloading" until all phases complete (no partial playback)

**Keyboard Shortcuts**:
- Playback: Space = play/pause, Left/Right = seek, F = fullscreen
- Navigation: Tab/Arrow keys = browse, Enter = select, Esc = back
- Quick actions: D = download, S = search, U = update catalog

**Series Navigation**:
- Click series → show seasons (list with availability status per season)
- Click season → show episodes (list with episode number + title)
- Track last watched episode (auto-resume at timestamp)

### Download Pipeline (Phase 3)

**3-Click Workflow**:
1. User selects movie/series from catalog
2. User clicks "Download" button
3. When ready, user clicks "Play" button

**Download Process**:
1. **Video Download (0-33% or 0-50% if no translation)**
   - Start torrent download (libtorrent, 2-3 concurrent allowed)
   - Monitor progress and detect video file completion

2. **Subtitle Download (34-66% or 50-100% if no translation)**
   - **Direct Download Mode** (catalog specifies `subtitle.file_id`):
     - Download subtitle directly using OpenSubtitles file_id (no search needed)
     - Faster and more predictable than search
   - **Fallback Search Mode** (if no file_id provided):
     - Search OpenSubtitles API for matching subtitle
     - Download best match

3. **Translation (67-100%, skipped if `needs_translation: false`)**
   - If `needs_translation: true`: Translate subtitle to Polish via Gemini API
   - If `needs_translation: false`: Skip translation (Polish subtitle already downloaded)
   - Cache translated subtitle as `{filename}-pl.srt`

4. **Mark as "Ready"** - All phases complete, video ready to play

**Error Handling**:
- Network failures: auto-retry silently with exponential backoff
- No seeders: try download, fail gracefully with message, allow manual retry
- Translation failures: mark as failed, show progressive disclosure error (simple message + "Show details")
- 3 retry attempts for Gemini API, then mark failed

**State Persistence**:
- Pause all downloads on app close
- Resume from saved state on app reopen
- SQLite stores download progress, watch history

### Voice-Over Feature (Phase 4 - Research)

**Status**: Needs research and prototyping. Not currently implemented.

**Planned Approach**:
- Cloud TTS service (Google Cloud TTS / Amazon Polly / Azure - undecided)
- Client generates on-demand when user first plays movie
- Polish neural/WaveNet voices
- Cache generated audio permanently (never regenerate)
- Audio ducking: lower original audio during dialogue (implementation TBD)
- Mixing approach TBD (VLC filters vs pre-processed file vs dual tracks)

**Cost Management**:
- Cache all TTS audio permanently
- Track API usage and costs
- Monthly budget alerts
- Display cumulative costs in settings page
- Optimize to minimize API calls

## Key Patterns & Implementation Details

### Filename-Based Subtitle Matching

When playing a video, the app:
1. Extracts season/episode info using regex (SEASON_EPISODE_REGEX in movie_player.py:35-39)
2. Cleans query by removing year, quality tags, brackets (CLEAN_QUERY_REGEX in movie_player.py:41-45)
3. Searches for .srt files with matching basename in same directory
4. Auto-loads first matching .srt to VLC player
5. **Priority**: Prefer `-pl` (translated) subtitles when multiple matches exist

### Asynchronous Operations

All network operations (torrent search, subtitle search/download, translation) run in daemon threads and emit signals to update UI from main thread.

**Known issue**: Thread management could be improved. Consider async patterns or task queue instead of daemon threads everywhere.

### Cursor Auto-Hide

Video frame hides cursor after 3 seconds of inactivity (CURSOR_HIDE_TIMEOUT_MS in movie_player.py:32) to provide clean playback experience for keyboard users.

### Fullscreen Behavior

When entering fullscreen mode:
- Steal all keyboard input for playback controls
- No tab navigation available
- Space = play/pause, arrows = seek, F/double-click = toggle fullscreen

### Subtitle File Handling

**Known issue**: Duplicate file handling logic scattered across files. Should be centralized.

Current behavior:
- When downloading new subtitle, removes other .srt files with same video basename
- Keeps only the newly downloaded/translated subtitle
- Logic in `_remove_other_srt_files()` in movie_player.py:88

### Error Message Strategy

- Progressive disclosure: simple user-friendly message by default
- "Show details" button reveals technical error info
- Helps non-technical users while enabling debugging

## Common Development Tasks

### Fixing Gemini Translation Delimiter Issue

**Current problem**: Prompt uses '|' as delimiter, which appears in .srt formatting

**Solution** (in `source/translation_manager.py`):
1. Change prompt to send subtitle entries as JSON array instead of delimited string
2. Update parsing logic to handle JSON array response
3. Update batch processing to construct/deconstruct JSON properly
4. Keep existing retry logic and error handling

### Implementing Catalog Sync

**New files needed**:
- `source/catalog_manager.py` - Handles catalog.json fetch, SQLite storage, sync logic
- `source/catalog_tab.py` - UI for Movies/Series with list view and genre filtering

**Key functionality**:
1. Fetch catalog.json from configured URL (default: GitHub Pages)
2. Compare `last_updated` timestamp with local SQLite version
3. Perform incremental sync (new + changed entries only)
4. Update SQLite with new data
5. Emit signal to refresh UI
6. Show progress dialog during sync

### Adding Series Episode Tracking

**SQLite schema additions**:
```sql
CREATE TABLE watch_history (
  series_id TEXT,
  season_number INTEGER,
  episode_number INTEGER,
  last_position INTEGER,  -- milliseconds
  last_watched TIMESTAMP,
  completed BOOLEAN,
  PRIMARY KEY (series_id, season_number, episode_number)
);
```

**Implementation**:
1. On video playback, detect if file is part of series (check catalog)
2. Periodically save playback position to SQLite (every 10 seconds)
3. On playback end, check if >90% watched → mark completed
4. When user selects series, query watch_history for last incomplete episode
5. Auto-resume at saved timestamp

### Refactoring Signal Complexity

**Current issue**: Too many signals in MoviePlayerApp, hard to follow

**Suggested approach**:
1. Introduce mediator/coordinator classes for subsystems
2. Group related signals into subsystem-specific signal objects
3. Use event bus pattern for cross-component communication
4. Document signal flow with diagrams in code comments

## Testing and Code Quality

Currently, there is no testing or linting infrastructure configured in this project. The codebase does not include:
- Unit tests or integration tests
- Test configuration files (pytest.ini, etc.)
- Linting configuration (.pylintrc, .flake8, ruff.toml, etc.)
- Pre-commit hooks or CI/CD pipelines

When adding testing/linting infrastructure, consider:
- PyQt applications are typically tested with `pytest-qt` for GUI components
- VLC integration requires mocking or test fixtures due to media player dependencies
- Network-dependent components (torrent search, subtitle API, translation API) should use mocked responses
- Subtitle translation batching logic would benefit from unit tests (especially delimiter handling)
- Catalog sync logic should have integration tests

## Development Priorities

**Phase 1: Server-Based Catalog** (Current Focus)
1. Design catalog.json schema
2. Build initial catalog with 5-10 titles
3. Set up GitHub Pages hosting
4. Implement catalog_manager.py (fetch, sync, SQLite storage)
5. Build manual sync UI with progress dialog

**Phase 2: UI Streamlining**
1. Remove Downloads and Filmweb tabs
2. Implement Movies/Series tabs with genre filtering
3. Build list view with metadata display
4. Implement availability status indicators
5. Add detailed 3-phase progress display
6. Add keyboard shortcuts

**Phase 3: Subtitle Improvements**
1. Fix Gemini delimiter issue (JSON array format)
2. Improve error handling and retry logic
3. Implement permanent caching
4. Optimize batch sizes

**Phase 4: Voice-Over Feature**
1. Research and select TTS service
2. Prototype audio ducking
3. Implement TTS generation and caching
4. Build audio mixing pipeline
5. Add cost tracking

## Known Issues & Refactoring Targets

**Bugs**:
- Gemini translation uses '|' delimiter which conflicts with .srt formatting → switch to JSON array
- Subtitle file handling logic is scattered → centralize in dedicated module

**Code Quality**:
- Movie player signal complexity is high → refactor with mediator pattern
- Daemon threads everywhere → consider async/await or task queue
- No error tracking or logging framework → add structured logging

**Technical Debt**:
- No tests or linting → add pytest + pytest-qt + ruff
- Hard-coded constants scattered in files → centralize in config.py
- No retry/backoff utilities → create reusable decorators

**Features to Remove**:
- Downloads tab → replaced by catalog workflow
- Filmweb tab → replaced by curated catalog
- Current torrent search UI → replaced by catalog magnet links

## Cost Management

**Caching Strategy**:
- Never re-translate subtitles (cache permanently)
- Never re-generate TTS audio (cache permanently)
- Store cached files alongside video files on HDD

**Monitoring**:
- Track Gemini API calls and estimated costs
- Track TTS API usage and costs
- Show cumulative costs in settings page
- Alert when approaching monthly budget threshold

**Optimization**:
- Use JSON array format for efficient batching
- Batch size optimization: balance accuracy vs cost (currently 10, may increase)
- Prefer larger batches when accuracy permits

## Configuration Notes

### Locale & Translation

- Hardcoded to `pl_PL` (Polish-only by design)
- If supporting other languages in future, make locale configurable
- Translation files in `translations/` directory

### UI Scaling

- Default scale factor: 1.5x (main.py:30)
- Optimized for 1080p display on Raspberry Pi
- Adjust for different screen resolutions

### VLC Integration

- VLC handles subtitle encoding detection (don't pre-process)
- VLC handles playback errors (don't wrap too heavily)
- Subtitle track loading: use VLC's native add_slave() method

## File Organization

```
hackflix/
├── main.py                          # Entry point
├── source/
│   ├── movie_player.py              # Main window and playback control
│   ├── video_frame.py               # VLC video widget
│   ├── file_browser.py              # Legacy library tab (will be replaced)
│   ├── downloads_tab.py             # Legacy downloads UI (will be removed)
│   ├── web_browser_tab.py           # Legacy Filmweb browser (will be removed)
│   ├── torrent_manager.py           # Torrent search and download
│   ├── subtitle_manager.py          # OpenSubtitles API client
│   ├── subtitle_dialog.py           # Subtitle search results UI
│   ├── translation_manager.py       # Gemini translation client
│   ├── dark_theme.qss               # Dark theme stylesheet
│   └── [NEW] catalog_manager.py     # Catalog sync and SQLite (TODO)
│   └── [NEW] catalog_tab.py         # Movies/Series catalog UI (TODO)
├── translations/
│   ├── pl_PL.ts                     # Polish translation source
│   └── pl_PL.qm                     # Compiled translation
├── .env                             # API keys (not in repo)
├── pyproject.toml                   # Python dependencies
├── REQUIREMENTS.md                  # Detailed requirements document
└── CLAUDE.md                        # This file
```
