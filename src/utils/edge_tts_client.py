"""Edge-TTS client for text-to-speech synthesis.

Provides text-to-speech generation using Microsoft Edge's TTS API
with hardcoded Polish voice configuration.
"""

import asyncio
import logging
from pathlib import Path
from typing import Callable

import edge_tts

from src.config import TTS_VOICE

logger = logging.getLogger(__name__)

# Maximum concurrent TTS requests to avoid overwhelming the API
MAX_CONCURRENT_TTS = 10


class TTSError(Exception):
    """Raised when TTS generation fails."""

    pass


class EdgeTTSClient:
    """Client for Edge Text-to-Speech synthesis."""

    VOICE = TTS_VOICE
    OUTPUT_RATE = 24000

    def __init__(self) -> None:
        """Initialize the TTS client with configured voice."""
        self.voice = self.VOICE
        if not self.voice:
            raise TTSError("TTS_VOICE not configured")

    def generate_tts(self, text: str, output_path: Path) -> Path:
        """Generate TTS audio for the given text.

        Args:
            text: Text to synthesize.
            output_path: Path for the output MP3 file.

        Returns:
            Path to the generated audio file.

        Raises:
            TTSError: On synthesis or file write failure.
        """
        if not text or text.strip() == "":
            raise TTSError("Cannot generate TTS for empty text")

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                loop.run_until_complete(self._generate_async(text, output_path))
            finally:
                loop.close()

            if not output_path.exists() or output_path.stat().st_size == 0:
                raise TTSError(f"TTS generation produced empty file: {output_path}")

            logger.info("Generated TTS audio to %s", output_path)
            return output_path

        except asyncio.TimeoutError as e:
            raise TTSError(f"TTS generation timed out: {e}") from e
        except Exception as e:
            raise TTSError(f"TTS generation failed: {e}") from e

    async def _generate_async(self, text: str, output_path: Path) -> None:
        """Async implementation of TTS generation.

        Args:
            text: Text to synthesize.
            output_path: Path for the output MP3 file.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            communicate = edge_tts.Communicate(text, self.voice)
            await communicate.save(str(output_path))
        except Exception as e:
            raise TTSError(f"Async TTS save failed: {e}")

    def generate_tts_batch(
        self,
        items: list[tuple[str, Path]],
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[tuple[int, Path | None, str | None]]:
        """Generate TTS audio for multiple texts in parallel.

        Args:
            items: List of (text, output_path) tuples.
            progress_callback: Optional callback(completed, total) for progress updates.

        Returns:
            List of (index, output_path or None, error_message or None) tuples.
            On success: (index, path, None). On failure: (index, None, error_message).
        """
        if not items:
            return []

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                results = loop.run_until_complete(
                    self._generate_batch_async(items, progress_callback)
                )
            finally:
                loop.close()

            return results

        except Exception as e:
            logger.error("Batch TTS generation failed: %s", e)
            # Return all items as failed
            return [(i, None, str(e)) for i in range(len(items))]

    async def _generate_batch_async(
        self,
        items: list[tuple[str, Path]],
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[tuple[int, Path | None, str | None]]:
        """Async implementation of batch TTS generation.

        Uses a semaphore to limit concurrent requests.
        """
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_TTS)
        results: list[tuple[int, Path | None, str | None]] = []
        completed_count = 0
        total = len(items)
        lock = asyncio.Lock()

        async def generate_one(index: int, text: str, output_path: Path) -> None:
            nonlocal completed_count

            async with semaphore:
                try:
                    await self._generate_async(text, output_path)

                    if not output_path.exists() or output_path.stat().st_size == 0:
                        async with lock:
                            results.append((index, None, "Empty output file"))
                    else:
                        async with lock:
                            results.append((index, output_path, None))
                            logger.debug("Generated TTS %d/%d: %s", index + 1, total, output_path)
                except Exception as e:
                    async with lock:
                        results.append((index, None, str(e)))
                        logger.warning("TTS failed for item %d: %s", index, e)
                finally:
                    async with lock:
                        completed_count += 1
                        if progress_callback:
                            progress_callback(completed_count, total)

        # Create tasks for all items
        tasks = [
            generate_one(i, text, path)
            for i, (text, path) in enumerate(items)
        ]

        # Run all tasks concurrently
        await asyncio.gather(*tasks)

        return results

    def generate_tts_sync(self, text: str, output_path: Path) -> Path:
        """Synchronous wrapper for TTS generation.

        Args:
            text: Text to synthesize.
            output_path: Path for the output MP3 file.

        Returns:
            Path to the generated audio file.
        """
        return self.generate_tts(text, output_path)

    def text_needs_tts(self, text: str) -> bool:
        """Check if text should be processed by TTS.

        Args:
            text: Text to check.

        Returns:
            False for empty strings, sound effect markers, or "..."
        """
        stripped = text.strip()

        if not stripped:
            return False

        if stripped == "...":
            return False

        if stripped.startswith("[") and stripped.endswith("]"):
            return False

        if stripped.startswith("(") and stripped.endswith(")"):
            return False

        return True
