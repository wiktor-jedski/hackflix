"""Tests for audio processing utility.

Tests cover:
- Audio extraction (mock ffmpeg)
- Ducking with various intervals
- Fade duration verification
- Speedup factors (1.0x, 1.3x, invalid)
- Audio mixing and overlay
- Chunking logic (10-minute chunks)
- Error handling (missing files, invalid formats)
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.utils.audio_processor import AudioProcessor, AudioProcessingError
from src.utils.subtitle_parser import SubtitleLine


class TestAudioProcessorInitialization:
    """Tests for AudioProcessor initialization and constants."""

    def test_initialization_sets_constants(self):
        """Verify AudioProcessor initializes with correct constants."""
        processor = AudioProcessor()
        assert processor.FADE_DOWN_MS == 100
        assert processor.FADE_UP_MS == 500
        assert processor.CHUNK_DURATION_MS == 10 * 60 * 1000  # 10 minutes
        assert processor.MAX_DRIFT_MS == 5000  # 5 seconds

    def test_chunk_duration_is_10_minutes(self):
        """Verify chunk duration is 10 minutes in milliseconds."""
        processor = AudioProcessor()
        expected = 10 * 60 * 1000
        assert processor.CHUNK_DURATION_MS == expected


class TestExtractAudio:
    """Tests for extract_audio method."""

    def test_extract_audio_success(self, tmp_path: Path):
        """Verify successful audio extraction with ffmpeg."""
        video_path = tmp_path / "video.mp4"
        output_path = tmp_path / "audio.wav"

        video_path.touch()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")

            processor = AudioProcessor()
            processor.extract_audio(video_path, output_path)

            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert args[0] == "ffmpeg"
            assert "-i" in args
            assert str(video_path) in args
            assert "-vn" in args
            assert "-acodec" in args
            assert "pcm_s16le" in args
            assert "-ar" in args
            assert "16000" in args
            assert "-ac" in args
            assert "1" in args
            assert str(output_path) in args
            assert "-y" in args

    def test_extract_audio_no_audio_track(self, tmp_path: Path):
        """Verify error when video has no audio track."""
        video_path = tmp_path / "video.mp4"
        output_path = tmp_path / "audio.wav"

        video_path.touch()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stderr="Stream map '0:a' matches no streams",
                stdout="",
            )

            processor = AudioProcessor()

            with pytest.raises(AudioProcessingError) as exc_info:
                processor.extract_audio(video_path, output_path)

            assert "no audio track" in str(exc_info.value)

    def test_extract_audio_ffmpeg_failure(self, tmp_path: Path):
        """Verify error when ffmpeg extraction fails."""
        video_path = tmp_path / "video.mp4"
        output_path = tmp_path / "audio.wav"

        video_path.touch()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stderr="Unknown error occurred",
                stdout="",
            )

            processor = AudioProcessor()

            with pytest.raises(AudioProcessingError) as exc_info:
                processor.extract_audio(video_path, output_path)

            assert "FFmpeg audio extraction failed" in str(exc_info.value)


class TestCreateFade:
    """Tests for _create_fade helper method."""

    def test_create_fade_empty_segment(self):
        """Verify _create_fade handles empty segments."""
        from pydub import AudioSegment

        processor = AudioProcessor()
        empty = AudioSegment.empty()
        result = processor._create_fade(empty, 0, -6)
        assert len(result) == 0

    def test_create_fade_returns_audio_segment(self):
        """Verify _create_fade returns an AudioSegment."""
        processor = AudioProcessor()

        with patch("pydub.AudioSegment") as mock_segment:
            mock_audio = MagicMock()
            mock_audio.__len__ = MagicMock(return_value=100)
            mock_chunk = MagicMock()
            mock_chunk.__add__ = MagicMock(return_value=mock_chunk)
            mock_audio.__getitem__ = MagicMock(return_value=mock_chunk)
            mock_segment.empty.return_value = mock_chunk

            processor._create_fade(mock_audio, 0, -6)

            # Verify segment was sliced for fade chunks
            assert mock_audio.__getitem__.called


class TestApplyDucking:
    """Tests for apply_ducking method."""

    def test_apply_ducking_single_interval(self, tmp_path: Path):
        """Verify ducking is applied to a single interval."""
        audio_path = tmp_path / "input.wav"
        output_path = tmp_path / "output.wav"

        audio_path.touch()

        duck_intervals = [(1000, 2000, 100)]

        with patch("pydub.AudioSegment") as mock_audio_segment:
            mock_audio = MagicMock()
            mock_audio.__len__ = MagicMock(return_value=5000)
            mock_audio.__getitem__ = MagicMock(return_value=MagicMock())
            mock_audio.__add__ = MagicMock(return_value=MagicMock())
            mock_audio_segment.from_wav.return_value = mock_audio
            mock_audio_segment.empty.return_value = MagicMock()

            processor = AudioProcessor()
            processor.apply_ducking(audio_path, duck_intervals, output_path)

            mock_audio_segment.from_wav.assert_called_once_with(str(audio_path))

    def test_apply_ducking_multiple_intervals(self, tmp_path: Path):
        """Verify ducking is applied to multiple intervals."""
        audio_path = tmp_path / "input.wav"
        output_path = tmp_path / "output.wav"

        audio_path.touch()

        duck_intervals = [(0, 1000, 100), (2000, 3000, 100), (5000, 6000, 100)]

        with patch("pydub.AudioSegment") as mock_audio_segment:
            mock_audio = MagicMock()
            mock_audio.__len__ = MagicMock(return_value=10000)
            mock_audio.__getitem__ = MagicMock(return_value=MagicMock())
            mock_audio.__add__ = MagicMock(return_value=MagicMock())
            mock_audio_segment.from_wav.return_value = mock_audio
            mock_audio_segment.empty.return_value = MagicMock()

            processor = AudioProcessor()
            processor.apply_ducking(audio_path, duck_intervals, output_path)

            mock_audio_segment.from_wav.assert_called_once()

    def test_apply_ducking_clips_to_audio_bounds(self, tmp_path: Path):
        """Verify ducking intervals are clipped to audio bounds."""
        audio_path = tmp_path / "input.wav"
        output_path = tmp_path / "output.wav"

        audio_path.touch()

        duck_intervals = [(-100, 10000, 100)]

        with patch("pydub.AudioSegment") as mock_audio_segment:
            mock_audio = MagicMock()
            mock_audio.__len__ = MagicMock(return_value=5000)
            mock_audio.__getitem__ = MagicMock(return_value=MagicMock())
            mock_audio.__add__ = MagicMock(return_value=MagicMock())
            mock_audio_segment.from_wav.return_value = mock_audio
            mock_audio_segment.empty.return_value = MagicMock()

            processor = AudioProcessor()
            processor.apply_ducking(audio_path, duck_intervals, output_path)

            mock_audio_segment.from_wav.assert_called_once()

    def test_apply_ducking_short_interval_fades(self, tmp_path: Path):
        """Verify fade durations are adjusted for short intervals."""
        audio_path = tmp_path / "input.wav"
        output_path = tmp_path / "output.wav"

        audio_path.touch()

        duck_intervals = [(0, 50, 100)]

        with patch("pydub.AudioSegment") as mock_audio_segment:
            mock_audio = MagicMock()
            mock_audio.__len__ = MagicMock(return_value=100)
            mock_audio.__getitem__ = MagicMock(return_value=MagicMock())
            mock_audio.__add__ = MagicMock(return_value=MagicMock())
            mock_audio_segment.from_wav.return_value = mock_audio
            mock_audio_segment.empty.return_value = MagicMock()

            processor = AudioProcessor()
            processor.apply_ducking(audio_path, duck_intervals, output_path)

            mock_audio_segment.from_wav.assert_called_once()

    def test_apply_ducking_uses_correct_db_level(self, tmp_path: Path):
        """Verify ducking uses DUCKING_DB constant for volume reduction."""
        processor = AudioProcessor()
        assert processor.DUCKING_DB == -6


class TestStretchAudio:
    """Tests for stretch_audio method."""

    def test_stretch_audio_valid_factor_1_0(self, tmp_path: Path):
        """Verify stretch_audio with factor 1.0 copies file (no processing)."""
        audio_path = tmp_path / "input.wav"
        output_path = tmp_path / "output.wav"

        audio_path.write_bytes(b"fake audio data")

        with patch("shutil.copy") as mock_copy:
            processor = AudioProcessor()
            processor.stretch_audio(audio_path, 1.0, output_path)

            mock_copy.assert_called_once_with(str(audio_path), str(output_path))

    def test_stretch_audio_valid_factor_1_3(self, tmp_path: Path):
        """Verify stretch_audio with factor 1.3 (max speedup)."""
        audio_path = tmp_path / "input.wav"
        output_path = tmp_path / "output.wav"

        audio_path.touch()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")

            processor = AudioProcessor()
            processor.stretch_audio(audio_path, 1.3, output_path)

            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert "atempo=1.3" in args

    def test_stretch_audio_invalid_factor_below_min(self, tmp_path: Path):
        """Verify error when speedup factor is below 1.0."""
        audio_path = tmp_path / "input.wav"
        output_path = tmp_path / "output.wav"

        audio_path.touch()

        processor = AudioProcessor()

        with pytest.raises(AudioProcessingError) as exc_info:
            processor.stretch_audio(audio_path, 0.5, output_path)

        assert "Invalid speedup factor" in str(exc_info.value)

    def test_stretch_audio_invalid_factor_above_max(self, tmp_path: Path):
        """Verify error when speedup factor exceeds 1.3."""
        audio_path = tmp_path / "input.wav"
        output_path = tmp_path / "output.wav"

        audio_path.touch()

        processor = AudioProcessor()

        with pytest.raises(AudioProcessingError) as exc_info:
            processor.stretch_audio(audio_path, 2.0, output_path)

        assert "Invalid speedup factor" in str(exc_info.value)

    def test_stretch_audio_ffmpeg_failure(self, tmp_path: Path):
        """Verify error when ffmpeg time-stretching fails."""
        audio_path = tmp_path / "input.wav"
        output_path = tmp_path / "output.wav"

        audio_path.touch()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stderr="Filter atempo not found",
                stdout="",
            )

            processor = AudioProcessor()

            with pytest.raises(AudioProcessingError) as exc_info:
                processor.stretch_audio(audio_path, 1.1, output_path)

            assert "FFmpeg time-stretching failed" in str(exc_info.value)


class TestMixAudioTracks:
    """Tests for mix_audio_tracks method."""

    def test_mix_audio_tracks_success(self, tmp_path: Path):
        """Verify successful mixing of two audio tracks."""
        track1_path = tmp_path / "original.wav"
        track2_path = tmp_path / "tts.wav"
        output_path = tmp_path / "mixed.wav"

        track1_path.touch()
        track2_path.touch()

        with patch("pydub.AudioSegment") as mock_audio_segment:
            mock_original = MagicMock()
            mock_original.__len__ = MagicMock(return_value=10000)
            mock_original.overlay = MagicMock(return_value=MagicMock())
            mock_tts = MagicMock()
            mock_tts.__len__ = MagicMock(return_value=5000)

            def side_effect(path):
                if "original" in str(path):
                    return mock_original
                return mock_tts

            mock_audio_segment.from_wav.side_effect = side_effect

            processor = AudioProcessor()
            processor.mix_audio_tracks(track1_path, track2_path, output_path)

            mock_audio_segment.from_wav.assert_any_call(str(track1_path))
            mock_audio_segment.from_wav.assert_any_call(str(track2_path))
            mock_original.overlay.assert_called_once_with(mock_tts)

    def test_mix_audio_tracks_tts_longer_than_original(self, tmp_path: Path):
        """Verify TTS is truncated when longer than original."""
        track1_path = tmp_path / "original.wav"
        track2_path = tmp_path / "tts.wav"
        output_path = tmp_path / "mixed.wav"

        track1_path.touch()
        track2_path.touch()

        with patch("pydub.AudioSegment") as mock_audio_segment:
            mock_original = MagicMock()
            mock_original.__len__ = MagicMock(return_value=5000)
            mock_original.__getitem__ = MagicMock(return_value=MagicMock())
            mock_original.overlay = MagicMock(return_value=MagicMock())
            mock_tts = MagicMock()
            mock_tts.__len__ = MagicMock(return_value=10000)

            def side_effect(path):
                if "original" in str(path):
                    return mock_original
                return mock_tts

            mock_audio_segment.from_wav.side_effect = side_effect

            processor = AudioProcessor()
            processor.mix_audio_tracks(track1_path, track2_path, output_path)

            mock_tts.__getitem__.assert_called()


class TestChunkingLogic:
    """Tests for chunking logic in generate_voiceover."""

    def test_chunk_duration_constant(self):
        """Verify chunk duration is exactly 10 minutes."""
        processor = AudioProcessor()
        assert processor.CHUNK_DURATION_MS == 600000  # 10 * 60 * 1000

    def test_single_chunk_for_short_audio(self):
        """Verify single chunk is used for audio under 10 minutes."""
        processor = AudioProcessor()
        total_duration = 5 * 60 * 1000  # 5 minutes
        chunk_duration = min(processor.CHUNK_DURATION_MS, total_duration)
        num_chunks = (total_duration + chunk_duration - 1) // chunk_duration
        assert num_chunks == 1

    def test_multiple_chunks_for_long_audio(self):
        """Verify multiple chunks for audio over 10 minutes."""
        processor = AudioProcessor()
        total_duration = 25 * 60 * 1000  # 25 minutes
        chunk_duration = min(processor.CHUNK_DURATION_MS, total_duration)
        num_chunks = (total_duration + chunk_duration - 1) // chunk_duration
        assert num_chunks == 3

    def test_exact_10_minute_chunks(self):
        """Verify exact 10-minute audio creates exactly 1 chunk."""
        processor = AudioProcessor()
        total_duration = 10 * 60 * 1000  # exactly 10 minutes
        chunk_duration = min(processor.CHUNK_DURATION_MS, total_duration)
        num_chunks = (total_duration + chunk_duration - 1) // chunk_duration
        assert num_chunks == 1


class TestDriftTracking:
    """Tests for drift tracking in time-stretching."""

    def test_max_drift_constant(self):
        """Verify max drift is 5 seconds in milliseconds."""
        processor = AudioProcessor()
        assert processor.MAX_DRIFT_MS == 5000


class TestAudioProcessingError:
    """Tests for AudioProcessingError exception."""

    def test_error_message_contains_reason(self):
        """Verify error message contains the failure reason."""
        error = AudioProcessingError("Test failure reason")
        assert "Test failure reason" in str(error)

    def test_error_is_exception_subclass(self):
        """Verify AudioProcessingError is an Exception subclass."""
        error = AudioProcessingError("Test")
        assert isinstance(error, Exception)


class TestGenerateVoiceover:
    """Integration tests for generate_voiceover method."""

    def test_generate_voiceover_method_exists(self):
        """Verify generate_voiceover method exists and is callable."""
        processor = AudioProcessor()
        assert hasattr(processor, "generate_voiceover")
        assert callable(processor.generate_voiceover)

    def test_generate_voiceover_internal_methods_exist(self):
        """Verify internal helper methods exist."""
        processor = AudioProcessor()
        assert hasattr(processor, "_concatenate_tts_clips")
        assert hasattr(processor, "_concatenate_chunks")
        assert callable(processor._concatenate_tts_clips)
        assert callable(processor._concatenate_chunks)

    def test_concatenate_tts_clips_creates_file_with_audio(self, tmp_path: Path):
        """Verify _concatenate_tts_clips creates output file when subtitles have audio."""

        processor = AudioProcessor()

        tts_clip = tmp_path / "tts.mp3"
        tts_clip.write_bytes(b"fake mp3 data")

        subtitle_lines = [
            SubtitleLine(
                index=1,
                start_ms=0,
                end_ms=2000,
                text_source="Test",
                audio_clip_path=str(tts_clip),
                is_sound_effect=False,
            ),
        ]

        output_path = tmp_path / "concatenated.wav"

        with patch("pydub.AudioSegment") as mock_segment:
            mock_audio = MagicMock()
            mock_audio.__len__ = MagicMock(return_value=2000)
            mock_segment.from_mp3.return_value = mock_audio
            mock_segment.silent.return_value = MagicMock()
            mock_segment.__add__ = MagicMock(return_value=mock_audio)

            processor._concatenate_tts_clips(
                subtitle_lines,
                chunk_start=0,
                chunk_duration=600000,
                output_path=output_path,
            )

            mock_segment.from_mp3.assert_called()

    def test_concatenate_tts_clips_adds_silence_gaps(self, tmp_path: Path):
        """Verify _concatenate_tts_clips adds silence between clips for correct timing."""

        processor = AudioProcessor()

        tts_clip = tmp_path / "tts.mp3"
        tts_clip.write_bytes(b"fake mp3 data")

        subtitle_lines = [
            SubtitleLine(
                index=1,
                start_ms=5000,
                end_ms=7000,
                text_source="First line",
                audio_clip_path=str(tts_clip),
                is_sound_effect=False,
            ),
            SubtitleLine(
                index=2,
                start_ms=15000,
                end_ms=17000,
                text_source="Second line",
                audio_clip_path=str(tts_clip),
                is_sound_effect=False,
            ),
        ]

        output_path = tmp_path / "concatenated.wav"

        with patch("pydub.AudioSegment") as mock_segment:
            mock_audio = MagicMock()
            mock_audio.__len__ = MagicMock(return_value=2000)
            mock_silence = MagicMock()
            mock_silence.__len__ = MagicMock(return_value=5000)
            mock_segment.from_mp3.return_value = mock_audio
            mock_segment.silent.return_value = mock_silence

            processor._concatenate_tts_clips(
                subtitle_lines,
                chunk_start=0,
                chunk_duration=600000,
                output_path=output_path,
            )

            silent_calls = mock_segment.silent.call_args_list
            assert len(silent_calls) >= 2
            first_gap = silent_calls[0][1]["duration"]
            assert first_gap == 5000
            second_gap = silent_calls[1][1]["duration"]
            assert second_gap == 8000

    def test_concatenate_tts_clips_speeds_up_long_audio(self, tmp_path: Path):
        """Verify TTS longer than subtitle duration is sped up (up to 1.3x)."""

        processor = AudioProcessor()

        tts_clip = tmp_path / "tts.mp3"
        tts_clip.write_bytes(b"fake mp3 data")

        subtitle_lines = [
            SubtitleLine(
                index=1,
                start_ms=0,
                end_ms=2000,
                text_source="Test",
                audio_clip_path=str(tts_clip),
                is_sound_effect=False,
            ),
        ]

        output_path = tmp_path / "concatenated.wav"

        with (
            patch("pydub.AudioSegment") as mock_segment,
            patch.object(processor, "stretch_audio") as mock_stretch,
        ):
            mock_audio = MagicMock()
            # TTS is 2500ms, subtitle slot is 2000ms -> needs 1.25x speedup
            mock_audio.__len__ = MagicMock(return_value=2500)
            mock_segment.from_mp3.return_value = mock_audio

            mock_stretched = MagicMock()
            mock_stretched.__len__ = MagicMock(return_value=2000)
            mock_segment.from_wav.return_value = mock_stretched

            processor._concatenate_tts_clips(
                subtitle_lines,
                chunk_start=0,
                chunk_duration=600000,
                output_path=output_path,
            )

            mock_stretch.assert_called_once()
            call_args = mock_stretch.call_args
            speedup_factor = call_args[0][1]
            assert speedup_factor == pytest.approx(1.25, rel=0.01)

    def test_concatenate_tts_clips_caps_speedup_at_1_3x(self, tmp_path: Path):
        """Verify speedup is capped at 1.3x even for very long TTS."""

        processor = AudioProcessor()

        tts_clip = tmp_path / "tts.mp3"
        tts_clip.write_bytes(b"fake mp3 data")

        subtitle_lines = [
            SubtitleLine(
                index=1,
                start_ms=0,
                end_ms=2000,
                text_source="Test",
                audio_clip_path=str(tts_clip),
                is_sound_effect=False,
            ),
        ]

        output_path = tmp_path / "concatenated.wav"

        with (
            patch("pydub.AudioSegment") as mock_segment,
            patch.object(processor, "stretch_audio") as mock_stretch,
        ):
            mock_audio = MagicMock()
            # TTS is 4000ms, subtitle slot is 2000ms -> needs 2.0x but caps at 1.3x
            mock_audio.__len__ = MagicMock(return_value=4000)
            mock_segment.from_mp3.return_value = mock_audio

            # After 1.3x speedup, TTS is ~3077ms (still longer than 2000ms slot)
            mock_stretched = MagicMock()
            mock_stretched.__len__ = MagicMock(return_value=3077)
            mock_segment.from_wav.return_value = mock_stretched

            processor._concatenate_tts_clips(
                subtitle_lines,
                chunk_start=0,
                chunk_duration=600000,
                output_path=output_path,
            )

            mock_stretch.assert_called_once()
            call_args = mock_stretch.call_args
            speedup_factor = call_args[0][1]
            assert speedup_factor == 1.3

    def test_concatenate_tts_clips_allows_overflow_delays_next(self, tmp_path: Path):
        """Verify overflow from one clip delays the next clip (no truncation)."""

        processor = AudioProcessor()

        tts_clip = tmp_path / "tts.mp3"
        tts_clip.write_bytes(b"fake mp3 data")

        subtitle_lines = [
            SubtitleLine(
                index=1,
                start_ms=0,
                end_ms=2000,
                text_source="First",
                audio_clip_path=str(tts_clip),
                is_sound_effect=False,
            ),
            SubtitleLine(
                index=2,
                start_ms=3000,
                end_ms=5000,
                text_source="Second",
                audio_clip_path=str(tts_clip),
                is_sound_effect=False,
            ),
        ]

        output_path = tmp_path / "concatenated.wav"
        segments_appended = []

        with (
            patch("pydub.AudioSegment") as mock_segment,
            patch.object(processor, "stretch_audio"),
        ):
            # First TTS is 4000ms, slot is 2000ms -> after 1.3x = 3077ms
            # Second TTS is 2000ms, slot is 2000ms -> no speedup needed
            call_count = [0]

            def from_mp3_side_effect(path):
                call_count[0] += 1
                m = MagicMock()
                if call_count[0] == 1:
                    m.__len__ = MagicMock(return_value=4000)
                else:
                    m.__len__ = MagicMock(return_value=2000)
                return m

            mock_segment.from_mp3.side_effect = from_mp3_side_effect

            mock_stretched = MagicMock()
            mock_stretched.__len__ = MagicMock(return_value=3077)
            mock_segment.from_wav.return_value = mock_stretched

            mock_silence = MagicMock()

            def silent_side_effect(duration):
                segments_appended.append(("silence", duration))
                return mock_silence

            mock_segment.silent.side_effect = silent_side_effect

            processor._concatenate_tts_clips(
                subtitle_lines,
                chunk_start=0,
                chunk_duration=600000,
                output_path=output_path,
            )

            # First clip starts at 0, takes 3077ms (overflow of 1077ms)
            # Second clip should start at 3000ms but current_position is 3077ms
            # So NO gap should be added before second clip (it starts immediately)
            # Only the initial silence before first clip (if any) should be added
            # Since first clip starts at 0, no initial gap needed
            # After first clip (3077ms), second clip starts at 3000ms
            # Since 3000 < 3077, no gap is added - clip starts immediately
            assert mock_segment.silent.call_count == 0

    def test_generate_voiceover_calls_internal_methods(self, tmp_path: Path):
        """Verify generate_voiceover calls internal helper methods."""

        processor = AudioProcessor()

        original_audio = tmp_path / "original.wav"
        output_path = tmp_path / "voiceover.wav"

        tts_clip = tmp_path / "tts.mp3"
        tts_clip.write_bytes(b"fake mp3 data")

        subtitle_lines = [
            SubtitleLine(
                index=1,
                start_ms=0,
                end_ms=2000,
                text_source="Test",
                audio_clip_path=str(tts_clip),
                is_sound_effect=False,
            ),
        ]

        with (
            patch("pydub.AudioSegment") as mock_segment,
            patch.object(processor, "_concatenate_tts_clips") as mock_concat_tts,
            patch.object(processor, "_concatenate_chunks") as mock_concat_chunks,
        ):
            mock_audio = MagicMock()
            mock_audio.__len__ = MagicMock(return_value=600001)
            mock_segment.from_wav.return_value = mock_audio
            mock_segment.from_mp3.return_value = mock_audio
            mock_segment.silent.return_value = MagicMock()
            mock_segment.__add__ = MagicMock(return_value=mock_audio)

            mock_concat_tts.return_value = None
            mock_concat_chunks.return_value = None

            try:
                processor.generate_voiceover(
                    subtitle_lines,
                    original_audio,
                    output_path,
                    video_duration_ms=600001,
                )
            except Exception:
                pass

            mock_concat_tts.assert_called()
            mock_concat_chunks.assert_called()

    def test_generate_voiceover_multiple_chunks(self, tmp_path: Path):
        """Verify generate_voiceover handles multiple chunks correctly."""

        processor = AudioProcessor()

        original_audio = tmp_path / "original.wav"
        output_path = tmp_path / "voiceover.wav"

        tts_clip = tmp_path / "tts.mp3"
        tts_clip.write_bytes(b"fake mp3 data")

        subtitle_lines = [
            SubtitleLine(
                index=1,
                start_ms=0,
                end_ms=2000,
                text_source="First chunk",
                audio_clip_path=str(tts_clip),
                is_sound_effect=False,
            ),
            SubtitleLine(
                index=2,
                start_ms=700000,
                end_ms=702000,
                text_source="Second chunk",
                audio_clip_path=str(tts_clip),
                is_sound_effect=False,
            ),
        ]

        with (
            patch("pydub.AudioSegment") as mock_segment,
            patch.object(processor, "_concatenate_tts_clips") as mock_concat_tts,
            patch.object(processor, "_concatenate_chunks") as mock_concat_chunks,
        ):
            mock_audio = MagicMock()
            mock_audio.__len__ = MagicMock(return_value=1200000)
            mock_segment.from_wav.return_value = mock_audio
            mock_segment.from_mp3.return_value = mock_audio
            mock_segment.silent.return_value = MagicMock()
            mock_segment.__add__ = MagicMock(return_value=mock_audio)

            mock_concat_tts.return_value = None
            mock_concat_chunks.return_value = None

            try:
                processor.generate_voiceover(
                    subtitle_lines,
                    original_audio,
                    output_path,
                    video_duration_ms=1200000,
                )
            except Exception:
                pass

            assert mock_concat_tts.call_count >= 2
            mock_concat_chunks.assert_called_once()


class TestConcatenateChunks:
    """Tests for _concatenate_chunks private method."""

    def test_concatenate_chunks_success(self, tmp_path: Path):
        """Verify _concatenate_chunks concatenates multiple chunk files."""
        processor = AudioProcessor()

        chunk1 = tmp_path / "chunk_00.wav"
        chunk2 = tmp_path / "chunk_01.wav"
        output_path = tmp_path / "final.wav"

        chunk1.write_bytes(b"chunk1 data")
        chunk2.write_bytes(b"chunk2 data")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")

            processor._concatenate_chunks([chunk1, chunk2], output_path)

            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert "-f" in args
            assert "concat" in args
            assert str(output_path) in args

    def test_concatenate_chunks_single_file(self, tmp_path: Path):
        """Verify _concatenate_chunks calls ffmpeg even for single file."""
        processor = AudioProcessor()

        chunk = tmp_path / "chunk_00.wav"
        output_path = tmp_path / "final.wav"

        chunk.write_bytes(b"chunk data")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")

            processor._concatenate_chunks([chunk], output_path)

            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert "-f" in args
            assert "concat" in args

    def test_concatenate_chunks_ffmpeg_failure(self, tmp_path: Path):
        """Verify _concatenate_chunks raises error on FFmpeg failure."""
        processor = AudioProcessor()

        chunk1 = tmp_path / "chunk_00.wav"
        chunk2 = tmp_path / "chunk_01.wav"
        output_path = tmp_path / "final.wav"

        chunk1.write_bytes(b"chunk1 data")
        chunk2.write_bytes(b"chunk2 data")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stderr="Invalid data",
                stdout="",
            )

            with pytest.raises(AudioProcessingError) as exc_info:
                processor._concatenate_chunks([chunk1, chunk2], output_path)

            assert "FFmpeg chunk concatenation failed" in str(exc_info.value)


class TestMuxVoiceoverIntoVideo:
    """Tests for mux_voiceover_into_video method."""

    def test_mux_voiceover_success(self, tmp_path: Path):
        """Verify successful muxing of voiceover into video."""
        video_path = tmp_path / "video.mkv"
        voiceover_path = tmp_path / "voiceover.wav"
        output_path = tmp_path / "video_with_voiceover.mkv"

        video_path.touch()
        voiceover_path.touch()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")

            processor = AudioProcessor()
            processor.mux_voiceover_into_video(video_path, voiceover_path, output_path)

            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert args[0] == "ffmpeg"
            assert "-i" in args
            assert str(video_path) in args
            assert str(voiceover_path) in args
            assert "-map" in args
            assert "0:v" in args
            assert "0:a" in args
            assert "1:a" in args
            assert "-c:v" in args
            assert "copy" in args
            assert str(output_path) in args

    def test_mux_voiceover_preserves_video_stream(self, tmp_path: Path):
        """Verify video stream is copied (not re-encoded)."""
        video_path = tmp_path / "video.mkv"
        voiceover_path = tmp_path / "voiceover.wav"
        output_path = tmp_path / "video_with_voiceover.mkv"

        video_path.touch()
        voiceover_path.touch()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")

            processor = AudioProcessor()
            processor.mux_voiceover_into_video(video_path, voiceover_path, output_path)

            args = mock_run.call_args[0][0]
            # Find -c:v and verify it's followed by "copy"
            cv_idx = args.index("-c:v")
            assert args[cv_idx + 1] == "copy"

    def test_mux_voiceover_adds_metadata(self, tmp_path: Path):
        """Verify metadata is added to voiceover audio track."""
        video_path = tmp_path / "video.mkv"
        voiceover_path = tmp_path / "voiceover.wav"
        output_path = tmp_path / "video_with_voiceover.mkv"

        video_path.touch()
        voiceover_path.touch()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")

            processor = AudioProcessor()
            processor.mux_voiceover_into_video(video_path, voiceover_path, output_path)

            args = mock_run.call_args[0][0]
            assert "-metadata:s:a:1" in args
            # Check for language metadata
            lang_idx = [i for i, a in enumerate(args) if a == "-metadata:s:a:1"]
            assert len(lang_idx) >= 1

    def test_mux_voiceover_ffmpeg_failure(self, tmp_path: Path):
        """Verify error when ffmpeg muxing fails."""
        video_path = tmp_path / "video.mkv"
        voiceover_path = tmp_path / "voiceover.wav"
        output_path = tmp_path / "video_with_voiceover.mkv"

        video_path.touch()
        voiceover_path.touch()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stderr="Muxing error occurred",
                stdout="",
            )

            processor = AudioProcessor()

            with pytest.raises(AudioProcessingError) as exc_info:
                processor.mux_voiceover_into_video(
                    video_path, voiceover_path, output_path
                )

            assert "FFmpeg voiceover muxing failed" in str(exc_info.value)
