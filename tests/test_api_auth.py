"""Inbox writes on this machine must not require the halt token."""

from __future__ import annotations

from types import SimpleNamespace

from api.app import _is_loopback


def _request(host: str):
    return SimpleNamespace(client=SimpleNamespace(host=host))


def test_loopback_hosts_are_recognised() -> None:
    assert _is_loopback(_request("127.0.0.1"))
    assert _is_loopback(_request("::1"))
    assert _is_loopback(_request("127.0.0.12"))
    assert _is_loopback(_request("::ffff:127.0.0.1"))


def test_remote_hosts_are_not_loopback() -> None:
    assert not _is_loopback(_request("8.8.8.8"))
    assert not _is_loopback(_request("10.0.0.4"))
    assert not _is_loopback(SimpleNamespace(client=None))
