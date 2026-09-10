"""Regime sit-outs are metadata, not a research kill.

Overall OOS gates (PF >= 1.15, CI excludes zero, beats-random) stay hard.
A net-negative bear/bull/chop sleeve is approved with blocked_regimes so
paper can skip new entries while that regime is active.
"""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

from config.settings import TradingMode
from config.universe import ShortParams, Universe
from core.execution.engine import PlanEntry, build_plan, paper_regime_sitout_reason
from core.strategy.base import SignalSide
from research.validate import (
    DEFAULT_CRITERIA,
    SymbolVerdict,
    _evaluate_gates,
    activation_mode_for,
    adverse_regimes,
    blocked_regimes_from_record,
    write_approvals,
)


class _PassingWF:
    """Walk-forward stub that clears every aggregate OOS gate."""

    def __init__(self, **overrides) -> None:
        self.total_oos_trades = 40
        self.oos_profit_factor = 1.40
        self.oos_expectancy_pct = 0.25
        self.oos_max_drawdown_pct = 8.0
        self.profitable_fold_ratio = 60.0
        self._stability: dict = {}
        self.oos_win_rate = 55.0
        self.folds: list = []
        for key, value in overrides.items():
            setattr(self, key, value)

    def parameter_stability(self) -> dict:
        return self._stability


def _significance(*, ci_ok: bool = True, beats: bool = True, p_value: float = 0.01):
    return SimpleNamespace(
        bootstrap=SimpleNamespace(is_significant=ci_ok),
        permutation=SimpleNamespace(beats_random=beats, p_value=p_value),
    )


def test_adverse_regimes_require_five_trades_and_nonpositive_expectancy() -> None:
    losing = adverse_regimes(
        {
            "bull": {"trades": 12, "expectancy_pct": -0.10},
            "bear": {"trades": 8, "expectancy_pct": 0.40},
            "chop": {"trades": 3, "expectancy_pct": -1.00},  # too thin to count
        }
    )
    assert losing == ["bull"]


def test_evaluate_gates_regime_loss_is_not_a_hard_fail() -> None:
    """Aggregate OOS already clears PF / CI / beats-random — do not reject."""
    failures = _evaluate_gates(_PassingWF(), _significance(), DEFAULT_CRITERIA)
    assert failures == []
    assert not any("loses money in regime" in reason for reason in failures)


def test_evaluate_gates_still_fails_weak_profit_factor() -> None:
    failures = _evaluate_gates(
        _PassingWF(oos_profit_factor=1.05),
        _significance(),
        DEFAULT_CRITERIA,
    )
    assert any("profit factor" in reason and "1.15" in reason for reason in failures)
    assert not any("loses money in regime" in reason for reason in failures)


def test_evaluate_gates_still_fails_ci_including_zero() -> None:
    failures = _evaluate_gates(
        _PassingWF(),
        _significance(ci_ok=False),
        DEFAULT_CRITERIA,
    )
    assert "expectancy confidence interval includes zero" in failures


def test_evaluate_gates_still_fails_when_it_does_not_beat_random() -> None:
    failures = _evaluate_gates(
        _PassingWF(),
        _significance(beats=False, p_value=0.40),
        DEFAULT_CRITERIA,
    )
    assert any("does not beat random entries" in reason for reason in failures)


def test_blocked_regimes_from_record_prefers_structured_fields() -> None:
    rec = {
        "regime_disable": ["bull", "chop"],
        "blocked_regimes": ["bear"],
        "failures": ["loses money in regime(s): bear"],
    }
    assert blocked_regimes_from_record(rec) == ["bull", "chop"]


def test_blocked_regimes_from_record_parses_legacy_failure_string() -> None:
    rec = {"failures": ["loses money in regime(s): bear, chop"]}
    assert blocked_regimes_from_record(rec) == ["bear", "chop"]


def test_activation_mode_regime_gated_only_when_approved() -> None:
    assert activation_mode_for(approved=True, blocked=["bull"]) == "regime_gated"
    assert activation_mode_for(approved=True, blocked=[]) == "unrestricted"
    assert activation_mode_for(approved=False, blocked=["bull"]) == "rejected"


def test_write_approvals_persists_regime_sitout_metadata(tmp_path) -> None:
    path = tmp_path / "approved_strategies.json"
    wf = _PassingWF()
    verdict = SymbolVerdict(
        symbol="ETHUSDT",
        side="SHORT",
        timeframe="4h",
        strategy="mama_fama_cross",
        walk_forward=wf,  # type: ignore[arg-type]
        regime_results={
            "bull": {"trades": 10, "expectancy_pct": -0.2, "net_pnl": -12.0},
            "bear": {"trades": 14, "expectancy_pct": 0.5, "net_pnl": 40.0},
            "chop": {"trades": 8, "expectancy_pct": 0.1, "net_pnl": 4.0},
        },
        blocked_regimes=["bull"],
        failures=[],
    )
    assert verdict.approved is True
    assert verdict.activation_mode == "regime_gated"
    write_approvals([verdict], path=path)
    rec = json.loads(path.read_text(encoding="utf-8"))["mama_fama_cross:ETHUSDT:SHORT:4h"]
    assert rec["approved"] is True
    assert rec["failures"] == []
    assert rec["blocked_regimes"] == ["bull"]
    assert rec["regime_disable"] == ["bull"]
    assert rec["activation_mode"] == "regime_gated"
    assert rec["regime_results"]["bull"]["expectancy_pct"] == -0.2


def test_symbol_verdict_approved_despite_blocked_regimes() -> None:
    verdict = SymbolVerdict(
        symbol="BTCUSDT",
        side="LONG",
        walk_forward=MagicMock(folds=[]),
        blocked_regimes=["bear", "chop"],
        failures=[],
    )
    assert verdict.approved is True
    assert "loses money" not in " ".join(verdict.failures)
    assert verdict.regime_disable == ["bear", "chop"]


def test_paper_plan_consumes_blocked_regimes(monkeypatch) -> None:
    universe = Universe(
        long_params={},
        short_params={"BTCUSDT": ShortParams(symbol="BTCUSDT", timeframe="4h")},
        approvals={
            "atr_channel_breakout:BTCUSDT:SHORT:4h": {
                "approved": True,
                "timeframe": "4h",
                "strategy": "atr_channel_breakout",
                "params": {"atr_k": 2.0},
                "blocked_regimes": ["bull"],
                "regime_disable": ["bull"],
                "activation_mode": "regime_gated",
            }
        },
    )
    monkeypatch.setattr("core.execution.engine.get_universe", lambda: universe)
    monkeypatch.setattr("firm.research_jobs.paper_scan_family", lambda: "bb_squeeze_breakout")
    monkeypatch.setattr("firm.research_jobs._active_job_for", lambda family: None)

    paper = build_plan(require_approval=False, candidates=["BTCUSDT"])
    gated = [
        e
        for e in paper.entries
        if e.strategy.name == "atr_channel_breakout" and e.symbol == "BTCUSDT"
    ]
    assert gated, "regime-gated approved sleeve must stay on the paper blotter"
    assert gated[0].blocked_regimes == ("bull",)
    assert gated[0].activation_mode == "regime_gated"

    live = build_plan(require_approval=True)
    assert any(e.strategy.name == "atr_channel_breakout" for e in live.entries)


def test_paper_sits_out_in_blocked_regime() -> None:
    strategy = MagicMock()
    strategy.name = "atr_channel_breakout"
    entry = PlanEntry(
        symbol="BTCUSDT",
        side=SignalSide.SHORT,
        strategy=strategy,
        timeframe="4h",
        blocked_regimes=("bull",),
        activation_mode="regime_gated",
    )
    reason = paper_regime_sitout_reason(
        entry,
        current_regime="bull",
        trading_mode=TradingMode.PAPER,
        lookup_regime=False,
    )
    assert reason is not None
    assert "regime sit-out" in reason
    assert "bull" in reason

    # Other regimes still trade.
    assert (
        paper_regime_sitout_reason(
            entry,
            current_regime="bear",
            trading_mode=TradingMode.PAPER,
            lookup_regime=False,
        )
        is None
    )
    # Unknown regime fails open.
    assert (
        paper_regime_sitout_reason(
            entry,
            current_regime=None,
            trading_mode=TradingMode.PAPER,
            lookup_regime=False,
        )
        is None
    )
    # Live never sits out here — go-live is the live gate.
    assert (
        paper_regime_sitout_reason(
            entry,
            current_regime="bull",
            trading_mode=TradingMode.LIVE,
            lookup_regime=False,
        )
        is None
    )


def test_engine_scan_loop_records_regime_sitout(monkeypatch) -> None:
    """Paper cycle must skip new entries, not drop the sleeve from the plan."""
    from core.execution.engine import TradingEngine, TradingPlan

    strategy = MagicMock()
    strategy.name = "atr_channel_breakout"
    entry = PlanEntry(
        symbol="BTCUSDT",
        side=SignalSide.SHORT,
        strategy=strategy,
        timeframe="4h",
        blocked_regimes=("bull",),
        activation_mode="regime_gated",
    )
    broker = MagicMock()
    broker.health_check.return_value = (True, "ok")
    broker.get_balance.return_value = 10_000.0
    broker.get_positions.return_value = []
    risk = MagicMock()
    risk.kill_switch.is_tripped = False
    risk.check_portfolio_health.return_value = []
    ledger = MagicMock()
    ledger.reconcile.return_value = []
    ledger.open_positions.return_value = []
    engine = TradingEngine(
        broker=broker,
        risk_engine=risk,
        ledger=ledger,
        plan=TradingPlan(entries=[entry]),
        data_source=MagicMock(),
    )
    monkeypatch.setattr(engine, "refresh_scan_plan", lambda: False)
    monkeypatch.setattr(engine, "_manage_open_positions", lambda: 0)
    monkeypatch.setattr(engine, "_refresh_crowding", lambda: None)
    monkeypatch.setattr(
        "core.execution.engine.paper_regime_sitout_reason",
        lambda _entry: "regime sit-out: bull is blocked for atr_channel_breakout (bull)",
    )
    monkeypatch.setattr("core.execution.engine.persist_last_cycle", lambda *a, **k: None)
    report = engine.run_cycle()
    assert report.orders_placed == 0
    assert report.signals_found == 0
    assert report.rejections == [
        ("BTCUSDT", "regime sit-out: bull is blocked for atr_channel_breakout (bull)")
    ]


def test_paper_scan_sleeves_remain_empty() -> None:
    from config.pipeline import PAPER_SCAN_SLEEVES

    assert PAPER_SCAN_SLEEVES == ()
