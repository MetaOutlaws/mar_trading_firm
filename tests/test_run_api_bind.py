"""Dashboard bind host: Docker/Cursor must not stay on loopback-only."""

from __future__ import annotations

from scripts.run_api import bind_host


def test_laptop_keeps_loopback() -> None:
    assert bind_host("127.0.0.1", in_docker=False, in_cursor_agent=False) == "127.0.0.1"


def test_docker_publish_leaves_loopback() -> None:
    assert bind_host("127.0.0.1", in_docker=True, in_cursor_agent=False) == "0.0.0.0"


def test_cursor_agent_leaves_loopback() -> None:
    assert bind_host("127.0.0.1", in_docker=False, in_cursor_agent=True) == "0.0.0.0"


def test_explicit_non_loopback_is_honoured() -> None:
    assert bind_host("10.0.0.8", in_docker=True, in_cursor_agent=True) == "10.0.0.8"
