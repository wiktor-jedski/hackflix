"""Test error logging to app.log file."""

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.config import LoggingConfig


class TestErrorLogging:
    """Tests for error logging to app.log."""

    def test_errors_logged_to_app_log_file(self, tmp_path):
        """Verify errors are written to app.log file."""
        from src.config import LOG_DIR, setup_logging

        log_file = tmp_path / "app.log"
        with patch("src.config.LOG_DIR", tmp_path):
            with patch("src.config.ensure_directories"):
                setup_logging(LoggingConfig(debug=True))

        logger = logging.getLogger("test_error_logger")
        test_error_message = "Test error message for app.log verification"
        logger.error(test_error_message)

        for handler in logging.root.handlers:
            handler.flush()

        assert log_file.exists(), "Log file should exist after logging"
        log_contents = log_file.read_text(encoding="utf-8")
        assert test_error_message in log_contents, (
            f"Error message should be in log file. Got: {log_contents}"
        )

    def test_exceptions_logged_with_traceback(self, tmp_path):
        """Verify exception tracebacks are written to app.log."""
        from src.config import LOG_DIR, setup_logging

        log_file = tmp_path / "app.log"
        with patch("src.config.LOG_DIR", tmp_path):
            with patch("src.config.ensure_directories"):
                setup_logging(LoggingConfig(debug=True))

        logger = logging.getLogger("test_exception_logger")
        try:
            raise ValueError("Test exception for logging")
        except ValueError:
            logger.exception("Exception occurred during test")

        for handler in logging.root.handlers:
            handler.flush()

        assert log_file.exists()
        log_contents = log_file.read_text(encoding="utf-8")
        assert "Test exception for logging" in log_contents
        assert "ValueError" in log_contents

    def test_pipeline_error_logged_to_file(self, tmp_path, db_manager):
        """Verify pipeline errors appear in app.log."""
        from src.config import LOG_DIR, PipelineState, setup_logging
        from src.services.pipeline_service import PipelineService

        log_file = tmp_path / "app.log"
        with patch("src.config.LOG_DIR", tmp_path):
            with patch("src.config.ensure_directories"):
                setup_logging(LoggingConfig(debug=True))

        db_manager.upsert_content(
            {
                "version": 1,
                "timestamp": "2024-05-20T10:00:00Z",
                "items": [
                    {
                        "id": "movie-uuid-1",
                        "type": "movie",
                        "title": "Test Movie",
                        "genres": "Test",
                        "magnet": "magnet:?xt=urn:btih:test123",
                        "poster_url": "https://example.com/test.jpg",
                        "subtitle_id": 123,
                        "translation_needed": True,
                        "file_path": str(tmp_path / "video.mp4"),
                    },
                ],
            }
        )

        video_files = db_manager.get_video_file(1)
        video_file_id = video_files["id"]

        (tmp_path / "video.mp4").touch()

        mock_db_manager = MagicMock()
        mock_db_manager.get_video_file.return_value = {
            "id": video_file_id,
            "file_path": str(tmp_path / "video.mp4"),
            "subtitle_id": 123,
            "needs_translation": True,
            "pipeline_state": PipelineState.NONE.value,
        }
        mock_db_manager.get_translation_progress.return_value = None

        pipeline_service = PipelineService(mock_db_manager)
        pipeline_service._video_file_id = video_file_id

        error_messages = []
        pipeline_service.signals.error_occurred.connect(
            lambda file_id, msg: error_messages.append(msg)
        )

        with patch.object(pipeline_service, "_fetch_subtitles") as mock_fetch:
            mock_fetch.side_effect = Exception("Simulated OpenSubtitles API failure")

            pipeline_service.start_process(video_file_id)
            pipeline_service.wait()

        for handler in logging.root.handlers:
            handler.flush()

        assert log_file.exists()
        log_contents = log_file.read_text(encoding="utf-8")
        assert (
            "Pipeline failed" in log_contents
            or "Simulated OpenSubtitles API failure" in log_contents
        )

    def test_download_error_logged_to_file(self, tmp_path):
        """Verify download errors appear in app.log."""
        from src.config import LOG_DIR, DownloadState, setup_logging

        log_file = tmp_path / "app.log"
        with patch("src.config.LOG_DIR", tmp_path):
            with patch("src.config.ensure_directories"):
                setup_logging(LoggingConfig(debug=True))

        logger = logging.getLogger("src.services.torrent_service")
        test_error = "Torrent connection failed: timeout"
        logger.error("Download failed: %s", test_error)

        for handler in logging.root.handlers:
            handler.flush()

        assert log_file.exists()
        log_contents = log_file.read_text(encoding="utf-8")
        assert "Download failed" in log_contents
        assert test_error in log_contents

    def test_database_error_logged_to_file(self, tmp_path):
        """Verify database errors appear in app.log."""
        from src.config import LOG_DIR, setup_logging

        log_file = tmp_path / "app.log"
        with patch("src.config.LOG_DIR", tmp_path):
            with patch("src.config.ensure_directories"):
                setup_logging(LoggingConfig(debug=True))

        logger = logging.getLogger("src.database")
        test_error = "Foreign key constraint violation"
        logger.error("Database operation failed: %s", test_error)

        for handler in logging.root.handlers:
            handler.flush()

        assert log_file.exists()
        log_contents = log_file.read_text(encoding="utf-8")
        assert "Database operation failed" in log_contents
        assert test_error in log_contents

    def test_warning_logged_to_file(self, tmp_path):
        """Verify warnings are written to app.log."""
        from src.config import LOG_DIR, setup_logging

        log_file = tmp_path / "app.log"
        with patch("src.config.LOG_DIR", tmp_path):
            with patch("src.config.ensure_directories"):
                setup_logging(LoggingConfig(debug=True))

        logger = logging.getLogger("test_warning_logger")
        warning_message = "This is a warning message for testing"
        logger.warning(warning_message)

        for handler in logging.root.handlers:
            handler.flush()

        assert log_file.exists()
        log_contents = log_file.read_text(encoding="utf-8")
        assert warning_message in log_contents

    def test_info_logged_to_file(self, tmp_path):
        """Verify info messages are written to app.log."""
        from src.config import LOG_DIR, setup_logging

        log_file = tmp_path / "app.log"
        with patch("src.config.LOG_DIR", tmp_path):
            with patch("src.config.ensure_directories"):
                setup_logging(LoggingConfig(debug=True))

        logger = logging.getLogger("test_info_logger")
        info_message = "Application started successfully"
        logger.info(info_message)

        for handler in logging.root.handlers:
            handler.flush()

        assert log_file.exists()
        log_contents = log_file.read_text(encoding="utf-8")
        assert info_message in log_contents

    def test_log_format_includes_timestamp_and_level(self, tmp_path):
        """Verify log format includes timestamp and log level."""
        from src.config import LOG_DIR, LOG_DATE_FORMAT, LOG_FORMAT, setup_logging

        log_file = tmp_path / "app.log"
        with patch("src.config.LOG_DIR", tmp_path):
            with patch("src.config.ensure_directories"):
                setup_logging(LoggingConfig(debug=True))

        logger = logging.getLogger("test_format_logger")
        logger.info("Format test message")

        for handler in logging.root.handlers:
            handler.flush()

        assert log_file.exists()
        log_contents = log_file.read_text(encoding="utf-8")
        assert "Format test message" in log_contents
        assert "INFO" in log_contents
        import re

        timestamp_pattern = r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}"
        assert re.search(timestamp_pattern, log_contents), (
            f"Timestamp should match pattern. Got: {log_contents}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
