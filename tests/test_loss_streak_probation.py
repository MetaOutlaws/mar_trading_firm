"""Paper loss-streak probation.

Flag off must leave the global 6-loss hard block in place. Flag on (paper
only) judges each sleeve family + side, sizes half-risk trials through the
existing sizer, and journals both the raw and clustered streaks.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from config.settings import get_settings
from core.db import session_scope
from core.ledger.models import RiskEvent, TradeRecord
from core.ledger.store import Ledger
from core.risk.engine import PortfolioState, RiskEngine, RiskVerdict, TradeIntent
from core.risk.killswitch import KillSwitch
from core.risk.limits import PAPER_LIMITS, RiskLimits
from core.risk.loss_streak_probation import (
    STRATEGY_EXPECTANCY_MIN_TRADES,
    ClosedFill,
    cluster_loss_streak,
    loss_streak_probation_enabled,
    strategy_key,
    trailing_losses,
)
from tests.test_paper_universe_sleeves import RISK_LIMITS_PATH, RISK_LIMITS_SHA256

T0 = datetime(2024, 1, 1, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _reset_probation_flag():
    import core.risk.loss_streak_probation as probation

    get_settings.cache_clear()
    probation._warned_non_paper = False
    yield
    probation._warned_non_paper = False
    get_settings.cache_clear()


@pytest.fixture
def engine(tmp_path) -> RiskEngine:
    return RiskEngine(limits=RiskLimits(), kill_switch=KillSwitch(path=tmp_path / "kill.json"))


def _enable(monkeypatch, **extra: str) -> None:
    monkeypatch.setenv("TRADING_MODE", extra.pop("TRADING_MODE", "paper"))
    monkeypatch.setenv("LOSS_STREAK_PROBATION", extra.pop("LOSS_STREAK_PROBATION", "true"))
    for key, value in extra.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()


def _intent(symbol: str = "BTCUSDT", strategy: str = "ema_adx", side: str = "LONG") -> TradeIntent:
    entry = 100.0
    stop = entry * (1 - 0.03) if side == "LONG" else entry * (1 + 0.03)
    return TradeIntent(
        symbol=symbol,
        side=side,
        entry_price=entry,
        stop_price=stop,
        take_profit_price=entry * 1.06,
        strategy=strategy,
        score=1.0,
        sector="majors",
    )


def _state(**overrides) -> PortfolioState:
    payload = {"equity": 10_000.0, "peak_equity": 10_000.0}
    payload.update(overrides)
    return PortfolioState(**payload)


def _row(
    *,
    raw_streak: int = 0,
    clustered_streak: int | None = None,
    nets: list[float] | None = None,
    trial_open: bool = False,
) -> dict:
    return {
        "raw_streak": raw_streak,
        "clustered_streak": raw_streak if clustered_streak is None else clustered_streak,
        "nets": list(nets or []),
        "trial_open": trial_open,
    }


def _fill(
    *,
    strategy: str = "ema_adx",
    side: str = "LONG",
    net_pnl: float,
    entry: datetime,
    exit_at: datetime,
    trade_id: int = 1,
) -> ClosedFill:
    return ClosedFill(
        strategy=strategy,
        side=side,
        net_pnl=net_pnl,
        entry_time=entry,
        exit_time=exit_at,
        trade_id=trade_id,
    )


def _capture_journal(state: PortfolioState) -> list[dict]:
    found: list[dict] = []

    def _journal(*args, **kwargs):
        found.append({"args": args, "kwargs": kwargs})

    state.journal_risk_event = _journal
    return found


def _context(found: list[dict]) -> dict:
    assert found, "expected a probation journal row"
    return found[-1]["kwargs"]["context"]


# ---------------------------------------------------------------------------
# Clustering (Brian): overlapping holds are one, sequential holds are not
# ---------------------------------------------------------------------------
def test_overlapping_losses_are_one_cluster() -> None:
    """A later entry that starts before the running exit joins the cluster."""
    losses = [
        _fill(net_pnl=-1, entry=T0, exit_at=T0 + timedelta(hours=3), trade_id=1),
        _fill(net_pnl=-1, entry=T0 + timedelta(hours=1), exit_at=T0 + timedelta(hours=4), trade_id=2),
        _fill(net_pnl=-1, entry=T0 + timedelta(hours=2), exit_at=T0 + timedelta(hours=5), trade_id=3),
    ]
    assert cluster_loss_streak(losses) == 1
    assert len(trailing_losses(losses)) == 3


def test_sequential_losses_count_individually() -> None:
    """Entry exactly at the previous exit does not overlap."""
    losses = [
        _fill(net_pnl=-1, entry=T0, exit_at=T0 + timedelta(hours=1), trade_id=1),
        _fill(net_pnl=-2, entry=T0 + timedelta(hours=1), exit_at=T0 + timedelta(hours=2), trade_id=2),
        _fill(net_pnl=-3, entry=T0 + timedelta(hours=2), exit_at=T0 + timedelta(hours=3), trade_id=3),
    ]
    assert cluster_loss_streak(losses) == 3


def test_mixed_overlap_and_a_later_loss_are_two_clusters() -> None:
    """Two holds that share time, then one that starts after both have exited."""
    losses = [
        _fill(net_pnl=-1, entry=T0, exit_at=T0 + timedelta(hours=10), trade_id=1),
        _fill(net_pnl=-1, entry=T0 + timedelta(hours=2), exit_at=T0 + timedelta(hours=3), trade_id=2),
        _fill(net_pnl=-1, entry=T0 + timedelta(hours=11), exit_at=T0 + timedelta(hours=12), trade_id=3),
    ]
    assert cluster_loss_streak(losses) == 2


def test_a_win_ends_the_trailing_streak_before_clustering() -> None:
    older = _fill(net_pnl=-5, entry=T0, exit_at=T0 + timedelta(hours=1), trade_id=1)
    win = _fill(net_pnl=4, entry=T0 + timedelta(hours=2), exit_at=T0 + timedelta(hours=3), trade_id=2)
    first = _fill(net_pnl=-1, entry=T0 + timedelta(hours=4), exit_at=T0 + timedelta(hours=6), trade_id=3)
    second = _fill(
        net_pnl=-1,
        entry=T0 + timedelta(hours=5),
        exit_at=T0 + timedelta(hours=7),
        trade_id=4,
    )
    losses = trailing_losses([older, win, first, second])
    assert [fill.trade_id for fill in losses] == [4, 3]
    assert cluster_loss_streak(losses) == 1


def test_cluster_flag_defaults_off_and_the_block_uses_the_raw_count(engine, monkeypatch) -> None:
    """Three overlapping losses are one cluster, but the default streak is 3."""
    assert get_settings().loss_streak_cluster_overlapping is False
    _enable(monkeypatch)
    assert get_settings().loss_streak_cluster_overlapping is False
    # Positive expectancy must not override the raw block of 3.
    state = _state(
        consecutive_losses=6,
        probation_by_strategy={
            "ema_adx LONG": _row(
                raw_streak=3,
                clustered_streak=1,
                nets=[10.0] * 20,
                trial_open=True,
            )
        },
    )
    found = _capture_journal(state)
    decision = engine.evaluate(_intent(), state)
    assert decision.verdict is RiskVerdict.REJECTED
    assert decision.probation_action == "blocked"
    assert "loss streak 3" in decision.reasons[0]
    ctx = _context(found)
    assert ctx["raw_streak"] == 3
    assert ctx["clustered_streak"] == 1
    assert ctx["strategy_streak"] == 3
    assert ctx["rolling_expectancy"] > 0
    assert ctx["action"] == "blocked"


def test_cluster_flag_on_uses_clusters_and_still_journals_both(engine, monkeypatch) -> None:
    _enable(monkeypatch, LOSS_STREAK_CLUSTER_OVERLAPPING="true")
    # Same overlapping book: clustered streak 1 is under the block, and the
    # positive sample is full size. Expectancy itself is not clustered.
    state = _state(
        consecutive_losses=6,
        probation_by_strategy={
            "ema_adx LONG": _row(raw_streak=3, clustered_streak=1, nets=[10.0] * 20, trial_open=False)
        },
    )
    found = _capture_journal(state)
    full = engine.evaluate(_intent(), _state())
    decision = engine.evaluate(_intent(), state)
    assert decision.is_approved
    assert decision.probation_action == "normal"
    assert decision.notional == pytest.approx(full.notional)
    ctx = _context(found)
    assert ctx["strategy_streak"] == 1
    assert ctx["raw_streak"] == 3
    assert ctx["clustered_streak"] == 1
    assert ctx["cluster_overlapping"] is True
    assert ctx["rolling_expectancy"] == pytest.approx(10.0)


def test_sequential_losses_still_block_when_clustering_is_on(engine, monkeypatch) -> None:
    _enable(monkeypatch, LOSS_STREAK_CLUSTER_OVERLAPPING="true")
    state = _state(
        consecutive_losses=6,
        probation_by_strategy={
            "ema_adx LONG": _row(raw_streak=3, clustered_streak=3, nets=[10.0] * 20, trial_open=False)
        },
    )
    decision = engine.evaluate(_intent(), state)
    assert decision.probation_action == "trial"
    assert decision.probation_trial is True
    assert decision.notional == pytest.approx(500.0)


# ---------------------------------------------------------------------------
# Flag off is today's cool-down. Limits pin does not move.
# ---------------------------------------------------------------------------
def test_flag_off_global_block_still_trips_at_six(engine, monkeypatch) -> None:
    monkeypatch.delenv("LOSS_STREAK_PROBATION", raising=False)
    get_settings.cache_clear()
    assert loss_streak_probation_enabled() is False
    state = _state(consecutive_losses=6)
    decision = engine.evaluate(_intent(), state)
    assert decision.verdict is RiskVerdict.HALTED
    assert decision.reasons == ["6 consecutive losses >= limit 6; cooling down"]
    assert decision.probation_action == ""


def test_flag_off_ignores_a_populated_strategy_book(engine, monkeypatch) -> None:
    monkeypatch.setenv("LOSS_STREAK_PROBATION", "false")
    get_settings.cache_clear()
    state = _state(
        consecutive_losses=6,
        probation_by_strategy={"ema_adx LONG": _row(raw_streak=0, nets=[10.0] * 20)},
    )
    found = _capture_journal(state)
    decision = engine.evaluate(_intent(), state)
    assert decision.verdict is RiskVerdict.HALTED
    assert found == []


def test_below_the_block_flag_on_matches_flag_off(engine, monkeypatch) -> None:
    """Global streak under 6 and strategy streak under 3: same size as today."""
    quiet = _state(
        consecutive_losses=2,
        probation_by_strategy={"ema_adx LONG": _row(raw_streak=2, nets=[-1.0, -1.0])},
    )
    off = engine.evaluate(_intent(), quiet)
    _enable(monkeypatch)
    on = engine.evaluate(_intent(), quiet)
    assert on.summary() == off.summary()
    assert on.quantity == off.quantity
    assert on.notional == off.notional
    assert on.risk_amount == off.risk_amount
    assert on.verdict is off.verdict
    assert on.probation_action == ""


def test_live_and_testnet_ignore_the_flag(engine, monkeypatch, caplog) -> None:
    monkeypatch.setenv("LOSS_STREAK_PROBATION", "true")
    monkeypatch.setenv("TRADING_MODE", "testnet")
    get_settings.cache_clear()
    with caplog.at_level(logging.WARNING, logger="core.risk.loss_streak_probation"):
        assert loss_streak_probation_enabled() is False
        assert loss_streak_probation_enabled() is False
    assert caplog.text.count("LOSS_STREAK_PROBATION is set") == 1
    halted = engine.evaluate(_intent(), _state(consecutive_losses=6))
    assert halted.verdict is RiskVerdict.HALTED
    assert "cooling down" in halted.reasons[0]

    monkeypatch.setenv("TRADING_MODE", "live")
    monkeypatch.setenv("GO_LIVE_CONFIRMED", "I_ACCEPT_THE_RISK")
    monkeypatch.setenv("BYBIT_LIVE_API_KEY", "k")
    monkeypatch.setenv("BYBIT_LIVE_API_SECRET", "s")
    get_settings.cache_clear()
    import core.risk.loss_streak_probation as probation

    probation._warned_non_paper = False
    assert loss_streak_probation_enabled() is False
    assert engine.evaluate(_intent(), _state(consecutive_losses=6)).verdict is RiskVerdict.HALTED


def test_risk_limits_pin_and_threshold_are_unchanged() -> None:
    digest = hashlib.sha256(RISK_LIMITS_PATH.read_bytes()).hexdigest()
    assert digest == RISK_LIMITS_SHA256
    limits = RiskLimits()
    assert limits.max_consecutive_losses == 6
    assert "loss_streak_probation" not in limits.to_dict()
    assert "strategy_loss_block" not in limits.to_dict()
    assert PAPER_LIMITS.max_consecutive_losses == 6


def test_sizer_multiplier_scales_the_result_and_leaves_one_untouched(engine) -> None:
    """Half risk is half the size the sizer already approved. The cap math is not edited."""
    state = _state()
    intent = _intent()
    base = engine._size_position(intent, state)
    same = engine._size_position(intent, state, risk_multiplier=1.0)
    assert same == base
    # 10% of $10k binds before the 1% risk budget at a 3% stop, so the
    # unscaled notional is $1,000. Scaling the risk budget alone would
    # still print $1,000. The multiplier scales the result.
    assert base[1] == pytest.approx(1_000.0)
    half = engine._size_position(intent, state, risk_multiplier=0.5)
    assert half[0] == pytest.approx(base[0] * 0.5)
    assert half[1] == pytest.approx(500.0)
    assert half[2] == pytest.approx(base[2] * 0.5)
    assert half[4] is True


# ---------------------------------------------------------------------------
# Scrutiny, block, trial, expectancy
# ---------------------------------------------------------------------------
def test_global_streak_does_not_block_when_probation_is_on(engine, monkeypatch) -> None:
    _enable(monkeypatch)
    state = _state(consecutive_losses=6, probation_by_strategy={})
    decision = engine.evaluate(_intent(), state)
    assert decision.verdict is not RiskVerdict.HALTED
    assert decision.is_approved
    # No closed trades: under scrutiny that is half size, not a block.
    assert decision.probation_action == "half"
    assert decision.notional == pytest.approx(500.0)


def test_other_gates_still_reject_under_probation(engine, monkeypatch) -> None:
    """The global cool-down is the only gate this flag lifts."""
    _enable(monkeypatch)
    from tests.test_risk import position

    crowded = _state(
        consecutive_losses=6,
        open_positions=[position(f"SYM{i}USDT", sector=f"s{i}") for i in range(5)],
        probation_by_strategy={},
    )
    decision = engine.evaluate(_intent(), crowded)
    assert decision.verdict is RiskVerdict.REJECTED
    assert any("open positions" in reason for reason in decision.reasons)

    busy = _state(consecutive_losses=6, trades_today=20, probation_by_strategy={})
    capped = engine.evaluate(_intent(), busy)
    assert capped.verdict is RiskVerdict.REJECTED
    assert any("trades today" in reason for reason in capped.reasons)

    duplicate = _state(
        consecutive_losses=6,
        open_positions=[position("BTCUSDT")],
        probation_by_strategy={},
    )
    held = engine.evaluate(_intent(), duplicate)
    assert held.verdict is RiskVerdict.REJECTED
    assert any("already holding" in reason for reason in held.reasons)

    daily = _state(consecutive_losses=6, realised_pnl_today=-350.0, probation_by_strategy={})
    halted = engine.evaluate(_intent(), daily)
    assert halted.verdict is RiskVerdict.HALTED
    assert any("daily loss" in reason for reason in halted.reasons)
    assert not any("consecutive losses" in reason for reason in halted.reasons)


def test_block_beats_positive_expectancy_and_the_other_side_is_full_size(
    engine, monkeypatch, caplog
) -> None:
    """A 3-loss long is blocked during scrutiny. The short of the same family is not."""
    _enable(monkeypatch)
    book = {
        "ema_adx LONG": _row(raw_streak=3, clustered_streak=3, nets=[8.0] * 20, trial_open=True),
        "ema_adx SHORT": _row(raw_streak=0, clustered_streak=0, nets=[4.0] * 20, trial_open=False),
    }
    state = _state(consecutive_losses=6, probation_by_strategy=book)
    found = _capture_journal(state)
    with caplog.at_level(logging.INFO, logger="core.risk.loss_streak_probation"):
        blocked = engine.evaluate(_intent(strategy="ema_adx", side="LONG"), state)
        allowed = engine.evaluate(
            _intent(symbol="ETHUSDT", strategy="ema_adx", side="SHORT"), state
        )
    assert blocked.verdict is RiskVerdict.REJECTED
    assert blocked.probation_action == "blocked"
    assert blocked.quantity == 0
    full = engine.evaluate(_intent(symbol="ETHUSDT", strategy="ema_adx", side="SHORT"), _state())
    assert allowed.is_approved
    assert allowed.probation_action == "normal"
    assert allowed.notional == pytest.approx(full.notional)
    assert allowed.notional == pytest.approx(1_000.0)
    blocked_ctx = found[0]["kwargs"]["context"]
    allowed_ctx = found[1]["kwargs"]["context"]
    for ctx in (blocked_ctx, allowed_ctx):
        assert "raw_streak" in ctx and "clustered_streak" in ctx
        assert ctx["global_streak"] == 6
        assert "win_rate" in ctx and "n" in ctx
        assert ctx["rolling_expectancy"] > 0
    assert blocked_ctx["strategy"] == "ema_adx LONG"
    assert blocked_ctx["action"] == "blocked"
    assert allowed_ctx["strategy"] == "ema_adx SHORT"
    assert allowed_ctx["action"] == "normal"
    assert "strategy=ema_adx LONG" in caplog.text
    assert "raw_streak=3" in caplog.text
    assert "clustered_streak=3" in caplog.text
    assert "action=blocked" in caplog.text


def test_one_trial_at_a_time_and_a_win_clears_the_block(engine, monkeypatch) -> None:
    _enable(monkeypatch)
    key = "ema_adx LONG"
    no_trial = _state(
        consecutive_losses=2,
        probation_by_strategy={key: _row(raw_streak=3, nets=[-1.0, -1.0, -1.0], trial_open=False)},
    )
    trial = engine.evaluate(_intent(), no_trial)
    assert trial.probation_action == "trial"
    assert trial.probation_trial is True
    assert trial.notional == pytest.approx(500.0)
    assert trial.verdict is RiskVerdict.APPROVED_REDUCED

    held = _state(
        consecutive_losses=2,
        probation_by_strategy={key: _row(raw_streak=3, nets=[-1.0, -1.0, -1.0], trial_open=True)},
    )
    blocked = engine.evaluate(_intent(symbol="ETHUSDT"), held)
    assert blocked.probation_action == "blocked"
    assert blocked.verdict is RiskVerdict.REJECTED

    # The trial closed as another loss. The slot is free. The block remains.
    after_loss = _state(
        consecutive_losses=2,
        probation_by_strategy={key: _row(raw_streak=4, nets=[-1.0] * 4, trial_open=False)},
    )
    again = engine.evaluate(_intent(symbol="SOLUSDT"), after_loss)
    assert again.probation_action == "trial"
    assert again.notional == pytest.approx(500.0)

    # A winning close resets the strategy streak. Outside scrutiny the next
    # entry is the ordinary full size, not another trial.
    cleared = _state(
        consecutive_losses=0,
        probation_by_strategy={key: _row(raw_streak=0, nets=[5.0, -1.0, -1.0, -1.0], trial_open=False)},
    )
    full = engine.evaluate(_intent(), _state())
    after_win = engine.evaluate(_intent(), cleared)
    assert after_win.probation_action == ""
    assert after_win.notional == pytest.approx(full.notional)
    assert after_win.notional == pytest.approx(1_000.0)


def test_expectancy_branches_under_scrutiny(engine, monkeypatch) -> None:
    _enable(monkeypatch)
    full = engine.evaluate(_intent(), _state())

    def decide(nets: list[float]):
        state = _state(
            consecutive_losses=6,
            probation_by_strategy={"ema_adx LONG": _row(raw_streak=0, nets=nets)},
        )
        return engine.evaluate(_intent(), state)

    positive = decide([1.0] * 20)
    assert positive.probation_action == "normal"
    assert positive.notional == pytest.approx(full.notional)

    flat = decide([1.0, -1.0, 1.0, -1.0, 0.0])
    assert flat.probation_action == "normal"
    assert flat.notional == pytest.approx(full.notional)

    negative = decide([1.0, -1.0, 1.0, -1.0, -0.01])
    assert negative.probation_action == "half"
    assert negative.notional == pytest.approx(full.notional * 0.5)

    short = decide([10.0] * 4)
    assert short.probation_action == "half"
    assert short.notional == pytest.approx(500.0)
    assert STRATEGY_EXPECTANCY_MIN_TRADES == 5


def test_expectancy_window_is_the_latest_closes_only(engine, monkeypatch) -> None:
    _enable(monkeypatch, STRATEGY_EXPECTANCY_WINDOW="5")
    # Newest five are first. They are profitable. The older three are not.
    nets = [10.0, 10.0, 10.0, 10.0, 10.0, -100.0, -100.0, -100.0]
    state = _state(
        consecutive_losses=6,
        probation_by_strategy={"ema_adx LONG": _row(raw_streak=0, nets=nets)},
    )
    decision = engine.evaluate(_intent(), state)
    assert decision.probation_action == "normal"
    ctx_n = _capture_journal(state)
    engine.evaluate(_intent(), state)
    assert _context(ctx_n)["n"] == 5
    assert _context(ctx_n)["rolling_expectancy"] == pytest.approx(10.0)


def test_outside_scrutiny_bad_expectancy_stays_full_size(engine, monkeypatch) -> None:
    _enable(monkeypatch)
    state = _state(
        consecutive_losses=5,
        probation_by_strategy={"ema_adx LONG": _row(raw_streak=2, nets=[-5.0] * 20)},
    )
    found = _capture_journal(state)
    full = engine.evaluate(_intent(), _state())
    decision = engine.evaluate(_intent(), state)
    assert decision.probation_action == ""
    assert decision.notional == pytest.approx(full.notional)
    assert found == []


def test_strategy_loss_block_is_configurable(engine, monkeypatch) -> None:
    _enable(monkeypatch, STRATEGY_LOSS_BLOCK="4")
    state = _state(
        consecutive_losses=1,
        probation_by_strategy={"ema_adx LONG": _row(raw_streak=3, trial_open=False)},
    )
    decision = engine.evaluate(_intent(), state)
    assert decision.is_approved
    assert decision.probation_action == ""
    assert decision.notional == pytest.approx(1_000.0)


# ---------------------------------------------------------------------------
# Persistence: the book is derived from closed rows, including trials
# ---------------------------------------------------------------------------
def _insert_trade(
    session,
    *,
    strategy: str,
    side: str,
    net_pnl: float,
    entry: datetime,
    exit_at: datetime,
    symbol: str = "XRPUSDT",
) -> None:
    session.add(
        TradeRecord(
            symbol=symbol,
            side=side,
            mode="paper",
            strategy=strategy,
            quantity=1.0,
            notional=100.0,
            entry_price=100.0,
            exit_price=100.0 + net_pnl,
            entry_time=entry,
            exit_time=exit_at,
            gross_pnl=net_pnl,
            net_pnl=net_pnl,
            exit_reason="test",
        )
    )


def test_restart_derives_the_same_streak_and_global_count_is_unclustered(
    firm_db, monkeypatch
) -> None:
    _enable(monkeypatch)
    with session_scope() as session:
        # Older win, then three overlapping losses and one later loss.
        _insert_trade(
            session,
            strategy="ema_adx",
            side="LONG",
            net_pnl=5.0,
            entry=T0 - timedelta(days=1),
            exit_at=T0 - timedelta(hours=12),
            symbol="OLDUSDT",
        )
        overlapping = [
            (T0, T0 + timedelta(hours=3)),
            (T0 + timedelta(hours=1), T0 + timedelta(hours=4)),
            (T0 + timedelta(hours=2), T0 + timedelta(hours=5)),
        ]
        for index, (entry, exit_at) in enumerate(overlapping):
            _insert_trade(
                session,
                strategy="ema_adx",
                side="LONG",
                net_pnl=-1.0,
                entry=entry,
                exit_at=exit_at,
                symbol=f"A{index}USDT",
            )
        _insert_trade(
            session,
            strategy="ema_adx",
            side="LONG",
            net_pnl=-1.0,
            entry=T0 + timedelta(hours=6),
            exit_at=T0 + timedelta(hours=7),
            symbol="BUSDT",
        )
    ledger = Ledger(mode="paper")
    ledger.open_position(
        symbol="ETHUSDT",
        side="LONG",
        quantity=1.0,
        entry_price=100.0,
        expected_entry_price=100.0,
        take_profit=110.0,
        stop_loss=90.0,
        strategy="ema_adx",
        sector="layer1",
        signal_score=1.0,
        signal_reason="open while blocked",
        broker_order_id="trial-slot",
        opened_at=T0 + timedelta(days=1),
    )
    # A new ledger is a restart. Nothing about the streak was stored beside
    # the closed trades and the open row.
    restarted = Ledger(mode="paper")
    assert restarted.consecutive_losses() == 4
    book = restarted.strategy_probation_book()
    assert book["ema_adx LONG"]["raw_streak"] == 4
    assert book["ema_adx LONG"]["clustered_streak"] == 2
    assert book["ema_adx LONG"]["trial_open"] is True

    monkeypatch.setenv("LOSS_STREAK_CLUSTER_OVERLAPPING", "true")
    get_settings.cache_clear()
    clustered = Ledger(mode="paper").strategy_probation_book()
    # Clustered streak at the open was 2, under the block of 3, so that
    # open row is not a trial. The global count above stays 4.
    assert clustered["ema_adx LONG"]["raw_streak"] == 4
    assert clustered["ema_adx LONG"]["clustered_streak"] == 2
    assert clustered["ema_adx LONG"]["trial_open"] is False
    assert Ledger(mode="paper").consecutive_losses() == 4


def test_ledger_trial_loss_keeps_the_block_and_a_win_clears_it(firm_db, monkeypatch, tmp_path) -> None:
    _enable(monkeypatch)
    with session_scope() as session:
        for index in range(3):
            entry = T0 + timedelta(hours=index * 2)
            _insert_trade(
                session,
                strategy="ema_adx",
                side="LONG",
                net_pnl=-1.0,
                entry=entry,
                exit_at=entry + timedelta(hours=1),
                symbol=f"S{index}USDT",
            )
    engine = RiskEngine(limits=RiskLimits(), kill_switch=KillSwitch(path=tmp_path / "kill.json"))
    ledger = Ledger(mode="paper")
    first = ledger.portfolio_state(10_000.0)
    assert first.probation_by_strategy["ema_adx LONG"]["raw_streak"] == 3
    assert first.consecutive_losses == 3
    trial = engine.evaluate(_intent(), first)
    assert trial.probation_action == "trial"
    assert trial.notional == pytest.approx(500.0)

    position_id = ledger.open_position(
        symbol="ETHUSDT",
        side="LONG",
        quantity=1.0,
        entry_price=100.0,
        expected_entry_price=100.0,
        take_profit=110.0,
        stop_loss=90.0,
        strategy="ema_adx",
        sector="layer1",
        signal_score=1.0,
        signal_reason="trial",
        broker_order_id="t1",
        opened_at=datetime.now(timezone.utc),
    )
    held = ledger.portfolio_state(10_000.0)
    blocked = engine.evaluate(_intent(symbol="SOLUSDT"), held)
    assert blocked.probation_action == "blocked"
    assert held.probation_by_strategy["ema_adx LONG"]["trial_open"] is True

    ledger.close_position(
        position_id=position_id,
        exit_price=90.0,
        expected_exit_price=90.0,
        exit_reason="stop",
        fees=0.0,
        entry_fees=0.0,
        exit_fees=0.0,
    )
    after_loss = Ledger(mode="paper").portfolio_state(10_000.0)
    assert after_loss.probation_by_strategy["ema_adx LONG"]["raw_streak"] == 4
    assert after_loss.probation_by_strategy["ema_adx LONG"]["trial_open"] is False
    next_trial = engine.evaluate(_intent(symbol="ADAUSDT"), after_loss)
    assert next_trial.probation_action == "trial"
    assert next_trial.notional == pytest.approx(500.0)

    winner_id = ledger.open_position(
        symbol="ADAUSDT",
        side="LONG",
        quantity=1.0,
        entry_price=100.0,
        expected_entry_price=100.0,
        take_profit=110.0,
        stop_loss=90.0,
        strategy="ema_adx",
        sector="layer1",
        signal_score=1.0,
        signal_reason="trial win",
        broker_order_id="t2",
        opened_at=datetime.now(timezone.utc),
    )
    ledger.close_position(
        position_id=winner_id,
        exit_price=110.0,
        expected_exit_price=110.0,
        exit_reason="target",
        fees=0.0,
        entry_fees=0.0,
        exit_fees=0.0,
    )
    cleared = Ledger(mode="paper").portfolio_state(10_000.0)
    assert cleared.probation_by_strategy["ema_adx LONG"]["raw_streak"] == 0
    assert cleared.probation_by_strategy["ema_adx LONG"]["clustered_streak"] == 0
    full = engine.evaluate(_intent(), _state())
    after_win = engine.evaluate(_intent(), cleared)
    assert after_win.is_approved
    assert after_win.probation_action == ""
    assert after_win.notional == pytest.approx(full.notional)

    with session_scope() as session:
        rows = list(
            session.scalars(
                select(RiskEvent).where(RiskEvent.event_type == "loss_streak_probation")
            )
        )
    assert rows
    assert all("raw_streak" in (row.context or {}) for row in rows)
    assert all("clustered_streak" in (row.context or {}) for row in rows)
    assert any(row.action_taken == "blocked" for row in rows)
    assert any(row.action_taken == "trial" for row in rows)


# ---------------------------------------------------------------------------
# F111 calls the same evaluate
# ---------------------------------------------------------------------------
def _seed_f111_losses(n: int = 6) -> None:
    from core.strategy.f111_config import STRATEGY_ID

    with session_scope() as session:
        for index in range(n):
            entry = T0 + timedelta(hours=index * 2)
            _insert_trade(
                session,
                strategy=STRATEGY_ID,
                side="LONG",
                net_pnl=-1.0,
                entry=entry,
                exit_at=entry + timedelta(minutes=30),
                symbol=f"F{index}USDT",
            )


def _drive_f111_fill(tmp_path, ledger, risk):
    from datetime import timedelta as _td

    from tests.test_f111_paper import T0 as F111_T0
    from tests.test_f111_paper import _broker, _pass_signal, _runtime

    prices = {"BTCUSDT": 101.0}
    runtime = _runtime(tmp_path, broker=_broker(prices), risk=risk, ledger=ledger)
    _pass_signal(runtime)
    runtime.observe_minute(
        symbol="BTCUSDT",
        minute=F111_T0,
        high=102,
        low=99,
        close=101,
        quote=101,
        quote_time=F111_T0,
        observed_at=F111_T0,
    )
    action = F111_T0 + _td(minutes=1)
    runtime.observe_minute(
        symbol="BTCUSDT",
        minute=action,
        high=102,
        low=100,
        close=101,
        quote=101,
        quote_time=action,
        observed_at=action,
    )
    return runtime


def test_f111_flag_off_still_halts_on_the_global_streak(firm_db, monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("LOSS_STREAK_PROBATION", raising=False)
    get_settings.cache_clear()
    _seed_f111_losses(6)
    ledger = Ledger(mode="paper")
    assert ledger.consecutive_losses() == 6
    risk = RiskEngine(limits=PAPER_LIMITS, kill_switch=KillSwitch(path=tmp_path / "kill.json"))
    runtime = _drive_f111_fill(tmp_path, ledger, risk)
    assert runtime.broker.get_positions() == []
    reasons = [row.get("rejection_reason") or "" for row in runtime.events]
    assert any("consecutive losses" in reason for reason in reasons)


def test_f111_trial_is_half_size_and_a_second_trial_is_blocked(firm_db, monkeypatch, tmp_path) -> None:
    from core.execution.broker import Instrument
    from core.strategy.f111_config import STRATEGY_ID

    _enable(monkeypatch)
    _seed_f111_losses(6)
    risk = RiskEngine(limits=PAPER_LIMITS, kill_switch=KillSwitch(path=tmp_path / "k1.json"))
    ledger = Ledger(mode="paper")
    runtime = _drive_f111_fill(tmp_path, ledger, risk)
    positions = runtime.broker.get_positions()
    assert len(positions) == 1
    quote = 101.0
    atr = 1.02
    intent = TradeIntent(
        symbol="BTCUSDT",
        side="LONG",
        entry_price=quote,
        stop_price=quote - 3.0 * atr,
        take_profit_price=quote + 4.0 * atr,
        strategy=STRATEGY_ID,
        score=1.0,
        sector="majors",
    )
    sized = risk._size_position(intent, PortfolioState(equity=10_000.0, peak_equity=10_000.0))
    half = risk._size_position(
        intent,
        PortfolioState(equity=10_000.0, peak_equity=10_000.0),
        risk_multiplier=0.5,
    )
    step = Instrument("BTCUSDT", tick_size=0.01, qty_step=0.001, min_qty=0.001, min_notional=5.0)
    assert positions[0].quantity == pytest.approx(step.round_quantity(half[0]))
    assert positions[0].quantity < step.round_quantity(sized[0])

    with session_scope() as session:
        events = list(
            session.scalars(
                select(RiskEvent).where(RiskEvent.event_type == "loss_streak_probation")
            )
        )
    assert events
    ctx = events[-1].context
    assert ctx["strategy"] == strategy_key(STRATEGY_ID, "LONG")
    assert ctx["action"] == "trial"
    assert ctx["raw_streak"] == 6
    assert ctx["clustered_streak"] == 6
    assert ctx["global_streak"] == 6
    assert ctx["risk_multiplier"] == 0.5

    # The fill is the open trial. The slot is derived from that open row, so
    # a second entry of the same strategy is blocked until it closes. ETH is
    # free: the duplicate-symbol gate is not what rejects it. This is the
    # same RiskEngine.evaluate F111 just called.
    state = ledger.portfolio_state(10_000.0)
    assert state.probation_by_strategy[strategy_key(STRATEGY_ID, "LONG")]["trial_open"] is True
    decision = risk.evaluate(
        TradeIntent(
            symbol="ETHUSDT",
            side="LONG",
            entry_price=quote,
            stop_price=quote - 3.0 * atr,
            take_profit_price=quote + 4.0 * atr,
            strategy=STRATEGY_ID,
            score=1.0,
            sector="other",
        ),
        state,
    )
    assert decision.probation_action == "blocked"
    assert decision.verdict is RiskVerdict.REJECTED
