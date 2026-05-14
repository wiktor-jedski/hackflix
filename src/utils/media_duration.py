"""Media duration probing helpers."""

import json
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def probe_duration_seconds(path: str | Path) -> int:
    """Return media duration in seconds using ffprobe, or 0 if unavailable."""
    media_path = Path(path)
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "json",
                str(media_path),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
        data = json.loads(result.stdout)
        duration = float(data.get("format", {}).get("duration") or 0)
        return max(0, round(duration))
    except (
        FileNotFoundError,
        subprocess.SubprocessError,
        json.JSONDecodeError,
        TypeError,
        ValueError,
    ) as e:
        logger.warning("Could not probe media duration for %s: %s", media_path, e)
        return 0
