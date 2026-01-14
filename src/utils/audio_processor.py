"""Audio processing utility for voiceover generation.

Provides functionality for audio extraction, ducking, time-stretching,
and mixing for the PipelineService.
"""

import logging
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


class AudioProcessingError(Exception):
    """Raised when audio processing fails."""

    pass


class AudioProcessor:
    """Handles audio manipulation for voiceover generation."""

    FADE_DOWN_MS = 100
    FADE_UP_MS = 500
    CHUNK_DURATION_MS = 10 * 60 * 1000  # 10 minutes
    MAX_DRIFT_MS = 5000  # 5 seconds

    def extract_audio(self, video_path: Path, output_path: Path) -> None:
        """Extract audio track from video file using FFmpeg.

        Args:
            video_path: Path to the video file.
            output_path: Path for the output WAV file.

        Raises:
            AudioProcessingError: If FFmpeg fails or video has no audio track.
        """
        cmd = [
            "ffmpeg",
            "-i",
            str(video_path),
            "-vn",
            "-acodec",
            "pcm_s16le",
            "-ar",
            "16000",
            "-ac",
            "1",
            str(output_path),
            "-y",
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            if "Stream map '0:a' matches no streams" in result.stderr:
                raise AudioProcessingError("Video has no audio track")
            raise AudioProcessingError(
                f"FFmpeg audio extraction failed: {result.stderr}"
            )

        logger.info("Extracted audio from %s to %s", video_path, output_path)

    def apply_ducking(
        self,
        audio_path: Path,
        duck_intervals: list[tuple[int, int, int]],
        output_path: Path,
    ) -> None:
        """Apply dynamic ducking to audio based on subtitle timestamps.

        Args:
            audio_path: Path to input audio file.
            duck_intervals: List of (start_ms, end_ms, fade_down_ms) tuples.
            output_path: Path for output audio file.
        """
        from pydub import AudioSegment

        audio = AudioSegment.from_wav(str(audio_path))

        for start_ms, end_ms, fade_ms in duck_intervals:
            start_ms = max(0, start_ms)
            end_ms = min(len(audio), end_ms)

            fade_down = min(fade_ms, (end_ms - start_ms) // 2)
            fade_up = min(self.FADE_UP_MS, (end_ms - start_ms) - fade_down)

            before = audio[:start_ms]
            during = audio[start_ms:end_ms]
            after = audio[end_ms:]

            ducked = during - 6
            if fade_down > 0:
                ducked = ducked.fade_out(fade_down)
            if fade_up > 0:
                ducked = ducked.fade_in(fade_up)

            audio = before + ducked + after

        audio.export(str(output_path), format="wav")
        logger.info("Applied ducking to %d intervals", len(duck_intervals))

    def stretch_audio(
        self,
        audio_path: Path,
        speedup_factor: float,
        output_path: Path,
    ) -> None:
        """Time-stretch audio to fit within time constraints.

        Args:
            audio_path: Path to input audio.
            speedup_factor: Speed multiplier (1.0 = no change, >1.0 = faster).
            output_path: Path for output audio.

        Raises:
            AudioProcessingError: If speedup_factor is out of valid range.
        """
        if speedup_factor < 1.0 or speedup_factor > 1.3:
            raise AudioProcessingError(
                f"Invalid speedup factor: {speedup_factor}. Must be 1.0-1.3"
            )

        if speedup_factor == 1.0:
            shutil.copy(str(audio_path), str(output_path))
            logger.info("No stretching needed, copied audio to %s", output_path)
            return

        cmd = [
            "ffmpeg",
            "-i",
            str(audio_path),
            "-filter:a",
            f"atempo={speedup_factor}",
            str(output_path),
            "-y",
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.returncode != 0:
            raise AudioProcessingError(
                f"FFmpeg time-stretching failed: {result.stderr}"
            )

        logger.info("Stretched audio by factor %.2f to %s", speedup_factor, output_path)

    def mix_audio_tracks(
        self,
        track1_path: Path,
        track2_path: Path,
        output_path: Path,
    ) -> None:
        """Overlay TTS track onto original audio track.

        Args:
            track1_path: Path to original audio (will be ducked).
            track2_path: Path to TTS voiceover track.
            output_path: Path for mixed output.
        """
        from pydub import AudioSegment

        original = AudioSegment.from_wav(str(track1_path))
        tts = AudioSegment.from_wav(str(track2_path))

        if len(tts) > len(original):
            tts = tts[: len(original)]

        mixed = original.overlay(tts)
        mixed.export(str(output_path), format="wav")
        logger.info("Mixed tracks to %s", output_path)

    def generate_voiceover(
        self,
        subtitle_lines: list,
        original_audio_path: Path,
        output_path: Path,
        video_duration_ms: int,
    ) -> None:
        """Generate full voiceover with dynamic ducking and chunking.

        Args:
            subtitle_lines: List of SubtitleLine objects with audio_clip_path set.
            original_audio_path: Path to extracted original audio.
            output_path: Path for final voiceover WAV.
            video_duration_ms: Total video duration for chunk calculations.
        """
        from pydub import AudioSegment
        from src.config import DUCKING_FADE_MS

        original = AudioSegment.from_wav(str(original_audio_path))
        total_duration = len(original)
        chunk_duration = min(self.CHUNK_DURATION_MS, total_duration)
        num_chunks = (total_duration + chunk_duration - 1) // chunk_duration

        chunk_paths: list[Path] = []

        for chunk_idx in range(num_chunks):
            chunk_start = chunk_idx * chunk_duration
            chunk_end = min(chunk_start + chunk_duration, total_duration)

            chunk_audio = original[chunk_start:chunk_end]
            chunk_path = output_path.parent / f"chunk_{chunk_idx:02d}.wav"
            chunk_audio.export(str(chunk_path), format="wav")

            duck_intervals: list[tuple[int, int, int]] = []

            for line in subtitle_lines:
                if not line.audio_clip_path:
                    continue

                line_start = line.start_ms - chunk_start
                line_end = line.end_ms - chunk_start

                if line_end < 0 or line_start >= chunk_duration:
                    continue

                line_start = max(0, line_start)
                line_end = min(chunk_duration, line_end)

                duck_intervals.append((line_start, line_end, DUCKING_FADE_MS))

            if duck_intervals:
                ducked_path = chunk_path.parent / f"chunk_{chunk_idx:02d}_ducked.wav"
                self.apply_ducking(chunk_path, duck_intervals, ducked_path)
                chunk_path = ducked_path

            tts_concat_path = chunk_path.parent / f"chunk_{chunk_idx:02d}_tts.wav"
            self._concatenate_tts_clips(
                subtitle_lines, chunk_start, chunk_duration, tts_concat_path
            )

            if tts_concat_path.exists():
                final_chunk_path = (
                    chunk_path.parent / f"chunk_{chunk_idx:02d}_mixed.wav"
                )
                self.mix_audio_tracks(chunk_path, tts_concat_path, final_chunk_path)
                chunk_paths.append(final_chunk_path)
            else:
                chunk_paths.append(chunk_path)

        if len(chunk_paths) == 1:
            import shutil

            shutil.move(str(chunk_paths[0]), str(output_path))
        else:
            self._concatenate_chunks(chunk_paths, output_path)

        logger.info("Generated voiceover at %s", output_path)

    def _concatenate_tts_clips(
        self,
        subtitle_lines: list,
        chunk_start: int,
        chunk_duration: int,
        output_path: Path,
    ) -> None:
        """Concatenate TTS clips for a chunk into a single audio file.

        Args:
            subtitle_lines: All subtitle lines with audio paths.
            chunk_start: Start time of chunk in milliseconds.
            chunk_duration: Duration of chunk in milliseconds.
            output_path: Path for concatenated TTS file.
        """
        from pydub import AudioSegment

        concat_segments: list[AudioSegment] = []

        for line in subtitle_lines:
            if not line.audio_clip_path:
                continue

            line_start = line.start_ms - chunk_start
            line_end = line.end_ms - chunk_start

            if line_end < 0 or line_start >= chunk_duration:
                continue

            line_start = max(0, line_start)
            line_end = min(chunk_duration, line_end)
            line_duration = line_end - line_start

            try:
                tts_audio = AudioSegment.from_mp3(line.audio_clip_path)

                if len(tts_audio) > line_duration:
                    tts_audio = tts_audio[:line_duration]
                elif len(tts_audio) < line_duration:
                    silence = AudioSegment.silent(
                        duration=line_duration - len(tts_audio)
                    )
                    tts_audio = tts_audio + silence

                if line_start > len(concat_segments) * 1000 * 3600:
                    gap_duration = line_start - len(concat_segments) * 1000 * 3600
                    concat_segments.append(AudioSegment.silent(duration=gap_duration))

                concat_segments.append(tts_audio)
            except Exception as e:
                logger.warning(
                    "Failed to load TTS clip %s: %s", line.audio_clip_path, e
                )

        if concat_segments:
            combined = sum(concat_segments)
            combined.export(str(output_path), format="wav")  # type: ignore[union-attr]
        else:
            output_path.touch()

    def _concatenate_chunks(self, chunk_paths: list[Path], output_path: Path) -> None:
        """Concatenate multiple audio chunks using FFmpeg concat filter.

        Args:
            chunk_paths: List of paths to chunk audio files.
            output_path: Path for final concatenated output.
        """
        concat_list_path = output_path.parent / "concat_list.txt"

        with open(concat_list_path, "w") as f:
            for chunk_path in chunk_paths:
                f.write(f"file '{chunk_path}'\n")

        cmd = [
            "ffmpeg",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_list_path),
            "-c",
            "copy",
            str(output_path),
            "-y",
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        concat_list_path.unlink()

        if result.returncode != 0:
            raise AudioProcessingError(
                f"FFmpeg chunk concatenation failed: {result.stderr}"
            )

        logger.info("Concatenated %d chunks to %s", len(chunk_paths), output_path)
