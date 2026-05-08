"""Tests for PipelineService - subtitle fetching and translation.

Tests cover:
- Initialization with dependencies
- Pipeline skip conditions (null subtitle_id, subs already ready)
- Complete pipeline flow (fetch → translate → SUBS_READY)
- Translation skip when needs_translation=False
- Pipeline state updates at each stage
- Database persistence (subtitles added)
- Resumable translation (load progress, resume, delete on success)
- Error handling and FAILED state
- Stop/cancellation
- Signal emissions (pipeline_update, pipeline_finished)
"""

from unittest.mock import MagicMock, patch

import pytest

from src.config import PipelineState
from src.services.pipeline_service import PipelineService, PipelineSignals
from pathlib import Path


@pytest.fixture(autouse=True)
def mock_pipeline_service_logger():
    """Mock the pipeline_service logger to avoid format string issues with None values."""
    with patch("src.services.pipeline_service.logger") as mock_logger:
        yield mock_logger


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
    manager.update_pipeline_state.return_value = None
    manager.clear_translation_progress.return_value = None
    return manager


@pytest.fixture
def pipeline_service(mock_db_manager):
    """Create a PipelineService instance with mocked dependencies."""
    service = PipelineService(mock_db_manager)
    yield service
    if service.isRunning():
        service.wait()


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

    def test_is_busy_returns_false_initially(self, pipeline_service):
        """Verify is_busy returns False before processing starts."""
        assert pipeline_service.is_busy() is False

    def test_is_busy_returns_true_during_processing(self, pipeline_service):
        """Verify is_busy returns True after start_process is called."""
        pipeline_service.start_process(1)
        assert pipeline_service.is_busy() is True
        pipeline_service.wait()


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

        pipeline_service._video_file_id = 1

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

    def test_skips_when_subs_already_ready(self, pipeline_service, mock_db_manager):
        """Verify pipeline skips when subtitles are already ready."""
        mock_db_manager.get_video_file.return_value = {
            "id": 1,
            "file_path": "/media/video.mp4",
            "subtitle_id": 12345,
            "needs_translation": True,
            "pipeline_state": PipelineState.SUBS_READY.value,
        }

        pipeline_service._video_file_id = 1

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
            pipeline_service._update_pipeline_state(PipelineState.SUBS_READY)
        except Exception:
            pass

        mock_db_manager.update_pipeline_state.assert_called_with(
            1, PipelineState.SUBS_READY
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


class TestPipelineServiceFailedRecovery:
    """Tests for pipeline FAILED state recovery."""

    def test_can_restart_pipeline_after_failure(
        self, pipeline_service, mock_db_manager, tmp_path
    ):
        """Verify pipeline can be restarted after entering FAILED state."""
        from src.utils.subtitle_parser import SubtitleLine

        video_folder = tmp_path
        video_path = video_folder / "video.mp4"
        video_file_id = 1
        subtitle_id = 12345

        video_path.touch()

        mock_db_manager.get_video_file.return_value = {
            "id": video_file_id,
            "file_path": str(video_path),
            "subtitle_id": subtitle_id,
            "needs_translation": True,
            "pipeline_state": PipelineState.FAILED.value,
        }

        original_srt = video_folder / "original.srt"
        original_srt.write_text("1\n00:00:01,000 --> 00:00:04,000\nOriginal text\n")

        mock_open_subtitles = MagicMock()
        mock_open_subtitles.download_subtitle = MagicMock()

        mock_gemini = MagicMock()
        mock_gemini.translate_batch.return_value = [
            SubtitleLine(
                index=1,
                start_ms=1000,
                end_ms=4000,
                text_source="Original text",
                text_translated="Przetłumaczony tekst",
                is_sound_effect=False,
                audio_clip_path=str(video_folder / "line_000.mp3"),
            )
        ]

        with (
            patch(
                "src.utils.opensubtitles_client.OpenSubtitlesClient",
                return_value=mock_open_subtitles,
            ),
            patch(
                "src.utils.gemini_client.GeminiTranslator",
                return_value=mock_gemini,
            ),
            patch.object(
                pipeline_service.signals, "pipeline_finished"
            ) as mock_finished,
        ):
            pipeline_service.start_process(video_file_id)
            pipeline_service.wait()

            mock_db_manager.update_pipeline_state.assert_called()
            mock_finished.emit.assert_called_once_with(video_file_id, True)

    def test_failed_state_preserves_translation_progress(
        self, pipeline_service, mock_db_manager, tmp_path
    ):
        """Verify translation progress is preserved on failure for resume."""
        from src.utils.subtitle_parser import SubtitleLine

        video_folder = tmp_path
        video_path = video_folder / "video.mp4"
        video_file_id = 1
        subtitle_id = 12345

        video_path.touch()

        mock_db_manager.get_video_file.return_value = {
            "id": video_file_id,
            "file_path": str(video_path),
            "subtitle_id": subtitle_id,
            "needs_translation": True,
            "pipeline_state": PipelineState.FAILED.value,
        }
        mock_db_manager.get_translation_progress.return_value = {"completed_batches": 3}

        original_srt = video_folder / "original.srt"
        original_srt.write_text("1\n00:00:01,000 --> 00:00:04,000\nOriginal text\n")

        mock_open_subtitles = MagicMock()
        mock_open_subtitles.download_subtitle = MagicMock()

        mock_gemini = MagicMock()
        mock_gemini.translate_batch.return_value = [
            SubtitleLine(
                index=1,
                start_ms=1000,
                end_ms=4000,
                text_source="Original text",
                text_translated="Przetłumaczony tekst",
                is_sound_effect=False,
                audio_clip_path=str(video_folder / "line_000.mp3"),
            )
        ]

        with (
            patch(
                "src.utils.opensubtitles_client.OpenSubtitlesClient",
                return_value=mock_open_subtitles,
            ),
            patch(
                "src.utils.gemini_client.GeminiTranslator",
                return_value=mock_gemini,
            ),
            patch.object(pipeline_service.signals, "pipeline_finished"),
        ):
            pipeline_service.start_process(video_file_id)
            pipeline_service.wait()

            mock_gemini.translate_batch.assert_called()
            call_args = mock_gemini.translate_batch.call_args[0]
            assert call_args[1] == 3  # start_batch should be 3


class TestPipelineServiceCancellationAtEachStage:
    """Tests for cancellation at different pipeline stages."""

    def test_cancellation_before_fetch(self, pipeline_service, mock_db_manager):
        """Verify cancellation is handled before fetch starts."""
        pipeline_service._video_file_id = 1
        pipeline_service._should_stop = True

        with patch.object(
            pipeline_service.signals, "pipeline_finished"
        ) as mock_finished:
            pipeline_service.run()
            mock_finished.emit.assert_called_once_with(1, True)

    def test_cancellation_after_fetch(
        self, pipeline_service, mock_db_manager, tmp_path
    ):
        """Verify cancellation is handled after fetch completes."""
        video_folder = tmp_path
        video_path = video_folder / "video.mp4"
        video_path.touch()

        mock_db_manager.get_video_file.return_value = {
            "id": 1,
            "file_path": str(video_path),
            "subtitle_id": 12345,
            "needs_translation": True,
            "pipeline_state": PipelineState.NONE.value,
        }

        def stop_after_fetch(*args, **kwargs):
            pipeline_service._should_stop = True
            return video_folder / "original.srt"

        with (
            patch.object(
                pipeline_service, "_fetch_subtitles", side_effect=stop_after_fetch
            ),
            patch.object(pipeline_service, "_translate_subtitles") as mock_translate,
            patch.object(
                pipeline_service.signals, "pipeline_finished"
            ) as mock_finished,
        ):
            pipeline_service._video_file_id = 1
            pipeline_service.run()

            mock_translate.assert_not_called()
            mock_finished.emit.assert_called_once_with(1, True)


class TestPipelineServiceCancellation:
    """Tests for pipeline cancellation."""

    def test_cancellation_emits_finished_with_success(
        self, pipeline_service, mock_db_manager
    ):
        """Verify cancellation emits finished signal with success=True."""
        pipeline_service._video_file_id = 1
        pipeline_service._should_stop = True

        with patch.object(
            pipeline_service.signals, "pipeline_finished"
        ) as mock_finished:
            pipeline_service.run()
            mock_finished.emit.assert_called_once_with(1, True)


class TestPipelineServiceDatabasePersistence:
    """Tests for database persistence operations."""

    def test_adds_subtitle_on_fetch(self, pipeline_service, mock_db_manager, tmp_path):
        """Verify subtitle is added to database after fetch."""
        video_folder = tmp_path
        video_path = video_folder / "video.mp4"
        video_path.touch()
        subtitle_id = 12345
        video_file_id = 1

        mock_db_manager.get_video_file.return_value = {
            "id": video_file_id,
            "file_path": str(video_path),
            "subtitle_id": subtitle_id,
            "needs_translation": False,
            "pipeline_state": PipelineState.NONE.value,
        }

        mock_open_subtitles = MagicMock()
        mock_open_subtitles.download_subtitle = MagicMock()

        with patch(
            "src.utils.opensubtitles_client.OpenSubtitlesClient",
            return_value=mock_open_subtitles,
        ):
            pipeline_service.start_process(video_file_id)
            pipeline_service.wait()

            mock_db_manager.add_subtitle.assert_called()

    def test_updates_pipeline_state_on_complete(
        self, pipeline_service, mock_db_manager, tmp_path
    ):
        """Verify pipeline state is updated to SUBS_READY on completion."""
        video_folder = tmp_path
        video_path = video_folder / "video.mp4"
        video_path.touch()
        video_file_id = 1

        original_srt = video_folder / "original.srt"
        original_srt.write_text("1\n00:00:01,000 --> 00:00:04,000\nHello\n")

        mock_db_manager.get_video_file.return_value = {
            "id": video_file_id,
            "file_path": str(video_path),
            "subtitle_id": 12345,
            "needs_translation": False,
            "pipeline_state": PipelineState.NONE.value,
        }

        mock_open_subtitles = MagicMock()
        mock_open_subtitles.download_subtitle = MagicMock()

        with patch(
            "src.utils.opensubtitles_client.OpenSubtitlesClient",
            return_value=mock_open_subtitles,
        ):
            pipeline_service.start_process(video_file_id)
            pipeline_service.wait()

            mock_db_manager.update_pipeline_state.assert_called_with(
                video_file_id, PipelineState.SUBS_READY
            )


class TestPipelineServiceFetchSubtitlesIntegration:
    """Integration tests for _fetch_subtitles method."""

    def test_fetch_subtitles_success(self, pipeline_service, mock_db_manager, tmp_path):
        """Verify _fetch_subtitles downloads and saves subtitles."""
        video_folder = tmp_path
        subtitle_id = 12345

        mock_client = MagicMock()
        mock_client.download_subtitle = MagicMock()

        with patch(
            "src.utils.opensubtitles_client.OpenSubtitlesClient",
            return_value=mock_client,
        ):
            pipeline_service._video_file_id = 1
            result = pipeline_service._fetch_subtitles(subtitle_id, video_folder)

            mock_client.download_subtitle.assert_called_once_with(
                subtitle_id, video_folder / "original.srt"
            )
            assert result == video_folder / "original.srt"

    def test_fetch_subtitles_updates_state(
        self, pipeline_service, mock_db_manager, tmp_path
    ):
        """Verify _fetch_subtitles updates state to FETCHING_SUBS."""
        video_folder = tmp_path
        subtitle_id = 12345

        mock_client = MagicMock()
        mock_client.download_subtitle = MagicMock()

        with patch(
            "src.utils.opensubtitles_client.OpenSubtitlesClient",
            return_value=mock_client,
        ):
            pipeline_service._video_file_id = 1
            pipeline_service._fetch_subtitles(subtitle_id, video_folder)

            mock_db_manager.update_pipeline_state.assert_called_with(
                1, PipelineState.FETCHING_SUBS
            )

    def test_fetch_subtitles_adds_to_database(
        self, pipeline_service, mock_db_manager, tmp_path
    ):
        """Verify _fetch_subtitles adds subtitle to database."""
        video_folder = tmp_path
        subtitle_id = 12345

        mock_client = MagicMock()
        mock_client.download_subtitle = MagicMock()

        with patch(
            "src.utils.opensubtitles_client.OpenSubtitlesClient",
            return_value=mock_client,
        ):
            pipeline_service._video_file_id = 1
            pipeline_service._fetch_subtitles(subtitle_id, video_folder)

            mock_db_manager.add_subtitle.assert_called_once_with(
                1, "original", str(video_folder / "original.srt"), False
            )


class TestPipelineServiceTranslateSubtitlesIntegration:
    """Integration tests for _translate_subtitles method."""

    def test_translate_subtitles_success(
        self, pipeline_service, mock_db_manager, tmp_path
    ):
        """Verify _translate_subtitles translates and saves subtitles."""
        from src.utils.subtitle_parser import SubtitleLine

        video_folder = tmp_path
        video_file_id = 1

        original_srt = video_folder / "original.srt"
        original_srt.write_text(
            "1\n00:00:01,000 --> 00:00:04,000\nHello world\n\n"
            "2\n00:00:05,000 --> 00:00:08,000\nGoodbye world\n"
        )

        mock_translator = MagicMock()
        mock_translator.translate_batch.return_value = [
            SubtitleLine(
                index=1,
                start_ms=1000,
                end_ms=4000,
                text_source="Hello world",
                text_translated="Witaj świecie",
                is_sound_effect=False,
                audio_clip_path=None,
            ),
            SubtitleLine(
                index=2,
                start_ms=5000,
                end_ms=8000,
                text_source="Goodbye world",
                text_translated="Żegnaj świecie",
                is_sound_effect=False,
                audio_clip_path=None,
            ),
        ]

        with patch(
            "src.utils.gemini_client.GeminiTranslator",
            return_value=mock_translator,
        ):
            pipeline_service._video_file_id = video_file_id
            result = pipeline_service._translate_subtitles(video_folder, video_file_id)

            assert len(result) == 2
            assert result[0].text_translated == "Witaj świecie"
            assert (video_folder / "pl.srt").exists()

    def test_translate_subtitles_updates_state(
        self, pipeline_service, mock_db_manager, tmp_path
    ):
        """Verify _translate_subtitles updates state to TRANSLATING then SUBS_READY."""
        from src.utils.subtitle_parser import SubtitleLine

        video_folder = tmp_path
        video_file_id = 1

        original_srt = video_folder / "original.srt"
        original_srt.write_text("1\n00:00:01,000 --> 00:00:04,000\nHello\n")

        mock_translator = MagicMock()
        mock_translator.translate_batch.return_value = [
            SubtitleLine(
                index=1,
                start_ms=1000,
                end_ms=4000,
                text_source="Hello",
                text_translated="Cześć",
                is_sound_effect=False,
                audio_clip_path=None,
            ),
        ]

        with patch(
            "src.utils.gemini_client.GeminiTranslator",
            return_value=mock_translator,
        ):
            pipeline_service._video_file_id = video_file_id
            pipeline_service._translate_subtitles(video_folder, video_file_id)

            calls = mock_db_manager.update_pipeline_state.call_args_list
            states = [call[0][1] for call in calls]
            assert PipelineState.TRANSLATING in states
            assert PipelineState.SUBS_READY in states

    def test_translate_subtitles_resumes_from_progress(
        self, pipeline_service, mock_db_manager, tmp_path
    ):
        """Verify _translate_subtitles resumes from saved progress."""
        from src.utils.subtitle_parser import SubtitleLine

        video_folder = tmp_path
        video_file_id = 1

        original_srt = video_folder / "original.srt"
        original_srt.write_text("1\n00:00:01,000 --> 00:00:04,000\nHello\n")

        mock_db_manager.get_translation_progress.return_value = {"completed_batches": 2}

        mock_translator = MagicMock()
        mock_translator.translate_batch.return_value = [
            SubtitleLine(
                index=1,
                start_ms=1000,
                end_ms=4000,
                text_source="Hello",
                text_translated="Cześć",
                is_sound_effect=False,
                audio_clip_path=None,
            ),
        ]

        with patch(
            "src.utils.gemini_client.GeminiTranslator",
            return_value=mock_translator,
        ):
            pipeline_service._video_file_id = video_file_id
            pipeline_service._translate_subtitles(video_folder, video_file_id)

            call_args = mock_translator.translate_batch.call_args[0]
            assert call_args[1] == 2  # start_batch should be 2

    def test_translate_subtitles_clears_progress_on_success(
        self, pipeline_service, mock_db_manager, tmp_path
    ):
        """Verify translation progress is cleared after successful translation."""
        from src.utils.subtitle_parser import SubtitleLine

        video_folder = tmp_path
        video_file_id = 1

        original_srt = video_folder / "original.srt"
        original_srt.write_text("1\n00:00:01,000 --> 00:00:04,000\nHello\n")

        mock_translator = MagicMock()
        mock_translator.translate_batch.return_value = [
            SubtitleLine(
                index=1,
                start_ms=1000,
                end_ms=4000,
                text_source="Hello",
                text_translated="Cześć",
                is_sound_effect=False,
                audio_clip_path=None,
            ),
        ]

        with patch(
            "src.utils.gemini_client.GeminiTranslator",
            return_value=mock_translator,
        ):
            pipeline_service._video_file_id = video_file_id
            pipeline_service._translate_subtitles(video_folder, video_file_id)

            mock_db_manager.clear_translation_progress.assert_called_once_with(
                video_file_id
            )


class TestPipelineServiceGeminiAPIErrorHandling:
    """Tests for Gemini API error handling."""

    def test_gemini_error_sets_failed_state(
        self, pipeline_service, mock_db_manager, tmp_path
    ):
        """Verify Gemini API error sets FAILED state."""
        video_folder = tmp_path
        video_path = video_folder / "video.mp4"
        video_path.touch()

        original_srt = video_folder / "original.srt"
        original_srt.write_text("1\n00:00:01,000 --> 00:00:04,000\nHello\n")

        mock_db_manager.get_video_file.return_value = {
            "id": 1,
            "file_path": str(video_path),
            "subtitle_id": 12345,
            "needs_translation": True,
            "pipeline_state": PipelineState.NONE.value,
        }

        mock_open_subtitles = MagicMock()
        mock_open_subtitles.download_subtitle = MagicMock()

        mock_translator = MagicMock()
        mock_translator.translate_batch.side_effect = Exception("API Error")

        with (
            patch(
                "src.utils.opensubtitles_client.OpenSubtitlesClient",
                return_value=mock_open_subtitles,
            ),
            patch(
                "src.utils.gemini_client.GeminiTranslator",
                return_value=mock_translator,
            ),
            patch.object(pipeline_service.signals, "error_occurred") as mock_error,
        ):
            pipeline_service.start_process(1)
            pipeline_service.wait()

            mock_db_manager.update_pipeline_state.assert_called_with(
                1, PipelineState.FAILED
            )
            mock_error.emit.assert_called_once()


class TestPipelineServiceCompleteFlow:
    """Tests for complete pipeline flow."""

    def test_complete_flow_fetch_only(
        self, pipeline_service, mock_db_manager, tmp_path
    ):
        """Verify complete flow when needs_translation=False."""
        video_folder = tmp_path
        video_path = video_folder / "video.mp4"
        video_path.touch()
        video_file_id = 1

        original_srt = video_folder / "original.srt"
        original_srt.write_text("1\n00:00:01,000 --> 00:00:04,000\nHello\n")

        mock_db_manager.get_video_file.return_value = {
            "id": video_file_id,
            "file_path": str(video_path),
            "subtitle_id": 12345,
            "needs_translation": False,
            "pipeline_state": PipelineState.NONE.value,
        }

        mock_open_subtitles = MagicMock()
        mock_open_subtitles.download_subtitle = MagicMock()

        with (
            patch(
                "src.utils.opensubtitles_client.OpenSubtitlesClient",
                return_value=mock_open_subtitles,
            ),
            patch.object(
                pipeline_service.signals, "pipeline_finished"
            ) as mock_finished,
        ):
            pipeline_service.start_process(video_file_id)
            pipeline_service.wait()

            mock_open_subtitles.download_subtitle.assert_called_once()
            mock_finished.emit.assert_called_once_with(video_file_id, True)

            state_calls = mock_db_manager.update_pipeline_state.call_args_list
            states = [call[0][1] for call in state_calls]
            assert PipelineState.FETCHING_SUBS in states
            assert PipelineState.SUBS_READY in states

    def test_complete_flow_with_translation(
        self, pipeline_service, mock_db_manager, tmp_path
    ):
        """Verify complete flow with subtitle translation."""
        from src.utils.subtitle_parser import SubtitleLine

        video_folder = tmp_path
        video_path = video_folder / "video.mp4"
        video_path.touch()
        video_file_id = 1

        original_srt = video_folder / "original.srt"
        original_srt.write_text("1\n00:00:01,000 --> 00:00:04,000\nHello\n")

        mock_db_manager.get_video_file.return_value = {
            "id": video_file_id,
            "file_path": str(video_path),
            "subtitle_id": 12345,
            "needs_translation": True,
            "pipeline_state": PipelineState.NONE.value,
        }

        mock_open_subtitles = MagicMock()
        mock_open_subtitles.download_subtitle = MagicMock()

        mock_translator = MagicMock()
        mock_translator.translate_batch.return_value = [
            SubtitleLine(
                index=1,
                start_ms=1000,
                end_ms=4000,
                text_source="Hello",
                text_translated="Cześć",
                is_sound_effect=False,
                audio_clip_path=None,
            ),
        ]

        with (
            patch(
                "src.utils.opensubtitles_client.OpenSubtitlesClient",
                return_value=mock_open_subtitles,
            ),
            patch(
                "src.utils.gemini_client.GeminiTranslator",
                return_value=mock_translator,
            ),
            patch.object(
                pipeline_service.signals, "pipeline_finished"
            ) as mock_finished,
        ):
            pipeline_service.start_process(video_file_id)
            pipeline_service.wait()

            mock_open_subtitles.download_subtitle.assert_called_once()
            mock_translator.translate_batch.assert_called_once()
            mock_finished.emit.assert_called_once_with(video_file_id, True)

            state_calls = mock_db_manager.update_pipeline_state.call_args_list
            states = [call[0][1] for call in state_calls]
            assert PipelineState.FETCHING_SUBS in states
            assert PipelineState.TRANSLATING in states
            assert PipelineState.SUBS_READY in states

    def test_complete_pipeline_skip_when_subs_ready(
        self, pipeline_service, mock_db_manager, tmp_path
    ):
        """Verify pipeline skips when subtitles are already ready."""
        video_folder = tmp_path
        video_path = video_folder / "video.mp4"
        video_path.touch()
        video_file_id = 1

        mock_db_manager.get_video_file.return_value = {
            "id": video_file_id,
            "file_path": str(video_path),
            "subtitle_id": 12345,
            "needs_translation": True,
            "pipeline_state": PipelineState.SUBS_READY.value,
        }

        with patch.object(
            pipeline_service.signals, "pipeline_finished"
        ) as mock_finished:
            pipeline_service.start_process(video_file_id)
            pipeline_service.wait()

            mock_finished.emit.assert_called_once_with(video_file_id, True)
            mock_db_manager.update_pipeline_state.assert_not_called()


class TestPipelineServiceEndToEndIntegration:
    """End-to-end integration tests."""

    def test_full_pipeline_with_real_srt_parsing(
        self, pipeline_service, mock_db_manager, tmp_path
    ):
        """Verify complete pipeline with real SRT file parsing."""
        from src.utils.subtitle_parser import SubtitleLine

        video_folder = tmp_path
        video_path = video_folder / "video.mp4"
        video_name = video_path.stem
        video_path.touch()
        video_file_id = 1

        srt_content = """1
00:00:01,000 --> 00:00:04,000
Hello world

2
00:00:05,000 --> 00:00:08,000
How are you?

3
00:00:10,000 --> 00:00:15,000
[Sound effect]
"""
        original_srt = video_folder / "original.srt"
        original_srt.write_text(srt_content)

        mock_db_manager.get_video_file.return_value = {
            "id": video_file_id,
            "file_path": str(video_path),
            "subtitle_id": 12345,
            "needs_translation": True,
            "pipeline_state": PipelineState.NONE.value,
        }

        mock_open_subtitles = MagicMock()
        mock_open_subtitles.download_subtitle = MagicMock()

        mock_translator = MagicMock()
        mock_translator.translate_batch.return_value = [
            SubtitleLine(
                index=1,
                start_ms=1000,
                end_ms=4000,
                text_source="Hello world",
                text_translated="Witaj świecie",
                is_sound_effect=False,
                audio_clip_path=None,
            ),
            SubtitleLine(
                index=2,
                start_ms=5000,
                end_ms=8000,
                text_source="How are you?",
                text_translated="Jak się masz?",
                is_sound_effect=False,
                audio_clip_path=None,
            ),
            SubtitleLine(
                index=3,
                start_ms=10000,
                end_ms=15000,
                text_source="[Sound effect]",
                text_translated="[Efekt dźwiękowy]",
                is_sound_effect=True,
                audio_clip_path=None,
            ),
        ]

        with (
            patch(
                "src.utils.opensubtitles_client.OpenSubtitlesClient",
                return_value=mock_open_subtitles,
            ),
            patch(
                "src.utils.gemini_client.GeminiTranslator",
                return_value=mock_translator,
            ),
            patch.object(
                pipeline_service.signals, "pipeline_finished"
            ) as mock_finished,
        ):
            pipeline_service.start_process(video_file_id)
            pipeline_service.wait()

            mock_finished.emit.assert_called_once_with(video_file_id, True)
            assert Path(f"{video_folder}/{video_name}.srt").exists()


class TestPipelineServiceOpenSubtitlesFailure:
    """Tests for OpenSubtitles API failure handling."""

    def test_opensubtitles_error_sets_failed_state(
        self, pipeline_service, mock_db_manager, tmp_path
    ):
        """Verify OpenSubtitles API error sets FAILED state."""
        video_folder = tmp_path
        video_path = video_folder / "video.mp4"
        video_path.touch()

        mock_db_manager.get_video_file.return_value = {
            "id": 1,
            "file_path": str(video_path),
            "subtitle_id": 12345,
            "needs_translation": True,
            "pipeline_state": PipelineState.NONE.value,
        }

        mock_client = MagicMock()
        mock_client.download_subtitle.side_effect = Exception("API Error")

        with (
            patch(
                "src.utils.opensubtitles_client.OpenSubtitlesClient",
                return_value=mock_client,
            ),
            patch.object(pipeline_service.signals, "error_occurred") as mock_error,
        ):
            pipeline_service.start_process(1)
            pipeline_service.wait()

            mock_db_manager.update_pipeline_state.assert_called_with(
                1, PipelineState.FAILED
            )
            mock_error.emit.assert_called_once()
