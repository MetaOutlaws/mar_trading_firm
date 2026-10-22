"""Exit supervision stays on a 15-20s cadence while entries are busy.

Flag off does not change entry ordering. It does change exit timing: F111's
minute step used to run on the same thread as ``supervise_exits``, so a ~36s
F111 pass stretched the stop gap even with ``ENTRY_ORDERING_GBN`` off. The
exit thread covers that gap. Live stays off this thread.
"""

from __future__ import annotations

import math
import threading
import time

import pandas as pd
import pytest
from sqlalchemy import text

from core.db import get_engine
from core.execution.broker import InvalidOrder
from core.data.ohlcv import BybitOHLCV
from core.execution.engine import PAPER_EXIT_POLL_SECONDS, TradingPlan
from core.execution.exit_supervisor import EXIT_CADENCE_LIMIT_SECONDS, PaperExitSupervisor
from core.strategy.base import Signal, SignalSide
from scripts.run_paper_trading import _hot_poll
from tests.test_f05_exit_supervision import (
    STARTING,
    SYMBOL,
    _drive_through_stop,
    _engine,
    _open_long,
    _scan_plan,
)


def _prices() -> dict[str, float]:
    return {SYMBOL: 100_000.0}


def test_cadence_constants_match_the_15_to_20_second_bar() -> None:
    assert PAPER_EXIT_POLL_SECONDS == 15
    assert EXIT_CADENCE_LIMIT_SECONDS == 20
    assert PAPER_EXIT_POLL_SECONDS <= EXIT_CADENCE_LIMIT_SECONDS


def test_exit_gap_stays_inside_the_limit_during_f111_poll_and_beta_fetch(
    tmp_path, monkeypatch, firm_db
) -> None:
    """Slow F111, a slow poll, and a throttled 1d read must not stall stops.

    The interval here is shortened so the test does not sleep 15s. The gap
    limit scales with that interval by the same 20/15 ratio as production.
    """
    prices = _prices()
    engine = _engine(tmp_path, monkeypatch, firm_db, prices, plan=TradingPlan())
    interval = 0.05
    limit = interval * (EXIT_CADENCE_LIMIT_SECONDS / PAPER_EXIT_POLL_SECONDS)
    supervisor = PaperExitSupervisor(engine, interval=interval)
    supervisor.start()
    beta_threads: list[str] = []
    try:
        def slow_f111(_engine, **_kwargs):  # noqa: ANN001
            time.sleep(0.30)

        def slow_poll(_engine, **_kwargs):  # noqa: ANN001
            time.sleep(0.30)

        monkeypatch.setattr(
            "core.execution.f111_paper.run_attached_minute_step", slow_f111
        )
        monkeypatch.setattr(
            "core.execution.paper_bar_eval.poll_paper_book", slow_poll
        )
        start = time.monotonic()
        _hot_poll(engine)

        def slow_daily(symbol: str, timeframe: str = "1d", bars: int = 45):
            beta_threads.append(threading.current_thread().name)
            time.sleep(0.30)
            return pd.DataFrame()

        class _Data:
            def fetch_latest(self, symbol: str, timeframe: str = "1d", bars: int = 45):
                return slow_daily(symbol, timeframe, bars)

        from core.execution.entry_ordering import budgeted_daily_fetch

        fetch = budgeted_daily_fetch(_Data(), 45, budget=5.0)
        try:
            fetch("ETHUSDT")
        except Exception:
            pass
        end = time.monotonic()
    finally:
        supervisor.stop()

    during = [stamp for stamp in supervisor.calls if start <= stamp <= end]
    assert len(during) >= 3
    gaps = [later - earlier for earlier, later in zip(during, during[1:])]
    assert gaps
    assert max(gaps) <= limit + 0.08
    assert beta_threads
    assert all(name != "paper-exit-supervisor" for name in beta_threads)


def test_supervise_exits_does_not_fetch_betas(
    tmp_path, monkeypatch, firm_db
) -> None:
    engine = _engine(tmp_path, monkeypatch, firm_db, _prices(), plan=TradingPlan())

    def explode(*_args, **_kwargs):  # noqa: ANN001
        raise AssertionError("beta fetch on the exit path")

    monkeypatch.setattr(
        "core.execution.entry_ordering.load_betas", explode
    )
    monkeypatch.setattr(
        "core.execution.entry_ordering.budgeted_daily_fetch", explode
    )
    engine.supervise_exits()


def test_fetch_beta_daily_stops_at_the_deadline_without_a_request() -> None:
    source = BybitOHLCV(testnet=True)
    calls: list[float] = []

    def _page(*_args, **kwargs):  # noqa: ANN001
        calls.append(float(kwargs.get("timeout") or 0.0))
        raise RuntimeError("down")

    source._request_page = _page  # type: ignore[method-assign]
    try:
        with pytest.raises(TimeoutError):
            source.fetch_beta_daily(
                "ETHUSDT",
                bars=5,
                timeout=0.4,
                attempts=2,
                deadline=0.0,
                monotonic=lambda: 1.0,
            )
        assert calls == []
        with pytest.raises(TimeoutError):
            source.fetch_beta_daily(
                "ETHUSDT",
                bars=5,
                timeout=0.4,
                attempts=2,
                deadline=100.0,
                monotonic=lambda: 0.0,
            )
        assert calls == [0.4, 0.4]
    finally:
        source.close()


def test_concurrent_exit_and_entry_stay_consistent(
    tmp_path, monkeypatch, firm_db
) -> None:
    """An exit and an entry on one symbol must not both settle it."""
    prices = _prices()
    engine = _engine(tmp_path, monkeypatch, firm_db, prices, plan=_scan_plan())
    _open_long(engine, prices)
    _drive_through_stop(prices)
    errors: list[BaseException] = []
    barrier = threading.Barrier(2)
    signal = Signal(
        symbol=SYMBOL,
        side=SignalSide.LONG,
        timestamp=pd.Timestamp("2026-10-10T12:00:00Z"),
        price=prices[SYMBOL],
        score=1.0,
        reason="race",
        strategy="race",
        take_profit_pct=0.02,
        stop_loss_pct=0.02,
    )

    def exit_loop() -> None:
        barrier.wait(timeout=5)
        for _ in range(25):
            try:
                engine.supervise_exits()
            except Exception as exc:
                errors.append(exc)

    def entry_loop() -> None:
        barrier.wait(timeout=5)
        for _ in range(25):
            try:
                engine._attempt_entry(signal, STARTING, {SYMBOL: prices[SYMBOL]})
            except InvalidOrder:
                continue
            except Exception as exc:
                errors.append(exc)

    workers = [
        threading.Thread(target=exit_loop),
        threading.Thread(target=entry_loop),
    ]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=30)
        assert not worker.is_alive()

    assert errors == []
    broker_symbols = {row.symbol for row in engine.broker.get_positions()}
    ledger_symbols = {row.symbol for row in engine.ledger.open_positions()}
    assert broker_symbols == ledger_symbols
    assert math.isfinite(float(engine.broker.cash))
    with get_engine().connect() as conn:
        assert conn.execute(text("PRAGMA integrity_check")).scalar() == "ok"
        duplicated = conn.execute(
            text(
                "select position_id from trades "
                "group by position_id having count(*) > 1"
            )
        ).fetchall()
        assert duplicated == []
        closed = conn.execute(text("select count(*) from trades")).scalar()
    assert int(closed or 0) >= 1
