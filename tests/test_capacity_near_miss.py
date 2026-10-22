"""Report-only near-miss rows for paper capacity rejections.

A fired signal that the risk layer turns down for the sector cap, the daily
trade cap, or the gross exposure cap is appended to a daily JSONL. The row
is not part of the rolling near-miss window. Nothing here places an order
or edits a limit.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from types import SimpleNamespace

import pandas as pd
import pytest

from config.settings import TradingMode
from core.execution.engine import PlanEntry, TradingEngine, TradingPlan
from core.risk.engine import (
    OpenPosition,
    PortfolioState,
    RiskEngine,
    RiskVerdict,
    TradeIntent,
)
from core.risk.killswitch import KillSwitch
from core.risk.limits import PAPER_LIMITS
from core.strategy.base import Signal, SignalSide
from firm.near_miss_log import (
    MAX_ROWS,
    RISK_REJECTION_MAX_ROWS,
    append_near_misses,
    read_capacity_rejections,
    read_near_misses,
)

WHEN = datetime(2026, 10, 20, 16, 1, tzinfo=timezone.utc)
EQUITY = 10_000.0


class _Sectors:
    """The candidate's sector. Open positions carry their own sector string."""

    def sector_of(self, symbol: str) -> str:
        del symbol
        return "other"


class _Ledger:
    def __init__(self, state: PortfolioState) -> None:
        self.state = state
        self.rejected: list[dict] = []

    def portfolio_state(self, equity: float, marks: dict | None = None) -> PortfolioState:
        del equity, marks
        return self.state

    def record_rejected_signal(self, **kwargs: object) -> None:
        self.rejected.append(kwargs)

    def record_risk_event(self, *args: object, **kwargs: object) -> None:
        del args, kwargs


class _Broker:
    def __init__(self) -> None:
        self.orders: list[dict] = []

    def place_market_order(self, **kwargs: object) -> None:
        self.orders.append(dict(kwargs))
        raise AssertionError("a rejected paper entry must not be ordered")


def _position(symbol: str, sector: str, notional: float) -> OpenPosition:
    return OpenPosition(
        symbol=symbol,
        side="LONG",
        quantity=notional / 100.0,
        entry_price=100.0,
        notional=notional,
        sector=sector,
    )


def _state(**overrides: object) -> PortfolioState:
    payload: dict = {
        "equity": EQUITY,
        "peak_equity": EQUITY,
        "open_positions": [],
        "trades_today": 0,
        "day": "2026-10-20",
    }
    payload.update(overrides)
    return PortfolioState(**payload)


def _signal(symbol: str = "ZECUSDT") -> Signal:
    return Signal(
        symbol=symbol,
        side=SignalSide.LONG,
        timestamp=pd.Timestamp("2026-10-20T12:00:00Z"),
        price=100.0,
        score=1.0,
        reason="fired",
        strategy="doji_star_reversal",
        take_profit_pct=0.05,
        stop_loss_pct=0.03,
    )


def _engine(
    state: PortfolioState,
    tmp_path,
    monkeypatch,
    universe: object | None = None,
) -> TradingEngine:
    # Default tests pin the sector lookup. Pass a real Universe to prove the
    # row uses sector_of, including SECTOR_OVERRIDES.
    source = _Sectors() if universe is None else universe
    monkeypatch.setattr("core.execution.engine.get_universe", lambda: source)
    monkeypatch.setattr(
        "core.execution.engine.get_settings",
        lambda: SimpleNamespace(trading_mode=TradingMode.PAPER),
    )
    monkeypatch.setattr("firm.near_miss_log.RISK_REJECTION_DIR", tmp_path / "near_miss_risk")
    monkeypatch.setattr("firm.near_miss_log._utcnow", lambda: WHEN)
    sleeve = SimpleNamespace(name="doji_star_reversal")
    plan = TradingPlan(
        entries=[
            PlanEntry(
                symbol="ZECUSDT",
                side=SignalSide.LONG,
                strategy=sleeve,  # type: ignore[arg-type]
                timeframe="1h",
            )
        ]
    )
    return TradingEngine(
        broker=_Broker(),  # type: ignore[arg-type]
        risk_engine=RiskEngine(
            limits=PAPER_LIMITS,
            kill_switch=KillSwitch(path=tmp_path / "kill.json"),
        ),
        ledger=_Ledger(state),  # type: ignore[arg-type]
        plan=plan,
        data_source=object(),  # type: ignore[arg-type]
    )


def _outcome(decision) -> tuple:
    return (
        decision.verdict,
        decision.quantity,
        decision.notional,
        decision.risk_amount,
        tuple(decision.reasons),
        tuple(decision.warnings),
        decision.is_approved,
    )


def _rows(tmp_path) -> list[dict]:
    return read_capacity_rejections(directory=tmp_path / "near_miss_risk")


def _assert_common(row: dict) -> None:
    assert row["kind"] == "capacity_rejection"
    assert row["ts"] == "2026-10-20T16:01:00+00:00"
    assert row["symbol"] == "ZECUSDT"
    assert row["sleeve"] == "doji_star_reversal"
    assert row["rule"] == "doji_star_reversal"
    assert row["clock"] == "1h"
    assert row["side"] == "LONG"
    assert row["sector"] == "other"
    assert row["sector_limit"] == PAPER_LIMITS.max_positions_per_sector == 2
    assert row["daily_trade_limit"] == PAPER_LIMITS.max_daily_trades == 20
    assert row["utc_day"] == "2026-10-20"
    assert row["equity"] == pytest.approx(EQUITY)
    assert row["notional_limit"] == pytest.approx(EQUITY * PAPER_LIMITS.max_total_exposure_pct)
    assert isinstance(row["reasons"], list)
    assert isinstance(row["reason_text"], list)
    assert row["reason_text"]  # the engine's own strings, not a truncated code


def test_sector_cap_rejection_records_count_and_proposed_size(tmp_path, monkeypatch) -> None:
    state = _state(
        open_positions=[
            _position("SOLUSDT", "other", 100.0),
            _position("AVAXUSDT", "other", 100.0),
        ]
    )
    engine = _engine(state, tmp_path, monkeypatch)
    decision = engine._attempt_entry(_signal(), EQUITY, {})

    assert decision.verdict is RiskVerdict.REJECTED
    assert decision.quantity == 0
    assert decision.notional == 0
    assert engine.broker.orders == []  # type: ignore[attr-defined]
    rows = _rows(tmp_path)
    assert len(rows) == 1
    row = rows[0]
    _assert_common(row)
    assert row["reasons"] == ["sector_cap"]
    assert any("sector" in text for text in row["reason_text"])
    assert row["sector_count"] == 2
    assert row["daily_trade_count"] == 0
    assert row["gross_exposure"] == pytest.approx(200.0)
    # 3% stop would size off risk to ~$3.3k; the 10% position cap binds first.
    # Exposure headroom is still open, so the proposed notional is that cap.
    assert row["proposed_notional"] == pytest.approx(EQUITY * PAPER_LIMITS.max_position_pct)


def test_near_miss_sector_uses_universe_sector_of(tmp_path, monkeypatch) -> None:
    """ZEC is layer1 via SECTOR_OVERRIDES, not the shared 'other' bucket."""
    from config.universe import Universe

    universe = Universe()
    assert universe.sector_of("ZECUSDT") == "layer1"
    assert universe.sector_of("PUMPFUNUSDT") == "emerging"
    assert universe.sector_of("DEXEUSDT") == "other"
    state = _state(
        open_positions=[
            _position("ADAUSDT", "layer1", 100.0),
            _position("AVAXUSDT", "layer1", 100.0),
        ]
    )
    engine = _engine(state, tmp_path, monkeypatch, universe=universe)
    decision = engine._attempt_entry(_signal("ZECUSDT"), EQUITY, {})

    assert decision.verdict is RiskVerdict.REJECTED
    assert decision.notional == 0
    assert any("sector 'layer1'" in reason for reason in decision.reasons)
    assert not any("sector 'other'" in reason for reason in decision.reasons)
    row = _rows(tmp_path)[0]
    assert row["symbol"] == "ZECUSDT"
    assert row["sector"] == universe.sector_of("ZECUSDT") == "layer1"
    assert row["sector_count"] == 2
    assert row["sector_limit"] == 2
    assert row["reasons"] == ["sector_cap"]


def test_max_daily_trades_rejection_records_the_utc_day(tmp_path, monkeypatch) -> None:
    state = _state(trades_today=PAPER_LIMITS.max_daily_trades)
    engine = _engine(state, tmp_path, monkeypatch)
    decision = engine._attempt_entry(_signal(), EQUITY, {})

    assert decision.verdict is RiskVerdict.REJECTED
    assert decision.notional == 0
    row = _rows(tmp_path)[0]
    _assert_common(row)
    assert row["reasons"] == ["max_daily_trades"]
    assert any("trades today" in text for text in row["reason_text"])
    assert row["daily_trade_count"] == 20
    assert row["daily_trade_limit"] == 20
    assert row["utc_day"] == "2026-10-20"
    assert row["sector_count"] == 0
    assert row["gross_exposure"] == pytest.approx(0.0)
    assert row["proposed_notional"] == pytest.approx(EQUITY * PAPER_LIMITS.max_position_pct)


def test_gross_exposure_rejection_records_exposure_before_the_entry(tmp_path, monkeypatch) -> None:
    state = _state(open_positions=[_position("SOLUSDT", "layer1", EQUITY * 0.80)])
    engine = _engine(state, tmp_path, monkeypatch)
    decision = engine._attempt_entry(_signal(), EQUITY, {})

    assert decision.verdict is RiskVerdict.REJECTED
    assert decision.notional == 0
    row = _rows(tmp_path)[0]
    _assert_common(row)
    assert row["reasons"] == ["max_total_exposure_pct"]
    assert any("total exposure" in text for text in row["reason_text"])
    assert row["gross_exposure"] == pytest.approx(EQUITY * 0.80)
    assert row["notional_limit"] == pytest.approx(EQUITY * 0.80)
    # Headroom under the gross cap is zero, so the sizer's proposal is zero.
    # The decision's own notional stays zero either way; this row is the log.
    assert row["proposed_notional"] == pytest.approx(0.0)
    assert row["sector_count"] == 0
    assert row["daily_trade_count"] == 0


def test_every_failing_capacity_reason_is_recorded(tmp_path, monkeypatch) -> None:
    """Two names already in the sector, the daily count full, and gross at the cap."""
    state = _state(
        trades_today=PAPER_LIMITS.max_daily_trades,
        open_positions=[
            _position("SOLUSDT", "other", EQUITY * 0.40),
            _position("AVAXUSDT", "other", EQUITY * 0.40),
        ],
    )
    engine = _engine(state, tmp_path, monkeypatch)
    decision = engine._attempt_entry(_signal(), EQUITY, {})

    assert decision.verdict is RiskVerdict.REJECTED
    assert len(decision.reasons) >= 3
    row = _rows(tmp_path)[0]
    _assert_common(row)
    assert row["reasons"] == [
        "max_daily_trades",
        "sector_cap",
        "max_total_exposure_pct",
    ]
    assert row["sector_count"] == 2
    assert row["daily_trade_count"] == 20
    assert row["gross_exposure"] == pytest.approx(EQUITY * 0.80)
    text = " ".join(row["reason_text"])
    assert "trades today" in text
    assert "sector" in text
    assert "total exposure" in text
    # The first reason is not the only one kept.
    assert row["reasons"][0] != row["reasons"][-1]
    assert len(row["reason_text"]) == len(decision.reasons)


def test_decision_matches_when_the_near_miss_write_raises(tmp_path, monkeypatch, caplog) -> None:
    state = _state(
        open_positions=[
            _position("SOLUSDT", "other", 100.0),
            _position("AVAXUSDT", "other", 100.0),
        ]
    )
    engine = _engine(state, tmp_path, monkeypatch)
    logged = engine._attempt_entry(_signal(), EQUITY, {})
    assert len(_rows(tmp_path)) == 1
    price = 100.0
    direct = engine.risk.evaluate(
        TradeIntent(
            symbol="ZECUSDT",
            side="LONG",
            entry_price=price,
            stop_price=price * (1.0 - 0.03),
            take_profit_price=price * (1.0 + 0.05),
            strategy="doji_star_reversal",
            score=1.0,
            sector="other",
        ),
        state,
    )
    assert _outcome(logged) == _outcome(direct)
    before = _outcome(logged)

    def _boom(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise OSError("forced log failure")

    monkeypatch.setattr("firm.near_miss_log._append_capacity_rejection", _boom)
    with caplog.at_level(logging.WARNING):
        forced = engine._attempt_entry(_signal(), EQUITY, {})

    assert _outcome(forced) == before
    assert _outcome(logged) == before
    assert forced.verdict is RiskVerdict.REJECTED
    assert forced.is_approved is False
    assert engine.broker.orders == []  # type: ignore[attr-defined]
    assert len(_rows(tmp_path)) == 1
    assert any("not written" in record.message for record in caplog.records)


def test_f111_paper_rejection_uses_the_same_capacity_log(tmp_path, monkeypatch) -> None:
    """F111 fills through its own risk.evaluate. The row is the same schema."""
    from core.execution.f111_paper import F111Runtime
    from core.strategy.f111_config import STRATEGY_ID

    state = _state(trades_today=PAPER_LIMITS.max_daily_trades)
    risk = RiskEngine(limits=PAPER_LIMITS, kill_switch=KillSwitch(path=tmp_path / "kill.json"))
    intent = TradeIntent(
        symbol="WLDUSDT",
        side="LONG",
        entry_price=100.0,
        stop_price=97.0,
        take_profit_price=105.0,
        strategy=STRATEGY_ID,
        score=1.0,
        sector="ai",
    )
    decision = risk.evaluate(intent, state)
    assert decision.verdict is RiskVerdict.REJECTED
    before = _outcome(decision)
    monkeypatch.setattr("firm.near_miss_log.RISK_REJECTION_DIR", tmp_path / "near_miss_risk")
    monkeypatch.setattr("firm.near_miss_log._utcnow", lambda: WHEN)
    monkeypatch.setattr(
        "config.settings.get_settings",
        lambda: SimpleNamespace(trading_mode=TradingMode.PAPER),
    )
    runtime = SimpleNamespace(
        config={"signal": {"timeframe": "1h"}},
        risk=risk,
    )
    F111Runtime._note_capacity_rejection(runtime, intent, state, decision)
    assert _outcome(decision) == before
    row = _rows(tmp_path)[0]
    assert row["symbol"] == "WLDUSDT"
    assert row["sleeve"] == STRATEGY_ID
    assert row["rule"] == STRATEGY_ID
    assert row["clock"] == "1h"
    assert row["reasons"] == ["max_daily_trades"]
    assert row["daily_trade_count"] == 20
    assert row["sector"] == "ai"
    assert row["utc_day"] == "2026-10-20"


def test_live_mode_does_not_write_a_capacity_row(tmp_path, monkeypatch) -> None:
    state = _state(trades_today=PAPER_LIMITS.max_daily_trades)
    engine = _engine(state, tmp_path, monkeypatch)
    monkeypatch.setattr(
        "core.execution.engine.get_settings",
        lambda: SimpleNamespace(trading_mode=TradingMode.LIVE),
    )
    decision = engine._attempt_entry(_signal(), EQUITY, {})
    assert decision.verdict is RiskVerdict.REJECTED
    assert _rows(tmp_path) == []


def test_a_non_capacity_rejection_is_not_a_near_miss_row(tmp_path, monkeypatch) -> None:
    state = _state(open_positions=[_position("ZECUSDT", "other", 100.0)])
    engine = _engine(state, tmp_path, monkeypatch)
    decision = engine._attempt_entry(_signal(), EQUITY, {})
    assert decision.verdict is RiskVerdict.REJECTED
    assert any("already holding" in reason for reason in decision.reasons)
    assert _rows(tmp_path) == []


def test_an_approved_entry_does_not_write_a_near_miss_row(tmp_path, monkeypatch) -> None:
    engine = _engine(_state(), tmp_path, monkeypatch)
    # The approval path reaches the broker. Fail the order so this test does
    # not need a fill, and so the near-miss file is the only thing observed.
    engine.broker.place_market_order = lambda **kwargs: SimpleNamespace(  # type: ignore[method-assign]
        success=False, error="stopped in the test", fill_price=None
    )
    decision = engine._attempt_entry(_signal(), EQUITY, {})
    assert decision.is_approved
    assert _rows(tmp_path) == []


def test_capacity_rows_survive_past_the_rolling_near_miss_window(tmp_path, monkeypatch) -> None:
    """241 rows stay. The rolling near-miss file still caps; this file does not."""
    directory = tmp_path / "near_miss_risk"
    monkeypatch.setattr("firm.near_miss_log.RISK_REJECTION_DIR", directory)
    monkeypatch.setattr("firm.near_miss_log._utcnow", lambda: WHEN)
    from firm.near_miss_log import record_capacity_rejection

    state = _state(trades_today=PAPER_LIMITS.max_daily_trades)
    intent = TradeIntent(
        symbol="ZECUSDT",
        side="LONG",
        entry_price=100.0,
        stop_price=97.0,
        strategy="doji_star_reversal",
        sector="other",
    )
    decision = RiskEngine(
        limits=PAPER_LIMITS,
        kill_switch=KillSwitch(path=tmp_path / "kill.json"),
    ).evaluate(intent, state)
    assert decision.verdict is RiskVerdict.REJECTED

    for index in range(241):
        intent = TradeIntent(
            symbol=f"S{index}USDT",
            side="LONG",
            entry_price=100.0,
            stop_price=97.0,
            strategy="doji_star_reversal",
            sector="other",
        )
        wrote = record_capacity_rejection(
            intent=intent,
            state=state,
            limits=PAPER_LIMITS,
            decision=decision,
            sleeve="doji_star_reversal",
            rule="doji_star_reversal",
            clock="1h",
            proposed_notional=1_000.0,
            now=WHEN,
            directory=directory,
        )
        assert wrote is True

    kept = read_capacity_rejections(directory=directory, day="2026-10-20")
    assert len(kept) == 241
    assert kept[0]["symbol"] == "S0USDT"
    assert kept[-1]["symbol"] == "S240USDT"
    assert kept[0]["reasons"] == ["max_daily_trades"]

    rolling = tmp_path / "near_miss_log.jsonl"
    burst = [
        {
            "symbol": f"N{index}USDT",
            "side": "LONG",
            "condition": "extension_gate",
            "normalized": 0.1,
            "gap": 0.1,
        }
        for index in range(MAX_ROWS + 25)
    ]
    bounded = append_near_misses(burst, scan_type="f111", bar_time=WHEN, now=WHEN, path=rolling)
    assert bounded == MAX_ROWS
    assert read_near_misses(now=WHEN, path=rolling)["count"] == MAX_ROWS
    # Filling and pruning the rolling log does not touch the daily file.
    assert len(read_capacity_rejections(directory=directory)) == 241
    assert "capacity_rejection" not in rolling.read_text(encoding="utf-8")


def test_daily_files_rotate_and_the_larger_cap_is_not_240(tmp_path, monkeypatch) -> None:
    directory = tmp_path / "near_miss_risk"
    monkeypatch.setattr("firm.near_miss_log.RISK_REJECTION_MAX_ROWS", 250)
    from firm.near_miss_log import record_capacity_rejection

    state = _state(trades_today=20)
    risk = RiskEngine(
        limits=PAPER_LIMITS,
        kill_switch=KillSwitch(path=tmp_path / "kill.json"),
    )
    probe = TradeIntent(
        symbol="ZECUSDT",
        side="LONG",
        entry_price=100.0,
        stop_price=97.0,
        strategy="ema_adx_trend",
        sector="other",
    )
    decision = risk.evaluate(probe, state)
    next_day = datetime(2026, 10, 21, 0, 5, tzinfo=timezone.utc)
    record_capacity_rejection(
        intent=probe,
        state=state,
        limits=PAPER_LIMITS,
        decision=decision,
        sleeve="ema_adx_trend",
        rule="ema_adx_trend",
        clock="4h",
        proposed_notional=1_000.0,
        now=next_day,
        directory=directory,
    )
    for index in range(260):
        intent = TradeIntent(
            symbol=f"D{index}USDT",
            side="SHORT",
            entry_price=100.0,
            stop_price=103.0,
            strategy="ema_adx_trend",
            sector="other",
        )
        record_capacity_rejection(
            intent=intent,
            state=state,
            limits=PAPER_LIMITS,
            decision=decision,
            sleeve="ema_adx_trend",
            rule="ema_adx_trend",
            clock="4h",
            proposed_notional=1_000.0,
            now=WHEN,
            directory=directory,
        )

    day_one = read_capacity_rejections(directory=directory, day="2026-10-20")
    day_two = read_capacity_rejections(directory=directory, day="2026-10-21")
    assert len(day_one) == 250
    assert day_one[0]["symbol"] == "D10USDT"
    assert day_one[-1]["symbol"] == "D259USDT"
    assert len(day_two) == 1
    assert day_two[0]["symbol"] == "ZECUSDT"
    assert day_two[0]["clock"] == "4h"
    # 241 would have fit. The cap that binds is the larger one, not 240.
    assert 241 < 250 < RISK_REJECTION_MAX_ROWS
    assert len(read_capacity_rejections(directory=directory)) == 251
