"""Headless libtorrent worker process.

This module is intentionally separate from the PySide GUI process. The
libtorrent Python extension can crash the interpreter on Raspberry Pi/aarch64;
running it here keeps that native failure isolated from the application UI.
"""

from __future__ import annotations

import json
import os
import select
import socket
import sys
import time
from pathlib import Path
from typing import Any, cast

import libtorrent as _libtorrent

lt = cast(Any, _libtorrent)

VIDEO_EXTENSIONS = frozenset({".mkv", ".mp4", ".avi", ".webm", ".mov", ".wmv", ".flv"})

STATE_NAMES = {
    int(lt.torrent_status.states.checking_files): "checking_files",
    int(lt.torrent_status.states.downloading_metadata): "downloading_metadata",
    int(lt.torrent_status.states.downloading): "downloading",
    int(lt.torrent_status.states.finished): "finished",
    int(lt.torrent_status.states.seeding): "seeding",
    int(lt.torrent_status.states.allocating): "allocating",
    int(lt.torrent_status.states.checking_resume_data): "checking_resume_data",
}


def get_listen_interfaces() -> str:
    """Choose a routable listen address for libtorrent."""
    configured = os.environ.get("HACKFLIX_TORRENT_LISTEN_INTERFACES")
    if configured:
        return configured

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("1.1.1.1", 80))
            local_ip = probe.getsockname()[0]
    except OSError:
        return "0.0.0.0:6881,[::]:6881"

    if local_ip.startswith("127."):
        return "0.0.0.0:6881,[::]:6881"
    return f"{local_ip}:6881"


def emit(event: dict[str, Any]) -> None:
    """Write one JSON event to stdout."""
    print(json.dumps(event), flush=True)


def find_largest_video(handle: Any) -> str | None:
    """Find the largest video file in a completed torrent."""
    torrent_info = handle.torrent_file()
    if not torrent_info:
        return None

    save_path = Path(handle.status().save_path)
    largest_video: tuple[Path | None, int] = (None, 0)
    files = torrent_info.files()
    for i in range(files.num_files()):
        file_path = save_path / files.file_path(i)
        file_size = files.file_size(i)
        if file_path.suffix.lower() in VIDEO_EXTENSIONS and file_size > largest_video[1]:
            largest_video = (file_path, file_size)

    return str(largest_video[0]) if largest_video[0] else None


def get_video_files(handle: Any) -> list[dict[str, Any]]:
    """Return video files from a completed torrent."""
    torrent_info = handle.torrent_file()
    if not torrent_info:
        return []

    save_path = Path(handle.status().save_path)
    video_files: list[dict[str, Any]] = []
    files = torrent_info.files()
    for i in range(files.num_files()):
        file_path = save_path / files.file_path(i)
        if file_path.suffix.lower() in VIDEO_EXTENSIONS:
            video_files.append(
                {
                    "path": str(file_path),
                    "size": files.file_size(i),
                }
            )

    return video_files


def remove_torrent(session: Any, handle: Any, delete_files: bool = False) -> None:
    """Remove a torrent, optionally deleting downloaded payload files."""
    if delete_files:
        session.remove_torrent(handle, lt.options_t.delete_files)
        return

    session.remove_torrent(handle)


def handle_command(
    command: dict[str, Any],
    session: Any,
    handles: dict[int, Any],
    handle_to_context: dict[str, int],
    contexts: dict[int, str],
) -> bool:
    """Handle one command from the parent process.

    Returns:
        True to keep running, False to stop the worker.
    """
    command_name = command.get("command")

    if command_name == "stop":
        return False

    if command_name == "add":
        context_id = int(command["id"])
        if context_id in handles:
            emit(
                {
                    "event": "error",
                    "id": context_id,
                    "message": "Torrent already exists",
                }
            )
            return True
        try:
            atp = lt.parse_magnet_uri(command["magnet"])
            atp.save_path = command["download_dir"]
            handle = session.add_torrent(atp)
            if command.get("sequential"):
                handle.set_sequential_download(True)
            handles[context_id] = handle
            handle_to_context[str(handle.info_hash())] = context_id
            contexts[context_id] = command["type"]
            emit({"event": "added", "id": context_id})
        except Exception as e:
            emit({"event": "error", "id": context_id, "message": str(e)})

    if command_name == "cancel":
        context_id = int(command["id"])
        handle = handles.pop(context_id, None)
        contexts.pop(context_id, None)
        if handle is not None:
            handle_to_context.pop(str(handle.info_hash()), None)
            remove_torrent(session, handle, bool(command.get("delete_files", False)))

    return True


def main() -> int:
    """Run the worker command loop."""
    listen_interfaces = get_listen_interfaces()
    session = lt.session(
        {
            "user_agent": "Hackflix/1.0",
            "listen_interfaces": listen_interfaces,
            "enable_dht": True,
            "enable_lsd": True,
            "enable_upnp": True,
            "enable_natpmp": True,
            "announce_to_all_trackers": True,
            "announce_to_all_tiers": True,
            "alert_mask": (
                lt.alert.category_t.error_notification
                | lt.alert.category_t.status_notification
                | lt.alert.category_t.storage_notification
            ),
        }
    )
    handles: dict[int, Any] = {}
    handle_to_context: dict[str, int] = {}
    contexts: dict[int, str] = {}
    stdin_fd = sys.stdin.fileno()
    os.set_blocking(stdin_fd, False)
    command_buffer = ""

    emit({"event": "ready", "listen_interfaces": listen_interfaces})

    while True:
        readable, _, _ = select.select([stdin_fd], [], [], 0.5)
        if readable:
            try:
                chunk = os.read(stdin_fd, 65536)
            except BlockingIOError:
                chunk = b""
            if not chunk:
                return 0
            command_buffer += chunk.decode()
            while "\n" in command_buffer:
                line, command_buffer = command_buffer.split("\n", 1)
                if not line:
                    continue
                command = json.loads(line)
                if not handle_command(
                    command, session, handles, handle_to_context, contexts
                ):
                    return 0

        for alert in session.pop_alerts():
            if isinstance(alert, lt.torrent_error_alert):
                context_id = handle_to_context.get(str(alert.handle.info_hash()))
                if context_id is not None:
                    emit(
                        {
                            "event": "error",
                            "id": context_id,
                            "message": str(alert.error.message()),
                        }
                    )
                    handles.pop(context_id, None)
                    contexts.pop(context_id, None)
                    handle_to_context.pop(str(alert.handle.info_hash()), None)
            elif isinstance(alert, lt.tracker_error_alert):
                context_id = handle_to_context.get(str(alert.handle.info_hash()))
                if context_id is not None:
                    emit(
                        {
                            "event": "tracker_error",
                            "id": context_id,
                            "url": alert.url,
                            "message": str(alert.error.message()),
                        }
                    )
            elif isinstance(alert, lt.metadata_received_alert):
                context_id = handle_to_context.get(str(alert.handle.info_hash()))
                if context_id is not None:
                    emit({"event": "metadata_received", "id": context_id})

        for context_id, handle in list(handles.items()):
            if not handle.is_valid():
                continue

            status = handle.status()
            progress = int(status.progress * 100)
            if status.state == lt.torrent_status.states.seeding:
                context_type = contexts.get(context_id)
                if context_type == "movie":
                    video_path = find_largest_video(handle)
                    if video_path:
                        emit({"event": "completed", "id": context_id, "path": video_path})
                    else:
                        emit(
                            {
                                "event": "error",
                                "id": context_id,
                                "message": "No video file found in torrent",
                            }
                        )
                else:
                    emit(
                        {
                            "event": "season_completed",
                            "id": context_id,
                            "files": get_video_files(handle),
                        }
                    )

                session.remove_torrent(handle)
                handles.pop(context_id, None)
                contexts.pop(context_id, None)
                handle_to_context.pop(str(handle.info_hash()), None)
            elif status.state in (
                lt.torrent_status.states.downloading,
                lt.torrent_status.states.downloading_metadata,
                lt.torrent_status.states.checking_files,
                lt.torrent_status.states.checking_resume_data,
            ):
                emit(
                    {
                        "event": "progress",
                        "id": context_id,
                        "progress": progress,
                        "download_rate": status.download_rate / 1024,
                        "upload_rate": status.upload_rate / 1024,
                        "peers": status.num_peers,
                        "seeds": status.num_seeds,
                        "state": STATE_NAMES.get(int(status.state), str(status.state)),
                        "has_metadata": status.has_metadata,
                        "total_wanted_done": status.total_wanted_done,
                        "total_wanted": status.total_wanted,
                    }
                )

        time.sleep(0.1)


if __name__ == "__main__":
    raise SystemExit(main())
