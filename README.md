# hackflix

A movie player with suggestions and voice-over translations. Built with PyQt5 for signal-driven MVC architecture, featuring automated subtitle fetching, AI-powered translation, and full lector mode voiceover generation.

## Features

- **Torrent Streaming**: Stream movies while downloading with WebTorrent integration
- **Smart Suggestions**: Get movie recommendations based on your library
- **Voiceover Mode**: AI-generated Polish voiceover (lector) for any video
  - Automatic subtitle fetching from OpenSubtitles
  - Gemini AI translation with resumable batch processing
  - Edge-TTS Polish voice synthesis (MarekNeural)
  - Dynamic audio ducking for clear voiceover
  - Time-stretching with cumulative drift tracking

## System Requirements

- **Python 3.11+**
- **FFmpeg** (required for voiceover generation)
- **VLC** (required for video playback)
- **Internet connection** (for subtitle downloads, AI translation, TTS)

### FFmpeg Installation

```bash
# Ubuntu/Debian
sudo apt install ffmpeg

# macOS
brew install ffmpeg

# Windows
# Download from https://ffmpeg.org/download.html
```

## Installation

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# or
.venv\Scripts\activate  # Windows

# Install dependencies
pip install -e .
```

## Configuration

Configure environment variables before running:

| Variable | Description | Required |
|----------|-------------|----------|
| `OPENSUBTITLES_API_KEY` | OpenSubtitles API key for subtitle downloads | Yes |
| `GEMINI_API_KEY` | Google Gemini API key for translation | Yes |

### Optional Configuration

```bash
# Set custom media folder (default: ~/Movies/hackflix)
export HACKFLIX_MEDIA_DIR=/path/to/media

# Set cache directory (default: ~/.cache/hackflix)
export HACKFLIX_CACHE_DIR=/path/to/cache
```

## Usage

### Starting the Application

```bash
python -m src.main
```

### Adding Movies

1. Click "Add Torrent" or drag magnet links to the window
2. The application streams while downloading
3. Once download completes, subtitle fetching auto-starts if `subtitle_id` is set

### Voiceover Generation

When a video has an associated `subtitle_id`:
1. **Fetch**: Downloads original subtitles from OpenSubtitles
2. **Translate**: Gemini AI translates to Polish in 30-line batches (resumable)
3. **TTS**: Edge-TTS generates Polish voice clips
4. **Mix**: Original audio is ducked (100ms fade down, 500ms fade up) and overlaid with TTS
5. **Output**: Final voiceover saved as `voiceover_pl.wav`

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+O` | Add torrent/movie |
| `Space` | Play/Pause |
| `F` | Toggle fullscreen |
| `V` | Toggle voiceover mode |
| `M` | Mute/Unmute |

## Architecture

Signal-Driven MVC with PyQt5:
- **View (UI)**: Dumb components in `src/ui/` - display data, emit signals only
- **Controller**: `src/controllers/app_controller.py` - handles state and routing
- **Model**: Raw sqlite3 in `src/database/` - per-operation connections
- **Services**: QThread-based workers in `src/services/`
  - TorrentService: WebTorrent streaming
  - PipelineService: Voiceover generation pipeline
  - PlaybackService: VLC-based playback

## Pipeline States

| State | Description |
|-------|-------------|
| `PENDING` | Waiting to start |
| `QUEUED` | Added to processing queue |
| `DOWNLOADING` | Currently downloading |
| `COMPLETED` | Download finished |
| `FETCHING_SUBS` | Downloading subtitles |
| `TRANSLATING` | AI translation in progress |
| `SUBS_READY` | Subtitles ready |
| `GENERATING_TTS` | Voice synthesis |
| `MIXING_AUDIO` | Audio mixing with ducking |
| `VOICEOVER_READY` | Voiceover complete |
| `FAILED` | Processing error |

## Performance Notes

- **Memory Optimization**: Voiceover processing uses 10-minute chunks to avoid RAM exhaustion (Pi 5 optimization)
- **Resumable Translation**: Translation saves progress every 30 lines; resumes from last batch on failure
- **Drift Tracking**: Time-stretching tracks cumulative drift (max 5 seconds before clipping)
- **Max Speedup**: 1.3x audio speed for subtitle alignment

## API Dependencies

| Service | Purpose | Rate Limits |
|---------|---------|-------------|
| OpenSubtitles | Subtitle downloads | 50 req/min (free tier) |
| Google Gemini | Translation | 60 RPM (free tier) |
| Edge-TTS | Voice synthesis | No strict limits |

## Testing

```bash
# Run all tests with coverage
pytest --cov=src tests/ --cov-report=term-missing

# Run specific test file
pytest tests/test_pipeline_service.py

# Run with verbose output
pytest -v tests/
```

## License

MIT
