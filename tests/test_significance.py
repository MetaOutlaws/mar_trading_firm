"""
Significance testing tests.

Validated against synthetic data where the right answer is known in advance: a
pure coin flip must be reported as no edge, and a strong planted edge must be
detected. A significance test that cannot tell these apart is worse than none,
because it manufactures false confidence.
"""

from __future__ import annotations

import numpy as np
import pytest

from research.significance import (
    MIN_SAMPLE_FOR_INFERENCE,
    assess,
    bootstrap_expectancy,
    monte_carlo_paths,
)


# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------
def test_bootstrap_finds_no_edge_in_a_fair_coin_flip():
    """Symmetric random returns must produce a CI spanning zero."""
    rng = np.random.default_rng(1)
    returns = rng.normal(0.0, 2.0, 200)
    result = bootstrap_expectancy(returns, iterations=2000)

    assert result.ci_low < 0 < result.ci_high
    assert not result.is_significant


def test_bootstrap_detects_a_strong_planted_edge():
    """A clear positive mean with low variance must be flagged significant."""
    rng = np.random.default_rng(2)
    returns = rng.normal(1.5, 1.0, 200)
    result = bootstrap_expectancy(returns, iterations=2000)

    assert result.ci_low > 0
    assert result.is_significant
    assert result.observed_mean == pytest.approx(1.5, abs=0.3)


def test_bootstrap_is_reproducible():
    """Fixed seed means a fixed answer; otherwise the test proves nothing."""
    returns = [1.0, -2.0, 3.0, -1.0, 0.5] * 20
    first = bootstrap_expectancy(returns, iterations=1000)
    second = bootstrap_expectancy(returns, iterations=1000)
    assert first.ci_low == second.ci_low
    assert first.ci_high == second.ci_high


def test_bootstrap_widens_interval_on_small_samples():
    """Less data must mean more uncertainty, not a luckier verdict."""
    rng = np.random.default_rng(3)
    population = rng.normal(0.5, 2.0, 500)

    small = bootstrap_expectancy(population[:20], iterations=2000)
    large = bootstrap_expectancy(population, iterations=2000)

    assert (small.ci_high - small.ci_low) > (large.ci_high - large.ci_low)


def test_bootstrap_handles_empty_input():
    result = bootstrap_expectancy([], iterations=100)
    assert result.sample_size == 0
    assert not result.is_significant


# ---------------------------------------------------------------------------
# Monte Carlo
# ---------------------------------------------------------------------------
def test_monte_carlo_drawdown_exceeds_the_realised_path():
    """Reshuffling must surface worse orderings than the one that occurred.

    This is the practical value of the test: the drawdown you must budget for is
    not the one history happened to hand you.
    """
    rng = np.random.default_rng(4)
    returns = rng.normal(0.3, 3.0, 150)
    result = monte_carlo_paths(returns, position_fraction=0.10, iterations=2000)

    assert result.worst_max_drawdown_pct >= result.median_max_drawdown_pct
    assert result.p95_max_drawdown_pct >= result.median_max_drawdown_pct
    assert result.median_max_drawdown_pct > 0


def test_monte_carlo_flags_ruin_risk_on_oversized_positions():
    """Large position sizing on a losing edge must show real ruin probability."""
    rng = np.random.default_rng(5)
    losing = rng.normal(-2.0, 5.0, 200)
    result = monte_carlo_paths(losing, position_fraction=1.0, iterations=1000)

    assert result.probability_of_loss > 0.9
    assert result.probability_of_ruin > 0.0


def test_monte_carlo_smaller_size_reduces_ruin():
    """Position sizing is the main lever on survival; the model must reflect it."""
    rng = np.random.default_rng(6)
    returns = rng.normal(-1.0, 6.0, 200)

    big = monte_carlo_paths(returns, position_fraction=1.0, iterations=1000)
    small = monte_carlo_paths(returns, position_fraction=0.05, iterations=1000)

    assert small.probability_of_ruin <= big.probability_of_ruin
    assert small.median_max_drawdown_pct < big.median_max_drawdown_pct


# ---------------------------------------------------------------------------
# Combined verdict
# ---------------------------------------------------------------------------
def _fake_trades(returns: list[float]):
    """Build minimal Trade objects carrying only what the tests need."""
    from datetime import datetime, timedelta, timezone

    from core.strategy.base import SignalSide
    from research.engine import ExitReason, Trade

    base = datetime(2024, 1, 1, tzinfo=timezone.utc)
    trades = []
    equity = 10_000.0
    for i, ret in enumerate(returns):
        pnl = 1000.0 * ret / 100.0
        equity += pnl
        trades.append(
            Trade(
                symbol="TEST",
                side=SignalSide.LONG,
                entry_time=base + timedelta(hours=i * 4),
                entry_price=100.0,
                exit_time=base + timedelta(hours=i * 4 + 2),
                exit_price=100.0 * (1 + ret / 100.0),
                quantity=10.0,
                notional=1000.0,
                gross_pnl=pnl,
                fees=0.0,
                funding=0.0,
                net_pnl=pnl,
                return_pct=ret,
                exit_reason=ExitReason.TAKE_PROFIT if ret > 0 else ExitReason.STOP_LOSS,
                bars_held=8,
                entry_score=1.0,
                entry_reason="test",
                equity_after=equity,
            )
        )
    return trades


def test_verdict_rejects_a_small_sample_however_good_it_looks():
    """The legacy failure mode: 20 trades at a 90% win rate is not evidence."""
    returns = [5.0] * 18 + [-5.0] * 2  # 90% win rate, 20 trades
    report = assess(_fake_trades(returns), iterations=1000)

    assert report.sample_size < MIN_SAMPLE_FOR_INFERENCE
    assert not report.passes
    assert "INSUFFICIENT DATA" in report.verdict


def test_verdict_rejects_a_large_but_edgeless_sample():
    rng = np.random.default_rng(7)
    returns = list(rng.normal(0.0, 3.0, 200))
    report = assess(_fake_trades(returns), iterations=1000)

    assert not report.passes
    assert "NO DEMONSTRATED EDGE" in report.verdict


def test_verdict_accepts_a_large_sample_with_a_real_edge():
    """With no candles supplied the permutation test is skipped, and the
    bootstrap alone should confirm a strong planted edge."""
    rng = np.random.default_rng(8)
    returns = list(rng.normal(1.2, 1.5, 300))
    report = assess(_fake_trades(returns), iterations=1000)

    assert report.bootstrap is not None
    assert report.bootstrap.is_significant
    assert report.passes


def test_report_is_serialisable():
    import json

    report = assess(_fake_trades([1.0, -1.0, 2.0] * 20), iterations=500)
    payload = json.dumps(report.summary())
    assert "verdict" in payload
