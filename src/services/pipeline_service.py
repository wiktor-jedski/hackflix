"""PipelineService for AI-powered subtitle translation and voiceover generation.

This service orchestrates the transformation of raw video into localized content
with full lector mode (ducked original audio + TTS overlay).

Architecture:
    - Runs in a QThread to keep UI responsive
    - Uses signals to communicate progress and completion
    - Divides processing into 10-minute chunks for Pi 5 memory optimization
    - Supports resumable translation with batch progress tracking

Pipeline Stages:
    1. FETCH_SUBS: Download subtitles from OpenSubtitles API
    2. TRANSLATE: Batch translate with Gemini API (resumable)
    3. SUBS_READY: Subtitles available for direct playback
    4. GENERATING_TTS: Create audio clips with edge-tts
    5. MIXING_AUDIO: FFmpeg merge audio tracks
    6. VOICEOVER_READY: Final voiceover available
"""

import logging
from pathlib import Path
from typing import Optional

from PyQt5.QtCore import QObject, QThread, pyqtSignal, pyqtSlot

from src.config import PipelineState, VOICEOVER_LANGUAGE

logger = logging.getLogger(__name__)


class PipelineSignals(QObject):
    """Signals for PipelineService communication."""

    pipeline_update = pyqtSignal(int, PipelineState, str)
    pipeline_finished = pyqtSignal(int, bool)
    error_occurred = pyqtSignal(int, str)


class PipelineService(QThread):
    """QThread worker for subtitle translation and voiceover generation.

    Attributes:
        signals: Signal emitters for progress and completion events.
        db_manager: Database manager for persistence operations.
        _video_file_id: ID of the video file being processed.
        _should_stop: Flag for cancellation support.
        _current_state: Current pipeline state for tracking.

    Signals:
        pipeline_update: Emitted with (file_id, state, message) on stage changes.
        pipeline_finished: Emitted with (file_id, success) when processing ends.
    """

    def __init__(self, db_manager) -> None:
        """Initialize the PipelineService.

        Args:
            db_manager: DatabaseManager instance for persistence operations.
        """
        super().__init__()
        self.signals = PipelineSignals()
        self.db_manager = db_manager
        self._video_file_id: Optional[int] = None
        self._should_stop = False
        self._current_state = PipelineState.NONE

        logger.info("PipelineService initialized")

    def is_busy(self) -> bool:
        """Check if the pipeline is currently processing.

        Returns:
            True if pipeline is running, False otherwise.
        """
        return self.isRunning()

    @pyqtSlot(int)
    def start_process(self, video_file_id: int) -> None:
        """Entry point to start pipeline processing for a video file.

        Args:
            video_file_id: Database ID of the video file to process.
        """
        self._video_file_id = video_file_id
        self._should_stop = False
        self.start()

    def stop(self) -> None:
        """Request the pipeline to stop processing.

        Sets a flag that is checked between stages to allow graceful cancellation.
        """
        self._should_stop = True
        logger.info("Pipeline stop requested for video_file_id=%d", self._video_file_id)

    def run(self) -> None:
        """Execute the main pipeline orchestration.

        This is the QRunnable entry point called when the thread starts.
        It orchestrates the complete flow from subtitle fetch to voiceover generation.

        Flow:
            1. Retrieve video file details from DB
            2. Check skip conditions (no subtitle_id, voiceover exists)
            3. Fetch subtitles (OpenSubtitles API)
            4. Translate if needed (Gemini API, resumable)
            5. Generate TTS clips (Edge-TTS)
            6. Extract original audio (FFmpeg)
            7. Mix voiceover (dynamic ducking + overlay)
            8. Persist results to DB
        """
        if self._video_file_id is None:
            logger.error("Pipeline run called without video_file_id")
            return

        try:
            video_file = self.db_manager.get_video_file(self._video_file_id)
            if video_file is None:
                logger.error("Video file not found: id=%d", self._video_file_id)
                self.signals.pipeline_finished.emit(self._video_file_id, False)
                return

            video_path = Path(video_file["file_path"])
            video_folder = video_path.parent
            subtitle_id = video_file.get("subtitle_id")
            needs_translation = video_file.get("needs_translation", False)

            if self._should_stop:
                self._emit_update(PipelineState.NONE, "Cancelled")
                self.signals.pipeline_finished.emit(self._video_file_id, True)
                return

            if subtitle_id is None:
                logger.info(
                    "No subtitle_id for video_file_id=%d, skipping pipeline",
                    self._video_file_id,
                )
                self.signals.pipeline_finished.emit(self._video_file_id, True)
                return

            if video_file.get("pipeline_state") == PipelineState.VOICEOVER_READY.value:
                logger.info(
                    "Voiceover already exists for video_file_id=%d, skipping",
                    self._video_file_id,
                )
                self.signals.pipeline_finished.emit(self._video_file_id, True)
                return

            self._fetch_subtitles(subtitle_id, video_folder)

            if self._should_stop:
                self._emit_update(PipelineState.NONE, "Cancelled")
                self.signals.pipeline_finished.emit(self._video_file_id, True)
                return

            if needs_translation:
                self._translate_subtitles(video_folder, self._video_file_id)

            if self._should_stop:
                self._emit_update(PipelineState.NONE, "Cancelled")
                self.signals.pipeline_finished.emit(self._video_file_id, True)
                return

            subtitle_lines = self._parse_subtitles(video_folder)
            self._generate_tts_clips(subtitle_lines, video_folder)

            if self._should_stop:
                self._emit_update(PipelineState.NONE, "Cancelled")
                self.signals.pipeline_finished.emit(self._video_file_id, True)
                return

            original_audio_path = self._extract_original_audio(video_path, video_folder)

            if self._should_stop:
                self._emit_update(PipelineState.NONE, "Cancelled")
                self.signals.pipeline_finished.emit(self._video_file_id, True)
                return

            video_duration_ms = self._get_video_duration(video_path)
            voiceover_path = self._generate_voiceover(
                subtitle_lines, original_audio_path, video_folder, video_duration_ms
            )

            if voiceover_path and voiceover_path.exists():
                # Mux voiceover into video for proper seek support
                muxed_video_path = self._mux_voiceover_into_video(
                    video_path, voiceover_path, video_folder
                )

                self.db_manager.add_voiceover(
                    self._video_file_id,
                    VOICEOVER_LANGUAGE,
                    str(voiceover_path),
                    str(muxed_video_path) if muxed_video_path else None,
                )
                self._update_pipeline_state(PipelineState.VOICEOVER_READY)
                logger.info(
                    "Pipeline completed successfully for video_file_id=%d",
                    self._video_file_id,
                )
                self.signals.pipeline_finished.emit(self._video_file_id, True)
            else:
                raise RuntimeError("Voiceover generation failed")

        except Exception as e:
            logger.exception(
                "Pipeline failed for video_file_id=%d: %s", self._video_file_id, e
            )
            self._update_pipeline_state(PipelineState.FAILED)
            self.signals.error_occurred.emit(self._video_file_id, str(e))
            self.signals.pipeline_finished.emit(self._video_file_id, False)

    def _emit_update(self, state: PipelineState, message: str) -> None:
        """Emit a pipeline update signal.

        Args:
            state: Current pipeline state.
            message: Human-readable status message.
        """
        self._current_state = state
        self.db_manager.update_pipeline_state(self._video_file_id, state)
        self.signals.pipeline_update.emit(self._video_file_id, state, message)
        logger.info(
            "Pipeline update: video_file_id=%d, state=%s, message=%s",
            self._video_file_id,
            state.value,
            message,
        )

    def _update_pipeline_state(self, state: PipelineState) -> None:
        """Update pipeline state in database.

        Args:
            state: New pipeline state to set.
        """
        self._current_state = state
        self.db_manager.update_pipeline_state(self._video_file_id, state)

    def _fetch_subtitles(self, subtitle_id: int, video_folder: Path) -> Path:
        """Fetch subtitles from OpenSubtitles API.

        Args:
            subtitle_id: OpenSubtitles ID to download.
            video_folder: Destination folder for subtitle files.

        Returns:
            Path to the downloaded original.srt file.
        """
        self._emit_update(PipelineState.FETCHING_SUBS, "Downloading subtitles...")

        from src.utils.opensubtitles_client import OpenSubtitlesClient

        client = OpenSubtitlesClient()
        output_path = video_folder / "original.srt"
        client.download_subtitle(subtitle_id, output_path)

        self.db_manager.add_subtitle(
            self._video_file_id, str(output_path), "original", subtitle_id
        )

        logger.info("Subtitles downloaded to %s", output_path)
        return output_path

    def _translate_subtitles(self, video_folder: Path, video_file_id: int) -> list:
        """Translate subtitles using Gemini API with resumable batching.

        Args:
            video_folder: Folder containing subtitle files.
            video_file_id: Database ID for progress tracking.

        Returns:
            List of translated SubtitleLine objects.
        """
        self._emit_update(PipelineState.TRANSLATING, "Translating subtitles...")

        from src.utils.subtitle_parser import parse_srt_file
        from src.utils.gemini_client import GeminiTranslator

        original_srt = video_folder / "original.srt"
        translated_srt = video_folder / "pl.srt"

        subtitle_lines = parse_srt_file(original_srt)

        progress = self.db_manager.get_translation_progress(video_file_id)
        start_batch = progress["completed_batches"] if progress else 0

        translator = GeminiTranslator()
        translated_lines = translator.translate_batch(
            subtitle_lines, start_batch, video_file_id
        )

        from src.utils.subtitle_parser import write_srt_file

        write_srt_file(translated_srt, translated_lines)

        self.db_manager.add_subtitle(video_file_id, str(translated_srt), "polish", None)
        self.db_manager.clear_translation_progress(video_file_id)

        self._emit_update(PipelineState.SUBS_READY, "Translation complete")

        logger.info("Translation completed for video_file_id=%d", video_file_id)
        return translated_lines

    def _parse_subtitles(self, video_folder: Path) -> list:
        """Parse subtitle file for TTS generation.

        Args:
            video_folder: Folder containing subtitle files.

        Returns:
            List of SubtitleLine objects ready for TTS.
        """
        from src.utils.subtitle_parser import parse_srt_file, merge_close_subtitles

        translated_srt = video_folder / "pl.srt"
        if translated_srt.exists():
            subtitles = parse_srt_file(translated_srt)
        else:
            subtitles = parse_srt_file(video_folder / "original.srt")

        return merge_close_subtitles(subtitles)

    def _generate_tts_clips(self, subtitle_lines: list, video_folder: Path) -> list:
        """Generate TTS audio clips for subtitle lines in parallel.

        Args:
            subtitle_lines: List of SubtitleLine objects.
            video_folder: Output folder for audio clips.

        Returns:
            List of SubtitleLine objects with audio_path set.
        """
        self._emit_update(PipelineState.GENERATING_TTS, "Generating voice clips...")

        from src.utils.edge_tts_client import EdgeTTSClient

        client = EdgeTTSClient()
        temp_dir = video_folder / "temp_tts"
        temp_dir.mkdir(exist_ok=True)

        # Collect items that need TTS generation
        tts_items: list[tuple[int, str, Path]] = []  # (line_index, text, output_path)

        for i, line in enumerate(subtitle_lines):
            if self._should_stop:
                return []

            line_text = (
                line.text_translated if line.text_translated else line.text_source
            )
            if line.is_sound_effect or not client.text_needs_tts(line_text):
                continue

            audio_path = temp_dir / f"line_{i:03d}.mp3"
            tts_items.append((i, line_text, audio_path))

        if not tts_items:
            logger.info("No TTS items to generate")
            return subtitle_lines

        # Progress callback to update UI
        def on_progress(completed: int, total: int) -> None:
            if self._should_stop:
                return
            progress = int((completed / total) * 100)
            self._emit_update(
                PipelineState.GENERATING_TTS, f"Generating voice clips... {progress}%"
            )

        # Generate all TTS clips in parallel
        batch_items = [(text, path) for _, text, path in tts_items]
        results = client.generate_tts_batch(batch_items, on_progress)

        # Map results back to subtitle lines
        index_to_line_idx = {i: line_idx for i, (line_idx, _, _) in enumerate(tts_items)}

        for batch_idx, output_path, error in results:
            line_idx = index_to_line_idx[batch_idx]
            if output_path and not error:
                subtitle_lines[line_idx].audio_clip_path = str(output_path)
            else:
                logger.warning("TTS failed for line %d: %s", line_idx, error)

        successful = sum(1 for _, path, _ in results if path is not None)
        logger.info(
            "TTS generation complete: %d/%d successful", successful, len(tts_items)
        )
        return subtitle_lines

    def _extract_original_audio(self, video_path: Path, video_folder: Path) -> Path:
        """Extract original audio track from video using FFmpeg.

        Args:
            video_path: Path to the video file.
            video_folder: Output folder for audio files.

        Returns:
            Path to the extracted WAV file.
        """
        from src.utils.audio_processor import AudioProcessor

        self._emit_update(PipelineState.MIXING_AUDIO, "Extracting audio track...")

        output_path = video_folder / "original_audio.wav"
        processor = AudioProcessor()
        processor.extract_audio(video_path, output_path)

        logger.info("Original audio extracted to %s", output_path)
        return output_path

    def _get_video_duration(self, video_path: Path) -> int:
        """Get video duration in milliseconds.

        Args:
            video_path: Path to video file.

        Returns:
            Duration in milliseconds.
        """
        import subprocess

        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(video_path),
            ],
            capture_output=True,
            text=True,
        )
        return int(float(result.stdout.strip()) * 1000)

    def _generate_voiceover(
        self,
        subtitle_lines: list,
        original_audio_path: Path,
        video_folder: Path,
        video_duration_ms: int,
    ) -> Path:
        """Generate final voiceover with full lector mode.

        Args:
            subtitle_lines: List of SubtitleLine objects with audio paths.
            original_audio_path: Path to extracted original audio.
            video_folder: Working folder for intermediate files.
            video_duration_ms: Total video duration.

        Returns:
            Path to final voiceover WAV file.
        """
        from src.utils.audio_processor import AudioProcessor

        self._emit_update(PipelineState.MIXING_AUDIO, "Mixing voiceover...")

        processor = AudioProcessor()
        voiceover_path = video_folder / "voiceover_pl.wav"

        processor.generate_voiceover(
            subtitle_lines, original_audio_path, voiceover_path, video_duration_ms
        )

        self._cleanup_temp_files(video_folder)

        logger.info("Voiceover generated at %s", voiceover_path)
        return voiceover_path

    def _mux_voiceover_into_video(
        self,
        video_path: Path,
        voiceover_path: Path,
        video_folder: Path,
    ) -> Optional[Path]:
        """Mux voiceover into video file as an additional audio track.

        This creates a new video file with the voiceover embedded, which
        fixes seeking issues that occur with VLC's input-slave option.

        Args:
            video_path: Path to the original video file.
            voiceover_path: Path to the voiceover WAV file.
            video_folder: Working folder for output.

        Returns:
            Path to the muxed video file, or None if muxing fails.
        """
        from src.utils.audio_processor import AudioProcessor, AudioProcessingError

        self._emit_update(PipelineState.MIXING_AUDIO, "Embedding voiceover track...")

        # Generate output filename: original_name_voiceover.mkv
        original_stem = video_path.stem
        muxed_video_path = video_folder / f"{original_stem}_voiceover.mkv"

        try:
            processor = AudioProcessor()
            processor.mux_voiceover_into_video(
                video_path, voiceover_path, muxed_video_path
            )
            logger.info("Muxed video created at %s", muxed_video_path)
            return muxed_video_path
        except AudioProcessingError as e:
            logger.error("Failed to mux voiceover into video: %s", e)
            # Return None to fall back to input-slave approach
            return None

    def _cleanup_temp_files(self, video_folder: Path) -> None:
        """Clean up temporary TTS and chunk files.

        Args:
            video_folder: Folder containing temp files.
        """
        import shutil

        temp_dir = video_folder / "temp_tts"
        if temp_dir.exists():
            shutil.rmtree(temp_dir)

        for chunk_file in video_folder.glob("chunk_*.wav"):
            chunk_file.unlink()

        logger.info("Temporary files cleaned up")
