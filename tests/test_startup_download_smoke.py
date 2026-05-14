"""Real startup smoke test for torrent download creation.

This test is intentionally opt-in because it starts the real application and
uses the real configured torrent catalog/database. Run it on the Pi with:

    RUN_STARTUP_DOWNLOAD_SMOKE=1 uv run pytest tests/test_startup_download_smoke.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest


def _tail_text(path: Path, max_lines: int = 80) -> str:
    """Return the last lines from a text file if it exists."""
    if not path.exists():
        return f"{path} does not exist"

    return "\n".join(path.read_text(errors="replace").splitlines()[-max_lines:])


def _finish_process(process: subprocess.Popen[str]) -> tuple[int | None, str, str]:
    """Terminate the app process and collect buffered output."""
    if process.poll() is None:
        process.terminate()
        try:
            stdout, stderr = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate(timeout=5)
    else:
        stdout, stderr = process.communicate(timeout=5)

    return process.returncode, stdout, stderr


@pytest.mark.skipif(
    os.environ.get("RUN_STARTUP_DOWNLOAD_SMOKE") != "1",
    reason="set RUN_STARTUP_DOWNLOAD_SMOKE=1 to run the real startup smoke test",
)
def test_startup_creates_file_in_movies_within_10_seconds() -> None:
    """Start the app briefly and verify a torrent creates a file in /home/pi/movies."""
    movies_dir = Path("/home/pi/movies")
    movies_dir.mkdir(parents=True, exist_ok=True)
    before = {path for path in movies_dir.rglob("*") if path.is_file()}

    env = os.environ.copy()
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    env.setdefault("HACKFLIX_TORRENT_BACKEND", "process")
    env["MEDIA_LIBRARY_PATH"] = str(movies_dir)

    process = subprocess.Popen(
        [sys.executable, "src/main.py"],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    time.sleep(10)
    after = {path for path in movies_dir.rglob("*") if path.is_file()}
    created = after - before
    exited_early = process.poll() is not None
    returncode, stdout, stderr = _finish_process(process)

    diagnostics = (
        f"returncode={returncode}\n"
        f"created={[str(path) for path in sorted(created)]}\n"
        f"stdout tail:\n{stdout[-4000:]}\n"
        f"stderr tail:\n{stderr[-4000:]}\n"
        f"app.log tail:\n{_tail_text(Path('/home/pi/.config/hackflix/logs/app.log'))}\n"
        f"error.log tail:\n{_tail_text(Path('error.log'))}"
    )
    assert not exited_early, f"app exited before the 10 second smoke window\n{diagnostics}"
    assert created, f"no files appeared in /home/pi/movies after 10 seconds\n{diagnostics}"
