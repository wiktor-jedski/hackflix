# 01_SYSTEM_ARCHITECTURE.md

## 1. Architectural Pattern
The application will follow a **Signal-Driven Model-View-Controller (MVC)** architecture utilizing the **PyQt5** framework.

*   **View (UI):** Dumb components. They only display data and emit signals on key presses. They do not contain business logic.
*   **Controller (Logic):** Connects Views to Services. Handles application state, routing, and user input interpretation.
*   **Model (Data):** Raw sqlite3 module with per-operation connections representing the SQLite database state.
*   **Services (Workers):** Background workers handling long-running tasks (Downloads, Processing, Playback) to keep the Main UI Thread responsive.

## 2. High-Level Diagram

```mermaid
graph TD
    User((User Input)) -->|Keyboard Events| InputMgr[Input Manager]
    InputMgr -->|Route Command| Controller[Main Controller]
    
    subgraph Frontend [UI Layer - Main Thread]
        Controller -->|Update UI| LibraryView
        Controller -->|Update UI| PlayerView
        Controller -->|Update UI| SettingsView
    end

    subgraph Backend [Service Layer - Worker Threads]
        Controller -->|Command| PlayerSvc[Player Service (VLC)]
        Controller -->|Command| DownSvc[Download Service (Torrent)]
        Controller -->|Command| MetaSvc[Metadata Service (Sync)]
        Controller -->|Command| PipelineSvc[VoiceOver Pipeline]
        
        PipelineSvc -->|Fetch| SubAPI[OpenSubtitles API]
        PipelineSvc -->|Translate| GemAPI[Gemini API]
        PipelineSvc -->|Audio| TTS[TTS Engine]
        PipelineSvc -->|Mix| FFMPEG[FFmpeg]
    end

    subgraph Data [Persistence Layer]
        DownSvc -->|Write| FileSys[File System / HDD]
        PipelineSvc -->|Read/Write| FileSys
        MetaSvc -->|Read/Write| DB[(SQLite Database)]
        DB <-->|ORM| Controller
    end
```

## 3. Core Subsystems

### 3.1. Frontend Layer (PyQt5)
*   **MainWindow:** The container window handling the global application loop.
*   **Views:**
    *   `LibraryView`: Grid/List representation of movies/series.
    *   `PlayerView`: Container for the VLC video output and OSD (On-Screen Display).
    *   `StatusOverlay`: A global overlay for notifications (e.g., "Download Started").
*   **InputManager:** A dedicated event filter that intercepts global keyboard strokes, normalizes them, and emits semantic signals (e.g., mapping `Key_P` to `Signal_SyncTriggered`).

### 3.2. Service Layer (Logic & Background Tasks)
*   **PlayerService:** Wrapper around `python-vlc`. It manages the `vlc.Instance` and `vlc.MediaPlayer`. It must handle embedding the video into a PyQt `QFrame` widget using the window ID (`winId`).
*   **DownloadService:** Wrapper around embedded `libtorrent` with persistent session state. It runs in a separate thread, polling for progress and emitting percentage updates to the UI. Downloads season packs sequentially (episode 1 first, then 2, etc.).
*   **MetadataService:** Responsible for fetching `content.json`, parsing it, and updating the SQLite database via "Upsert" logic (Update if exists, Insert if new).
*   **PipelineService:** The "Factory" for voice-overs. It orchestrates the sequence: `Extract SRT` -> `Translate` -> `TTS Generation` -> `Audio Mixing`.

### 3.3. Persistence Layer
*   **Database:** SQLite 3 via raw `sqlite3` module with per-operation connections.
*   **Storage Structure:**
    *   `~/.config/pi-player/`: DB file, settings, logs.
    *   `/mnt/usb_storage/pi-library/`: Completed media files, subtitles, and voiceovers.
*   **Torrent State:** Persistent session state saved to disk (resume data, DHT nodes) for faster startup.

## 4. Concurrency Model & State Management

**Critical Rule:** The User Interface (Main Thread) must **never** perform file I/O or network requests synchronously.

1.  **QThread Strategy:** All Services (Download, Pipeline, Metadata) will inherit from or utilize `QObject` moved to a `QThread`.
2.  **Communication:**
    *   **Main -> Worker:** Method calls (Slots).
    *   **Worker -> Main:** Signals (e.g., `downloadProgress(int)`, `processingFinished(bool)`).
3.  **Global State:** A `SessionState` singleton will track:
    *   Current View (Library vs Player).
    *   Currently Selected Item ID.
    *   Active Background Tasks count.

## 5. Technology Stack & Constraints

| Component | Technology | Version / Note |
| :--- | :--- | :--- |
| **Language** | Python | 3.11.x (Bookworm Std) - single environment for dev and prod |
| **GUI Framework** | PyQt5 | Latest Stable, with external .qm translation files |
| **Media Engine** | LibVLC + python-vlc | Hardware accel enabled (tested on Pi 5) |
| **Database** | SQLite + raw sqlite3 | Per-operation connections, no ORM |
| **Torrent Client** | `libtorrent` | Embedded library with persistent session state |
| **Audio Proc** | FFmpeg + pydub | CLI wrapper and Python library |
| **Translation** | Google Gemini API | `google-generativeai` via env var for API key |
| **TTS** | `edge-tts` | Hardcoded `pl-PL-MarekNeural` voice |
| **Subtitles** | OpenSubtitles.com API | Server specifies exact subtitle_id |

## 6. Error Handling Strategy

Since the device is a "set-top box" style appliance, it cannot show Python stack traces to the user.

1.  **Global Exception Hook:** Catch unhandled exceptions in PyQt.
2.  **User Feedback:** If an error occurs (e.g., "Disk Full"), show a `ToastNotification` overlay in the UI (multiple toasts stack visually), then log the error to `app.log`.
3.  **Recovery:** Failed downloads or processing jobs must be marked as `Error` in the DB, allowing the user to retry via the UI later. Clicking on existing item runs a status validation check (video + subtitles exist), then proceeds with recovery action if mismatch found. For series, only the selected episode is validated.
4.  **Crash Recovery:** On application startup, automatically resume all incomplete downloads and pipeline processing.
5.  **HDD Disconnect:** Errors are surfaced only when the user attempts to access media files (lazy error handling).
6.  **Dependency Check:** Application fails fast on startup if required dependencies (VLC, libtorrent) are missing.
7.  **Hidden Exit:** Ctrl+Q allows quitting the application (not advertised in UI).
