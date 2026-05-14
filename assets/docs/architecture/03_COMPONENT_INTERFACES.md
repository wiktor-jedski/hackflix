# 03_COMPONENT_INTERFACES.md

## 1. Core Application Logic

### 1.1. `AppController` (Singleton)
**Responsibility:** The central brain. It orchestrates communication between the UI, Database, and Background Services. It holds the application state.

*   **Properties:**
    *   `current_view`: Enum (LIBRARY, PLAYER, SETTINGS)
    *   `selected_item_id`: String (UUID)
    *   `db`: Instance of `DatabaseManager`

*   **Methods:**
    *   `bootstrap()`: Initialize DB, check internet, load settings.
    *   `handle_input(action: ActionEnum)`: Receives semantic actions from InputManager and routes them (e.g., if in Library -> move cursor; if in Player -> pause).
    *   `trigger_sync()`: Starts the MetadataService background task.
    *   `play_media(file_id: int)`: Prepares the PlayerService and switches view.

### 1.2. `InputManager` (QObject)
**Responsibility:** Intercepts raw Qt Key Events, applies per-key-type debouncing, and maps keys to semantic Application Actions.

*   **Debounce Strategy:**
    *   **Navigation keys (Arrows):** Allow key repeat for fast scrolling.
    *   **Action keys (D, P, Enter, S):** Debounced to prevent accidental double-triggers.

*   **Signals:**
    *   `action_triggered(action: ActionEnum, context: dict)`

*   **Key Mapping (Hardcoded per requirements):**
    *   `Key_Tab`: `Action.SWITCH_TAB` (Movies <-> Series)
    *   `Key_S`: `Action.SEARCH`
    *   `Key_D`: `Action.DELETE`
    *   `Key_P`: `Action.SYNC`
    *   `Key_Return`: `Action.CONFIRM`
    *   `Key_Esc`: `Action.CANCEL` / `Action.BACK`
    *   `Arrows`: `Action.NAVIGATE`
    *   `Ctrl+Key_Q`: `Action.QUIT` (Hidden exit shortcut)

---

## 2. Service Interfaces (Background Workers)

All services below must inherit from `QObject` and be designed to run in a `QThread` to prevent UI freezing.

### 2.1. `DatabaseManager`
**Responsibility:** Manages raw sqlite3 connections with per-operation connection lifecycle.

*   **Methods:**
    *   `upsert_content(json_data: dict)`: Parses `content.json` and updates `media_items` / `seasons` / `video_files`. Preserves orphaned items.
    *   `get_library_items(type: str, search_filter: str = None)`: Returns list of items for the UI grid, optionally filtered.
    *   `get_video_details(media_id: str)`: Returns file path, subtitle status, audio status.
    *   `update_file_state(file_id: int, state: str, progress: int)`: Updates status columns.
    *   `update_resume_position(file_id: int, position_seconds: int)`: Saves playback position.
    *   `get_translation_progress(file_id: int)`: Returns batch progress for resumable translation.
    *   `update_translation_progress(file_id: int, batch: int, total: int)`: Saves translation progress.

### 2.2. `TorrentService`
**Responsibility:** Wrapper for embedded `libtorrent` with persistent session state.

*   **Signals:**
    *   `download_progress(file_id: int, percentage: int, speed: str)`
    *   `download_completed(file_id: int, path: str)`
    *   `download_error(file_id: int, error: str)`

*   **Methods:**
    *   `initialize()`: Loads persistent session state from disk (DHT nodes, resume data).
    *   `start_download(magnet: str, save_path: str, sequential: bool = False)`: Adds torrent. If `sequential=True`, prioritize files in order (for season packs).
    *   `pause_download(hash: str)`
    *   `delete_download(hash: str, delete_files: bool)`
    *   `poll_status()`: Called by a QTimer every 2 seconds to emit progress.
    *   `save_state()`: Persists session state to disk (called on shutdown and periodically).
    *   `find_video_file(torrent_path: str) -> str`: Returns path to largest file in download folder.

### 2.3. `PlayerService` (VLC Wrapper)
**Responsibility:** Manages the `libvlc` instance. It must render into a `QFrame` widget provided by the UI. Tested on Pi 5 with hardware acceleration defaults.

*   **Signals:**
    *   `playback_finished()`
    *   `time_changed(current_ms: int, total_ms: int)`
    *   `error_occurred(msg: str)`

*   **Methods:**
    *   `initialize(video_frame_id: int)`: Binds VLC to the UI widget `winId`.
    *   `load_video(path: str, local_audio_path: str = None)`:
        *   If `local_audio_path` (voiceover) is provided, tell VLC to load it as an external audio track (`input-slave`).
    *   `load_subtitle(path: str)`: Adds subtitle file (only from strict expected paths).
    *   `get_audio_tracks() -> list`: Returns list of all audio tracks (original + voiceover).
    *   `cycle_audio_track()`: Cycles through all available audio tracks sequentially.
    *   `toggle_pause()`
    *   `seek(delta_ms: int)`
    *   `get_position_seconds() -> int`: Returns current playback position for resume.
    *   `set_position_seconds(seconds: int)`: Seeks to saved resume position.

### 2.4. `PipelineService` (The AI Worker)
**Responsibility:** Orchestrates the transformation of raw video into a translated, voice-over experience with full lector mode.

*   **Signals:**
    *   `pipeline_update(file_id: int, state: PipelineState, message: str)`
    *   `pipeline_finished(file_id: int, success: bool)`

*   **Methods:**
    *   `start_process(video_file_id: int)`: Main entry point.
    *   `_fetch_subtitles(subtitle_id: int)`: Uses OpenSubtitles API with server-specified ID.
    *   `_translate_subtitles(srt_path: str)`:
        *   Chunks `.srt` text into 20-50 line batches.
        *   Sends to Gemini API with JSON-to-JSON transformation.
        *   **Resumable:** Tracks batch progress in DB, resumes from last successful batch on failure.
        *   Saves `pl.srt`.
    *   `_generate_voiceover(srt_path: str, video_path: str)`:
        *   Parses SRT, skips bracketed sound effects (e.g., `[Door slams]`).
        *   Calls `edge-tts` with `pl-PL-MarekNeural` voice.
        *   Time-stretches clips (max 1.3x), tracks cumulative drift (max 5s before clipping to resync).
        *   **Full Lector Mode:** Extracts original audio, applies dynamic ducking with fade, mixes with TTS.
        *   Generates in 10-minute chunks, concatenates, **cleans up intermediate files immediately**.
        *   Stores final voiceover permanently.

---

## 3. UI View Contracts

These are "dumb" classes. They implement a standard interface so the Controller can manage them generically.

### 3.1. `AbstractView` (Interface)
*   `bind_controller(controller)`: Link to logic.
*   `on_focus_gained()`: Visual update (e.g., highlight first item).
*   `handle_navigation(direction: ActionEnum)`: Return `True` if view handled it, `False` if it bubbled up.

### 3.2. `LibraryView`
*   **Components:**
    *   `Header`: Tabs for Movies/Series (no breadcrumbs - clean UI).
    *   `List`: Thumbnail display (cached locally), download/play when clicked on, status indicators (Icons).
*   **Logic:**
    *   List navigation using arrow keys.
    *   Scrolling support.
    *   Search filter **persists** until explicitly cleared (pressing S again or Esc in search overlay).
    *   Entering a Series item shows List of Seasons. Entering a Season shows list of Episodes.
    *   **Navigation stack preserved:** Returning from player restores exact drill-down context.

### 3.3. `PlayerView`
*   **Components:**
    *   `VideoFrame`: The black box for VLC.
    *   `OSD (On Screen Display)`: **Minimal icons only** (no text/numbers) for Volume, Seek, Pause status.
*   **Logic:**
    *   Hides mouse cursor.
    *   Enters full screen mode.
    *   Fades out OSD after 3 seconds of inactivity.
    *   On exit (Esc): saves resume position (to the second), returns to **exact previous library state**.

### 3.4. `StatusOverlay` (Toast Notifications)
*   **Logic:**
    *   Multiple toasts **stack visually** (not queued).
    *   Each toast auto-dismisses after configurable timeout.
