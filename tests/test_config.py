"""Tests for the configuration module."""

import logging
from pathlib import Path
from unittest import mock

from src.config import (
    DownloadState,
    LoggingConfig,
    PipelineState,
    setup_logging,
    TTS_VOICE,
    MAX_TTS_SPEEDUP,
    TRANSLATION_BATCH_SIZE,
)


class TestDownloadState:
    """Tests for DownloadState enum."""

    def test_all_states_defined(self) -> None:
        """Verify all expected download states exist."""
        expected = {"PENDING", "QUEUED", "DOWNLOADING", "COMPLETED", "ERROR"}
        actual = {state.name for state in DownloadState}
        assert actual == expected

    def test_state_values(self) -> None:
        """Verify state values match their names."""
        for state in DownloadState:
            assert state.value == state.name


class TestPipelineState:
    """Tests for PipelineState enum."""

    def test_all_states_defined(self) -> None:
        """Verify all expected pipeline states exist."""
        expected = {
            "NONE",
            "FETCHING_SUBS",
            "TRANSLATING",
            "SUBS_READY",
            "GENERATING_TTS",
            "MIXING_AUDIO",
            "VOICEOVER_READY",
            "FAILED",
        }
        actual = {state.name for state in PipelineState}
        assert actual == expected

    def test_state_values(self) -> None:
        """Verify state values match their names."""
        for state in PipelineState:
            assert state.value == state.name


class TestConstants:
    """Tests for configuration constants."""

    def test_tts_voice_is_polish(self) -> None:
        """Verify TTS voice is the required Polish voice."""
        assert TTS_VOICE == "pl-PL-MarekNeural"

    def test_max_tts_speedup(self) -> None:
        """Verify max TTS speedup is within reasonable bounds."""
        assert 1.0 < MAX_TTS_SPEEDUP <= 2.0
        assert MAX_TTS_SPEEDUP == 1.3

    def test_translation_batch_size(self) -> None:
        """Verify translation batch size is reasonable."""
        assert 10 <= TRANSLATION_BATCH_SIZE <= 100
        assert TRANSLATION_BATCH_SIZE == 30


class TestCheckRequiredEnvVars:
    """Tests for environment variable checking."""

    def test_returns_empty_when_all_present(self) -> None:
        """Returns empty list when all required vars are set."""
        import src.config

        # Temporarily set the module-level variables
        original_catalog = src.config.CATALOG_URL
        original_gemini = src.config.GEMINI_API_KEY
        original_opensubs = src.config.OPENSUBTITLES_API_KEY
        try:
            src.config.CATALOG_URL = "https://example.com/catalog"
            src.config.GEMINI_API_KEY = "test-key"
            src.config.OPENSUBTITLES_API_KEY = "test-key"
            missing = src.config.check_required_env_vars()
            assert missing == []
        finally:
            src.config.CATALOG_URL = original_catalog
            src.config.GEMINI_API_KEY = original_gemini
            src.config.OPENSUBTITLES_API_KEY = original_opensubs

    def test_returns_missing_vars(self) -> None:
        """Returns list of missing variable names."""
        import src.config

        # Temporarily clear the module-level variables
        original_catalog = src.config.CATALOG_URL
        original_gemini = src.config.GEMINI_API_KEY
        original_opensubs = src.config.OPENSUBTITLES_API_KEY
        try:
            src.config.CATALOG_URL = ""
            src.config.GEMINI_API_KEY = ""
            src.config.OPENSUBTITLES_API_KEY = ""
            missing = src.config.check_required_env_vars()
            assert "CATALOG_URL" in missing
            assert "GEMINI_API_KEY" in missing
            assert "OPENSUBTITLES_API_KEY" in missing
        finally:
            src.config.CATALOG_URL = original_catalog
            src.config.GEMINI_API_KEY = original_gemini
            src.config.OPENSUBTITLES_API_KEY = original_opensubs


class TestEnsureDirectories:
    """Tests for directory creation."""

    def test_creates_directories(self, tmp_path: Path) -> None:
        """Verify all required directories are created."""
        import src.config

        # Save original values
        original_config = src.config.CONFIG_DIR
        original_log = src.config.LOG_DIR
        original_cache = src.config.CACHE_DIR
        original_torrent = src.config.TORRENT_STATE_DIR

        try:
            # Override with temp paths
            src.config.CONFIG_DIR = tmp_path / "config"
            src.config.LOG_DIR = tmp_path / "config" / "logs"
            src.config.CACHE_DIR = tmp_path / "config" / "cache"
            src.config.TORRENT_STATE_DIR = tmp_path / "config" / "torrents"

            src.config.ensure_directories()

            assert (tmp_path / "config").exists()
            assert (tmp_path / "config" / "logs").exists()
            assert (tmp_path / "config" / "cache").exists()
            assert (tmp_path / "config" / "torrents").exists()
        finally:
            # Restore original values
            src.config.CONFIG_DIR = original_config
            src.config.LOG_DIR = original_log
            src.config.CACHE_DIR = original_cache
            src.config.TORRENT_STATE_DIR = original_torrent


class TestSetupLogging:
    """Tests for logging setup."""

    def test_configures_root_logger(self, tmp_path: Path) -> None:
        """Verify root logger is configured."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        with mock.patch("src.config.LOG_DIR", log_dir):
            root_logger = logging.getLogger()
            root_logger.handlers.clear()

            setup_logging(LoggingConfig(debug=False))

            assert root_logger.level == logging.INFO
            assert len(root_logger.handlers) >= 1

    def test_debug_mode(self, tmp_path: Path) -> None:
        """Verify debug mode sets DEBUG level."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        with mock.patch("src.config.LOG_DIR", log_dir):
            root_logger = logging.getLogger()
            root_logger.handlers.clear()

            setup_logging(LoggingConfig(debug=True))

            assert root_logger.level == logging.DEBUG

    def test_creates_log_file(self, tmp_path: Path) -> None:
        """Verify log file is created."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()

        with mock.patch("src.config.LOG_DIR", log_dir):
            root_logger = logging.getLogger()
            root_logger.handlers.clear()

            setup_logging(LoggingConfig(debug=False))

            logging.info("Test log message")

            log_files = list(log_dir.glob("*.log"))
            assert len(log_files) >= 1
