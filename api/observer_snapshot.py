"""Background snapshot for ``GET /api/observers``.

The desk poll used to rebuild F111 telemetry and the BL8 ledger on the
request itself. That walk grew with the append-only files (several seconds)
while the browser gave up at four seconds and blanked the panel.

The refresher below owns that work. It runs about every 60 seconds and
again when a scan file changes. Request handlers only copy the latest
snapshot, so a poll cannot start a second build. Before the first
successful build the payload is a warming document, not an empty list.
A failed refresh keeps the previous snapshot and records the error.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Quiet tabs poll faster than this. The snapshot is already in memory, so
# the extra polls do not rebuild the scan.
REFRESH_INTERVAL_SECONDS = 60.0

# How often the refresher stats scan files. A completed scan shows up as a
# new size or mtime and is picked up on the next look, without waiting out
# the full minute. Stat calls stay off the request path.
SCAN_WATCH_SECONDS = 2.0

_KNOWN_IDS = ("f111", "bl8")

# Tests set this to "0" so importing the app does not start a build.
_AUTOSTART_ENV = "OBSERVER_SNAPSHOTS_AUTOSTART"


def utc_now_iso() -> str:
    """UTC timestamp with a Z suffix, second resolution plus microseconds."""
    stamp = datetime.now(timezone.utc).isoformat(timespec="microseconds")
    return stamp.replace("+00:00", "Z")


def warming_payload(error: str | None = None) -> dict[str, Any]:
    """No snapshot yet. ``observers`` is null so the desk cannot treat it as empty."""
    body: dict[str, Any] = {
        "ok": True,
        "status": "warming",
        "warming": True,
        "empty": False,
        "generated_at": None,
        "observers": None,
        "pulses": None,
        "detail": (
            "Observers snapshot is warming. The first read has not finished. "
            "This is not an empty book."
        ),
    }
    if error:
        body["refresh_error"] = error
    return body


def stamp_payload(payload: dict[str, Any], generated_at: str | None = None) -> dict[str, Any]:
    """Copy a compute result and mark it ready or explicitly empty.

    An empty ``observers`` list is a real answer from a finished build.
    Warming is a different status and is never produced here.
    """
    out = dict(payload)
    cards = out.get("observers")
    empty = isinstance(cards, list) and len(cards) == 0
    out["generated_at"] = generated_at or utc_now_iso()
    out["warming"] = False
    out["empty"] = empty
    out["status"] = "empty" if empty else "ready"
    out.pop("refresh_error", None)
    return out


def compute_observers_payload() -> dict[str, Any]:
    """Build both cards. Only the refresher calls this.

    Request handlers must not call it. Tests patch this name and count calls
    across a burst of GETs.
    """
    from api.observer_status import list_observers

    payload = list_observers()
    if not isinstance(payload, dict):
        raise TypeError("observers payload must be a dict")
    return payload


def _stat_part(path: Path | None) -> tuple[str, int, int]:
    """Path, mtime_ns, and size. Missing files are a stable zero part."""
    if path is None:
        return ("", 0, 0)
    target = Path(path)
    try:
        st = target.stat()
    except OSError:
        return (str(target), 0, 0)
    return (str(target), int(st.st_mtime_ns), int(st.st_size))


def read_scan_token() -> tuple[Any, ...]:
    """Cheap identity of the latest F111 and BL8 scan files.

    Size and mtime move when a scan appends. The bytes are not read and the
    book is not hashed. This stays on the refresher, not on GET.
    """
    parts: list[Any] = []
    try:
        from core.strategy.f111_config import STATE_PATH, TELEMETRY_PATH

        parts.append(_stat_part(TELEMETRY_PATH))
        parts.append(_stat_part(STATE_PATH))
    except Exception as exc:
        parts.append(("f111", type(exc).__name__))
    try:
        from api.observer_status import bl8_paths

        paths = bl8_paths()
        for name in ("status", "database", "config"):
            raw = paths.get(name)
            parts.append(_stat_part(raw if isinstance(raw, Path) else None))
    except Exception as exc:
        parts.append(("bl8", type(exc).__name__))
    return tuple(parts)


class ObserverSnapshotStore:
    """One in-process snapshot and the thread that refreshes it."""

    def __init__(
        self,
        interval_s: float = REFRESH_INTERVAL_SECONDS,
        scan_poll_s: float = SCAN_WATCH_SECONDS,
    ) -> None:
        self.interval_s = float(interval_s)
        self.scan_poll_s = float(scan_poll_s)
        self._lock = threading.Lock()
        self._snapshot: dict[str, Any] | None = None
        self._error: str | None = None
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread: threading.Thread | None = None
        self._scan_token: tuple[Any, ...] | None = None

    @property
    def running(self) -> bool:
        thread = self._thread
        return thread is not None and thread.is_alive()

    def start(self) -> None:
        """Start the refresher if it is not already running."""
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._stop.clear()
            self._wake.clear()
            thread = threading.Thread(
                target=self._loop,
                name="observer-snapshot",
                daemon=True,
            )
            self._thread = thread
            thread.start()

    def start_if_enabled(self) -> bool:
        """Start unless ``OBSERVER_SNAPSHOTS_AUTOSTART`` is turned off."""
        flag = os.environ.get(_AUTOSTART_ENV, "1").strip().lower()
        if flag in {"0", "false", "no", "off"}:
            return False
        self.start()
        return True

    def stop(self, timeout: float = 5.0) -> None:
        """Stop the refresher. A refresh already inside compute is allowed to finish."""
        self._stop.set()
        self._wake.set()
        thread = self._thread
        if thread is not None and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=timeout)
        if thread is None or not thread.is_alive():
            self._thread = None

    def notify_scan_complete(self) -> None:
        """Wake the refresher. The caller does not build the snapshot."""
        self._wake.set()

    def clear(self) -> None:
        """Drop the snapshot. The next serve is warming until a refresh lands."""
        with self._lock:
            self._snapshot = None
            self._error = None

    def seed(self, snapshot: dict[str, Any]) -> None:
        """Install a snapshot without computing. Tests use this for the hot path."""
        if not isinstance(snapshot, dict):
            raise TypeError("snapshot must be a dict")
        with self._lock:
            self._snapshot = dict(snapshot)
            error = snapshot.get("refresh_error")
            self._error = str(error) if error else None

    def refresh(self) -> None:
        """Build once. On failure the previous snapshot stays and the error is kept."""
        try:
            payload = compute_observers_payload()
        except Exception as exc:
            logger.warning("observer snapshot refresh failed: %s", exc)
            with self._lock:
                self._error = f"{type(exc).__name__}: {exc}"
            return
        snap = stamp_payload(payload)
        with self._lock:
            self._snapshot = snap
            self._error = None

    def serve(self) -> dict[str, Any]:
        """Return the cached snapshot. Does not compute, stat, or wait on a build."""
        with self._lock:
            snap = self._snapshot
            error = self._error
        if snap is None:
            return warming_payload(error)
        out = dict(snap)
        cards = out.get("observers")
        if isinstance(cards, list):
            out["observers"] = list(cards)
        pulses = out.get("pulses")
        if isinstance(pulses, list):
            out["pulses"] = list(pulses)
        if error:
            out["refresh_error"] = error
        else:
            out.pop("refresh_error", None)
        return out

    def serve_one(self, observer_id: str) -> dict[str, Any]:
        """One card from the snapshot. Unknown ids raise ``KeyError`` (HTTP 404).

        This does not call the per-observer builder. A known id before the
        first snapshot is a warming document for that id.
        """
        key = str(observer_id or "").strip().lower()
        if key not in _KNOWN_IDS:
            raise KeyError(key)
        snap = self.serve()
        if snap.get("status") == "warming" or snap.get("observers") is None:
            return {
                "id": key,
                "status": "warming",
                "warming": True,
                "empty": False,
                "generated_at": None,
                "detail": snap.get("detail"),
                "refresh_error": snap.get("refresh_error"),
            }
        for card in snap.get("observers") or []:
            if isinstance(card, dict) and str(card.get("id") or "").lower() == key:
                out = dict(card)
                out["generated_at"] = snap.get("generated_at")
                if snap.get("refresh_error"):
                    out["refresh_error"] = snap["refresh_error"]
                return out
        raise KeyError(key)

    def _loop(self) -> None:
        while not self._stop.is_set():
            self.refresh()
            if self._stop.is_set():
                return
            self._scan_token = self._safe_scan_token()
            deadline = time.monotonic() + self.interval_s
            if self._wait_until_due(deadline):
                return

    def _wait_until_due(self, deadline: float) -> bool:
        """Sleep until the interval, a scan change, or stop.

        Returns True when the thread should exit.
        """
        while not self._stop.is_set():
            if self._wake.is_set():
                self._wake.clear()
                return False
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            woke = self._wake.wait(min(self.scan_poll_s, remaining))
            if self._stop.is_set():
                return True
            if woke:
                self._wake.clear()
                return False
            if self._safe_scan_token() != self._scan_token:
                return False
        return True

    def _safe_scan_token(self) -> tuple[Any, ...]:
        try:
            return read_scan_token()
        except Exception:
            logger.exception("observer scan token failed")
            return self._scan_token or ()


# Process-wide snapshot. The API process serves this object.
snapshot_store = ObserverSnapshotStore()
