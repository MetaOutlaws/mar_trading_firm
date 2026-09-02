"""
Risk engine tests, including fault injection.

The legacy project declared `MAX_POSITIONS = 5` and `MAX_DAILY_TRADES = 30` and
never checked either. Every limit here has a test that proves enforcement
actually happens, so the same class of defect cannot recur silently.

Also verified: the kill switch survives a restart, cannot be reset without an
explicit acknowledgement, and agents can only ever reduce risk.
"""

from __future__ import annotations

import pytest

from core.risk.engine import (
    OpenPosition,
    PortfolioState,
    RiskEngine,
    RiskVerdict,
    TradeIntent,
)
from core.risk.killswitch import KillSwitch, TripReason
from core.risk.limits import RiskLimits


@pytest.fixture
def kill_switch(tmp_path) -> KillSwitch:
    """An isolated kill switch per test, so state cannot leak between them."""
    return KillSwitch(path=tmp_path / "killswitch.json")


@pytest.fixture
def engine(kill_switch) -> RiskEngine:
    return RiskEngine(limits=RiskLimits(), kill_switch=kill_switch)


@pytest.fixture
def healthy_state() -> PortfolioState:
    return PortfolioState(equity=10_000.0, peak_equity=10_000.0)


def long_intent(symbol: str = "BTCUSDT", sector: str = "majors", stop_pct: float = 0.03):
    """A well-formed long intent with a 3% stop."""
    entry = 100.0
    return TradeIntent(
        symbol=symbol,
        side="LONG",
        entry_price=entry,
        stop_price=entry * (1 - stop_pct),
        take_profit_price=entry * 1.06,
        strategy="rsi_trend",
        score=2.0,
        sector=sector,
    )


def position(symbol: str, sector: str = "majors", notional: float = 500.0) -> OpenPosition:
    return OpenPosition(
        symbol=symbol,
        side="LONG",
        quantity=notional / 100.0,
        entry_price=100.0,
        notional=notional,
        sector=sector,
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------
def test_valid_trade_is_approved(engine, healthy_state):
    decision = engine.evaluate(long_intent(), healthy_state)
    assert decision.is_approved
    assert decision.quantity > 0
    assert decision.notional > 0


def test_risk_amount_respects_the_per_trade_budget(engine, healthy_state):
    """A 1% risk budget on $10k equity means at most $100 at risk."""
    decision = engine.evaluate(long_intent(stop_pct=0.03), healthy_state)
    assert decision.is_approved
    # 1% of 10,000 = 100. Allow a cent of rounding.
    assert decision.risk_amount <= 100.01


def test_wider_stop_produces_a_smaller_position(kill_switch, healthy_state):
    """Risk-based sizing: a wider stop must mean a smaller position.

    Uses a deliberately loose notional cap so the risk budget is the binding
    constraint. With the production caps the notional limit binds first for any
    stop under 10%, which is a separate (and intentionally conservative)
    behaviour covered by `test_position_notional_cap_binds_when_stop_is_very_tight`.
    """
    loose = RiskEngine(
        limits=RiskLimits(max_position_pct=1.0, max_total_exposure_pct=1.0),
        kill_switch=kill_switch,
    )

    tight = loose.evaluate(long_intent(stop_pct=0.02), healthy_state)
    wide = loose.evaluate(long_intent(stop_pct=0.10), healthy_state)

    assert tight.notional > wide.notional
    # Risk held constant is the whole point of sizing off the stop distance.
    assert tight.risk_amount == pytest.approx(wide.risk_amount, rel=0.01)
    assert tight.risk_amount == pytest.approx(100.0, rel=0.01)  # 1% of $10k


def test_production_caps_keep_per_trade_risk_well_under_budget(engine, healthy_state):
    """With a 10% notional cap, a typical 3% stop risks ~0.3% of equity.

    Documents the interaction: the notional cap, not the risk budget, is the
    active constraint at normal stop distances. That is deliberately
    conservative -- the risk budget is a ceiling, not a target.
    """
    decision = engine.evaluate(long_intent(stop_pct=0.03), healthy_state)
    risk_fraction = decision.risk_amount / healthy_state.equity
    assert risk_fraction < 0.01
    assert risk_fraction == pytest.approx(0.003, abs=0.0005)


def test_position_notional_cap_binds_when_stop_is_very_tight(engine, healthy_state):
    """A 0.5% stop would imply a huge position; the notional cap must clamp it."""
    decision = engine.evaluate(long_intent(stop_pct=0.005), healthy_state)
    assert decision.is_approved
    # Max 10% of $10k equity = $1,000.
    assert decision.notional <= 1_000.01


# ---------------------------------------------------------------------------
# Position count limits (the legacy project's unenforced ones)
# ---------------------------------------------------------------------------
def test_max_concurrent_positions_is_enforced(engine, healthy_state):
    healthy_state.open_positions = [
        position(f"SYM{i}USDT", sector=f"sector{i}") for i in range(5)
    ]
    decision = engine.evaluate(long_intent(), healthy_state)
    assert decision.verdict is RiskVerdict.REJECTED
    assert any("open positions" in r for r in decision.reasons)


def test_max_daily_trades_is_enforced(engine, healthy_state):
    healthy_state.trades_today = 20
    decision = engine.evaluate(long_intent(), healthy_state)
    assert decision.verdict is RiskVerdict.REJECTED
    assert any("trades today" in r for r in decision.reasons)


def test_duplicate_symbol_is_rejected(engine, healthy_state):
    healthy_state.open_positions = [position("BTCUSDT")]
    decision = engine.evaluate(long_intent("BTCUSDT"), healthy_state)
    assert decision.verdict is RiskVerdict.REJECTED
    assert any("already holding" in r for r in decision.reasons)


def test_sector_concentration_is_capped(engine, healthy_state):
    """Five correlated alt longs are one leveraged bet, not five positions."""
    healthy_state.open_positions = [
        position("SOLUSDT", sector="layer1"),
        position("AVAXUSDT", sector="layer1"),
    ]
    decision = engine.evaluate(long_intent("DOTUSDT", sector="layer1"), healthy_state)
    assert decision.verdict is RiskVerdict.REJECTED
    assert any("correlation risk" in r for r in decision.reasons)


def test_different_sectors_are_allowed(engine, healthy_state):
    healthy_state.open_positions = [
        position("SOLUSDT", sector="layer1"),
        position("AVAXUSDT", sector="layer1"),
    ]
    decision = engine.evaluate(long_intent("BTCUSDT", sector="majors"), healthy_state)
    assert decision.is_approved


# ---------------------------------------------------------------------------
# Exposure
# ---------------------------------------------------------------------------
def test_total_exposure_cap_is_enforced(engine, healthy_state):
    # $5,000 of exposure on $10,000 equity is exactly the 50% cap.
    healthy_state.open_positions = [
        position("A", sector="s1", notional=2_500.0),
        position("B", sector="s2", notional=2_500.0),
    ]
    decision = engine.evaluate(long_intent(), healthy_state)
    assert decision.verdict is RiskVerdict.REJECTED
    assert any("total exposure" in r for r in decision.reasons)


def test_exposure_headroom_shrinks_the_position(engine, healthy_state):
    """Near the exposure cap, a trade is allowed but only at reduced size."""
    healthy_state.open_positions = [position("A", sector="s1", notional=4_600.0)]
    decision = engine.evaluate(long_intent(stop_pct=0.02), healthy_state)

    assert decision.verdict is RiskVerdict.APPROVED_REDUCED
    # Only $400 of headroom remains under the 50% cap.
    assert decision.notional <= 400.01
    assert any("exposure headroom" in w for w in decision.warnings)


# ---------------------------------------------------------------------------
# Loss limits and halts
# ---------------------------------------------------------------------------
def test_daily_loss_limit_halts_new_entries(engine, healthy_state):
    healthy_state.realised_pnl_today = -350.0  # 3.5% of equity, limit is 3%
    decision = engine.evaluate(long_intent(), healthy_state)
    assert decision.verdict is RiskVerdict.HALTED
    assert any("daily loss" in r for r in decision.reasons)


def test_daily_profit_does_not_halt(engine, healthy_state):
    healthy_state.realised_pnl_today = 500.0
    decision = engine.evaluate(long_intent(), healthy_state)
    assert decision.is_approved


def test_consecutive_losses_trigger_cooldown(engine, healthy_state):
    healthy_state.consecutive_losses = 6
    decision = engine.evaluate(long_intent(), healthy_state)
    assert decision.verdict is RiskVerdict.HALTED
    assert any("consecutive losses" in r for r in decision.reasons)


def test_drawdown_breach_trips_the_kill_switch(engine, healthy_state, kill_switch):
    """A drawdown breach must halt permanently, not just block one trade.

    It means the strategy is operating outside its validated envelope, which
    warrants human investigation rather than an automatic retry.
    """
    healthy_state.peak_equity = 10_000.0
    healthy_state.equity = 8_400.0  # 16% drawdown, limit is 15%

    decision = engine.evaluate(long_intent(), healthy_state)

    assert decision.verdict is RiskVerdict.HALTED
    assert kill_switch.is_tripped
    assert kill_switch.read().reason is TripReason.MAX_DRAWDOWN


def test_zero_equity_is_halted(engine):
    state = PortfolioState(equity=0.0, peak_equity=10_000.0)
    decision = engine.evaluate(long_intent(), state)
    assert decision.verdict is RiskVerdict.HALTED


# ---------------------------------------------------------------------------
# Stop-loss discipline
# ---------------------------------------------------------------------------
def test_missing_stop_is_rejected(engine, healthy_state):
    intent = long_intent()
    intent.stop_price = 0.0
    decision = engine.evaluate(intent, healthy_state)
    assert decision.verdict is RiskVerdict.REJECTED
    assert any("no stop loss" in r for r in decision.reasons)


def test_stop_on_the_wrong_side_is_rejected(engine, healthy_state):
    """A long stop above entry would fill immediately."""
    intent = long_intent()
    intent.stop_price = intent.entry_price * 1.05
    decision = engine.evaluate(intent, healthy_state)
    assert decision.verdict is RiskVerdict.REJECTED
    assert any("not below entry" in r for r in decision.reasons)


def test_short_stop_must_be_above_entry(engine, healthy_state):
    intent = TradeIntent(
        symbol="BTCUSDT", side="SHORT", entry_price=100.0, stop_price=95.0, sector="majors"
    )
    decision = engine.evaluate(intent, healthy_state)
    assert decision.verdict is RiskVerdict.REJECTED
    assert any("not above entry" in r for r in decision.reasons)


def test_absurdly_tight_stop_is_rejected(engine, healthy_state):
    """A 0.1% stop is market noise, not risk management."""
    decision = engine.evaluate(long_intent(stop_pct=0.001), healthy_state)
    assert decision.verdict is RiskVerdict.REJECTED
    assert any("below minimum" in r for r in decision.reasons)


def test_absurdly_wide_stop_is_rejected(engine, healthy_state):
    decision = engine.evaluate(long_intent(stop_pct=0.30), healthy_state)
    assert decision.verdict is RiskVerdict.REJECTED
    assert any("above maximum" in r for r in decision.reasons)


def test_invalid_side_is_rejected(engine, healthy_state):
    intent = long_intent()
    intent.side = "SIDEWAYS"
    decision = engine.evaluate(intent, healthy_state)
    assert decision.verdict is RiskVerdict.REJECTED


def test_negative_price_is_rejected(engine, healthy_state):
    intent = long_intent()
    intent.entry_price = -5.0
    decision = engine.evaluate(intent, healthy_state)
    assert decision.verdict is RiskVerdict.REJECTED


# ---------------------------------------------------------------------------
# Kill switch behaviour
# ---------------------------------------------------------------------------
def test_tripped_switch_blocks_everything(engine, healthy_state, kill_switch):
    kill_switch.trip(TripReason.MANUAL, "operator halted trading", tripped_by="tester")
    decision = engine.evaluate(long_intent(), healthy_state)
    assert decision.verdict is RiskVerdict.HALTED
    assert any("kill switch tripped" in r for r in decision.reasons)


def test_kill_switch_state_exposes_is_tripped(kill_switch):
    """Gather paths call is_tripped on the snapshot from read(), not only KillSwitch."""
    state = kill_switch.read()
    assert state.is_tripped is False
    kill_switch.trip(TripReason.MANUAL, "alias check", tripped_by="tester")
    assert kill_switch.read().is_tripped is True


def test_kill_switch_survives_restart(tmp_path):
    """Fault injection: the halt must persist across process restarts.

    A halt that clears on restart is not a halt, and a crash loop is exactly
    when trading must stay stopped.
    """
    path = tmp_path / "killswitch.json"
    KillSwitch(path=path).trip(TripReason.BROKER_ERROR, "connection lost")

    # A completely fresh instance, as if the process had restarted.
    assert KillSwitch(path=path).is_tripped


def test_kill_switch_preserves_the_first_trip_reason(kill_switch):
    """Cascading failures must not overwrite the root cause."""
    kill_switch.trip(TripReason.DATA_STALE, "no candles for 30 minutes")
    kill_switch.trip(TripReason.BROKER_ERROR, "secondary failure")

    assert kill_switch.read().reason is TripReason.DATA_STALE


def test_kill_switch_reset_requires_acknowledgement(kill_switch):
    kill_switch.trip(TripReason.MANUAL, "test")

    with pytest.raises(ValueError, match="acknowledgement"):
        kill_switch.reset(operator="tester", acknowledgement="whatever")

    assert kill_switch.is_tripped


def test_kill_switch_reset_works_with_acknowledgement(kill_switch):
    kill_switch.trip(TripReason.MANUAL, "test")
    kill_switch.reset(operator="tester", acknowledgement="I HAVE INVESTIGATED THE CAUSE")
    assert not kill_switch.is_tripped


def test_corrupt_kill_switch_file_fails_open(tmp_path):
    """A corrupt state file must not silently halt a healthy system.

    Real trips are also recorded as risk events in the database, so failing
    open here does not lose the audit trail.
    """
    path = tmp_path / "killswitch.json"
    path.write_text("{ this is not json", encoding="utf-8")
    assert not KillSwitch(path=path).is_tripped


# ---------------------------------------------------------------------------
# Agents can only reduce risk
# ---------------------------------------------------------------------------
def test_agent_can_reduce_position_size(engine, healthy_state):
    decision = engine.evaluate(long_intent(), healthy_state)
    original = decision.notional

    adjusted = engine.apply_agent_adjustment(decision, 0.5, agent="risk_officer")

    assert adjusted.is_approved
    assert adjusted.notional == pytest.approx(original * 0.5)
    assert adjusted.verdict is RiskVerdict.APPROVED_REDUCED


def test_agent_cannot_increase_position_size(engine, healthy_state):
    """The core safety invariant of the whole agent architecture."""
    decision = engine.evaluate(long_intent(), healthy_state)
    original = decision.notional

    adjusted = engine.apply_agent_adjustment(decision, 3.0, agent="overconfident_agent")

    assert adjusted.notional == pytest.approx(original)
    assert any("clamped" in w for w in adjusted.warnings)


def test_agent_can_veto_with_zero_multiplier(engine, healthy_state):
    decision = engine.evaluate(long_intent(), healthy_state)
    adjusted = engine.apply_agent_adjustment(decision, 0.0, agent="risk_officer")

    assert not adjusted.is_approved
    assert any("vetoed" in r for r in adjusted.reasons)


def test_agent_cannot_revive_a_rejected_trade(engine, healthy_state):
    """An agent must not be able to turn a rejection into an approval."""
    healthy_state.trades_today = 20  # forces rejection
    decision = engine.evaluate(long_intent(), healthy_state)
    assert not decision.is_approved

    adjusted = engine.apply_agent_adjustment(decision, 1.0, agent="eager_agent")
    assert not adjusted.is_approved


def test_negative_multiplier_is_treated_as_a_veto(engine, healthy_state):
    decision = engine.evaluate(long_intent(), healthy_state)
    adjusted = engine.apply_agent_adjustment(decision, -2.0, agent="buggy_agent")
    assert not adjusted.is_approved


# ---------------------------------------------------------------------------
# No LLM in the risk path
# ---------------------------------------------------------------------------
def test_risk_modules_import_nothing_that_can_reach_a_network():
    """Structural guarantee: risk decisions must be reproducible offline.

    Scans the risk package's source for network and LLM imports. A failure here
    means someone has made risk decisions dependent on an external service.
    """
    import pathlib

    import core.risk as risk_package

    forbidden = ("httpx", "requests", "openai", "anthropic", "urllib.request", "socket")
    root = pathlib.Path(risk_package.__file__).parent

    for source_file in root.glob("*.py"):
        text = source_file.read_text(encoding="utf-8")
        for token in forbidden:
            assert f"import {token}" not in text, (
                f"{source_file.name} imports {token}; the risk engine must stay "
                "deterministic and offline"
            )


# ---------------------------------------------------------------------------
# Health warnings
# ---------------------------------------------------------------------------
def test_health_warns_before_limits_bind(engine):
    """Warn at 80% of a limit, so there is time to react."""
    state = PortfolioState(equity=8_800.0, peak_equity=10_000.0)  # 12% drawdown of a 15% limit
    warnings = engine.check_portfolio_health(state)
    assert any("kill-switch threshold" in w for w in warnings)


def test_health_is_quiet_when_all_is_well(engine, healthy_state):
    assert engine.check_portfolio_health(healthy_state) == []
