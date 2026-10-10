"""Paper sleeves are evaluated once, on the poll after the bar closes.

15m, 1h, 4h, and any other known clock share that path. On SGP1 a cycle
runs for about 0.5-1 minute and the next cycle starts about 15.5 minutes
later, which is past the 15-minute latency window for a 15m close the poll
missed. These tests drive the clock. They do not talk to an exchange.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pandas as pd
import pytest

from config.settings import get_settings
from core.data.ohlcv import TIMEFRAME_DELTAS
from core.execution.engine import PlanEntry, TradingEngine, TradingPlan
from core.execution.paper import PaperBroker
from core.execution.paper_bar_eval import (
    bar_is_actionable,
    cycle_paper_bar,
    is_known_timeframe,
    last_closed_bar_open,
    poll_paper_book,
    sleeve_key,
)
from core.ledger.store import Ledger
from core.risk.engine import RiskDecision, RiskEngine, RiskVerdict
from core.risk.killswitch import KillSwitch, TripReason
from core.risk.limits import PAPER_LIMITS
from core.strategy.base import SignalSide, Strategy
from research.costs import FRICTIONLESS
from tests.test_execution import StubDataSource

UTC = timezone.utc
STARTING = 10_000.0


def _at(hour: int, minute: int = 0, second: int = 0, *, day: int = 10) -> datetime:
    return datetime(2026, 10, day, hour, minute, second, tzinfo=UTC)


class Clock:
    def __init__(self, when: datetime) -> None:
        self.when = when

    def __call__(self) -> datetime:
        return self.when


class CandleFeed:
    """Closed bars up to the clock, plus the still-forming bar the exchange sends."""

    def __init__(self, clock: Clock) -> None:
        self.clock = clock
        self.calls: list[tuple[str, str]] = []

    def fetch_latest(self, symbol: str, timeframe: str, bars: int = 300) -> pd.DataFrame:
        self.calls.append((symbol, timeframe))
        step = TIMEFRAME_DELTAS[timeframe]
        epoch = int(self.clock.when.timestamp())
        step_s = int(step.total_seconds())
        forming = datetime.fromtimestamp((epoch // step_s) * step_s, tz=UTC)
        index = pd.date_range(end=forming, periods=bars, freq=step, tz="UTC")
        close = [100_000.0] * len(index)
        frame = pd.DataFrame(
            {
                "open": close,
                "high": close,
                "low": close,
                "close": close,
                "volume": [1.0] * len(index),
                "turnover": [1.0] * len(index),
            },
            index=index,
        )
        frame.index.name = "timestamp"
        return frame

    def close(self) -> None:
        return None


class RecordingStrategy(Strategy):
    """Flat on every bar. Records the closed bar it was shown."""

    min_bars = 2

    def __init__(self, name: str) -> None:
        super().__init__()
        self.name = name
        self.seen: list[datetime] = []

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.seen.append(candles.index[-1].to_pydatetime())
        return self.empty_signals(candles)


class AlwaysLong(Strategy):
    name = "always_long"
    min_bars = 2

    def __init__(self) -> None:
        super().__init__()
        self.calls = 0

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.calls += 1
        out = self.empty_signals(candles)
        last = len(out) - 1
        out.iloc[last, out.columns.get_loc("signal")] = 1
        out.iloc[last, out.columns.get_loc("side")] = SignalSide.LONG.value
        out.iloc[last, out.columns.get_loc("score")] = 1.0
        out.iloc[last, out.columns.get_loc("reason")] = "always"
        return out


def _entry(symbol: str, side: SignalSide, strategy: Strategy, timeframe: str) -> PlanEntry:
    return PlanEntry(symbol=symbol, side=side, strategy=strategy, timeframe=timeframe)


def _engine(tmp_path, monkeypatch, clock: Clock, entries: list[PlanEntry]) -> TradingEngine:
    from core.execution import engine as engine_mod

    monkeypatch.setattr(engine_mod, "_now", clock)
    monkeypatch.setattr(engine_mod, "LAST_CYCLE_PATH", tmp_path / "last_cycle.json")
    prices = {"BTCUSDT": 100_000.0, "ETHUSDT": 3_000.0, "SOLUSDT": 150.0}
    broker = PaperBroker(
        starting_equity=STARTING,
        costs=FRICTIONLESS,
        data_source=StubDataSource(prices),
    )
    engine = TradingEngine(
        broker=broker,
        risk_engine=RiskEngine(
            limits=PAPER_LIMITS, kill_switch=KillSwitch(tmp_path / "kill.json")
        ),
        ledger=Ledger(mode="paper", starting_equity=STARTING),
        plan=TradingPlan(entries=entries),
        data_source=CandleFeed(clock),  # type: ignore[arg-type]
    )
    setattr(engine, "paper_bar_state_path", tmp_path / "paper_bar_eval_state.json")
    monkeypatch.setattr(engine, "refresh_scan_plan", lambda: False)
    monkeypatch.setattr(engine, "_refresh_crowding", lambda: None)
    return engine


def _opens(strategy: RecordingStrategy) -> list[datetime]:
    return [stamp.astimezone(UTC).replace(microsecond=0) for stamp in strategy.seen]


def test_close_schedule_matches_15m_1h_and_4h() -> None:
    opened_15 = _at(11, 45)
    assert last_closed_bar_open(_at(12, 0), "15m") == opened_15
    assert last_closed_bar_open(_at(12, 0), "15min") == opened_15
    assert last_closed_bar_open(_at(12, 14, 59), "15m") == opened_15
    assert last_closed_bar_open(_at(12, 15), "15m") == _at(12, 0)
    assert last_closed_bar_open(_at(11, 59, 59), "15m") == _at(11, 30)
    assert bar_is_actionable(_at(12, 0), "15m", opened_15)
    assert bar_is_actionable(_at(12, 15), "15m", opened_15)
    assert bar_is_actionable(_at(12, 15, 1), "15m", opened_15) is False
    # 30m is another bar size in the same key family.
    assert is_known_timeframe("30m")
    assert is_known_timeframe("15min")
    assert is_known_timeframe("2d") is False
    assert last_closed_bar_open(_at(12, 0), "30m") == _at(11, 30)
    assert last_closed_bar_open(_at(12, 30), "30m") == _at(12, 0)

    assert last_closed_bar_open(_at(12, 0), "1h") == _at(11)
    assert last_closed_bar_open(_at(11, 59, 59), "1h") == _at(10)
    assert last_closed_bar_open(_at(12, 0, 1), "4h") == _at(8)
    assert last_closed_bar_open(_at(7, 59), "4h") == _at(0)
    assert last_closed_bar_open(_at(0, 0), "4h") == _at(20, day=9)
    opened = _at(11)
    assert bar_is_actionable(_at(12, 0), "1h", opened)
    assert bar_is_actionable(_at(12, 15), "1h", opened)
    assert bar_is_actionable(_at(12, 15, 1), "1h", opened) is False
    assert bar_is_actionable(_at(11, 59, 59), "1h", opened) is False


def test_polls_miss_no_bar_when_a_cycle_runs_long(tmp_path, monkeypatch, firm_db, caplog) -> None:
    """Polls every 15s, with one gap that ends inside the latency window.

    A cycle that blocks the poll from 13:00 to 13:10 must still catch the
    13:00 close. run_cycle during the window must not evaluate those bars again.
    """
    clock = Clock(_at(11, 50))
    hourly = RecordingStrategy("hourly_book")
    four = RecordingStrategy("four_hour_book")
    engine = _engine(
        tmp_path,
        monkeypatch,
        clock,
        [
            _entry("BTCUSDT", SignalSide.LONG, hourly, "1h"),
            _entry("ETHUSDT", SignalSide.SHORT, four, "4h"),
        ],
    )
    cycle_at = {_at(12, 6), _at(13, 11), _at(16, 2)}
    gap_start, gap_end = _at(13, 0), _at(13, 10)
    caplog.set_level(logging.INFO, logger="core.execution.paper_bar_eval")

    moment = _at(11, 50)
    stop = _at(16, 20)
    while moment <= stop:
        clock.when = moment
        if not (gap_start <= moment < gap_end):
            poll_paper_book(engine, budget_seconds=30)
        if moment in cycle_at:
            engine.run_cycle()
        moment += timedelta(seconds=15)

    assert _opens(hourly) == [_at(11), _at(12), _at(13), _at(14), _at(15)]
    assert _opens(four) == [_at(8), _at(12)]
    logged = [rec.message for rec in caplog.records if rec.message.startswith("paper bar eval")]
    assert len(logged) == 7
    hourly_line = (
        "sleeve=BTCUSDT|1h|LONG|hourly_book bar=2026-10-10T11:00:00+00:00 "
        "signal=none reason=no_signal"
    )
    four_line = "sleeve=ETHUSDT|4h|SHORT|four_hour_book bar=2026-10-10T08:00:00+00:00"
    assert any(hourly_line in line for line in logged)
    assert any(four_line in line for line in logged)


def test_poll_and_cycle_and_restart_evaluate_a_bar_once(tmp_path, monkeypatch, firm_db) -> None:
    clock = Clock(_at(12, 5))
    strategy = RecordingStrategy("once")
    engine = _engine(
        tmp_path,
        monkeypatch,
        clock,
        [_entry("BTCUSDT", SignalSide.LONG, strategy, "1h")],
    )
    assert poll_paper_book(engine) == 1
    engine.run_cycle()
    poll_paper_book(engine)
    assert _opens(strategy) == [_at(11)]

    restarted = RecordingStrategy("once")
    again = _engine(
        tmp_path,
        monkeypatch,
        clock,
        [_entry("BTCUSDT", SignalSide.LONG, restarted, "1h")],
    )
    # Same cursor file. A new process must not run the bar a second time.
    setattr(again, "paper_bar_state_path", engine.paper_bar_state_path)
    poll_paper_book(again)
    again.run_cycle()
    assert restarted.seen == []


def test_restart_catch_up_is_the_current_bar_only(tmp_path, monkeypatch, firm_db) -> None:
    clock = Clock(_at(14, 10))
    hourly = RecordingStrategy("catch_hourly")
    four = RecordingStrategy("catch_four")
    engine = _engine(
        tmp_path,
        monkeypatch,
        clock,
        [
            _entry("BTCUSDT", SignalSide.LONG, hourly, "1h"),
            _entry("BTCUSDT", SignalSide.SHORT, four, "4h"),
        ],
    )
    # Pretend an older bar was the last one this process finished.
    state_path = engine.paper_bar_state_path  # type: ignore[attr-defined]
    state_path.write_text(
        json.dumps(
            {
                "version": 1,
                "sleeves": {
                    "BTCUSDT|1h|LONG|catch_hourly": {
                        "bar_open": "2026-10-10T10:00:00+00:00",
                    }
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    assert poll_paper_book(engine) == 1
    assert _opens(hourly) == [_at(13)]
    # 4h close at 12:00 is already outside the 15-minute window at 14:10.
    assert four.seen == []
    poll_paper_book(engine)
    assert _opens(hourly) == [_at(13)]

    clock.when = _at(14, 20)
    late = RecordingStrategy("late")
    late_engine = _engine(
        tmp_path,
        monkeypatch,
        clock,
        [_entry("ETHUSDT", SignalSide.LONG, late, "1h")],
    )
    setattr(late_engine, "paper_bar_state_path", tmp_path / "empty_state.json")
    assert poll_paper_book(late_engine) == 0
    assert late.seen == []


def test_duplicate_position_or_order_does_not_place_again(tmp_path, monkeypatch, firm_db) -> None:
    clock = Clock(_at(12, 5))
    strategy = AlwaysLong()
    engine = _engine(
        tmp_path,
        monkeypatch,
        clock,
        [_entry("BTCUSDT", SignalSide.LONG, strategy, "1h")],
    )
    engine.risk.evaluate = lambda _intent, _state: RiskDecision(  # type: ignore[method-assign]
        verdict=RiskVerdict.APPROVED, quantity=0.01, notional=1_000.0
    )
    placed: list[str] = []
    real_place = engine.broker.place_market_order

    def _place(*args, **kwargs):  # noqa: ANN002, ANN003
        placed.append(args[0] if args else kwargs.get("symbol", ""))
        return real_place(*args, **kwargs)

    engine.broker.place_market_order = _place  # type: ignore[method-assign]

    assert poll_paper_book(engine) == 1
    assert placed == ["BTCUSDT"]
    assert len(engine.broker.get_positions()) == 1

    # Crash window: the order filled and the cursor was not saved.
    state = engine._paper_bar_state
    state.sleeves.clear()
    state._persist()
    calls_after_fill = strategy.calls
    poll_paper_book(engine)
    assert placed == ["BTCUSDT"]
    assert len(engine.broker.get_positions()) == 1
    assert strategy.calls == calls_after_fill + 1

    # A resting order blocks even when the book is flat.
    flat = AlwaysLong()
    flat_engine = _engine(
        tmp_path,
        monkeypatch,
        clock,
        [_entry("ETHUSDT", SignalSide.LONG, flat, "1h")],
    )
    setattr(flat_engine, "paper_bar_state_path", tmp_path / "orders.json")
    flat_engine.risk.evaluate = engine.risk.evaluate  # type: ignore[method-assign]
    flat_placed: list[str] = []
    real_flat = flat_engine.broker.place_market_order

    def _flat_place(*args, **kwargs):  # noqa: ANN002, ANN003
        flat_placed.append("x")
        return real_flat(*args, **kwargs)

    flat_engine.broker.place_market_order = _flat_place  # type: ignore[method-assign]
    flat_engine.broker.get_open_orders = lambda symbol=None: [  # type: ignore[method-assign]
        SimpleNamespace(symbol="ETHUSDT", reduce_only=False)
    ]
    poll_paper_book(flat_engine)
    assert flat_placed == []
    assert flat.calls == 1
    poll_paper_book(flat_engine)
    assert flat.calls == 1

    # Ledger row with no broker position is the same guard.
    ledger_only = AlwaysLong()
    ledger_engine = _engine(
        tmp_path,
        monkeypatch,
        clock,
        [_entry("SOLUSDT", SignalSide.LONG, ledger_only, "1h")],
    )
    setattr(ledger_engine, "paper_bar_state_path", tmp_path / "ledger.json")
    ledger_engine.risk.evaluate = engine.risk.evaluate  # type: ignore[method-assign]
    ledger_engine.ledger.open_position(
        symbol="SOLUSDT",
        side="LONG",
        quantity=1.0,
        entry_price=150.0,
        expected_entry_price=150.0,
        take_profit=200.0,
        stop_loss=100.0,
        strategy="always_long",
        sector="other",
        signal_score=1.0,
        signal_reason="seed",
        broker_order_id="seed",
    )
    blocked: list[str] = []
    def _blocked(*_args, **_kwargs):  # noqa: ANN002, ANN003
        blocked.append("placed")

    ledger_engine.broker.place_market_order = _blocked  # type: ignore[method-assign]
    poll_paper_book(ledger_engine)
    assert blocked == []
    assert ledger_only.calls == 1


def test_poll_refetches_a_timeframe_only_when_a_new_close_is_due(
    tmp_path, monkeypatch, firm_db
) -> None:
    clock = Clock(_at(12, 30))
    long_side = RecordingStrategy("btc_long")
    short_side = RecordingStrategy("btc_short")
    four = RecordingStrategy("btc_four")
    engine = _engine(
        tmp_path,
        monkeypatch,
        clock,
        [
            _entry("BTCUSDT", SignalSide.LONG, long_side, "1h"),
            _entry("BTCUSDT", SignalSide.SHORT, short_side, "1h"),
            _entry("BTCUSDT", SignalSide.SHORT, four, "4h"),
        ],
    )
    feed = engine._data
    poll_paper_book(engine)
    assert feed.calls == []

    clock.when = _at(12, 0, 15)
    poll_paper_book(engine)
    assert feed.calls == [("BTCUSDT", "1h"), ("BTCUSDT", "4h")]
    poll_paper_book(engine)
    clock.when = _at(12, 14)
    poll_paper_book(engine)
    assert feed.calls == [("BTCUSDT", "1h"), ("BTCUSDT", "4h")]

    clock.when = _at(13, 0, 15)
    poll_paper_book(engine)
    # New 1h close. The 4h bar is the same one and its window has closed.
    assert feed.calls == [("BTCUSDT", "1h"), ("BTCUSDT", "4h"), ("BTCUSDT", "1h")]
    assert _opens(long_side) == [_at(11), _at(12)]
    assert _opens(short_side) == [_at(11), _at(12)]
    assert _opens(four) == [_at(8)]


def test_poll_budget_defers_the_rest_of_the_book(tmp_path, monkeypatch, firm_db) -> None:
    clock = Clock(_at(12, 5))
    sleeves = [RecordingStrategy(f"budget_{name}") for name in ("btc", "eth", "sol")]
    entries = [
        _entry(symbol, SignalSide.LONG, strategy, "1h")
        for symbol, strategy in zip(("BTCUSDT", "ETHUSDT", "SOLUSDT"), sleeves, strict=True)
    ]
    engine = _engine(tmp_path, monkeypatch, clock, entries)

    class Mono:
        def __init__(self) -> None:
            self.t = 0.0

        def __call__(self) -> float:
            return self.t

    mono = Mono()
    feed = engine._data
    real_fetch = feed.fetch_latest

    def _slow(symbol: str, timeframe: str, bars: int = 300) -> pd.DataFrame:
        mono.t += 5.0
        return real_fetch(symbol, timeframe, bars)

    feed.fetch_latest = _slow  # type: ignore[method-assign]
    assert poll_paper_book(engine, budget_seconds=4, monotonic=mono) == 1
    assert poll_paper_book(engine, budget_seconds=4, monotonic=mono) == 1
    assert poll_paper_book(engine, budget_seconds=4, monotonic=mono) == 1
    assert [_opens(item) for item in sleeves] == [[_at(11)], [_at(11)], [_at(11)]]


def test_poll_takes_15m_once_and_skips_live_mode_and_a_tripped_switch(
    tmp_path, monkeypatch, firm_db
) -> None:
    clock = Clock(_at(12, 5))
    # 12:05 is inside the window for the 15m bar that opened 11:45.
    slow = RecordingStrategy("rsi_trend")
    engine = _engine(
        tmp_path,
        monkeypatch,
        clock,
        [_entry("BTCUSDT", SignalSide.LONG, slow, "15m")],
    )
    assert poll_paper_book(engine) == 1
    assert _opens(slow) == [_at(11, 45)]
    engine.run_cycle()
    poll_paper_book(engine)
    assert _opens(slow) == [_at(11, 45)]

    odd = RecordingStrategy("not_a_clock")
    odd_engine = _engine(
        tmp_path,
        monkeypatch,
        clock,
        [_entry("ETHUSDT", SignalSide.LONG, odd, "2d")],
    )
    setattr(odd_engine, "paper_bar_state_path", tmp_path / "unknown_tf.json")
    assert poll_paper_book(odd_engine) == 0
    assert odd.seen == []
    skipped = cycle_paper_bar(
        odd_engine, odd_engine.plan.entries[0], equity=STARTING, marks={}
    )
    assert skipped.handled is False

    hourly = RecordingStrategy("armed")
    armed = _engine(
        tmp_path,
        monkeypatch,
        clock,
        [_entry("BTCUSDT", SignalSide.LONG, hourly, "1h")],
    )
    monkeypatch.setenv("TRADING_MODE", "testnet")
    get_settings.cache_clear()
    try:
        assert poll_paper_book(armed) == 0
        assert hourly.seen == []
    finally:
        monkeypatch.delenv("TRADING_MODE", raising=False)
        get_settings.cache_clear()

    monkeypatch.setenv("GO_LIVE_CONFIRMED", "I_ACCEPT_THE_RISK")
    get_settings.cache_clear()
    try:
        assert poll_paper_book(armed) == 0
    finally:
        monkeypatch.delenv("GO_LIVE_CONFIRMED", raising=False)
        get_settings.cache_clear()

    halted = RecordingStrategy("halted")
    halted_engine = _engine(
        tmp_path,
        monkeypatch,
        clock,
        [_entry("BTCUSDT", SignalSide.LONG, halted, "1h")],
    )
    halted_engine.risk.kill_switch.trip(TripReason.MANUAL, "test", tripped_by="test")
    assert poll_paper_book(halted_engine) == 0
    assert halted.seen == []


def test_15m_close_is_taken_once_across_the_sgp1_cycle_gap(
    tmp_path, monkeypatch, firm_db, caplog
) -> None:
    """SGP1: the cycle body is about a minute, and cycles are about 15.5 min apart.

    The 12:00 15m close lands while that body has the poll paused. The first
    poll after the wait records bar 11:45. The cycle at 12:15 looks at the
    next bar, so it cannot be the thing that saves 11:45, and it must not
    run 11:45 again. A 30m sleeve on the same plan uses the same path.
    """
    clock = Clock(_at(11, 45))
    rsi = RecordingStrategy("rsi_trend")
    donchian = RecordingStrategy("donchian_breakout")
    neckline = RecordingStrategy("double_top_neckline_break")
    half_hour = RecordingStrategy("half_hour_book")
    engine = _engine(
        tmp_path,
        monkeypatch,
        clock,
        [
            _entry("BTCUSDT", SignalSide.LONG, rsi, "15m"),
            _entry("BTCUSDT", SignalSide.LONG, donchian, "15m"),
            _entry("BTCUSDT", SignalSide.SHORT, neckline, "15m"),
            _entry("ETHUSDT", SignalSide.LONG, half_hour, "30m"),
        ],
    )
    # 60s body, then the next start 15.5 minutes after the previous start.
    cycle_starts = (_at(11, 59, 30), _at(12, 15), _at(12, 30, 30), _at(12, 46))
    body = timedelta(seconds=60)
    caplog.set_level(logging.INFO, logger="core.execution.paper_bar_eval")
    feed = engine._data

    moment = _at(11, 45)
    while moment <= _at(12, 46):
        clock.when = moment
        in_body = any(start < moment < start + body for start in cycle_starts)
        if moment in cycle_starts:
            poll_paper_book(engine, budget_seconds=30)
            engine.run_cycle()
        elif not in_body:
            poll_paper_book(engine, budget_seconds=30)
        if moment == _at(12, 0, 30):
            # 12:00 close was inside the 11:59:30 body. This poll records it.
            assert _opens(rsi) == [_at(11, 30), _at(11, 45)]
            assert _opens(half_hour) == [_at(11), _at(11, 30)]
        moment += timedelta(seconds=15)

    fifteen = [_at(11, 30), _at(11, 45), _at(12), _at(12, 15), _at(12, 30)]
    assert _opens(rsi) == fifteen
    assert _opens(donchian) == fifteen
    assert _opens(neckline) == fifteen
    assert _opens(half_hour) == [_at(11), _at(11, 30), _at(12)]
    # One fetch per close. The three BTC 15m sleeves share it.
    assert feed.calls.count(("BTCUSDT", "15m")) == 5
    assert feed.calls.count(("ETHUSDT", "30m")) == 3
    assert last_closed_bar_open(_at(12, 15), "15m") == _at(12)
    assert bar_is_actionable(_at(12, 15, 1), "15m", _at(11, 45)) is False

    logged = [rec.message for rec in caplog.records if rec.message.startswith("paper bar eval")]
    gap_line = (
        "sleeve=BTCUSDT|15m|LONG|rsi_trend bar=2026-10-10T11:45:00+00:00 "
        "signal=none reason=no_signal source=poll"
    )
    assert any(gap_line in line for line in logged)
    assert len(logged) == 18

    clock.when = _at(12, 20)
    restarted = RecordingStrategy("rsi_trend")
    stale = RecordingStrategy("stale_30m")
    again = _engine(
        tmp_path,
        monkeypatch,
        clock,
        [
            _entry("BTCUSDT", SignalSide.LONG, restarted, "15m"),
            _entry("ETHUSDT", SignalSide.LONG, stale, "30m"),
        ],
    )
    setattr(again, "paper_bar_state_path", tmp_path / "restart_15m.json")
    # Current 15m bar only. The 30m window for 11:30 already closed at 12:15.
    assert poll_paper_book(again) == 1
    assert _opens(restarted) == [_at(12)]
    assert stale.seen == []
    again.run_cycle()
    assert _opens(restarted) == [_at(12)]


def test_hot_poll_runs_f111_then_the_paper_book(monkeypatch) -> None:
    from scripts.run_paper_trading import _hot_poll

    calls: list[str] = []
    monkeypatch.setattr(
        "core.execution.f111_paper.run_attached_minute_step",
        lambda _engine: calls.append("f111"),
    )
    monkeypatch.setattr(
        "core.execution.paper_bar_eval.poll_paper_book",
        lambda _engine: calls.append("bars"),
    )
    _hot_poll(object())
    assert calls == ["f111", "bars"]

    def _boom(_engine: object) -> None:
        raise RuntimeError("f111 down")

    calls.clear()
    monkeypatch.setattr("core.execution.f111_paper.run_attached_minute_step", _boom)
    _hot_poll(object())
    assert calls == ["bars"]


def test_non_paper_broker_does_not_use_the_cursor(tmp_path, monkeypatch) -> None:
    clock = Clock(_at(12, 5))
    monkeypatch.setattr("core.execution.engine._now", clock)
    strategy = RecordingStrategy("live_book")
    broker = MagicMock()
    broker.health_check.return_value = (True, "ok")
    broker.get_balance.return_value = STARTING
    broker.get_positions.return_value = []
    risk = MagicMock()
    risk.kill_switch.is_tripped = False
    risk.check_portfolio_health.return_value = []
    ledger = MagicMock()
    ledger.reconcile.return_value = []
    ledger.open_positions.return_value = []
    ledger.performance.return_value = {"net_pnl": 0.0}
    engine = TradingEngine(
        broker=broker,
        risk_engine=risk,
        ledger=ledger,
        plan=TradingPlan(entries=[_entry("BTCUSDT", SignalSide.LONG, strategy, "1h")]),
        data_source=CandleFeed(clock),  # type: ignore[arg-type]
    )
    monkeypatch.setattr(engine, "refresh_scan_plan", lambda: False)
    monkeypatch.setattr(engine, "_refresh_crowding", lambda: None)
    monkeypatch.setattr(engine, "_record_cycle_accounting", lambda *args, **kwargs: None)
    monkeypatch.setattr("core.execution.engine.persist_last_cycle", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        "core.execution.engine.paper_regime_sitout_reason", lambda _entry: None
    )
    assert poll_paper_book(engine) == 0
    engine.run_cycle()
    engine.run_cycle()
    # Live still evaluates on the cycle. There is no once-per-bar cursor.
    assert len(strategy.seen) == 2
    assert sleeve_key(engine.plan.entries[0]) == "BTCUSDT|1h|LONG|live_book"
