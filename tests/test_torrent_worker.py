"""Tests for the headless torrent worker helpers."""

from __future__ import annotations

import importlib
import sys
from unittest import mock

import pytest

from src.services import torrent_worker


def test_get_listen_interfaces_uses_env_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Configured listen interfaces take precedence."""
    monkeypatch.setenv("HACKFLIX_TORRENT_LISTEN_INTERFACES", "192.168.1.10:6881")

    assert torrent_worker.get_listen_interfaces() == "192.168.1.10:6881"


def test_get_listen_interfaces_uses_detected_routable_ip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A routable local IP is bound explicitly."""
    monkeypatch.delenv("HACKFLIX_TORRENT_LISTEN_INTERFACES", raising=False)
    socket_instance = mock.MagicMock()
    socket_instance.getsockname.return_value = ("192.168.0.88", 45678)
    socket_context = mock.MagicMock()
    socket_context.__enter__.return_value = socket_instance

    with mock.patch.object(torrent_worker.socket, "socket", return_value=socket_context):
        assert torrent_worker.get_listen_interfaces() == "192.168.0.88:6881"


def test_get_listen_interfaces_falls_back_for_loopback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Loopback detection falls back to libtorrent's wildcard binding."""
    monkeypatch.delenv("HACKFLIX_TORRENT_LISTEN_INTERFACES", raising=False)
    socket_instance = mock.MagicMock()
    socket_instance.getsockname.return_value = ("127.0.0.1", 45678)
    socket_context = mock.MagicMock()
    socket_context.__enter__.return_value = socket_instance

    with mock.patch.object(torrent_worker.socket, "socket", return_value=socket_context):
        assert torrent_worker.get_listen_interfaces() == "0.0.0.0:6881,[::]:6881"


def test_get_listen_interfaces_falls_back_on_probe_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Network probe failures fall back to libtorrent's wildcard binding."""
    monkeypatch.delenv("HACKFLIX_TORRENT_LISTEN_INTERFACES", raising=False)

    with mock.patch.object(torrent_worker.socket, "socket", side_effect=OSError):
        assert torrent_worker.get_listen_interfaces() == "0.0.0.0:6881,[::]:6881"


def test_get_video_files_returns_video_paths(tmp_path) -> None:
    """Video file metadata is exported for process-backend season matching."""
    handle = mock.MagicMock()
    status = mock.MagicMock()
    status.save_path = str(tmp_path)
    handle.status.return_value = status

    files = mock.MagicMock()
    files.num_files.return_value = 3
    files.file_path.side_effect = ["readme.txt", "Show.S01E01.mkv", "Show.S01E02.mp4"]
    files.file_size.side_effect = [1000, 1100]
    torrent_info = mock.MagicMock()
    torrent_info.files.return_value = files
    handle.torrent_file.return_value = torrent_info

    assert torrent_worker.get_video_files(handle) == [
        {"path": str(tmp_path / "Show.S01E01.mkv"), "size": 1000},
        {"path": str(tmp_path / "Show.S01E02.mp4"), "size": 1100},
    ]


def test_get_video_files_returns_empty_without_torrent_info() -> None:
    """Missing torrent metadata returns no video files."""
    handle = mock.MagicMock()
    handle.torrent_file.return_value = None

    assert torrent_worker.get_video_files(handle) == []


def test_handle_command_processes_multiple_adds() -> None:
    """Verify add commands register distinct movie and season contexts."""
    mock_lt = mock.MagicMock()
    mock_lt.torrent_status.states.checking_files = 0
    mock_lt.torrent_status.states.downloading_metadata = 1
    mock_lt.torrent_status.states.downloading = 2
    mock_lt.torrent_status.states.finished = 3
    mock_lt.torrent_status.states.seeding = 4
    mock_lt.torrent_status.states.allocating = 5
    mock_lt.torrent_status.states.checking_resume_data = 6

    modules_to_remove = [
        module_name
        for module_name in sys.modules
        if module_name == "src.services.torrent_worker" or "libtorrent" in module_name
    ]
    for module_name in modules_to_remove:
        del sys.modules[module_name]

    with mock.patch.dict("sys.modules", {"libtorrent": mock_lt}):
        torrent_worker = importlib.import_module("src.services.torrent_worker")

    session = mock.MagicMock()
    movie_handle = mock.MagicMock()
    movie_handle.info_hash.return_value = "movie_hash"
    season_handle = mock.MagicMock()
    season_handle.info_hash.return_value = "season_hash"
    session.add_torrent.side_effect = [movie_handle, season_handle]
    handles: dict[int, object] = {}
    handle_to_context: dict[str, int] = {}
    contexts: dict[int, str] = {}

    keep_running = torrent_worker.handle_command(
        {
            "command": "add",
            "type": "movie",
            "id": 16,
            "magnet": "magnet:?movie",
            "download_dir": "/downloads",
        },
        session,
        handles,
        handle_to_context,
        contexts,
    )
    keep_running = torrent_worker.handle_command(
        {
            "command": "add",
            "type": "season",
            "id": -1,
            "magnet": "magnet:?season",
            "download_dir": "/downloads",
        },
        session,
        handles,
        handle_to_context,
        contexts,
    )

    assert keep_running is True
    assert handles == {16: movie_handle, -1: season_handle}
    assert handle_to_context == {"movie_hash": 16, "season_hash": -1}
    assert contexts == {16: "movie", -1: "season"}


def test_handle_command_cancel_deletes_payload_files(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cancel commands can request libtorrent payload file deletion."""
    session = mock.MagicMock()
    handle = mock.MagicMock()
    handle.info_hash.return_value = "movie_hash"
    handles: dict[int, object] = {16: handle}
    handle_to_context = {"movie_hash": 16}
    contexts = {16: "movie"}
    mock_lt = mock.MagicMock()
    mock_lt.options_t.delete_files = "delete-files"

    monkeypatch.setattr(torrent_worker, "lt", mock_lt)

    keep_running = torrent_worker.handle_command(
        {"command": "cancel", "id": 16, "delete_files": True},
        session,
        handles,
        handle_to_context,
        contexts,
    )

    assert keep_running is True
    assert handles == {}
    assert handle_to_context == {}
    assert contexts == {}
    session.remove_torrent.assert_called_once_with(handle, "delete-files")


def test_remove_torrent_without_delete_files_uses_default_remove() -> None:
    """Default torrent removal keeps payload files."""
    session = mock.MagicMock()
    handle = mock.MagicMock()

    torrent_worker.remove_torrent(session, handle)

    session.remove_torrent.assert_called_once_with(handle)
