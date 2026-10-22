"""Paper exit cadence, independent of F111 and the entry poll.

``wait_for_next_cycle`` used to call ``supervise_exits`` and then ``_hot_poll``
on the same thread. F111's minute step is about 36s even with
``ENTRY_ORDERING_GBN`` off, and a GBN poll can run longer than that, so the
gap between stop checks grew past a minute. This thread calls
``supervise_exits`` every ``PAPER_EXIT_POLL_SECONDS`` (15s) while that work
runs. The target gap is at most 20s.

Flag off does not change entry ordering. It does change exit timing: stops
are no longer waiting behind F111. That is intentional.

The thread only starts for a paper broker. Live stays on the exchange's own
stops. Quotes are taken before ``engine.book_guard``; the lock covers the
close, so an entry cannot mutate that same position at the same time. Beta
fetches are not on this thread. ``stop`` waits until an in-flight
``supervise_exits`` returns, and a call that is still running after 60s is
logged.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from typing import Any, Callable

from core.execution.engine import PAPER_EXIT_POLL_SECONDS
from core.execution.paper import PaperBroker

logger = logging.getLogger(__name__)

#: Acceptance bar for the gap between stop checks. The thread wakes every
#: ``PAPER_EXIT_POLL_SECONDS``; this is the limit a stalled poll must not cross.
EXIT_CADENCE_LIMIT_SECONDS = 20

#: Log an alert when one ``supervise_exits`` call is still running after this.
EXIT_STALL_ALERT_SECONDS = 60.0

#: Bound on recorded call timestamps. The thread only needs a recent window.
EXIT_CALL_HISTORY = 256


class PaperExitSupervisor:
    """Daemon thread. ``start`` is a no-op unless the broker is paper."""

    def __init__(
        self,
        engine: Any,
        *,
        interval: float = PAPER_EXIT_POLL_SECONDS,
        sleep: Callable[[float], None] | None = None,
        stall_after: float = EXIT_STALL_ALERT_SECONDS,
    ) -> None:
        self.engine = engine
        self.interval = float(interval)
        self.stall_after = float(stall_after)
        self._sleep = sleep
        self._stop = threading.Event()
        self._inflight = threading.Event()
        self._thread: threading.Thread | None = None
        self._stall_timer: threading.Timer | None = None
        #: Monotonic time of each ``supervise_exits`` call. Tests read this.
        self.calls: deque[float] = deque(maxlen=EXIT_CALL_HISTORY)

    def start(self) -> None:
        if self._thread is not None:
            return
        if not isinstance(getattr(self.engine, "broker", None), PaperBroker):
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="paper-exit-supervisor",
            daemon=True,
        )
        self._thread.start()

    def stop(self, timeout: float | None = None) -> None:
        """Ask the thread to exit and wait for the in-flight exit check.

        ``timeout`` defaults to waiting until that call returns, so
        ``engine.close()`` does not run while a close is still committing.
        """
        self._stop.set()
        thread = self._thread
        self._thread = None
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=timeout)
        self._cancel_stall_timer()

    def _run(self) -> None:
        while not self._stop.is_set():
            started = time.monotonic()
            self._inflight.set()
            self._arm_stall_timer()
            try:
                self.engine.supervise_exits()
                self.calls.append(started)
            except Exception:
                logger.exception("Paper exit supervisor failed; will retry")
            finally:
                self._inflight.clear()
                self._cancel_stall_timer()
            elapsed = time.monotonic() - started
            remaining = self.interval - elapsed
            if self._sleep is not None:
                # Tests inject a sleep. Still wake when stop is set.
                if self._stop.wait(0):
                    return
                self._sleep(max(0.0, remaining))
                continue
            if self._stop.wait(max(0.0, remaining)):
                return

    def _arm_stall_timer(self) -> None:
        limit = self.stall_after

        def alert() -> None:
            if self._inflight.is_set():
                logger.error(
                    "ALERT: supervise_exits has not completed in more than %.0fs",
                    limit,
                )

        timer = threading.Timer(limit, alert)
        timer.daemon = True
        self._stall_timer = timer
        timer.start()

    def _cancel_stall_timer(self) -> None:
        timer = self._stall_timer
        self._stall_timer = None
        if timer is not None:
            timer.cancel()
