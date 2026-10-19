"""Shared fixtures. Isolate the firm database so tests never touch the live file."""

from __future__ import annotations

import os

import pytest

# The observers snapshot is built off the request path. Tests that want a
# build call refresh() or seed() themselves so the suite does not walk the
# scan files in a background thread.
os.environ["OBSERVER_SNAPSHOTS_AUTOSTART"] = "0"

from config.settings import get_settings
from core.db import get_engine, get_session_factory, init_db


@pytest.fixture
def firm_db(tmp_path, monkeypatch):
    """Point the app at a throwaway SQLite file for the duration of a test."""
    db_path = tmp_path / "firm_test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    init_db()
    yield db_path
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    get_settings.cache_clear()
