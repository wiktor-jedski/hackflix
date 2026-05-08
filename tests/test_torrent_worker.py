"""Tests for the headless torrent worker helpers."""

from __future__ import annotations

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
