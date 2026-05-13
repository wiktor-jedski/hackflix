"""Tests for media duration probing."""

import subprocess
from unittest.mock import MagicMock

from src.utils.media_duration import probe_duration_seconds


def test_probe_duration_seconds_returns_rounded_value(mocker) -> None:
    """Test ffprobe JSON duration is rounded to seconds."""
    mocker.patch(
        "src.utils.media_duration.subprocess.run",
        return_value=MagicMock(stdout='{"format": {"duration": "125.6"}}'),
    )

    assert probe_duration_seconds("/tmp/movie.mkv") == 126


def test_probe_duration_seconds_returns_zero_on_failure(mocker) -> None:
    """Test ffprobe failures produce an unavailable duration."""
    mocker.patch(
        "src.utils.media_duration.subprocess.run",
        side_effect=subprocess.TimeoutExpired("ffprobe", 10),
    )

    assert probe_duration_seconds("/tmp/movie.mkv") == 0
