"""Configuration module for Hackflix.

This module contains all constants, settings, state enumerations,
and logging configuration for the application.
"""

import logging
import os
from dataclasses import dataclass
from enum import Enum
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


# =============================================================================
# Path Configuration
# =============================================================================

CONFIG_DIR = Path(os.environ.get("CONFIG_DIR", Path.home() / ".config" / "hackflix"))
DATABASE_PATH = Path(os.environ.get("DATABASE_PATH", CONFIG_DIR / "db.sqlite"))
LOG_DIR = CONFIG_DIR / "logs"
CACHE_DIR = CONFIG_DIR / "cache"
TORRENT_STATE_DIR = CONFIG_DIR / "torrents"
MEDIA_LIBRARY_PATH = Path(
    os.environ.get("MEDIA_LIBRARY_PATH", "/mnt/usb_storage/hackflix-library")
)


def ensure_directories() -> None:
    """Create all required directories if they don't exist."""
    for directory in [CONFIG_DIR, LOG_DIR, CACHE_DIR, TORRENT_STATE_DIR, TTS_TEMP_DIR]:
        directory.mkdir(parents=True, exist_ok=True)


# =============================================================================
# API Configuration
# =============================================================================

CATALOG_URL = os.environ.get("CATALOG_URL", "")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
OPENSUBTITLES_API_KEY = os.environ.get("OPENSUBTITLES_API_KEY", "")


def check_required_env_vars() -> list[str]:
    """Check for required environment variables and return missing ones.

    Returns:
        List of missing environment variable names.
    """
    missing = []
    if not CATALOG_URL:
        missing.append("CATALOG_URL")
    if not GEMINI_API_KEY:
        missing.append("GEMINI_API_KEY")
    if not OPENSUBTITLES_API_KEY:
        missing.append("OPENSUBTITLES_API_KEY")
    return missing


# =============================================================================
# State Enumerations
# =============================================================================


class DownloadState(Enum):
    """Download state for video files and seasons.

    States:
        PENDING: Known from content.json, download not started.
        QUEUED: Added to torrent client, waiting.
        DOWNLOADING: Active torrent activity.
        COMPLETED: File exists on disk.
        ERROR: Download failed, can retry.
    """

    PENDING = "PENDING"
    QUEUED = "QUEUED"
    DOWNLOADING = "DOWNLOADING"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"


class PipelineState(Enum):
    """Pipeline state for subtitle/voiceover processing.

    States:
        NONE: No processing required or not started.
        FETCHING_SUBS: Querying OpenSubtitles API.
        TRANSLATING: Sending text to Gemini API.
        SUBS_READY: Subtitles ready, video can be watched with subs.
        GENERATING_TTS: Creating audio clips with edge-tts.
        MIXING_AUDIO: FFmpeg merging audio tracks.
        VOICEOVER_READY: Voiceover audio available.
        FAILED: Pipeline broke (API error, quota exceeded, etc.).
    """

    NONE = "NONE"
    FETCHING_SUBS = "FETCHING_SUBS"
    TRANSLATING = "TRANSLATING"
    SUBS_READY = "SUBS_READY"
    GENERATING_TTS = "GENERATING_TTS"
    MIXING_AUDIO = "MIXING_AUDIO"
    VOICEOVER_READY = "VOICEOVER_READY"
    FAILED = "FAILED"


# =============================================================================
# Application Constants
# =============================================================================

# TTS Configuration
TTS_VOICE = "pl-PL-MarekNeural"
VOICEOVER_LANGUAGE = "pl"
MAX_TTS_SPEEDUP = 1.3
MAX_TIMING_DRIFT_SECONDS = 5.0

# Audio Ducking Configuration
DUCKING_FADE_MS = 100
DUCKING_LEVEL_DB = -15

# UI Timing Constants
OSD_FADE_TIMEOUT_MS = 3000
TOAST_TIMEOUT_MS = 5000

# Translation Configuration
TRANSLATION_BATCH_SIZE = 30

# Pipeline Configuration
PIPELINE_CHUNK_DURATION_MINUTES = 10
TTS_TEMP_DIR = CACHE_DIR / "tts"
VOICEOVER_PATH_TEMPLATE = "{video_folder}/voiceover_pl.wav"

# Torrent Configuration
TORRENT_POLL_INTERVAL_MS = 2000

# Player Configuration
PLAYER_VOLUME_STEP: int = 5
PLAYER_SEEK_SECONDS: int = 10
PLAYER_TIME_UPDATE_INTERVAL_MS: int = 500

# Logging Configuration
LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
LOG_BACKUP_COUNT = 7  # Keep 7 days of logs


@dataclass
class LoggingConfig:
    """Logging configuration."""

    debug: bool = False
    log_file: Optional[str] = None
    level: str = "INFO"


# =============================================================================
# Logging Setup
# =============================================================================


def setup_logging(config: Optional[LoggingConfig] = None) -> None:
    """Configure application logging.

    Sets up file and console handlers with appropriate formatting.
    File handler uses daily rotation with LOG_BACKUP_COUNT days retention.

    Args:
        config: LoggingConfig instance. If None, uses defaults.
    """
    ensure_directories()

    if config is None:
        config = LoggingConfig()

    log_level = logging.DEBUG if config.debug else logging.INFO
    log_file_path = config.log_file if config.log_file else str(LOG_DIR / "app.log")

    # Create formatter
    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove any existing handlers
    root_logger.handlers.clear()

    # File handler with daily rotation
    file_handler = TimedRotatingFileHandler(
        log_file_path,
        when="midnight",
        interval=1,
        backupCount=LOG_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # Console handler for development
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    logging.info("Logging initialized (level=%s)", logging.getLevelName(log_level))
