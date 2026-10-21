"""Short single-flight cache for dashboard responses.

The paper cycle and the walk-forward do not call ``floor_cache``. Those
paths keep reading proposals, the book, and the job ledger themselves.
This module only serves a repeated dashboard read.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any


class ResponseCache:
    """One in-flight build per name, then a TTL.

    The lock is not held across ``build``. Waiters block on an event and
    then read the slot the leader stored. A failed build wakes them so
    the next request can try again.
    """

    def __init__(self, ttl_seconds: float) -> None:
        self.ttl_seconds = float(ttl_seconds)
        self._lock = threading.Lock()
        self._slots: dict[str, tuple[tuple[Any, ...], float, str, dict[str, Any]]] = {}
        self._inflight: dict[str, threading.Event] = {}

    def clear(self) -> None:
        """Drop stored responses. An in-flight build may still refill."""
        with self._lock:
            self._slots.clear()

    def fetch(
        self,
        name: str,
        key: tuple[Any, ...],
        build: Callable[[], dict[str, Any]],
    ) -> dict[str, Any]:
        """Return the response for ``key``, building it once when it is stale."""
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
                    raise TypeError(f"{name} response must be a dict")
                epoch = time.time()
                computed_at = datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()
                with self._lock:
                    self._slots[name] = (key, epoch, computed_at, payload)
                return _stamp(payload, computed_at, 0)
            finally:
                with self._lock:
                    if self._inflight.get(name) is event:
                        self._inflight.pop(name, None)
                    event.set()

    def _lookup(self, name: str, key: tuple[Any, ...]) -> dict[str, Any] | None:
        slot = self._slots.get(name)
        if slot is None or slot[0] != key:
            return None
        _key, epoch, computed_at, payload = slot
        elapsed = time.time() - epoch
        if elapsed > self.ttl_seconds:
            return None
        return _stamp(payload, computed_at, max(0, int(elapsed)))


def _stamp(payload: dict[str, Any], computed_at: str, age: int) -> dict[str, Any]:
    """Copy the top dict and record when the build ran. Nested values are shared."""
    out = dict(payload)
    out["computed_at"] = computed_at
    out["age"] = age
    return out


# /api/floor. The F111 and observer panels use the same 30s window so
# the three heavy polls do not rebuild on the same tick.
floor_cache = ResponseCache(30.0)
