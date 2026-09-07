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

from config.universe import LongParams, ShortParams, Universe, parse_approval_key
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


def test_paper_plan_keeps_two_families_on_same_symbol_side(monkeypatch) -> None:
    """A second approved family on the same pair must still scan.

    Collapsing to unique (symbol, side) dropped week_open_reclaim and
    orb_fail_reversion on XRPUSDT SHORT, and double_top on BTCUSDT SHORT.
    """
    from core.execution.engine import build_plan

    universe = Universe(
        long_params={"XRPUSDT": LongParams(symbol="XRPUSDT", timeframe="4h")},
        short_params={
            "BTCUSDT": ShortParams(symbol="BTCUSDT", timeframe="4h"),
            "XRPUSDT": ShortParams(symbol="XRPUSDT", timeframe="4h"),
        },
        approvals={
            "atr_channel_breakout:BTCUSDT:SHORT:4h": {
                "approved": True,
                "timeframe": "4h",
                "strategy": "atr_channel_breakout",
                "params": {"atr_k": 2.0},
            },
            "double_top_neckline_break:BTCUSDT:SHORT:1h": {
                "approved": True,
                "timeframe": "1h",
                "strategy": "double_top_neckline_break",
                "params": {},
            },
            "week_open_reclaim:XRPUSDT:SHORT:4h": {
                "approved": True,
                "timeframe": "4h",
                "strategy": "week_open_reclaim",
                "params": {},
            },
            "orb_fail_reversion:XRPUSDT:SHORT:4h": {
                "approved": True,
                "timeframe": "4h",
                "strategy": "orb_fail_reversion",
                "params": {},
            },
            "mama_fama_cross:BTCUSDT:SHORT:4h": {
                "approved": False,
                "paper_override": True,
                "timeframe": "4h",
                "strategy": "mama_fama_cross",
                "params": {"fastlimit": 0.5, "slowlimit": 0.05},
            },
        },
    )
    monkeypatch.setattr("core.execution.engine.get_universe", lambda: universe)
    monkeypatch.setattr("firm.research_jobs.paper_scan_family", lambda: "bb_squeeze_breakout")
    monkeypatch.setattr("firm.research_jobs._active_job_for", lambda family: None)

    assert len(universe.approved_records) == 4
    assert len(universe.approved_pairs) == 2
    assert set(universe.approved_pairs) == {("BTCUSDT", "SHORT"), ("XRPUSDT", "SHORT")}

    paper = build_plan(require_approval=False, candidates=["BTCUSDT", "XRPUSDT"])
    paper_ids = {
        (e.strategy.name, e.symbol, e.side.value, e.timeframe) for e in paper.entries
    }
    assert ("atr_channel_breakout", "BTCUSDT", "SHORT", "4h") in paper_ids
    assert ("double_top_neckline_break", "BTCUSDT", "SHORT", "1h") in paper_ids
    assert ("week_open_reclaim", "XRPUSDT", "SHORT", "4h") in paper_ids
    assert ("orb_fail_reversion", "XRPUSDT", "SHORT", "4h") in paper_ids
    assert ("mama_fama_cross", "BTCUSDT", "SHORT", "4h") in paper_ids
    approved_in_plan = [
        e
        for e in paper.entries
        if any(
            e.strategy.name == rec.get("strategy")
            and e.symbol == parse_approval_key(key)[1]
            and e.side.value == parse_approval_key(key)[2]
            and e.timeframe == rec.get("timeframe")
            for key, rec in universe.approved_records
        )
    ]
    assert len(approved_in_plan) == len(universe.approved_records)

    live = build_plan(require_approval=True)
    live_ids = {
        (e.strategy.name, e.symbol, e.side.value, e.timeframe) for e in live.entries
    }
    assert live_ids == {
        ("atr_channel_breakout", "BTCUSDT", "SHORT", "4h"),
        ("double_top_neckline_break", "BTCUSDT", "SHORT", "1h"),
        ("week_open_reclaim", "XRPUSDT", "SHORT", "4h"),
        ("orb_fail_reversion", "XRPUSDT", "SHORT", "4h"),
    }
    assert ("mama_fama_cross", "BTCUSDT", "SHORT", "4h") not in live_ids


def test_approved_count_matches_approved_true_research_keys(monkeypatch) -> None:
    """API approved_count is every approved=True key, not unique (symbol, side).

    Paper-override-only rows stay out of the count.
    """
    from config.universe import parse_approval_key
    from api.app import strategies

    universe = Universe(
        approvals={
            "week_open_reclaim:XRPUSDT:SHORT:4h": {
                "approved": True,
                "timeframe": "4h",
                "strategy": "week_open_reclaim",
            },
            "orb_fail_reversion:XRPUSDT:SHORT:4h": {
                "approved": True,
                "timeframe": "4h",
                "strategy": "orb_fail_reversion",
            },
            "double_top_neckline_break:BTCUSDT:SHORT:1h": {
                "approved": True,
                "timeframe": "1h",
                "strategy": "double_top_neckline_break",
            },
            "mama_fama_cross:ETHUSDT:SHORT:4h": {
                "approved": False,
                "paper_override": True,
                "timeframe": "4h",
                "strategy": "mama_fama_cross",
            },
        }
    )
    assert len(universe.approved_records) == 3
    assert len(universe.approved_pairs) == 2
    fake_get = lambda: universe  # noqa: E731
    fake_get.cache_clear = lambda: None
    monkeypatch.setattr("config.universe.get_universe", fake_get)
    payload = strategies()
    assert payload["approved_count"] == 3
    assert payload["paper_override_count"] == 1
    approved_keys = [p["key"] for p in payload["pairs"] if p.get("approved") is True]
    assert set(approved_keys) == {
        "week_open_reclaim:XRPUSDT:SHORT:4h",
        "orb_fail_reversion:XRPUSDT:SHORT:4h",
        "double_top_neckline_break:BTCUSDT:SHORT:1h",
    }
    assert all(parse_approval_key(k) is not None for k in approved_keys)


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


def test_paper_plan_includes_every_disk_approved_research_key(monkeypatch) -> None:
    """Whatever is approved=True on disk must appear in the paper scan plan."""
    from config.universe import get_universe
    from core.execution.engine import build_plan

    get_universe.cache_clear()
    universe = get_universe()
    monkeypatch.setattr("core.execution.engine.get_universe", lambda: universe)
    monkeypatch.setattr("firm.research_jobs.paper_scan_family", lambda: "bb_squeeze_breakout")
    monkeypatch.setattr("firm.research_jobs._active_job_for", lambda family: None)
    plan = build_plan(require_approval=False, candidates=["BTCUSDT"])
    plan_ids = {
        (e.strategy.name, e.symbol, e.side.value, e.timeframe) for e in plan.entries
    }
    for key, rec in universe.approved_records:
        parsed = parse_approval_key(key)
        assert parsed is not None
        name, symbol, side = parsed
        rec_name = str(rec.get("strategy") or name).strip() or name
        tf = str(rec.get("timeframe") or "")
        assert (rec_name, symbol, side, tf) in plan_ids, f"missing approved sleeve {key}"


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
