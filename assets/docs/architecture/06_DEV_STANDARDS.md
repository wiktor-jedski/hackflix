# 06_DEV_STANDARDS.md

## 1. Technology Stack & Dependencies

All development must be strictly compatible with **Debian 12 (Bookworm)** running on a Raspberry Pi 5.
**Single environment** for both development and production (same Python version, same dependencies).

*   **Python Version:** `3.11.x` (System default) - do not use newer versions
*   **Virtual Environment:** Use `uv`.
*   **Key Libraries:**
    *   `PyQt5` (GUI) - *Note: Using PyQt5 for broader compatibility with vlc bindings.*
    *   `python-vlc` (Media Player) - tested on Pi 5 with hardware acceleration
    *   `libtorrent` (Embedded Torrent Client) - not qbittorrent-api
    *   `google-genai` (Translation) - API key via environment variable
    *   `edge-tts` (Voice Synthesis) - online only, hardcoded `pl-PL-MarekNeural`
    *   `pydub` (Audio Processing)
    *   `pytest`, `pytest-qt`, `pytest-mock` (Testing)
*   **NOT using:**
    *   `SQLAlchemy` - use raw `sqlite3` with per-operation connections
    *   `qbittorrent-api` - use embedded `libtorrent` instead

---

## 2. Project Directory Structure

The code agent must adhere to this folder structure. No loose files in root except `main.py` and config files.

```text
hackflix/
├── assets/                 # Icons, default placeholders, CSS styles
│   ├── docs/               # Architecture documentation
│   └── translations/       # External .qm translation files (en.qm, pl.qm)
├── src/
│   ├── __init__.py
│   ├── main.py             # Entry point
│   ├── config.py           # Constants and Settings
│   ├── database/           # DB Connection logic (raw sqlite3)
│   │   ├── schema.py       # Table definitions
│   │   └── db_manager.py   # Per-operation connection management
│   ├── controllers/        # App Logic
│   │   └── app_controller.py
│   ├── services/           # Background Workers (QThreads)
│   │   ├── player_service.py
│   │   ├── torrent_service.py  # Embedded libtorrent
│   │   ├── metadata_service.py
│   │   └── pipeline_service.py
│   ├── ui/                 # PyQt Views and Widgets
│   │   ├── windows/
│   │   ├── components/
│   │   └── input_manager.py
│   └── utils/              # Helpers (Time format, File ops)
├── tests/                  # Mirror of src structure
├── logs/                   # Runtime logs (gitignored)
└── README.md
```

---

## 3. Coding Standards

To ensure maintainability by an AI or human:

1.  **Type Hinting:** **MANDATORY**. Every function signature must have type hints.
    *   *Bad:* `def play(file):`
    *   *Good:* `def play(file_path: str) -> None:`
2.  **Docstrings:** Every class and public method must have a docstring explaining *what* it does and *what* it returns.
3.  **No Logic in Views:** UI classes (`src/ui`) must not import `services` or `database`. They communicate purely via Signals/Slots or the Controller.
4.  **Error Handling:** Never use bare `try: except:`. Catch specific exceptions (`vlc.VLCException`, `sqlite3.Error`). Log errors immediately.
5.  **Test Coverage**: Every code change has to be covered by tests before committing. Complete test suite should be run before the commit.

---

## 4. Testing Strategy

Since we cannot easily run VLC or check HDMI output in a CI environment, we rely heavily on **Mocking**.

### 4.1. Unit Tests (`pytest`)
*   **Database:** Use an in-memory SQLite database (`:memory:`) for testing models and queries.
*   **Utilities:** Test string formatting, time parsing, and path logic.

### 4.2. Mocking Hardware & VLC
**Do not** attempt to instantiate real VLC instances in tests. It will crash headless environments.

*   **Mock Player:** Create a `MockPlayerService` that implements the same methods as `PlayerService` but just sets internal flags (e.g., `self.is_playing = True`) and emits signals immediately.
*   **Mock File System:** Use the `tmp_path` fixture in Pytest. Never write to real `/home` or `/mnt` directories during tests.

### 4.3. UI Tests (`pytest-qt`)
We will use `pytest-qt` to simulate key presses and verify signal emission.

*   **Example Test:**
    ```python
    def test_search_trigger(qtbot, library_view):
        qtbot.addWidget(library_view)
        # Simulate pressing 'S'
        qtbot.keyClick(library_view, Qt.Key_S)
        # Assert that the 'search_requested' signal was emitted
        assert library_view.signals.search_requested.emit_count == 1
    ```

---

## 5. Logging Protocol

The application runs as a "black box" appliance. Logs are the only way to debug.

*   **Library:** standard `logging` module.
*   **Format:** `%(asctime)s | %(levelname)s | %(name)s | %(message)s`
*   **Levels:**
    *   `DEBUG`: detailed variable states (disabled in production).
    *   `INFO`: "User pressed Play", "Download started".
    *   `WARNING`: "Subtitle API timeout", "Frame dropped".
    *   `ERROR`: "Database locked", "Network unreachable".

---

## 6. Implementation Workflow (For the Agent)

When the coding agent begins, it should follow this sequence to avoid circular dependencies:

1.  **Phase 1: Foundation** -> Setup `src/config.py`, Logging, and `src/database/` schema (raw sqlite3).
2.  **Phase 2: Services** -> Implement `MetadataService` (Sync) and `TorrentService` (embedded libtorrent) logic *without* UI.
3.  **Phase 3: Core UI** -> Build `MainWindow` and `InputManager`. Connect them to dummy data. Add i18n support (external .qm files).
4.  **Phase 4: Player Integration** -> Implement `PlayerService` (VLC) and connect to `PlayerView`.
5.  **Phase 5: Pipeline** -> Implement the AI Subtitle/Voiceover pipeline with full lector mode. **(COMPLETED Jan 2026)**
    *   Subtitle parser utility for SRT parsing/writing with sound effect detection
    *   Audio processor utility for extraction, ducking, stretching, and mixing
    *   OpenSubtitles API client for subtitle downloads
    *   Gemini API client for batch translation with resumable progress tracking
    *   Edge-TTS client for Polish voice synthesis (pl-PL-MarekNeural)
    *   PipelineService orchestration with state machine (FETCHING_SUBS -> TRANSLATING -> GENERATING_TTS -> MIXING_AUDIO -> VOICEOVER_READY)
    *   Full lector mode with dynamic ducking (20% reduction, 100ms/500ms fades)
    *   10-minute chunk processing for Pi 5 memory optimization
    *   Auto-resume incomplete pipelines on startup
    *   LibraryView status indicators for pipeline states

**Startup Requirements:**
*   Application must **fail fast** if required dependencies (VLC, libtorrent, FFmpeg) are missing.
*   On startup, **auto-resume** all incomplete downloads and pipeline processing.
*   No autostart built-in - user configures manually.

**Environment Variables Required:**
*   `GEMINI_API_KEY` - for translation
*   `OPENSUBTITLES_API_KEY` - for subtitle fetching
