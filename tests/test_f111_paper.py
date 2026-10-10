"""F111 paper rules, registry, persistence, and the retired hourly entries.

Saved-path parity against the private checkpoint is not claimed. The skip at
the bottom states that explicitly when the archive is absent.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from config.settings import TradingMode, get_settings
from core.data.bybit_linear_instruments import (
    AVAILABLE,
    UNAVAILABLE,
    InstrumentStatus,
    classify_instrument_response,
)
from core.execution.broker import Instrument
from core.execution.engine import TradingEngine, TradingPlan, build_plan
from core.execution.f111_paper import F111Runtime, fresh_scan, retire_hourly_entry_records
from core.execution.paper import PaperBroker
from core.ledger.store import Ledger
from core.risk.engine import RiskEngine
from core.risk.killswitch import KillSwitch
from core.risk.limits import PAPER_LIMITS
from core.strategy.f111_config import (
    STRATEGY_ID,
    assert_f111_paper_only,
    assert_not_a_second_worker,
    configuration_sha256,
    load_f111_config,
    refuse_historical_backtest,
)
from core.strategy.f111_semantics import (
    RESEARCH_FEE,
    floor_move,
    gate_decision,
    new_protection_state,
    plan_retest,
    research_net,
    simulate_policy331,
    simulate_reference_floor,
    step_protection,
)
from research.costs import CostModel
from scripts.enable_hourly_btc_connors_loweff import desired_records
from tests.test_execution import StubDataSource

T0 = datetime(2024, 6, 1, 12, 0, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _isolated_settings():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _available(symbol: str = "BTCUSDT") -> InstrumentStatus:
    return InstrumentStatus(
        symbol=symbol,
        availability=AVAILABLE,
        reason="Trading",
        exchange_status="Trading",
        tick_size=0.01,
        qty_step=0.001,
        min_qty=0.001,
        min_notional=5.0,
    )


def _runtime(tmp_path: Path, **kwargs) -> F111Runtime:
    config, digest = load_f111_config()
    runtime = F111Runtime(
        config=config,
        config_sha=digest,
        state_path=tmp_path / "f111_state.json",
        telemetry_path=tmp_path / "f111_telemetry.jsonl",
        disable_flag=tmp_path / "f111_paper_scan_disabled",
        clock=lambda: T0,
        **kwargs,
    )
    runtime.registry["BTCUSDT"] = _available()
    return runtime


def _broker(prices: dict[str, float]) -> PaperBroker:
    return PaperBroker(
        starting_equity=10_000.0,
        costs=CostModel(slippage=0.0, taker_fee=RESEARCH_FEE, include_funding=False),
        data_source=StubDataSource(prices),
        lock_cost_model=True,
    )


def _risk(tmp_path: Path) -> RiskEngine:
    return RiskEngine(limits=PAPER_LIMITS, kill_switch=KillSwitch(tmp_path / "killswitch.json"))


def _pass_signal(runtime: F111Runtime, **overrides):
    payload = dict(
        symbol="BTCUSDT",
        side="LONG",
        t0=T0,
        boundary=100.0,
        # 1.02 / 101 clears the 0.01 ATR/close gate. A fill near 101 then
        # puts a later 105 quote between the 1.25R arm and the 4 ATR target.
        prior_atr=1.02,
        close=101.0,
        compression=0.6,
        extension_atr=0.4,
        base_passed=True,
        observed_at=T0,
    )
    payload.update(overrides)
    return runtime.observe_signal(**payload)


def test_config_hash_thresholds_and_unverified_parity():
    config, digest = load_f111_config()
    assert digest == configuration_sha256()
    assert len(digest) == 64
    gates = config["signal"]["extra_gates"]
    assert gates["compression_strictly_greater_than"] == 0.5
    assert gates["original_signal_extension_prior_atr_max"] == 1.0
    assert gates["prior_atr_over_signal_close_min"] == 0.01
    assert config["entry"]["expiry_minutes"] == 60
    assert config["exits"]["initial_stop_prior_atr"] == 3
    assert config["exits"]["target_prior_atr"] == 4
    assert config["exits"]["activation_original_R"] == 1.25
    assert config["exits"]["intended_floor_original_R"] == 0.25
    assert config["live_authorized"] is False
    assert config["historical_2026_backtest_opened"] is False
    assert config["saved_path_parity"] == "UNVERIFIED"
    assert len(config["universe"]) == 96
    assert config["expected_scan_sleeves"] == 192
    text = (ROOT / "config" / "approved_strategies.json").read_text(encoding="utf-8")
    assert STRATEGY_ID not in text


def test_gate_equality_edges():
    assert gate_decision(compression=0.5, extension_atr=1.0, prior_atr=1.0, close=100.0) == (
        False,
        "compression_gate",
    )
    assert gate_decision(compression=0.5 + 1e-12, extension_atr=1.0, prior_atr=1.0, close=100.0)[0]
    assert gate_decision(compression=0.6, extension_atr=1.0, prior_atr=1.0, close=100.0)[0]
    assert gate_decision(compression=0.6, extension_atr=1.0 + 1e-9, prior_atr=1.0, close=100.0)[1] == (
        "extension_gate"
    )
    assert gate_decision(compression=0.6, extension_atr=0.2, prior_atr=1.0, close=100.0)[0]
    assert gate_decision(compression=0.6, extension_atr=0.2, prior_atr=0.999, close=100.0)[1] == (
        "high_vol_filter"
    )
    assert gate_decision(compression=0.6, extension_atr=0.2, prior_atr=1.0, close=100.0)[0]
    assert gate_decision(compression=float("nan"), extension_atr=0.2, prior_atr=1.0, close=100.0)[1] == (
        "missing_feature"
    )


def test_retest_fixtures_match_the_reference_planner():
    high = np.array([102.0, 102.0, 102.0, 102.0])
    low = np.array([101.0, 100.0, 99.0, 99.0])
    close = np.array([101.0, 100.0, 101.0, 101.0])
    # Boundary equality is not a strict reclaim.
    assert plan_retest(high, low, close, 0, 1, 100.0, 2)[0] == -1
    # The last completed minute of the window can fill the next open.
    assert plan_retest(high, low, close, 0, 1, 100.0, 3) == (3, "filled")
    assert plan_retest(high, low, close, 0, 1, 100.0, 9) == (3, "filled")
    # The last close has no following open, so it is not a confirmation.
    assert plan_retest(high, low, np.array([101.0, 100.0, 100.0, 101.0]), 0, 1, 100.0, 9)[0] == -1
    short = plan_retest(
        np.array([101.0, 101.0, 101.0]),
        np.array([99.0, 99.0, 99.0]),
        np.array([99.0, 99.0, 99.0]),
        0,
        -1,
        100.0,
        1,
    )
    assert short == (1, "filled")


def test_same_minute_touch_reclaim_no_touch_expiry_and_final_minute(tmp_path):
    runtime = _runtime(tmp_path)
    _pass_signal(runtime)
    # Touch and strict reclaim on the first minute. Fill is the next minute.
    runtime.observe_minute(
        symbol="BTCUSDT", minute=T0, high=102, low=99, close=101, quote=101, quote_time=T0, observed_at=T0
    )
    assert runtime.pending[0]["status"] == "scheduled"
    assert runtime.pending[0]["touch_time"] == runtime.pending[0]["reclaim_time"]
    assert runtime.pending[0]["action_time"] == (T0 + timedelta(minutes=1)).isoformat()

    quiet = _runtime(tmp_path / "quiet")
    _pass_signal(quiet)
    for offset in range(60):
        quiet.observe_minute(
            symbol="BTCUSDT",
            minute=T0 + timedelta(minutes=offset),
            high=102,
            low=101,
            close=101.5,
            quote=101.5,
            quote_time=T0 + timedelta(minutes=offset),
            observed_at=T0 + timedelta(minutes=offset),
        )
    assert quiet.pending[0]["status"] == "rejected"
    assert quiet.pending[0]["rejection_reason"] == "no_touch"

    touched = _runtime(tmp_path / "touched")
    _pass_signal(touched)
    for offset in range(60):
        touched.observe_minute(
            symbol="BTCUSDT",
            minute=T0 + timedelta(minutes=offset),
            high=102,
            low=100,
            close=100,  # on the boundary: touch, not reclaim
            quote=100,
            quote_time=T0 + timedelta(minutes=offset),
            observed_at=T0 + timedelta(minutes=offset),
        )
    assert touched.pending[0]["rejection_reason"] == "no_reclaim"

    final = _runtime(tmp_path / "final")
    _pass_signal(final)
    for offset in range(59):
        final.observe_minute(
            symbol="BTCUSDT",
            minute=T0 + timedelta(minutes=offset),
            high=102,
            low=101,
            close=101,
            quote=101,
            quote_time=T0 + timedelta(minutes=offset),
            observed_at=T0 + timedelta(minutes=offset),
        )
    final.observe_minute(
        symbol="BTCUSDT",
        minute=T0 + timedelta(minutes=59),
        high=102,
        low=99,
        close=101,
        quote=101,
        quote_time=T0 + timedelta(minutes=59),
        observed_at=T0 + timedelta(minutes=59),
    )
    assert final.pending[0]["status"] == "scheduled"
    assert final.pending[0]["action_time"] == (T0 + timedelta(minutes=60)).isoformat()


def test_missing_minute_and_stale_quote_do_not_fill(tmp_path):
    missing = _runtime(tmp_path / "missing")
    _pass_signal(missing)
    missing.observe_minute(
        symbol="BTCUSDT",
        minute=T0 + timedelta(minutes=2),
        high=102,
        low=99,
        close=101,
        quote=101,
        quote_time=T0 + timedelta(minutes=2),
        observed_at=T0 + timedelta(minutes=2),
    )
    assert missing.pending[0]["rejection_reason"] == "missing_candle_or_quote"
    assert missing.events[-1]["missing_candle_or_quote"] is True

    stale = _runtime(tmp_path / "stale")
    prices = {"BTCUSDT": 101.0}
    stale.broker = _broker(prices)
    stale.risk = _risk(tmp_path / "stale")
    _pass_signal(stale)
    stale.observe_minute(
        symbol="BTCUSDT", minute=T0, high=102, low=99, close=101, quote=101, quote_time=T0, observed_at=T0
    )
    action = T0 + timedelta(minutes=1)
    stale.observe_minute(
        symbol="BTCUSDT",
        minute=action,
        high=102,
        low=100,
        close=101,
        quote=101,
        quote_time=action,
        observed_at=action + timedelta(minutes=2),
    )
    assert stale.pending[0]["rejection_reason"] == "stale_action"
    assert stale.broker.get_positions() == []
    assert stale.events[-1]["configuration_sha256"] == configuration_sha256()


def test_opposite_signals_are_not_cancelled_and_same_action_is_rejected(tmp_path):
    runtime = _runtime(tmp_path)
    runtime.registry["ETHUSDT"] = _available("ETHUSDT")
    _pass_signal(runtime, symbol="ETHUSDT", side="LONG")
    _pass_signal(runtime, symbol="ETHUSDT", side="SHORT", boundary=100.0, close=99.0)
    assert len(runtime.pending) == 2
    # One minute that touches and reclaims both boundaries.
    runtime.observe_minute(
        symbol="ETHUSDT", minute=T0, high=101, low=99, close=100.5, quote=100.5, quote_time=T0, observed_at=T0
    )
    # Short reclaim needs close below 100. This bar reclaimed only the long.
    assert runtime.pending[0]["status"] == "scheduled"
    assert runtime.pending[1]["status"] == "watching"
    runtime.observe_minute(
        symbol="ETHUSDT",
        minute=T0 + timedelta(minutes=1),
        high=101,
        low=99,
        close=99.5,
        quote=99.5,
        quote_time=T0 + timedelta(minutes=1),
        observed_at=T0 + timedelta(minutes=1),
    )
    # The long's action minute is the short's reclaim minute. The short stays
    # pending for its own next minute. Nothing cancels the other side.
    assert runtime.pending[1]["status"] == "scheduled"
    assert runtime.pending[1]["side"] == "SHORT"
    assert runtime.pending[0]["rejection_reason"] == "paper broker or risk engine not attached"
    assert all("cancel" not in (row["rejection_reason"] or "") for row in runtime.events)


def test_simultaneous_opposite_entries_place_no_order(tmp_path):
    runtime = _runtime(tmp_path)
    prices = {"BTCUSDT": 100.0}
    runtime.broker = _broker(prices)
    runtime.risk = _risk(tmp_path)
    _pass_signal(runtime, side="LONG")
    _pass_signal(runtime, side="SHORT")
    for pending in runtime.pending:
        pending["status"] = "scheduled"
        pending["action_time"] = (T0 + timedelta(minutes=1)).isoformat()
        pending["next_minute"] = pending["action_time"]
        pending["touched"] = True
        pending["reclaim_time"] = T0.isoformat()
    action = T0 + timedelta(minutes=1)
    runtime.observe_minute(
        symbol="BTCUSDT",
        minute=action,
        high=100,
        low=100,
        close=100,
        quote=100,
        quote_time=action,
        observed_at=action,
    )
    assert runtime.broker.get_positions() == []
    reasons = {row["rejection_reason"] for row in runtime.events}
    assert "simultaneous_opposite_entries" in reasons


def test_restart_keeps_touch_reclaim_fill_and_protection(tmp_path):
    prices = {"BTCUSDT": 101.0}
    first = _runtime(tmp_path, broker=_broker(prices), risk=_risk(tmp_path))
    _pass_signal(first)
    first.observe_minute(
        symbol="BTCUSDT", minute=T0, high=101, low=99, close=100, quote=100, quote_time=T0, observed_at=T0
    )
    first.persist()
    second = _runtime(tmp_path, broker=first.broker, risk=first.risk)
    second.restore()
    assert second.pending[0]["touched"] is True
    assert second.pending[0]["reclaim_time"] is None
    second.observe_minute(
        symbol="BTCUSDT",
        minute=T0 + timedelta(minutes=1),
        high=102,
        low=99,
        close=101,
        quote=101,
        quote_time=T0 + timedelta(minutes=1),
        observed_at=T0 + timedelta(minutes=1),
    )
    assert second.pending[0]["status"] == "scheduled"
    second.persist()
    third = _runtime(tmp_path, broker=first.broker, risk=first.risk)
    third.restore()
    assert third.pending[0]["reclaim_time"] is not None
    action = T0 + timedelta(minutes=2)
    third.observe_minute(
        symbol="BTCUSDT",
        minute=action,
        high=102,
        low=100,
        close=101,
        quote=101,
        quote_time=action,
        observed_at=action,
    )
    assert third.pending[0]["status"] == "filled"
    assert "BTCUSDT" in third.protection
    assert third.protection["BTCUSDT"]["armed"] is False
    third.persist()
    fourth = _runtime(tmp_path, broker=first.broker, risk=first.risk)
    fourth.restore()
    assert fourth.protection["BTCUSDT"]["initial_stop"] == third.protection["BTCUSDT"]["initial_stop"]
    # A favourable quote arms on this sample. The tighter stop is not effective yet.
    fourth.observe_minute(
        symbol="BTCUSDT",
        minute=action + timedelta(minutes=1),
        high=110,
        low=104,
        close=105,
        quote=105,
        quote_time=action + timedelta(minutes=1),
        observed_at=action + timedelta(minutes=1),
        funding_fraction=0.0,
        funding_source="test",
    )
    assert fourth.protection["BTCUSDT"]["armed"] is True
    assert fourth.protection["BTCUSDT"]["effective_level"] == pytest.approx(
        -fourth.protection["BTCUSDT"]["stop_return"]
    )
    fourth.persist()
    fifth = _runtime(tmp_path, broker=first.broker, risk=first.risk)
    fifth.restore()
    assert fifth.protection["BTCUSDT"]["armed"] is True
    fifth.observe_minute(
        symbol="BTCUSDT",
        minute=action + timedelta(minutes=2),
        high=110,
        low=104,
        close=105,
        quote=105,
        quote_time=action + timedelta(minutes=2),
        observed_at=action + timedelta(minutes=2),
        funding_fraction=0.0,
        funding_source="test",
    )
    assert fifth.protection["BTCUSDT"]["effective_level"] > -fifth.protection["BTCUSDT"]["stop_return"]


def test_no_same_timestamp_reentry_and_no_duplicate_cash(tmp_path):
    prices = {"BTCUSDT": 101.0}
    broker = _broker(prices)
    runtime = _runtime(tmp_path, broker=broker, risk=_risk(tmp_path))
    _pass_signal(runtime)
    runtime.observe_minute(
        symbol="BTCUSDT", minute=T0, high=102, low=99, close=101, quote=101, quote_time=T0, observed_at=T0
    )
    action = T0 + timedelta(minutes=1)
    runtime.observe_minute(
        symbol="BTCUSDT", minute=action, high=102, low=100, close=101, quote=101, quote_time=action, observed_at=action
    )
    assert len(broker.get_positions()) == 1
    cash_after_one = broker.cash
    fees_after_one = broker.total_fees
    assert fees_after_one > 0
    # A second entry at the same timestamp is refused. Cash is not charged again.
    runtime.last_exit["BTCUSDT"] = action.isoformat()
    extra = dict(runtime.pending[0])
    extra["status"] = "scheduled"
    extra["source_signal_id"] = "second"
    extra["action_time"] = action.isoformat()
    extra["next_minute"] = action.isoformat()
    runtime.pending.append(extra)
    runtime.observe_minute(
        symbol="BTCUSDT", minute=action, high=102, low=100, close=101, quote=101, quote_time=action, observed_at=action
    )
    assert broker.cash == cash_after_one
    assert broker.total_fees == fees_after_one
    assert len(broker.get_positions()) == 1
    assert any(row["rejection_reason"] == "same_timestamp_reentry" for row in runtime.events)


def test_fees_on_both_legs_and_gap_through_stop(tmp_path):
    net = research_net(100.0, 110.0, 1, 0.001)
    assert net["fees"] == pytest.approx(RESEARCH_FEE * (1.0 + 1.1))
    assert net["net_return"] == pytest.approx(net["gross_return"] - net["fees"] - 0.001)
    credit = research_net(100.0, 110.0, 1, -0.002)
    assert credit["net_return"] > net["net_return"]

    prices = {"BTCUSDT": 101.0}
    broker = _broker(prices)
    runtime = _runtime(tmp_path, broker=broker, risk=_risk(tmp_path))
    _pass_signal(runtime)
    runtime.observe_minute(
        symbol="BTCUSDT", minute=T0, high=102, low=99, close=101, quote=101, quote_time=T0, observed_at=T0
    )
    action = T0 + timedelta(minutes=1)
    runtime.observe_minute(
        symbol="BTCUSDT", minute=action, high=102, low=100, close=101, quote=101, quote_time=action, observed_at=action
    )
    entry_fee = runtime.protection["BTCUSDT"]["entry_fee"]
    assert entry_fee > 0
    # Gap through the 3 ATR stop. The fill is the sampled quote, not the stop.
    gap_minute = action + timedelta(minutes=1)
    prices["BTCUSDT"] = 90.0
    runtime.observe_minute(
        symbol="BTCUSDT",
        minute=gap_minute,
        high=90,
        low=90,
        close=90,
        quote=90,
        quote_time=gap_minute,
        observed_at=gap_minute,
        funding_fraction=0.0,
        funding_source="test",
    )
    exit_event = runtime.events[-1]
    assert exit_event["entry_fee"] == pytest.approx(entry_fee)
    assert exit_event["exit_fee"] > 0
    assert exit_event["simulated_fill"] == pytest.approx(90.0)
    assert exit_event["initial_stop"] > 90.0
    assert broker.get_positions() == []
    assert broker.total_fees == pytest.approx(entry_fee + exit_event["exit_fee"])


def test_stop_before_target_and_protection_waits_a_minute():
    state = new_protection_state(entry_price=100.0, side=1, prior_atr=1.0, quantity=1.0, entry_fee=0.0)
    state["effective_level"] = 0.10
    state["decided_level"] = 0.10
    state["target_return"] = 0.05
    state["armed"] = True
    _updated, exit_row = step_protection(state, 108.0, funding_fraction=0.0, fee=RESEARCH_FEE, sample_id="both")
    assert exit_row is not None
    assert exit_row["reason"] == 4

    fresh = new_protection_state(entry_price=100.0, side=1, prior_atr=1.0, quantity=1.0, entry_fee=0.0)
    # 103.9 is past the 1.25R arm (103.75) and short of the 4 ATR target (104).
    armed, no_exit = step_protection(fresh, 103.9, funding_fraction=0.0, fee=RESEARCH_FEE, sample_id="arm")
    assert no_exit is None and armed["armed"] is True
    assert armed["effective_level"] == pytest.approx(-fresh["stop_return"])
    assert armed["decided_level"] > armed["effective_level"]

    spiked = new_protection_state(entry_price=100.0, side=1, prior_atr=1.0, quantity=1.0, entry_fee=0.0)
    spiked["armed"] = True
    spiked["best_move"] = 0.05
    spiked["effective_level"] = 0.01
    spiked["decided_level"] = 0.01
    held, not_yet = step_protection(spiked, 102.0, funding_fraction=0.2, fee=RESEARCH_FEE, sample_id="decide")
    assert not_yet is None
    assert held["decided_level"] > 0.01
    _tight, stopped = step_protection(held, 102.0, funding_fraction=0.2, fee=RESEARCH_FEE, sample_id="effective")
    assert stopped is not None and stopped["reason"] == 4

    debit = floor_move(1, RESEARCH_FEE, 0.01, 0.0075)
    credit = floor_move(1, RESEARCH_FEE, -0.01, 0.0075)
    assert debit > credit
    loose = new_protection_state(entry_price=100.0, side=1, prior_atr=1.0, quantity=1.0, entry_fee=0.0)
    loose["armed"] = True
    loose["best_move"] = 0.2
    loose["decided_level"] = debit
    loose["effective_level"] = -loose["stop_return"]
    kept, _none = step_protection(loose, 101.0, funding_fraction=-0.05, fee=RESEARCH_FEE, sample_id="credit")
    assert kept["decided_level"] == pytest.approx(debit)

    path = simulate_policy331(
        np.array([100.0, 100.0, 80.0]),
        0,
        1,
        1.0,
        funding_fraction=np.zeros(3),
    )
    assert path["reason"] == 1
    assert path["quote"] == 80.0
    short = simulate_policy331(
        np.array([100.0, 130.0]),
        0,
        -1,
        1.0,
        funding_fraction=np.zeros(2),
    )
    assert short["reason"] == 1
    assert short["quote"] == 130.0
    reference = simulate_reference_floor(
        np.array([100.0, 100.0, 80.0]),
        np.zeros(3),
        0,
        1,
        path["state"]["stop_return"],
        path["state"]["target_return"],
        1.25 * path["state"]["stop_return"],
        0.25 * path["state"]["stop_return"],
    )
    assert reference[0] == path["exit_i"]
    assert reference[2] == path["reason"]


def test_missing_funding_is_not_zero(tmp_path):
    prices = {"BTCUSDT": 101.0}
    runtime = _runtime(tmp_path, broker=_broker(prices), risk=_risk(tmp_path))
    _pass_signal(runtime)
    runtime.observe_minute(
        symbol="BTCUSDT", minute=T0, high=102, low=99, close=101, quote=101, quote_time=T0, observed_at=T0
    )
    action = T0 + timedelta(minutes=1)
    runtime.observe_minute(
        symbol="BTCUSDT", minute=action, high=102, low=100, close=101, quote=101, quote_time=action, observed_at=action
    )
    level_before = runtime.protection["BTCUSDT"]["decided_level"]
    runtime.observe_minute(
        symbol="BTCUSDT",
        minute=action + timedelta(minutes=1),
        high=110,
        low=104,
        close=105,
        quote=105,
        quote_time=action + timedelta(minutes=1),
        observed_at=action + timedelta(minutes=1),
        funding_fraction=None,
        funding_source=None,
    )
    assert runtime.protection["BTCUSDT"]["armed"] is False
    assert runtime.protection["BTCUSDT"]["decided_level"] == pytest.approx(level_before)
    assert runtime.events[-1]["rejection_reason"] == "funding_missing"


def test_risk_rejection_is_not_hidden_as_a_strategy_gate(tmp_path):
    prices = {"BTCUSDT": 101.0}
    runtime = _runtime(tmp_path, broker=_broker(prices), risk=_risk(tmp_path))
    # 3 ATR is 60% of price, past the portfolio stop-distance limit.
    _pass_signal(runtime, prior_atr=20.0, close=101.0)
    runtime.observe_minute(
        symbol="BTCUSDT", minute=T0, high=102, low=99, close=101, quote=101, quote_time=T0, observed_at=T0
    )
    action = T0 + timedelta(minutes=1)
    runtime.observe_minute(
        symbol="BTCUSDT", minute=action, high=102, low=100, close=101, quote=101, quote_time=action, observed_at=action
    )
    rejected = runtime.events[-1]
    assert rejected["gate_decision"] is True
    assert rejected["occupancy_or_risk_rejection"]
    assert "stop" in rejected["rejection_reason"]
    assert runtime.broker.get_positions() == []


def test_strategy_preserves_the_parent_and_adds_f111_gates(monkeypatch):
    from core.strategy.hourly_compression_btc_connors_loweff_v1 import (
        HourlyCompressionBtcConnorsLoweffV1Strategy,
    )
    from core.strategy.mar_f111_r12_extension_latefloor_v1 import (
        MarF111R12ExtensionLatefloorV1Strategy,
    )

    index = pd.date_range("2024-06-01", periods=4, freq="h", tz="UTC")
    candles = pd.DataFrame(
        {"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 1.0},
        index=index,
    )

    def parent(self, frame):
        out = self.empty_signals(frame)
        out["compression"] = 0.6
        out["prior_atr"] = 2.0
        out["extension_atr"] = self._extension
        out["entry_boundary"] = 90.0
        if self._emit:
            out.loc[out.index[-1], "signal"] = self.params.side.sign
            out.loc[out.index[-1], "side"] = self.params.side.value
            out.loc[out.index[-1], "score"] = 1.0
            out.loc[out.index[-1], "reason"] = "parent"
        return out

    monkeypatch.setattr(HourlyCompressionBtcConnorsLoweffV1Strategy, "generate_signals", parent)
    rule = MarF111R12ExtensionLatefloorV1Strategy()
    rule._extension = 2.0
    rule._emit = True
    blocked = rule.generate_signals(candles)
    assert int(blocked["signal"].iloc[-1]) == 0
    assert blocked["f111_rejection_reason"].iloc[-1] == "extension_gate"

    rule._extension = 0.5
    kept = rule.generate_signals(candles)
    assert int(kept["signal"].iloc[-1]) == 1
    assert kept["f111_rejection_reason"].iloc[-1] == ""

    rule._emit = False
    rule._extension = 0.5
    base_blocked = rule.generate_signals(candles)
    assert int(base_blocked["signal"].iloc[-1]) == 0
    assert base_blocked["f111_rejection_reason"].iloc[-1] == "base_signal_blocked"
    assert rule.latest_signal("BTCUSDT", candles) is None


def test_paper_only_enforcement(monkeypatch):
    monkeypatch.setenv("TRADING_MODE", "testnet")
    get_settings.cache_clear()
    with pytest.raises(RuntimeError, match="not paper"):
        assert_f111_paper_only()

    monkeypatch.setenv("TRADING_MODE", "live")
    monkeypatch.setenv("GO_LIVE_CONFIRMED", "I_ACCEPT_THE_RISK")
    monkeypatch.setenv("BYBIT_LIVE_API_KEY", "test-key")
    monkeypatch.setenv("BYBIT_LIVE_API_SECRET", "test-secret")
    get_settings.cache_clear()
    assert get_settings().trading_mode is TradingMode.LIVE
    with pytest.raises(RuntimeError, match="not paper"):
        assert_f111_paper_only()

    monkeypatch.setenv("TRADING_MODE", "paper")
    monkeypatch.setenv("GO_LIVE_CONFIRMED", "I_ACCEPT_THE_RISK")
    get_settings.cache_clear()
    with pytest.raises(RuntimeError, match="live confirmation"):
        assert_f111_paper_only()

    with pytest.raises(RuntimeError, match="2026"):
        refuse_historical_backtest(True)
    refuse_historical_backtest(False)


def test_live_and_paper_plans_cannot_select_f111(monkeypatch):
    from config.universe import Universe
    import core.execution.engine as engine

    record = {
        "strategy": STRATEGY_ID,
        "timeframe": "1h",
        "approved": True,
        "paper_override": True,
        "params": {},
    }
    approvals = {f"{STRATEGY_ID}:BTCUSDT:LONG:1h": record, f"{STRATEGY_ID}:BTCUSDT:SHORT:1h": record}
    monkeypatch.setattr(engine, "get_universe", lambda: Universe(approvals=approvals))
    monkeypatch.setattr("core.data.soko_trend.read_live_soko_trend", lambda: "chop")
    live = build_plan(require_approval=True)
    paper = build_plan(require_approval=False)
    assert all(entry.strategy.name != STRATEGY_ID for entry in live.entries)
    assert all(entry.strategy.name != STRATEGY_ID for entry in paper.entries)


def test_registry_unavailable_is_explicit_and_not_aliased():
    missing = classify_instrument_response("AKROUSDT", {"retCode": 0, "result": {"list": []}})
    assert missing.availability == UNAVAILABLE
    assert missing.reason == "not listed on Bybit linear"
    closed = classify_instrument_response(
        "MATICUSDT",
        {
            "retCode": 0,
            "result": {
                "list": [
                    {
                        "symbol": "MATICUSDT",
                        "status": "Closed",
                        "priceFilter": {"tickSize": "0.0001"},
                        "lotSizeFilter": {"qtyStep": "1", "minOrderQty": "1", "minNotionalValue": "5"},
                    }
                ]
            },
        },
    )
    assert closed.availability == UNAVAILABLE
    assert "Closed" in closed.reason
    mismatch = classify_instrument_response(
        "SHIB1000USDT",
        {
            "retCode": 0,
            "result": {
                "list": [
                    {
                        "symbol": "1000SHIBUSDT",
                        "status": "Trading",
                        "priceFilter": {"tickSize": "0.0001"},
                        "lotSizeFilter": {"qtyStep": "1", "minOrderQty": "1", "minNotionalValue": "5"},
                    }
                ]
            },
        },
    )
    assert mismatch.availability == UNAVAILABLE
    assert mismatch.symbol == "SHIB1000USDT"
    assert "1000SHIBUSDT" in mismatch.reason
    assert mismatch.returned_symbol == "1000SHIBUSDT"
    down = classify_instrument_response("BTCUSDT", None, error="HTTP 403")
    assert down.availability == UNAVAILABLE
    assert down.reason.startswith("instruments-info unreachable")

    config, _digest = load_f111_config()
    registry = []
    for symbol in config["universe"]:
        if symbol == "SHIB1000USDT":
            registry.append(mismatch)
        elif symbol == "AKROUSDT":
            registry.append(missing)
        elif symbol == "MATICUSDT":
            registry.append(closed)
        else:
            registry.append(_available(symbol))
    report = fresh_scan(registry=registry)
    assert report["sleeves_evaluated"] == 192
    assert report["orders_placed"] == 0
    assert report["available_symbols"] == 93
    assert report["unavailable_symbols"] == 3
    reasons = {item["symbol"]: item["reason"] for item in report["unavailable"]}
    assert reasons["SHIB1000USDT"].startswith("symbol mismatch")
    assert reasons["AKROUSDT"] == "not listed on Bybit linear"
    assert "Closed" in reasons["MATICUSDT"]
    assert {row["symbol"] for row in report["rows"]} == set(config["universe"])
    assert all(row["feature_values"]["evaluated"] is True for row in report["rows"])


def test_scan_does_not_start_a_second_worker(tmp_path, monkeypatch):
    pid = tmp_path / "paper.pid"
    pid.write_text("4242")
    monkeypatch.setattr("firm.locks.PAPER_PID_PATH", pid)
    with pytest.raises(RuntimeError, match="duplicate paper worker"):
        assert_not_a_second_worker(True)
    config, _digest = load_f111_config()
    report = fresh_scan(registry=[_available(symbol) for symbol in config["universe"]])
    assert report["sleeves_evaluated"] == 192
    assert pid.read_text() == "4242"
    assert_not_a_second_worker(False)


def test_retired_hourly_entries_keep_exit_supervision(tmp_path, monkeypatch, firm_db):
    from core.execution import engine as engine_mod

    book = {"_meta": "keep", **desired_records()}
    updated, removed = retire_hourly_entry_records(book)
    assert "_meta" in updated
    assert len(removed) == 6
    assert all(STRATEGY_ID not in key for key in updated)
    assert not any(str(value.get("strategy", "")).startswith("hourly_compression") for value in updated.values() if isinstance(value, dict))

    prices = {"BTCUSDT": 100.0}
    broker = PaperBroker(
        starting_equity=10_000.0,
        costs=CostModel(slippage=0.0, include_funding=False),
        data_source=StubDataSource(prices),
        lock_cost_model=True,
    )
    monkeypatch.setattr(engine_mod, "LAST_CYCLE_PATH", tmp_path / "last_cycle.json")
    ledger = Ledger(mode="paper", starting_equity=10_000.0)
    opened = broker.place_market_order("BTCUSDT", "LONG", 0.1, expected_price=100.0)
    assert opened.success
    broker.set_stops("BTCUSDT", take_profit=110.0, stop_loss=97.0)
    ledger.open_position(
        symbol="BTCUSDT",
        side="LONG",
        quantity=opened.filled_quantity or 0.01,
        entry_price=opened.fill_price,
        expected_entry_price=100.0,
        take_profit=110.0,
        stop_loss=97.0,
        strategy="hourly_compression_btc_connors_loweff_v1",
        sector="majors",
        signal_score=1.0,
        signal_reason="legacy hourly",
        broker_order_id=opened.order_id or "paper-legacy",
        entry_fee=opened.fee or 0.0,
    )
    engine = TradingEngine(
        broker=broker,
        risk_engine=_risk(tmp_path),
        ledger=ledger,
        plan=TradingPlan(),
        data_source=None,
    )
    # Retirement does not convert or close the open hourly position.
    assert ledger.open_positions()[0].strategy == "hourly_compression_btc_connors_loweff_v1"
    assert broker._positions["BTCUSDT"].stop_loss == pytest.approx(97.0)
    prices["BTCUSDT"] = 96.0
    closed = engine.supervise_exits()
    assert closed == 1
    assert broker.get_positions() == []
    assert ledger.open_positions() == []


def test_enable_script_does_not_reset_cash_or_add_f111(tmp_path, monkeypatch):
    from scripts.enable_f111_paper import main

    book = tmp_path / "approved_strategies.json"
    book.write_text(json.dumps({"_meta": "keep", **desired_records()}), encoding="utf-8")
    cash = tmp_path / "paper_cash.json"
    cash.write_text('{"cash": 12345}', encoding="utf-8")
    assert main(["--book", str(book)]) == 0
    assert json.loads(book.read_text())["BTCUSDT"] if False else "hourly_compression_btc_connors_loweff_v1" in book.read_text()
    assert main(["--book", str(book), "--apply"]) == 0
    updated = json.loads(book.read_text())
    assert "_meta" in updated
    assert STRATEGY_ID not in book.read_text()
    assert "hourly_compression" not in book.read_text()
    assert cash.read_text() == '{"cash": 12345}'
    backups = list(tmp_path.glob("approved_strategies.json.before-f111-*"))
    assert len(backups) == 1
    assert "hourly_compression_btc_connors_loweff_v1" in backups[0].read_text()


def test_operator_flag_stops_new_entries_without_closing(tmp_path):
    prices = {"BTCUSDT": 101.0}
    broker = _broker(prices)
    runtime = _runtime(tmp_path, broker=broker, risk=_risk(tmp_path))
    _pass_signal(runtime)
    runtime.observe_minute(
        symbol="BTCUSDT", minute=T0, high=102, low=99, close=101, quote=101, quote_time=T0, observed_at=T0
    )
    action = T0 + timedelta(minutes=1)
    runtime.observe_minute(
        symbol="BTCUSDT", minute=action, high=102, low=100, close=101, quote=101, quote_time=action, observed_at=action
    )
    assert len(broker.get_positions()) == 1
    flag = tmp_path / "f111_paper_scan_disabled"
    flag.write_text("rollback\n", encoding="utf-8")
    later = T0 + timedelta(hours=2)
    event = runtime.observe_signal(
        symbol="ETHUSDT",
        side="LONG",
        t0=later,
        boundary=100.0,
        prior_atr=1.02,
        close=101.0,
        compression=0.6,
        extension_atr=0.2,
        base_passed=True,
        observed_at=later,
    )
    assert event["rejection_reason"] == "f111_scan_disabled"
    assert len(broker.get_positions()) == 1
    assert broker._positions["BTCUSDT"].stop_loss is not None


def test_stale_signal_is_not_backfilled(tmp_path):
    runtime = _runtime(tmp_path)
    event = _pass_signal(runtime, observed_at=T0 + timedelta(minutes=5))
    assert event["rejection_reason"] == "stale_signal_not_backfilled"
    assert runtime.pending == []


def test_live_shaped_hourly_frame_keeps_signed_extension_for_long_and_short(tmp_path):
    """The SGP1 hourly frame, including the still-forming bar Bybit appends.

    extension_atr is negative when price has not broken the prior-20 boundary.
    That is every normal SHORT and most LONGs. The live reader must keep the
    sign. A price check (> 0) records those sleeves as missing_feature.
    """
    from dataclasses import replace

    from core.data.ohlcv import CANONICAL_COLUMNS, closed_candles
    from core.strategy.base import SignalSide
    from core.strategy.mar_f111_r12_extension_latefloor_v1 import (
        MarF111R12ExtensionLatefloorV1Strategy,
    )

    bars = MarF111R12ExtensionLatefloorV1Strategy.min_bars + 1
    index = pd.date_range("2024-01-01", periods=bars, freq="h", tz="UTC", name="timestamp")
    frame = pd.DataFrame(
        {
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.0,
            "volume": 10.0,
            "turnover": 1000.0,
        },
        index=index,
    )
    frame = frame[CANONICAL_COLUMNS].astype("float64")
    # Ten seconds into the last Bybit bar. closed_candles drops that bar.
    now = index[-1].to_pydatetime() + timedelta(seconds=10)

    class _LiveHourly:
        def fetch_latest(self, symbol: str, timeframe: str, bars: int = 860) -> pd.DataFrame:
            assert symbol == "BTCUSDT"
            assert timeframe == "1h"
            assert bars == 860
            return frame

    runtime = _runtime(tmp_path)
    runtime.registry["BTCUSDT"] = _available("BTCUSDT")
    runtime._consume_hourly(_LiveHourly(), now)

    closed = closed_candles(frame, "1h", now=now)
    assert list(closed.columns) == CANONICAL_COLUMNS
    assert closed.index.name == "timestamp"
    assert len(closed) == MarF111R12ExtensionLatefloorV1Strategy.min_bars
    expected: dict[str, float] = {}
    boundaries: dict[str, float] = {}
    for side in (SignalSide.LONG, SignalSide.SHORT):
        rule = MarF111R12ExtensionLatefloorV1Strategy(
            replace(MarF111R12ExtensionLatefloorV1Strategy().params, side=side)
        )
        signals = rule.generate_signals(rule.prepare_market_context("BTCUSDT", closed, None))
        extension = float(signals["extension_atr"].iloc[-1])
        assert extension < 0
        expected[side.value] = extension
        boundaries[side.value] = float(signals["entry_boundary"].iloc[-1])

    logged = [
        row
        for row in runtime.events
        if row.get("symbol") == "BTCUSDT" and row.get("side") in {"LONG", "SHORT"}
    ]
    assert {row["side"] for row in logged} == {"LONG", "SHORT"}
    for row in logged:
        got = row["feature_values"]["extension_atr"]
        assert got == pytest.approx(expected[row["side"]])
        assert got < 0
        assert row["rejection_reason"] != "missing_feature"
        assert row["feature_values"]["compression"] == pytest.approx(1.0)
        assert row["feature_values"]["boundary"] == pytest.approx(boundaries[row["side"]])
        assert row["feature_values"]["close"] == pytest.approx(100.0)
        assert row["feature_values"]["prior_atr"] > 0


def test_saved_path_parity_is_unverified_without_the_private_archive():
    config, _digest = load_f111_config()
    assert config["saved_path_parity"] == "UNVERIFIED"
    archive = ROOT / "MAR_R12_I11_factorial_checkpoint_20261010.zip"
    if not archive.exists():
        pytest.skip(
            "saved-path parity UNVERIFIED: private archive "
            "MAR_R12_I11_factorial_checkpoint_20261010.zip is not available"
        )
    pytest.fail("archive is present but this test does not invent a parity pass")


def test_instrument_round_trip_uses_exchange_metadata(tmp_path):
    """A verified tick/lot is what the paper broker rounds with. No inferred alias."""
    prices = {"BTCUSDT": 101.0}
    runtime = _runtime(tmp_path, broker=_broker(prices), risk=_risk(tmp_path))
    runtime.registry["BTCUSDT"] = InstrumentStatus(
        "BTCUSDT", AVAILABLE, "Trading", "Trading", tick_size=0.5, qty_step=0.1, min_qty=0.1, min_notional=5
    )
    _pass_signal(runtime)
    runtime.observe_minute(
        symbol="BTCUSDT", minute=T0, high=102, low=99, close=101, quote=101, quote_time=T0, observed_at=T0
    )
    action = T0 + timedelta(minutes=1)
    runtime.observe_minute(
        symbol="BTCUSDT", minute=action, high=102, low=100, close=101, quote=101, quote_time=action, observed_at=action
    )
    instrument = runtime.broker.get_instrument("BTCUSDT")
    assert isinstance(instrument, Instrument)
    assert instrument.tick_size == 0.5
    assert instrument.qty_step == 0.1
    quantity = runtime.broker.get_positions()[0].quantity
    assert quantity == pytest.approx(instrument.round_quantity(quantity))
