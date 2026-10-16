"""In-process cache for the heavy desk panels.

``/api/f111`` and ``/api/observers`` used to rebuild the census and the
why-no-trade panel on every browser poll. Those builds walk the latest
scan (one row per sleeve on the live book) plus the append-only F111
telemetry and the BL8 ledger. Overlapping polls did that work several
times at once, which is what pinned the dashboard API above one core.

One build is enough until the book file changes, the latest scan id
changes, or a short TTL passes. Requests that arrive during a build wait
for it instead of starting another one. The trading loop does not import
this module.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# The live desk poll is 60s. 30s is short of that interval, so a quiet
# tab still refreshes every poll, and a burst of overlapping polls shares
# one build instead of stacking on the AnyIO thread pool.
DEFAULT_TTL_SECONDS = 30.0

# Tail window for the latest telemetry line. A gate row is under 1KB;
# 16KB still covers a long feature payload without reading the file.
_TAIL_BYTES = 16_384


class _Slot:
    """One cached panel. ``payload`` is the builder's dict, not a copy."""

    def __init__(
        self,
        key: tuple[Any, ...],
        epoch: float,
        computed_at: str,
        payload: dict[str, Any],
    ) -> None:
        self.key = key
        self.epoch = epoch
        self.computed_at = computed_at
        self.payload = payload


class PanelCache:
    """TTL cache with one in-flight build per panel name.

    The lock is not held across ``build``. Waiters block on an event, then
    read the slot the leader stored. A failed build wakes them so the next
    request can try again.
    """

    def __init__(self, ttl_seconds: float = DEFAULT_TTL_SECONDS) -> None:
        self.ttl_seconds = float(ttl_seconds)
        self._lock = threading.Lock()
        self._slots: dict[str, _Slot] = {}
        self._inflight: dict[str, threading.Event] = {}

    def clear(self) -> None:
        """Drop stored panels. In-flight builds still finish and may refill."""
        with self._lock:
            self._slots.clear()

    def fetch(
        self,
        name: str,
        key: tuple[Any, ...],
        build: Callable[[], dict[str, Any]],
    ) -> dict[str, Any]:
        """Return the panel for ``key``, building it once when it is stale."""
        while True:
            with self._lock:
                fresh = self._lookup(name, key)
                if fresh is not None:
                    return fresh
                event = self._inflight.get(name)
                if event is None:
                    event = threading.Event()
                    self._inflight[name] = event
                    leader = True
                else:
                    leader = False
            if not leader:
                event.wait()
                continue
            try:
                payload = build()
                if not isinstance(payload, dict):
                    raise TypeError(f"{name} panel must be a dict")
                epoch = time.time()
                computed_at = datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()
                with self._lock:
                    self._slots[name] = _Slot(key, epoch, computed_at, payload)
                return _annotate(payload, computed_at, 0)
            finally:
                with self._lock:
                    if self._inflight.get(name) is event:
                        self._inflight.pop(name, None)
                    event.set()

    def _lookup(self, name: str, key: tuple[Any, ...]) -> dict[str, Any] | None:
        slot = self._slots.get(name)
        if slot is None or slot.key != key:
            return None
        # Expiry uses the fractional clock. The payload age is whole seconds.
        elapsed = time.time() - slot.epoch
        if elapsed > self.ttl_seconds:
            return None
        return _annotate(slot.payload, slot.computed_at, max(0, int(elapsed)))


def _annotate(payload: dict[str, Any], computed_at: str, age: int) -> dict[str, Any]:
    """Copy the panel and stamp when it was built.

    ``age`` is seconds since ``computed_at``. Nested why-no-trade objects
    and observer cards get the same stamp so the panel can show it without
    a second clock. The stored slot is left untouched.
    """
    out = dict(payload)
    out["computed_at"] = computed_at
    out["age"] = age
    why = out.get("why_no_trade")
    if isinstance(why, dict):
        stamped = dict(why)
        stamped["computed_at"] = computed_at
        stamped["age"] = age
        out["why_no_trade"] = stamped
    cards = out.get("observers")
    if isinstance(cards, list):
        out["observers"] = [
            _annotate(card, computed_at, age) if isinstance(card, dict) else card
            for card in cards
        ]
    return out


# Process-wide cache. Tests call ``panel_cache.clear()`` between cases.
panel_cache = PanelCache()


def _stat_part(path: Path | None) -> tuple[str, int, int]:
    """Path, mtime_ns, size. A missing file is a stable empty part."""
    if path is None:
        return ("", 0, 0)
    target = Path(path)
    try:
        st = target.stat()
    except OSError:
        return (str(target), 0, 0)
    return (str(target), int(st.st_mtime_ns), int(st.st_size))


def book_fingerprint(path: Path | None = None) -> tuple[str, int, str]:
    """Live book identity: path, mtime_ns, and sha256 of the file bytes.

    The sha is the content key. mtime lets a caller see which write produced
    it. A missing book is an empty sha so the panel still renders.
    """
    from api.desk_status import live_approvals_path

    target = live_approvals_path(path)
    try:
        st = target.stat()
    except OSError:
        return (str(target), 0, "")
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    return (str(target), int(st.st_mtime_ns), digest)


def telemetry_scan_id(path: Path | None) -> str:
    """Latest F111 scan id from the tail of the append-only telemetry file.

    The id is ``run_id``, otherwise the bar close on the last line. The
    file's mtime and size are part of the token so an append still misses
    the cache when the last line cannot be parsed. Reading the tail does
    not load the rest of the file.
    """
    if path is None:
        return "missing"
    target = Path(path)
    if not target.is_file():
        return "missing"
    try:
        st = target.stat()
    except OSError:
        return "missing"
    token = ""
    try:
        with target.open("rb") as handle:
            handle.seek(0, 2)
            end = handle.tell()
            handle.seek(max(0, end - _TAIL_BYTES))
            raw = handle.read()
        text = raw.decode("utf-8", "replace")
        lines = text.splitlines()
        # A mid-line seek leaves a fragment in front. Drop it.
        if end > _TAIL_BYTES and lines:
            lines = lines[1:]
        last = ""
        for line in lines:
            if line.strip():
                last = line.strip()
        if last:
            obj = json.loads(last)
            if isinstance(obj, dict):
                raw_id = obj.get("run_id") or obj.get("source_signal_time") or obj.get("emitted_at")
                if raw_id is not None:
                    token = str(raw_id)
    except (OSError, UnicodeError, json.JSONDecodeError):
        token = ""
    return f"{st.st_mtime_ns}:{st.st_size}:{token}"


def _bl8_scan_id(status_path: Path | None, db_path: Path | None) -> str:
    """Latest BL8 scan: status heartbeat plus the newest observation id.

    ``MAX(id)`` uses the primary key. It does not parse context payloads.
    """
    heartbeat = ""
    status_part = _stat_part(status_path)
    if status_path is not None and Path(status_path).is_file():
        try:
            blob = json.loads(Path(status_path).read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            blob = None
        if isinstance(blob, dict) and blob.get("heartbeat_ms") is not None:
            heartbeat = str(blob.get("heartbeat_ms"))
    max_id = ""
    if db_path is not None and Path(db_path).is_file():
        uri = Path(db_path).resolve().as_uri() + "?mode=ro"
        try:
            db = sqlite3.connect(uri, uri=True, timeout=1)
        except sqlite3.Error:
            db = None
        if db is not None:
            try:
                db.execute("PRAGMA query_only=ON")
                row = db.execute("SELECT MAX(id) FROM observations").fetchone()
                if row is not None and row[0] is not None:
                    max_id = str(row[0])
            except sqlite3.Error:
                max_id = ""
            finally:
                db.close()
    return f"{status_part}:{heartbeat}|{_stat_part(db_path)}:{max_id}"


def _resolve_f111_paths(
    telemetry_path: Path | None,
    state_path: Path | None,
) -> tuple[Path, Path]:
    from core.strategy.f111_config import STATE_PATH, TELEMETRY_PATH

    telemetry = Path(telemetry_path) if telemetry_path is not None else TELEMETRY_PATH
    state = Path(state_path) if state_path is not None else STATE_PATH
    return telemetry, state


def f111_cache_key(
    telemetry_path: Path | None = None,
    state_path: Path | None = None,
) -> tuple[Any, ...]:
    """Key for the F111 panel: book mtime/sha plus the latest telemetry scan."""
    telemetry, state = _resolve_f111_paths(telemetry_path, state_path)
    return (
        "f111",
        book_fingerprint(None),
        _stat_part(telemetry),
        telemetry_scan_id(telemetry),
        _stat_part(state),
    )


def observers_cache_key(
    *,
    telemetry_path: Path | None = None,
    state_path: Path | None = None,
    status_path: Path | None = None,
    db_path: Path | None = None,
    config_path: Path | None = None,
) -> tuple[Any, ...]:
    """Key for both observer cards. Includes the F111 key and the BL8 scan."""
    from api.observer_status import bl8_paths

    paths = bl8_paths(status_path=status_path, db_path=db_path, config_path=config_path)
    status = paths["status"]
    database = paths["database"]
    config = paths["config"]
    return (
        "observers",
        f111_cache_key(telemetry_path, state_path),
        _bl8_scan_id(
            status if isinstance(status, Path) else None,
            database if isinstance(database, Path) else None,
        ),
        _stat_part(config if isinstance(config, Path) else None),
    )
