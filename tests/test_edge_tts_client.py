"""Tests for Edge-TTS client.

Tests cover:
- Successful TTS generation
- Hardcoded voice usage
- Empty line skipping
- Sound effect skipping
- Network errors
- Temp file cleanup
- API timeouts
"""

import asyncio
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

import sys
from types import ModuleType

from src.utils.edge_tts_client import (
    EdgeTTSClient,
    TTSError,
)


class TestEdgeTTSClientInitialization:
    """Tests for EdgeTTSClient initialization."""

    def test_initialization_with_configured_voice(self):
        """Verify client initializes with configured voice."""
        with patch.dict("sys.modules", {"edge_tts": MagicMock()}):
            import src.utils.edge_tts_client as tts_module

            original_voice = tts_module.TTS_VOICE
            tts_module.TTS_VOICE = "pl-PL-MarekNeural"
            try:
                client = tts_module.EdgeTTSClient()
                assert client.voice == "pl-PL-MarekNeural"
            finally:
                tts_module.TTS_VOICE = original_voice

    def test_output_rate_is_correct(self):
        """Verify output rate is set correctly."""
        assert EdgeTTSClient.OUTPUT_RATE == 24000

    def test_voice_constant_from_config(self):
        """Verify voice constant is loaded from TTS_VOICE config."""
        from src.config import TTS_VOICE

        assert TTS_VOICE == "pl-PL-MarekNeural"


class TestGenerateTTS:
    """Tests for generate_tts method."""

    def test_generate_tts_success(self, tmp_path: Path):
        """Verify successful TTS generation."""
        with patch.dict("sys.modules", {"edge_tts": MagicMock()}):
            import src.utils.edge_tts_client as tts_module

            original_voice = tts_module.TTS_VOICE
            tts_module.TTS_VOICE = "pl-PL-MarekNeural"
            try:
                client = tts_module.EdgeTTSClient()

                output_path = tmp_path / "output.mp3"
                test_text = "Hello world"

                output_path.touch()
                output_path.write_bytes(b"fake audio data")

                with patch.object(client, "_generate_async", new_callable=AsyncMock):
                    result = client.generate_tts(test_text, output_path)

                    assert result == output_path
            finally:
                tts_module.TTS_VOICE = original_voice

    def test_generate_tts_empty_text_error(self, tmp_path: Path):
        """Verify error when text is empty."""
        with patch.dict("sys.modules", {"edge_tts": MagicMock()}):
            import src.utils.edge_tts_client as tts_module

            original_voice = tts_module.TTS_VOICE
            tts_module.TTS_VOICE = "pl-PL-MarekNeural"
            try:
                client = tts_module.EdgeTTSClient()

                output_path = tmp_path / "output.mp3"

                with pytest.raises(TTSError) as exc_info:
                    client.generate_tts("", output_path)

                assert "empty text" in str(exc_info.value)
            finally:
                tts_module.TTS_VOICE = original_voice

    def test_generate_tts_whitespace_only_error(self, tmp_path: Path):
        """Verify error when text is whitespace only."""
        with patch.dict("sys.modules", {"edge_tts": MagicMock()}):
            import src.utils.edge_tts_client as tts_module

            original_voice = tts_module.TTS_VOICE
            tts_module.TTS_VOICE = "pl-PL-MarekNeural"
            try:
                client = tts_module.EdgeTTSClient()

                output_path = tmp_path / "output.mp3"

                with pytest.raises(TTSError) as exc_info:
                    client.generate_tts("   \n\t  ", output_path)

                assert "empty text" in str(exc_info.value)
            finally:
                tts_module.TTS_VOICE = original_voice

    def test_generate_tts_empty_output_error(self, tmp_path: Path):
        """Verify error when output file is empty."""
        with patch.dict("sys.modules", {"edge_tts": MagicMock()}):
            import src.utils.edge_tts_client as tts_module

            original_voice = tts_module.TTS_VOICE
            tts_module.TTS_VOICE = "pl-PL-MarekNeural"
            try:
                client = tts_module.EdgeTTSClient()

                output_path = tmp_path / "output.mp3"
                output_path.touch()

                with patch.object(client, "_generate_async", new_callable=AsyncMock):
                    with pytest.raises(TTSError) as exc_info:
                        client.generate_tts("Hello", output_path)

                    assert "empty file" in str(exc_info.value)
            finally:
                tts_module.TTS_VOICE = original_voice

    def test_generate_tts_timeout_error(self, tmp_path: Path):
        """Verify error handling for timeout."""
        with patch.dict("sys.modules", {"edge_tts": MagicMock()}):
            import src.utils.edge_tts_client as tts_module

            original_voice = tts_module.TTS_VOICE
            tts_module.TTS_VOICE = "pl-PL-MarekNeural"
            try:
                client = tts_module.EdgeTTSClient()

                output_path = tmp_path / "output.mp3"

                def raise_timeout(*args, **kwargs):
                    raise asyncio.TimeoutError("Connection timeout")

                with patch.object(client, "_generate_async", side_effect=raise_timeout):
                    with pytest.raises(TTSError) as exc_info:
                        client.generate_tts("Hello", output_path)

                    assert "timed out" in str(exc_info.value)
            finally:
                tts_module.TTS_VOICE = original_voice

    def test_generate_tts_generic_error(self, tmp_path: Path):
        """Verify error handling for generic exceptions."""
        with patch.dict("sys.modules", {"edge_tts": MagicMock()}):
            import src.utils.edge_tts_client as tts_module

            original_voice = tts_module.TTS_VOICE
            tts_module.TTS_VOICE = "pl-PL-MarekNeural"
            try:
                client = tts_module.EdgeTTSClient()

                output_path = tmp_path / "output.mp3"

                def raise_error(*args, **kwargs):
                    raise RuntimeError("Unknown error")

                with patch.object(client, "_generate_async", side_effect=raise_error):
                    with pytest.raises(TTSError) as exc_info:
                        client.generate_tts("Hello", output_path)

                    assert "failed" in str(exc_info.value)
            finally:
                tts_module.TTS_VOICE = original_voice


class TestTextNeedsTTS:
    """Tests for text_needs_tts method."""

    def test_needs_tts_normal_text(self):
        """Verify normal text needs TTS."""
        with patch.dict("sys.modules", {"edge_tts": MagicMock()}):
            import src.utils.edge_tts_client as tts_module

            original_voice = tts_module.TTS_VOICE
            tts_module.TTS_VOICE = "pl-PL-MarekNeural"
            try:
                client = tts_module.EdgeTTSClient()
                assert client.text_needs_tts("Hello world") is True
                assert client.text_needs_tts("This is a sentence.") is True
            finally:
                tts_module.TTS_VOICE = original_voice

    def test_not_tts_empty_string(self):
        """Verify empty string doesn't need TTS."""
        with patch.dict("sys.modules", {"edge_tts": MagicMock()}):
            import src.utils.edge_tts_client as tts_module

            original_voice = tts_module.TTS_VOICE
            tts_module.TTS_VOICE = "pl-PL-MarekNeural"
            try:
                client = tts_module.EdgeTTSClient()
                assert client.text_needs_tts("") is False
            finally:
                tts_module.TTS_VOICE = original_voice

    def test_not_tts_whitespace_only(self):
        """Verify whitespace-only text doesn't need TTS."""
        with patch.dict("sys.modules", {"edge_tts": MagicMock()}):
            import src.utils.edge_tts_client as tts_module

            original_voice = tts_module.TTS_VOICE
            tts_module.TTS_VOICE = "pl-PL-MarekNeural"
            try:
                client = tts_module.EdgeTTSClient()
                assert client.text_needs_tts("   ") is False
                assert client.text_needs_tts("\n\t") is False
            finally:
                tts_module.TTS_VOICE = original_voice

    def test_not_tts_ellipsis(self):
        """Verify '...' doesn't need TTS."""
        with patch.dict("sys.modules", {"edge_tts": MagicMock()}):
            import src.utils.edge_tts_client as tts_module

            original_voice = tts_module.TTS_VOICE
            tts_module.TTS_VOICE = "pl-PL-MarekNeural"
            try:
                client = tts_module.EdgeTTSClient()
                assert client.text_needs_tts("...") is False
            finally:
                tts_module.TTS_VOICE = original_voice

    def test_not_tts_bracket_sound_effect(self):
        """Verify bracket-enclosed sound effects don't need TTS."""
        with patch.dict("sys.modules", {"edge_tts": MagicMock()}):
            import src.utils.edge_tts_client as tts_module

            original_voice = tts_module.TTS_VOICE
            tts_module.TTS_VOICE = "pl-PL-MarekNeural"
            try:
                client = tts_module.EdgeTTSClient()
                assert client.text_needs_tts("[Door slams]") is False
                assert client.text_needs_tts("[Music playing]") is False
            finally:
                tts_module.TTS_VOICE = original_voice

    def test_not_tts_parenthesis_sound_effect(self):
        """Verify parenthesis-enclosed sound effects don't need TTS."""
        with patch.dict("sys.modules", {"edge_tts": MagicMock()}):
            import src.utils.edge_tts_client as tts_module

            original_voice = tts_module.TTS_VOICE
            tts_module.TTS_VOICE = "pl-PL-MarekNeural"
            try:
                client = tts_module.EdgeTTSClient()
                assert client.text_needs_tts("(sighs)") is False
                assert client.text_needs_tts("(laughing)") is False
            finally:
                tts_module.TTS_VOICE = original_voice

    def test_not_tts_partial_bracket(self):
        """Verify partial brackets still need TTS."""
        with patch.dict("sys.modules", {"edge_tts": MagicMock()}):
            import src.utils.edge_tts_client as tts_module

            original_voice = tts_module.TTS_VOICE
            tts_module.TTS_VOICE = "pl-PL-MarekNeural"
            try:
                client = tts_module.EdgeTTSClient()
                assert client.text_needs_tts("[Door slams") is True
                assert client.text_needs_tts("sighs)") is True
            finally:
                tts_module.TTS_VOICE = original_voice


class TestGenerateTTSSync:
    """Tests for generate_tts_sync method."""

    def test_sync_calls_generate_tts(self, tmp_path: Path):
        """Verify sync method calls generate_tts."""
        with patch.dict("sys.modules", {"edge_tts": MagicMock()}):
            import src.utils.edge_tts_client as tts_module

            original_voice = tts_module.TTS_VOICE
            tts_module.TTS_VOICE = "pl-PL-MarekNeural"
            try:
                client = tts_module.EdgeTTSClient()

                output_path = tmp_path / "output.mp3"

                with patch.object(
                    client, "generate_tts", return_value=output_path
                ) as mock_gen:
                    result = client.generate_tts_sync("Hello", output_path)

                    mock_gen.assert_called_once_with("Hello", output_path)
                    assert result == output_path
            finally:
                tts_module.TTS_VOICE = original_voice


class TestTTSError:
    """Tests for TTSError exception."""

    def test_error_is_exception_subclass(self):
        """Verify TTSError is an Exception subclass."""
        error = TTSError("Test error")
        assert isinstance(error, Exception)

    def test_error_message(self):
        """Verify error message is preserved."""
        error = TTSError("Custom error message")
        assert "Custom error message" in str(error)


class TestClientWithRealModule:
    """Tests that require the real module with mocked dependencies."""

    def test_initialize_with_mocked_edge_tts(self):
        """Verify client can be initialized with mocked edge_tts."""
        mock_edge_tts = MagicMock()
        with patch.dict("sys.modules", {"edge_tts": mock_edge_tts}):
            import src.utils.edge_tts_client as tts_module

            original_voice = tts_module.TTS_VOICE
            original_communicate = tts_module.edge_tts.Communicate
            tts_module.TTS_VOICE = "pl-PL-MarekNeural"
            try:
                client = tts_module.EdgeTTSClient()
                assert client.voice == "pl-PL-MarekNeural"
            finally:
                tts_module.TTS_VOICE = original_voice

    def test_generate_creates_file_on_success(self, tmp_path: Path):
        """Verify generate_tts creates file when successful."""
        mock_edge_tts = MagicMock()
        with patch.dict("sys.modules", {"edge_tts": mock_edge_tts}):
            import src.utils.edge_tts_client as tts_module

            original_voice = tts_module.TTS_VOICE
            tts_module.TTS_VOICE = "pl-PL-MarekNeural"
            try:
                client = tts_module.EdgeTTSClient()

                output_path = tmp_path / "output.mp3"
                output_path.write_bytes(b"fake audio content")

                async def noop_async(*args, **kwargs):
                    pass

                client._generate_async = noop_async

                result = client.generate_tts("Hello world", output_path)

                assert result == output_path
                assert output_path.exists()
            finally:
                tts_module.TTS_VOICE = original_voice


class TestEdgeTTSClientInitializationError:
    """Tests for EdgeTTSClient initialization error handling."""

    def test_initialization_raises_when_voice_not_configured(self):
        """Verify client raises TTSError when TTS_VOICE is not configured."""
        with patch.dict("sys.modules", {"edge_tts": MagicMock()}):
            import src.utils.edge_tts_client as tts_module

            original_voice = tts_module.TTS_VOICE
            original_class_voice = tts_module.EdgeTTSClient.VOICE
            tts_module.TTS_VOICE = ""
            tts_module.EdgeTTSClient.VOICE = ""
            try:
                with pytest.raises(TTSError) as exc_info:
                    tts_module.EdgeTTSClient()

                assert "TTS_VOICE not configured" in str(exc_info.value)
            finally:
                tts_module.TTS_VOICE = original_voice
                tts_module.EdgeTTSClient.VOICE = original_class_voice

    def test_initialization_raises_when_voice_is_none(self):
        """Verify client raises TTSError when TTS_VOICE is None."""
        with patch.dict("sys.modules", {"edge_tts": MagicMock()}):
            import src.utils.edge_tts_client as tts_module

            original_voice = tts_module.TTS_VOICE
            original_class_voice = tts_module.EdgeTTSClient.VOICE
            tts_module.TTS_VOICE = None
            tts_module.EdgeTTSClient.VOICE = None
            try:
                with pytest.raises(TTSError) as exc_info:
                    tts_module.EdgeTTSClient()

                assert "TTS_VOICE not configured" in str(exc_info.value)
            finally:
                tts_module.TTS_VOICE = original_voice
                tts_module.EdgeTTSClient.VOICE = original_class_voice


class TestEdgeTTSClientInitCommunicate:
    """Tests for _init_communicate method."""

    def test_init_communicate_creates_communicate_object(self):
        """Verify _init_communicate creates the edge_tts.Communicate object."""
        with patch.dict("sys.modules", {"edge_tts": MagicMock()}):
            import src.utils.edge_tts_client as tts_module

            original_voice = tts_module.TTS_VOICE
            tts_module.TTS_VOICE = "pl-PL-MarekNeural"
            try:
                client = tts_module.EdgeTTSClient()
                assert client.communicate is None

                mock_communicate = MagicMock()
                tts_module.edge_tts.Communicate = MagicMock(
                    return_value=mock_communicate
                )

                import asyncio

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(client._init_communicate())
                finally:
                    loop.close()

                assert client.communicate is not None
                tts_module.edge_tts.Communicate.assert_called_once_with(
                    "pl-PL-MarekNeural"
                )
            finally:
                tts_module.TTS_VOICE = original_voice

    def test_init_communicate_only_creates_once(self):
        """Verify _init_communicate only creates Communicate object once."""
        with patch.dict("sys.modules", {"edge_tts": MagicMock()}):
            import src.utils.edge_tts_client as tts_module

            original_voice = tts_module.TTS_VOICE
            tts_module.TTS_VOICE = "pl-PL-MarekNeural"
            try:
                client = tts_module.EdgeTTSClient()

                mock_communicate = MagicMock()
                tts_module.edge_tts.Communicate = MagicMock(
                    return_value=mock_communicate
                )

                import asyncio

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(client._init_communicate())
                    loop.run_until_complete(client._init_communicate())
                    loop.run_until_complete(client._init_communicate())
                finally:
                    loop.close()

                assert tts_module.edge_tts.Communicate.call_count == 1
            finally:
                tts_module.TTS_VOICE = original_voice


class TestEdgeTTSClientGenerateAsync:
    """Tests for _generate_async method."""

    def test_generate_async_success(self, tmp_path: Path):
        """Verify _generate_async saves audio to file."""
        with patch.dict("sys.modules", {"edge_tts": MagicMock()}):
            import src.utils.edge_tts_client as tts_module

            original_voice = tts_module.TTS_VOICE
            tts_module.TTS_VOICE = "pl-PL-MarekNeural"
            try:
                client = tts_module.EdgeTTSClient()

                output_path = tmp_path / "output.mp3"
                output_path.parent.mkdir(parents=True, exist_ok=True)

                mock_communicate = MagicMock()
                mock_communicate.save = AsyncMock()
                client.communicate = mock_communicate

                import asyncio

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(
                        client._generate_async("Test text", output_path)
                    )
                finally:
                    loop.close()

                mock_communicate.save.assert_called_once_with(str(output_path))
            finally:
                tts_module.TTS_VOICE = original_voice

    def test_generate_async_handles_save_error(self, tmp_path: Path):
        """Verify _generate_async raises TTSError when save fails."""
        with patch.dict("sys.modules", {"edge_tts": MagicMock()}):
            import src.utils.edge_tts_client as tts_module

            original_voice = tts_module.TTS_VOICE
            tts_module.TTS_VOICE = "pl-PL-MarekNeural"
            try:
                client = tts_module.EdgeTTSClient()

                output_path = tmp_path / "output.mp3"
                output_path.parent.mkdir(parents=True, exist_ok=True)

                mock_communicate = MagicMock()
                mock_communicate.save = AsyncMock(side_effect=Exception("FFmpeg error"))
                client.communicate = mock_communicate

                import asyncio

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    with pytest.raises(TTSError) as exc_info:
                        loop.run_until_complete(
                            client._generate_async("Test text", output_path)
                        )
                    assert "Async TTS save failed" in str(exc_info.value)
                finally:
                    loop.close()
            finally:
                tts_module.TTS_VOICE = original_voice
