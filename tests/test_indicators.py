"""
Indicator correctness tests.

These pin behaviour against hand-computable cases and known reference values.
Their purpose is regression protection: if someone "optimises" an indicator and
silently changes its output, every backtest ever recorded becomes incomparable.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core.strategy import indicators as ind


def series(values: list[float]) -> pd.Series:
    """Build a Series on a UTC 15-minute index, matching production candles."""
    index = pd.date_range("2024-01-01", periods=len(values), freq="15min", tz="UTC")
    return pd.Series(values, index=index, dtype="float64")


# ---------------------------------------------------------------------------
# EMA / SMA
# ---------------------------------------------------------------------------
def test_ema_of_constant_is_the_constant():
    """An EMA of a flat series equals that value at every point."""
    result = ind.ema(series([10.0] * 50), 10)
    assert np.allclose(result.values, 10.0)


def test_ema_first_value_seeds_with_first_observation():
    """With adjust=False, the EMA starts at the first observation."""
    result = ind.ema(series([5.0, 10.0, 15.0]), 3)
    assert result.iloc[0] == pytest.approx(5.0)
    # alpha = 2/(3+1) = 0.5, so the second point is midway.
    assert result.iloc[1] == pytest.approx(7.5)
    assert result.iloc[2] == pytest.approx(11.25)


def test_sma_requires_full_window():
    result = ind.sma(series([1.0, 2.0, 3.0, 4.0]), 3)
    assert pd.isna(result.iloc[0]) and pd.isna(result.iloc[1])
    assert result.iloc[2] == pytest.approx(2.0)
    assert result.iloc[3] == pytest.approx(3.0)


def test_ema_rejects_nonpositive_period():
    with pytest.raises(ValueError):
        ind.ema(series([1.0, 2.0]), 0)


# ---------------------------------------------------------------------------
# RSI
# ---------------------------------------------------------------------------
def test_rsi_all_gains_is_100():
    """An unbroken advance has zero average loss, so RSI pins at 100."""
    rising = series([float(i) for i in range(1, 60)])
    result = ind.rsi(rising, 14)
    assert result.iloc[-1] == pytest.approx(100.0)


def test_rsi_all_losses_is_zero():
    """An unbroken decline drives RSI to 0."""
    falling = series([float(i) for i in range(100, 40, -1)])
    result = ind.rsi(falling, 14)
    assert result.iloc[-1] == pytest.approx(0.0, abs=1e-9)


def test_rsi_of_flat_series_is_neutral():
    """No movement means no information; the guarded branch returns 50."""
    result = ind.rsi(series([42.0] * 60), 14)
    assert result.iloc[-1] == pytest.approx(50.0)


def test_rsi_stays_in_bounds_on_random_walk():
    rng = np.random.default_rng(7)
    walk = series(list(100 + np.cumsum(rng.normal(0, 1, 500))))
    result = ind.rsi(walk, 14).dropna()
    assert result.min() >= 0.0
    assert result.max() <= 100.0


def test_rsi_matches_wilder_reference():
    """Reference case from Wilder's original worked example.

    Using the classic 14-period sequence, RSI at the first computed bar is
    ~70.53. This is the canonical check that seeding is correct: an unseeded
    EWM gives a visibly different number here.
    """
    closes = [
        44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.42,
        45.84, 46.08, 45.89, 46.03, 45.61, 46.28, 46.28,
    ]
    result = ind.rsi(series(closes), 14)
    assert result.iloc[14] == pytest.approx(70.53, abs=0.15)


def test_rsi_is_deterministic():
    """Same input, same output. Non-determinism would invalidate every backtest."""
    rng = np.random.default_rng(3)
    walk = series(list(100 + np.cumsum(rng.normal(0, 1, 300))))
    first = ind.rsi(walk, 14)
    second = ind.rsi(walk, 14)
    pd.testing.assert_series_equal(first, second)


# ---------------------------------------------------------------------------
# MACD
# ---------------------------------------------------------------------------
def test_macd_of_constant_is_zero():
    macd_line, signal_line, histogram = ind.macd(series([100.0] * 100))
    assert np.allclose(macd_line.values, 0.0)
    assert np.allclose(signal_line.values, 0.0)
    assert np.allclose(histogram.values, 0.0)


def test_macd_positive_in_uptrend():
    rising = series([float(i) for i in range(1, 200)])
    macd_line, _, _ = ind.macd(rising)
    assert macd_line.iloc[-1] > 0


def test_macd_histogram_is_line_minus_signal():
    rng = np.random.default_rng(11)
    walk = series(list(100 + np.cumsum(rng.normal(0, 1, 200))))
    macd_line, signal_line, histogram = ind.macd(walk)
    pd.testing.assert_series_equal(histogram, macd_line - signal_line)


def test_macd_rejects_inverted_periods():
    with pytest.raises(ValueError):
        ind.macd(series([1.0] * 50), fast=26, slow=12)


# ---------------------------------------------------------------------------
# True range / ATR
# ---------------------------------------------------------------------------
def test_true_range_uses_widest_span():
    high = series([11.0, 15.0])
    low = series([9.0, 14.0])
    close = series([10.0, 14.5])
    result = ind.true_range(high, low, close)
    # Bar 0 has no previous close, so only high-low applies.
    assert result.iloc[0] == pytest.approx(2.0)
    # Bar 1: high-low=1, |high-prev_close|=5, |low-prev_close|=4 -> 5.
    assert result.iloc[1] == pytest.approx(5.0)


def test_atr_of_constant_range_equals_that_range():
    """A candle series with a fixed 2.0 span has ATR 2.0 once warmed up."""
    n = 60
    close = series([100.0] * n)
    high = close + 1.0
    low = close - 1.0
    result = ind.atr(high, low, close, 14)
    assert result.iloc[-1] == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# ADX
# ---------------------------------------------------------------------------
def test_adx_is_high_in_a_clean_trend():
    """A monotonic advance is maximally directional, so ADX should be high."""
    n = 200
    close = series([100.0 + i for i in range(n)])
    high = close + 0.5
    low = close - 0.5
    adx_value, plus_di, minus_di = ind.adx(high, low, close, 14)
    assert adx_value.iloc[-1] > 60
    assert plus_di.iloc[-1] > minus_di.iloc[-1]


def test_adx_is_low_in_chop():
    """An oscillating market has no net direction, so ADX should be modest."""
    n = 300
    values = [100.0 + (2.0 if i % 2 else -2.0) for i in range(n)]
    close = series(values)
    high = close + 0.5
    low = close - 0.5
    adx_value, _, _ = ind.adx(high, low, close, 14)
    assert adx_value.iloc[-1] < 25


def test_adx_components_stay_in_bounds():
    rng = np.random.default_rng(5)
    close = series(list(100 + np.cumsum(rng.normal(0, 1, 400))))
    high = close + abs(rng.normal(0, 0.5, 400))
    low = close - abs(rng.normal(0, 0.5, 400))
    adx_value, plus_di, minus_di = ind.adx(high, low, close, 14)
    for result in (adx_value.dropna(), plus_di.dropna(), minus_di.dropna()):
        assert result.min() >= 0.0
        assert result.max() <= 100.0


def test_adx_flat_market_gives_zero_not_nan():
    """A perfectly flat market divides by zero in DX; it must return 0."""
    close = series([100.0] * 100)
    adx_value, _, _ = ind.adx(close + 1, close - 1, close, 14)
    assert not adx_value.iloc[-1] != adx_value.iloc[-1]  # not NaN
    assert adx_value.iloc[-1] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Volume ratio
# ---------------------------------------------------------------------------
def test_volume_ratio_excludes_current_bar_from_baseline():
    """A 2x spike against a flat baseline must read exactly 2.0.

    If the current bar were included in the trailing mean, a 20-period window
    would report ~1.9 instead, and a 1.2 threshold would mean something
    different at every volatility level.
    """
    volumes = series([100.0] * 25 + [200.0])
    result = ind.volume_ratio(volumes, 20)
    assert result.iloc[-1] == pytest.approx(2.0)


def test_volume_ratio_is_nan_before_window_fills():
    result = ind.volume_ratio(series([100.0] * 10), 20)
    assert result.isna().all()


def test_volume_ratio_handles_zero_baseline():
    """A dead market must not produce inf and leak into comparisons."""
    volumes = series([0.0] * 25 + [50.0])
    result = ind.volume_ratio(volumes, 20)
    assert pd.isna(result.iloc[-1])


def test_bollinger_bands_width_is_k_std():
    """Upper/lower sit k population-stds from the SMA mid."""
    values = series([float(i) for i in range(1, 31)])
    mid, upper, lower = ind.bollinger_bands(values, period=20, k=2.0)
    assert pd.isna(mid.iloc[18])
    window = values.iloc[10:30]
    expected_mid = window.mean()
    expected_std = window.std(ddof=0)
    assert mid.iloc[-1] == pytest.approx(expected_mid)
    assert upper.iloc[-1] == pytest.approx(expected_mid + 2.0 * expected_std)
    assert lower.iloc[-1] == pytest.approx(expected_mid - 2.0 * expected_std)


def test_bollinger_bands_rejects_nonpositive():
    with pytest.raises(ValueError):
        ind.bollinger_bands(series([1.0, 2.0]), 0)
    with pytest.raises(ValueError):
        ind.bollinger_bands(series([1.0, 2.0]), 5, k=0)


def test_utc_opening_range_blank_during_window_then_locks():
    """Range is NaN in the opening hour, then equals that hour's high/low."""
    index = pd.date_range("2024-01-02", periods=4, freq="h", tz="UTC")
    high = pd.Series([10.0, 12.0, 11.0, 13.0], index=index)
    low = pd.Series([8.0, 9.0, 8.5, 9.5], index=index)
    range_high, range_low, ready = ind.utc_opening_range(high, low, range_hours=1.0)
    assert bool(ready.iloc[0]) is False
    assert pd.isna(range_high.iloc[0])
    assert bool(ready.iloc[1]) is True
    assert range_high.iloc[1] == pytest.approx(10.0)
    assert range_low.iloc[1] == pytest.approx(8.0)
    assert range_high.iloc[2] == pytest.approx(10.0)
    assert range_low.iloc[3] == pytest.approx(8.0)


def test_utc_opening_range_truncation_matches_prefix():
    index = pd.date_range("2024-01-02", periods=30, freq="h", tz="UTC")
    high = pd.Series(range(30), index=index, dtype="float64") + 100.0
    low = high - 2.0
    full_high, _, _ = ind.utc_opening_range(high, low, range_hours=1.0)
    cut = 10
    trunc_high, _, _ = ind.utc_opening_range(high.iloc[:cut], low.iloc[:cut], range_hours=1.0)
    pd.testing.assert_series_equal(full_high.iloc[:cut], trunc_high, check_names=False)


def test_utc_session_vwap_resets_at_midnight():
    index = pd.date_range("2024-01-02", periods=26, freq="h", tz="UTC")
    close = pd.Series([100.0] * 24 + [110.0, 110.0], index=index)
    high = close + 1.0
    low = close - 1.0
    volume = pd.Series(1.0, index=index)
    vwap = ind.utc_session_vwap(high, low, close, volume)
    assert vwap.iloc[0] == pytest.approx(100.0)
    assert vwap.iloc[23] == pytest.approx(100.0)
    assert vwap.iloc[24] == pytest.approx(110.0)


def test_prior_day_close_is_previous_session_last_bar():
    index = pd.date_range("2024-01-02", periods=26, freq="h", tz="UTC")
    close = pd.Series(range(26), index=index, dtype="float64")
    prev = ind.prior_day_close(close)
    assert pd.isna(prev.iloc[0])
    assert prev.iloc[24] == pytest.approx(23.0)
    assert prev.iloc[25] == pytest.approx(23.0)


def test_weekend_utc_range_publishes_monday_only():
    """Sat–Sun box is blank until Monday; Saturday never sees Sunday's high."""
    index = pd.date_range("2024-01-06", periods=80, freq="h", tz="UTC")
    high = pd.Series(101.0, index=index)
    low = pd.Series(99.0, index=index)
    high.loc["2024-01-07 15:00+00:00"] = 108.0
    range_high, range_low, ready = ind.weekend_utc_range(high, low)
    sat = index.get_loc(pd.Timestamp("2024-01-06 12:00", tz="UTC"))
    sun = index.get_loc(pd.Timestamp("2024-01-07 15:00", tz="UTC"))
    mon = index.get_loc(pd.Timestamp("2024-01-08 08:00", tz="UTC"))
    assert bool(ready.iloc[sat]) is False
    assert pd.isna(range_high.iloc[sat])
    assert bool(ready.iloc[sun]) is False
    assert bool(ready.iloc[mon]) is True
    assert range_high.iloc[mon] == pytest.approx(108.0)
    assert range_low.iloc[mon] == pytest.approx(99.0)


def test_weekend_utc_range_truncation_matches_prefix():
    index = pd.date_range("2024-01-06", periods=80, freq="h", tz="UTC")
    high = pd.Series(100.0, index=index) + np.arange(80)
    low = high - 2.0
    full_high, _, _ = ind.weekend_utc_range(high, low)
    cut = 40
    trunc_high, _, _ = ind.weekend_utc_range(high.iloc[:cut], low.iloc[:cut])
    pd.testing.assert_series_equal(full_high.iloc[:cut], trunc_high, check_names=False)


def test_prior_utc_day_range_publishes_after_midnight():
    """Yesterday's H/L is blank until the first bar of the next UTC day."""
    index = pd.date_range("2024-01-02", periods=30, freq="h", tz="UTC")
    high = pd.Series(101.0, index=index)
    low = pd.Series(99.0, index=index)
    high.iloc[5] = 110.0
    low.iloc[8] = 90.0
    prev_h, prev_l = ind.prior_utc_day_range(high, low)
    assert pd.isna(prev_h.iloc[5])
    assert pd.isna(prev_h.iloc[23])
    assert prev_h.iloc[24] == pytest.approx(110.0)
    assert prev_l.iloc[24] == pytest.approx(90.0)
    assert prev_h.iloc[29] == pytest.approx(110.0)


def test_utc_window_vwap_is_london_hours_not_utc_midnight():
    """London 08–16 VWAP ignores the Asian session and is not UTC-day VWAP."""
    index = pd.date_range("2024-01-02", periods=24, freq="h", tz="UTC")
    close = pd.Series(100.0, index=index)
    close.iloc[:8] = 80.0
    close.iloc[8:16] = 100.0
    close.iloc[16:] = 120.0
    high = close + 1.0
    low = close - 1.0
    volume = pd.Series(1.0, index=index)
    london = ind.utc_window_vwap(high, low, close, volume, start_hour=8.0, end_hour=16.0)
    session = ind.utc_session_vwap(high, low, close, volume)
    assert pd.isna(london.iloc[7])
    assert london.iloc[15] == pytest.approx(100.0)
    assert session.iloc[15] != pytest.approx(float(london.iloc[15]), abs=0.5)
    assert london.iloc[20] == pytest.approx(100.0)


def test_bar_covers_utc_hour_4h_and_1h():
    hourly = pd.date_range("2024-01-02", periods=24, freq="h", tz="UTC")
    covers_1h = ind.bar_covers_utc_hour(hourly, 15.0, bar_hours=1.0)
    assert bool(covers_1h.iloc[15]) is True
    assert bool(covers_1h.iloc[14]) is False
    four = pd.date_range("2024-01-02", periods=6, freq="4h", tz="UTC")
    covers_4h = ind.bar_covers_utc_hour(four, 15.0, bar_hours=4.0)
    # 12:00 4h bar covers 15:00; 16:00 does not.
    assert bool(covers_4h.loc[pd.Timestamp("2024-01-02 12:00", tz="UTC")]) is True
    assert bool(covers_4h.loc[pd.Timestamp("2024-01-02 16:00", tz="UTC")]) is False


def test_prior_rolling_mean_excludes_current_bar():
    values = series([10.0] * 5 + [100.0])
    mean = ind.prior_rolling_mean(values, 5)
    assert pd.isna(mean.iloc[4])
    assert mean.iloc[5] == pytest.approx(10.0)


def test_body_efficiency_is_body_over_true_range():
    index = pd.date_range("2024-01-02", periods=3, freq="h", tz="UTC")
    open_ = pd.Series([100.0, 100.0, 100.0], index=index)
    close = pd.Series([100.0, 110.0, 100.0], index=index)
    high = pd.Series([101.0, 112.0, 101.0], index=index)
    low = pd.Series([99.0, 99.0, 99.0], index=index)
    eff = ind.body_efficiency(open_, high, low, close)
    # Bar 1: body 10, TR = max(13, |112-100|, |99-100|) = 13 → 10/13.
    assert eff.iloc[1] == pytest.approx(10.0 / 13.0)
    assert eff.iloc[0] == pytest.approx(0.0)


def test_close_location_value_doji_at_high_is_one_efficiency_near_zero():
    """A doji pinned at the high has CLV near 1 and body efficiency near 0."""
    index = pd.date_range("2024-01-02", periods=2, freq="h", tz="UTC")
    open_ = pd.Series([100.05, 100.05], index=index)
    close = pd.Series([100.10, 100.10], index=index)
    high = pd.Series([100.15, 100.15], index=index)
    low = pd.Series([90.0, 90.0], index=index)
    clv = ind.close_location_value(high, low, close)
    eff = ind.body_efficiency(open_, high, low, close)
    assert clv.iloc[1] == pytest.approx((100.10 - 90.0) / (100.15 - 90.0))
    assert clv.iloc[1] > 0.99
    assert eff.iloc[1] < 0.05
    mean_clv = ind.mean_close_location(high, low, close, lookback=2)
    assert mean_clv.iloc[1] == pytest.approx(float(clv.mean()))
    # Zero-range bar is 0.5, not a divide-by-zero.
    flat = pd.Series([100.0], index=index[:1])
    assert ind.close_location_value(flat, flat, flat).iloc[0] == pytest.approx(0.5)


def test_rolling_second_max_min_are_causal():
    index = pd.date_range("2024-01-02", periods=5, freq="h", tz="UTC")
    high = pd.Series([1.0, 3.0, 2.0, 5.0, 4.0], index=index)
    low = pd.Series([10.0, 8.0, 9.0, 6.0, 7.0], index=index)
    second_high = ind.rolling_second_max(high, 3)
    second_low = ind.rolling_second_min(low, 3)
    assert pd.isna(second_high.iloc[1])
    assert second_high.iloc[2] == pytest.approx(2.0)
    assert second_high.iloc[3] == pytest.approx(3.0)
    assert second_low.iloc[2] == pytest.approx(9.0)
    assert second_low.iloc[3] == pytest.approx(8.0)
    # Last-bar shock cannot rewrite a prior second-extreme.
    shocked = high.copy()
    shocked.iloc[-1] = 100.0
    after = ind.rolling_second_max(shocked, 3)
    pd.testing.assert_series_equal(second_high.iloc[:-1], after.iloc[:-1])


def test_published_swing_pivots_equal_prices_still_event():
    """A second pivot at the same price still publishes; ffill would hide it."""
    index = pd.date_range("2024-01-02", periods=40, freq="h", tz="UTC")
    drift = 0.01 * np.arange(40)
    high = pd.Series(101.0 + drift, index=index)
    low = pd.Series(99.0 + drift, index=index)
    low.iloc[10] = 90.0
    high.iloc[18] = 110.0
    low.iloc[26] = 90.0
    pub_high, pub_low = ind.published_swing_pivots(high, low, left=3)
    low_events = [i for i, flag in enumerate(pub_low.notna()) if flag]
    high_events = [i for i, flag in enumerate(pub_high.notna()) if flag]
    assert len(low_events) >= 2
    assert len(high_events) >= 1
    assert pub_low.iloc[low_events[0]] == pytest.approx(90.0)
    assert pub_low.iloc[low_events[1]] == pytest.approx(90.0)
    assert pub_high.iloc[high_events[0]] == pytest.approx(110.0)
    # Publication is after confirmation: a future shock cannot rewrite prior events.
    shocked_high = high.copy()
    shocked_high.iloc[-1] = 200.0
    _, after_low = ind.published_swing_pivots(shocked_high, low, left=3)
    pd.testing.assert_series_equal(pub_low.iloc[:-1], after_low.iloc[:-1])


def test_lookback_swing_structure_double_bottom_neckline_is_intervening_high():
    index = pd.date_range("2024-01-02", periods=80, freq="h", tz="UTC")
    drift = 0.01 * np.arange(80)
    high = pd.Series(101.0 + drift, index=index)
    low = pd.Series(99.0 + drift, index=index)
    low.iloc[22] = 90.0
    high.iloc[34] = 110.0
    low.iloc[46] = 90.1
    structure = ind.lookback_swing_structure(high, low, lookback=40, left=3)
    # Second low publishes at 50; neckline must be the intervening high, not Donchian.
    assert structure["double_bottom_neckline"].iloc[58] == pytest.approx(110.0)
    assert structure["prev_low"].iloc[58] == pytest.approx(90.0)
    assert structure["last_low"].iloc[58] == pytest.approx(90.1)
    donchian_high = high.iloc[19:59].max()
    assert structure["double_bottom_neckline"].iloc[58] == pytest.approx(110.0)
    assert donchian_high == pytest.approx(110.0)
    cut = 50
    truncated = ind.lookback_swing_structure(high.iloc[:cut], low.iloc[:cut], lookback=40, left=3)
    pd.testing.assert_series_equal(
        structure["double_bottom_neckline"].iloc[:cut],
        truncated["double_bottom_neckline"],
        check_names=False,
    )


def test_iso_week_open_is_monday_0000_not_midweek():
    index = pd.date_range("2024-01-01", periods=48, freq="h", tz="UTC")
    open_ = pd.Series(100.0, index=index)
    open_.iloc[0] = 80.0
    open_.iloc[10] = 120.0
    week_open = ind.iso_week_open(open_)
    assert week_open.iloc[0] == pytest.approx(80.0)
    assert week_open.iloc[10] == pytest.approx(80.0)
    assert week_open.iloc[36] == pytest.approx(80.0)


def test_prior_utc_8h_session_publishes_after_session_ends():
    index = pd.date_range("2024-01-02", periods=24, freq="h", tz="UTC")
    high = pd.Series(101.0, index=index)
    low = pd.Series(99.0, index=index)
    close = pd.Series(100.0, index=index)
    high.iloc[3] = 110.0
    low.iloc[5] = 90.0
    close.iloc[7] = 92.0
    prev_h, prev_l, prev_c, mid, ready = ind.prior_utc_8h_session(high, low, close)
    assert bool(ready.iloc[7]) is False
    assert pd.isna(mid.iloc[7])
    assert bool(ready.iloc[8]) is True
    assert prev_h.iloc[8] == pytest.approx(110.0)
    assert prev_l.iloc[8] == pytest.approx(90.0)
    assert prev_c.iloc[8] == pytest.approx(92.0)
    assert mid.iloc[8] == pytest.approx(100.0)
    assert mid.iloc[12] == pytest.approx(100.0)


def test_rolling_vwap_is_not_session_vwap_or_vwma():
    """Typical-price rolling VWAP ≠ UTC session VWAP and ≠ close VWMA."""
    index = pd.date_range("2024-01-02", periods=24, freq="h", tz="UTC")
    close = pd.Series(100.0, index=index)
    high = close + 2.0
    low = close - 1.0
    volume = pd.Series(100.0, index=index)
    volume.iloc[20:] = 5_000.0
    close.iloc[20:] = 110.0
    high.iloc[20:] = 112.0
    low.iloc[20:] = 109.0
    rolled = ind.rolling_vwap(high, low, close, volume, period=20)
    session = ind.utc_session_vwap(high, low, close, volume)
    close_vwma = ind.vwma(close, volume, 20)
    assert rolled.iloc[23] != pytest.approx(float(session.iloc[23]), abs=0.05)
    assert rolled.iloc[23] != pytest.approx(float(close_vwma.iloc[23]), abs=0.05)


def test_bollinger_width_is_relative():
    close = pd.Series(np.linspace(100.0, 110.0, 40))
    width = ind.bollinger_width(close, period=20, k=2.0)
    mid, upper, lower = ind.bollinger_bands(close, 20, 2.0)
    assert width.iloc[30] == pytest.approx(
        float((upper.iloc[30] - lower.iloc[30]) / mid.iloc[30])
    )


def test_bar_buy_share_is_close_location_not_cumsum():
    index = pd.date_range("2024-01-02", periods=3, freq="h", tz="UTC")
    high = pd.Series([110.0, 110.0, 110.0], index=index)
    low = pd.Series([100.0, 100.0, 100.0], index=index)
    close = pd.Series([101.0, 109.0, 105.0], index=index)
    share = ind.bar_buy_share(high, low, close)
    assert share.iloc[0] == pytest.approx(0.10)
    assert share.iloc[1] == pytest.approx(0.90)
    assert share.iloc[2] == pytest.approx(0.50)
    # Zero-range bar is 0.5, not a divide-by-zero.
    flat_high = pd.Series([100.0], index=index[:1])
    assert ind.bar_buy_share(flat_high, flat_high, flat_high).iloc[0] == pytest.approx(0.5)
