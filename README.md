# hackflix

A movie and TV library application for Raspberry Pi 5 (and other Linux desktops). It syncs a remote catalog, downloads selected titles via libtorrent, automatically fetches and translates subtitles to Polish, and plays them through VLC. Built with PyQt6 in a signal-driven MVC architecture.

## Features

- **Catalog Sync**: Pulls a remote `content.json` catalog and caches poster images locally.
- **Torrent Downloads**: Embedded libtorrent session with DHT, LSD, UPnP, and resumable session state. Supports both single-file (movie) and multi-file (season pack) torrents with automatic episode-to-file matching.
- **Subtitle Pipeline**: After download completes, fetches subtitles from OpenSubtitles and (optionally) translates them to Polish using Google Gemini in resumable 30-line batches.
- **VLC Playback**: Fullscreen video playback with audio-track cycling, mute, seek, volume control, and resume-from-position.
- **Auto-Resume**: Incomplete downloads and incomplete subtitle pipelines are resumed automatically on startup.

## System Requirements

- **Python 3.11** (the project pins `>=3.11,<3.12`)
- **VLC** (for `python-vlc` playback)
- **libtorrent** (Python bindings, available via the `libtorrent` PyPI package or system package)
- **FFmpeg** (checked at startup; required to launch)
- **Internet connection** (catalog sync, torrents, subtitle download, translation)

### System package install

```bash
# Arch
sudo pacman -S vlc ffmpeg libtorrent-rasterbar

# Ubuntu/Debian
sudo apt install vlc ffmpeg python3-libtorrent
```

## Installation

The project uses [uv](https://github.com/astral-sh/uv) for dependency management.

```bash
uv sync
```

## Configuration

Hackflix reads configuration from environment variables (a `.env` file in the project root is loaded automatically).

| Variable | Description | Required |
|----------|-------------|----------|
| `CATALOG_URL` | URL of the `content.json` catalog used by the metadata sync. | Yes |
| `GEMINI_API_KEY` | Google Gemini API key, used for subtitle translation. | Yes |
| `OPENSUBTITLES_API_KEY` | OpenSubtitles API key, used for subtitle download. | Yes |
| `MEDIA_LIBRARY_PATH` | Where downloaded media is stored. Defaults to `/mnt/usb_storage/hackflix-library`. | No |
| `CONFIG_DIR` | Where the database, logs, cache, and torrent state live. Defaults to `~/.config/hackflix`. | No |
| `DATABASE_PATH` | Path to the SQLite database file. Defaults to `$CONFIG_DIR/db.sqlite`. | No |
| `DEBUG` | Set to `true` to enable debug-level logging. | No |

## Usage

```bash
uv run python src/main.py
```

The application starts fullscreen (it is intended for set-top-box-style use on a Pi). Press `P` to sync the catalog, then navigate the library and press `Enter` on an item to start downloading or to play it once it is ready.

After a movie download completes, if the catalog supplies a `subtitle_id` for that file the subtitle pipeline will:
1. Download the original subtitle from OpenSubtitles.
2. Translate it to Polish in resumable 30-line batches via Gemini (skipped if `needs_translation` is false).
3. Mark the file as `SUBS_READY`; VLC then loads the Polish subtitle (or the original as a fallback) automatically when you play the file.

### Keyboard Shortcuts

#### Library

| Shortcut | Action |
|----------|--------|
| `Up` / `Down` | Move selection |
| `Tab` | Switch between Movies and Series tabs |
| `Enter` | Activate (start download, drill into series/season, or play) |
| `Esc` | Go back |
| `S` | Open search |
| `X` | Clear search filter |
| `D` | Delete the selected item's downloaded files |
| `P` | Sync catalog metadata |
| `Ctrl+Q` | Quit |

#### Player

| Shortcut | Action |
|----------|--------|
| `Space` / `Enter` | Play / Pause |
| `Left` / `Right` | Seek backward / forward |
| `Up` / `Down` | Volume up / down |
| `M` | Mute / Unmute |
| `L` | Cycle audio track |
| `Esc` | Stop and return to library |

## Architecture

Signal-Driven MVC with PyQt6:

- **View (UI)**: Dumb components in `src/ui/` — display data and emit signals. No business logic, no service or DB imports.
- **Controller**: `src/controllers/app_controller.py` — state machine, signal routing, and orchestration.
- **Model**: Raw `sqlite3` in `src/database/` with per-operation connections (no ORM).
- **Services** (`src/services/`, all `QThread`-based):
  - `MetadataService` — fetches the remote catalog and caches posters.
  - `TorrentService` — libtorrent session, download progress, resume data.
  - `PipelineService` — subtitle fetch and translation.
  - `PlayerService` — VLC bindings.

The UI thread never performs file I/O or network requests synchronously; all such work happens in services.

## State Enumerations

**Download State:** `PENDING` → `QUEUED` → `DOWNLOADING` → `COMPLETED` / `ERROR`

**Pipeline State:** `NONE` → `FETCHING_SUBS` → `TRANSLATING` → `SUBS_READY` / `FAILED`

## Testing

```bash
# All tests with coverage
uv run pytest --cov=src tests/ --cov-report=term-missing

# Single test file
uv run pytest tests/test_database.py
```

The project targets 100% line coverage; see `CLAUDE.md` for the coverage policy.

## Lint and Format

```bash
uv run ruff check .
uv run ruff format .
uv run ty check
```

## License

MIT (see `LICENSE`).
