"""
Subtitle parser utility for SRT format handling.

Provides parsing and writing functionality for SubRip subtitle files,
including sound effect detection and timestamp conversion.
"""

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class SubtitleLine:
    """Represents a single line in a subtitle file.

    Attributes:
        index: The sequential number of the subtitle line.
        start_ms: Start time in milliseconds.
        end_ms: End time in milliseconds.
        text_source: Original subtitle text.
        text_translated: Translated text (filled after translation).
        audio_clip_path: Path to generated TTS audio clip (filled after TTS).
        is_sound_effect: True if line is a sound effect description.
    """

    index: int
    start_ms: int
    end_ms: int
    text_source: str
    text_translated: str = ""
    audio_clip_path: str = ""
    is_sound_effect: bool = False


class SubtitleParseError(Exception):
    """Raised when subtitle file cannot be parsed."""

    pass


def _parse_timestamp(timestamp: str) -> int:
    """Convert SRT timestamp format to milliseconds.

    Args:
        timestamp: Timestamp in format "HH:MM:SS,mmm"

    Returns:
        Time in milliseconds.

    Raises:
        SubtitleParseError: If timestamp format is invalid.
    """
    pattern = r"(\d{2}):(\d{2}):(\d{2}),(\d{3})"
    match = re.match(pattern, timestamp)
    if not match:
        raise SubtitleParseError(f"Invalid timestamp format: {timestamp}")

    hours, minutes, seconds, milliseconds = map(int, match.groups())
    total_ms = (hours * 3600 + minutes * 60 + seconds) * 1000 + milliseconds
    return total_ms


def _format_timestamp(ms: int) -> str:
    """Convert milliseconds to SRT timestamp format.

    Args:
        milliseconds: Time in milliseconds.

    Returns:
        Timestamp in format "HH:MM:SS,mmm"
    """
    hours = ms // (3600 * 1000)
    ms_remaining = ms % (3600 * 1000)
    minutes = ms_remaining // (60 * 1000)
    ms_remaining = ms_remaining % (60 * 1000)
    seconds = ms_remaining // 1000
    milliseconds = ms_remaining % 1000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def _is_sound_effect(text: str) -> bool:
    """Check if text is a sound effect description.

    Sound effects are enclosed in square brackets [...] or parentheses (...).

    Args:
        text: Subtitle text to check.

    Returns:
        True if text is a sound effect pattern.
    """
    stripped = text.strip()
    return (stripped.startswith("[") and stripped.endswith("]")) or (
        stripped.startswith("(") and stripped.endswith(")")
    )


def parse_srt_file(path: Path) -> list[SubtitleLine]:
    """Parse an SRT subtitle file into a list of SubtitleLine objects.

    Args:
        path: Path to the SRT file.

    Returns:
        List of SubtitleLine objects in order.

    Raises:
        FileNotFoundError: If the file does not exist.
        SubtitleParseError: If the file cannot be parsed.
    """
    if not path.exists():
        raise FileNotFoundError(f"Subtitle file not found: {path}")

    content = path.read_text(encoding="utf-8")
    lines = content.split("\n")
    subtitles: list[SubtitleLine] = []

    i = 0
    line_count = len(lines)

    while i < line_count:
        line = lines[i].strip()

        if not line:
            i += 1
            continue

        if not line.isdigit():
            i += 1
            continue

        try:
            index = int(line)
        except ValueError:
            i += 1
            continue

        if i + 1 >= line_count:
            raise SubtitleParseError(f"Unexpected end of file at line {i + 1}")

        timestamp_line = lines[i + 1].strip()
        timestamp_pattern = r"(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})"
        match = re.match(timestamp_pattern, timestamp_line)

        if not match:
            raise SubtitleParseError(
                f"Invalid timestamp line at line {i + 2}: {timestamp_line}"
            )

        start_timestamp, end_timestamp = match.groups()
        start_ms = _parse_timestamp(start_timestamp)
        end_ms = _parse_timestamp(end_timestamp)

        text_lines: list[str] = []
        j = i + 2

        while j < line_count:
            text_line = lines[j]
            if not text_line.strip():
                break
            text_lines.append(text_line.rstrip("\r"))
            j += 1

        text = "\n".join(text_lines)
        is_effect = _is_sound_effect(text)

        subtitles.append(
            SubtitleLine(
                index=index,
                start_ms=start_ms,
                end_ms=end_ms,
                text_source=text,
                is_sound_effect=is_effect,
            )
        )

        i = j

    return subtitles


def write_srt_file(path: Path, subtitle_lines: list[SubtitleLine]) -> None:
    """Write SubtitleLine objects to an SRT file.

    Args:
        path: Output path for the SRT file.
        subtitle_lines: List of SubtitleLine objects to write.
    """
    lines: list[str] = []

    for sub in subtitle_lines:
        text = sub.text_translated if sub.text_translated else sub.text_source

        start_str = _format_timestamp(sub.start_ms)
        end_str = _format_timestamp(sub.end_ms)

        lines.append(str(sub.index))
        lines.append(f"{start_str} --> {end_str}")
        lines.append(text)
        lines.append("")

    content = "\n".join(lines)
    path.write_text(content, encoding="utf-8")
