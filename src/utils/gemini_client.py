"""Gemini API client for subtitle translation.

Provides batch translation of subtitle lines using Google's Gemini API
with support for resumable processing and progress tracking.
"""

import json
import logging

from google import genai
from google.genai import types

from src.config import GEMINI_API_KEY, TRANSLATION_BATCH_SIZE

logger = logging.getLogger(__name__)


class GeminiTranslationError(Exception):
    """Raised when Gemini translation operations fail."""

    pass


class GeminiTranslator:
    """Client for Gemini API subtitle translation."""

    SYSTEM_PROMPT = """You are a professional subtitle translator. Translate the following subtitles from English to Polish while:

1. Preserve the original meaning and tone
2. Keep subtitle timing markers unchanged
3. Preserve sound effect markers like [Sound effect] or (Parenthesized text)
4. Maintain appropriate line breaks within subtitle entries
5. Use natural, conversational Polish
6. Keep translations concise to fit subtitle timing

Return ONLY a valid JSON object with this structure:
{
    "translations": [
        {"index": 1, "text": "translated text here"},
        {"index": 2, "text": "translated text here"}
    ]
}

Do not include any explanation or markdown formatting."""

    MODEL_NAME = "gemini-1.5-pro"

    def __init__(self) -> None:
        """Initialize the translator with API key from config."""
        self.api_key = GEMINI_API_KEY
        if not self.api_key:
            raise GeminiTranslationError("GEMINI_API_KEY not configured")

        self.client = genai.Client(api_key=self.api_key)

    def translate_batch(
        self,
        subtitle_lines: list,
        start_batch: int = 0,
        video_file_id: int | None = None,
    ) -> list:
        """Translate a batch of subtitle lines.

        Args:
            subtitle_lines: List of SubtitleLine objects to translate.
            start_batch: Batch index to start from (for resume support).
            video_file_id: Optional video file ID for progress tracking.

        Returns:
            List of SubtitleLine objects with translated text.
        """
        if not subtitle_lines:
            return []

        batch_size = TRANSLATION_BATCH_SIZE
        total_batches = (len(subtitle_lines) + batch_size - 1) // batch_size

        all_translated: list = []

        for batch_idx in range(start_batch, total_batches):
            start_idx = batch_idx * batch_size
            end_idx = min(start_idx + batch_size, len(subtitle_lines))
            batch = subtitle_lines[start_idx:end_idx]

            logger.info(
                "Translating batch %d/%d (lines %d-%d)",
                batch_idx + 1,
                total_batches,
                start_idx + 1,
                end_idx,
            )

            try:
                translated_batch = self._translate_single_batch(
                    batch, batch_idx + 1, total_batches
                )
                all_translated.extend(translated_batch)

            except GeminiTranslationError as e:
                if "rate limit" in str(e).lower() or "429" in str(e):
                    logger.warning("Rate limit hit, waiting before retry...")
                    import time

                    for _ in range(60):
                        if hasattr(self, "_should_stop") and self._should_stop:
                            raise GeminiTranslationError("Cancelled")
                        time.sleep(1)
                    translated_batch = self._translate_single_batch(
                        batch, batch_idx + 1, total_batches
                    )
                    all_translated.extend(translated_batch)
                else:
                    raise

        logger.info("Translation complete: %d lines processed", len(all_translated))
        return all_translated

    def _translate_single_batch(
        self,
        batch: list,
        batch_number: int,
        total_batches: int,
    ) -> list:
        """Translate a single batch of subtitles.

        Args:
            batch: List of SubtitleLine objects to translate.
            batch_number: Current batch number (for prompt).
            total_batches: Total number of batches.

        Returns:
            List of SubtitleLine objects with translated text.
        """
        user_prompt = self._build_translation_prompt(batch, batch_number, total_batches)

        try:
            response = self.client.models.generate_content(
                model=self.MODEL_NAME,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=self.SYSTEM_PROMPT,
                    temperature=0.3,
                    max_output_tokens=8192,
                ),
            )

            response_text = response.text
            if response_text is None:
                raise GeminiTranslationError("Empty response from Gemini")

            if response_text.startswith("```"):
                lines = response_text.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines[-1].startswith("```"):
                    lines = lines[:-1]
                response_text = "\n".join(lines)

            response_text = response_text.strip()

            result = json.loads(response_text)

            translations = {
                t["index"]: t["text"] for t in result.get("translations", [])
            }

            for line in batch:
                if line.index in translations:
                    line.text_translated = translations[line.index]
                else:
                    line.text_translated = line.text_source

            return batch

        except json.JSONDecodeError as e:
            logger.error("Failed to parse Gemini response: %s", e)
            logger.debug("Response was: %s", response_text)
            raise GeminiTranslationError(f"Invalid JSON response from Gemini: {e}")

    def _build_translation_prompt(
        self, batch: list, batch_number: int, total_batches: int
    ) -> str:
        """Build the translation prompt for a batch of subtitles.

        Args:
            batch: List of SubtitleLine objects.
            batch_number: Current batch number (for prompt).
            total_batches: Total number of batches.

        Returns:
            Formatted prompt string for Gemini API.
        """
        lines_data = []
        for line in batch:
            lines_data.append(
                f"---BEGIN_SUBTITLE---\n"
                f"Index: {line.index}\n"
                f"Start: {line.start_ms}ms\n"
                f"End: {line.end_ms}ms\n"
                f"Text: {line.text_source}\n"
                f"---END_SUBTITLE---"
            )

        return f"""Translate the following {len(batch)} subtitle entries to Polish.

Batch {batch_number} of total batches.

{"".join(lines_data)}

Translate all subtitles above. Return JSON with translations."""
