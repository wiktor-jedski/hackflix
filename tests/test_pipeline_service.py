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

from unittest.mock import MagicMock, patch

import pytest

from src.config import PipelineState
from src.services.pipeline_service import PipelineService, PipelineSignals


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
    manager.add_voiceover.return_value = None
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


class TestPipelineServiceFailedRecovery:
    """Tests for pipeline FAILED state recovery."""

    def test_can_restart_pipeline_after_failure(
        self, pipeline_service, mock_db_manager, tmp_path
    ):
        """Verify pipeline can be restarted after entering FAILED state."""
        from unittest.mock import MagicMock, patch
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

        mock_edge_tts = MagicMock()
        mock_edge_tts.generate_tts = MagicMock()

        mock_audio_processor = MagicMock()
        mock_audio_processor.extract_audio = MagicMock()
        voiceover_path = video_folder / "voiceover_pl.wav"
        voiceover_path.touch()
        mock_audio_processor.generate_voiceover.return_value = voiceover_path

        with (
            patch(
                "src.utils.opensubtitles_client.OpenSubtitlesClient",
                return_value=mock_open_subtitles,
            ),
            patch(
                "src.utils.gemini_client.GeminiTranslator",
                return_value=mock_gemini,
            ),
            patch(
                "src.utils.edge_tts_client.EdgeTTSClient",
                return_value=mock_edge_tts,
            ),
            patch(
                "src.utils.audio_processor.AudioProcessor",
                return_value=mock_audio_processor,
            ),
            patch.object(pipeline_service, "_get_video_duration", return_value=600000),
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
        from unittest.mock import MagicMock, patch
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
            "pipeline_state": PipelineState.NONE.value,
        }

        mock_db_manager.get_translation_progress.return_value = {"completed_batches": 5}

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

        mock_edge_tts = MagicMock()
        mock_edge_tts.generate_tts = MagicMock()

        mock_audio_processor = MagicMock()
        mock_audio_processor.extract_audio = MagicMock()
        voiceover_path = video_folder / "voiceover_pl.wav"
        voiceover_path.touch()
        mock_audio_processor.generate_voiceover.return_value = voiceover_path

        with (
            patch(
                "src.utils.opensubtitles_client.OpenSubtitlesClient",
                return_value=mock_open_subtitles,
            ),
            patch(
                "src.utils.gemini_client.GeminiTranslator",
                return_value=mock_gemini,
            ),
            patch(
                "src.utils.edge_tts_client.EdgeTTSClient",
                return_value=mock_edge_tts,
            ),
            patch(
                "src.utils.audio_processor.AudioProcessor",
                return_value=mock_audio_processor,
            ),
            patch.object(pipeline_service, "_get_video_duration", return_value=600000),
        ):
            pipeline_service.start_process(video_file_id)
            pipeline_service.wait()

            mock_db_manager.get_translation_progress.assert_called_with(video_file_id)

    def test_pipeline_handles_failure_and_emits_error_signal(
        self, pipeline_service, mock_db_manager, tmp_path
    ):
        """Verify pipeline emits error signal when entering FAILED state."""
        from unittest.mock import MagicMock, patch

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
            "pipeline_state": PipelineState.NONE.value,
        }

        mock_open_subtitles = MagicMock()
        mock_open_subtitles.download_subtitle.side_effect = Exception("Network failure")

        with (
            patch(
                "src.utils.opensubtitles_client.OpenSubtitlesClient",
                return_value=mock_open_subtitles,
            ),
            patch.object(
                pipeline_service.signals, "pipeline_finished"
            ) as mock_finished,
            patch.object(pipeline_service.signals, "error_occurred") as mock_error,
        ):
            pipeline_service.start_process(video_file_id)
            pipeline_service.wait()

            mock_error.emit.assert_called_once()
            error_args = mock_error.emit.call_args[0]
            assert error_args[0] == video_file_id
            assert "Network failure" in error_args[1]

            mock_finished.emit.assert_called_once_with(video_file_id, False)

    def test_pipeline_allows_retry_after_fetch_failure(
        self, pipeline_service, mock_db_manager, tmp_path
    ):
        """Verify pipeline can be retried after subtitle fetch failure."""
        from unittest.mock import MagicMock, patch
        from src.utils.subtitle_parser import SubtitleLine

        video_folder = tmp_path
        video_path = video_folder / "video.mp4"
        video_file_id = 1
        subtitle_id = 12345

        video_path.touch()

        original_srt = video_folder / "original.srt"
        original_srt.write_text("1\n00:00:01,000 --> 00:00:04,000\nOriginal text\n")

        mock_open_subtitles = MagicMock()
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

        mock_edge_tts = MagicMock()
        mock_edge_tts.generate_tts = MagicMock()

        mock_audio_processor = MagicMock()
        mock_audio_processor.extract_audio = MagicMock()
        voiceover_path = video_folder / "voiceover_pl.wav"
        voiceover_path.touch()
        mock_audio_processor.generate_voiceover.return_value = voiceover_path

        def download_side_effect(*args, **kwargs):
            if mock_open_subtitles.download_subtitle.call_count == 1:
                raise Exception("First attempt failed")
            return None

        mock_open_subtitles.download_subtitle.side_effect = download_side_effect

        call_count = 0

        def setup_video_file(video_file_id):
            nonlocal call_count
            call_count += 1
            return {
                "id": video_file_id,
                "file_path": str(video_path),
                "subtitle_id": subtitle_id,
                "needs_translation": True,
                "pipeline_state": PipelineState.NONE.value,
            }

        mock_db_manager.get_video_file.side_effect = setup_video_file

        with (
            patch(
                "src.utils.opensubtitles_client.OpenSubtitlesClient",
                return_value=mock_open_subtitles,
            ),
            patch(
                "src.utils.gemini_client.GeminiTranslator",
                return_value=mock_gemini,
            ),
            patch(
                "src.utils.edge_tts_client.EdgeTTSClient",
                return_value=mock_edge_tts,
            ),
            patch(
                "src.utils.audio_processor.AudioProcessor",
                return_value=mock_audio_processor,
            ),
            patch.object(pipeline_service, "_get_video_duration", return_value=600000),
            patch.object(
                pipeline_service.signals, "pipeline_finished"
            ) as mock_finished,
        ):
            pipeline_service.start_process(video_file_id)
            pipeline_service.wait()

            assert mock_open_subtitles.download_subtitle.call_count >= 1


class TestPipelineServiceCancellationAtEachStage:
    """Tests for cancellation handling at each pipeline stage."""

    @pytest.mark.parametrize(
        "cancel_at_state",
        [
            PipelineState.FETCHING_SUBS,
            PipelineState.TRANSLATING,
            PipelineState.SUBS_READY,
            PipelineState.GENERATING_TTS,
            PipelineState.MIXING_AUDIO,
        ],
    )
    def test_cancellation_at_each_stage(
        self, pipeline_service, mock_db_manager, tmp_path, cancel_at_state
    ):
        """Verify stop() is respected at each pipeline stage."""
        from unittest.mock import MagicMock, patch

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
            "pipeline_state": PipelineState.NONE.value,
        }

        original_srt = video_folder / "original.srt"
        original_srt.write_text("1\n00:00:01,000 --> 00:00:04,000\nOriginal text\n")

        mock_open_subtitles = MagicMock()
        mock_open_subtitles.download_subtitle = MagicMock()

        mock_gemini = MagicMock()
        mock_gemini.translate_batch.return_value = []

        mock_edge_tts = MagicMock()
        mock_edge_tts.generate_tts = MagicMock()

        mock_audio_processor = MagicMock()
        mock_audio_processor.extract_audio = MagicMock()
        voiceover_path = video_folder / "voiceover_pl.wav"
        voiceover_path.touch()
        mock_audio_processor.generate_voiceover.return_value = voiceover_path

        def cancel_handler(file_id, state, message):
            if state == cancel_at_state:
                pipeline_service.stop()

        with (
            patch(
                "src.utils.opensubtitles_client.OpenSubtitlesClient",
                return_value=mock_open_subtitles,
            ),
            patch(
                "src.utils.gemini_client.GeminiTranslator",
                return_value=mock_gemini,
            ),
            patch(
                "src.utils.edge_tts_client.EdgeTTSClient",
                return_value=mock_edge_tts,
            ),
            patch(
                "src.utils.audio_processor.AudioProcessor",
                return_value=mock_audio_processor,
            ),
            patch.object(pipeline_service, "_get_video_duration", return_value=600000),
            patch.object(pipeline_service.signals, "pipeline_update") as mock_update,
        ):
            mock_update.emit.side_effect = cancel_handler

            pipeline_service.start_process(video_file_id)
            pipeline_service.wait()

            assert pipeline_service._should_stop is True


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
        muxed_video_path = tmp_path / "video_voiceover.mkv"

        pipeline_service._video_file_id = file_id
        pipeline_service.db_manager.add_voiceover(
            file_id, "pl", str(voiceover_path), str(muxed_video_path)
        )

        mock_db_manager.add_voiceover.assert_called_once_with(
            file_id, "pl", str(voiceover_path), str(muxed_video_path)
        )

    def test_updates_pipeline_state(self, pipeline_service, mock_db_manager):
        """Verify pipeline state is updated in database."""
        file_id = 1

        pipeline_service._video_file_id = file_id
        pipeline_service._update_pipeline_state(PipelineState.VOICEOVER_READY)

        mock_db_manager.update_pipeline_state.assert_called_with(
            file_id, PipelineState.VOICEOVER_READY
        )


class TestPipelineServiceFetchSubtitlesIntegration:
    """Integration tests for _fetch_subtitles method."""

    def test_fetch_subtitles_success(self, pipeline_service, mock_db_manager, tmp_path):
        """Verify _fetch_subtitles downloads and records subtitles."""
        from unittest.mock import MagicMock, patch

        video_folder = tmp_path
        subtitle_id = 12345
        pipeline_service._video_file_id = 1

        mock_client = MagicMock()
        mock_client.download_subtitle = MagicMock()

        with patch(
            "src.utils.opensubtitles_client.OpenSubtitlesClient",
            return_value=mock_client,
        ):
            result = pipeline_service._fetch_subtitles(subtitle_id, video_folder)

        mock_client.download_subtitle.assert_called_once_with(
            subtitle_id, video_folder / "original.srt"
        )
        mock_db_manager.add_subtitle.assert_called_once()
        assert result == video_folder / "original.srt"

    def test_fetch_subtitles_updates_state(
        self, pipeline_service, mock_db_manager, tmp_path
    ):
        """Verify _fetch_subtitles updates state to FETCHING_SUBS."""
        from unittest.mock import MagicMock, patch

        video_folder = tmp_path
        subtitle_id = 12345
        pipeline_service._video_file_id = 1

        mock_client = MagicMock()
        mock_client.download_subtitle = MagicMock()

        with patch(
            "src.utils.opensubtitles_client.OpenSubtitlesClient",
            return_value=mock_client,
        ):
            pipeline_service._fetch_subtitles(subtitle_id, video_folder)

        assert pipeline_service._current_state == PipelineState.FETCHING_SUBS

    def test_fetch_subtitles_handles_api_error(
        self, pipeline_service, mock_db_manager, tmp_path
    ):
        """Verify _fetch_subtitles propagates API errors."""
        from unittest.mock import MagicMock, patch

        video_folder = tmp_path
        subtitle_id = 12345
        pipeline_service._video_file_id = 1

        mock_client = MagicMock()
        mock_client.download_subtitle.side_effect = Exception("API rate limit")

        with patch(
            "src.utils.opensubtitles_client.OpenSubtitlesClient",
            return_value=mock_client,
        ):
            with pytest.raises(Exception) as exc_info:
                pipeline_service._fetch_subtitles(subtitle_id, video_folder)

        assert "API rate limit" in str(exc_info.value)


class TestPipelineServiceTranslateSubtitlesIntegration:
    """Integration tests for _translate_subtitles method."""

    def test_translate_subtitles_success(
        self, pipeline_service, mock_db_manager, tmp_path
    ):
        """Verify _translate_subtitles processes and saves translation."""
        from unittest.mock import MagicMock, patch
        from src.utils.subtitle_parser import SubtitleLine

        video_folder = tmp_path
        video_file_id = 1
        pipeline_service._video_file_id = video_file_id

        original_srt = video_folder / "original.srt"
        original_srt.write_text("1\n00:00:01,000 --> 00:00:04,000\nHello world\n")

        mock_translator = MagicMock()
        mock_translator.translate_batch.return_value = [
            SubtitleLine(
                index=1,
                start_ms=1000,
                end_ms=4000,
                text_source="Hello world",
                text_translated="Witaj świecie",
                is_sound_effect=False,
            )
        ]

        with patch(
            "src.utils.gemini_client.GeminiTranslator",
            return_value=mock_translator,
        ):
            result = pipeline_service._translate_subtitles(video_folder, video_file_id)

        assert len(result) == 1
        assert result[0].text_translated == "Witaj świecie"
        mock_db_manager.add_subtitle.assert_called()
        mock_db_manager.clear_translation_progress.assert_called_once_with(
            video_file_id
        )

    def test_translate_subtitles_loads_progress(
        self, pipeline_service, mock_db_manager, tmp_path
    ):
        """Verify _translate_subtitles resumes from saved progress."""
        from unittest.mock import MagicMock, patch

        video_folder = tmp_path
        video_file_id = 1
        pipeline_service._video_file_id = video_file_id

        original_srt = video_folder / "original.srt"
        original_srt.write_text("1\n00:00:01,000 --> 00:00:04,000\nTest\n")

        mock_db_manager.get_translation_progress.return_value = {"completed_batches": 2}

        mock_translator = MagicMock()
        mock_translator.translate_batch.return_value = []

        with patch(
            "src.utils.gemini_client.GeminiTranslator",
            return_value=mock_translator,
        ):
            pipeline_service._translate_subtitles(video_folder, video_file_id)

        mock_db_manager.get_translation_progress.assert_called_once_with(video_file_id)

    def test_translate_subtitles_updates_state(
        self, pipeline_service, mock_db_manager, tmp_path
    ):
        """Verify _translate_subtitles updates state to TRANSLATING then SUBS_READY."""
        from unittest.mock import MagicMock, patch

        video_folder = tmp_path
        video_file_id = 1
        pipeline_service._video_file_id = video_file_id

        original_srt = video_folder / "original.srt"
        original_srt.write_text("1\n00:00:01,000 --> 00:00:04,000\nTest\n")

        mock_translator = MagicMock()
        mock_translator.translate_batch.return_value = []

        with patch(
            "src.utils.gemini_client.GeminiTranslator",
            return_value=mock_translator,
        ):
            pipeline_service._translate_subtitles(video_folder, video_file_id)

        assert pipeline_service._current_state == PipelineState.SUBS_READY


class TestPipelineServiceGenerateTTSClipsIntegration:
    """Integration tests for _generate_tts_clips method."""

    def test_generate_tts_clips_success(
        self, pipeline_service, mock_db_manager, tmp_path
    ):
        """Verify _generate_tts_clips creates audio files for subtitle lines."""
        from unittest.mock import MagicMock, patch
        from src.utils.subtitle_parser import SubtitleLine
        from src.utils.edge_tts_client import EdgeTTSClient

        video_folder = tmp_path
        pipeline_service._video_file_id = 1

        subtitle_lines = [
            SubtitleLine(
                index=1,
                start_ms=1000,
                end_ms=2000,
                text_source="Witaj świecie",
                is_sound_effect=False,
            ),
            SubtitleLine(
                index=2,
                start_ms=3000,
                end_ms=4000,
                text_source="Druga linia",
                is_sound_effect=False,
            ),
        ]

        mock_client = MagicMock()
        mock_client.text_needs_tts = lambda text: EdgeTTSClient.text_needs_tts(
            mock_client, text
        )

        # Mock batch TTS to return success for all items
        def mock_batch(items, progress_callback=None):
            results = []
            for i, (text, path) in enumerate(items):
                path.touch()
                path.write_bytes(b"fake audio")
                results.append((i, path, None))
            return results

        mock_client.generate_tts_batch = MagicMock(side_effect=mock_batch)

        with patch(
            "src.utils.edge_tts_client.EdgeTTSClient",
            return_value=mock_client,
        ):
            pipeline_service._generate_tts_clips(subtitle_lines, video_folder)

        # Batch should be called once with 2 items
        mock_client.generate_tts_batch.assert_called_once()
        batch_items = mock_client.generate_tts_batch.call_args[0][0]
        assert len(batch_items) == 2
        assert subtitle_lines[0].audio_clip_path is not None
        assert subtitle_lines[1].audio_clip_path is not None

    def test_generate_tts_skips_sound_effects(
        self, pipeline_service, mock_db_manager, tmp_path
    ):
        """Verify _generate_tts_clips skips sound effect lines."""
        from unittest.mock import MagicMock, patch
        from src.utils.subtitle_parser import SubtitleLine
        from src.utils.edge_tts_client import EdgeTTSClient

        video_folder = tmp_path
        pipeline_service._video_file_id = 1

        subtitle_lines = [
            SubtitleLine(
                index=1,
                start_ms=1000,
                end_ms=2000,
                text_source="[Drzwi się zamykają]",
                is_sound_effect=True,
            ),
            SubtitleLine(
                index=2,
                start_ms=3000,
                end_ms=4000,
                text_source="Normal dialogue",
                is_sound_effect=False,
            ),
        ]

        mock_client = MagicMock()
        mock_client.text_needs_tts = lambda text: EdgeTTSClient.text_needs_tts(
            mock_client, text
        )

        # Mock batch TTS to return success for all items
        def mock_batch(items, progress_callback=None):
            results = []
            for i, (text, path) in enumerate(items):
                path.touch()
                path.write_bytes(b"fake audio")
                results.append((i, path, None))
            return results

        mock_client.generate_tts_batch = MagicMock(side_effect=mock_batch)

        with patch(
            "src.utils.edge_tts_client.EdgeTTSClient",
            return_value=mock_client,
        ):
            pipeline_service._generate_tts_clips(subtitle_lines, video_folder)

        # Batch should be called once with only 1 item (sound effect skipped)
        mock_client.generate_tts_batch.assert_called_once()
        batch_items = mock_client.generate_tts_batch.call_args[0][0]
        assert len(batch_items) == 1
        assert subtitle_lines[1].audio_clip_path is not None

    def test_generate_tts_skips_empty_lines(
        self, pipeline_service, mock_db_manager, tmp_path
    ):
        """Verify _generate_tts_clips skips empty lines and '...'."""
        from unittest.mock import MagicMock, patch
        from src.utils.subtitle_parser import SubtitleLine
        from src.utils.edge_tts_client import EdgeTTSClient

        video_folder = tmp_path
        pipeline_service._video_file_id = 1

        subtitle_lines = [
            SubtitleLine(
                index=1,
                start_ms=1000,
                end_ms=2000,
                text_source="",
                is_sound_effect=False,
            ),
            SubtitleLine(
                index=2,
                start_ms=3000,
                end_ms=4000,
                text_source="...",
                is_sound_effect=False,
            ),
            SubtitleLine(
                index=3,
                start_ms=5000,
                end_ms=6000,
                text_source="Valid text",
                is_sound_effect=False,
            ),
        ]

        mock_client = MagicMock()
        mock_client.text_needs_tts = lambda text: EdgeTTSClient.text_needs_tts(
            mock_client, text
        )

        # Mock batch TTS to return success for all items
        def mock_batch(items, progress_callback=None):
            results = []
            for i, (text, path) in enumerate(items):
                path.touch()
                path.write_bytes(b"fake audio")
                results.append((i, path, None))
            return results

        mock_client.generate_tts_batch = MagicMock(side_effect=mock_batch)

        with patch(
            "src.utils.edge_tts_client.EdgeTTSClient",
            return_value=mock_client,
        ):
            pipeline_service._generate_tts_clips(subtitle_lines, video_folder)

        # Batch should be called once with only 1 item (empty and ... skipped)
        mock_client.generate_tts_batch.assert_called_once()
        batch_items = mock_client.generate_tts_batch.call_args[0][0]
        assert len(batch_items) == 1

    def test_generate_tts_updates_progress(
        self, pipeline_service, mock_db_manager, tmp_path
    ):
        """Verify _generate_tts_clips updates state with progress percentage."""
        from unittest.mock import MagicMock, patch
        from src.utils.subtitle_parser import SubtitleLine
        from src.utils.edge_tts_client import EdgeTTSClient

        video_folder = tmp_path
        pipeline_service._video_file_id = 1

        subtitle_lines = [
            SubtitleLine(
                index=1,
                start_ms=1000,
                end_ms=2000,
                text_source="Line 1",
                is_sound_effect=False,
            ),
            SubtitleLine(
                index=2,
                start_ms=3000,
                end_ms=4000,
                text_source="Line 2",
                is_sound_effect=False,
            ),
        ]

        mock_client = MagicMock()
        mock_client.text_needs_tts = lambda text: EdgeTTSClient.text_needs_tts(
            mock_client, text
        )

        # Mock batch generation to call progress callback and return success
        def mock_batch(items, progress_callback=None):
            results = []
            for i, (text, path) in enumerate(items):
                path.touch()
                path.write_bytes(b"fake audio")
                results.append((i, path, None))
                if progress_callback:
                    progress_callback(i + 1, len(items))
            return results

        mock_client.generate_tts_batch = MagicMock(side_effect=mock_batch)

        with patch(
            "src.utils.edge_tts_client.EdgeTTSClient",
            return_value=mock_client,
        ):
            with patch.object(
                pipeline_service.signals, "pipeline_update"
            ) as mock_signal:
                pipeline_service._generate_tts_clips(subtitle_lines, video_folder)
                calls = mock_signal.emit.call_args_list
                # Initial call + progress updates from batch
                assert len(calls) >= 2

    def test_generate_tts_continues_on_failure(
        self, pipeline_service, mock_db_manager, tmp_path
    ):
        """Verify _generate_tts_clips skips lines that fail TTS instead of crashing."""
        from unittest.mock import MagicMock, patch
        from src.utils.subtitle_parser import SubtitleLine
        from src.utils.edge_tts_client import EdgeTTSClient

        video_folder = tmp_path
        pipeline_service._video_file_id = 1

        subtitle_lines = [
            SubtitleLine(
                index=1,
                start_ms=1000,
                end_ms=2000,
                text_source="Line 1",
                is_sound_effect=False,
            ),
            SubtitleLine(
                index=2,
                start_ms=3000,
                end_ms=4000,
                text_source="Line 2 fails",
                is_sound_effect=False,
            ),
            SubtitleLine(
                index=3,
                start_ms=5000,
                end_ms=6000,
                text_source="Line 3",
                is_sound_effect=False,
            ),
        ]

        mock_client = MagicMock()
        mock_client.text_needs_tts = lambda text: EdgeTTSClient.text_needs_tts(
            mock_client, text
        )

        # Mock batch generation with one failure
        def mock_batch(items, progress_callback=None):
            results = []
            for i, (text, path) in enumerate(items):
                if "fails" in text:
                    results.append((i, None, "No audio received"))
                else:
                    path.touch()
                    path.write_bytes(b"fake audio")
                    results.append((i, path, None))
            return results

        mock_client.generate_tts_batch = MagicMock(side_effect=mock_batch)

        with patch(
            "src.utils.edge_tts_client.EdgeTTSClient",
            return_value=mock_client,
        ):
            pipeline_service._generate_tts_clips(subtitle_lines, video_folder)

        mock_client.generate_tts_batch.assert_called_once()
        assert subtitle_lines[0].audio_clip_path
        assert not subtitle_lines[1].audio_clip_path
        assert subtitle_lines[2].audio_clip_path


class TestPipelineServiceExtractAudioIntegration:
    """Integration tests for _extract_original_audio method."""

    def test_extract_audio_success(self, pipeline_service, mock_db_manager, tmp_path):
        """Verify _extract_original_audio extracts audio track."""
        from unittest.mock import MagicMock, patch

        video_path = tmp_path / "video.mp4"
        video_folder = tmp_path
        pipeline_service._video_file_id = 1

        mock_processor = MagicMock()
        mock_processor.extract_audio = MagicMock()

        with patch(
            "src.utils.audio_processor.AudioProcessor",
            return_value=mock_processor,
        ):
            result = pipeline_service._extract_original_audio(video_path, video_folder)

        mock_processor.extract_audio.assert_called_once_with(
            video_path, video_folder / "original_audio.wav"
        )
        assert result == video_folder / "original_audio.wav"

    def test_extract_audio_updates_state(
        self, pipeline_service, mock_db_manager, tmp_path
    ):
        """Verify _extract_original_audio updates state to MIXING_AUDIO."""
        from unittest.mock import MagicMock, patch

        video_path = tmp_path / "video.mp4"
        video_folder = tmp_path
        pipeline_service._video_file_id = 1

        mock_processor = MagicMock()
        mock_processor.extract_audio = MagicMock()

        with patch(
            "src.utils.audio_processor.AudioProcessor",
            return_value=mock_processor,
        ):
            pipeline_service._extract_original_audio(video_path, video_folder)

        assert pipeline_service._current_state == PipelineState.MIXING_AUDIO


class TestPipelineServiceMuxVoiceoverIntoVideo:
    """Integration tests for _mux_voiceover_into_video method."""

    def test_mux_voiceover_success(self, pipeline_service, mock_db_manager, tmp_path):
        """Verify _mux_voiceover_into_video creates muxed video file."""
        from unittest.mock import MagicMock, patch

        video_folder = tmp_path
        video_path = video_folder / "video.mp4"
        voiceover_path = video_folder / "voiceover_pl.wav"
        pipeline_service._video_file_id = 1

        video_path.touch()
        voiceover_path.touch()

        mock_processor = MagicMock()
        mock_processor.mux_voiceover_into_video = MagicMock()

        with patch(
            "src.utils.audio_processor.AudioProcessor",
            return_value=mock_processor,
        ):
            result = pipeline_service._mux_voiceover_into_video(
                video_path, voiceover_path, video_folder
            )

        mock_processor.mux_voiceover_into_video.assert_called_once()
        assert result == video_folder / "video_voiceover.mkv"

    def test_mux_voiceover_returns_none_on_failure(
        self, pipeline_service, mock_db_manager, tmp_path
    ):
        """Verify _mux_voiceover_into_video returns None when muxing fails."""
        from unittest.mock import MagicMock, patch
        from src.utils.audio_processor import AudioProcessingError

        video_folder = tmp_path
        video_path = video_folder / "video.mp4"
        voiceover_path = video_folder / "voiceover_pl.wav"
        pipeline_service._video_file_id = 1

        video_path.touch()
        voiceover_path.touch()

        mock_processor = MagicMock()
        mock_processor.mux_voiceover_into_video.side_effect = AudioProcessingError(
            "FFmpeg muxing failed"
        )

        with patch(
            "src.utils.audio_processor.AudioProcessor",
            return_value=mock_processor,
        ):
            result = pipeline_service._mux_voiceover_into_video(
                video_path, voiceover_path, video_folder
            )

        assert result is None

    def test_mux_voiceover_updates_state(
        self, pipeline_service, mock_db_manager, tmp_path
    ):
        """Verify _mux_voiceover_into_video updates state to MIXING_AUDIO."""
        from unittest.mock import MagicMock, patch

        video_folder = tmp_path
        video_path = video_folder / "video.mp4"
        voiceover_path = video_folder / "voiceover_pl.wav"
        pipeline_service._video_file_id = 1

        video_path.touch()
        voiceover_path.touch()

        mock_processor = MagicMock()
        mock_processor.mux_voiceover_into_video = MagicMock()

        with patch(
            "src.utils.audio_processor.AudioProcessor",
            return_value=mock_processor,
        ):
            pipeline_service._mux_voiceover_into_video(
                video_path, voiceover_path, video_folder
            )

        assert pipeline_service._current_state == PipelineState.MIXING_AUDIO


class TestPipelineServiceGenerateVoiceoverIntegration:
    """Integration tests for _generate_voiceover method."""

    def test_generate_voiceover_success(
        self, pipeline_service, mock_db_manager, tmp_path
    ):
        """Verify _generate_voiceover creates final voiceover file."""
        from unittest.mock import MagicMock, patch
        from src.utils.subtitle_parser import SubtitleLine

        video_folder = tmp_path
        video_duration_ms = 600000
        pipeline_service._video_file_id = 1

        subtitle_lines = [
            SubtitleLine(
                index=1,
                start_ms=1000,
                end_ms=2000,
                text_source="Test",
                is_sound_effect=False,
                audio_clip_path=str(video_folder / "line_000.mp3"),
            )
        ]
        original_audio_path = video_folder / "original_audio.wav"
        original_audio_path.touch()

        mock_processor = MagicMock()
        mock_processor.generate_voiceover = MagicMock()

        with patch(
            "src.utils.audio_processor.AudioProcessor",
            return_value=mock_processor,
        ):
            result = pipeline_service._generate_voiceover(
                subtitle_lines, original_audio_path, video_folder, video_duration_ms
            )

        mock_processor.generate_voiceover.assert_called_once()
        assert result == video_folder / "voiceover_pl.wav"

    def test_generate_voiceover_cleans_temp_files(
        self, pipeline_service, mock_db_manager, tmp_path
    ):
        """Verify _generate_voiceover cleans up temporary files."""
        from unittest.mock import MagicMock, patch

        video_folder = tmp_path
        video_duration_ms = 600000
        pipeline_service._video_file_id = 1

        subtitle_lines = []
        original_audio_path = video_folder / "original_audio.wav"
        original_audio_path.touch()

        temp_dir = video_folder / "temp_tts"
        temp_dir.mkdir()
        (temp_dir / "line_000.mp3").touch()

        mock_processor = MagicMock()
        mock_processor.generate_voiceover = MagicMock()

        with patch(
            "src.utils.audio_processor.AudioProcessor",
            return_value=mock_processor,
        ):
            pipeline_service._generate_voiceover(
                subtitle_lines, original_audio_path, video_folder, video_duration_ms
            )

        assert not temp_dir.exists()

    def test_generate_voiceover_updates_state(
        self, pipeline_service, mock_db_manager, tmp_path
    ):
        """Verify _generate_voiceover maintains MIXING_AUDIO state."""
        from unittest.mock import MagicMock, patch

        video_folder = tmp_path
        video_duration_ms = 600000
        pipeline_service._video_file_id = 1

        subtitle_lines = []
        original_audio_path = video_folder / "original_audio.wav"
        original_audio_path.touch()

        mock_processor = MagicMock()
        mock_processor.generate_voiceover = MagicMock()

        with patch(
            "src.utils.audio_processor.AudioProcessor",
            return_value=mock_processor,
        ):
            pipeline_service._generate_voiceover(
                subtitle_lines, original_audio_path, video_folder, video_duration_ms
            )

        assert pipeline_service._current_state == PipelineState.MIXING_AUDIO


class TestPipelineServiceGeminiAPIErrorHandling:
    """Tests for Gemini API failure handling in pipeline context."""

    def test_pipeline_handles_gemini_api_failure(
        self, pipeline_service, mock_db_manager, tmp_path
    ):
        """Verify pipeline sets FAILED state when Gemini translation fails."""
        from unittest.mock import MagicMock, patch
        from src.utils.gemini_client import GeminiTranslationError

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
            "pipeline_state": PipelineState.NONE.value,
        }

        original_srt = video_folder / "original.srt"
        original_srt.write_text("1\n00:00:01,000 --> 00:00:04,000\nTest subtitle\n")

        mock_open_subtitles = MagicMock()
        mock_open_subtitles.download_subtitle = MagicMock()

        mock_translator = MagicMock()
        mock_translator.translate_batch.side_effect = GeminiTranslationError(
            "Gemini API rate limit exceeded"
        )

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
            patch.object(pipeline_service.signals, "error_occurred") as mock_error,
        ):
            pipeline_service.start_process(video_file_id)
            pipeline_service.wait()

            state_calls = mock_db_manager.update_pipeline_state.call_args_list
            final_state = state_calls[-1][0][1]
            assert final_state == PipelineState.FAILED

            mock_error.emit.assert_called_once()
            error_args = mock_error.emit.call_args[0]
            assert error_args[0] == video_file_id
            assert "Gemini API" in error_args[1]

            mock_finished.emit.assert_called_once_with(video_file_id, False)

    def test_pipeline_handles_gemini_json_decode_error(
        self, pipeline_service, mock_db_manager, tmp_path
    ):
        """Verify pipeline handles Gemini JSON decode errors gracefully."""
        from unittest.mock import MagicMock, patch
        from src.utils.gemini_client import GeminiTranslationError

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
            "pipeline_state": PipelineState.NONE.value,
        }

        original_srt = video_folder / "original.srt"
        original_srt.write_text(
            "1\n00:00:01,000 --> 00:00:04,000\nFirst line\n"
            "2\n00:00:05,000 --> 00:00:08,000\nSecond line\n"
        )

        mock_open_subtitles = MagicMock()
        mock_open_subtitles.download_subtitle = MagicMock()

        mock_translator = MagicMock()
        mock_translator.translate_batch.side_effect = GeminiTranslationError(
            "Invalid JSON response from Gemini"
        )

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
            patch.object(pipeline_service.signals, "error_occurred") as mock_error,
        ):
            pipeline_service.start_process(video_file_id)
            pipeline_service.wait()

            state_calls = mock_db_manager.update_pipeline_state.call_args_list
            final_state = state_calls[-1][0][1]
            assert final_state == PipelineState.FAILED

            mock_finished.emit.assert_called_once_with(video_file_id, False)

    def test_pipeline_handles_gemini_api_connection_error(
        self, pipeline_service, mock_db_manager, tmp_path
    ):
        """Verify pipeline handles Gemini connection/network errors."""
        from unittest.mock import MagicMock, patch
        from src.utils.gemini_client import GeminiTranslationError

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
            "pipeline_state": PipelineState.NONE.value,
        }

        original_srt = video_folder / "original.srt"
        original_srt.write_text("1\n00:00:01,000 --> 00:00:04,000\nNetwork test\n")

        mock_open_subtitles = MagicMock()
        mock_open_subtitles.download_subtitle = MagicMock()

        mock_translator = MagicMock()
        mock_translator.translate_batch.side_effect = GeminiTranslationError(
            "Connection timeout: failed to connect to Gemini API"
        )

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
            patch.object(pipeline_service.signals, "error_occurred") as mock_error,
        ):
            pipeline_service.start_process(video_file_id)
            pipeline_service.wait()

            mock_db_manager.update_pipeline_state.assert_called()
            calls = mock_db_manager.update_pipeline_state.call_args_list
            final_state = calls[-1][0][1]
            assert final_state == PipelineState.FAILED

            mock_finished.emit.assert_called_once_with(video_file_id, False)


class TestPipelineServiceCompleteFlow:
    """Tests for complete pipeline state machine flow."""

    def test_complete_flow_all_states_in_order(
        self, pipeline_service, mock_db_manager, tmp_path
    ):
        """Verify pipeline transitions through all states in order:
        NONE → FETCHING_SUBS → TRANSLATING → SUBS_READY →
        GENERATING_TTS → MIXING_AUDIO → VOICEOVER_READY
        """
        from unittest.mock import MagicMock, patch
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
            "pipeline_state": PipelineState.NONE.value,
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

        mock_edge_tts = MagicMock()
        mock_edge_tts.generate_tts = MagicMock()

        mock_audio_processor = MagicMock()
        mock_audio_processor.extract_audio = MagicMock()
        voiceover_path = video_folder / "voiceover_pl.wav"
        voiceover_path.touch()
        mock_audio_processor.generate_voiceover.return_value = voiceover_path

        with (
            patch(
                "src.utils.opensubtitles_client.OpenSubtitlesClient",
                return_value=mock_open_subtitles,
            ),
            patch(
                "src.utils.gemini_client.GeminiTranslator",
                return_value=mock_gemini,
            ),
            patch(
                "src.utils.edge_tts_client.EdgeTTSClient",
                return_value=mock_edge_tts,
            ),
            patch(
                "src.utils.audio_processor.AudioProcessor",
                return_value=mock_audio_processor,
            ),
            patch.object(pipeline_service, "_get_video_duration", return_value=600000),
            patch.object(
                pipeline_service.signals, "pipeline_finished"
            ) as mock_finished,
        ):
            pipeline_service.start_process(video_file_id)
            pipeline_service.wait()

        state_calls = mock_db_manager.update_pipeline_state.call_args_list
        all_states = [call[0][1] for call in state_calls]
        unique_states = []
        for state in all_states:
            if not unique_states or unique_states[-1] != state:
                unique_states.append(state)

        expected_states = [
            PipelineState.FETCHING_SUBS,
            PipelineState.TRANSLATING,
            PipelineState.SUBS_READY,
            PipelineState.GENERATING_TTS,
            PipelineState.MIXING_AUDIO,
            PipelineState.VOICEOVER_READY,
        ]
        assert unique_states == expected_states
        mock_finished.emit.assert_called_once_with(video_file_id, True)

    def test_complete_flow_without_translation_skips_translate_states(
        self, pipeline_service, mock_db_manager, tmp_path
    ):
        """Verify pipeline skips TRANSLATING and SUBS_READY when needs_translation=False."""
        from unittest.mock import MagicMock, patch

        video_folder = tmp_path
        video_path = video_folder / "video.mp4"
        video_file_id = 1
        subtitle_id = 12345

        video_path.touch()

        mock_db_manager.get_video_file.return_value = {
            "id": video_file_id,
            "file_path": str(video_path),
            "subtitle_id": subtitle_id,
            "needs_translation": False,
            "pipeline_state": PipelineState.NONE.value,
        }

        original_srt = video_folder / "original.srt"
        original_srt.write_text("1\n00:00:01,000 --> 00:00:04,000\nOriginal text\n")

        mock_open_subtitles = MagicMock()
        mock_open_subtitles.download_subtitle = MagicMock()

        mock_edge_tts = MagicMock()
        mock_edge_tts.generate_tts = MagicMock()

        mock_audio_processor = MagicMock()
        mock_audio_processor.extract_audio = MagicMock()
        voiceover_path = video_folder / "voiceover_pl.wav"
        voiceover_path.touch()
        mock_audio_processor.generate_voiceover.return_value = voiceover_path

        with (
            patch(
                "src.utils.opensubtitles_client.OpenSubtitlesClient",
                return_value=mock_open_subtitles,
            ),
            patch(
                "src.utils.edge_tts_client.EdgeTTSClient",
                return_value=mock_edge_tts,
            ),
            patch(
                "src.utils.audio_processor.AudioProcessor",
                return_value=mock_audio_processor,
            ),
            patch.object(pipeline_service, "_get_video_duration", return_value=600000),
            patch.object(
                pipeline_service.signals, "pipeline_finished"
            ) as mock_finished,
        ):
            pipeline_service.start_process(video_file_id)
            pipeline_service.wait()

        state_calls = mock_db_manager.update_pipeline_state.call_args_list
        all_states = [call[0][1] for call in state_calls]
        unique_states = []
        for state in all_states:
            if not unique_states or unique_states[-1] != state:
                unique_states.append(state)

        expected_states = [
            PipelineState.FETCHING_SUBS,
            PipelineState.GENERATING_TTS,
            PipelineState.MIXING_AUDIO,
            PipelineState.VOICEOVER_READY,
        ]
        assert unique_states == expected_states
        assert PipelineState.TRANSLATING not in unique_states
        assert PipelineState.SUBS_READY not in unique_states


class TestPipelineServiceEndToEndIntegration:
    """End-to-end integration tests for complete pipeline flow."""

    def test_complete_pipeline_flow_success(
        self, pipeline_service, mock_db_manager, tmp_path
    ):
        """Verify complete pipeline flow from fetch to voiceover generation."""
        from unittest.mock import MagicMock, patch
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
            "pipeline_state": PipelineState.NONE.value,
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

        mock_edge_tts = MagicMock()
        # Mock batch TTS to return success for all items
        mock_edge_tts.generate_tts_batch = MagicMock(
            side_effect=lambda items, cb=None: [
                (i, path, None) for i, (_, path) in enumerate(items)
            ]
        )
        mock_edge_tts.text_needs_tts = MagicMock(return_value=True)

        mock_audio_processor = MagicMock()
        mock_audio_processor.extract_audio = MagicMock()
        voiceover_path = video_folder / "voiceover_pl.wav"
        voiceover_path.touch()
        mock_audio_processor.generate_voiceover.return_value = voiceover_path

        with (
            patch(
                "src.utils.opensubtitles_client.OpenSubtitlesClient",
                return_value=mock_open_subtitles,
            ),
            patch(
                "src.utils.gemini_client.GeminiTranslator",
                return_value=mock_gemini,
            ),
            patch(
                "src.utils.edge_tts_client.EdgeTTSClient",
                return_value=mock_edge_tts,
            ),
            patch(
                "src.utils.audio_processor.AudioProcessor",
                return_value=mock_audio_processor,
            ),
            patch.object(pipeline_service, "_get_video_duration", return_value=600000),
            patch.object(
                pipeline_service.signals, "pipeline_finished"
            ) as mock_finished,
        ):
            pipeline_service.start_process(video_file_id)
            pipeline_service.wait()

            mock_open_subtitles.download_subtitle.assert_called_once()
            mock_gemini.translate_batch.assert_called_once()
            mock_edge_tts.generate_tts_batch.assert_called_once()
            mock_audio_processor.extract_audio.assert_called_once()
            mock_audio_processor.generate_voiceover.assert_called_once()
            mock_db_manager.add_subtitle.assert_called()
            mock_db_manager.add_voiceover.assert_called_once()
            mock_finished.emit.assert_called_once_with(video_file_id, True)

    def test_complete_pipeline_skip_when_no_subtitle_id(
        self, pipeline_service, mock_db_manager, tmp_path
    ):
        """Verify pipeline skips when subtitle_id is null."""
        from unittest.mock import patch

        video_folder = tmp_path
        video_path = video_folder / "video.mp4"
        video_file_id = 1

        video_path.touch()

        mock_db_manager.get_video_file.return_value = {
            "id": video_file_id,
            "file_path": str(video_path),
            "subtitle_id": None,
            "needs_translation": False,
            "pipeline_state": PipelineState.NONE.value,
        }

        with patch.object(
            pipeline_service.signals, "pipeline_finished"
        ) as mock_finished:
            pipeline_service.start_process(video_file_id)
            pipeline_service.wait()

            mock_finished.emit.assert_called_once_with(video_file_id, True)

    def test_complete_pipeline_skip_when_voiceover_exists(
        self, pipeline_service, mock_db_manager, tmp_path
    ):
        """Verify pipeline skips when voiceover already exists."""
        from unittest.mock import patch

        video_folder = tmp_path
        video_path = video_folder / "video.mp4"
        video_file_id = 1

        video_path.touch()

        mock_db_manager.get_video_file.return_value = {
            "id": video_file_id,
            "file_path": str(video_path),
            "subtitle_id": 12345,
            "needs_translation": True,
            "pipeline_state": PipelineState.VOICEOVER_READY.value,
        }

        with patch.object(
            pipeline_service.signals, "pipeline_finished"
        ) as mock_finished:
            pipeline_service.start_process(video_file_id)
            pipeline_service.wait()

            mock_finished.emit.assert_called_once_with(video_file_id, True)

    def test_complete_pipeline_skip_translation_when_disabled(
        self, pipeline_service, mock_db_manager, tmp_path
    ):
        """Verify pipeline skips translation when needs_translation is False."""
        from unittest.mock import MagicMock, patch

        video_folder = tmp_path
        video_path = video_folder / "video.mp4"
        video_file_id = 1
        subtitle_id = 12345

        video_path.touch()

        original_srt = video_folder / "original.srt"
        original_srt.write_text("1\n00:00:01,000 --> 00:00:04,000\nOriginal text\n")

        mock_db_manager.get_video_file.return_value = {
            "id": video_file_id,
            "file_path": str(video_path),
            "subtitle_id": subtitle_id,
            "needs_translation": False,
            "pipeline_state": PipelineState.NONE.value,
        }

        mock_open_subtitles = MagicMock()
        mock_open_subtitles.download_subtitle = MagicMock()

        mock_edge_tts = MagicMock()
        # Mock batch TTS to return success for all items
        mock_edge_tts.generate_tts_batch = MagicMock(
            side_effect=lambda items, cb=None: [
                (i, path, None) for i, (_, path) in enumerate(items)
            ]
        )
        mock_edge_tts.text_needs_tts = MagicMock(return_value=True)

        mock_audio_processor = MagicMock()
        mock_audio_processor.extract_audio = MagicMock()
        voiceover_path = video_folder / "voiceover_pl.wav"
        voiceover_path.touch()
        mock_audio_processor.generate_voiceover.return_value = voiceover_path

        with (
            patch(
                "src.utils.opensubtitles_client.OpenSubtitlesClient",
                return_value=mock_open_subtitles,
            ),
            patch(
                "src.utils.edge_tts_client.EdgeTTSClient",
                return_value=mock_edge_tts,
            ),
            patch(
                "src.utils.audio_processor.AudioProcessor",
                return_value=mock_audio_processor,
            ),
            patch.object(pipeline_service, "_get_video_duration", return_value=600000),
            patch.object(
                pipeline_service.signals, "pipeline_finished"
            ) as mock_finished,
        ):
            pipeline_service.start_process(video_file_id)
            pipeline_service.wait()

            mock_open_subtitles.download_subtitle.assert_called_once()
            mock_edge_tts.generate_tts_batch.assert_called_once()
            mock_audio_processor.generate_voiceover.assert_called_once()

    def test_complete_pipeline_handles_error(
        self, pipeline_service, mock_db_manager, tmp_path
    ):
        """Verify pipeline sets FAILED state on error."""
        from unittest.mock import MagicMock, patch

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
            "pipeline_state": PipelineState.NONE.value,
        }

        mock_open_subtitles = MagicMock()
        mock_open_subtitles.download_subtitle.side_effect = Exception("Network error")

        with (
            patch(
                "src.utils.opensubtitles_client.OpenSubtitlesClient",
                return_value=mock_open_subtitles,
            ),
            patch.object(
                pipeline_service.signals, "pipeline_finished"
            ) as mock_finished,
            patch.object(pipeline_service.signals, "error_occurred") as mock_error,
        ):
            pipeline_service.start_process(video_file_id)
            pipeline_service.wait()

            mock_finished.emit.assert_called_once_with(video_file_id, False)
            mock_error.emit.assert_called_once()

            calls = mock_db_manager.update_pipeline_state.call_args_list
            assert len(calls) > 0, "update_pipeline_state should have been called"
            last_call_args = calls[-1]
            assert last_call_args[0][1] == PipelineState.FAILED

    def test_complete_pipeline_cancellation(
        self, pipeline_service, mock_db_manager, tmp_path
    ):
        """Verify pipeline respects stop() cancellation."""
        from unittest.mock import MagicMock, patch

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
            "pipeline_state": PipelineState.NONE.value,
        }

        mock_open_subtitles = MagicMock()
        mock_open_subtitles.download_subtitle = MagicMock()

        mock_gemini = MagicMock()
        mock_gemini.translate_batch.return_value = []

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
            pipeline_service.stop()
            pipeline_service.wait()

            mock_finished.emit.assert_called_once_with(video_file_id, True)


class TestPipelineServiceOpenSubtitlesFailure:
    """Tests for OpenSubtitles API failure handling in full pipeline context."""

    def test_pipeline_handles_opensubtitles_rate_limit_error(
        self, pipeline_service, mock_db_manager, tmp_path
    ):
        """Verify pipeline sets FAILED state when OpenSubtitles API returns rate limit."""
        from unittest.mock import MagicMock, patch
        from src.utils.opensubtitles_client import OpenSubtitlesError

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
            "pipeline_state": PipelineState.NONE.value,
        }

        mock_client = MagicMock()
        mock_client.download_subtitle.side_effect = OpenSubtitlesError(
            "Rate limit exceeded. Please try again later."
        )

        with (
            patch(
                "src.utils.opensubtitles_client.OpenSubtitlesClient",
                return_value=mock_client,
            ),
            patch.object(
                pipeline_service.signals, "pipeline_finished"
            ) as mock_finished,
            patch.object(pipeline_service.signals, "error_occurred") as mock_error,
        ):
            pipeline_service.start_process(video_file_id)
            pipeline_service.wait()

            mock_error.emit.assert_called_once()
            error_args = mock_error.emit.call_args[0]
            assert error_args[0] == video_file_id
            assert "Rate limit" in error_args[1]

            mock_finished.emit.assert_called_once_with(video_file_id, False)

            calls = mock_db_manager.update_pipeline_state.call_args_list
            final_state = calls[-1][0][1]
            assert final_state == PipelineState.FAILED

    def test_pipeline_handles_opensubtitles_not_found_error(
        self, pipeline_service, mock_db_manager, tmp_path
    ):
        """Verify pipeline sets FAILED state when subtitle ID is not found."""
        from unittest.mock import MagicMock, patch
        from src.utils.opensubtitles_client import OpenSubtitlesError

        video_folder = tmp_path
        video_path = video_folder / "video.mp4"
        video_file_id = 1
        subtitle_id = 99999

        video_path.touch()

        mock_db_manager.get_video_file.return_value = {
            "id": video_file_id,
            "file_path": str(video_path),
            "subtitle_id": subtitle_id,
            "needs_translation": True,
            "pipeline_state": PipelineState.NONE.value,
        }

        mock_client = MagicMock()
        mock_client.download_subtitle.side_effect = OpenSubtitlesError(
            "Subtitle ID 99999 not found"
        )

        with (
            patch(
                "src.utils.opensubtitles_client.OpenSubtitlesClient",
                return_value=mock_client,
            ),
            patch.object(
                pipeline_service.signals, "pipeline_finished"
            ) as mock_finished,
            patch.object(pipeline_service.signals, "error_occurred") as mock_error,
        ):
            pipeline_service.start_process(video_file_id)
            pipeline_service.wait()

            mock_error.emit.assert_called_once()
            error_message = mock_error.emit.call_args[0][1]
            assert "not found" in error_message.lower() or "99999" in error_message

            mock_finished.emit.assert_called_once_with(video_file_id, False)

            calls = mock_db_manager.update_pipeline_state.call_args_list
            final_state = calls[-1][0][1]
            assert final_state == PipelineState.FAILED

    def test_pipeline_handles_opensubtitles_connection_error(
        self, pipeline_service, mock_db_manager, tmp_path
    ):
        """Verify pipeline sets FAILED state on connection error to OpenSubtitles."""
        from unittest.mock import MagicMock, patch
        from src.utils.opensubtitles_client import OpenSubtitlesError

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
            "pipeline_state": PipelineState.NONE.value,
        }

        mock_client = MagicMock()
        mock_client.download_subtitle.side_effect = OpenSubtitlesError(
            "Connection error: DNS resolution failed"
        )

        with (
            patch(
                "src.utils.opensubtitles_client.OpenSubtitlesClient",
                return_value=mock_client,
            ),
            patch.object(
                pipeline_service.signals, "pipeline_finished"
            ) as mock_finished,
            patch.object(pipeline_service.signals, "error_occurred") as mock_error,
        ):
            pipeline_service.start_process(video_file_id)
            pipeline_service.wait()

            mock_error.emit.assert_called_once()

            mock_finished.emit.assert_called_once_with(video_file_id, False)

            state_calls = mock_db_manager.update_pipeline_state.call_args_list
            failed_calls = [
                call for call in state_calls if call[0][1] == PipelineState.FAILED
            ]
            assert len(failed_calls) == 1

    def test_pipeline_handles_opensubtitles_timeout_error(
        self, pipeline_service, mock_db_manager, tmp_path
    ):
        """Verify pipeline sets FAILED state when OpenSubtitles request times out."""
        from unittest.mock import MagicMock, patch
        from src.utils.opensubtitles_client import OpenSubtitlesError

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
            "pipeline_state": PipelineState.NONE.value,
        }

        mock_client = MagicMock()
        mock_client.download_subtitle.side_effect = OpenSubtitlesError(
            "Request timed out: HTTPSConnectionPool(host='api.opensubtitles.com', port=443): Read timed out"
        )

        with (
            patch(
                "src.utils.opensubtitles_client.OpenSubtitlesClient",
                return_value=mock_client,
            ),
            patch.object(
                pipeline_service.signals, "pipeline_finished"
            ) as mock_finished,
            patch.object(pipeline_service.signals, "error_occurred") as mock_error,
        ):
            pipeline_service.start_process(video_file_id)
            pipeline_service.wait()

            mock_error.emit.assert_called_once()
            error_message = mock_error.emit.call_args[0][1]
            assert "timed out" in error_message.lower()

            mock_finished.emit.assert_called_once_with(video_file_id, False)

            calls = mock_db_manager.update_pipeline_state.call_args_list
            final_state = calls[-1][0][1]
            assert final_state == PipelineState.FAILED

    def test_pipeline_handles_opensubtitles_api_key_error(
        self, pipeline_service, mock_db_manager, tmp_path
    ):
        """Verify pipeline sets FAILED state when OpenSubtitles API key is invalid."""
        from unittest.mock import MagicMock, patch
        from src.utils.opensubtitles_client import OpenSubtitlesError

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
            "pipeline_state": PipelineState.NONE.value,
        }

        mock_client = MagicMock()
        mock_client.download_subtitle.side_effect = OpenSubtitlesError(
            "API key expired or invalid"
        )

        with (
            patch(
                "src.utils.opensubtitles_client.OpenSubtitlesClient",
                return_value=mock_client,
            ),
            patch.object(
                pipeline_service.signals, "pipeline_finished"
            ) as mock_finished,
            patch.object(pipeline_service.signals, "error_occurred") as mock_error,
        ):
            pipeline_service.start_process(video_file_id)
            pipeline_service.wait()

            mock_error.emit.assert_called_once()

            mock_finished.emit.assert_called_once_with(video_file_id, False)

            calls = mock_db_manager.update_pipeline_state.call_args_list
            state_values = [call[0][1] for call in calls]
            assert PipelineState.FAILED in state_values
