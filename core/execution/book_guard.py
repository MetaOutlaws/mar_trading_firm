"""One lock for paper book mutations.

Exit supervision runs on its own thread so a slow F111 step or entry poll
cannot stretch the stop cadence. Entries and exits take this lock for the
fill or the close. Funding, quotes, and instrument lookups are fetched
before the lock. The apply step checks the quote timestamp. A ticker that
has to run again under the lock uses a timeout of at most 2 seconds. The
same thread may re-enter (an exit calls the broker, which is still inside
the exit).
"""

from __future__ import annotations

import threading
from datetime import timedelta

#: A quote older than this at apply time is fetched again.
QUOTE_MAX_AGE = timedelta(seconds=5)

#: Cap for a ticker that cannot be moved out of the book lock.
LOCKED_TICKER_TIMEOUT_SECONDS = 2.0


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
