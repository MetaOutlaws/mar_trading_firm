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


# ---------------------------------------------------------------------------
# Donchian — next coded family after rejected rsi_trend
# ---------------------------------------------------------------------------
def test_donchian_is_registered() -> None:
    from core.strategy.registry import list_strategies

    assert "rsi_trend" in list_strategies()
    assert "donchian_breakout" in list_strategies()


def test_donchian_long_fires_on_prior_channel_break() -> None:
    """A close through the prior N-bar high must fire a LONG when ADX is off."""
    from core.strategy.donchian_breakout import DonchianBreakoutStrategy, DonchianParams

    n = 80
    close = np.full(n, 100.0)
    close[-1] = 120.0
    high = np.full(n, 101.0)
    high[-1] = 121.0
    low = np.full(n, 99.0)
    low[-1] = 119.0
    index = pd.date_range("2023-01-01", periods=n, freq="15min", tz="UTC")
    frame = pd.DataFrame(
        {
            "open": close,
            "high": high,
            "low": low,
            "close": close,
            "volume": np.full(n, 1_000.0),
        },
        index=index,
    )
    frame.index.name = "timestamp"
    strategy = DonchianBreakoutStrategy(
        DonchianParams(side=SignalSide.LONG, lookback=20, min_adx=0.0)
    )
    signals = strategy.generate_signals(frame)
    assert int(signals["signal"].iloc[-1]) == 1
    assert signals["side"].iloc[-1] == SignalSide.LONG.value
    # Warm-up must stay flat even on a synthetic breakout series.
    assert (signals["signal"].iloc[: strategy.min_bars] == 0).all()


def test_donchian_live_path_matches_backtest(candles) -> None:
    from core.strategy.donchian_breakout import DonchianBreakoutStrategy, DonchianParams

    strategy = DonchianBreakoutStrategy(DonchianParams(min_adx=0.0))
    signals = strategy.generate_signals(candles)
    last = signals.iloc[-1]
    live = strategy.latest_signal("BTCUSDT", candles)
    if int(last["signal"]) == 0:
        assert live is None
    else:
        assert live is not None
        assert live.side.value == last["side"]
        assert live.strategy == "donchian_breakout"


def test_donchian_future_shock_does_not_change_past(candles) -> None:
    from core.strategy.donchian_breakout import DonchianBreakoutStrategy, DonchianParams

    strategy = DonchianBreakoutStrategy(DonchianParams(min_adx=0.0))
    shocked = candles.copy()
    shocked.iloc[-1, shocked.columns.get_loc("close")] *= 1.5
    shocked.iloc[-1, shocked.columns.get_loc("high")] *= 1.6
    original = strategy.generate_signals(candles)["signal"].iloc[:-1]
    after = strategy.generate_signals(shocked)["signal"].iloc[:-1]
    pd.testing.assert_series_equal(original, after)


def test_ema_adx_is_registered() -> None:
    from core.strategy.registry import list_strategies

    assert "ema_adx_trend" in list_strategies()


def test_ema_adx_long_fires_on_pullback_to_fast_ema() -> None:
    """In an uptrend, tagging the fast EMA and closing back above must fire LONG."""
    from core.strategy.ema_adx_trend import EmaAdxParams, EmaAdxTrendStrategy

    n = 120
    close = np.linspace(100.0, 140.0, n)
    high = close + 0.4
    low = close - 0.4
    # Last bar dips through the fast EMA then closes back on the trend.
    low[-1] = close[-1] - 8.0
    high[-1] = close[-1] + 0.2
    index = pd.date_range("2023-01-01", periods=n, freq="4h", tz="UTC")
    frame = pd.DataFrame(
        {
            "open": np.concatenate([[close[0]], close[:-1]]),
            "high": high,
            "low": low,
            "close": close,
            "volume": np.full(n, 1_000.0),
        },
        index=index,
    )
    frame.index.name = "timestamp"
    strategy = EmaAdxTrendStrategy(
        EmaAdxParams(side=SignalSide.LONG, ema_fast=20, ema_slow=50, min_adx=0.0)
    )
    signals = strategy.generate_signals(frame)
    assert int(signals["signal"].iloc[-1]) == 1
    assert signals["side"].iloc[-1] == SignalSide.LONG.value
    assert (signals["signal"].iloc[: strategy.min_bars] == 0).all()


def test_ema_adx_live_path_matches_backtest(candles) -> None:
    from core.strategy.ema_adx_trend import EmaAdxParams, EmaAdxTrendStrategy

    strategy = EmaAdxTrendStrategy(EmaAdxParams(min_adx=0.0))
    signals = strategy.generate_signals(candles)
    last = signals.iloc[-1]
    live = strategy.latest_signal("BTCUSDT", candles)
    if int(last["signal"]) == 0:
        assert live is None
    else:
        assert live is not None
        assert live.side.value == last["side"]
        assert live.strategy == "ema_adx_trend"


def test_ema_adx_future_shock_does_not_change_past(candles) -> None:
    from core.strategy.ema_adx_trend import EmaAdxParams, EmaAdxTrendStrategy

    strategy = EmaAdxTrendStrategy(EmaAdxParams(min_adx=0.0))
    shocked = candles.copy()
    shocked.iloc[-1, shocked.columns.get_loc("close")] *= 1.5
    shocked.iloc[-1, shocked.columns.get_loc("high")] *= 1.6
    original = strategy.generate_signals(candles)["signal"].iloc[:-1]
    after = strategy.generate_signals(shocked)["signal"].iloc[:-1]
    pd.testing.assert_series_equal(original, after)


def test_bollinger_is_registered() -> None:
    from core.strategy.registry import list_strategies

    assert "bollinger_mean_reversion" in list_strategies()


def _chop_then_stretch(n: int = 80, last_close: float = 85.0) -> pd.DataFrame:
    """Quiet series around 100, then a last-bar stretch used to fire a fade."""
    close = 100.0 + 0.25 * np.sin(np.linspace(0, 6 * np.pi, n))
    close[-1] = last_close
    high = close + 0.2
    low = close - 0.2
    if last_close < 100:
        low[-1] = last_close - 0.4
    else:
        high[-1] = last_close + 0.4
    index = pd.date_range("2023-01-01", periods=n, freq="4h", tz="UTC")
    frame = pd.DataFrame(
        {
            "open": np.concatenate([[close[0]], close[:-1]]),
            "high": high,
            "low": low,
            "close": close,
            "volume": np.full(n, 1_000.0),
        },
        index=index,
    )
    frame.index.name = "timestamp"
    return frame


def test_bollinger_long_fires_on_lower_band_stretch() -> None:
    from core.strategy.bollinger_mean_reversion import (
        BollingerMeanReversionStrategy,
        BollingerMrParams,
    )

    frame = _chop_then_stretch(last_close=85.0)
    strategy = BollingerMeanReversionStrategy(
        BollingerMrParams(side=SignalSide.LONG, bb_period=20, band_k=2.0, max_adx=0.0)
    )
    signals = strategy.generate_signals(frame)
    assert int(signals["signal"].iloc[-1]) == 1
    assert signals["side"].iloc[-1] == SignalSide.LONG.value
    assert (signals["signal"].iloc[: strategy.min_bars] == 0).all()


def test_bollinger_short_fires_on_upper_band_stretch() -> None:
    from core.strategy.bollinger_mean_reversion import (
        BollingerMeanReversionStrategy,
        BollingerMrParams,
    )

    frame = _chop_then_stretch(last_close=115.0)
    strategy = BollingerMeanReversionStrategy(
        BollingerMrParams(side=SignalSide.SHORT, bb_period=20, band_k=2.0, max_adx=0.0)
    )
    signals = strategy.generate_signals(frame)
    assert int(signals["signal"].iloc[-1]) == -1
    assert signals["side"].iloc[-1] == SignalSide.SHORT.value


def test_bollinger_live_path_matches_backtest(candles) -> None:
    from core.strategy.bollinger_mean_reversion import (
        BollingerMeanReversionStrategy,
        BollingerMrParams,
    )

    strategy = BollingerMeanReversionStrategy(BollingerMrParams(max_adx=0.0))
    signals = strategy.generate_signals(candles)
    last = signals.iloc[-1]
    live = strategy.latest_signal("BTCUSDT", candles)
    if int(last["signal"]) == 0:
        assert live is None
    else:
        assert live is not None
        assert live.side.value == last["side"]
        assert live.strategy == "bollinger_mean_reversion"


def test_bollinger_future_shock_does_not_change_past(candles) -> None:
    from core.strategy.bollinger_mean_reversion import (
        BollingerMeanReversionStrategy,
        BollingerMrParams,
    )

    strategy = BollingerMeanReversionStrategy(BollingerMrParams(max_adx=0.0))
    shocked = candles.copy()
    shocked.iloc[-1, shocked.columns.get_loc("close")] *= 0.7
    shocked.iloc[-1, shocked.columns.get_loc("low")] *= 0.65
    original = strategy.generate_signals(candles)["signal"].iloc[:-1]
    after = strategy.generate_signals(shocked)["signal"].iloc[:-1]
    pd.testing.assert_series_equal(original, after)


def test_trend_pullback_htf_is_registered() -> None:
    from core.strategy.registry import list_strategies

    assert "trend_pullback_htf" in list_strategies()


def _htf_uptrend(n: int = 400, last_dip: float = 12.0) -> pd.DataFrame:
    close = np.linspace(100.0, 180.0, n)
    high = close + 0.5
    low = close - 0.5
    low[-1] = close[-1] - last_dip
    high[-1] = close[-1] + 0.3
    index = pd.date_range("2023-01-01", periods=n, freq="h", tz="UTC")
    frame = pd.DataFrame(
        {
            "open": np.concatenate([[close[0]], close[:-1]]),
            "high": high,
            "low": low,
            "close": close,
            "volume": np.full(n, 1_000.0),
        },
        index=index,
    )
    frame.index.name = "timestamp"
    return frame


def test_trend_pullback_htf_long_fires_on_1h_tag_in_4h_uptrend() -> None:
    from core.strategy.trend_pullback_htf import (
        TrendPullbackHtfParams,
        TrendPullbackHtfStrategy,
    )

    frame = _htf_uptrend()
    strategy = TrendPullbackHtfStrategy(
        TrendPullbackHtfParams(side=SignalSide.LONG, min_adx=0.0)
    )
    signals = strategy.generate_signals(frame)
    assert int(signals["signal"].iloc[-1]) == 1
    assert signals["side"].iloc[-1] == SignalSide.LONG.value
    assert (signals["signal"].iloc[: strategy.min_bars] == 0).all()


def test_trend_pullback_htf_future_shock_does_not_change_past() -> None:
    from core.strategy.trend_pullback_htf import (
        TrendPullbackHtfParams,
        TrendPullbackHtfStrategy,
    )

    frame = _htf_uptrend()
    strategy = TrendPullbackHtfStrategy(TrendPullbackHtfParams(min_adx=0.0))
    shocked = frame.copy()
    shocked.iloc[-1, shocked.columns.get_loc("close")] *= 1.2
    shocked.iloc[-1, shocked.columns.get_loc("high")] *= 1.25
    original = strategy.generate_signals(frame)["signal"].iloc[:-1]
    after = strategy.generate_signals(shocked)["signal"].iloc[:-1]
    pd.testing.assert_series_equal(original, after)


def test_atr_channel_is_registered() -> None:
    from core.strategy.registry import list_strategies

    assert "atr_channel_breakout" in list_strategies()


def test_atr_channel_long_fires_on_prior_band_break() -> None:
    """A close through the prior EMA + k·ATR must fire LONG when ADX is off."""
    from core.strategy.atr_channel_breakout import (
        AtrChannelBreakoutStrategy,
        AtrChannelParams,
    )

    n = 80
    close = np.full(n, 100.0)
    close[-1] = 120.0
    high = np.full(n, 101.0)
    high[-1] = 121.0
    low = np.full(n, 99.0)
    low[-1] = 119.0
    index = pd.date_range("2023-01-01", periods=n, freq="4h", tz="UTC")
    frame = pd.DataFrame(
        {
            "open": close,
            "high": high,
            "low": low,
            "close": close,
            "volume": np.full(n, 1_000.0),
        },
        index=index,
    )
    frame.index.name = "timestamp"
    strategy = AtrChannelBreakoutStrategy(
        AtrChannelParams(side=SignalSide.LONG, min_adx=0.0)
    )
    signals = strategy.generate_signals(frame)
    assert int(signals["signal"].iloc[-1]) == 1
    assert signals["side"].iloc[-1] == SignalSide.LONG.value
    assert (signals["signal"].iloc[: strategy.min_bars] == 0).all()


def test_atr_channel_live_path_matches_backtest(candles) -> None:
    from core.strategy.atr_channel_breakout import (
        AtrChannelBreakoutStrategy,
        AtrChannelParams,
    )

    strategy = AtrChannelBreakoutStrategy(AtrChannelParams(min_adx=0.0))
    signals = strategy.generate_signals(candles)
    last = signals.iloc[-1]
    live = strategy.latest_signal("BTCUSDT", candles)
    if int(last["signal"]) == 0:
        assert live is None
    else:
        assert live is not None
        assert live.side.value == last["side"]
        assert live.strategy == "atr_channel_breakout"


def test_atr_channel_future_shock_does_not_change_past(candles) -> None:
    from core.strategy.atr_channel_breakout import (
        AtrChannelBreakoutStrategy,
        AtrChannelParams,
    )

    strategy = AtrChannelBreakoutStrategy(AtrChannelParams(min_adx=0.0))
    shocked = candles.copy()
    shocked.iloc[-1, shocked.columns.get_loc("close")] *= 1.5
    shocked.iloc[-1, shocked.columns.get_loc("high")] *= 1.6
    original = strategy.generate_signals(candles)["signal"].iloc[:-1]
    after = strategy.generate_signals(shocked)["signal"].iloc[:-1]
    pd.testing.assert_series_equal(original, after)
