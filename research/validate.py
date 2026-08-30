"""
The validation pipeline: the only route by which a strategy earns trading rights.

Combines every guard built in this package into a single verdict per
symbol/side, then writes `config/approved_strategies.json`. Nothing else in the
firm can grant trading approval -- not a config flag, not an agent, not a human
editing a Python file.

Gate structure, deliberately two-tier:

* **Per-symbol approval** clears one symbol/side to trade. Requires enough
  out-of-sample trades to be measurable, a profit factor above 1, positive
  expectancy whose bootstrap interval excludes zero, and stable parameters.
* **Portfolio go-live** (checked separately, in `scripts/check_go_live.py`)
  requires the full plan gates: 300+ OOS trades across 3+ regimes including a
  bear, aggregate PF >= 1.3, drawdown < 15%.

A symbol can be approved for paper trading while the portfolio remains far from
live-ready. That is the intended state for a long time.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

from config.universe import APPROVALS_PATH
from core.data.funding import FundingHistory
from core.strategy.base import SignalSide, StrategyParams
from core.strategy.rsi_golden_cross import RsiTrendParams, RsiTrendStrategy
from research.datasets import Period, Regime
from research.engine import BacktestConfig, BacktestEngine
from research.significance import SignificanceReport, assess
from research.walkforward import WalkForwardResult, walk_forward

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Per-symbol approval thresholds
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ApprovalCriteria:
    """Thresholds a single symbol/side must clear to be allowed to trade."""

    min_oos_trades: int = 30
    min_profit_factor: float = 1.15
    min_expectancy_pct: float = 0.0
    require_significant_expectancy: bool = True
    max_drawdown_pct: float = 25.0
    min_profitable_fold_ratio: float = 50.0
    #: Coefficient of variation above which optimised parameters are considered
    #: unstable, i.e. fitted to noise.
    max_parameter_cv: float = 0.35


DEFAULT_CRITERIA = ApprovalCriteria()


@dataclass
class SymbolVerdict:
    """Validation outcome for one symbol/side."""

    symbol: str
    side: str
    timeframe: str = "15m"
    reoptimise_days: int = 60
    walk_forward: WalkForwardResult | None = None
    significance: SignificanceReport | None = None
    regime_results: dict[str, dict[str, Any]] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)
    error: str | None = None

    @property
    def approved(self) -> bool:
        return not self.failures and self.error is None and self.walk_forward is not None

    @property
    def selected_params(self) -> dict[str, Any]:
        """Parameters live trading should use right now.

        Walk-forward validates a *process* -- "optimise on the trailing window,
        trade the next one" -- not a single fixed parameter set. The honest
        translation to live trading is therefore the choice the most recent fold
        made, refreshed every `reoptimise_days`. Freezing the whole-history
        optimum instead would be trading a parameter set that was never tested
        out of sample.
        """
        if self.walk_forward is None:
            return {}
        for fold in reversed(self.walk_forward.folds):
            if fold.best_params:
                return dict(fold.best_params)
        return {}

    def summary(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "side": self.side,
            "timeframe": self.timeframe,
            "approved": self.approved,
            "failures": self.failures,
            "error": self.error,
            "selected_params": self.selected_params,
            "walk_forward": self.walk_forward.summary() if self.walk_forward else None,
            "significance": self.significance.summary() if self.significance else None,
            "by_regime": self.regime_results,
        }

    def __str__(self) -> str:
        if self.error:
            return f"{self.symbol} {self.side}: ERROR - {self.error}"
        status = "APPROVED" if self.approved else "REJECTED"
        detail = f" ({'; '.join(self.failures)})" if self.failures else ""
        wf = f" | {self.walk_forward}" if self.walk_forward else ""
        return f"{self.symbol} {self.side}: {status}{detail}{wf}"


def strategy_factory_for(side: SignalSide):
    """Return a factory that builds the RSI/trend strategy for one side."""

    def factory(params: StrategyParams) -> RsiTrendStrategy:
        return RsiTrendStrategy(params)  # type: ignore[arg-type]

    del side  # side is carried inside the params object
    return factory


def default_search_space(side: SignalSide) -> dict[str, list[Any]]:
    """Parameter grid searched per walk-forward fold.

    Kept deliberately small. A grid of thousands of combinations against a
    180-day training window guarantees an overfit winner; the point of the
    search is to adapt coarsely to regime, not to find a magic setting.
    """
    if side is SignalSide.LONG:
        return {
            "rsi_min": [25.0, 30.0, 35.0],
            "rsi_max": [40.0, 45.0, 50.0],
            "volume_threshold": [1.0, 1.2, 1.5],
            "take_profit_pct": [0.03, 0.05],
            "stop_loss_pct": [0.02, 0.03, 0.05],
        }
    return {
        "rsi_threshold": [60.0, 65.0, 70.0],
        "volume_threshold": [1.0, 1.2, 1.5],
        "take_profit_pct": [0.03, 0.05],
        "stop_loss_pct": [0.02, 0.03, 0.05],
    }


def validate_symbol(
    symbol: str,
    side: SignalSide,
    candles: pd.DataFrame,
    config: BacktestConfig,
    periods: list[Period] | None = None,
    funding: FundingHistory | None = None,
    criteria: ApprovalCriteria = DEFAULT_CRITERIA,
    search_space: dict[str, list[Any]] | None = None,
    train_days: int = 180,
    test_days: int = 60,
    timeframe: str = "15m",
) -> SymbolVerdict:
    """Run the full validation pipeline for one symbol/side."""
    verdict = SymbolVerdict(
        symbol=symbol, side=side.value, timeframe=timeframe, reoptimise_days=test_days
    )

    if candles.empty or len(candles) < 3_000:
        verdict.error = f"insufficient history ({len(candles)} bars)"
        return verdict

    base_params = RsiTrendParams(side=side)
    factory = strategy_factory_for(side)
    space = search_space if search_space is not None else default_search_space(side)

    try:
        wf = walk_forward(
            symbol=symbol,
            candles=candles,
            strategy_factory=factory,
            base_params=base_params,
            search_space=space,
            config=config,
            train_days=train_days,
            test_days=test_days,
            funding=funding,
        )
    except Exception as exc:
        logger.exception("Walk-forward failed for %s %s", symbol, side.value)
        verdict.error = f"walk-forward failed: {exc}"
        return verdict

    verdict.walk_forward = wf
    oos_trades = wf.oos_trades

    verdict.significance = assess(
        oos_trades, candles=candles, position_fraction=config.position_fraction
    )

    if periods:
        verdict.regime_results = _regime_breakdown(oos_trades, periods)

    verdict.failures = _evaluate_gates(wf, verdict.significance, verdict.regime_results, criteria)
    return verdict


def _evaluate_gates(
    wf: WalkForwardResult,
    significance: SignificanceReport,
    regime_results: dict[str, dict[str, Any]],
    criteria: ApprovalCriteria,
) -> list[str]:
    """Collect every reason a symbol fails approval.

    All gates are evaluated rather than short-circuiting, so the report explains
    the full picture instead of only the first problem.
    """
    failures: list[str] = []

    if wf.total_oos_trades < criteria.min_oos_trades:
        failures.append(
            f"only {wf.total_oos_trades} OOS trades (need >= {criteria.min_oos_trades})"
        )

    pf = wf.oos_profit_factor
    if np.isfinite(pf) and pf < criteria.min_profit_factor:
        failures.append(f"OOS profit factor {pf:.2f} < {criteria.min_profit_factor}")

    if wf.oos_expectancy_pct <= criteria.min_expectancy_pct:
        failures.append(f"OOS expectancy {wf.oos_expectancy_pct:+.3f}% is not positive")

    if wf.oos_max_drawdown_pct > criteria.max_drawdown_pct:
        failures.append(
            f"OOS drawdown {wf.oos_max_drawdown_pct:.1f}% > {criteria.max_drawdown_pct}%"
        )

    if wf.profitable_fold_ratio < criteria.min_profitable_fold_ratio:
        failures.append(
            f"only {wf.profitable_fold_ratio:.0f}% of folds profitable "
            f"(need >= {criteria.min_profitable_fold_ratio:.0f}%)"
        )

    if criteria.require_significant_expectancy:
        if significance.bootstrap is None or not significance.bootstrap.is_significant:
            failures.append("expectancy confidence interval includes zero")
        if significance.permutation and not significance.permutation.beats_random:
            failures.append(
                f"does not beat random entries (p={significance.permutation.p_value:.3f})"
            )

    unstable = [
        f"{name} (cv={stats['cv']:.2f})"
        for name, stats in wf.parameter_stability().items()
        if stats["cv"] > criteria.max_parameter_cv
    ]
    if unstable:
        failures.append("unstable parameters: " + ", ".join(unstable))

    # A strategy that only works in one regime is a bet on that regime.
    if regime_results:
        losing = [
            name
            for name, stats in regime_results.items()
            if stats.get("trades", 0) >= 5 and stats.get("expectancy_pct", 0.0) <= 0
        ]
        if losing:
            failures.append(f"loses money in regime(s): {', '.join(sorted(losing))}")

    return failures


def _regime_breakdown(trades: list, periods: list[Period]) -> dict[str, dict[str, Any]]:
    """Aggregate out-of-sample trades by market regime.

    Reported per regime rather than per quarter: the question is whether the
    strategy survives a bear market, not how it did in one specific quarter.
    """
    buckets: dict[str, list] = {r.value: [] for r in Regime}

    for trade in trades:
        entry = pd.Timestamp(trade.entry_time)
        for period in periods:
            if pd.Timestamp(period.start) <= entry <= pd.Timestamp(period.end):
                buckets[period.regime.value].append(trade)
                break

    breakdown: dict[str, dict[str, Any]] = {}
    for regime, bucket in buckets.items():
        if not bucket:
            breakdown[regime] = {"trades": 0}
            continue

        returns = [t.return_pct for t in bucket]
        wins = [t for t in bucket if t.is_win]
        profit = sum(t.net_pnl for t in wins)
        loss = abs(sum(t.net_pnl for t in bucket if not t.is_win))

        breakdown[regime] = {
            "trades": len(bucket),
            "win_rate": round(len(wins) / len(bucket) * 100.0, 2),
            "expectancy_pct": round(float(np.mean(returns)), 4),
            "profit_factor": round(profit / loss, 3) if loss > 0 else None,
            "net_pnl": round(sum(t.net_pnl for t in bucket), 2),
        }

    return breakdown


def evaluate_baseline_by_regime(
    symbol: str,
    side: SignalSide,
    candles: pd.DataFrame,
    periods: list[Period],
    config: BacktestConfig,
    funding: FundingHistory | None = None,
) -> dict[str, Any]:
    """Run the *unoptimised* baseline parameters separately in each period.

    Complements walk-forward by answering a simpler question: do the legacy
    parameters, exactly as configured, work outside the window they were fitted
    to? This is the direct test the legacy project never ran.
    """
    engine = BacktestEngine(config)
    strategy = RsiTrendStrategy(RsiTrendParams(side=side))
    out: dict[str, Any] = {}

    for period in periods:
        start_index = candles.index.searchsorted(pd.Timestamp(period.start))
        end_index = candles.index.searchsorted(pd.Timestamp(period.end), side="right")
        window = candles.iloc[max(0, start_index - 300) : end_index]

        if len(window) < strategy.min_bars + 50:
            continue

        result = engine.run(symbol, window, strategy, funding)
        out[period.name] = {
            "regime": period.regime.value,
            "trades": result.total_trades,
            "win_rate": round(result.win_rate, 2),
            "profit_factor": (
                round(result.profit_factor, 3) if np.isfinite(result.profit_factor) else None
            ),
            "return_pct": round(result.total_return_pct, 3),
            "expectancy_pct": round(result.expectancy_pct, 4),
        }

    return out


def write_approvals(verdicts: list[SymbolVerdict], path=APPROVALS_PATH) -> dict[str, Any]:
    """Merge approval decisions into `config/approved_strategies.json`.

    Records rejections as well as approvals: an auditable "why is this symbol
    not trading?" record matters as much as the permission itself.

    Merges rather than overwrites, because longs and shorts are validated in
    separate runs on different timeframes. A plain overwrite would silently
    revoke every verdict from the other run.
    """
    payload: dict[str, Any] = {}
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Existing approvals unreadable (%s); starting fresh.", exc)
            payload = {}

    payload["_generated_at"] = datetime.now(timezone.utc).isoformat()
    payload["_readme"] = (
        "Written by research/validate.py. This file is the ONLY source of "
        "trading rights. Do not hand-edit: rerun validation instead."
    )

    for verdict in verdicts:
        wf = verdict.walk_forward
        payload[f"{verdict.symbol}:{verdict.side}"] = {
            "approved": verdict.approved,
            "failures": verdict.failures,
            "error": verdict.error,
            "timeframe": verdict.timeframe,
            # The live engine trades these, refreshed every reoptimise_days.
            "params": verdict.selected_params,
            "reoptimise_days": verdict.reoptimise_days,
            "oos_trades": wf.total_oos_trades if wf else 0,
            "oos_win_rate": round(wf.oos_win_rate, 2) if wf else 0.0,
            "oos_profit_factor": (
                round(wf.oos_profit_factor, 3)
                if wf and np.isfinite(wf.oos_profit_factor)
                else None
            ),
            "oos_expectancy_pct": round(wf.oos_expectancy_pct, 4) if wf else 0.0,
            "oos_max_drawdown_pct": round(wf.oos_max_drawdown_pct, 2) if wf else 0.0,
            "validated_at": datetime.now(timezone.utc).isoformat(),
        }

    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    logger.info("Wrote approvals for %d symbol/side pairs to %s", len(verdicts), path)
    return payload
