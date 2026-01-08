# Download System V2 - Migration Guide

## Overview

This guide explains how to migrate from the old sequential download system (V1) to the new parallel download system (V2).

## Key Improvements in V2

### 1. **Parallel Downloads for Movies**
- Video and subtitle downloads happen simultaneously
- Faster overall completion time
- Two separate progress bars in UI

### 2. **Smart Resume Logic**
- On download start/resume, checks what's already completed:
  - Is video file present and valid? → Skip video download
  - Is subtitle file present? → Skip subtitle download
  - Is translation needed and translated file present? → Skip translation
- Resumes from first incomplete component

### 3. **Component-Level Status Tracking**
- `video_status`: pending, downloading, completed, failed
- `subtitle_status`: pending, downloading, completed, failed, not_needed
- `translation_status`: pending, translating, completed, failed, not_needed

### 4. **Subtitle Queue for Series (5/day limit)**
- Automatically queues subtitle downloads for all episodes
- Respects OpenSubtitles 5 downloads/day limit
- Handles quota exhaustion gracefully (pauses queue until next day)

### 5. **Fixed Threading Issues**
- QTimer objects created in correct thread
- Proper thread-safe signal connections

## Migration Steps

### Step 1: Run Database Migration

```bash
python migrate_download_state.py
```

This adds the following columns to `download_state` table:
- `video_status` TEXT
- `subtitle_status` TEXT
- `translation_status` TEXT
- `subtitle_quota_date` TEXT
- `subtitle_quota_used` INTEGER

### Step 2: Replace DownloadOrchestrator Import

**Old code (movie_player.py or catalog_tab.py):**
```python
from source.download_orchestrator import DownloadOrchestrator
from source.download_state_manager import DownloadStateManager
```

**New code:**
```python
from source.download_orchestrator_v2 import DownloadOrchestratorV2
from source.download_state_manager_v2 import DownloadStateManagerV2
```

### Step 3: Update Signal Connections

**Old signals (V1):**
```python
orchestrator.progress_updated.connect(self.on_progress_updated)
orchestrator.phase_changed.connect(self.on_phase_changed)
orchestrator.download_complete.connect(self.on_download_complete)
orchestrator.download_failed.connect(self.on_download_failed)
```

**New signals (V2):**
```python
# Dual progress bars
orchestrator.video_progress_updated.connect(self.on_video_progress_updated)
orchestrator.subtitle_progress_updated.connect(self.on_subtitle_progress_updated)

# Status changes
orchestrator.video_status_changed.connect(self.on_video_status_changed)
orchestrator.subtitle_status_changed.connect(self.on_subtitle_status_changed)

# Completion/failure
orchestrator.download_complete.connect(self.on_download_complete)
orchestrator.download_failed.connect(self.on_download_failed)

# Quota exceeded (for series)
orchestrator.subtitle_quota_exceeded.connect(self.on_quota_exceeded)
```

### Step 4: Update UI to Show Dual Progress Bars

**Old UI (single progress bar):**
```python
def on_progress_updated(self, item_id, phase, overall_progress, phase_progress):
    # Update single progress bar
    self.progress_bar.setValue(int(overall_progress))
    self.status_label.setText(f"{phase}: {phase_progress:.0f}%")
```

**New UI (dual progress bars):**
```python
def on_video_progress_updated(self, item_id, progress):
    # Update video progress bar
    self.video_progress_bar.setValue(int(progress))
    self.video_label.setText(f"Video: {progress:.0f}%")

def on_subtitle_progress_updated(self, item_id, progress):
    # Update subtitle progress bar (includes translation if needed)
    self.subtitle_progress_bar.setValue(int(progress))
    self.subtitle_label.setText(f"Subtitles: {progress:.0f}%")
```

### Step 5: Handle Resume on Double-Click

**Example: Resume download when user double-clicks unfinished download**
```python
def on_item_double_clicked(self, item_id):
    """Handle double-click on catalog item"""

    # Get item metadata from catalog
    movie = self.catalog_manager.get_movie_by_id(item_id)

    if not movie:
        return

    # Start or resume download (V2 orchestrator handles smart resume automatically)
    self.orchestrator.start_download(
        item_id=item_id,
        item_type='movie',
        magnet_link=movie['magnet_link'],
        title=movie['title'],
        metadata=movie  # Include subtitle config
    )
```

The V2 orchestrator will automatically:
1. Check if video is already downloaded → skip if complete
2. Check if subtitle is already downloaded → skip if complete
3. Check if translation is already done → skip if complete
4. Resume from the first incomplete component

## API Changes

### DownloadOrchestratorV2 Constructor

```python
orchestrator = DownloadOrchestratorV2(
    state_manager=state_manager_v2,
    subtitle_manager=subtitle_manager,
    translator=translator,
    download_dir="~/Videos/HackFlix"
)
```

### Signal Signatures

**Video Progress:**
```python
video_progress_updated = pyqtSignal(str, float)  # (item_id, progress 0-100)
```

**Subtitle Progress:**
```python
subtitle_progress_updated = pyqtSignal(str, float)  # (item_id, progress 0-100)
# Note: For items needing translation:
# - 0-50%: Subtitle download
# - 50-100%: Translation
```

**Status Changes:**
```python
video_status_changed = pyqtSignal(str, str)  # (item_id, status)
subtitle_status_changed = pyqtSignal(str, str)  # (item_id, status)
```

**Completion:**
```python
download_complete = pyqtSignal(str, str, str)  # (item_id, video_path, subtitle_path)
```

**Failure:**
```python
download_failed = pyqtSignal(str, str, str)  # (item_id, component, error_message)
# component: 'video', 'subtitle', or 'translation'
```

**Quota Exceeded:**
```python
subtitle_quota_exceeded = pyqtSignal(int)  # (remaining_quota)
```

## Quota Management for Series

When downloading a series season:

1. **Video torrent downloads** (all episodes at once)
2. **Subtitle queue is created** for all episodes
3. **Up to 5 subtitles download** immediately (daily quota)
4. **Remaining subtitles queued** for next day
5. **User notified** when quota is exceeded

**Handle quota exceeded:**
```python
def on_quota_exceeded(self, remaining):
    QMessageBox.information(
        self,
        "Subtitle Quota Exceeded",
        f"You've reached the daily subtitle download limit (5/day).\n"
        f"Remaining subtitles will be downloaded tomorrow.\n\n"
        f"Quota remaining today: {remaining}"
    )
```

## Backward Compatibility

The V2 system reads from the same `download_state` table as V1. After running the migration:

- **Existing downloads** are automatically migrated
- **Old V1 code** will continue to work (ignores new columns)
- **New V2 code** provides enhanced functionality

However, **DO NOT run V1 and V2 orchestrators simultaneously** - they will conflict.

## Testing Checklist

### Movies
- [PENDING] Start new movie download → verify video + subtitle download in parallel
- [PENDING] Pause app during video download → restart → verify video resumes
- [PENDING] Pause app during subtitle download → restart → verify subtitle resumes
- [PENDING] Pause app during translation → restart → verify translation resumes
- [PENDING] Download movie with `needs_translation: false` → verify translation skipped
- [PENDING] Download movie with no subtitle_file_id → verify subtitle skipped

### Series
- [PENDING] Start season download → verify all episodes added to subtitle queue
- [PENDING] Download season with >5 episodes → verify only 5 subtitles download today
- [PENDING] Verify quota exceeded message shown
- [PENDING] Resume next day → verify remaining subtitles download

### Resume Logic
- [PENDING] Manually download video file → start download → verify video skipped
- [PENDING] Manually download subtitle → start download → verify subtitle skipped
- [PENDING] Manually translate subtitle → start download → verify translation skipped

## Troubleshooting

### Issue: "Quota exceeded" but I haven't downloaded anything today

**Solution:** Quota is tracked by date. If the `subtitle_quota_date` column has an old date, the quota will reset automatically. Check database:

```sql
SELECT subtitle_quota_date, subtitle_quota_used
FROM download_state
WHERE subtitle_quota_date IS NOT NULL
LIMIT 1;
```

If showing old date, manually reset:
```sql
UPDATE download_state
SET subtitle_quota_date = NULL, subtitle_quota_used = 0;
```

### Issue: Download shows as "downloading" but nothing happens

**Solution:** This means the orchestrator crashed or was not properly initialized. Check:

1. Is `DownloadOrchestratorV2` instance created?
2. Are signals connected?
3. Check error.log for Python exceptions

To reset:
```python
state_manager.set_status(item_id, 'available')
```

### Issue: Video completes but subtitle doesn't start

**Solution:** Check if subtitle_file_id is present in metadata. If missing, subtitle download will be skipped.

```python
movie = catalog_manager.get_movie_by_id(item_id)
print(movie.get('subtitle'))  # Should show file_id, language, needs_translation
```

## File Structure

```
source/
├── download_orchestrator.py           # OLD V1 (deprecated)
├── download_orchestrator_v2.py        # NEW V2 (use this)
├── download_state_manager.py          # OLD V1 (deprecated)
├── download_state_manager_v2.py       # NEW V2 (use this)
├── subtitle_manager.py                # Unchanged
└── translation_manager.py             # Unchanged

migrate_download_state.py              # Migration script (run once)
```

## Next Steps

1. Run migration script
2. Update imports in `movie_player.py` or `catalog_tab.py`
3. Update signal connections
4. Update UI to show dual progress bars
5. Test with a movie download
6. Test with a series download (>5 episodes)
7. Test resume functionality

## Notes

- V1 orchestrator can be safely deleted after migration is complete
- Both V1 and V2 can coexist during transition period (but don't run both at once)
- Migration is backward compatible - V1 code will continue to work
- Subtitle queue is automatic - no manual intervention needed
- Progress is persisted to database - survives app restarts
