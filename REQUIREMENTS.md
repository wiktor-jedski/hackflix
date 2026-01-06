# HackFlix - Requirements & Design Document

## Project Vision

A streamlined PyQt5-based movie player for Raspberry Pi 5 designed for Polish-speaking users. The app provides a curated catalog of movies and series with automated download, subtitle translation, and (planned) TTS voice-over generation. Optimized for wireless keyboard navigation and non-technical users.

## Core Principles

- **Minimize clicks**: 3-click workflow (Select → Download → Play)
- **Polish-only focus**: All UI and subtitles in Polish
- **Local-first architecture**: Works offline after initial catalog sync
- **Automated pipeline**: Video + subtitles + translation + voiceover packaged together
- **Small curated catalog**: 50-200 high-quality titles, starting with 5-10 favorites

## Hardware & Environment

- **Platform**: Raspberry Pi 5
- **Storage**: External HDD (always connected)
- **Display**: 1080p via HDMI
- **Audio**: HDMI output
- **OS**: Raspbian or DietPi
- **Input**: Wireless keyboard (not IR remote)
- **Python**: 3.13+ with uv package manager

## Architecture Overview

### Server-Based Catalog System

**Catalog Server**:
- Static `catalog.json` file hosted on GitHub Pages
- Built on top of existing metadata APIs (TMDB/IMDb/OMDb)
- Contains: title, year, genre, description, magnet link, file size, subtitle languages
- Includes timestamp field for version tracking (`last_updated`)
- Small curated selection (50-200 titles) based on personal favorites + high ratings

**Local Database**:
- SQLite database for offline-first operation
- Stores catalog data, download state, watch history
- Manual sync control: user triggers "Update catalog" via UI
- Incremental smart sync: fetches new titles + changed entries since last sync timestamp
- Progress dialog shown during sync

**Series Structure**:
- Each season has separate magnet link entry in catalog
- Download full season torrents (all episodes together)
- Track last watched episode per series (season + episode + timestamp)
- Playback position stored in SQLite for series only (movies restart from beginning)

### Download Workflow

**3-Click User Journey**:
1. **Select**: User clicks movie/series from catalog
2. **Download**: Explicit download button starts the process
3. **Play**: Play button appears when everything is ready

**Download Process**:
- Downloads consist of 3 phases (equal thirds): video (0-33%), subtitles (34-66%), translation (67-100%)
- Display detailed sub-progress: "Video: 15% (of its 33%), Subtitles: 0%, Translation: 0%"
- Remain in "Downloading" state until video + subtitles + translation all complete
- Wait for all components before allowing playback (no partial playback)
- Allow 2-3 concurrent downloads
- Pause downloads on app close, resume from saved progress on reopen
- Try download and fail gracefully if no seeders found (timeout-based detection)

**Download Organization**:
- Torrents download to user-selected directory on external HDD
- Keep folder structure intact (no auto-extraction)
- Library does recursive search through folders
- Full season torrents for series (one magnet per season)

### Subtitle & Translation Pipeline

**Subtitle Acquisition**:
- Search OpenSubtitles.com API by video filename
- Use best match score from API for selection
- Download .srt files to video directory
- VLC handles subtitle encoding detection (no pre-processing)
- Always prefer -pl (Polish translated) subtitles when multiple .srt files match

**Translation Process**:
- Google Gemini API for English → Polish translation
- Use JSON array format (not delimited strings) to avoid '|' character conflict with .srt formatting
- Batch size configurable (currently 10 subtitle entries)
- Trust Gemini's line break formatting (don't force original breaks)
- 3 retry attempts on transient errors, then mark as failed
- Cache translated subtitles permanently (never re-translate)
- Saved as `{filename}-pl.srt`

**Translation Failure Handling**:
- Mark download as "Translation failed" state
- User can manually retry translation
- Progressive disclosure: simple error message + "Show details" for technical info

### Voice-Over Feature (Research Phase)

**Current Status**: Needs research and prototyping

**Planned Approach**:
- Cloud TTS service (Google Cloud TTS / Amazon Polly / Azure - not decided)
- Client generates voiceover on-demand when user first plays movie
- Polish language voices (high quality neural/WaveNet models)
- Cache generated TTS audio permanently to avoid repeated API calls
- Audio ducking: lower original audio volume during dialogue (implementation TBD)
- Mixing approach not yet researched (VLC filters vs pre-processed file vs dual tracks)

**Cost Management**:
- Cache all generated voiceover tracks permanently
- Monthly budget alerts for API usage
- Display cumulative API costs in settings page
- Optimize batch operations to minimize API calls

## User Interface Design

### Tab Structure

**Two main tabs**:
1. **Movies**: Curated movie catalog
2. **Series**: Curated TV series catalog

**Remove current tabs**: Downloads, Filmweb (workflow streamlined)

### Catalog Display

**Layout**: List view with metadata
- Rows showing: poster thumbnail + title + genre + year + availability status
- Simple genre tabs for filtering (Action, Comedy, Drama, Sci-Fi, etc.)
- Poster images from TMDB/IMDb URLs, cached on-demand by client

**Availability Status States**:
- **Download available**: Movie in catalog with working magnet
- **Downloading**: In progress (0-100% with phase details)
- **Ready**: Fully downloaded with translated subtitles
- **Unavailable**: Hide from catalog entirely (only show available movies)

**Failed States**:
- **Download failed**: No seeders or network error
- **Translation failed**: Gemini API error or quota exceeded

### Navigation & Controls

**Keyboard Shortcuts**:
- **Playback controls**: Space = play/pause, Left/Right = seek, F = fullscreen
- **Navigation**: Tab/Arrow keys for browsing, Enter = select, Esc = back
- **Quick actions**: D = download selected, S = search, U = update catalog

**Fullscreen Mode**:
- Steal all keyboard input for playback controls
- No tab navigation available during fullscreen
- Double-click video or F key to toggle fullscreen

**Cursor Behavior**:
- Auto-hide after 3 seconds of inactivity during video playback
- Show on any mouse movement or keyboard activity

### Functionality

**Delete Movies**:
- Context menu "Delete" option with confirmation dialog
- Removes video + subtitle files + cached voiceover + torrent data
- Preserves watch history (series episode tracking)

**Series Episode Tracking**:
- Remember last watched episode (stored in SQLite)
- Auto-resume at exact timestamp within episode
- Display seasons after clicking series
- Display episodes after clicking season

## Technical Implementation Details

### API Configuration

**Required API Keys** (.env file):
```
OPENSUBTITLES_API_KEY=required
OPENSUBTITLES_USERNAME=optional (>5 downloads/day)
OPENSUBTITLES_PASSWORD=optional
GEMINI_API_KEY=required
# TTS_API_KEY=required (when voiceover implemented)
```

**Startup Behavior**:
- Block app launch if required API keys missing
- Show error dialog: "Configuration required" and exit
- Forces proper setup before first use

### Error Handling

**Network Failures**:
- Auto-retry silently with exponential backoff
- Show success/failure toast when resolved
- Queue operations for retry on reconnect

**API Errors**:
- Progressive disclosure: simple message + "Show details" button for technical info
- Gemini translation: 3 retries then mark as failed
- OpenSubtitles quota: show quota info signal when available

**Edge Cases**:
- HDD disconnection during playback: won't happen in practice (HDD always connected)
- VLC playback errors: let VLC handle natively
- Encoding issues: VLC handles subtitle encoding detection

### Localization

- Hardcoded to Polish locale (`pl_PL`)
- All UI strings use `self.tr()` for translation
- Load translations from `translations/pl_PL.qm`
- Apply dark theme from `source/dark_theme.qss`
- UI scale factor: 1.5x (configured in main.py)

### Performance & State

**Download Persistence**:
- Save torrent progress to disk (libtorrent handles resume)
- Pause all downloads on app close
- Resume from saved state on app reopen
- SQLite stores download state, watch history, catalog cache

**Concurrent Operations**:
- 2-3 concurrent torrent downloads allowed
- Parallel subtitle search/download per video
- Background translation processing with progress signals

## Development Priorities

### Phase 1: Server-Based Catalog (Current Focus)
1. Design and implement catalog.json schema
2. Build initial catalog with 5-10 favorite titles
3. Set up GitHub Pages hosting
4. Implement client-side catalog sync with SQLite storage
5. Build manual sync UI with progress dialog

### Phase 2: UI Streamlining
1. Remove Downloads and Filmweb tabs
2. Implement Movies/Series tab structure
3. Build list view with metadata display
4. Add genre filtering tabs
5. Implement availability status indicators
6. Add detailed progress display (3-phase with sub-progress)
7. Keyboard shortcuts for navigation and quick actions

### Phase 3: Subtitle Improvements
1. Fix Gemini prompt delimiter issue (switch to JSON array format)
2. Improve error handling and retry logic
3. Implement translation result caching
4. Optimize batch sizes for accuracy and cost

### Phase 4: Voice-Over Feature (Research Required)
1. Research and select cloud TTS service
2. Prototype audio ducking approaches
3. Implement TTS generation and caching
4. Build audio mixing pipeline
5. Add cost tracking and budget alerts

## Known Issues & Refactoring Targets

**Current Pain Points**:
- Too many manual steps to watch a movie (being addressed in Phase 2)
- Search and discovery UX is cumbersome (solved by curated catalog)
- Subtitle translation has '|' character formatting conflict (fixing with JSON array)

**Code Quality Issues**:
- Movie player signal complexity: too many signals connecting too many components, hard to follow flow
- Duplicate file handling logic: subtitle matching and .srt removal scattered across files, should be centralized
- Thread management: daemon threads everywhere, consider async patterns or task queue

**Not Implementing**:
- IMDb rating/suggestion feature: replaced by server-based curated catalog
- Filmweb browser: removed in favor of curated catalog workflow
- Auto-extraction of torrent folders: library recursive search is sufficient
- Resume for movies: only series need playback position tracking
- Multi-language support: Polish-only focus is intentional

## Cost Management Strategy

**Caching Strategy**:
- Cache all translated subtitles permanently (one-time cost per title)
- Cache all generated TTS voiceover tracks permanently
- Never re-translate or re-generate unless explicitly requested

**Monitoring & Alerts**:
- Track Gemini API call counts and estimated costs
- Track TTS API usage and costs
- Monthly budget alerts when approaching thresholds
- Display cumulative costs in settings page

**Optimization**:
- Batch Gemini operations efficiently (JSON array format)
- Minimize API calls through aggressive caching
- Use appropriate TTS voice quality tier (balance cost vs quality)

## Future Considerations

- Expand catalog to 50-200 titles over time based on usage
- Consider multi-user support with separate watch history
- Explore local TTS options for offline voiceover generation
- Add recommendation engine based on watch history
- Support for other subtitle languages (while keeping Polish UI)
