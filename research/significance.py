"""
Statistical significance testing for trading results.

A 71% win rate over 20 trades and a coin flip are hard to tell apart, yet the
legacy project treated the former as proof. These tools answer the only question
that matters before risking money: **could this result plausibly have happened
by chance?**

Three complementary tests:

1. **Bootstrap confidence intervals.** Resample the observed trades with
   replacement to bound the true expectancy. If the 95% interval includes zero,
   there is no demonstrated edge.
2. **Monte Carlo path simulation.** Reshuffle trade order thousands of times.
   Trade sequence is arbitrary, but drawdown depends on it heavily, so this
   reveals the drawdown you should actually plan for rather than the one that
   happened to occur.
3. **Permutation test.** Compare the strategy's expectancy against random entries
   of identical count and holding period. This is the strictest test: it asks
   whether the *timing* carries information, or whether the results merely
   reflect the market's own drift.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Sequence

import numpy as np
import pandas as pd

from research.engine import Trade

logger = logging.getLogger(__name__)

DEFAULT_ITERATIONS = 10_000

#: Results with fewer trades than this cannot be meaningfully tested. This is
#: also the plan's go-live sample-size gate.
MIN_SAMPLE_FOR_INFERENCE = 30


@dataclass
class BootstrapResult:
    """Bootstrap confidence interval for mean per-trade return."""

    observed_mean: float
    ci_low: float
    ci_high: float
    p_value_positive: float
    iterations: int
    sample_size: int

    @property
    def is_significant(self) -> bool:
        """True when the 95% interval excludes zero and the edge is positive."""
        return self.ci_low > 0.0

    def summary(self) -> dict[str, object]:
        return {
            "observed_mean_pct": round(self.observed_mean, 4),
            "ci95_low_pct": round(self.ci_low, 4),
            "ci95_high_pct": round(self.ci_high, 4),
            "p_value_not_positive": round(self.p_value_positive, 4),
            "significant": self.is_significant,
            "sample_size": self.sample_size,
            "iterations": self.iterations,
        }


@dataclass
class MonteCarloResult:
    """Distribution of outcomes across reshuffled trade orderings."""

    median_return_pct: float
    p5_return_pct: float
    p95_return_pct: float
    median_max_drawdown_pct: float
    p95_max_drawdown_pct: float
    worst_max_drawdown_pct: float
    probability_of_loss: float
    probability_of_ruin: float
    iterations: int

    def summary(self) -> dict[str, object]:
        return {
            "median_return_pct": round(self.median_return_pct, 3),
            "p5_return_pct": round(self.p5_return_pct, 3),
            "p95_return_pct": round(self.p95_return_pct, 3),
            "median_max_drawdown_pct": round(self.median_max_drawdown_pct, 2),
            "p95_max_drawdown_pct": round(self.p95_max_drawdown_pct, 2),
            "worst_max_drawdown_pct": round(self.worst_max_drawdown_pct, 2),
            "probability_of_loss": round(self.probability_of_loss, 4),
            "probability_of_ruin": round(self.probability_of_ruin, 4),
            "iterations": self.iterations,
        }


@dataclass
class PermutationResult:
    """Strategy expectancy versus random entries of the same shape."""

    observed_expectancy_pct: float
    random_mean_pct: float
    random_std_pct: float
    percentile: float
    p_value: float
    iterations: int

    @property
    def beats_random(self) -> bool:
        """True when the strategy beats random entries at the 5% level."""
        return self.p_value < 0.05

    def summary(self) -> dict[str, object]:
        return {
            "observed_expectancy_pct": round(self.observed_expectancy_pct, 4),
            "random_mean_pct": round(self.random_mean_pct, 4),
            "random_std_pct": round(self.random_std_pct, 4),
            "percentile_vs_random": round(self.percentile, 2),
            "p_value": round(self.p_value, 4),
            "beats_random": self.beats_random,
            "iterations": self.iterations,
        }


@dataclass
class SignificanceReport:
    """All significance tests for one strategy result."""

    sample_size: int
    bootstrap: BootstrapResult | None = None
    monte_carlo: MonteCarloResult | None = None
    permutation: PermutationResult | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def verdict(self) -> str:
        """One-line conclusion combining every test that ran."""
        if self.sample_size < MIN_SAMPLE_FOR_INFERENCE:
            return (
                f"INSUFFICIENT DATA: {self.sample_size} trades, "
                f"need >= {MIN_SAMPLE_FOR_INFERENCE} for inference"
            )

        failures = []
        if self.bootstrap and not self.bootstrap.is_significant:
            failures.append("expectancy CI includes zero")
        if self.permutation and not self.permutation.beats_random:
            failures.append("does not beat random entries")

        if failures:
            return "NO DEMONSTRATED EDGE: " + "; ".join(failures)
        return "EDGE IS STATISTICALLY SUPPORTED"

    @property
    def passes(self) -> bool:
        """Whether every applicable test supports a real edge."""
        return self.verdict == "EDGE IS STATISTICALLY SUPPORTED"

    def summary(self) -> dict[str, object]:
        return {
            "sample_size": self.sample_size,
            "verdict": self.verdict,
            "passes": self.passes,
            "bootstrap": self.bootstrap.summary() if self.bootstrap else None,
            "monte_carlo": self.monte_carlo.summary() if self.monte_carlo else None,
            "permutation": self.permutation.summary() if self.permutation else None,
            "notes": self.notes,
        }


def bootstrap_expectancy(
    returns: Sequence[float],
    iterations: int = DEFAULT_ITERATIONS,
    confidence: float = 0.95,
    seed: int = 42,
) -> BootstrapResult:
    """Bootstrap a confidence interval for mean per-trade return.

    Args:
        returns: Per-trade returns in percent.
        iterations: Resamples to draw.
        confidence: Interval width, e.g. 0.95.
        seed: Fixed for reproducibility -- a significance test that changes
            answer between runs is not a test.
    """
    data = np.asarray(returns, dtype="float64")
    if data.size == 0:
        return BootstrapResult(0.0, 0.0, 0.0, 1.0, iterations, 0)

    rng = np.random.default_rng(seed)
    # Vectorised resampling: (iterations, n) index matrix in one draw.
    indices = rng.integers(0, data.size, size=(iterations, data.size))
    means = data[indices].mean(axis=1)

    tail = (1.0 - confidence) / 2.0
    ci_low, ci_high = np.quantile(means, [tail, 1.0 - tail])

    # Share of resamples that were not profitable: an empirical one-sided p.
    p_value = float((means <= 0).mean())

    return BootstrapResult(
        observed_mean=float(data.mean()),
        ci_low=float(ci_low),
        ci_high=float(ci_high),
        p_value_positive=p_value,
        iterations=iterations,
        sample_size=int(data.size),
    )


def monte_carlo_paths(
    returns: Sequence[float],
    position_fraction: float = 0.10,
    iterations: int = DEFAULT_ITERATIONS,
    ruin_threshold: float = 0.5,
    seed: int = 42,
) -> MonteCarloResult:
    """Simulate reshuffled trade orderings to bound drawdown risk.

    The set of trades is treated as fixed and only their order is randomised.
    Final return varies little under reshuffling, but maximum drawdown varies a
    great deal -- and drawdown is what ends accounts.

    Args:
        returns: Per-trade returns on notional, in percent.
        position_fraction: Fraction of equity per trade, converting a notional
            return into an account return.
        iterations: Paths to simulate.
        ruin_threshold: Equity fraction counted as ruin (0.5 = down 50%).
        seed: Fixed for reproducibility.
    """
    data = np.asarray(returns, dtype="float64") / 100.0 * position_fraction
    if data.size == 0:
        return MonteCarloResult(0, 0, 0, 0, 0, 0, 0, 0, iterations)

    rng = np.random.default_rng(seed)

    final_returns = np.empty(iterations)
    max_drawdowns = np.empty(iterations)
    ruined = 0

    for i in range(iterations):
        shuffled = rng.permutation(data)
        equity = np.cumprod(1.0 + shuffled)

        final_returns[i] = (equity[-1] - 1.0) * 100.0

        peak = np.maximum.accumulate(equity)
        max_drawdowns[i] = abs(((equity - peak) / peak).min()) * 100.0

        if equity.min() <= ruin_threshold:
            ruined += 1

    return MonteCarloResult(
        median_return_pct=float(np.median(final_returns)),
        p5_return_pct=float(np.quantile(final_returns, 0.05)),
        p95_return_pct=float(np.quantile(final_returns, 0.95)),
        median_max_drawdown_pct=float(np.median(max_drawdowns)),
        p95_max_drawdown_pct=float(np.quantile(max_drawdowns, 0.95)),
        worst_max_drawdown_pct=float(max_drawdowns.max()),
        probability_of_loss=float((final_returns < 0).mean()),
        probability_of_ruin=ruined / iterations,
        iterations=iterations,
    )


def permutation_test(
    candles: pd.DataFrame,
    observed_trades: Sequence[Trade],
    iterations: int = 2_000,
    seed: int = 42,
) -> PermutationResult:
    """Test whether entry *timing* carries information.

    Random entries are drawn matching the observed trade count and the observed
    distribution of holding periods, then scored with the same simple
    close-to-close return. If the strategy's expectancy sits inside the random
    distribution, its results are explained by market drift rather than skill.

    This deliberately ignores take-profit and stop-loss mechanics on both sides,
    so the comparison isolates timing.
    """
    trades = list(observed_trades)
    if not trades or candles.empty:
        return PermutationResult(0.0, 0.0, 0.0, 0.0, 1.0, iterations)

    closes = candles["close"].to_numpy(dtype="float64")
    n_bars = closes.size

    holding_periods = np.array([max(t.bars_held, 1) for t in trades])
    signs = np.array([t.side.sign for t in trades], dtype="float64")
    n_trades = len(trades)

    if n_bars <= holding_periods.max() + 2:
        return PermutationResult(0.0, 0.0, 0.0, 0.0, 1.0, iterations)

    observed = float(np.mean([t.return_pct for t in trades]))

    rng = np.random.default_rng(seed)
    random_expectancies = np.empty(iterations)

    for i in range(iterations):
        entries = rng.integers(0, n_bars - holding_periods.max() - 1, size=n_trades)
        exits = entries + holding_periods

        entry_prices = closes[entries]
        exit_prices = closes[exits]

        # Same directional mix as the observed trades, so a long-only strategy
        # is compared against random longs rather than a mix.
        returns = signs * (exit_prices - entry_prices) / entry_prices * 100.0
        random_expectancies[i] = returns.mean()

    percentile = float((random_expectancies < observed).mean() * 100.0)
    # One-sided p: how often random matched or beat the strategy.
    p_value = float((random_expectancies >= observed).mean())

    return PermutationResult(
        observed_expectancy_pct=observed,
        random_mean_pct=float(random_expectancies.mean()),
        random_std_pct=float(random_expectancies.std(ddof=1)),
        percentile=percentile,
        p_value=p_value,
        iterations=iterations,
    )


def assess(
    trades: Sequence[Trade],
    candles: pd.DataFrame | None = None,
    position_fraction: float = 0.10,
    iterations: int = DEFAULT_ITERATIONS,
) -> SignificanceReport:
    """Run every applicable significance test and return a combined verdict."""
    trade_list = list(trades)
    report = SignificanceReport(sample_size=len(trade_list))

    if not trade_list:
        report.notes.append("No trades to assess.")
        return report

    returns = [t.return_pct for t in trade_list]

    report.bootstrap = bootstrap_expectancy(returns, iterations=iterations)
    report.monte_carlo = monte_carlo_paths(
        returns, position_fraction=position_fraction, iterations=min(iterations, 5_000)
    )

    if candles is not None and not candles.empty:
        report.permutation = permutation_test(candles, trade_list)
    else:
        report.notes.append("Permutation test skipped: no candle data supplied.")

    if len(trade_list) < MIN_SAMPLE_FOR_INFERENCE:
        report.notes.append(
            f"Sample of {len(trade_list)} trades is below the {MIN_SAMPLE_FOR_INFERENCE} "
            "needed for inference; treat all figures as indicative only."
        )

    return report
