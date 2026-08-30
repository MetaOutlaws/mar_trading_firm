"""
Strategy contract tests.

The most important test in this file is `test_live_path_matches_backtest_path`.
The predecessor project maintained separate live and backtest signal
implementations that disagreed by ~30 percentage points of win rate, with no way
to tell which was correct. These tests assert that such a divergence is
impossible here.

The second most important is `test_no_lookahead_*`: a signal must never change
because of data that arrived after it.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core.strategy.base import SignalSide
from core.strategy.rsi_golden_cross import RsiTrendParams, RsiTrendStrategy


def make_candles(n: int = 800, seed: int = 42, drift: float = 0.0002) -> pd.DataFrame:
    """Synthesise a plausible OHLCV history with an upward drift.

    Drift is deliberate: the LONG strategy requires a golden cross, so a
    driftless random walk would produce almost no signals and the tests would
    pass vacuously.
    """
    rng = np.random.default_rng(seed)
    returns = rng.normal(drift, 0.012, n)
    close = 100.0 * np.exp(np.cumsum(returns))

    index = pd.date_range("2023-01-01", periods=n, freq="15min", tz="UTC")
    spread = np.abs(rng.normal(0, 0.004, n)) * close

    frame = pd.DataFrame(
        {
            "open": np.concatenate([[close[0]], close[:-1]]),
            "high": close + spread,
            "low": close - spread,
            "close": close,
            "volume": np.abs(rng.lognormal(6.0, 0.6, n)),
            "turnover": np.abs(rng.lognormal(12.0, 0.6, n)),
        },
        index=index,
    )
    frame.index.name = "timestamp"
    return frame


@pytest.fixture
def candles() -> pd.DataFrame:
    return make_candles()


@pytest.fixture
def long_strategy() -> RsiTrendStrategy:
    # A wide RSI band and low volume bar so the synthetic data actually fires.
    return RsiTrendStrategy(
        RsiTrendParams(side=SignalSide.LONG, rsi_min=25, rsi_max=50, volume_threshold=1.0)
    )


@pytest.fixture
def short_strategy() -> RsiTrendStrategy:
    return RsiTrendStrategy(
        RsiTrendParams(side=SignalSide.SHORT, rsi_threshold=60, volume_threshold=1.0)
    )


# ---------------------------------------------------------------------------
# Schema contract
# ---------------------------------------------------------------------------
def test_signals_are_indexed_like_the_input(long_strategy, candles):
    signals = long_strategy.generate_signals(candles)
    pd.testing.assert_index_equal(signals.index, candles.index)


def test_signals_have_required_columns(long_strategy, candles):
    signals = long_strategy.generate_signals(candles)
    for column in ("signal", "side", "score", "reason"):
        assert column in signals.columns


def test_signal_values_are_valid(long_strategy, candles):
    signals = long_strategy.generate_signals(candles)
    assert set(signals["signal"].unique()) <= {0, 1, -1}
    assert set(signals["side"].unique()) <= {s.value for s in SignalSide}


def test_malformed_candles_are_rejected(long_strategy, candles):
    with pytest.raises(ValueError, match="missing columns"):
        long_strategy.generate_signals(candles.drop(columns=["volume"]))

    with pytest.raises(ValueError, match="sorted ascending"):
        long_strategy.generate_signals(candles.iloc[::-1])


def test_insufficient_history_yields_no_signals(long_strategy):
    signals = long_strategy.generate_signals(make_candles(n=50))
    assert (signals["signal"] == 0).all()


def test_warmup_window_never_signals(long_strategy, candles):
    """Partially seeded indicators must not generate trades."""
    signals = long_strategy.generate_signals(candles)
    warmup = signals.iloc[: long_strategy.min_bars]
    assert (warmup["signal"] == 0).all()


# ---------------------------------------------------------------------------
# The core guarantee: one implementation for live and backtest
# ---------------------------------------------------------------------------
def test_live_path_matches_backtest_path(long_strategy, candles):
    """`latest_signal` must agree with the last row of `generate_signals`.

    This is the structural reason live trading cannot drift away from the
    backtest: both read the same computation.
    """
    signals = long_strategy.generate_signals(candles)
    last = signals.iloc[-1]
    live = long_strategy.latest_signal("BTCUSDT", candles)

    if int(last["signal"]) == 0:
        assert live is None
    else:
        assert live is not None
        assert live.side.value == last["side"]
        assert live.score == pytest.approx(float(last["score"]))
        assert live.reason == last["reason"]
        assert live.price == pytest.approx(float(candles["close"].iloc[-1]))
        assert live.timestamp == candles.index[-1]


def test_live_path_matches_backtest_at_every_bar(long_strategy, candles):
    """Walk the history bar by bar; live and backtest must agree at each step.

    This is the strong form of the guarantee. For a sample of cut points, the
    live call on data up to bar `t` must match the backtest's row `t`. Any
    lookahead or state leakage would show up here.
    """
    signals = long_strategy.generate_signals(candles)

    # Sample rather than test all 800 bars: each check recomputes the history.
    cut_points = range(long_strategy.min_bars + 10, len(candles), 37)

    for cut in cut_points:
        window = candles.iloc[: cut + 1]
        live = long_strategy.latest_signal("BTCUSDT", window)
        expected = signals.iloc[cut]

        if int(expected["signal"]) == 0:
            assert live is None, f"bar {cut}: live fired but backtest did not"
        else:
            assert live is not None, f"bar {cut}: backtest fired but live did not"
            assert live.side.value == expected["side"], f"bar {cut}: side mismatch"


# ---------------------------------------------------------------------------
# No lookahead
# ---------------------------------------------------------------------------
def test_no_lookahead_truncation_invariance(long_strategy, candles):
    """Signals for bars 0..t must not change when later bars are removed.

    Indicators here are all trailing, so truncating the future is a no-op for
    the past. If any calculation peeked forward, the two runs would differ.
    """
    full = long_strategy.generate_signals(candles)
    cut = 600
    truncated = long_strategy.generate_signals(candles.iloc[:cut])

    pd.testing.assert_series_equal(
        full["signal"].iloc[:cut],
        truncated["signal"],
        check_names=False,
    )


def test_no_lookahead_future_shock_does_not_change_past(long_strategy, candles):
    """A violent move at the end must not alter any earlier signal."""
    shocked = candles.copy()
    shocked.iloc[-1, shocked.columns.get_loc("close")] *= 1.5
    shocked.iloc[-1, shocked.columns.get_loc("high")] *= 1.6
    shocked.iloc[-1, shocked.columns.get_loc("volume")] *= 20

    original = long_strategy.generate_signals(candles)["signal"].iloc[:-1]
    after = long_strategy.generate_signals(shocked)["signal"].iloc[:-1]

    pd.testing.assert_series_equal(original, after)


# ---------------------------------------------------------------------------
# Entry logic
# ---------------------------------------------------------------------------
def test_long_entries_satisfy_every_stated_condition(long_strategy, candles):
    """Each LONG signal must independently satisfy all four documented rules."""
    signals = long_strategy.generate_signals(candles)
    fired = signals[signals["signal"] == 1]

    if fired.empty:
        pytest.skip("no LONG signals in this synthetic sample")

    params = long_strategy.params
    assert (fired["rsi"] >= params.rsi_min).all(), "RSI below band"
    assert (fired["rsi"] <= params.rsi_max).all(), "RSI above band"
    assert (fired["rsi_change"] > 0).all(), "RSI not rising"
    assert (fired["ema_fast"] > fired["ema_slow"]).all(), "no golden cross"
    assert (fired["volume_ratio"] > params.volume_threshold).all(), "volume too low"


def test_short_entries_satisfy_every_stated_condition(short_strategy, candles):
    """Each SHORT signal must independently satisfy all four documented rules."""
    signals = short_strategy.generate_signals(candles)
    fired = signals[signals["signal"] == -1]

    if fired.empty:
        pytest.skip("no SHORT signals in this synthetic sample")

    params = short_strategy.params
    assert (fired["rsi"] >= params.rsi_threshold).all(), "RSI not overbought"
    assert (fired["rsi_change"] < 0).all(), "RSI not falling"
    assert (
        candles.loc[fired.index, "close"] > fired["ema_slow"]
    ).all(), "price not above EMA200"
    assert (fired["volume_ratio"] > params.volume_threshold).all(), "volume too low"


def test_long_and_short_are_separate_instances(candles):
    """One strategy object trades one side, so results are never commingled."""
    long_signals = RsiTrendStrategy(
        RsiTrendParams(side=SignalSide.LONG, rsi_min=25, rsi_max=50, volume_threshold=1.0)
    ).generate_signals(candles)
    short_signals = RsiTrendStrategy(
        RsiTrendParams(side=SignalSide.SHORT, rsi_threshold=60, volume_threshold=1.0)
    ).generate_signals(candles)

    assert (long_signals["signal"] >= 0).all()
    assert (short_signals["signal"] <= 0).all()


def test_tighter_filters_never_produce_more_signals(candles):
    """Monotonicity check: raising the volume bar cannot add signals."""
    loose = RsiTrendStrategy(
        RsiTrendParams(side=SignalSide.LONG, rsi_min=25, rsi_max=50, volume_threshold=1.0)
    ).generate_signals(candles)
    strict = RsiTrendStrategy(
        RsiTrendParams(side=SignalSide.LONG, rsi_min=25, rsi_max=50, volume_threshold=2.5)
    ).generate_signals(candles)

    assert (strict["signal"] != 0).sum() <= (loose["signal"] != 0).sum()


def test_scores_are_bounded_and_finite(long_strategy, candles):
    signals = long_strategy.generate_signals(candles)
    scores = signals["score"]
    assert np.isfinite(scores).all()
    assert (scores >= 0).all()
    assert (scores <= 3.0001).all()


def test_fired_signals_carry_a_reason(long_strategy, candles):
    """Every trade must be explainable, for the dashboard and for audits."""
    signals = long_strategy.generate_signals(candles)
    fired = signals[signals["signal"] != 0]
    if fired.empty:
        pytest.skip("no signals in this synthetic sample")
    assert (fired["reason"].str.len() > 0).all()
