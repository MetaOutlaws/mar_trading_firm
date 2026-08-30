"""Shared fixtures. Isolate the firm database so tests never touch the live file."""

from __future__ import annotations

import pytest

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
