"""API_MEMDEBUG is off unless an operator turns it on.

These tests do not start the server. They check the guard in
``scripts/run_api.py``: unset leaves tracemalloc and SIGUSR1 alone; the
armed hook writes a bounded snapshot directory.
"""

from __future__ import annotations

import logging
import signal
import tracemalloc

from scripts.run_api import dump_memdebug, install_memdebug, memdebug_enabled, uninstall_memdebug


def test_memdebug_is_off_when_the_env_var_is_unset(monkeypatch) -> None:
    """Unset API_MEMDEBUG does not start tracemalloc or install a handler."""
    monkeypatch.delenv("API_MEMDEBUG", raising=False)
    monkeypatch.delenv("API_MEMDEBUG_DIR", raising=False)
    tracing = tracemalloc.is_tracing()
    handler = signal.getsignal(signal.SIGUSR1)
    assert memdebug_enabled() is False
    assert install_memdebug() is False
    assert tracemalloc.is_tracing() is tracing
    assert signal.getsignal(signal.SIGUSR1) is handler
    assert dump_memdebug() is None


def test_memdebug_writes_a_bounded_snapshot_dir(tmp_path, monkeypatch, caplog) -> None:
    """SIGUSR1's writer keeps only the last few files and logs the path."""
    monkeypatch.setenv("API_MEMDEBUG", "1")
    monkeypatch.setenv("API_MEMDEBUG_DIR", str(tmp_path))
    try:
        with caplog.at_level(logging.INFO, logger="scripts.run_api"):
            assert install_memdebug() is True
            assert tracemalloc.is_tracing() is True
            handler = signal.getsignal(signal.SIGUSR1)
            assert handler is not signal.SIG_DFL
            handler(signal.SIGUSR1, None)
            written = dump_memdebug()
        assert written is not None
        snap_path, diff_path = written
        assert snap_path.exists()
        assert diff_path.exists()
        assert snap_path.name in caplog.text
        text = diff_path.read_text(encoding="utf-8")
        assert "top differences" in text or "top allocations" in text
        for _ in range(4):
            dump_memdebug()
        files = sorted(path.name for path in tmp_path.glob("tracemalloc-*"))
        # Each dump writes a snapshot and a diff. Three pairs remain.
        assert len(files) == 6
        assert files == sorted(files)
    finally:
        uninstall_memdebug()
        assert tracemalloc.is_tracing() is False
