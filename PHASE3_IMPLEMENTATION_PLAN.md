# Phase 3: Download Pipeline Integration - Implementation Plan

## Overview

Phase 3 implements the complete download-to-play pipeline for HackFlix, transforming it from a catalog viewer into a fully functional movie/series player. This phase integrates torrent downloading, subtitle management, translation, and playback into a seamless 3-click workflow.

**Status**: ⏳ Not Started
**Estimated Duration**: 5-7 days
**Dependencies**: Phase 1 (Catalog), Phase 2 (UI) complete

---

## Goals

### Primary Objectives
1. **Download Pipeline**: Implement automated video + subtitle + translation workflow
2. **Progress Tracking**: Real-time 3-phase progress display with persistence
3. **Playback Integration**: Connect catalog items to VLC player with subtitle loading
4. **Watch History**: Track series episode progress and auto-resume
5. **Error Recovery**: Robust error handling with retry mechanisms

### Success Criteria
- ✅ User can download movie/series from catalog with single click
- ✅ Progress shows accurate 3-phase breakdown (video/subtitles/translation)
- ✅ Downloads persist across app restarts
- ✅ Play button launches video with Polish subtitles auto-loaded
- ✅ Series episodes track watch progress and resume position
- ✅ Failed downloads show clear errors with retry option

---

## Architecture Overview

### Download Pipeline Flow

```
User clicks "Download"
    ↓
[Phase 1: Video Download (0-33%)]
    • Start torrent download via TorrentDownloader
    • Monitor progress, update database
    • Detect video file completion
    ↓
[Phase 2: Subtitle Download (34-66%)]
    • Extract filename, detect season/episode
    • Search OpenSubtitles API for match
    • Download best match (prefer English for translation)
    ↓
[Phase 3: Translation (67-100%)]
    • Translate subtitle to Polish via Gemini API
    • Save translated .srt file
    • Mark as "ready"
    ↓
[Complete: Ready to Play]
```

### Key Components

**DownloadOrchestrator** (new)
- Central coordinator for download pipeline
- Manages state transitions (video → subtitles → translation)
- Emits progress signals
- Handles error recovery

**DownloadStateManager** (new)
- SQLite interface for download_state table
- CRUD operations for download tracking
- Query methods for UI display

**TorrentDownloader** (existing)
- Already implemented in source/torrent_manager.py
- Wraps libtorrent for torrent downloads
- Emits progress signals

**SubtitleManager** (existing)
- Already implemented in source/subtitle_manager.py
- OpenSubtitles API client
- Search and download methods

**SubtitleTranslator** (existing)
- Already implemented in source/translation_manager.py
- Gemini API client for translation
- Batch processing with retry logic

---

## Phase 3a: Download Orchestration

**Status**: ⏳ Pending
**Estimated Duration**: 2 days

### Goals
- Implement DownloadOrchestrator to coordinate pipeline
- Integrate TorrentDownloader, SubtitleManager, SubtitleTranslator
- Handle state transitions between phases

### Tasks

⬜ **Create DownloadOrchestrator Class**:
- File: `source/download_orchestrator.py`
- Responsibilities:
  - Coordinate 3-phase download pipeline
  - Emit progress signals for UI updates
  - Handle state persistence to database
  - Support pause/resume functionality
- Signals:
  - `progress_updated(item_id, phase, overall_progress, phase_progress)`
  - `phase_changed(item_id, phase_name)`
  - `download_complete(item_id, video_path, subtitle_path)`
  - `download_failed(item_id, phase, error_message)`

⬜ **Create DownloadStateManager Class**:
- File: `source/download_state_manager.py`
- Responsibilities:
  - SQLite interface for download_state table
  - CRUD operations: create, update, get, delete
  - Query methods: get_all_downloading(), get_by_status()
  - Progress update methods
- Methods:
  - `create_download(item_id, item_type, magnet_link)`
  - `update_progress(item_id, phase, progress)`
  - `set_status(item_id, status)`
  - `get_download_state(item_id)`
  - `get_all_active_downloads()`

⬜ **Integrate TorrentDownloader**:
- Instantiate TorrentDownloader in DownloadOrchestrator
- Map magnet link to torrent download
- Monitor torrent progress (emit updates every 1-2 seconds)
- Detect video file completion (check for .mp4, .mkv, .avi)
- Handle torrent errors (no seeders, network issues)

⬜ **Integrate SubtitleManager**:
- Trigger subtitle search when video completes
- Extract filename, detect season/episode using SEASON_EPISODE_REGEX
- Search OpenSubtitles API with cleaned query
- Download best match (prefer English for translation source)
- Handle subtitle search failures (no results, API errors)

⬜ **Integrate SubtitleTranslator**:
- Trigger translation when subtitle downloads
- Use existing batch translation logic
- Monitor translation progress (batch N of M)
- Save translated subtitle as `{filename}-pl.srt`
- Handle translation failures (API errors, quota exceeded)

⬜ **Implement State Transitions**:
- Track current phase: 'video', 'subtitles', 'translation'
- Update database on phase change
- Calculate overall progress:
  - Video: 0-33%
  - Subtitles: 34-66%
  - Translation: 67-100%
- Emit signals for UI updates

⬜ **Add Pause/Resume Support**:
- Pause all active downloads on app close
- Save torrent resume data to database
- Restore downloads on app reopen
- Resume from last saved state

### Files to Create
- `source/download_orchestrator.py` (~500 lines)
- `source/download_state_manager.py` (~300 lines)

### Files to Modify
- `source/movie_player.py` - Add download orchestrator initialization
- `source/catalog_manager.py` - Add download state query methods

### Testing Checklist
- [ ] Download orchestrator instantiates successfully
- [ ] Torrent download starts and shows progress
- [ ] Video file detected when download completes
- [ ] Subtitle search triggered automatically
- [ ] Translation triggered after subtitle download
- [ ] Overall progress calculated correctly (0-100%)
- [ ] State persisted to database
- [ ] Pause/resume works across app restarts

---

## Phase 3b: Progress Display Integration

**Status**: ⏳ Pending
**Estimated Duration**: 1.5 days

### Goals
- Connect DownloadOrchestrator to ThreePhaseProgressBar
- Update catalog UI to show live progress
- Handle progress updates efficiently

### Tasks

⬜ **Update CatalogTab for Progress Display**:
- Connect DownloadOrchestrator signals to catalog UI
- When progress_updated signal received, update list item
- Show ThreePhaseProgressBar for items with status='downloading'
- Update status badges in real-time

⬜ **Integrate ThreePhaseProgressBar**:
- Replace simple progress text with ThreePhaseProgressBar widget
- Show phase breakdown:
  - Video: 0-33% (green when active)
  - Subtitles: 34-66% (green when active)
  - Translation: 67-100% (green when active)
- Highlight current phase
- Show detailed sub-progress: "Video: 15% (of 33%), Subtitles: 0%, Translation: 0%"

⬜ **Optimize Progress Updates**:
- Throttle UI updates (max 2-3 per second)
- Batch database writes (every 5 seconds or on phase change)
- Use QTimer to coalesce rapid updates
- Avoid blocking main thread with progress calculations

⬜ **Handle Multiple Concurrent Downloads**:
- Support 2-3 concurrent downloads (configurable)
- Queue additional downloads beyond limit
- Show queue position in UI: "Queued (position 2)"
- Auto-start next download when slot becomes available

⬜ **Add Download Controls**:
- Pause button for active downloads
- Resume button for paused downloads
- Cancel button (with confirmation dialog)
- Retry button for failed downloads

### Files to Modify
- `source/catalog_tab.py` - Add progress display integration
- `source/download_orchestrator.py` - Add pause/cancel methods
- `source/movie_player.py` - Connect orchestrator signals

### Testing Checklist
- [ ] Progress bar appears when download starts
- [ ] 3-phase breakdown shows correctly
- [ ] Progress updates smoothly without lag
- [ ] Current phase highlighted
- [ ] Multiple downloads tracked independently
- [ ] Pause/resume works correctly
- [ ] Cancel removes download from list
- [ ] Retry button works for failed downloads

---

## Phase 3c: Play Functionality & Watch History

**Status**: ⏳ Pending
**Estimated Duration**: 2 days

### Goals
- Implement play functionality for downloaded items
- Load video and subtitles in VLC player
- Track watch history for series episodes
- Auto-resume from last position

### Tasks

⬜ **Implement Play from Catalog**:
- Handle play_requested signal from CatalogTab
- Check download_state: only play if status='ready'
- For movies:
  - Query download_state for video_path
  - Load video in VLC player
  - Load translated subtitle (`-pl.srt`)
- For series episodes:
  - Show episode selection dialog (already exists)
  - Query download_state for season
  - Find episode file in season folder
  - Load video + subtitle

⬜ **Subtitle Auto-Loading**:
- When playing video, search for matching subtitle:
  - Priority 1: `{filename}-pl.srt` (translated)
  - Priority 2: `{filename}.pl.srt` (Polish)
  - Priority 3: Any .srt with matching basename
- Use VLC's `add_slave()` method to load subtitle
- Set subtitle track active by default

⬜ **Implement Watch History Tracking**:
- On video play start:
  - Detect if file is series episode (check database)
  - Create watch_history entry if not exists
- During playback:
  - Save position every 10 seconds to database
  - Update `last_position`, `last_watched` timestamp
- On video stop/close:
  - Save final position
  - If >90% watched, mark `completed=TRUE`

⬜ **Auto-Resume for Series**:
- When playing series episode:
  - Check watch_history for last_position
  - If position > 0 and not completed:
    - Show "Resume from XX:XX" option
    - Auto-resume if user confirms
  - If completed, start from beginning

⬜ **Next Episode Auto-Advance**:
- When episode completes (>90% watched):
  - Check if next episode available
  - Show "Play Next Episode" notification
  - Auto-advance after 5 seconds (or user skip)
  - Continue to next episode seamlessly

⬜ **Update Series Navigation Dialog**:
- Show watch progress indicators:
  - `[●50%]` - In progress (resume available)
  - `[✓100%]` - Completed
  - No marker - Not started
- Auto-select first unwatched episode
- Highlight currently playing episode

### Files to Modify
- `source/movie_player.py` - Implement play handlers, watch history tracking
- `source/catalog_tab.py` - Update play_requested signal handler
- `source/series_navigation.py` - Add watch progress indicators
- `source/catalog_manager.py` - Add watch history query methods

### New Methods in MoviePlayerApp
- `play_catalog_item(item_id, item_type)`
- `play_video_file(video_path, subtitle_path=None, resume_position=0)`
- `update_watch_history()`
- `show_next_episode_notification()`

### Database Integration
- Use `watch_history` table for episode tracking
- Query: `SELECT * FROM watch_history WHERE series_id=? AND season_number=? AND episode_number=?`
- Update: `UPDATE watch_history SET last_position=?, last_watched=? WHERE ...`
- Mark complete: `UPDATE watch_history SET completed=TRUE WHERE ...`

### Testing Checklist
- [ ] Play button works for movies with status='ready'
- [ ] Video loads in VLC player
- [ ] Polish subtitle auto-loads
- [ ] Watch history created on play start
- [ ] Position saved every 10 seconds
- [ ] Auto-resume prompt shown for incomplete episodes
- [ ] Next episode notification shown on completion
- [ ] Series navigation shows watch progress indicators

---

## Phase 3d: Error Handling & Recovery

**Status**: ⏳ Pending
**Estimated Duration**: 1.5 days

### Goals
- Robust error handling at each phase
- User-friendly error messages
- Automatic retry with exponential backoff
- Manual retry option

### Tasks

⬜ **Implement Phase-Specific Error Handling**:

**Video Download Errors**:
- No seeders available:
  - Show: "No seeders available for this torrent"
  - Action: Mark as failed, allow retry
- Network connection lost:
  - Auto-retry after 30s, 1m, 2m (exponential backoff)
  - Max 3 auto-retries
- Disk space insufficient:
  - Show: "Insufficient disk space (need X GB, have Y GB)"
  - Action: Pause download, show warning

**Subtitle Search Errors**:
- No subtitles found:
  - Show: "No subtitles found for this video"
  - Action: Mark as translation_failed, allow manual subtitle upload
- API quota exceeded:
  - Show: "OpenSubtitles quota exceeded (limit: X/day)"
  - Action: Pause subtitle phase, retry tomorrow
- API timeout:
  - Auto-retry after 10s, 30s, 1m
  - Max 3 retries

**Translation Errors**:
- Gemini API quota exceeded:
  - Show: "Translation quota exceeded for today"
  - Action: Mark as translation_failed, retry tomorrow
- Translation quality low (count mismatch):
  - Auto-retry with smaller batch size
  - Fall back to single-entry translation
- API timeout:
  - Auto-retry after 10s, 30s, 1m
  - Max 3 retries

⬜ **Implement Retry Mechanisms**:
- Automatic retry with exponential backoff:
  - Retry intervals: 10s, 30s, 1m, 2m, 5m
  - Max retries per phase: 3
  - Reset retry count on phase change
- Manual retry button:
  - Resume from failed phase
  - Reset error state
  - Start download from last successful checkpoint

⬜ **Add Error State Persistence**:
- Store error details in download_state table:
  - `error_message`: User-friendly message
  - `error_details`: Full traceback for debugging
  - `failed_at`: Timestamp of failure
- Query failed downloads:
  - `SELECT * FROM download_state WHERE status='failed'`
- Allow retry from database state

⬜ **Implement Progressive Disclosure for Errors**:
- Simple message shown by default: "Download failed: No seeders"
- "Show Details" button reveals:
  - Full error message
  - Phase where failure occurred
  - Timestamp
  - Retry count
  - Suggested action

⬜ **Add Download Validation**:
- Video file validation:
  - Check file exists and size > 0
  - Verify video codec (using ffprobe or mediainfo)
  - Warn if codec unsupported by VLC
- Subtitle file validation:
  - Check .srt syntax (parse with pysrt)
  - Verify encoding (UTF-8)
  - Warn if subtitle damaged

⬜ **Implement Download Cleanup**:
- Clean up partial downloads on failure
- Remove incomplete video files (configurable)
- Keep subtitle files (can be reused)
- Clear torrent resume data for failed downloads

### Files to Modify
- `source/download_orchestrator.py` - Add error handling, retry logic
- `source/download_state_manager.py` - Add error state methods
- `source/catalog_tab.py` - Show error messages, retry button

### New Classes
- `DownloadError` (exception class)
- `RetryStrategy` (configurable retry logic)

### Testing Checklist
- [ ] Network errors trigger auto-retry
- [ ] Max retries respected (no infinite loops)
- [ ] Manual retry button works
- [ ] Error messages are user-friendly
- [ ] "Show Details" reveals full error info
- [ ] Failed downloads can be deleted
- [ ] Cleanup removes partial files

---

## Configuration & Settings

### Download Settings (Phase 3+)

Add to settings dialog (future work):
- Download directory (default: ~/Videos/HackFlix)
- Max concurrent downloads (default: 2)
- Max download speed (default: unlimited)
- Auto-retry enabled (default: true)
- Delete failed downloads (default: false)
- Subtitle search language priority (default: en, pl)

### API Rate Limiting

**OpenSubtitles**:
- Free tier: 5 downloads/day
- Logged in: 10+ downloads/day
- Track usage in api_usage table
- Show quota warning at 80%

**Gemini API**:
- Free tier: 15 requests/minute, 1500/day
- Batch size: 10 entries (configurable)
- Track costs in api_usage table
- Show monthly cost projection

---

## Database Integration

### Download State Queries

**Create new download**:
```sql
INSERT INTO download_state (id, type, status, progress, phase)
VALUES (?, ?, 'downloading', 0.0, 'video');
```

**Update progress**:
```sql
UPDATE download_state
SET progress = ?, phase_progress = ?, video_progress = ?, updated_at = CURRENT_TIMESTAMP
WHERE id = ?;
```

**Set phase**:
```sql
UPDATE download_state
SET phase = ?, phase_progress = 0.0, updated_at = CURRENT_TIMESTAMP
WHERE id = ?;
```

**Mark complete**:
```sql
UPDATE download_state
SET status = 'ready', progress = 100.0, completed_at = CURRENT_TIMESTAMP
WHERE id = ?;
```

**Mark failed**:
```sql
UPDATE download_state
SET status = 'failed', error_message = ?, error_details = ?, failed_at = CURRENT_TIMESTAMP
WHERE id = ?;
```

**Get active downloads**:
```sql
SELECT * FROM download_state
WHERE status = 'downloading'
ORDER BY started_at ASC;
```

### Watch History Queries

**Create/update watch position**:
```sql
INSERT OR REPLACE INTO watch_history
(series_id, season_number, episode_number, file_path, last_position, duration, last_watched)
VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP);
```

**Get watch progress**:
```sql
SELECT * FROM watch_history
WHERE series_id = ? AND season_number = ? AND episode_number = ?;
```

**Get last watched episode**:
```sql
SELECT * FROM watch_history
WHERE series_id = ?
ORDER BY last_watched DESC
LIMIT 1;
```

**Get next unwatched episode**:
```sql
SELECT * FROM episodes
WHERE season_id = ? AND episode_number > ?
  AND NOT EXISTS (
    SELECT 1 FROM watch_history
    WHERE episode_number = episodes.episode_number AND completed = TRUE
  )
ORDER BY episode_number ASC
LIMIT 1;
```

---

## File Organization

### New Files

```
source/
├── download_orchestrator.py      # Central download coordinator (~500 lines)
├── download_state_manager.py     # SQLite interface (~300 lines)
└── [Updated] movie_player.py     # Add play handlers, watch history
└── [Updated] catalog_tab.py      # Progress display integration
└── [Updated] catalog_manager.py  # Download state queries
```

### Existing Files Used

- `source/torrent_manager.py` - TorrentDownloader class
- `source/subtitle_manager.py` - SubtitleManager class
- `source/translation_manager.py` - SubtitleTranslator class
- `source/progress_widget.py` - ThreePhaseProgressBar class
- `source/series_navigation.py` - SeasonSelectionDialog class

---

## Testing Strategy

### Unit Tests (to be added)

**DownloadOrchestrator**:
- Test state transitions (video → subtitles → translation)
- Test progress calculations
- Test error handling
- Test pause/resume

**DownloadStateManager**:
- Test CRUD operations
- Test query methods
- Test concurrent updates

**Play Functionality**:
- Test video loading
- Test subtitle auto-loading
- Test watch history tracking
- Test auto-resume

### Integration Tests

**Full Download Pipeline**:
1. Start download from catalog
2. Monitor progress through all 3 phases
3. Verify files created (video, subtitle, translated subtitle)
4. Verify database state updated
5. Verify "Play" button enabled

**Error Recovery**:
1. Simulate network failure during video download
2. Verify auto-retry triggered
3. Verify download resumes correctly
4. Verify state persisted across app restart

**Watch History**:
1. Play series episode
2. Stop midway through
3. Restart app
4. Verify resume prompt shown
5. Verify playback resumes at correct position

### Manual Testing Checklist

- [ ] Download movie from catalog
- [ ] Download series season from catalog
- [ ] Monitor progress through all phases
- [ ] Pause and resume download
- [ ] Restart app with active downloads
- [ ] Play downloaded movie
- [ ] Play series episode
- [ ] Watch episode to completion
- [ ] Verify next episode auto-advance
- [ ] Simulate network failure
- [ ] Verify error message shown
- [ ] Click retry button
- [ ] Delete failed download
- [ ] Check database state after operations

---

## Performance Considerations

### Download Performance

- **Concurrent Downloads**: Limit to 2-3 to avoid overwhelming network/disk
- **Progress Updates**: Throttle to 2-3 per second (avoid UI lag)
- **Database Writes**: Batch updates every 5 seconds (reduce I/O)
- **Torrent Settings**: Configure libtorrent for optimal speed vs. resource usage

### Memory Management

- **Subtitle Files**: Load lazily, don't keep in memory
- **Translation Batches**: Process in chunks of 10-20 entries
- **Video Files**: Stream from disk, don't buffer entire file
- **Progress Tracking**: Use lightweight signals, avoid deep copies

### Database Optimization

- **Indexes**: Already created for download_state.status, watch_history.series_id
- **Transactions**: Use transactions for multi-step updates
- **Connection Pooling**: Reuse database connections (avoid open/close overhead)

---

## Security Considerations

### Magnet Link Validation

- Verify magnet URI format before passing to libtorrent
- Check info_hash length (40 hex characters)
- Sanitize torrent name (no path traversal)

### Subtitle File Safety

- Validate .srt file syntax before loading
- Check file size (reject files >10 MB)
- Scan for malicious content (e.g., embedded scripts)

### Download Path Sanitization

- Use Path library for safe path construction
- Prevent path traversal attacks (no ../ in filenames)
- Validate file extensions (only .mp4, .mkv, .avi, .srt)

### API Key Protection

- Never log API keys
- Store API keys in .env file (not in code)
- Rotate keys if compromised

---

## Cost Management

### Gemini API Costs

**Estimated Costs**:
- Translation: ~$0.01 per subtitle (100-200 entries)
- Monthly budget: $5-10 (50-100 movies/episodes)

**Cost Optimization**:
- Cache translations permanently (never re-translate)
- Use batch processing (10 entries per request)
- Track usage in api_usage table
- Show cumulative cost in settings page
- Alert when approaching monthly budget

### OpenSubtitles API Costs

**Free Tier Limits**:
- 5 downloads/day (anonymous)
- 10-40 downloads/day (logged in)

**Cost Optimization**:
- Cache subtitles permanently
- Track quota usage
- Show quota warning at 80%

---

## Rollout Plan

### Phase 3a: Download Orchestration (Week 1)
- Days 1-2: Implement DownloadOrchestrator and DownloadStateManager
- Day 2: Integrate TorrentDownloader, SubtitleManager, SubtitleTranslator
- Day 2: Test full pipeline (video → subtitles → translation)

### Phase 3b: Progress Display (Week 1)
- Day 3: Connect orchestrator to ThreePhaseProgressBar
- Day 3: Update catalog UI for live progress
- Day 3: Test concurrent downloads

### Phase 3c: Play Functionality (Week 2)
- Day 4: Implement play handlers for movies and series
- Day 4: Add watch history tracking
- Day 5: Implement auto-resume and next episode
- Day 5: Test watch history persistence

### Phase 3d: Error Handling (Week 2)
- Day 6: Implement error handling for all phases
- Day 6: Add retry mechanisms
- Day 7: Test error recovery scenarios
- Day 7: Final integration testing

---

## Success Metrics

### User Experience Metrics
- **Time to Play**: <2 minutes from download start to first playback (for small files)
- **Success Rate**: >95% of downloads complete successfully
- **Resume Success**: 100% of paused downloads resume correctly
- **Error Clarity**: All errors show user-friendly messages

### Technical Metrics
- **Progress Accuracy**: ±2% deviation from actual progress
- **Database Writes**: <10 writes/second (avoid thrashing)
- **Memory Usage**: <200 MB additional (vs Phase 2)
- **CPU Usage**: <25% average during downloads

### Quality Metrics
- **Translation Quality**: >90% of subtitles translated correctly
- **Subtitle Sync**: >95% of subtitles in sync with video
- **Video Compatibility**: >95% of videos play in VLC

---

## Dependencies

### External Libraries
- **libtorrent**: Torrent downloading (already installed)
- **pysrt**: Subtitle parsing (already installed)
- **requests**: HTTP requests (already installed)
- **python-vlc**: VLC player bindings (already installed)

### API Dependencies
- **OpenSubtitles API**: Subtitle search and download
- **Google Gemini API**: Subtitle translation

### Internal Dependencies
- Phase 1: CatalogManager, database schema ✅
- Phase 2: CatalogTab, ThreePhaseProgressBar, SeriesNavigationDialog ✅

---

## Risk Assessment

### High Risk
1. **Torrent reliability**: No seeders = download fails
   - Mitigation: Clear error messages, allow retry, curate catalog for popular torrents
2. **API quota limits**: Could block downloads
   - Mitigation: Track usage, cache aggressively, warn users before quota exceeded

### Medium Risk
1. **Subtitle sync issues**: Subtitles out of sync with video
   - Mitigation: Test with various videos, allow manual subtitle upload
2. **Translation quality**: Gemini might produce poor translations
   - Mitigation: Review translations, allow manual editing (future)

### Low Risk
1. **Database corruption**: SQLite file corruption during writes
   - Mitigation: Use transactions, regular backups
2. **Disk space**: Running out of space during downloads
   - Mitigation: Check available space before download, show warnings

---

## Future Enhancements (Post-Phase 3)

### Phase 4: Voice-Over Generation
- TTS integration (Google Cloud TTS / Azure)
- Audio mixing with original video
- Cost tracking and budgeting

### Phase 5: Advanced Features
- Grid view for catalog
- Search within catalog
- Custom subtitle upload
- Manual translation editing
- Subtitle timing adjustment
- Multiple audio tracks
- Download queue management

### Phase 6: Performance Optimization
- Parallel torrent connections
- Predictive subtitle pre-loading
- Background translation queue
- Streaming playback (start before download completes)

---

## Implementation Timeline

| Week | Phase | Tasks | Status |
|------|-------|-------|--------|
| 1    | 3a    | Download orchestration, state management | ⏳ Pending |
| 1    | 3b    | Progress display integration | ⏳ Pending |
| 2    | 3c    | Play functionality, watch history | ⏳ Pending |
| 2    | 3d    | Error handling, testing | ⏳ Pending |

**Total Estimated Time**: 5-7 days

---

## Contact & Feedback

For questions or issues with Phase 3 implementation:
- Refer to `/home/wiktor/Work/hackflix/CLAUDE.md` for project context
- Review database schema at `source/db_schema.py`
- Check Phase 1-2 plans for completed features

**Last Updated**: 2026-01-07 by Claude Code
**Status**: ⏳ Planning Complete, Ready for Implementation
