"""One lock for paper book mutations.

Exit supervision runs on its own thread so a slow F111 step or entry poll
cannot stretch the stop cadence. Entries and exits both take this lock for
the whole fill or the whole close, and neither holds it across a network
fetch. The same thread may re-enter (an exit calls the broker, which is
still inside the exit).
"""

from __future__ import annotations

import threading


class BookGuard:
    """Process-local re-entrant lock shared by the exit thread and entries."""

    def __init__(self) -> None:
        self._lock = threading.RLock()

    def __enter__(self) -> "BookGuard":
        self._lock.acquire()
        return self

    def __exit__(self, *exc: object) -> bool:
        self._lock.release()
        return False
