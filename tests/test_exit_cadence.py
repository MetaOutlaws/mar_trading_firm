"""Exit supervision stays on a 15-20s cadence while entries are busy.

Flag off does not change entry ordering. It does change exit timing: F111's
minute step used to run on the same thread as ``supervise_exits``, so a ~36s
F111 pass stretched the stop gap even with ``ENTRY_ORDERING_GBN`` off. The
exit thread covers that gap. Live stays off this thread.
"""

from __future__ import annotations

import logging
import math
import threading
import time
from collections import deque
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest
from sqlalchemy import text

from core.db import get_engine
from core.execution.broker import InvalidOrder
from core.data.ohlcv import BybitOHLCV
from core.execution.book_guard import BookGuard
from core.execution.engine import PAPER_EXIT_POLL_SECONDS, TradingPlan
from core.data.bybit_linear_instruments import AVAILABLE, InstrumentStatus
from core.data.funding import FundingHistory
from core.execution.paper import PaperBroker
from core.execution.exit_supervisor import (
    EXIT_CADENCE_LIMIT_SECONDS,
    EXIT_CALL_HISTORY,
    EXIT_STOP_JOIN_SECONDS,
    PaperExitSupervisor,
)
from core.execution.f111_paper import F111Runtime
from core.execution.paper_cash import KIND_FUNDING, PaperCashStore
from core.strategy.base import Signal, SignalSide
from core.strategy.f111_semantics import new_protection_state
from research.costs import CostModel
from scripts.run_paper_trading import _hot_poll
from tests.test_execution import StubDataSource
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
        lock_entries: list[str] = []
        funding_calls: list[str] = []
        real_enter = BookGuard.__enter__

        def tracking_enter(self):  # noqa: ANN001
            if self is engine.book_guard and threading.current_thread() is threading.main_thread():
                lock_entries.append("enter")
            return real_enter(self)

        monkeypatch.setattr(BookGuard, "__enter__", tracking_enter)
        opened = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
        _open_long(engine, prices)
        ram = engine.broker._positions[SYMBOL]
        ram.observed_funding_only = True
        state = new_protection_state(
            entry_price=ram.entry_price,
            side=1,
            prior_atr=100.0,
            quantity=ram.quantity,
            entry_fee=ram.entry_fee,
        )
        state.update(
            symbol=SYMBOL,
            side_name="LONG",
            opened_at=(opened - timedelta(minutes=5)).isoformat(),
            last_protection_minute=(opened - timedelta(minutes=2)).isoformat(),
        )
        runtime = F111Runtime(
            broker=engine.broker,
            risk=engine.risk,
            ledger=engine.ledger,
            engine=engine,
            clock=lambda: opened,
            state_path=tmp_path / "f111-runtime.json",
            disable_flag=tmp_path / "f111-disabled",
        )
        runtime.protection[SYMBOL] = state
        original_price = engine.broker.get_price

        def slow_price(symbol: str, timeout: float | None = None) -> float | None:
            # The exit thread must not sit behind this fetch.
            if threading.current_thread().name != "paper-exit-supervisor":
                time.sleep(0.30)
            return original_price(symbol, timeout=timeout)

        engine.broker.get_price = slow_price  # type: ignore[method-assign]

        def slow_funding(*_args, **_kwargs):  # noqa: ANN001
            funding_calls.append(threading.current_thread().name)
            time.sleep(0.30)
            return (0.0, "slow-test")

        monkeypatch.setattr(
            "core.execution.f111_paper._funding_for_open", slow_funding
        )

        def real_f111(_engine, **_kwargs):  # noqa: ANN001
            runtime._consume_minutes(SYMBOL, None, opened)

        def slow_poll(_engine, **_kwargs):  # noqa: ANN001
            time.sleep(0.30)

        monkeypatch.setattr(
            "core.execution.f111_paper.run_attached_minute_step", real_f111
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
    assert funding_calls == ["MainThread"]
    assert lock_entries, "the F111 step must take book_guard"
    assert isinstance(supervisor.calls, deque)
    assert supervisor.calls.maxlen == EXIT_CALL_HISTORY


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


def test_reconcile_during_an_exit_does_not_false_trip(
    tmp_path, monkeypatch, firm_db
) -> None:
    """Broker snapshot and the ledger read share the book lock.

    Reconcile copies the broker book first. The exit is then released so it
    can commit before the ledger read. The lock makes that commit wait, so
    both sides still describe the open book. Removing the lock lets the
    exit land in the gap and reconcile reports a mismatch.
    """
    prices = _prices()
    engine = _engine(tmp_path, monkeypatch, firm_db, prices, plan=TradingPlan())
    _open_long(engine, prices)
    _drive_through_stop(prices)
    snapshot_taken = threading.Event()
    exit_done = threading.Event()
    real_snapshot = engine.broker.snapshot_positions
    real_reconcile = engine.ledger.reconcile

    def snapshot() -> list:
        rows = real_snapshot()
        snapshot_taken.set()
        return rows

    def reconcile(snapshots: list) -> list[str]:
        # Started only after the snapshot. With the book lock held, this
        # times out and the ledger is still the pre-exit book. Without the
        # lock, the exit finishes and sets the event first.
        exit_done.wait(timeout=0.6)
        return real_reconcile(snapshots)

    engine.broker.snapshot_positions = snapshot  # type: ignore[method-assign]
    engine.ledger.reconcile = reconcile  # type: ignore[method-assign]
    errors: list[BaseException] = []
    mismatches: list[str] = []

    def reconcile_first() -> None:
        try:
            mismatches.extend(engine.reconcile_broker())
        except Exception as exc:
            errors.append(exc)

    def exit_after_snapshot() -> None:
        assert snapshot_taken.wait(timeout=5)
        try:
            engine.supervise_exits()
        except Exception as exc:
            errors.append(exc)
        finally:
            exit_done.set()

    recon_thread = threading.Thread(target=reconcile_first)
    recon_thread.start()
    assert snapshot_taken.wait(timeout=5)
    exit_thread = threading.Thread(target=exit_after_snapshot)
    exit_thread.start()
    recon_thread.join(timeout=10)
    exit_thread.join(timeout=10)
    assert not recon_thread.is_alive()
    assert not exit_thread.is_alive()

    assert errors == []
    assert mismatches == []
    assert engine.risk.kill_switch.is_tripped is False
    broker_symbols = {row.symbol for row in real_snapshot()}
    ledger_symbols = {row.symbol for row in engine.ledger.open_positions()}
    assert broker_symbols == ledger_symbols
    assert broker_symbols == set()


def test_concurrent_funding_accrual_debits_once(
    tmp_path, monkeypatch, firm_db
) -> None:
    """A second accrual started between plan and book debits the target once.

    The hook runs while the book lock is held. The second accrual blocks
    there, then finds the target already accrued. Dropping the lock lets
    the second accrual finish inside the pause.
    """
    prices = _prices()
    engine = _engine(tmp_path, monkeypatch, firm_db, prices, plan=TradingPlan())
    broker = engine.broker
    broker.costs = CostModel(
        taker_fee=0.0,
        maker_fee=0.0,
        slippage=0.0,
        include_funding=True,
        default_funding_rate=0.0001,
    )
    broker._lock_cost_model = True
    broker._cash_store = PaperCashStore(tmp_path / "cash.json")
    opened = datetime(2026, 10, 10, tzinfo=timezone.utc)
    broker._now = lambda: opened
    _open_long(engine, prices)
    later = opened + timedelta(hours=8)
    broker._now = lambda: later
    position = broker._positions[SYMBOL]
    expected = broker.costs_for(SYMBOL).funding_cost(
        "LONG", position.opened_at, later, position.notional
    )
    assert expected > 0
    cash_after_open = broker.cash
    errors: list[BaseException] = []
    second_started = threading.Event()
    second_done = threading.Event()
    holder: dict[str, threading.Thread] = {}

    def pause(_planned: list) -> None:
        if holder:
            return

        def run() -> None:
            second_started.set()
            try:
                broker.accrue_funding()
            except Exception as exc:
                errors.append(exc)
            finally:
                second_done.set()

        worker = threading.Thread(target=run)
        holder["thread"] = worker
        worker.start()
        assert second_started.wait(timeout=5)
        time.sleep(0.2)
        assert not second_done.is_set()

    broker.before_funding_book = pause
    try:
        broker.accrue_funding()
    finally:
        broker.before_funding_book = None
        worker = holder.get("thread")
        if worker is not None:
            worker.join(timeout=5)
            assert not worker.is_alive()

    assert position.funding_accrued == pytest.approx(expected)
    assert broker.cash == pytest.approx(cash_after_open - expected)
    rows = [event for event in broker._cash_store.events() if event.get("kind") == KIND_FUNDING]
    assert errors == []
    assert len(rows) == 1
    assert rows[0]["amount"] == pytest.approx(expected)
    assert (
        engine._settle_paper_exit(
            SYMBOL, "timeout", at_mark=False, mark_price=prices[SYMBOL]
        )
        == 1
    )
    assert SYMBOL not in broker._positions


def test_interleaved_accruals_with_different_targets_debit_once(
    tmp_path, monkeypatch, firm_db
) -> None:
    """An earlier plan and a later target in one 8h window debit the later target.

    The earlier accrual holds the book lock between plan and book. The later
    accrual blocks on that lock, then books only the unpaid increment.
    """
    prices = _prices()
    engine = _engine(tmp_path, monkeypatch, firm_db, prices, plan=TradingPlan())
    broker = engine.broker
    broker.costs = CostModel(
        taker_fee=0.0,
        maker_fee=0.0,
        slippage=0.0,
        include_funding=True,
        default_funding_rate=0.0001,
    )
    broker._lock_cost_model = True
    broker._cash_store = PaperCashStore(tmp_path / "cash.json")
    opened = datetime(2026, 10, 10, 1, tzinfo=timezone.utc)
    broker._now = lambda: opened
    _open_long(engine, prices)
    earlier = opened + timedelta(hours=2)
    later = opened + timedelta(hours=3)
    position = broker._positions[SYMBOL]
    target_later = broker.costs_for(SYMBOL).funding_cost(
        "LONG", position.opened_at, later, position.notional
    )
    assert target_later > 0
    cash_after_open = broker.cash
    errors: list[BaseException] = []
    later_started = threading.Event()
    later_done = threading.Event()
    holder: dict[str, threading.Thread] = {}

    def pause(_planned: list) -> None:
        if holder:
            return

        def run() -> None:
            later_started.set()
            try:
                broker.accrue_funding(later)
            except Exception as exc:
                errors.append(exc)
            finally:
                later_done.set()

        worker = threading.Thread(target=run)
        holder["thread"] = worker
        worker.start()
        assert later_started.wait(timeout=5)
        time.sleep(0.2)
        assert not later_done.is_set()

    broker.before_funding_book = pause
    try:
        broker.accrue_funding(earlier)
    finally:
        broker.before_funding_book = None
        worker = holder.get("thread")
        if worker is not None:
            worker.join(timeout=5)
            assert not worker.is_alive()

    assert errors == []
    debited = cash_after_open - broker.cash
    assert debited == pytest.approx(target_later)
    assert position.funding_accrued == pytest.approx(target_later)


def test_stop_waits_for_the_inflight_exit_and_alerts_past_sixty_seconds(
    tmp_path, monkeypatch, firm_db, caplog
) -> None:
    engine = _engine(tmp_path, monkeypatch, firm_db, _prices(), plan=TradingPlan())
    entered = threading.Event()
    release = threading.Event()

    def hang() -> int:
        entered.set()
        release.wait(timeout=2)
        return 0

    engine.supervise_exits = hang  # type: ignore[method-assign]
    supervisor = PaperExitSupervisor(engine, interval=0.05, stall_after=0.05)
    caplog.set_level(logging.ERROR, logger="core.execution.exit_supervisor")
    supervisor.start()
    assert entered.wait(timeout=2)
    time.sleep(0.12)

    def let_go() -> None:
        time.sleep(0.2)
        release.set()

    threading.Thread(target=let_go).start()
    began = time.monotonic()
    supervisor.stop()
    assert time.monotonic() - began >= 0.15
    assert "supervise_exits has not completed" in caplog.text


def test_funding_sign_flip_books_the_running_sum(tmp_path) -> None:
    """A rate that changes sign still moves cash to the cumulative target.

    Funding is a running signed sum. After +0.0003 and then -0.0005 on
    1000 notional, a long's accrued funding is -0.20 and a short's is +0.20.
    """
    opened = datetime(2026, 10, 10, 1, tzinfo=timezone.utc)
    rates = pd.Series(
        [0.0003, -0.0005],
        index=pd.to_datetime(["2026-10-10T08:00:00Z", "2026-10-10T16:00:00Z"]),
    )
    history = FundingHistory("XRPUSDT", rates)

    def run(side: str) -> None:
        broker = PaperBroker(
            starting_equity=10_000.0,
            costs=CostModel(
                taker_fee=0.0,
                maker_fee=0.0,
                slippage=0.0,
                include_funding=True,
                default_funding_rate=0.0001,
            ),
            data_source=StubDataSource({"XRPUSDT": 1.0}),
            cash_store=PaperCashStore(tmp_path / f"cash-{side}.json"),
            lock_cost_model=True,
        )
        broker._now = lambda: opened
        broker.set_funding_history("XRPUSDT", history)
        opened_order = broker.place_market_order(
            "XRPUSDT", side, 1000.0, expected_price=1.0
        )
        assert opened_order.success, opened_order.error
        position = broker._positions["XRPUSDT"]
        cash_after_open = broker.cash
        broker.accrue_funding(opened + timedelta(hours=8))
        broker.accrue_funding(opened + timedelta(hours=16))
        expected = broker._funding_cost(position, opened + timedelta(hours=16))
        assert position.funding_accrued == pytest.approx(expected)
        assert cash_after_open - broker.cash == pytest.approx(expected)
        if side == "LONG":
            assert position.funding_accrued == pytest.approx(-0.20)
        else:
            assert position.funding_accrued == pytest.approx(0.20)

    run("LONG")
    run("SHORT")


def test_try_fill_lock_hold_does_not_scale_with_open_position_tickers(
    tmp_path, monkeypatch, firm_db
) -> None:
    """Equity for a fill is priced before the book lock.

    Open positions are marked outside the lock. ``_try_fill`` then recomputes
    equity from those marks. A ticker that runs only while the lock is held
    must not be called once per open position. Falling back to ``get_balance``
    under the lock would sleep once per position and this fails.
    """
    fills = {1: "ETHUSDT", 4: "BNBUSDT"}
    extras = ["SOLUSDT", "XRPUSDT", "DOGEUSDT", "ADAUSDT"]
    now = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
    prices = {symbol: 100.0 for symbol in (*fills.values(), *extras)}

    def run(open_count: int) -> tuple[list[str], float, int]:
        fill = fills[open_count]
        engine = _engine(
            tmp_path, monkeypatch, firm_db, prices, plan=TradingPlan()
        )
        for symbol in extras[:open_count]:
            opened = engine.broker.place_market_order(
                symbol, "LONG", 0.1, expected_price=100.0
            )
            assert opened.success, opened.error
        runtime = F111Runtime(
            broker=engine.broker,
            risk=engine.risk,
            ledger=engine.ledger,
            engine=engine,
            clock=lambda: now,
            state_path=tmp_path / f"f111-lock-{open_count}.json",
            disable_flag=tmp_path / "f111-scan-flag-absent",
        )
        runtime.registry[fill] = InstrumentStatus(
            symbol=fill,
            availability=AVAILABLE,
            reason="Trading",
            exchange_status="Trading",
            tick_size=0.01,
            qty_step=0.01,
            min_qty=0.01,
            min_notional=5.0,
        )
        runtime.pending.append(
            {
                "symbol": fill,
                "side": "LONG",
                "sign": 1,
                "source_signal_id": f"lock-hold-{fill}",
                "source_signal_time": now.isoformat(),
                "cohort": "majors",
                "sector": "other",
                "prior_atr": 1.0,
                "action_time": now.isoformat(),
                "status": "scheduled",
            }
        )
        depth = {"n": 0}
        locked: list[str] = []
        real_enter = BookGuard.__enter__
        real_exit = BookGuard.__exit__

        def tracking_enter(self):  # noqa: ANN001
            if self is engine.book_guard:
                depth["n"] += 1
            return real_enter(self)

        def tracking_exit(self, *exc: object):  # noqa: ANN001
            try:
                return real_exit(self, *exc)
            finally:
                if self is engine.book_guard and depth["n"] > 0:
                    depth["n"] -= 1

        def slow_price(symbol: str, timeout: float | None = None) -> float | None:
            del timeout
            if depth["n"] > 0:
                locked.append(symbol)
                time.sleep(0.05)
            return prices.get(symbol)

        monkeypatch.setattr(BookGuard, "__enter__", tracking_enter)
        monkeypatch.setattr(BookGuard, "__exit__", tracking_exit)
        engine.broker.get_price = slow_price  # type: ignore[method-assign]
        calls = {"n": 0}
        real_equity = runtime._equity_for_fill

        def equity(marks, marks_at):  # noqa: ANN001
            calls["n"] += 1
            return real_equity(marks, marks_at)

        runtime._equity_for_fill = equity  # type: ignore[method-assign]
        started = time.monotonic()
        runtime._consume_minutes(fill, None, now)
        return locked, time.monotonic() - started, calls["n"]

    locked_one, elapsed_one, calls_one = run(1)
    locked_four, elapsed_four, calls_four = run(4)
    assert calls_one == 1
    assert calls_four == 1
    assert locked_one == []
    assert locked_four == []
    assert elapsed_four < elapsed_one + 0.1


def test_stop_returns_when_the_inflight_exit_outlasts_the_timeout(
    tmp_path, monkeypatch, firm_db, caplog
) -> None:
    """``stop`` waits 30s by default, then logs and returns."""
    assert EXIT_STOP_JOIN_SECONDS == 30.0
    engine = _engine(tmp_path, monkeypatch, firm_db, _prices(), plan=TradingPlan())
    entered = threading.Event()
    release = threading.Event()

    def hang() -> int:
        entered.set()
        release.wait(timeout=5)
        return 0

    engine.supervise_exits = hang  # type: ignore[method-assign]
    supervisor = PaperExitSupervisor(engine, interval=0.05, stall_after=60.0)
    caplog.set_level(logging.ERROR, logger="core.execution.exit_supervisor")
    supervisor.start()
    assert entered.wait(timeout=2)
    began = time.monotonic()
    try:
        supervisor.stop(timeout=0.05)
        elapsed = time.monotonic() - began
    finally:
        release.set()
    assert elapsed < 0.5
    assert "continuing to close" in caplog.text
