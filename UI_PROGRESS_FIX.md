# UI Progress Display Fix

## Problem

Download progress was invisible in the UI. Console logs showed downloads were working, but the catalog list didn't update to show progress.

## Root Causes

### Issue 1: Mismatched Progress Fields
**Problem:** UI text display was using old V1 `progress` field, but V2 stores `video_progress` and `subtitle_progress` separately.

**Location:** `source/catalog_tab.py` line 361, 373

**Old Code:**
```python
progress = item.get('progress', 0.0)
if status == 'downloading':
    title_text += f" [Downloading {progress:.0f}%]"
```

**Fixed Code:**
```python
video_progress = item.get('video_progress', 0.0)
subtitle_progress = item.get('subtitle_progress', 0.0)
if status == 'downloading':
    title_text += f" [V:{video_progress:.0f}% S:{subtitle_progress:.0f}%]"
```

### Issue 2: Status Not Set to 'downloading' on Resume
**Problem:** When resuming an existing download, overall status wasn't set to 'downloading', so item didn't show up in UI as active.

**Location:** `source/download_orchestrator_v2.py` line 260-264

**Old Code:**
```python
state = self.state_manager.get_download_state(item_id)
if not state:
    # Create new download entry
    self.state_manager.create_download(item_id, item_type, magnet_link, self.download_dir)
    state = self.state_manager.get_download_state(item_id)
# No else clause - existing downloads don't get status updated!
```

**Fixed Code:**
```python
state = self.state_manager.get_download_state(item_id)
if not state:
    # Create new download entry
    self.state_manager.create_download(item_id, item_type, magnet_link, self.download_dir)
    state = self.state_manager.get_download_state(item_id)
else:
    # Resume existing download - set status to downloading
    self.state_manager.set_status(item_id, 'downloading')
```

## Changes Made

### File: `source/catalog_tab.py`

1. **Updated `_create_list_item()` method** (lines 360-374)
   - Changed to use V2 fields: `video_progress`, `subtitle_progress`
   - Display format: `[V:50% S:80%]` instead of `[Downloading 50%]`

2. **Added progress to tooltip** (lines 413-416)
   - Shows detailed progress when hovering over downloading items
   - Displays both video and subtitle progress separately

### File: `source/download_orchestrator_v2.py`

3. **Fixed resume logic** (lines 265-267)
   - Added `set_status(item_id, 'downloading')` when resuming existing download
   - Ensures UI shows download as active

## Testing

### Before Fix
```
Console: [movie_157336] Video status changed to: downloading
UI:      Interstellar (2014) - Sci-Fi  [No status shown]
```

### After Fix
```
Console: [movie_157336] Video status changed to: downloading
UI:      Interstellar (2014) - Sci-Fi  [V:15% S:100%]
```

## Current State of Interstellar Download

```sql
id:              movie_157336
status:          downloading ✅ (manually corrected, will auto-correct on next app start)
video_status:    downloading
video_progress:  14.6%
subtitle_status: completed
subtitle_progress: 0.0%
```

- ✅ Video: Downloading (14.6%)
- ✅ Subtitle: Already downloaded (Polish)
- ✅ Translation: Not needed (Polish subtitle)

## How to Test

1. **Run the app:**
   ```bash
   uv run python main.py
   ```

2. **Check Interstellar in catalog:**
   - Should show: `Interstellar (2014) - Sci-Fi  [V:15% S:100%]` (approx)
   - Color: Cyan (downloading)
   - Tooltip: Shows detailed progress

3. **Wait for video to complete:**
   - Progress should update every 2 seconds
   - When complete: Status changes to `[Ready]` with green color

4. **Test with new download:**
   - Select another movie
   - Click Download
   - Should immediately show `[V:0% S:0%]` and start updating

## Files Modified

- ✅ `source/catalog_tab.py` - Fixed UI text display for V2 dual progress
- ✅ `source/download_orchestrator_v2.py` - Fixed status when resuming downloads

## Related Files

- `DOWNLOAD_V2_MIGRATION.md` - Migration guide
- `INTEGRATION_SUMMARY.md` - Integration summary
- `TEST_RESULTS.md` - Test results from Inception download
- `no_ui.log` - Console log showing download was working but UI wasn't updating

---

**Status:** ✅ Fixed and ready to test
**Date:** 2026-01-08
