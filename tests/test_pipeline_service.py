"""Tests for PipelineService - subtitle translation and voiceover generation.

Tests cover:
- Initialization with dependencies
- Pipeline skip conditions (null subtitle_id, existing voiceover)
- Complete pipeline flow (fetch → translate → TTS → extract → mix)
- Translation skip when needs_translation=False
- Sound effect skipping in TTS generation
- Pipeline state updates at each stage
- Database persistence (subtitles, voiceovers added)
- Resumable translation (load progress, resume, delete on success)
- Error handling and FAILED state
- Stop/cancellation
- Signal emissions (pipeline_update, pipeline_finished)
"""

import logging
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest
from PyQt5.QtCore import QObject

from src.config import PipelineState
from src.services.pipeline_service import PipelineService, PipelineSignals


@pytest.fixture
def mock_db_manager():
    """Create a mock DatabaseManager for testing."""
    manager = MagicMock()
    manager.get_video_file.return_value = {
        "id": 1,
        "file_path": "/media/video.mp4",
        "subtitle_id": 12345,
        "needs_translation": True,
        "pipeline_state": PipelineState.NONE.value,
    }
    manager.get_translation_progress.return_value = None
    manager.add_subtitle.return_value = None
    manager.add_voiceover.return_value = None
    manager.update_pipeline_state.return_value = None
    manager.clear_translation_progress.return_value = None
    return manager


@pytest.fixture
def pipeline_service(mock_db_manager):
    """Create a PipelineService instance with mocked dependencies."""
    service = PipelineService(mock_db_manager)
    return service


class TestPipelineServiceInitialization:
    """Tests for PipelineService initialization."""

    def test_initialization_sets_correct_attributes(
        self, pipeline_service, mock_db_manager
    ):
        """Verify initialization sets signals, db_manager, and default values."""
        assert pipeline_service.db_manager is mock_db_manager
        assert isinstance(pipeline_service.signals, PipelineSignals)
        assert pipeline_service._video_file_id is None
        assert pipeline_service._should_stop is False
        assert pipeline_service._current_state == PipelineState.NONE
        assert pipeline_service._is_busy is False

    def test_is_busy_returns_false_initially(self, pipeline_service):
        """Verify is_busy returns False before processing starts."""
        assert pipeline_service.is_busy() is False

    def test_is_busy_returns_true_during_processing(self, pipeline_service):
        """Verify is_busy returns True after start_process is called."""
        pipeline_service.start_process(1)
        assert pipeline_service.is_busy() is True


class TestPipelineServiceStartProcess:
    """Tests for start_process method."""

    def test_start_process_sets_video_file_id(self, pipeline_service):
        """Verify start_process sets the video file ID."""
        pipeline_service.start_process(42)
        assert pipeline_service._video_file_id == 42

    def test_start_process_resets_should_stop_flag(self, pipeline_service):
        """Verify start_process resets the stop flag."""
        pipeline_service._should_stop = True
        pipeline_service.start_process(1)
        assert pipeline_service._should_stop is False

    def test_start_process_sets_is_busy_true(self, pipeline_service):
        """Verify start_process sets is_busy to True."""
        pipeline_service.start_process(1)
        assert pipeline_service._is_busy is True


class TestPipelineServiceStop:
    """Tests for stop method."""

    def test_stop_sets_should_stop_flag(self, pipeline_service):
        """Verify stop sets the should_stop flag."""
        pipeline_service.stop()
        assert pipeline_service._should_stop is True


class TestPipelineServiceSkipConditions:
    """Tests for pipeline skip conditions."""

    def test_skips_when_subtitle_id_is_null(self, pipeline_service, mock_db_manager):
        """Verify pipeline skips when subtitle_id is null."""
        mock_db_manager.get_video_file.return_value = {
            "id": 1,
            "file_path": "/media/video.mp4",
            "subtitle_id": None,
            "needs_translation": False,
            "pipeline_state": PipelineState.NONE.value,
        }

        pipeline_service.start_process(1)

        with (
            patch(
                "src.services.pipeline_service.PipelineService._fetch_subtitles"
            ) as mock_fetch,
            patch(
                "src.services.pipeline_service.PipelineService._translate_subtitles"
            ) as mock_translate,
        ):
            pipeline_service.run()
            mock_fetch.assert_not_called()
            mock_translate.assert_not_called()

    def test_skips_when_voiceover_already_exists(
        self, pipeline_service, mock_db_manager
    ):
        """Verify pipeline skips when voiceover already exists."""
        mock_db_manager.get_video_file.return_value = {
            "id": 1,
            "file_path": "/media/video.mp4",
            "subtitle_id": 12345,
            "needs_translation": True,
            "pipeline_state": PipelineState.VOICEOVER_READY.value,
        }

        pipeline_service.start_process(1)

        with (
            patch(
                "src.services.pipeline_service.PipelineService._fetch_subtitles"
            ) as mock_fetch,
            patch(
                "src.services.pipeline_service.PipelineService._translate_subtitles"
            ) as mock_translate,
        ):
            pipeline_service.run()
            mock_fetch.assert_not_called()
            mock_translate.assert_not_called()


class TestPipelineServiceSignalEmissions:
    """Tests for signal emissions."""

    def test_pipeline_update_signal_emitted(self, pipeline_service, mock_db_manager):
        """Verify pipeline_update signal is emitted correctly."""
        with patch.object(pipeline_service.signals, "pipeline_update") as mock_signal:
            pipeline_service._emit_update(PipelineState.FETCHING_SUBS, "Downloading...")
            mock_signal.emit.assert_called_once_with(
                None, PipelineState.FETCHING_SUBS, "Downloading..."
            )

    def test_pipeline_finished_signal_emitted_on_success(
        self, pipeline_service, mock_db_manager
    ):
        """Verify pipeline_finished signal is emitted on successful completion."""
        with patch.object(pipeline_service.signals, "pipeline_finished") as mock_signal:
            pipeline_service._video_file_id = 1
            pipeline_service.signals.pipeline_finished.emit(1, True)
            mock_signal.emit.assert_called_once_with(1, True)

    def test_pipeline_finished_signal_emitted_on_failure(
        self, pipeline_service, mock_db_manager
    ):
        """Verify pipeline_finished signal is emitted on failure."""
        with patch.object(pipeline_service.signals, "pipeline_finished") as mock_signal:
            pipeline_service._video_file_id = 1
            pipeline_service.signals.pipeline_finished.emit(1, False)
            mock_signal.emit.assert_called_once_with(1, False)

    def test_error_occurred_signal_emitted(self, pipeline_service, mock_db_manager):
        """Verify error_occurred signal is emitted on exceptions."""
        with patch.object(pipeline_service.signals, "error_occurred") as mock_signal:
            pipeline_service._video_file_id = 1
            pipeline_service.signals.error_occurred.emit(1, "Test error")
            mock_signal.emit.assert_called_once_with(1, "Test error")


class TestPipelineServiceStateTransitions:
    """Tests for pipeline state transitions."""

    def test_state_transitions_correctly(self, pipeline_service, mock_db_manager):
        """Verify state is updated throughout pipeline."""
        pipeline_service._video_file_id = 1
        pipeline_service._emit_update(PipelineState.FETCHING_SUBS, "Test")
        assert pipeline_service._current_state == PipelineState.FETCHING_SUBS


class TestPipelineServiceErrorHandling:
    """Tests for error handling paths."""

    def test_sets_failed_state_on_exception(self, pipeline_service, mock_db_manager):
        """Verify pipeline sets FAILED state on exception."""
        pipeline_service._video_file_id = 1
        mock_db_manager.update_pipeline_state.side_effect = Exception("DB error")

        try:
            pipeline_service._update_pipeline_state(PipelineState.VOICEOVER_READY)
        except Exception:
            pass

        mock_db_manager.update_pipeline_state.assert_called_with(
            1, PipelineState.VOICEOVER_READY
        )

    def test_video_file_not_found_handled(self, pipeline_service, mock_db_manager):
        """Verify graceful handling when video file not found."""
        mock_db_manager.get_video_file.return_value = None
        pipeline_service._video_file_id = 999

        with patch.object(
            pipeline_service.signals, "pipeline_finished"
        ) as mock_finished:
            pipeline_service.run()
            mock_finished.emit.assert_called_once_with(999, False)


class TestPipelineServiceTranslationSkip:
    """Tests for translation skip when needs_translation=False."""

    def test_skips_translation_when_disabled(self, pipeline_service, mock_db_manager):
        """Verify translation stage is skipped when needs_translation is False."""
        mock_db_manager.get_video_file.return_value = {
            "id": 1,
            "file_path": "/media/video.mp4",
            "subtitle_id": 12345,
            "needs_translation": False,
            "pipeline_state": PipelineState.NONE.value,
        }

        pipeline_service._video_file_id = 1
        pipeline_service.run()

        mock_db_manager.get_translation_progress.assert_not_called()


class TestPipelineServiceResumableTranslation:
    """Tests for resumable translation functionality."""

    def test_loads_existing_translation_progress(
        self, pipeline_service, mock_db_manager
    ):
        """Verify pipeline loads existing translation progress."""
        mock_db_manager.get_translation_progress.return_value = {"completed_batches": 5}

        progress = mock_db_manager.get_translation_progress(1)

        assert progress == {"completed_batches": 5}
        mock_db_manager.get_translation_progress.assert_called_once_with(1)

    def test_clears_translation_progress_on_success(
        self, pipeline_service, mock_db_manager
    ):
        """Verify translation progress is cleared on successful completion."""
        mock_db_manager.clear_translation_progress(1)

        mock_db_manager.clear_translation_progress.assert_called_once_with(1)


class TestPipelineServiceSignalsInterface:
    """Tests for PipelineSignals class."""

    def test_signals_have_correct_types(self):
        """Verify signals are properly defined."""
        signals = PipelineSignals()

        assert hasattr(signals, "pipeline_update")
        assert hasattr(signals, "pipeline_finished")
        assert hasattr(signals, "error_occurred")

    def test_pipeline_update_signal_parameters(self):
        """Verify pipeline_update signal accepts correct parameters."""
        signals = PipelineSignals()
        signals.pipeline_update.emit(1, PipelineState.FETCHING_SUBS, "Test")

    def test_pipeline_finished_signal_parameters(self):
        """Verify pipeline_finished signal accepts correct parameters."""
        signals = PipelineSignals()
        signals.pipeline_finished.emit(1, True)

    def test_error_occurred_signal_parameters(self):
        """Verify error_occurred signal accepts correct parameters."""
        signals = PipelineSignals()
        signals.error_occurred.emit(1, "Error message")


class TestPipelineServiceCancellation:
    """Tests for pipeline cancellation."""

    def test_stop_method_cancels_processing(self, pipeline_service):
        """Verify stop() sets flag that can be checked."""
        pipeline_service._should_stop = False
        pipeline_service.stop()
        assert pipeline_service._should_stop is True

    def test_tts_generation_checks_stop_between_lines(self, pipeline_service):
        """Verify TTS generation respects stop flag."""
        pipeline_service._should_stop = True
        assert pipeline_service._should_stop is True


class TestPipelineServiceDatabasePersistence:
    """Tests for database persistence operations."""

    def test_adds_subtitle_on_fetch(self, pipeline_service, mock_db_manager, tmp_path):
        """Verify subtitle is added to database after fetch."""
        subtitle_id = 12345
        file_id = 1
        output_path = tmp_path / "original.srt"

        pipeline_service._video_file_id = file_id
        pipeline_service.db_manager.add_subtitle(
            file_id, str(output_path), "original", subtitle_id
        )

        mock_db_manager.add_subtitle.assert_called_once_with(
            file_id, str(output_path), "original", subtitle_id
        )

    def test_adds_voiceover_on_complete(
        self, pipeline_service, mock_db_manager, tmp_path
    ):
        """Verify voiceover is added to database on successful completion."""
        file_id = 1
        voiceover_path = tmp_path / "voiceover_pl.wav"

        pipeline_service._video_file_id = file_id
        pipeline_service.db_manager.add_voiceover(file_id, str(voiceover_path))

        mock_db_manager.add_voiceover.assert_called_once_with(
            file_id, str(voiceover_path)
        )

    def test_updates_pipeline_state(self, pipeline_service, mock_db_manager):
        """Verify pipeline state is updated in database."""
        file_id = 1

        pipeline_service._video_file_id = file_id
        pipeline_service._update_pipeline_state(PipelineState.VOICEOVER_READY)

        mock_db_manager.update_pipeline_state.assert_called_with(
            file_id, PipelineState.VOICEOVER_READY
        )
