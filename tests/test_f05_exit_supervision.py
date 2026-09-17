"""
F05 — exit supervision under halt and empty plan.

Review (`docs/MAR_Trading_Firm_Review_2026-09-12.md`): a tripped kill switch
returned from ``run_cycle`` before ``_manage_open_positions``; the paper runner
then ``break``; an empty startup plan exited the process after hydrate. Paper
stops live only in this process, so those paths orphaned open risk.

Policy (documented in ``core/execution/engine.py``):

- ENTRY_HALT (kill switch): no new orders; paper ``check_stops`` still runs.
- EMPTY_PLAN: no scan rows; paper ``check_stops`` still runs.
- BLIND (broker unhealthy): skip this cycle's poll; do not invent fills.
- STOP_SERVICE: only when halted/empty-plan *and* the book is flat, or SIGINT.

Live flags stay off. This module does not touch approvals or go-live gates.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from config.settings import TradingMode
from core.execution.engine import (
    PAPER_EXIT_POLL_SECONDS,
    PlanEntry,
    TradingEngine,
    TradingPlan,
    may_break_on_halt,
    may_stop_for_empty_plan,
)
from core.execution.paper import PaperBroker
from core.ledger.store import Ledger
from core.risk.engine import RiskEngine
from core.risk.killswitch import KillSwitch, TripReason
from core.risk.limits import PAPER_LIMITS
from core.strategy.base import SignalSide, Strategy
from research.costs import FRICTIONLESS
from scripts.run_paper_trading import wait_for_next_cycle
from tests.test_execution import StubDataSource


STARTING = 10_000.0
SYMBOL = "BTCUSDT"


class SilentStrategy(Strategy):
    """Never emits a signal — used only so a plan row exists."""

    name = "f05_silent"
    min_bars = 1

    def generate_signals(self, candles):  # noqa: ANN001
        return self.empty_signals(candles)


@pytest.fixture
def prices() -> dict[str, float]:
    return {SYMBOL: 100_000.0}


def _engine(tmp_path, monkeypatch, firm_db, prices, *, plan: TradingPlan) -> TradingEngine:
    """Paper engine with isolated kill switch, last_cycle, and no plan refresh."""
    from core.execution import engine as engine_mod

    monkeypatch.setattr(engine_mod, "LAST_CYCLE_PATH", tmp_path / "last_cycle.json")
    ks = KillSwitch(tmp_path / "killswitch.json")
    broker = PaperBroker(
        starting_equity=STARTING,
        costs=FRICTIONLESS,
        data_source=StubDataSource(prices),
    )
    ledger = Ledger(mode="paper", starting_equity=STARTING)
    engine = TradingEngine(
        broker=broker,
        risk_engine=RiskEngine(limits=PAPER_LIMITS, kill_switch=ks),
        ledger=ledger,
        plan=plan,
        data_source=MagicMock(),
    )
    monkeypatch.setattr(engine, "refresh_scan_plan", lambda: False)
    return engine


def _open_long(engine: TradingEngine, prices: dict[str, float]) -> None:
    """Seed a protected paper long in both RAM and the SQLite ledger."""
    result = engine.broker.place_market_order(
        SYMBOL, "LONG", 0.01, expected_price=prices[SYMBOL]
    )
    assert result.success
    assert engine.broker.set_stops(SYMBOL, take_profit=105_000.0, stop_loss=97_000.0)
    engine.ledger.open_position(
        symbol=SYMBOL,
        side="LONG",
        quantity=result.filled_quantity or 0.01,
        entry_price=result.fill_price,
        expected_entry_price=prices[SYMBOL],
        take_profit=105_000.0,
        stop_loss=97_000.0,
        strategy="f05",
        sector="other",
        signal_score=1.0,
        signal_reason="f05-seed",
        broker_order_id=result.order_id or "paper-f05",
        entry_fee=result.fee or 0.0,
    )


def _drive_through_stop(prices: dict[str, float]) -> None:
    prices[SYMBOL] = 96_500.0


def _scan_plan() -> TradingPlan:
    return TradingPlan(
        entries=[
            PlanEntry(
                symbol=SYMBOL,
                side=SignalSide.LONG,
                strategy=SilentStrategy(),
                timeframe="4h",
            )
        ]
    )


def test_policy_empty_plan_stops_only_when_flat() -> None:
    assert may_stop_for_empty_plan(plan_empty=True, open_count=0) is True
    assert may_stop_for_empty_plan(plan_empty=True, open_count=1) is False
    assert may_stop_for_empty_plan(plan_empty=False, open_count=0) is False


def test_policy_halt_breaks_only_when_flat() -> None:
    assert may_break_on_halt(halted=True, open_count=0) is True
    assert may_break_on_halt(halted=True, open_count=1) is False
    assert may_break_on_halt(halted=False, open_count=1) is False


def test_live_flags_stay_off() -> None:
    """CEO LOCK: F05 must not change the fail-closed live / auto-advance defaults."""
    from config.settings import Settings

    assert Settings.model_fields["trading_mode"].default is TradingMode.PAPER
    assert Settings.model_fields["pipeline_auto_advance"].default is False
    assert PAPER_EXIT_POLL_SECONDS > 0
    assert PAPER_EXIT_POLL_SECONDS < 900


def test_kill_switch_still_runs_check_stops(tmp_path, monkeypatch, firm_db, prices) -> None:
    """Review reproduction: tripped switch must still close a paper stop."""
    engine = _engine(tmp_path, monkeypatch, firm_db, prices, plan=_scan_plan())
    _open_long(engine, prices)
    engine.risk.kill_switch.trip(TripReason.MANUAL, "f05 halt", tripped_by="test")
    _drive_through_stop(prices)

    evaluate = MagicMock(side_effect=AssertionError("scan must not run under ENTRY_HALT"))
    monkeypatch.setattr(engine, "_evaluate", evaluate)

    report = engine.run_cycle()

    assert report.halted is True
    assert report.entries_blocked is True
    assert report.exit_supervision_ran is True
    assert report.positions_closed == 1
    assert report.orders_placed == 0
    assert report.symbols_scanned == 0
    evaluate.assert_not_called()
    assert engine.broker.get_positions() == []
    assert engine.ledger.open_positions() == []
    assert engine.open_exposure_count() == 0


def test_kill_switch_without_trigger_keeps_the_position(
    tmp_path, monkeypatch, firm_db, prices
) -> None:
    engine = _engine(tmp_path, monkeypatch, firm_db, prices, plan=_scan_plan())
    _open_long(engine, prices)
    engine.risk.kill_switch.trip(TripReason.MANUAL, "f05 halt", tripped_by="test")

    report = engine.run_cycle()

    assert report.halted is True
    assert report.exit_supervision_ran is True
    assert report.positions_closed == 0
    assert report.orders_placed == 0
    assert len(engine.broker.get_positions()) == 1
    assert len(engine.ledger.open_positions()) == 1


def test_empty_plan_still_runs_check_stops(tmp_path, monkeypatch, firm_db, prices) -> None:
    """Restart with open paper risk and zero plan entries must monitor stops."""
    engine = _engine(tmp_path, monkeypatch, firm_db, prices, plan=TradingPlan())
    _open_long(engine, prices)
    _drive_through_stop(prices)

    report = engine.run_cycle()

    assert report.halted is False
    assert report.entries_blocked is False
    assert report.exit_supervision_ran is True
    assert report.positions_closed == 1
    assert report.orders_placed == 0
    assert report.symbols_scanned == 0
    assert engine.broker.get_positions() == []
    assert engine.ledger.open_positions() == []


def test_empty_plan_without_stop_hit_does_not_orphan(
    tmp_path, monkeypatch, firm_db, prices
) -> None:
    engine = _engine(tmp_path, monkeypatch, firm_db, prices, plan=TradingPlan())
    _open_long(engine, prices)

    report = engine.run_cycle()

    assert report.exit_supervision_ran is True
    assert report.positions_closed == 0
    assert engine.open_exposure_count() == 1
    assert may_stop_for_empty_plan(plan_empty=True, open_count=engine.open_exposure_count()) is False


def test_unhealthy_broker_does_not_invent_fills(
    tmp_path, monkeypatch, firm_db, prices
) -> None:
    """BLIND: skip this cycle's poll. Process-level keep-alive is the runner."""
    engine = _engine(tmp_path, monkeypatch, firm_db, prices, plan=TradingPlan())
    _open_long(engine, prices)
    _drive_through_stop(prices)
    monkeypatch.setattr(engine.broker, "health_check", lambda: (False, "feed down"))

    report = engine.run_cycle()

    assert report.halted is True
    assert report.entries_blocked is True
    assert report.exit_supervision_ran is False
    assert report.positions_closed == 0
    assert len(engine.broker.get_positions()) == 1
    assert len(engine.ledger.open_positions()) == 1


def test_recon_mismatch_still_polls_paper_stops(
    tmp_path, monkeypatch, firm_db, prices
) -> None:
    """Recon trip used to return before manage. Paper stops must still fire."""
    engine = _engine(tmp_path, monkeypatch, firm_db, prices, plan=_scan_plan())
    _open_long(engine, prices)
    _drive_through_stop(prices)
    monkeypatch.setattr(engine.ledger, "reconcile", lambda _snaps: ["qty mismatch"])

    report = engine.run_cycle()

    assert report.halted is True
    assert "reconciliation mismatch" in report.halt_reason
    assert report.exit_supervision_ran is True
    assert report.positions_closed == 1
    assert report.orders_placed == 0
    assert engine.broker.get_positions() == []


def test_dirty_recon_does_not_settle_live_missing_rows(tmp_path, monkeypatch) -> None:
    """F05 must not 'fix' F06 by ticker-settling a dirty live book."""
    from core.execution import engine as engine_mod

    monkeypatch.setattr(engine_mod, "LAST_CYCLE_PATH", tmp_path / "last_cycle.json")
    broker = MagicMock()
    broker.health_check.return_value = (True, "ok")
    broker.get_balance.return_value = STARTING
    broker.get_positions.return_value = []
    broker.get_price.return_value = 50_000.0
    ledger = MagicMock()
    ledger.reconcile.return_value = ["BTCUSDT: open in ledger but not at broker"]
    ledger.open_positions.return_value = [
        SimpleNamespace(
            id=1,
            symbol=SYMBOL,
            quantity=0.01,
            entry_price=100_000.0,
            entry_fee=0.0,
        )
    ]
    ledger.record_risk_event.return_value = None
    ledger.record_equity.return_value = None
    ledger.portfolio_state.return_value = MagicMock()
    risk = MagicMock()
    risk.kill_switch.is_tripped = False
    risk.kill_switch.trip.return_value = None
    risk.check_portfolio_health.return_value = []
    engine = TradingEngine(
        broker=broker,
        risk_engine=risk,
        ledger=ledger,
        plan=TradingPlan(),
        data_source=MagicMock(),
    )
    monkeypatch.setattr(engine, "refresh_scan_plan", lambda: False)

    report = engine.run_cycle()

    assert report.halted is True
    assert report.exit_supervision_ran is True
    ledger.close_position.assert_not_called()


def test_wait_poll_closes_paper_stop(tmp_path, monkeypatch, firm_db, prices) -> None:
    """Tight wait-loop poll is the independent paper stop path (F05 / F15 overlap)."""
    engine = _engine(tmp_path, monkeypatch, firm_db, prices, plan=TradingPlan())
    _open_long(engine, prices)
    _drive_through_stop(prices)

    wait_for_next_cycle(
        engine,
        PAPER_EXIT_POLL_SECONDS,
        shutdown=lambda: False,
        sleep=lambda _s: None,
        poll_seconds=PAPER_EXIT_POLL_SECONDS,
    )

    assert engine.broker.get_positions() == []
    assert engine.ledger.open_positions() == []


def test_wait_poll_skips_non_paper_broker() -> None:
    engine = MagicMock()
    engine.broker = MagicMock()  # not a PaperBroker
    wait_for_next_cycle(engine, 15, shutdown=lambda: False, sleep=lambda _s: None)
    engine.supervise_exits.assert_not_called()
