"""Serve the Employee Floor API and dashboard.

``API_MEMDEBUG`` is off unless the operator sets it. Unset, this process
does not start tracemalloc and does not install a signal handler. Set to
``1`` (or true/yes/on) before a leak investigation: tracemalloc starts, and
``SIGUSR1`` writes a snapshot plus a top-N diff under ``API_MEMDEBUG_DIR``
(default ``data/memdebug``). Only the last few files are kept. This is not
armed on SGP1 unless that env var is set.
"""

from __future__ import annotations

import logging
import os
import signal
import tracemalloc
from datetime import datetime, timezone
from pathlib import Path

import uvicorn

from config.settings import get_settings
from core.db import init_db

logger = logging.getLogger("scripts.run_api")

# Truthy values. Anything else, including unset and empty, leaves the hook off.
_MEMDEBUG_ON = {"1", "true", "yes", "on"}
# Snapshot plus diff text. Three pairs is enough to compare a climb.
_MEMDEBUG_KEEP_FILES = 6
_MEMDEBUG_TOP = 25
_MEMDEBUG_FRAMES = 10

_installed = False
_previous_handler: signal.Handlers | None = None
_previous_snapshot: tracemalloc.Snapshot | None = None
_dump_seq = 0


def memdebug_enabled() -> bool:
    """True only when ``API_MEMDEBUG`` is explicitly turned on."""
    return os.environ.get("API_MEMDEBUG", "").strip().lower() in _MEMDEBUG_ON


def memdebug_dir() -> Path:
    """Where SIGUSR1 writes. ``API_MEMDEBUG_DIR`` overrides the default."""
    raw = os.environ.get("API_MEMDEBUG_DIR", "").strip()
    if raw:
        return Path(raw)
    from config.settings import PROJECT_ROOT

    return Path(PROJECT_ROOT) / "data" / "memdebug"


def install_memdebug() -> bool:
    """Arm tracemalloc and SIGUSR1, or do nothing when the env var is off.

    Returns True only when the hook is installed. A second call does not
    stack handlers. Unset ``API_MEMDEBUG`` does not call ``tracemalloc.start``
    and does not change the current SIGUSR1 handler.
    """
    global _installed, _previous_handler
    if not memdebug_enabled():
        return False
    if _installed:
        return True
    if not hasattr(signal, "SIGUSR1"):
        logger.warning("API_MEMDEBUG is set but SIGUSR1 is not available")
        return False
    tracemalloc.start(_MEMDEBUG_FRAMES)
    _previous_handler = signal.getsignal(signal.SIGUSR1)
    signal.signal(signal.SIGUSR1, _handle_sigusr1)
    _installed = True
    destination = memdebug_dir()
    logger.info(
        "API_MEMDEBUG on. SIGUSR1 writes tracemalloc snapshots under %s",
        destination,
    )
    return True


def uninstall_memdebug() -> None:
    """Tests use this so a later case is not left tracing."""
    global _installed, _previous_handler, _previous_snapshot, _dump_seq
    if _installed and _previous_handler is not None:
        signal.signal(signal.SIGUSR1, _previous_handler)
    _previous_handler = None
    if _installed and tracemalloc.is_tracing():
        tracemalloc.stop()
    _installed = False
    _previous_snapshot = None
    _dump_seq = 0


def _handle_sigusr1(signum: int, frame: object) -> None:
    """SIGUSR1 entry. Failures are logged and do not stop the server."""
    del signum, frame
    try:
        dump_memdebug()
    except Exception:
        logger.exception("API_MEMDEBUG snapshot failed")


def dump_memdebug() -> tuple[Path, Path] | None:
    """Write one snapshot and a top-N lineno diff. No-op if tracing is off."""
    global _previous_snapshot, _dump_seq
    if not tracemalloc.is_tracing():
        logger.warning("API_MEMDEBUG snapshot skipped; tracemalloc is not running")
        return None
    snapshot = tracemalloc.take_snapshot()
    directory = memdebug_dir()
    directory.mkdir(parents=True, exist_ok=True)
    _dump_seq += 1
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    stem = f"tracemalloc-{stamp}-{_dump_seq:04d}"
    snap_path = directory / f"{stem}.tracemalloc"
    diff_path = directory / f"{stem}.txt"
    snapshot.dump(str(snap_path))
    if _previous_snapshot is None:
        stats = snapshot.statistics("lineno")
        header = "top allocations (no previous snapshot)"
    else:
        stats = snapshot.compare_to(_previous_snapshot, "lineno")
        header = "top differences since the previous SIGUSR1"
    lines = [header, ""]
    lines.extend(str(stat) for stat in stats[:_MEMDEBUG_TOP])
    diff_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _previous_snapshot = snapshot
    _prune_memdebug(directory)
    logger.info("API_MEMDEBUG wrote %s and %s", snap_path, diff_path)
    return snap_path, diff_path


def _prune_memdebug(directory: Path) -> None:
    """Keep the newest snapshot files. Older dumps are deleted."""
    files = sorted(path for path in directory.glob("tracemalloc-*") if path.is_file())
    stale = files[: max(0, len(files) - _MEMDEBUG_KEEP_FILES)]
    for path in stale:
        try:
            path.unlink()
        except OSError:
            logger.warning("API_MEMDEBUG could not remove %s", path)


def main() -> None:
    install_memdebug()
    init_db()
    settings = get_settings()
    uvicorn.run("api.app:app", host=settings.api_host, port=settings.api_port, reload=False)


if __name__ == "__main__":
    main()
