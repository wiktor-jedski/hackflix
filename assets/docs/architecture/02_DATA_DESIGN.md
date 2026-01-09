# 02_DATA_DESIGN.md

## 1. File System Hierarchy

The application must manage storage across the Raspberry Pi's internal SD card (for OS/App logic) and an External HDD (for heavy media files).

### 1.1. Internal Storage (App Data)
Location: `~/.config/pi-player/` (Standard XDG Config)
*   `db.sqlite` - The main database file.
*   `settings.json` - Local configuration (volume settings, last sync timestamp, language preference). **Note: API keys stored in environment variables, not settings file.**
*   `logs/` - Application logs (rotated daily).
*   `cache/` - Thumbnails (cached on sync) and temporary small assets.
*   `torrents/` - Libtorrent session state and resume data for persistent torrenting.

### 1.2. External Storage (Media Library)
Location: `/mnt/usb_storage/pi-library/` (Configurable in settings)
*   `movies/`
    *   `{Title} ({Year})/`
        *   `video_file.mkv`
        *   `original.srt` (English/Source)
        *   `pl.srt` (Translated Polish)
        *   `voiceover_pl.wav` (Generated Audio Track)
*   `series/`
    *   `{ShowName}/`
        *   `Season {XX}/`
            *   `{ShowName} - S{XX}E{YY}.mkv`
            *   ... (subtitles and voiceovers per episode)

---

## 2. Server Sync Contract (`content.json`)

This is the JSON structure the server must provide to the player. The app will fetch this, parse it, and update the local database.

**Important:** The `version` field is ignored by the app - best-effort parsing is applied.

```json
{
  "version": 1,
  "timestamp": "2024-05-20T10:00:00Z",
  "items": [
    {
      "id": "uuid-v4-string",
      "type": "movie",
      "title": "Big Buck Bunny",
      "magnet": "magnet:?xt=urn:btih:...",
      "poster_url": "https://server.com/images/bbb.jpg",
      "subtitle_id": 123,
      "translation_needed": true
    },
    {
      "id": "uuid-v4-string-2",
      "type": "series",
      "title": "Open Source Show",
      "poster_url": "...",
      "seasons": [
        {
          "season_number": 1,
          "magnet": "magnet:?xt=urn:btih:...",
          "episodes": [
            {
              "episode_id": "uuid-ep-1",
              "number": 1,
              "title": "The Beginning",
              "subtitle_id": null,
              "translation_needed": false
            }
          ]
        }
      ]
    }
  ]
}
```

**Subtitle Logic:**
*   If `subtitle_id` is `null` → No subtitles needed, skip pipeline entirely.
*   If `subtitle_id` exists AND `translation_needed` is `false` → Polish subtitles are directly available.
*   If `subtitle_id` exists AND `translation_needed` is `true` → Download English subtitles and translate to Polish.

**Season Pack Logic:**
*   Each season has its own `magnet` link (season pack download).
*   Episodes are downloaded sequentially (E01 → E02 → E03...) via libtorrent file prioritization.

---

## 3. Database Schema (SQLite)

Using raw `sqlite3` module with per-operation connections (no ORM). Below are the table definitions.

### 3.1. Table: `settings`
Stores single-row configuration or key-value pairs.
*   `key` (PK, String)
*   `value` (String) - *JSON serialized if complex*

### 3.2. Table: `media_items` (The "Library")
Stores the high-level metadata for a Movie or TV Show.
*   `id` (PK, String/UUID) - Matches `content.json`.
*   `type` (Enum: 'movie', 'series')
*   `title` (String)
*   `poster_path` (String) - Local path to cached image (cached during sync).
*   `created_at` (DateTime)
*   `last_updated` (DateTime)

**Note:** Fields like year, runtime, overview are only shown if provided by the server. No external metadata enrichment (TMDB/IMDB).

### 3.3. Table: `seasons` (For Series Only)
Represents a season within a series, with its own magnet link.
*   `id` (PK, Integer, Auto-inc)
*   `media_item_id` (FK -> media_items.id)
*   `season_number` (Integer)
*   `magnet_link` (Text) - Season pack magnet.
*   **`state`** (Enum, see Section 4) - Download state for the season pack.
*   `download_progress` (Integer) - 0 to 100 for entire season.

### 3.4. Table: `video_files` (The "Playable Assets")
Represents a physical file on disk (A movie has 1, A series episode links to a season).
*   `id` (PK, Integer, Auto-inc)
*   `media_item_id` (FK -> media_items.id)
*   `season_id` (FK -> seasons.id, Nullable) - For series episodes.
*   `episode_number` (Integer, Nullable) - For series.
*   `episode_title` (String, Nullable)
*   `subtitle_id` (Integer, Nullable) - OpenSubtitles ID, null means no subs needed.
*   `needs_translation` (Boolean) - True if subtitles need English->Polish translation.
*   `file_path` (String) - Local path to the MKV/MP4 (discovered by largest file in folder).
*   `magnet_link` (Text, Nullable) - Only for movies. Series use season.magnet_link.
*   **`state`** (Enum, see Section 4) - For movies only.
*   **`pipeline_state`** (Enum, see Section 4) - Tracks subtitle/voiceover status.
*   `resume_position_seconds` (Integer) - Playback resume point.

### 3.5. Table: `subtitles`
*   `id` (PK, Integer)
*   `video_file_id` (FK -> video_files.id)
*   `language_code` (String) - e.g., 'en', 'pl'.
*   `is_translated` (Boolean) - True if translated by AI.
*   `file_path` (String)

### 3.6. Table: `voiceovers`
*   `id` (PK, Integer)
*   `video_file_id` (FK -> video_files.id)
*   `language_code` (String)
*   `file_path` (String) - Path to the generated .wav (stored permanently).

### 3.7. Table: `translation_progress`
Tracks translation batch progress for recovery on failure.
*   `id` (PK, Integer)
*   `video_file_id` (FK -> video_files.id)
*   `last_completed_batch` (Integer) - Index of last successfully translated batch.
*   `total_batches` (Integer)

---

## 4. State Enumerations

These states control the UI logic (what buttons are shown) and the background worker logic.

### 4.1. Download State (`video_files.state`)
| State | Description | UI Action Available |
| :--- | :--- | :--- |
| `PENDING` | Known from JSON, not started. | "Download" |
| `QUEUED` | Added to torrent client. | "Wait..." |
| `DOWNLOADING` | Active torrent activity. | Progress Bar / "Cancel" |
| `COMPLETED` | File exists on disk. | "Play" (or "Process" if pipeline needed) |
| `ERROR` | Download failed. | "Retry" |

### 4.2. Pipeline State (`video_files.pipeline_state`)
Used if `translation_needed = True`.
| State | Description |
| :--- | :--- |
| `NONE` | No processing required or not started. |
| `FETCHING_SUBS` | Querying OpenSubtitles. |
| `TRANSLATING` | Sending text to Gemini API. |
| `SUBS_READY` | Subtitles ready, user can watch video with subtitles. |
| `GENERATING_TTS` | Creating audio clips. |
| `MIXING_AUDIO` | FFmpeg merging audio. |
| `VOICEOVER_READY` | Voiceover available. |
| `FAILED` | Pipeline broke (e.g., API quota). |

---

## 5. Data Flow Logic

1.  **Sync:**
    *   User presses `P` -> `MetadataService` fetches `content.json` (single attempt, error toast on failure).
    *   Posters are cached locally during sync.
    *   Iterate items:
        *   If `id` exists in DB -> Update metadata.
        *   If `id` new -> Insert into `media_items` (and `seasons`/`video_files` for series).
        *   If `id` in DB but missing in JSON -> **Keep orphan indefinitely** (user may have downloaded files they want to keep).

2.  **Download:**
    *   **Movie:** User selects movie, presses `Enter` -> `DownloadService` adds magnet to libtorrent.
    *   **Series:** User navigates to season, presses `Enter` -> Downloads season pack with sequential episode priority (E01 first).
    *   Polling loop updates `download_progress` in DB.
    *   Video file discovered by finding largest file in downloaded folder.

3.  **Post-Processing:**
    *   When Download State -> `COMPLETED`:
        *   Check `video_files.subtitle_id`.
        *   If `null`: No subtitles needed, skip pipeline.
        *   If not `null`: Trigger `PipelineService`.
        *   Set Pipeline State -> `FETCHING_SUBS`.
        *   When subs fetched, check `video_files.needs_translation`.
        *   If `True`: Set Pipeline State -> `TRANSLATING`; else -> `SUBS_READY`.
        *   When subs translated, Set Pipeline State -> `SUBS_READY`
    *   Note - for movies, this happens automatically. For series, each subtitle is downloaded separately, when user wants to play a downloaded episode.

4.  **Voiceover Generation (Full Lector Mode):**
    *   When user requests voiceover (or configured for auto-generate):
        *   Extract original audio from video file.
        *   Generate TTS clips for each subtitle line (skip bracketed sound effects like `[Door slams]`).
        *   Apply dynamic ducking with fade to original audio.
        *   Mix ducked original + TTS into final voiceover file.
        *   Store voiceover permanently (not regenerated).
    *   Translation progress tracked per-batch for recovery on API failure.

5.  **Delete:**
    *   User selects item, presses `D`.
    *   Files deleted (video, subtitles, voiceover).
    *   **Database entry preserved** - item can be re-downloaded.
