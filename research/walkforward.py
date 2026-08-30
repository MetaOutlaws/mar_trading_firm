"""
Walk-forward validation and parameter optimisation.

An in-sample backtest measures how well parameters were fitted to the past, not
whether a strategy works. Walk-forward fixes that: optimise on a training
window, evaluate on the *next* untouched window, roll forward, repeat. Only the
out-of-sample results count.

Two outputs matter beyond the headline metrics:

* **Aggregate out-of-sample performance** across all folds. This is the honest
  estimate of what live trading would have produced.
* **Parameter stability.** If the optimal parameters lurch between folds, the
  optimiser is fitting noise, and no amount of good OOS performance in one fold
  should be trusted.

The objective function deserves a note. Ranking by profit factor alone rewards a
3-trade fluke with an infinite score, which is how the legacy project convinced
itself a 10-trade sample proved a 90% win rate. Here the objective is a
t-statistic-like quantity, `mean_return * sqrt(n)`, which grows with both edge
size and sample size, and a hard minimum trade count discards thin samples.
"""

from __future__ import annotations

import itertools
import logging
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from typing import Any, Callable, Sequence

import numpy as np
import pandas as pd

from core.data.funding import FundingHistory
from core.strategy.base import Strategy, StrategyParams
from research.engine import BacktestConfig, BacktestEngine, BacktestResult, Trade

logger = logging.getLogger(__name__)

#: Folds with fewer trades than this are treated as uninformative.
MIN_TRADES_PER_FOLD = 5


def objective_t_stat(result: BacktestResult, min_trades: int = MIN_TRADES_PER_FOLD) -> float:
    """Score a backtest by edge size scaled by sample size.

    `mean_return * sqrt(n)` is proportional to a t-statistic on per-trade
    returns. It prefers a small consistent edge over many trades to a large edge
    over three, which is the correct preference when the goal is a strategy that
    keeps working.
    """
    if result.total_trades < min_trades:
        return float("-inf")

    returns = np.array([t.return_pct for t in result.trades])
    if returns.std(ddof=1) == 0:
        return float("-inf")

    return float(returns.mean() / returns.std(ddof=1) * np.sqrt(len(returns)))


@dataclass
class Fold:
    """One train/test split and its results."""

    index: int
    train_start: datetime
    train_end: datetime
    test_start: datetime
    test_end: datetime
    best_params: dict[str, Any] = field(default_factory=dict)
    train_result: BacktestResult | None = None
    test_result: BacktestResult | None = None

    @property
    def is_valid(self) -> bool:
        """Whether this fold produced a usable out-of-sample measurement."""
        return self.test_result is not None and self.test_result.total_trades > 0

    def summary(self) -> dict[str, Any]:
        return {
            "fold": self.index,
            "train": f"{self.train_start.date()}..{self.train_end.date()}",
            "test": f"{self.test_start.date()}..{self.test_end.date()}",
            "best_params": self.best_params,
            "train_trades": self.train_result.total_trades if self.train_result else 0,
            "train_win_rate": round(self.train_result.win_rate, 2) if self.train_result else 0.0,
            "test_trades": self.test_result.total_trades if self.test_result else 0,
            "test_win_rate": round(self.test_result.win_rate, 2) if self.test_result else 0.0,
            "test_return_pct": (
                round(self.test_result.total_return_pct, 3) if self.test_result else 0.0
            ),
            "test_expectancy_pct": (
                round(self.test_result.expectancy_pct, 4) if self.test_result else 0.0
            ),
        }


@dataclass
class WalkForwardResult:
    """Aggregated out-of-sample results across all folds."""

    symbol: str
    strategy: str
    side: str
    folds: list[Fold] = field(default_factory=list)

    @property
    def oos_trades(self) -> list[Trade]:
        """Every out-of-sample trade, in chronological order."""
        trades: list[Trade] = []
        for fold in self.folds:
            if fold.test_result:
                trades.extend(fold.test_result.trades)
        return sorted(trades, key=lambda t: t.entry_time)

    @property
    def total_oos_trades(self) -> int:
        return len(self.oos_trades)

    @property
    def oos_win_rate(self) -> float:
        trades = self.oos_trades
        if not trades:
            return 0.0
        return sum(1 for t in trades if t.is_win) / len(trades) * 100.0

    @property
    def oos_profit_factor(self) -> float:
        trades = self.oos_trades
        profit = sum(t.net_pnl for t in trades if t.is_win)
        loss = abs(sum(t.net_pnl for t in trades if not t.is_win))
        if loss == 0:
            return float("inf") if profit > 0 else 0.0
        return profit / loss

    @property
    def oos_expectancy_pct(self) -> float:
        trades = self.oos_trades
        if not trades:
            return 0.0
        return float(np.mean([t.return_pct for t in trades]))

    @property
    def oos_equity_curve(self) -> pd.Series:
        """Compounded equity (starting at 1.0) across stitched OOS folds.

        Each fold restarts the engine at its initial capital, so fold P&L cannot
        simply be summed. Instead each trade's *account* return is recovered
        from its recorded P&L and the equity it produced, then compounded. This
        makes the curve comparable to one continuous run.
        """
        trades = self.oos_trades
        if not trades:
            return pd.Series(dtype="float64")

        equity = 1.0
        stamps: list[pd.Timestamp] = []
        values: list[float] = []

        for trade in trades:
            equity_before = trade.equity_after - trade.net_pnl
            if equity_before <= 0:
                continue
            equity *= 1.0 + trade.net_pnl / equity_before
            stamps.append(pd.Timestamp(trade.exit_time))
            values.append(equity)

        return pd.Series(values, index=pd.DatetimeIndex(stamps))

    @property
    def oos_max_drawdown_pct(self) -> float:
        curve = self.oos_equity_curve
        if curve.empty:
            return 0.0
        peak = curve.cummax()
        return abs(float(((curve - peak) / peak).min())) * 100.0

    @property
    def profitable_fold_ratio(self) -> float:
        """Share of valid folds that made money out of sample.

        More informative than the aggregate: a strategy carried by one
        spectacular fold is not a strategy.
        """
        valid = [f for f in self.folds if f.is_valid]
        if not valid:
            return 0.0
        winners = sum(1 for f in valid if f.test_result.total_return_pct > 0)  # type: ignore[union-attr]
        return winners / len(valid) * 100.0

    def parameter_stability(self) -> dict[str, dict[str, float]]:
        """Spread of each optimised parameter across folds.

        A coefficient of variation above ~0.3 means the optimiser is chasing
        noise, and the strategy's apparent edge is fragile.
        """
        collected: dict[str, list[float]] = {}
        for fold in self.folds:
            for key, value in fold.best_params.items():
                if isinstance(value, (int, float)) and not isinstance(value, bool):
                    collected.setdefault(key, []).append(float(value))

        stability: dict[str, dict[str, float]] = {}
        for key, values in collected.items():
            if len(values) < 2:
                continue
            mean = float(np.mean(values))
            std = float(np.std(values, ddof=1))
            stability[key] = {
                "mean": round(mean, 4),
                "std": round(std, 4),
                "min": round(min(values), 4),
                "max": round(max(values), 4),
                # Coefficient of variation: dimensionless instability measure.
                "cv": round(std / abs(mean), 4) if mean else 0.0,
            }
        return stability

    def summary(self) -> dict[str, Any]:
        pf = self.oos_profit_factor
        return {
            "symbol": self.symbol,
            "strategy": self.strategy,
            "side": self.side,
            "folds": len(self.folds),
            "valid_folds": sum(1 for f in self.folds if f.is_valid),
            "oos_trades": self.total_oos_trades,
            "oos_win_rate": round(self.oos_win_rate, 2),
            "oos_profit_factor": round(pf, 3) if np.isfinite(pf) else None,
            "oos_expectancy_pct": round(self.oos_expectancy_pct, 4),
            "oos_max_drawdown_pct": round(self.oos_max_drawdown_pct, 2),
            "profitable_fold_ratio": round(self.profitable_fold_ratio, 1),
            "parameter_stability": self.parameter_stability(),
            "fold_details": [f.summary() for f in self.folds],
        }

    def __str__(self) -> str:
        pf = f"{self.oos_profit_factor:.2f}" if np.isfinite(self.oos_profit_factor) else "inf"
        return (
            f"{self.symbol} {self.side} OOS | {self.total_oos_trades} trades | "
            f"WR {self.oos_win_rate:.1f}% | PF {pf} | "
            f"Exp {self.oos_expectancy_pct:+.3f}%/trade | "
            f"DD {self.oos_max_drawdown_pct:.1f}% | "
            f"{self.profitable_fold_ratio:.0f}% folds profitable"
        )


def grid_search(
    symbol: str,
    candles: pd.DataFrame,
    strategy_factory: Callable[[StrategyParams], Strategy],
    base_params: StrategyParams,
    search_space: dict[str, Sequence[Any]],
    config: BacktestConfig,
    funding: FundingHistory | None = None,
    objective: Callable[[BacktestResult], float] = objective_t_stat,
) -> tuple[StrategyParams, BacktestResult | None, float]:
    """Exhaustively search `search_space` and return the best parameter set.

    Args:
        symbol: Symbol under test.
        candles: Candles for the training window.
        strategy_factory: Builds a strategy from a parameter set.
        base_params: Starting parameters; search values override fields on it.
        search_space: Field name -> candidate values.
        config: Backtest configuration (costs, sizing).
        funding: Funding history for realistic carry.
        objective: Scoring function; higher is better.

    Returns:
        (best_params, best_result, best_score). Score is -inf when nothing
        cleared the minimum trade count.
    """
    engine = BacktestEngine(config)

    keys = list(search_space)
    combinations = list(itertools.product(*(search_space[k] for k in keys)))

    best_params = base_params
    best_result: BacktestResult | None = None
    best_score = float("-inf")

    for combination in combinations:
        candidate = replace(base_params, **dict(zip(keys, combination)))
        try:
            result = engine.run(symbol, candles, strategy_factory(candidate), funding)
        except Exception as exc:
            logger.debug("Parameter set %s failed: %s", dict(zip(keys, combination)), exc)
            continue

        score = objective(result)
        if score > best_score:
            best_score, best_params, best_result = score, candidate, result

    return best_params, best_result, best_score


def walk_forward(
    symbol: str,
    candles: pd.DataFrame,
    strategy_factory: Callable[[StrategyParams], Strategy],
    base_params: StrategyParams,
    search_space: dict[str, Sequence[Any]],
    config: BacktestConfig,
    train_days: int = 180,
    test_days: int = 60,
    warmup_bars: int = 300,
    funding: FundingHistory | None = None,
    objective: Callable[[BacktestResult], float] = objective_t_stat,
) -> WalkForwardResult:
    """Run rolling-window walk-forward validation.

    Args:
        symbol: Symbol under test.
        candles: Full candle history.
        strategy_factory: Builds a strategy from a parameter set.
        base_params: Baseline parameters.
        search_space: Parameters to optimise per fold. Empty dict skips
            optimisation and simply evaluates `base_params` out of sample.
        config: Backtest configuration.
        train_days: Length of each in-sample optimisation window.
        test_days: Length of each out-of-sample window; also the roll step, so
            test windows tile the history without overlapping.
        warmup_bars: Bars prepended to each window for indicator warm-up.
        funding: Funding history.
        objective: Fold scoring function.
    """
    side = getattr(base_params, "side", None)
    side_label = side.value if side is not None else "BOTH"

    result = WalkForwardResult(
        symbol=symbol,
        strategy=strategy_factory(base_params).name,
        side=side_label,
    )

    if candles.empty:
        logger.warning("%s: no candles, skipping walk-forward.", symbol)
        return result

    engine = BacktestEngine(config)
    history_start = candles.index[0].to_pydatetime()
    history_end = candles.index[-1].to_pydatetime()

    train_span = timedelta(days=train_days)
    test_span = timedelta(days=test_days)

    fold_index = 0
    train_start = history_start

    while True:
        train_end = train_start + train_span
        test_start = train_end
        test_end = test_start + test_span

        if test_end > history_end:
            break

        train_candles = _slice_with_warmup(candles, train_start, train_end, warmup_bars)
        test_candles = _slice_with_warmup(candles, test_start, test_end, warmup_bars)

        fold = Fold(
            index=fold_index,
            train_start=train_start,
            train_end=train_end,
            test_start=test_start,
            test_end=test_end,
        )

        if len(test_candles) < warmup_bars + 10:
            logger.debug("Fold %d: too few test bars, skipping.", fold_index)
        else:
            if search_space:
                chosen, train_result, score = grid_search(
                    symbol, train_candles, strategy_factory, base_params,
                    search_space, config, funding, objective,
                )
                # A training window that never cleared the trade minimum gives
                # no basis for choosing parameters, so the fold is discarded
                # rather than falling back to arbitrary defaults.
                if not np.isfinite(score):
                    logger.debug("Fold %d: no viable parameters in training.", fold_index)
                    fold.train_result = train_result
                    result.folds.append(fold)
                    fold_index += 1
                    train_start = train_start + test_span
                    continue
                fold.best_params = {k: getattr(chosen, k) for k in search_space}
                fold.train_result = train_result
            else:
                chosen = base_params
                fold.train_result = engine.run(
                    symbol, train_candles, strategy_factory(chosen), funding
                )

            fold.test_result = engine.run(
                symbol, test_candles, strategy_factory(chosen), funding
            )

        result.folds.append(fold)
        fold_index += 1
        train_start = train_start + test_span  # roll by one test window

    logger.info("%s", result)
    return result


def _slice_with_warmup(
    candles: pd.DataFrame, start: datetime, end: datetime, warmup_bars: int
) -> pd.DataFrame:
    """Slice [start, end] with `warmup_bars` of preceding history attached.

    The warm-up prefix is needed for indicators but must not be traded; the
    strategy's own `min_bars` suppression handles that.
    """
    start_index = candles.index.searchsorted(pd.Timestamp(start))
    end_index = candles.index.searchsorted(pd.Timestamp(end), side="right")
    return candles.iloc[max(0, start_index - warmup_bars) : end_index]
