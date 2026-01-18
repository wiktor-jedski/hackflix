"""Tests for Gemini API translation client.

Tests cover:
- Successful batch translation
- JSON structure preservation
- Line count validation
- Sound effect preservation
- Network/retry logic
- Rate limit handling
- Batch size enforcement
- Progress tracking
- Invalid JSON response
"""

import json
import pytest
from unittest.mock import MagicMock, patch

from src.utils.gemini_client import (
    GeminiTranslator,
    GeminiTranslationError,
)
from src.utils.subtitle_parser import SubtitleLine


class TestGeminiTranslatorInitialization:
    """Tests for GeminiTranslator initialization."""

    def test_initialization_with_valid_api_key(self):
        """Verify translator initializes with valid API key."""
        with patch("src.utils.gemini_client.GEMINI_API_KEY", "test-key"):
            with patch("src.utils.gemini_client.genai.configure"):
                translator = GeminiTranslator()
                assert translator.api_key == "test-key"

    def test_initialization_without_api_key(self):
        """Verify error when API key is not configured."""
        with patch("src.utils.gemini_client.GEMINI_API_KEY", ""):
            with pytest.raises(GeminiTranslationError) as exc_info:
                GeminiTranslator()
            assert "not configured" in str(exc_info.value)

    def test_system_prompt_contains_requirements(self):
        """Verify system prompt contains translation requirements."""
        prompt = GeminiTranslator.SYSTEM_PROMPT
        assert "English to Polish" in prompt
        assert "Preserve the original meaning" in prompt
        assert "sound effect" in prompt.lower()
        assert "JSON" in prompt


class TestTranslateBatch:
    """Tests for translate_batch method."""

    def test_translate_empty_batch(self):
        """Verify empty batch returns empty list."""
        with patch("src.utils.gemini_client.GEMINI_API_KEY", "test-key"):
            with patch("src.utils.gemini_client.genai.configure"):
                translator = GeminiTranslator()
                result = translator.translate_batch([])
                assert result == []

    def test_translate_single_line(self):
        """Verify translation of single subtitle line."""
        with patch("src.utils.gemini_client.GEMINI_API_KEY", "test-key"):
            with patch("src.utils.gemini_client.genai.configure"):
                translator = GeminiTranslator()

                subtitles = [
                    SubtitleLine(
                        index=1, start_ms=0, end_ms=2000, text_source="Hello world"
                    )
                ]

                mock_response = MagicMock()
                mock_response.text = json.dumps(
                    {"translations": [{"index": 1, "text": "Witaj świecie"}]}
                )

                with patch.object(
                    translator.model, "generate_content", return_value=mock_response
                ):
                    result = translator.translate_batch(subtitles)

                assert len(result) == 1
                assert result[0].text_translated == "Witaj świecie"

    def test_translate_batch_preserves_line_count(self):
        """Verify translation preserves subtitle line count."""
        with patch("src.utils.gemini_client.GEMINI_API_KEY", "test-key"):
            with patch("src.utils.gemini_client.genai.configure"):
                translator = GeminiTranslator()

                subtitles = [
                    SubtitleLine(index=1, start_ms=0, end_ms=2000, text_source="First"),
                    SubtitleLine(
                        index=2, start_ms=2000, end_ms=4000, text_source="Second"
                    ),
                    SubtitleLine(
                        index=3, start_ms=4000, end_ms=6000, text_source="Third"
                    ),
                ]

                mock_response = MagicMock()
                mock_response.text = json.dumps(
                    {
                        "translations": [
                            {"index": 1, "text": "Pierwszy"},
                            {"index": 2, "text": "Drugi"},
                            {"index": 3, "text": "Trzeci"},
                        ]
                    }
                )

                with patch.object(
                    translator.model, "generate_content", return_value=mock_response
                ):
                    result = translator.translate_batch(subtitles)

                assert len(result) == 3

    def test_translate_batch_resumes_from_start_batch(self):
        """Verify translation resumes from specified batch."""
        with patch("src.utils.gemini_client.GEMINI_API_KEY", "test-key"):
            with patch("src.utils.gemini_client.TRANSLATION_BATCH_SIZE", 2):
                with patch("src.utils.gemini_client.genai.configure"):
                    translator = GeminiTranslator()

                    subtitles = [
                        SubtitleLine(
                            index=1, start_ms=0, end_ms=2000, text_source="First"
                        ),
                        SubtitleLine(
                            index=2, start_ms=2000, end_ms=4000, text_source="Second"
                        ),
                        SubtitleLine(
                            index=3, start_ms=4000, end_ms=6000, text_source="Third"
                        ),
                        SubtitleLine(
                            index=4, start_ms=6000, end_ms=8000, text_source="Fourth"
                        ),
                    ]

                    mock_response = MagicMock()
                    mock_response.text = json.dumps(
                        {
                            "translations": [
                                {"index": 3, "text": "Trzeci"},
                                {"index": 4, "text": "Czwarty"},
                            ]
                        }
                    )

                    with patch.object(
                        translator.model, "generate_content", return_value=mock_response
                    ):
                        result = translator.translate_batch(subtitles, start_batch=1)

                    assert len(result) == 2
                    assert result[0].index == 3
                    assert result[1].index == 4

    def test_translate_batch_with_sound_effects(self):
        """Verify sound effects are preserved in translation."""
        with patch("src.utils.gemini_client.GEMINI_API_KEY", "test-key"):
            with patch("src.utils.gemini_client.genai.configure"):
                translator = GeminiTranslator()

                subtitles = [
                    SubtitleLine(
                        index=1,
                        start_ms=0,
                        end_ms=2000,
                        text_source="[Door slams]",
                        is_sound_effect=True,
                    ),
                    SubtitleLine(
                        index=2, start_ms=2000, end_ms=4000, text_source="Hello"
                    ),
                ]

                mock_response = MagicMock()
                mock_response.text = json.dumps(
                    {
                        "translations": [
                            {"index": 1, "text": "[Door slams]"},
                            {"index": 2, "text": "Cześć"},
                        ]
                    }
                )

                with patch.object(
                    translator.model, "generate_content", return_value=mock_response
                ):
                    result = translator.translate_batch(subtitles)

                assert result[0].text_translated == "[Door slams]"
                assert result[1].text_translated == "Cześć"

    def test_translate_handles_markdown_code_blocks(self):
        """Verify response with markdown code blocks is parsed correctly."""
        with patch("src.utils.gemini_client.GEMINI_API_KEY", "test-key"):
            with patch("src.utils.gemini_client.genai.configure"):
                translator = GeminiTranslator()

                subtitles = [
                    SubtitleLine(index=1, start_ms=0, end_ms=2000, text_source="Hello")
                ]

                mock_response = MagicMock()
                mock_response.text = """```json
{
    "translations": [
        {"index": 1, "text": "Witaj"}
    ]
}
```"""

                with patch.object(
                    translator.model, "generate_content", return_value=mock_response
                ):
                    result = translator.translate_batch(subtitles)

                assert result[0].text_translated == "Witaj"

    def test_translate_fallback_on_missing_translation(self):
        """Verify original text used when translation missing."""
        with patch("src.utils.gemini_client.GEMINI_API_KEY", "test-key"):
            with patch("src.utils.gemini_client.genai.configure"):
                translator = GeminiTranslator()

                subtitles = [
                    SubtitleLine(index=1, start_ms=0, end_ms=2000, text_source="Hello"),
                    SubtitleLine(
                        index=2, start_ms=2000, end_ms=4000, text_source="World"
                    ),
                ]

                mock_response = MagicMock()
                mock_response.text = json.dumps(
                    {"translations": [{"index": 1, "text": "Cześć"}]}
                )

                with patch.object(
                    translator.model, "generate_content", return_value=mock_response
                ):
                    result = translator.translate_batch(subtitles)

                assert result[0].text_translated == "Cześć"
                assert result[1].text_translated == "World"


class TestBuildTranslationPrompt:
    """Tests for _build_translation_prompt method."""

    def test_prompt_contains_batch_info(self):
        """Verify prompt contains batch number and total."""
        with patch("src.utils.gemini_client.GEMINI_API_KEY", "test-key"):
            with patch("src.utils.gemini_client.genai.configure"):
                translator = GeminiTranslator()

                subtitles = [
                    SubtitleLine(index=1, start_ms=0, end_ms=2000, text_source="Test")
                ]

                prompt = translator._build_translation_prompt(subtitles, 1, 3)

                assert "Batch 1 of total batches" in prompt
                assert "1 subtitle" in prompt
                assert "Test" in prompt

    def test_prompt_contains_subtitle_details(self):
        """Verify prompt contains subtitle index and timestamps."""
        with patch("src.utils.gemini_client.GEMINI_API_KEY", "test-key"):
            with patch("src.utils.gemini_client.genai.configure"):
                translator = GeminiTranslator()

                subtitles = [
                    SubtitleLine(
                        index=42, start_ms=5000, end_ms=7000, text_source="Hello"
                    )
                ]

                prompt = translator._build_translation_prompt(subtitles, 1, 1)

                assert "Index: 42" in prompt
                assert "5000ms" in prompt
                assert "7000ms" in prompt


class TestTranslateSingleBatch:
    """Tests for _translate_single_batch method."""

    def test_invalid_json_response(self):
        """Verify error on invalid JSON response."""
        with patch("src.utils.gemini_client.GEMINI_API_KEY", "test-key"):
            with patch("src.utils.gemini_client.genai.configure"):
                translator = GeminiTranslator()

                subtitles = [
                    SubtitleLine(index=1, start_ms=0, end_ms=2000, text_source="Test")
                ]

                mock_response = MagicMock()
                mock_response.text = "invalid json {"

                with patch.object(
                    translator.model, "generate_content", return_value=mock_response
                ):
                    with pytest.raises(GeminiTranslationError) as exc_info:
                        translator._translate_single_batch(subtitles, 1, 1)

                    assert "Invalid JSON" in str(exc_info.value)

    def test_missing_translations_key(self):
        """Verify handling when translations key is missing."""
        with patch("src.utils.gemini_client.GEMINI_API_KEY", "test-key"):
            with patch("src.utils.gemini_client.genai.configure"):
                translator = GeminiTranslator()

                subtitles = [
                    SubtitleLine(index=1, start_ms=0, end_ms=2000, text_source="Test")
                ]

                mock_response = MagicMock()
                mock_response.text = json.dumps({"other_key": "value"})

                with patch.object(
                    translator.model, "generate_content", return_value=mock_response
                ):
                    result = translator._translate_single_batch(subtitles, 1, 1)

                assert result[0].text_translated == "Test"


class TestRateLimitHandling:
    """Tests for rate limit handling."""

    def test_rate_limit_retry_on_429(self):
        """Verify automatic retry on 429 rate limit."""
        with patch("src.utils.gemini_client.GEMINI_API_KEY", "test-key"):
            with patch("src.utils.gemini_client.genai.configure"):
                translator = GeminiTranslator()

                subtitles = [
                    SubtitleLine(index=1, start_ms=0, end_ms=2000, text_source="Test")
                ]

                mock_429 = MagicMock()
                mock_429.__str__ = MagicMock(return_value="429 Resource exhausted")

                mock_response = MagicMock()
                mock_response.text = json.dumps(
                    {"translations": [{"index": 1, "text": "Test przetłumaczony"}]}
                )

                call_count = [0]

                def mock_generate(*args, **kwargs):
                    call_count[0] += 1
                    if call_count[0] == 1:
                        error = GeminiTranslationError("rate limit exceeded")
                        error._is_rate_limit = True
                        raise error
                    return mock_response

                with patch.object(
                    translator.model, "generate_content", side_effect=mock_generate
                ):
                    with patch("time.sleep"):  # Avoid actual sleep
                        result = translator.translate_batch(subtitles)

                assert call_count[0] == 2
                assert len(result) == 1


class TestGeminiTranslationError:
    """Tests for GeminiTranslationError exception."""

    def test_error_is_exception_subclass(self):
        """Verify GeminiTranslationError is an Exception subclass."""
        error = GeminiTranslationError("Test error")
        assert isinstance(error, Exception)

    def test_error_message(self):
        """Verify error message is preserved."""
        error = GeminiTranslationError("Custom error message")
        assert "Custom error message" in str(error)
