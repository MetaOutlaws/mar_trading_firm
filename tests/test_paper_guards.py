"""Guards that stop paper from filling on the wrong clock or a forming bar.

The ETH wick_rejection fill used asset_params 15m (family clock is 1h) and a
Bybit candle that had not closed. Live still requires research approval.
Paper may scan untested families; it must not scan a clock research already
failed, and it must not fall back to 15m when the catalog clock is missing.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pandas as pd
import pytest

from config.universe import LongParams, ShortParams, Universe
from core.data.ohlcv import closed_candles
from core.execution.engine import PlanEntry, TradingEngine, TradingPlan, _entry_for
from core.strategy.base import SignalSide, Strategy


def _bars(closes: list[float], *, start: datetime, freq: str = "15min") -> pd.DataFrame:
    index = pd.date_range(start, periods=len(closes), freq=freq, tz="UTC")
    frame = pd.DataFrame(
        {
            "open": closes,
            "high": [c + 1 for c in closes],
            "low": [c - 1 for c in closes],
            "close": closes,
            "volume": [1000.0] * len(closes),
            "turnover": [100_000.0] * len(closes),
        },
        index=index,
    )
    frame.index.name = "timestamp"
    return frame


class HotCloseStrategy(Strategy):
    """Fires only when the last bar's close is the sentinel 999."""

    name = "hot_close"
    min_bars = 2

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        out = self.empty_signals(candles)
        if float(candles["close"].iloc[-1]) >= 900:
            last = len(out) - 1
            out.iloc[last, out.columns.get_loc("signal")] = 1
            out.iloc[last, out.columns.get_loc("side")] = SignalSide.LONG.value
            out.iloc[last, out.columns.get_loc("score")] = 1.0
            out.iloc[last, out.columns.get_loc("reason")] = "hot"
        return out


def test_closed_candles_drops_the_forming_bar() -> None:
    start = datetime(2026, 8, 31, 17, 0, tzinfo=timezone.utc)
    frame = _bars([10.0, 11.0, 12.0], start=start)
    # Last bar opened 17:30; at 17:40 it is still forming.
    now = datetime(2026, 8, 31, 17, 40, tzinfo=timezone.utc)
    closed = closed_candles(frame, "15m", now=now)
    assert len(closed) == 2
    assert closed["close"].iloc[-1] == pytest.approx(11.0)


def test_closed_candles_keeps_a_finished_bar() -> None:
    start = datetime(2026, 8, 31, 17, 0, tzinfo=timezone.utc)
    frame = _bars([10.0, 11.0, 12.0], start=start)
    now = datetime(2026, 8, 31, 17, 45, tzinfo=timezone.utc)
    closed = closed_candles(frame, "15m", now=now)
    assert len(closed) == 3


def _engine_with(frame: pd.DataFrame) -> TradingEngine:
    class StubFeed:
        def fetch_latest(self, symbol: str, timeframe: str, bars: int = 300) -> pd.DataFrame:
            return frame

        def close(self) -> None:
            return None

    return TradingEngine(
        broker=MagicMock(),
        risk_engine=MagicMock(),
        ledger=MagicMock(),
        plan=TradingPlan(),
        data_source=StubFeed(),  # type: ignore[arg-type]
    )


def test_evaluate_ignores_a_forming_bar_signal(monkeypatch) -> None:
    """A 999 close on the in-progress candle must not become an order."""
    start = datetime(2026, 8, 31, 17, 0, tzinfo=timezone.utc)
    frame = _bars([10.0, 11.0, 999.0], start=start)
    engine = _engine_with(frame)
    entry = PlanEntry(
        symbol="ETHUSDT",
        side=SignalSide.LONG,
        strategy=HotCloseStrategy(),
        timeframe="15m",
    )
    frozen = datetime(2026, 8, 31, 17, 40, tzinfo=timezone.utc)
    monkeypatch.setattr("core.execution.engine._now", lambda: frozen)
    signal, price = engine._evaluate(entry)
    assert signal is None
    assert price == pytest.approx(999.0)


def test_evaluate_acts_on_the_just_closed_bar(monkeypatch) -> None:
    start = datetime(2026, 8, 31, 16, 30, tzinfo=timezone.utc)
    frame = _bars([10.0, 999.0], start=start)
    engine = _engine_with(frame)
    entry = PlanEntry(
        symbol="ETHUSDT",
        side=SignalSide.LONG,
        strategy=HotCloseStrategy(),
        timeframe="15m",
    )
    frozen = datetime(2026, 8, 31, 17, 5, tzinfo=timezone.utc)
    monkeypatch.setattr("core.execution.engine._now", lambda: frozen)
    signal, _price = engine._evaluate(entry)
    assert signal is not None
    assert signal.reason == "hot"


def test_evaluate_does_not_replay_an_old_closed_bar(monkeypatch) -> None:
    start = datetime(2026, 8, 31, 16, 0, tzinfo=timezone.utc)
    frame = _bars([10.0, 999.0], start=start)
    engine = _engine_with(frame)
    entry = PlanEntry(
        symbol="ETHUSDT",
        side=SignalSide.LONG,
        strategy=HotCloseStrategy(),
        timeframe="15m",
    )
    # Last bar opened 16:15, closed 16:30. At 16:50 the 15m latency window is over.
    frozen = datetime(2026, 8, 31, 16, 50, tzinfo=timezone.utc)
    monkeypatch.setattr("core.execution.engine._now", lambda: frozen)
    signal, _price = engine._evaluate(entry)
    assert signal is None


def test_paper_entry_uses_catalog_clock_not_asset_params(monkeypatch) -> None:
    universe = Universe(
        long_params={"ETHUSDT": LongParams(symbol="ETHUSDT", timeframe="15min")},
        short_params={"ETHUSDT": ShortParams(symbol="ETHUSDT", timeframe="4h")},
    )
    monkeypatch.setattr("core.execution.engine.get_universe", lambda: universe)
    monkeypatch.setattr("firm.research_jobs.paper_scan_family", lambda: "wick_rejection_reversal")
    monkeypatch.setattr("firm.research_jobs._active_job_for", lambda family: {"status": "running"})
    entry = _entry_for("ETHUSDT", SignalSide.LONG, require_approval=False)
    assert entry is not None
    assert entry.strategy.name == "wick_rejection_reversal"
    assert entry.timeframe == "1h"


def test_paper_skips_when_catalog_clock_is_missing(monkeypatch) -> None:
    universe = Universe(
        long_params={"ETHUSDT": LongParams(symbol="ETHUSDT", timeframe="15min")},
    )
    monkeypatch.setattr("core.execution.engine.get_universe", lambda: universe)
    monkeypatch.setattr("firm.research_jobs.paper_scan_family", lambda: "wick_rejection_reversal")
    monkeypatch.setattr("core.execution.engine._clock_timeframe", lambda family, side: "")
    entry = _entry_for("ETHUSDT", SignalSide.LONG, require_approval=False)
    assert entry is None


def test_paper_skips_a_clock_research_already_rejected(monkeypatch) -> None:
    universe = Universe(
        long_params={"ETHUSDT": LongParams(symbol="ETHUSDT", timeframe="15min")},
        approvals={
            "wick_rejection_reversal:ETHUSDT:LONG:1h": {
                "approved": False,
                "timeframe": "1h",
                "failures": ["profit_factor"],
            }
        },
    )
    monkeypatch.setattr("core.execution.engine.get_universe", lambda: universe)
    monkeypatch.setattr("firm.research_jobs.paper_scan_family", lambda: "wick_rejection_reversal")
    monkeypatch.setattr("firm.research_jobs._active_job_for", lambda family: None)
    entry = _entry_for("ETHUSDT", SignalSide.LONG, require_approval=False)
    assert entry is None


def test_paper_still_scans_while_that_family_job_is_running(monkeypatch) -> None:
    universe = Universe(
        long_params={"ETHUSDT": LongParams(symbol="ETHUSDT", timeframe="15min")},
        approvals={
            "wick_rejection_reversal:ETHUSDT:LONG:1h": {
                "approved": False,
                "timeframe": "1h",
            }
        },
    )
    monkeypatch.setattr("core.execution.engine.get_universe", lambda: universe)
    monkeypatch.setattr("firm.research_jobs.paper_scan_family", lambda: "wick_rejection_reversal")
    monkeypatch.setattr(
        "firm.research_jobs._active_job_for",
        lambda family: {"id": 79, "status": "running"},
    )
    entry = _entry_for("ETHUSDT", SignalSide.LONG, require_approval=False)
    assert entry is not None
    assert entry.timeframe == "1h"


def test_paper_plan_keeps_approved_pairs(monkeypatch) -> None:
    from core.execution.engine import build_plan

    universe = Universe(
        long_params={"SOLUSDT": LongParams(symbol="SOLUSDT", timeframe="15min")},
        short_params={
            "BTCUSDT": ShortParams(symbol="BTCUSDT", timeframe="15min"),
            "SOLUSDT": ShortParams(symbol="SOLUSDT", timeframe="15min"),
        },
        approvals={
            "atr_channel_breakout:BTCUSDT:SHORT:4h": {
                "approved": True,
                "timeframe": "4h",
                "strategy": "atr_channel_breakout",
                "params": {"atr_k": 2.0},
            },
            "doji_star_reversal:SOLUSDT:SHORT:1h": {
                "approved": True,
                "timeframe": "1h",
                "strategy": "doji_star_reversal",
                "params": {"run_bars": 3},
            },
        },
    )
    monkeypatch.setattr("core.execution.engine.get_universe", lambda: universe)
    monkeypatch.setattr("firm.research_jobs.paper_scan_family", lambda: "bb_squeeze_breakout")
    monkeypatch.setattr("firm.research_jobs._active_job_for", lambda family: None)
    plan = build_plan(require_approval=False, candidates=["BTCUSDT", "SOLUSDT"])
    approved = {
        (e.symbol, e.side.value, e.strategy.name, e.timeframe) for e in plan.entries
    }
    assert ("BTCUSDT", "SHORT", "atr_channel_breakout", "4h") in approved
    assert ("SOLUSDT", "SHORT", "doji_star_reversal", "1h") in approved


def test_approved_short_does_not_need_asset_params(monkeypatch) -> None:
    """ETH/SOL shorts passed walk-forward; asset_params.json has no short row."""
    universe = Universe(
        long_params={"ETHUSDT": LongParams(symbol="ETHUSDT", timeframe="15min")},
        short_params={},
        approvals={
            "atr_channel_breakout:ETHUSDT:SHORT:4h": {
                "approved": True,
                "timeframe": "4h",
                "strategy": "atr_channel_breakout",
                "params": {"atr_k": 2.0},
            }
        },
    )
    monkeypatch.setattr("core.execution.engine.get_universe", lambda: universe)
    entry = _entry_for("ETHUSDT", SignalSide.SHORT, require_approval=True)
    assert entry is not None
    assert entry.strategy.name == "atr_channel_breakout"
    assert entry.timeframe == "4h"
