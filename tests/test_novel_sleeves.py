"""Schema, entry, and no-lookahead tests for the operator-approved novel sleeves."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core.strategy.base import SignalSide
from core.strategy.registry import list_strategies


APPROVED = [
    "utc_session_vwap_reversion",
    "asian_range_breakout",
    "inside_bar_breakout",
    "swing_failure_reversal",
    "consecutive_bar_exhaustion",
    "wick_rejection_reversal",
    "prior_day_pivot_breakout",
    "weekend_gap_fill",
    "engulfing_reversal",
    "utc_midnight_gap_fill",
    "nr7_breakout",
    "failed_higher_high",
    "utc_session_twap_reversion",
    "prior_week_high_break",
    "round_number_fade",
    "doji_star_reversal",
    "outside_bar_reversal",
    "three_bar_play",
    "ny_cash_open_drive",
    "london_session_breakout",
    "stochastic_fade",
    "cci_reversion",
    "supertrend_flip",
    "heikin_ashi_trend",
    "williams_r_fade",
    "obv_break",
    "ichimoku_tk_cross",
    "mfi_fade",
    "chaikin_oscillator_cross",
    "chande_momentum_fade",
    "vortex_cross",
    "dpo_cycle_fade",
    "trix_cross",
    "force_index_fade",
    "awesome_oscillator_saucer",
    "aroon_crossover",
    "ppo_cross",
    "ultimate_oscillator_fade",
    "kst_cross",
    "tsi_cross",
    "fisher_transform_cross",
    "hull_ma_trend",
    "elder_ray_fade",
    "schaff_trend_cross",
    "mass_index_reversal",
    "ease_of_movement_fade",
    "coppock_curve_cross",
    "qstick_cross",
    "relative_vigor_cross",
    "klinger_volume_cross",
    "kaufman_efficiency_trend",
    "demarker_fade",
    "choppiness_index_break",
    "psychological_line_cross",
    "kairi_relative_fade",
    "linreg_slope_cross",
    "ehlers_decycler_cross",
    "volume_price_trend_break",
    "balance_of_power_cross",
    "twiggs_money_flow_fade",
    "parabolic_sar_flip",
    "center_of_gravity_cross",
    "mama_fama_cross",
    "connors_rsi_fade",
    "rsi_laguerre_fade",
    "vidya_trend",
    "t3_trend",
    "chaikin_money_flow_fade",
    "accumulation_distribution_break",
    "zero_lag_ema_cross",
    "smi_fade",
    "elder_impulse_trend",
    "rainbow_oscillator_cross",
    "laguerre_filter_cross",
    "gator_oscillator_cross",
    "williams_fractal_break",
    "volume_force_divergence",
    "session_liquidity_sweep",
    "bar_vwap_inflow_surge",
    "fib_retracement_bounce",
    "fib_extension_break",
    "measured_move_break",
    "up_down_turnover_imbalance",
    "signed_range_turnover_trend",
    "swing_anchored_vwap_pullback",
    "monday_range_sweep_reversal",
    "volume_imbalance_delta_reversal",
    "session_boundary_volume_fade",
    "vwap_spread_exhaustion",
    "vwap_volatility_band_fade",
    "london_close_inventory_fade",
    "utc_open_fail_reversion",
    "range_compression_volume_thrust",
    "turnover_climax_rejection_fade",
    "volume_dryup_range_break",
    "body_efficiency_follow",
    "week_open_reclaim",
    "prior_session_mid_reclaim",
    "close_location_persistence",
    "open_in_prior_range_fail",
    "equal_high_low_restest_fade",
    "double_bottom_neckline_break",
    "double_top_neckline_break",
    "ascending_triangle_break",
    "prior_day_extreme_reject",
    "failed_range_break_reversion",
    "asia_range_london_reject",
    "orb_fail_reversion",
    "nr7_fail_reversion",
    "ib_fail_reversion",
    "converging_wedge_break",
    "engulfing_fail_reversion",
    "wyckoff_spring_reclaim",
    "prior_close_magnet_fade",
    "classic_floor_pivot_reject",
    "failed_break_reclaim",
    "expansion_fail_fade",
    "candle_reject_reversal",
    "bullish_rectangle_fail_reclaim",
]


def _hourly(n: int, start: str = "2024-01-02") -> pd.DatetimeIndex:
    return pd.date_range(start, periods=n, freq="h", tz="UTC")


def _ohlcv(index: pd.DatetimeIndex, close: np.ndarray, high=None, low=None, open_=None) -> pd.DataFrame:
    close = np.asarray(close, dtype="float64")
    n = len(close)
    high = np.asarray(high if high is not None else close + 1.0, dtype="float64")
    low = np.asarray(low if low is not None else close - 1.0, dtype="float64")
    if open_ is None:
        open_ = np.concatenate([[close[0]], close[:-1]])
    frame = pd.DataFrame(
        {
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": np.full(n, 1_000.0),
        },
        index=index,
    )
    # Quote volume so bar_vwap = turnover / volume is defined on every fixture.
    frame["turnover"] = frame["volume"] * frame["close"]
    frame.index.name = "timestamp"
    return frame


def _signals(name: str, candles: pd.DataFrame, side: SignalSide = SignalSide.LONG):
    from research.validate import strategy_kit

    factory, base, _space = strategy_kit(name, side)
    return factory(base).generate_signals(candles)


def test_approved_novels_are_registered() -> None:
    names = set(list_strategies())
    missing = [n for n in APPROVED if n not in names]
    assert missing == []


@pytest.mark.parametrize("name", APPROVED)
def test_novel_kit_is_not_rsi(name: str) -> None:
    from research.validate import strategy_kit

    factory, base, space = strategy_kit(name, SignalSide.LONG)
    sleeve = factory(base)
    assert sleeve.name == name
    assert "rsi_min" not in space


def test_vwap_fade_long_entry() -> None:
    n = 48
    close = np.full(n, 100.0)
    close[30:] = 90.0
    candles = _ohlcv(_hourly(n), close)
    signals = _signals("utc_session_vwap_reversion", candles)
    assert int((signals["signal"] == 1).sum()) >= 1
    assert int(signals["signal"].iloc[0]) == 0


def test_asian_range_break_after_0800() -> None:
    n = 48
    close = np.full(n, 100.0)
    high = np.full(n, 101.0)
    low = np.full(n, 99.0)
    close[33] = 110.0
    high[33] = 111.0
    candles = _ohlcv(_hourly(n), close, high=high, low=low)
    signals = _signals("asian_range_breakout", candles)
    assert int(signals["signal"].iloc[33]) == 1
    assert int(signals["signal"].iloc[7]) == 0


def test_inside_bar_break() -> None:
    n = 24
    close = np.full(n, 100.0)
    high = np.full(n, 101.0)
    low = np.full(n, 99.0)
    high[18] = 110.0
    low[18] = 90.0
    close[18] = 100.0
    high[19] = 105.0
    low[19] = 95.0
    close[19] = 100.0
    close[20] = 112.0
    high[20] = 113.0
    candles = _ohlcv(_hourly(n), close, high=high, low=low)
    signals = _signals("inside_bar_breakout", candles)
    assert int(signals["signal"].iloc[20]) == 1


def test_swing_failure_long() -> None:
    n = 40
    close = np.full(n, 100.0)
    high = np.full(n, 102.0)
    low = np.full(n, 98.0)
    low[13] = 90.0
    high[13] = 100.0
    close[13] = 99.0
    low[20] = 85.0
    close[20] = 96.0
    high[20] = 100.0
    candles = _ohlcv(_hourly(n), close, high=high, low=low)
    signals = _signals("swing_failure_reversal", candles)
    assert int((signals["signal"] == 1).sum()) >= 1


def test_consecutive_exhaustion_long() -> None:
    n = 24
    close = np.full(n, 100.0)
    for i, value in enumerate([99, 98, 97, 96, 95], start=12):
        close[i] = value
    candles = _ohlcv(_hourly(n), close)
    signals = _signals("consecutive_bar_exhaustion", candles)
    assert int((signals["signal"] == 1).sum()) >= 1


def test_wick_rejection_long() -> None:
    n = 20
    close = np.full(n, 100.0)
    high = np.full(n, 101.0)
    low = np.full(n, 99.0)
    open_ = np.concatenate([[100.0], close[:-1]])
    open_[12] = 100.0
    close[12] = 100.5
    high[12] = 101.0
    low[12] = 90.0
    candles = _ohlcv(_hourly(n), close, high=high, low=low, open_=open_)
    signals = _signals("wick_rejection_reversal", candles)
    assert int(signals["signal"].iloc[12]) == 1


def test_prior_day_pivot_break() -> None:
    n = 48
    close = np.full(n, 100.0)
    high = np.full(n, 101.0)
    low = np.full(n, 99.0)
    close[40] = 108.0
    high[40] = 109.0
    candles = _ohlcv(_hourly(n), close, high=high, low=low)
    signals = _signals("prior_day_pivot_breakout", candles)
    assert int((signals["signal"] == 1).sum()) >= 1


def test_weekend_gap_fill_long() -> None:
    # Thursday 2024-01-04 through Monday.
    n = 120
    close = np.full(n, 100.0)
    open_ = np.concatenate([[100.0], close[:-1]])
    index = _hourly(n, start="2024-01-04")
    monday = index.dayofweek == 0
    first_monday = int(np.argmax(monday))
    open_[first_monday] = 90.0
    close[first_monday] = 92.0
    candles = _ohlcv(index, close, open_=open_)
    signals = _signals("weekend_gap_fill", candles)
    assert int(signals["signal"].iloc[first_monday]) == 1


def test_engulfing_long() -> None:
    n = 20
    close = np.full(n, 100.0)
    open_ = np.concatenate([[100.0], close[:-1]])
    open_[11] = 102.0
    close[11] = 98.0
    open_[12] = 97.0
    close[12] = 103.0
    high = np.maximum(open_, close) + 0.5
    low = np.minimum(open_, close) - 0.5
    candles = _ohlcv(_hourly(n), close, high=high, low=low, open_=open_)
    signals = _signals("engulfing_reversal", candles)
    assert int(signals["signal"].iloc[12]) == 1


def test_midnight_gap_fill_long() -> None:
    n = 48
    close = np.full(n, 100.0)
    open_ = np.concatenate([[100.0], close[:-1]])
    open_[24] = 90.0
    close[24] = 92.0
    candles = _ohlcv(_hourly(n), close, open_=open_)
    signals = _signals("utc_midnight_gap_fill", candles)
    assert int(signals["signal"].iloc[24]) == 1


def test_nr7_break_long() -> None:
    n = 24
    close = np.full(n, 100.0)
    high = np.full(n, 102.0)
    low = np.full(n, 98.0)
    high[12] = 100.2
    low[12] = 99.8
    close[12] = 100.0
    close[13] = 103.0
    high[13] = 104.0
    candles = _ohlcv(_hourly(n), close, high=high, low=low)
    signals = _signals("nr7_breakout", candles)
    assert int(signals["signal"].iloc[13]) == 1


def test_twap_fade_long_entry() -> None:
    n = 48
    close = np.full(n, 100.0)
    close[30:] = 90.0
    candles = _ohlcv(_hourly(n), close)
    signals = _signals("utc_session_twap_reversion", candles)
    assert int((signals["signal"] == 1).sum()) >= 1


def test_round_number_fade_long() -> None:
    n = 20
    close = np.full(n, 101.0)
    high = np.full(n, 102.0)
    low = np.full(n, 100.5)
    close[12] = 100.4
    high[12] = 101.0
    low[12] = 99.4
    candles = _ohlcv(_hourly(n), close, high=high, low=low)
    signals = _signals("round_number_fade", candles)
    assert int(signals["signal"].iloc[12]) == 1


def test_outside_bar_long() -> None:
    n = 20
    close = np.full(n, 100.0)
    open_ = np.concatenate([[100.0], close[:-1]])
    high = np.full(n, 101.0)
    low = np.full(n, 99.0)
    high[11] = 101.0
    low[11] = 99.0
    open_[12] = 99.5
    close[12] = 102.0
    high[12] = 103.0
    low[12] = 98.0
    candles = _ohlcv(_hourly(n), close, high=high, low=low, open_=open_)
    signals = _signals("outside_bar_reversal", candles)
    assert int(signals["signal"].iloc[12]) == 1


def test_three_bar_play_long() -> None:
    n = 20
    close = np.full(n, 100.0)
    open_ = np.concatenate([[100.0], close[:-1]])
    high = np.full(n, 101.0)
    low = np.full(n, 99.0)
    open_[10] = 98.0
    close[10] = 110.0
    high[10] = 111.0
    low[10] = 97.0
    open_[11] = 104.0
    close[11] = 105.0
    high[11] = 108.0
    low[11] = 102.0
    close[12] = 109.0
    high[12] = 110.0
    candles = _ohlcv(_hourly(n), close, high=high, low=low, open_=open_)
    signals = _signals("three_bar_play", candles)
    assert int(signals["signal"].iloc[12]) == 1


def test_doji_star_long() -> None:
    n = 24
    close = np.linspace(110, 95, n)
    open_ = np.concatenate([[close[0]], close[:-1]])
    high = np.maximum(open_, close) + 0.5
    low = np.minimum(open_, close) - 0.5
    # Force a doji at 16 after the down run; confirm at 17.
    open_[16] = 96.0
    close[16] = 96.05
    high[16] = 97.0
    low[16] = 95.0
    close[17] = 98.0
    high[17] = 98.5
    candles = _ohlcv(_hourly(n), close, high=high, low=low, open_=open_)
    signals = _signals("doji_star_reversal", candles)
    assert int(signals["signal"].iloc[17]) == 1


def test_ny_cash_open_drive_long() -> None:
    n = 24
    close = np.full(n, 100.0)
    open_ = np.concatenate([[100.0], close[:-1]])
    open_[13] = 100.0
    close[13] = 108.0
    candles = _ohlcv(_hourly(n, start="2024-01-02"), close, open_=open_)
    signals = _signals("ny_cash_open_drive", candles)
    assert int(signals["signal"].iloc[14]) == 1
    assert int(signals["signal"].iloc[13]) == 0


def test_london_range_break_after_1600() -> None:
    n = 48
    close = np.full(n, 100.0)
    high = np.full(n, 101.0)
    low = np.full(n, 99.0)
    close[16] = 110.0
    high[16] = 111.0
    candles = _ohlcv(_hourly(n, start="2024-01-02"), close, high=high, low=low)
    signals = _signals("london_session_breakout", candles)
    assert int(signals["signal"].iloc[16]) == 1
    assert int(signals["signal"].iloc[15]) == 0


def test_stochastic_fade_long_entry() -> None:
    n = 40
    close = np.concatenate([np.linspace(100, 80, 25), np.linspace(80, 84, 15)])
    high = close + 0.4
    low = close - 0.4
    candles = _ohlcv(_hourly(n), close, high=high, low=low)
    signals = _signals("stochastic_fade", candles)
    assert int((signals["signal"] == 1).sum()) >= 1


def test_cci_reversion_long_entry() -> None:
    n = 80
    close = np.full(n, 100.0)
    high = np.full(n, 101.0)
    low = np.full(n, 99.0)
    close[-8:] = 40.0
    high[-8:] = 41.0
    low[-8:] = 39.0
    candles = _ohlcv(_hourly(n), close, high=high, low=low)
    signals = _signals("cci_reversion", candles)
    assert int((signals["signal"] == 1).sum()) >= 1


def test_supertrend_flip_long_entry() -> None:
    n = 50
    close = np.concatenate([np.linspace(130, 80, 30), np.linspace(80, 140, 20)])
    high = close + 1.0
    low = close - 1.0
    candles = _ohlcv(_hourly(n), close, high=high, low=low)
    signals = _signals("supertrend_flip", candles)
    assert int((signals["signal"] == 1).sum()) >= 1


def test_heikin_ashi_trend_long_entry() -> None:
    n = 40
    close = np.concatenate([np.linspace(120, 80, 20), np.linspace(80, 130, 20)])
    high = close + 0.8
    low = close - 0.8
    candles = _ohlcv(_hourly(n), close, high=high, low=low)
    signals = _signals("heikin_ashi_trend", candles)
    assert int((signals["signal"] == 1).sum()) >= 1


def test_williams_r_fade_long_entry() -> None:
    n = 40
    close = np.concatenate([np.linspace(100, 80, 25), np.linspace(80, 84, 15)])
    high = close + 0.4
    low = close - 0.4
    candles = _ohlcv(_hourly(n), close, high=high, low=low)
    signals = _signals("williams_r_fade", candles)
    assert int((signals["signal"] == 1).sum()) >= 1


def test_obv_break_long_entry() -> None:
    n = 40
    close = np.concatenate([np.full(25, 100.0), np.linspace(100, 120, 15)])
    volume = np.concatenate([np.full(25, 100.0), np.full(15, 500.0)])
    candles = _ohlcv(_hourly(n), close)
    candles["volume"] = volume
    signals = _signals("obv_break", candles)
    assert int((signals["signal"] == 1).sum()) >= 1


def test_ichimoku_tk_cross_long_entry() -> None:
    n = 50
    close = np.concatenate([np.linspace(120, 80, 28), np.linspace(80, 130, 22)])
    high = close + 1.0
    low = close - 1.0
    candles = _ohlcv(_hourly(n), close, high=high, low=low)
    signals = _signals("ichimoku_tk_cross", candles)
    assert int((signals["signal"] == 1).sum()) >= 1


def test_mfi_fade_long_entry() -> None:
    n = 50
    close = np.concatenate([np.linspace(100, 70, 30), np.linspace(70, 76, 20)])
    high = close + 0.5
    low = close - 0.5
    candles = _ohlcv(_hourly(n), close, high=high, low=low)
    candles["volume"] = np.concatenate([np.full(30, 2_000.0), np.full(20, 800.0)])
    signals = _signals("mfi_fade", candles)
    assert int((signals["signal"] == 1).sum()) >= 1


def test_chaikin_oscillator_cross_long_entry() -> None:
    n = 80
    close = np.concatenate([np.linspace(120, 70, 40), np.linspace(70, 130, 40)])
    high = close.copy()
    low = close.copy()
    # Dump: closes hug the low so CLV is negative. Rally: closes hug the high.
    high[:40] = close[:40] + 3.0
    low[:40] = close[:40] - 0.1
    high[40:] = close[40:] + 0.1
    low[40:] = close[40:] - 3.0
    candles = _ohlcv(_hourly(n), close, high=high, low=low)
    signals = _signals("chaikin_oscillator_cross", candles)
    assert int((signals["signal"] == 1).sum()) >= 1


def test_chande_momentum_fade_long_entry() -> None:
    n = 40
    close = np.concatenate([np.linspace(100, 70, 25), np.linspace(70, 78, 15)])
    candles = _ohlcv(_hourly(n), close)
    signals = _signals("chande_momentum_fade", candles)
    assert int((signals["signal"] == 1).sum()) >= 1


def test_vortex_cross_long_entry() -> None:
    n = 50
    close = np.concatenate([np.linspace(130, 80, 28), np.linspace(80, 140, 22)])
    high = close + 1.0
    low = close - 1.0
    candles = _ohlcv(_hourly(n), close, high=high, low=low)
    signals = _signals("vortex_cross", candles)
    assert int((signals["signal"] == 1).sum()) >= 1


def test_dpo_cycle_fade_long_entry() -> None:
    n = 60
    close = np.concatenate([np.full(25, 100.0), np.linspace(100, 70, 20), np.linspace(70, 74, 15)])
    candles = _ohlcv(_hourly(n), close)
    signals = _signals("dpo_cycle_fade", candles)
    assert int((signals["signal"] == 1).sum()) >= 1


def test_trix_cross_long_entry() -> None:
    n = 140
    close = np.concatenate([np.linspace(140, 70, 80), np.linspace(70, 160, 60)])
    candles = _ohlcv(_hourly(n), close)
    signals = _signals("trix_cross", candles)
    assert int((signals["signal"] == 1).sum()) >= 1


def test_force_index_fade_long_entry() -> None:
    n = 80
    close = np.full(n, 100.0)
    close[55:60] = np.linspace(100, 60, 5)
    close[60:] = np.linspace(62, 78, n - 60)
    candles = _ohlcv(_hourly(n), close)
    volume = np.full(n, 200.0)
    volume[55:60] = 8_000.0
    candles["volume"] = volume
    signals = _signals("force_index_fade", candles)
    assert int((signals["signal"] == 1).sum()) >= 1


def test_awesome_oscillator_saucer_long_entry() -> None:
    n = 80
    close = np.linspace(80, 140, n)
    close[-4] = 136.0
    close[-3] = 134.0
    close[-2] = 133.0
    close[-1] = 145.0
    high = close + 0.8
    low = close - 0.8
    candles = _ohlcv(_hourly(n), close, high=high, low=low)
    signals = _signals("awesome_oscillator_saucer", candles)
    assert int((signals["signal"] == 1).sum()) >= 1


def test_aroon_crossover_long_entry() -> None:
    n = 60
    close = np.concatenate([np.linspace(140, 70, 35), np.linspace(70, 150, 25)])
    high = close + 1.0
    low = close - 1.0
    candles = _ohlcv(_hourly(n), close, high=high, low=low)
    signals = _signals("aroon_crossover", candles)
    assert int((signals["signal"] == 1).sum()) >= 1


def test_ppo_cross_long_entry() -> None:
    n = 80
    close = np.concatenate([np.linspace(140, 70, 45), np.linspace(70, 150, 35)])
    candles = _ohlcv(_hourly(n), close)
    signals = _signals("ppo_cross", candles)
    assert int((signals["signal"] == 1).sum()) >= 1


def test_ultimate_oscillator_fade_long_entry() -> None:
    n = 80
    close = np.concatenate([np.full(40, 100.0), np.linspace(100, 55, 25), np.linspace(55, 70, 15)])
    # Dump bars hug the low so buying pressure is tiny vs true range.
    high = close + 4.0
    low = close - 0.05
    high[40:65] = close[40:65] + 0.2
    low[40:65] = close[40:65] - 0.05
    candles = _ohlcv(_hourly(n), close, high=high, low=low)
    signals = _signals("ultimate_oscillator_fade", candles)
    assert int((signals["signal"] == 1).sum()) >= 1


def test_kst_cross_long_entry() -> None:
    n = 120
    close = np.concatenate([np.linspace(140, 70, 70), np.linspace(70, 160, 50)])
    candles = _ohlcv(_hourly(n), close)
    signals = _signals("kst_cross", candles)
    assert int((signals["signal"] == 1).sum()) >= 1


def test_tsi_cross_long_entry() -> None:
    n = 100
    close = np.concatenate([np.linspace(140, 70, 55), np.linspace(70, 160, 45)])
    candles = _ohlcv(_hourly(n), close)
    signals = _signals("tsi_cross", candles)
    assert int((signals["signal"] == 1).sum()) >= 1


def test_fisher_transform_cross_long_entry() -> None:
    n = 80
    close = np.concatenate([np.linspace(120, 60, 40), np.linspace(60, 140, 40)])
    candles = _ohlcv(_hourly(n), close)
    signals = _signals("fisher_transform_cross", candles)
    assert int((signals["signal"] == 1).sum()) >= 1


def test_hull_ma_trend_long_entry() -> None:
    n = 80
    close = np.concatenate([np.linspace(140, 70, 40), np.linspace(70, 150, 40)])
    candles = _ohlcv(_hourly(n), close)
    signals = _signals("hull_ma_trend", candles)
    assert int((signals["signal"] == 1).sum()) >= 1


def test_elder_ray_fade_long_entry() -> None:
    n = 100
    close = np.concatenate([np.full(50, 100.0), np.linspace(100, 60, 20), np.linspace(60, 90, 30)])
    high = close + 1.0
    low = close - 1.0
    low[50:70] = close[50:70] - 20.0
    candles = _ohlcv(_hourly(n), close, high=high, low=low)
    signals = _signals("elder_ray_fade", candles)
    assert int((signals["signal"] == 1).sum()) >= 1


def test_schaff_trend_cross_long_entry() -> None:
    n = 160
    wave = 12.0 * np.sin(np.linspace(0, 10 * np.pi, n))
    close = 100.0 + wave + np.concatenate([np.zeros(90), np.linspace(0, 50, 70)])
    candles = _ohlcv(_hourly(n), close)
    signals = _signals("schaff_trend_cross", candles)
    assert int((signals["signal"] == 1).sum()) >= 1


def test_mass_index_reversal_long_entry() -> None:
    n = 80
    close = np.concatenate([np.full(30, 100.0), np.full(25, 100.0), np.linspace(100, 108, 25)])
    high = np.concatenate([np.full(30, 101.0), np.full(25, 112.0), np.full(25, 101.5)])
    low = np.concatenate([np.full(30, 99.0), np.full(25, 88.0), np.full(25, 99.5)])
    candles = _ohlcv(_hourly(n), close, high=high, low=low)
    signals = _signals("mass_index_reversal", candles)
    assert int((signals["signal"] == 1).sum()) >= 1


def test_mass_index_trend_sma_blocks_long_in_downtrend() -> None:
    from core.strategy.base import SignalSide
    from core.strategy.mass_index_reversal import MassIndexReversalParams, MassIndexReversalStrategy

    n = 80
    close = np.concatenate([np.full(30, 100.0), np.full(25, 100.0), np.linspace(100, 108, 25)])
    high = np.concatenate([np.full(30, 101.0), np.full(25, 112.0), np.full(25, 101.5)])
    low = np.concatenate([np.full(30, 99.0), np.full(25, 88.0), np.full(25, 99.5)])
    candles = _ohlcv(_hourly(n), close, high=high, low=low)
    open_ = MassIndexReversalStrategy().generate_signals(candles)
    blocked = MassIndexReversalStrategy(
        MassIndexReversalParams(side=SignalSide.LONG, trend_sma=200)
    ).generate_signals(candles)
    # SMA(200) is not warm yet on 80 bars, so every long must stay off.
    assert int((open_["signal"] == 1).sum()) >= 1
    assert int((blocked["signal"] == 1).sum()) == 0


def test_ease_of_movement_fade_long_entry() -> None:
    n = 100
    close = np.concatenate([np.full(50, 100.0), np.linspace(100, 60, 20), np.linspace(60, 90, 30)])
    high = close + 1.0
    low = close - 1.0
    low[50:70] = close[50:70] - 12.0
    candles = _ohlcv(_hourly(n), close, high=high, low=low)
    signals = _signals("ease_of_movement_fade", candles)
    assert int((signals["signal"] == 1).sum()) >= 1


def test_coppock_curve_cross_long_entry() -> None:
    n = 80
    close = np.concatenate([np.linspace(140, 70, 40), np.linspace(70, 150, 40)])
    candles = _ohlcv(_hourly(n), close)
    signals = _signals("coppock_curve_cross", candles)
    assert int((signals["signal"] == 1).sum()) >= 1


def test_qstick_cross_long_entry() -> None:
    n = 40
    close = np.concatenate([np.linspace(120, 80, 20), np.linspace(80, 130, 20)])
    candles = _ohlcv(_hourly(n), close)
    signals = _signals("qstick_cross", candles)
    assert int((signals["signal"] == 1).sum()) >= 1


def test_relative_vigor_cross_long_entry() -> None:
    n = 50
    close = np.concatenate([np.linspace(120, 80, 25), np.linspace(80, 130, 25)])
    candles = _ohlcv(_hourly(n), close)
    signals = _signals("relative_vigor_cross", candles)
    assert int((signals["signal"] == 1).sum()) >= 1


def test_klinger_volume_cross_long_entry() -> None:
    n = 200
    close = 100.0 + 18.0 * np.sin(np.linspace(0, 6 * np.pi, n))
    candles = _ohlcv(_hourly(n), close)
    candles["volume"] = 1500.0 + 800.0 * np.sin(np.linspace(0, 6 * np.pi, n) + 0.8)
    signals = _signals("klinger_volume_cross", candles)
    assert int((signals["signal"] == 1).sum()) >= 1


def test_kaufman_efficiency_trend_long_entry() -> None:
    n = 40
    close = np.concatenate([np.full(15, 100.0), np.linspace(100, 140, 25)])
    candles = _ohlcv(_hourly(n), close)
    signals = _signals("kaufman_efficiency_trend", candles)
    assert int((signals["signal"] == 1).sum()) >= 1


def test_demarker_fade_long_entry() -> None:
    n = 50
    close = np.concatenate([np.full(20, 100.0), np.linspace(100, 70, 15), np.linspace(70, 85, 15)])
    high = close + 0.5
    low = close - 1.5
    low[20:35] = close[20:35] - 4.0
    candles = _ohlcv(_hourly(n), close, high=high, low=low)
    signals = _signals("demarker_fade", candles)
    assert int((signals["signal"] == 1).sum()) >= 1


def test_choppiness_index_break_long_entry() -> None:
    n = 40
    close = np.full(n, 100.0)
    high = np.full(n, 101.0)
    low = np.full(n, 99.0)
    close[-1] = 108.0
    high[-1] = 109.0
    candles = _ohlcv(_hourly(n), close, high=high, low=low)
    signals = _signals("choppiness_index_break", candles)
    assert int((signals["signal"] == 1).sum()) >= 1


def test_psychological_line_cross_long_entry() -> None:
    n = 40
    close = np.concatenate([np.linspace(120, 80, 20), np.linspace(80, 130, 20)])
    candles = _ohlcv(_hourly(n), close)
    signals = _signals("psychological_line_cross", candles)
    assert int((signals["signal"] == 1).sum()) >= 1


def test_kairi_relative_fade_long_entry() -> None:
    n = 50
    close = np.concatenate([np.full(25, 100.0), np.linspace(100, 80, 15), np.linspace(80, 86, 10)])
    candles = _ohlcv(_hourly(n), close)
    signals = _signals("kairi_relative_fade", candles)
    assert int((signals["signal"] == 1).sum()) >= 1


def test_linreg_slope_cross_long_entry() -> None:
    n = 50
    close = np.concatenate([np.linspace(130, 80, 25), np.linspace(80, 140, 25)])
    candles = _ohlcv(_hourly(n), close)
    signals = _signals("linreg_slope_cross", candles)
    assert int((signals["signal"] == 1).sum()) >= 1


def test_ehlers_decycler_cross_long_entry() -> None:
    n = 160
    close = 100.0 + 18.0 * np.sin(np.linspace(0, 8 * np.pi, n))
    candles = _ohlcv(_hourly(n), close)
    signals = _signals("ehlers_decycler_cross", candles)
    assert int((signals["signal"] == 1).sum()) >= 1


def test_volume_price_trend_break_long_entry() -> None:
    n = 40
    close = np.concatenate([np.full(25, 100.0), np.linspace(100, 120, 15)])
    candles = _ohlcv(_hourly(n), close)
    candles["volume"] = np.concatenate([np.full(25, 100.0), np.full(15, 500.0)])
    signals = _signals("volume_price_trend_break", candles)
    assert int((signals["signal"] == 1).sum()) >= 1


def test_balance_of_power_cross_long_entry() -> None:
    n = 40
    close = np.concatenate([np.linspace(120, 80, 20), np.linspace(80, 130, 20)])
    candles = _ohlcv(_hourly(n), close)
    signals = _signals("balance_of_power_cross", candles)
    assert int((signals["signal"] == 1).sum()) >= 1


def test_twiggs_money_flow_fade_long_entry() -> None:
    n = 100
    close = np.concatenate([np.full(40, 100.0), np.linspace(100, 60, 30), np.linspace(60, 90, 30)])
    high = close + 1.0
    low = close - 1.0
    high[40:70] = close[40:70] + 3.0
    low[40:70] = close[40:70] - 0.1
    high[70:] = close[70:] + 0.1
    low[70:] = close[70:] - 3.0
    candles = _ohlcv(_hourly(n), close, high=high, low=low)
    candles["volume"] = np.concatenate([np.full(40, 300.0), np.full(30, 2_500.0), np.full(30, 800.0)])
    signals = _signals("twiggs_money_flow_fade", candles)
    assert int((signals["signal"] == 1).sum()) >= 1


def test_parabolic_sar_flip_long_entry() -> None:
    n = 50
    close = np.concatenate([np.linspace(130, 80, 30), np.linspace(80, 140, 20)])
    high = close + 1.0
    low = close - 1.0
    candles = _ohlcv(_hourly(n), close, high=high, low=low)
    signals = _signals("parabolic_sar_flip", candles)
    assert int((signals["signal"] == 1).sum()) >= 1


def test_center_of_gravity_cross_long_entry() -> None:
    n = 60
    close = 100.0 + 12.0 * np.sin(np.linspace(0, 6 * np.pi, n))
    candles = _ohlcv(_hourly(n), close)
    signals = _signals("center_of_gravity_cross", candles)
    assert int((signals["signal"] == 1).sum()) >= 1


def test_mama_fama_cross_long_entry() -> None:
    n = 80
    close = np.concatenate([np.linspace(140, 70, 40), np.linspace(70, 150, 40)])
    candles = _ohlcv(_hourly(n), close)
    signals = _signals("mama_fama_cross", candles)
    assert int((signals["signal"] == 1).sum()) >= 1


def test_connors_rsi_fade_long_entry() -> None:
    n = 160
    close = np.concatenate([np.full(100, 100.0), np.linspace(100, 70, 40), np.linspace(70, 76, 20)])
    candles = _ohlcv(_hourly(n), close)
    signals = _signals("connors_rsi_fade", candles)
    assert int((signals["signal"] == 1).sum()) >= 1


def test_rsi_laguerre_fade_long_entry() -> None:
    n = 60
    close = np.concatenate([np.full(20, 100.0), np.linspace(100, 70, 25), np.linspace(70, 82, 15)])
    candles = _ohlcv(_hourly(n), close)
    signals = _signals("rsi_laguerre_fade", candles)
    assert int((signals["signal"] == 1).sum()) >= 1


def test_vidya_trend_long_entry() -> None:
    n = 80
    close = np.concatenate([np.linspace(120, 80, 40), np.linspace(80, 130, 40)])
    candles = _ohlcv(_hourly(n), close)
    signals = _signals("vidya_trend", candles)
    assert int((signals["signal"] == 1).sum()) >= 1


def test_t3_trend_long_entry() -> None:
    n = 80
    close = np.concatenate([np.linspace(130, 70, 40), np.linspace(70, 140, 40)])
    candles = _ohlcv(_hourly(n), close)
    signals = _signals("t3_trend", candles)
    assert int((signals["signal"] == 1).sum()) >= 1


def test_zero_lag_ema_cross_long_entry() -> None:
    n = 80
    close = np.concatenate([np.linspace(140, 70, 40), np.linspace(70, 150, 40)])
    candles = _ohlcv(_hourly(n), close)
    signals = _signals("zero_lag_ema_cross", candles)
    assert int((signals["signal"] == 1).sum()) >= 1


def test_laguerre_filter_cross_long_entry() -> None:
    n = 60
    close = np.concatenate([np.linspace(120, 80, 30), np.linspace(80, 130, 30)])
    candles = _ohlcv(_hourly(n), close)
    signals = _signals("laguerre_filter_cross", candles)
    assert int((signals["signal"] == 1).sum()) >= 1


def test_chaikin_money_flow_fade_long_entry() -> None:
    n = 80
    close = np.full(n, 100.0)
    high = np.full(n, 101.0)
    low = np.full(n, 99.0)
    close[20:55] = 88.0
    high[20:55] = 98.0
    low[20:55] = 86.0
    close[55:] = 92.0
    high[55:] = 94.0
    low[55:] = 90.0
    candles = _ohlcv(_hourly(n), close, high=high, low=low)
    signals = _signals("chaikin_money_flow_fade", candles)
    assert int((signals["signal"] == 1).sum()) >= 1


def test_accumulation_distribution_break_long_entry() -> None:
    n = 60
    close = np.full(n, 100.0)
    high = np.full(n, 110.0)
    low = np.full(n, 99.0)
    close[30:] = 120.0
    high[30:] = 121.0
    low[30:] = 100.0
    candles = _ohlcv(_hourly(n), close, high=high, low=low)
    candles["volume"] = np.concatenate([np.full(30, 100.0), np.full(30, 5_000.0)])
    signals = _signals("accumulation_distribution_break", candles)
    assert int((signals["signal"] == 1).sum()) >= 1


def test_smi_fade_long_entry() -> None:
    n = 80
    close = np.concatenate([np.full(20, 100.0), np.linspace(100, 60, 40), np.linspace(60, 72, 20)])
    candles = _ohlcv(_hourly(n), close)
    signals = _signals("smi_fade", candles)
    assert int((signals["signal"] == 1).sum()) >= 1


def test_elder_impulse_trend_long_entry() -> None:
    n = 80
    close = np.concatenate([np.linspace(140, 80, 40), np.linspace(80, 160, 40)])
    candles = _ohlcv(_hourly(n), close)
    signals = _signals("elder_impulse_trend", candles)
    assert int((signals["signal"] == 1).sum()) >= 1


def test_rainbow_oscillator_cross_long_entry() -> None:
    n = 80
    close = np.concatenate([np.linspace(130, 80, 40), np.linspace(80, 140, 40)])
    candles = _ohlcv(_hourly(n), close)
    signals = _signals("rainbow_oscillator_cross", candles)
    assert int((signals["signal"] == 1).sum()) >= 1


def test_gator_oscillator_cross_long_entry() -> None:
    n = 80
    close = np.concatenate([np.linspace(80, 130, 25), np.full(20, 130.0), np.linspace(130, 90, 15), np.linspace(90, 150, 20)])
    high = close + 1.0
    low = close - 1.0
    candles = _ohlcv(_hourly(n), close, high=high, low=low)
    signals = _signals("gator_oscillator_cross", candles)
    assert int((signals["signal"] == 1).sum()) >= 1


def _volume_force_chop(n: int = 160, seed: int = 0) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Quiet tape so ADX stays asleep, with room to plant a force extreme."""
    rng = np.random.default_rng(seed)
    close = 100.0 + rng.normal(0, 0.03, n)
    close[:70] = 100.0 + rng.normal(0, 0.03, 70)
    high = close + 0.08
    low = close - 0.08
    volume = np.full(n, 500.0)
    return close, high, low, volume


def test_volume_force_divergence_schema_and_long_entry() -> None:
    n = 160
    close, high, low, volume = _volume_force_chop(n, seed=0)
    # Heavy-volume dip plants a Volume Force low inside the later 20-bar window.
    close[72:76] = np.array([99.85, 99.70, 99.60, 99.75])
    high[72:76] = close[72:76] + 0.06
    low[72:76] = np.array([99.80, 99.62, 99.50, 99.68])
    volume[72:76] = 40_000.0
    close[76:130] = 100.0 + np.random.default_rng(1).normal(0, 0.03, 54)
    high[76:130] = close[76:130] + 0.08
    low[76:130] = close[76:130] - 0.08
    volume[76:130] = 500.0
    # New price low on tiny volume: force does not confirm.
    close[132:136] = np.array([99.70, 99.40, 99.10, 98.90])
    high[132:136] = close[132:136] + 0.06
    low[132:136] = np.array([99.55, 99.20, 98.85, 98.60])
    volume[132:136] = 60.0
    candles = _ohlcv(_hourly(n), close, high=high, low=low)
    candles["volume"] = volume
    signals = _signals("volume_force_divergence", candles)
    for column in ("signal", "side", "score", "reason", "volume_force", "adx"):
        assert column in signals.columns
    assert int(signals["signal"].iloc[0]) == 0
    assert int((signals["signal"] == 1).sum()) >= 1


def test_volume_force_divergence_short_entry() -> None:
    n = 160
    close, high, low, volume = _volume_force_chop(n, seed=0)
    # Heavy-volume rally plants a Volume Force high.
    close[72:76] = np.array([100.15, 100.30, 100.40, 100.25])
    high[72:76] = np.array([100.20, 100.38, 100.50, 100.32])
    low[72:76] = close[72:76] - 0.06
    volume[72:76] = 40_000.0
    close[76:130] = 100.0 + np.random.default_rng(1).normal(0, 0.03, 54)
    high[76:130] = close[76:130] + 0.08
    low[76:130] = close[76:130] - 0.08
    volume[76:130] = 500.0
    # New price high on tiny volume: force does not confirm.
    close[132:136] = np.array([100.15, 100.30, 100.50, 100.65])
    high[132:136] = np.array([100.28, 100.48, 100.72, 100.90])
    low[132:136] = close[132:136] - 0.06
    volume[132:136] = 60.0
    candles = _ohlcv(_hourly(n), close, high=high, low=low)
    candles["volume"] = volume
    signals = _signals("volume_force_divergence", candles, side=SignalSide.SHORT)
    assert int(signals["signal"].iloc[0]) == 0
    assert int((signals["signal"] == -1).sum()) >= 1


def _asian_box_day(n: int = 48) -> tuple[pd.DatetimeIndex, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Two UTC days of a 99–101 Asian box so London/NY can sweep it."""
    index = _hourly(n)
    close = np.full(n, 100.0)
    high = np.full(n, 101.0)
    low = np.full(n, 99.0)
    open_ = np.full(n, 100.0)
    return index, close, high, low, open_


def test_session_liquidity_sweep_schema_and_long_entry() -> None:
    index, close, high, low, open_ = _asian_box_day()
    # Bar 32 is 2024-01-03 08:00 UTC: Asian box is published, first London hour.
    # Wick through 99 by <1% and close back inside.
    low[32] = 98.15
    close[32] = 99.40
    open_[32] = 100.0
    high[32] = 100.20
    candles = _ohlcv(index, close, high=high, low=low, open_=open_)
    signals = _signals("session_liquidity_sweep", candles)
    for column in ("signal", "side", "score", "reason", "range_high", "range_low"):
        assert column in signals.columns
    assert int(signals["signal"].iloc[0]) == 0
    assert int(signals["signal"].iloc[7]) == 0
    assert int(signals["signal"].iloc[32]) == 1
    assert int((signals["signal"] == 1).sum()) >= 1


def test_session_liquidity_sweep_short_entry() -> None:
    index, close, high, low, open_ = _asian_box_day()
    high[32] = 101.85
    close[32] = 100.60
    open_[32] = 100.0
    low[32] = 99.80
    candles = _ohlcv(index, close, high=high, low=low, open_=open_)
    signals = _signals("session_liquidity_sweep", candles, side=SignalSide.SHORT)
    assert int(signals["signal"].iloc[0]) == 0
    assert int(signals["signal"].iloc[32]) == -1
    assert int((signals["signal"] == -1).sum()) >= 1


def test_session_liquidity_sweep_ignores_real_breakout() -> None:
    """A poke of more than 1% is a break, not a failed sweep — do not fade it."""
    index, close, high, low, open_ = _asian_box_day()
    low[32] = 97.00
    close[32] = 99.40
    open_[32] = 100.0
    high[32] = 100.20
    candles = _ohlcv(index, close, high=high, low=low, open_=open_)
    signals = _signals("session_liquidity_sweep", candles)
    assert int(signals["signal"].iloc[32]) == 0


def _quiet_vwap_tape(n: int = 80) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Flat tape with a small close-vs-bar-VWAP residual so the |pulse| baseline is nonzero."""
    close = np.full(n, 100.0)
    high = close + 1.0
    low = close - 1.0
    open_ = np.full(n, 99.8)
    volume = np.full(n, 1_000.0)
    # turnover a hair under volume*close → tiny positive pulse, baseline stays finite.
    return close, high, low, open_, volume


def test_bar_vwap_inflow_surge_schema_and_long_entry() -> None:
    n = 80
    close, high, low, open_, volume = _quiet_vwap_tape(n)
    turnover = volume * 99.5
    # Surge bar: close well above bar VWAP, same-direction body, heavy volume.
    close[60] = 110.0
    open_[60] = 100.0
    high[60] = 111.0
    low[60] = 99.5
    volume[60] = 8_000.0
    turnover[60] = 8_000.0 * 100.0
    candles = _ohlcv(_hourly(n), close, high=high, low=low, open_=open_)
    candles["volume"] = volume
    candles["turnover"] = turnover
    assert "turnover" in candles.columns
    signals = _signals("bar_vwap_inflow_surge", candles)
    for column in ("signal", "side", "score", "reason", "bar_vwap", "pulse", "surge"):
        assert column in signals.columns
    assert int(signals["signal"].iloc[0]) == 0
    assert int(signals["signal"].iloc[60]) == 1
    assert int((signals["signal"] == 1).sum()) >= 1
    assert signals["bar_vwap"].iloc[60] == pytest.approx(turnover[60] / volume[60])


def test_bar_vwap_inflow_surge_short_entry() -> None:
    n = 80
    close, high, low, open_, volume = _quiet_vwap_tape(n)
    turnover = volume * 100.5
    close[60] = 90.0
    open_[60] = 100.0
    high[60] = 100.5
    low[60] = 89.0
    volume[60] = 8_000.0
    turnover[60] = 8_000.0 * 100.0
    candles = _ohlcv(_hourly(n), close, high=high, low=low, open_=open_)
    candles["volume"] = volume
    candles["turnover"] = turnover
    signals = _signals("bar_vwap_inflow_surge", candles, side=SignalSide.SHORT)
    assert int(signals["signal"].iloc[0]) == 0
    assert int(signals["signal"].iloc[60]) == -1
    assert int((signals["signal"] == -1).sum()) >= 1
    assert signals["bar_vwap"].iloc[60] == pytest.approx(turnover[60] / volume[60])


def test_bar_vwap_inflow_surge_reads_turnover() -> None:
    """The sleeve must consume the unused turnover column, not invent a feed."""
    n = 80
    close, high, low, open_, volume = _quiet_vwap_tape(n)
    turnover = volume * 99.5
    close[60] = 110.0
    open_[60] = 100.0
    high[60] = 111.0
    low[60] = 99.5
    volume[60] = 8_000.0
    turnover[60] = 8_000.0 * 100.0
    candles = _ohlcv(_hourly(n), close, high=high, low=low, open_=open_)
    candles["volume"] = volume
    candles["turnover"] = turnover
    from research.validate import strategy_kit

    factory, base, _space = strategy_kit("bar_vwap_inflow_surge", SignalSide.LONG)
    sleeve = factory(base)
    with pytest.raises(ValueError, match="turnover"):
        sleeve.generate_signals(candles.drop(columns=["turnover"]))
    fired = sleeve.generate_signals(candles)
    assert int(fired["signal"].iloc[60]) == 1
    # Neutralise the print: turnover = volume * close → pulse 0, surge gone.
    muted = candles.copy()
    muted.loc[muted.index[60], "turnover"] = volume[60] * close[60]
    quiet = sleeve.generate_signals(muted)
    assert int(quiet["signal"].iloc[60]) == 0
    assert fired["bar_vwap"].iloc[60] == pytest.approx(turnover[60] / volume[60])


def _impulse_then_retrace(
    *,
    long_side: bool,
    n: int = 80,
    origin: float = 80.0,
    extreme: float = 120.0,
    swing_a: int = 10,
    swing_b: int = 25,
    bounce: int = 36,
) -> pd.DataFrame:
    """Plant two confirmed swings (left=3) and a 0.618 tag that closes back through.

    Background highs and lows are strictly increasing so `confirmed_swings`
    cannot mint a later 101/99 pivot that overwrites the impulse. The origin
    low sits more than 20 bars before the bounce so a Donchian-20 0.618 is
    a different number than the two-swing 0.618.
    """
    drift = 0.01 * np.arange(n)
    close = 100.0 + drift
    high = 101.0 + drift
    low = 99.0 + drift
    open_ = 100.0 + drift
    if long_side:
        # Only the origin low and impulse high are planted; the other side of
        # those bars stays on the rising background so it cannot become a pivot.
        low[swing_a] = origin
        close[swing_a] = min(close[swing_a], origin + 1.0)
        high[swing_b] = extreme
        close[swing_b] = extreme - 2.0
        level = extreme - 0.618 * (extreme - origin)
        low[bounce] = level - 0.8
        high[bounce] = level + 2.0
        close[bounce] = level + 1.2
        open_[bounce] = level - 0.2
    else:
        high[swing_a] = extreme
        close[swing_a] = extreme - 2.0
        low[swing_b] = origin
        close[swing_b] = origin + 2.0
        level = origin + 0.618 * (extreme - origin)
        high[bounce] = level + 0.8
        low[bounce] = level - 2.0
        close[bounce] = level - 1.2
        open_[bounce] = level + 0.2
    return _ohlcv(_hourly(n), close, high=high, low=low, open_=open_)


def test_fib_retracement_bounce_schema_and_long_entry() -> None:
    candles = _impulse_then_retrace(long_side=True)
    signals = _signals("fib_retracement_bounce", candles)
    for column in ("signal", "side", "score", "reason", "swing_high", "swing_low", "fib_level"):
        assert column in signals.columns
    assert int(signals["signal"].iloc[0]) == 0
    assert int((signals["signal"] == 1).sum()) >= 1


def test_fib_retracement_bounce_short_entry() -> None:
    candles = _impulse_then_retrace(long_side=False)
    signals = _signals("fib_retracement_bounce", candles, side=SignalSide.SHORT)
    assert int(signals["signal"].iloc[0]) == 0
    assert int((signals["signal"] == -1).sum()) >= 1


def test_fib_retracement_bounce_level_from_confirmed_swings_not_donchian() -> None:
    """0.618 is two confirmed swings, not a Donchian channel retrace."""
    from core.strategy import indicators as ind

    candles = _impulse_then_retrace(long_side=True)
    signals = _signals("fib_retracement_bounce", candles)
    fired = signals.index[signals["signal"] == 1]
    assert len(fired) >= 1
    bar = fired[0]
    swing_high, swing_low = ind.confirmed_swings(candles["high"], candles["low"], left=3)
    expected = swing_high.loc[bar] - 0.618 * (swing_high.loc[bar] - swing_low.loc[bar])
    assert signals.loc[bar, "fib_level"] == pytest.approx(float(expected))
    assert signals.loc[bar, "swing_high"] == pytest.approx(float(swing_high.loc[bar]))
    assert signals.loc[bar, "swing_low"] == pytest.approx(float(swing_low.loc[bar]))
    # Donchian 20 ending at this bar does not contain the origin low (bar 10).
    prior = slice(None, bar)
    donchian_high = candles.loc[prior, "high"].iloc[-20:].max()
    donchian_low = candles.loc[prior, "low"].iloc[-20:].min()
    donchian_618 = donchian_high - 0.618 * (donchian_high - donchian_low)
    assert signals.loc[bar, "fib_level"] != pytest.approx(float(donchian_618), abs=0.2)
    assert swing_low.loc[bar] == pytest.approx(80.0)
    assert swing_high.loc[bar] == pytest.approx(120.0)


def _impulse_then_extension(
    *,
    long_side: bool,
    n: int = 80,
    origin: float = 80.0,
    extreme: float = 120.0,
    swing_a: int = 10,
    swing_b: int = 25,
    break_bar: int = 40,
) -> pd.DataFrame:
    """Plant two confirmed swings (left=3) then a 1.618 extension break.

    Background highs and lows are strictly increasing so `confirmed_swings`
    cannot mint a later 101/99 pivot that overwrites the impulse. The origin
    sits more than 20 bars before the break so a Donchian-20 1.618 is a
    different number than the two-swing extension.
    """
    drift = 0.01 * np.arange(n)
    close = 100.0 + drift
    high = 101.0 + drift
    low = 99.0 + drift
    open_ = 100.0 + drift
    rng = extreme - origin
    if long_side:
        # Origin low then impulse high; break is H + 0.618*R, not a 0.618 bounce.
        low[swing_a] = origin
        close[swing_a] = min(close[swing_a], origin + 1.0)
        high[swing_b] = extreme
        close[swing_b] = extreme - 2.0
        ext = extreme + 0.618 * rng
        close[break_bar] = ext + 5.0
        high[break_bar] = ext + 6.0
        low[break_bar] = ext + 3.0
        open_[break_bar] = ext + 1.0
    else:
        high[swing_a] = extreme
        close[swing_a] = extreme - 2.0
        low[swing_b] = origin
        close[swing_b] = origin + 2.0
        ext = origin - 0.618 * rng
        close[break_bar] = ext - 5.0
        high[break_bar] = ext - 3.0
        low[break_bar] = ext - 6.0
        open_[break_bar] = ext - 1.0
    return _ohlcv(_hourly(n), close, high=high, low=low, open_=open_)


def test_fib_extension_break_schema_and_long_entry() -> None:
    candles = _impulse_then_extension(long_side=True)
    signals = _signals("fib_extension_break", candles)
    for column in ("signal", "side", "score", "reason", "swing_high", "swing_low", "fib_ext"):
        assert column in signals.columns
    assert int(signals["signal"].iloc[0]) == 0
    assert int((signals["signal"] == 1).sum()) >= 1
    assert int((signals["signal"] == -1).sum()) == 0


def test_fib_extension_break_short_entry() -> None:
    candles = _impulse_then_extension(long_side=False)
    signals = _signals("fib_extension_break", candles, side=SignalSide.SHORT)
    assert int(signals["signal"].iloc[0]) == 0
    assert int((signals["signal"] == -1).sum()) >= 1
    assert int((signals["signal"] == 1).sum()) == 0


def test_fib_extension_break_skip_bull_suppresses_short_on_bull_bars() -> None:
    """skip_bull=True drops SHORT entries on bull bars; default False keeps them."""
    from core.strategy.fib_extension_break import (
        FibExtensionBreakParams,
        FibExtensionBreakStrategy,
    )

    candles = _impulse_then_extension(long_side=False)
    candles = candles.copy()
    candles["regime"] = "bull"
    open_shorts = FibExtensionBreakStrategy(
        FibExtensionBreakParams(side=SignalSide.SHORT)
    ).generate_signals(candles)
    skipped = FibExtensionBreakStrategy(
        FibExtensionBreakParams(side=SignalSide.SHORT, skip_bull=True)
    ).generate_signals(candles)
    assert int((open_shorts["signal"] == -1).sum()) >= 1
    assert int((skipped["signal"] == -1).sum()) == 0
    # Bear bars still allow the short when skip_bull is on.
    bear = candles.copy()
    bear["regime"] = "bear"
    allowed = FibExtensionBreakStrategy(
        FibExtensionBreakParams(side=SignalSide.SHORT, skip_bull=True)
    ).generate_signals(bear)
    assert int((allowed["signal"] == -1).sum()) >= 1


def test_fib_extension_break_skip_bear_suppresses_long_on_bear_bars() -> None:
    from core.strategy.fib_extension_break import (
        FibExtensionBreakParams,
        FibExtensionBreakStrategy,
    )

    candles = _impulse_then_extension(long_side=True)
    candles = candles.copy()
    candles["regime"] = "bear"
    open_longs = FibExtensionBreakStrategy(
        FibExtensionBreakParams(side=SignalSide.LONG)
    ).generate_signals(candles)
    skipped = FibExtensionBreakStrategy(
        FibExtensionBreakParams(side=SignalSide.LONG, skip_bear=True)
    ).generate_signals(candles)
    assert int((open_longs["signal"] == 1).sum()) >= 1
    assert int((skipped["signal"] == 1).sum()) == 0


def test_fib_extension_break_1618_default_and_no_lookahead() -> None:
    """Default ratio is 1.618; skip_bull SMA fallback does not peek past t."""
    from core.strategy.fib_extension_break import (
        FibExtensionBreakParams,
        FibExtensionBreakStrategy,
        REGIME_SMA,
    )

    assert FibExtensionBreakParams().fib_ratio == 1.618
    candles = _impulse_then_extension(long_side=False, n=260, swing_a=210, swing_b=225, break_bar=240)
    sleeve = FibExtensionBreakStrategy(
        FibExtensionBreakParams(side=SignalSide.SHORT, skip_bull=True)
    )
    full = sleeve.generate_signals(candles)
    cut = 250
    truncated = sleeve.generate_signals(candles.iloc[:cut])
    pd.testing.assert_series_equal(
        full["signal"].iloc[:cut],
        truncated["signal"],
        check_names=False,
    )
    shocked = candles.copy()
    shocked.iloc[-1, shocked.columns.get_loc("close")] *= 0.5
    shocked.iloc[-1, shocked.columns.get_loc("low")] *= 0.5
    original = sleeve.generate_signals(candles)["signal"].iloc[:-1]
    after = sleeve.generate_signals(shocked)["signal"].iloc[:-1]
    pd.testing.assert_series_equal(original, after)
    # SMA(200) is causal: last-bar shock must not move the prior SMA label.
    from core.strategy import indicators as ind

    mid_full = ind.sma(candles["close"], REGIME_SMA)
    mid_shock = ind.sma(shocked["close"], REGIME_SMA)
    pd.testing.assert_series_equal(mid_full.iloc[:-1], mid_shock.iloc[:-1], check_names=False)


def test_fib_extension_break_ext_from_two_confirmed_swings() -> None:
    """ext = end + 0.618*(end-start) from two confirmed swings, not Donchian."""
    from core.strategy import indicators as ind

    candles = _impulse_then_extension(long_side=True)
    signals = _signals("fib_extension_break", candles)
    fired = signals.index[signals["signal"] == 1]
    assert len(fired) >= 1
    bar = fired[0]
    swing_high, swing_low = ind.confirmed_swings(candles["high"], candles["low"], left=3)
    start = swing_low.loc[bar]
    end = swing_high.loc[bar]
    expected = end + 0.618 * (end - start)
    assert signals.loc[bar, "fib_ext"] == pytest.approx(float(expected))
    assert signals.loc[bar, "swing_high"] == pytest.approx(float(end))
    assert signals.loc[bar, "swing_low"] == pytest.approx(float(start))
    assert signals.loc[bar, "last_event"] == pytest.approx(1.0)
    # Donchian 20 ending at this bar does not contain the origin low (bar 10).
    prior = slice(None, bar)
    donchian_high = candles.loc[prior, "high"].iloc[-20:].max()
    donchian_low = candles.loc[prior, "low"].iloc[-20:].min()
    donchian_ext = donchian_high + 0.618 * (donchian_high - donchian_low)
    assert signals.loc[bar, "fib_ext"] != pytest.approx(float(donchian_ext), abs=0.2)
    assert start == pytest.approx(80.0)
    assert end == pytest.approx(120.0)
    # 1.272 is the inner zone start of this family, not a 0.618 retracement bounce.
    inner = end + 0.272 * (end - start)
    assert signals.loc[bar, "fib_inner"] == pytest.approx(float(inner))
    bounce_618 = end - 0.618 * (end - start)
    assert signals.loc[bar, "fib_ext"] != pytest.approx(float(bounce_618), abs=0.2)


def _impulse_then_measured_move(
    *,
    long_side: bool,
    n: int = 80,
    origin: float = 80.0,
    extreme: float = 120.0,
    swing_a: int = 10,
    swing_b: int = 25,
    break_bar: int = 40,
) -> pd.DataFrame:
    """Plant two confirmed swings (left=3) then a 100% measured-move break.

    Background highs and lows are strictly increasing so `confirmed_swings`
    cannot mint a later 101/99 pivot that overwrites the impulse. The origin
    sits more than 20 bars before the break so a Donchian-20 AB=CD is a
    different number than the two-swing measured move. The break is past
    2*end-start, which is also past H+0.618*R (fib_extension_break).
    """
    drift = 0.01 * np.arange(n)
    close = 100.0 + drift
    high = 101.0 + drift
    low = 99.0 + drift
    open_ = 100.0 + drift
    rng = extreme - origin
    if long_side:
        # Origin low then impulse high; break is 2H-L, not H+0.618*R.
        low[swing_a] = origin
        close[swing_a] = min(close[swing_a], origin + 1.0)
        high[swing_b] = extreme
        close[swing_b] = extreme - 2.0
        mm = extreme + 1.0 * rng
        close[break_bar] = mm + 5.0
        high[break_bar] = mm + 6.0
        low[break_bar] = mm + 3.0
        open_[break_bar] = mm + 1.0
    else:
        high[swing_a] = extreme
        close[swing_a] = extreme - 2.0
        low[swing_b] = origin
        close[swing_b] = origin + 2.0
        mm = origin - 1.0 * rng
        close[break_bar] = mm - 5.0
        high[break_bar] = mm - 3.0
        low[break_bar] = mm - 6.0
        open_[break_bar] = mm - 1.0
    return _ohlcv(_hourly(n), close, high=high, low=low, open_=open_)


def test_measured_move_break_schema_and_long_entry() -> None:
    candles = _impulse_then_measured_move(long_side=True)
    signals = _signals("measured_move_break", candles)
    for column in ("signal", "side", "score", "reason", "swing_high", "swing_low", "mm"):
        assert column in signals.columns
    assert int(signals["signal"].iloc[0]) == 0
    assert int((signals["signal"] == 1).sum()) >= 1
    assert int((signals["signal"] == -1).sum()) == 0


def test_measured_move_break_short_entry() -> None:
    candles = _impulse_then_measured_move(long_side=False)
    signals = _signals("measured_move_break", candles, side=SignalSide.SHORT)
    assert int(signals["signal"].iloc[0]) == 0
    assert int((signals["signal"] == -1).sum()) >= 1
    assert int((signals["signal"] == 1).sum()) == 0


def test_measured_move_break_mm_from_two_confirmed_swings() -> None:
    """mm = end + 1.0*(end-start) from two confirmed swings, not Donchian, not 0.618R."""
    from core.strategy import indicators as ind

    candles = _impulse_then_measured_move(long_side=True)
    signals = _signals("measured_move_break", candles)
    fired = signals.index[signals["signal"] == 1]
    assert len(fired) >= 1
    bar = fired[0]
    swing_high, swing_low = ind.confirmed_swings(candles["high"], candles["low"], left=3)
    start = swing_low.loc[bar]
    end = swing_high.loc[bar]
    expected = end + 1.0 * (end - start)
    assert signals.loc[bar, "mm"] == pytest.approx(float(expected))
    assert signals.loc[bar, "swing_high"] == pytest.approx(float(end))
    assert signals.loc[bar, "swing_low"] == pytest.approx(float(start))
    assert signals.loc[bar, "last_event"] == pytest.approx(1.0)
    # Donchian 20 ending at this bar does not contain the origin low (bar 10).
    prior = slice(None, bar)
    donchian_high = candles.loc[prior, "high"].iloc[-20:].max()
    donchian_low = candles.loc[prior, "low"].iloc[-20:].min()
    donchian_mm = donchian_high + 1.0 * (donchian_high - donchian_low)
    assert signals.loc[bar, "mm"] != pytest.approx(float(donchian_mm), abs=0.2)
    assert start == pytest.approx(80.0)
    assert end == pytest.approx(120.0)
    # Not the 1.618 extension of the same impulse (H + 0.618*R).
    fib_1618 = end + 0.618 * (end - start)
    assert signals.loc[bar, "mm"] != pytest.approx(float(fib_1618), abs=0.2)
    assert expected == pytest.approx(160.0)


def test_measured_move_break_ratio_locked_at_one() -> None:
    """Walk-forward kit must not hunt 1.618 / 0.618 or skip_bull on this family."""
    from core.strategy.measured_move_break import MM_RATIO
    from research.validate import strategy_kit

    assert MM_RATIO == 1.0
    _factory, _base, space = strategy_kit("measured_move_break", SignalSide.LONG)
    assert "fib_ratio" not in space
    assert "mm_ratio" not in space
    assert "skip_bull" not in space
    assert "skip_bear" not in space
    assert 1.618 not in space.get("take_profit_pct", [])
    assert 0.618 not in space.get("take_profit_pct", [])


def _zigzag_turnover(
    n: int = 80,
    *,
    up_mult: float = 1.0,
    down_mult: float = 1.0,
) -> pd.DataFrame:
    """Oscillating close so up-bars and down-bars both exist.

    Close 100, 101, 100, 101… keeps the price path identical while tests
    reallocate turnover. A close-only oscillator cannot change side.
    """
    close = np.where(np.arange(n) % 2 == 0, 100.0, 101.0)
    high = close + 0.4
    low = close - 0.4
    open_ = np.concatenate([[100.0], close[:-1]])
    candles = _ohlcv(_hourly(n), close, high=high, low=low, open_=open_)
    up = close > np.concatenate([[close[0]], close[:-1]])
    down = close < np.concatenate([[close[0]], close[:-1]])
    turnover = np.full(n, 1_000.0)
    turnover[up] *= up_mult
    turnover[down] *= down_mult
    candles["turnover"] = turnover
    return candles


def test_up_down_turnover_imbalance_schema_and_long_entry() -> None:
    candles = _zigzag_turnover(up_mult=12.0, down_mult=1.0)
    signals = _signals("up_down_turnover_imbalance", candles)
    for column in ("signal", "side", "score", "reason", "imbalance", "up_turnover", "down_turnover"):
        assert column in signals.columns
    assert int(signals["signal"].iloc[0]) == 0
    assert int((signals["signal"] == 1).sum()) >= 1
    assert int((signals["signal"] == -1).sum()) == 0


def test_up_down_turnover_imbalance_short_entry() -> None:
    candles = _zigzag_turnover(up_mult=1.0, down_mult=12.0)
    signals = _signals("up_down_turnover_imbalance", candles, side=SignalSide.SHORT)
    assert int(signals["signal"].iloc[0]) == 0
    assert int((signals["signal"] == -1).sum()) >= 1
    assert int((signals["signal"] == 1).sum()) == 0


def test_up_down_turnover_imbalance_reads_turnover_not_close_only() -> None:
    """Same zigzag closes: only turnover allocation flips the side."""
    from research.validate import strategy_kit

    up_heavy = _zigzag_turnover(up_mult=12.0, down_mult=1.0)
    down_heavy = _zigzag_turnover(up_mult=1.0, down_mult=12.0)
    factory, base, _space = strategy_kit("up_down_turnover_imbalance", SignalSide.LONG)
    sleeve = factory(base)
    with pytest.raises(ValueError, match="turnover"):
        sleeve.generate_signals(up_heavy.drop(columns=["turnover"]))
    longs = sleeve.generate_signals(up_heavy)
    quiet = sleeve.generate_signals(down_heavy)
    assert int((longs["signal"] == 1).sum()) >= 1
    assert int((quiet["signal"] == 1).sum()) == 0
    short_factory, short_base, _ = strategy_kit(
        "up_down_turnover_imbalance", SignalSide.SHORT
    )
    shorts = short_factory(short_base).generate_signals(down_heavy)
    assert int((shorts["signal"] == -1).sum()) >= 1
    # Equal turnover on the same path is a wash — no follow-the-money edge.
    even = _zigzag_turnover(up_mult=1.0, down_mult=1.0)
    flat = sleeve.generate_signals(even)
    assert int((flat["signal"] == 1).sum()) == 0


def _signed_range_tape(
    n: int = 80,
    *,
    body: float = 0.2,
    burst_body: float = 6.0,
    burst_turnover: float = 20_000.0,
    burst_start: int = 50,
) -> pd.DataFrame:
    """Quiet small bodies, then a same-sign body burst with heavy turnover."""
    close = np.full(n, 100.0)
    open_ = np.full(n, 100.0 - body)
    high = close + 0.5
    low = open_ - 0.5
    volume = np.full(n, 1_000.0)
    turnover = volume * 100.0
    close[burst_start:] = 100.0 + burst_body
    open_[burst_start:] = 100.0
    high[burst_start:] = close[burst_start:] + 0.5
    low[burst_start:] = open_[burst_start:] - 0.5
    volume[burst_start:] = 2_000.0
    turnover[burst_start:] = burst_turnover
    candles = _ohlcv(_hourly(n), close, high=high, low=low, open_=open_)
    candles["volume"] = volume
    candles["turnover"] = turnover
    return candles


def test_signed_range_turnover_trend_schema_and_long_entry() -> None:
    candles = _signed_range_tape()
    signals = _signals("signed_range_turnover_trend", candles)
    for column in ("signal", "side", "score", "reason", "signed_range", "pulse", "trend"):
        assert column in signals.columns
    assert int(signals["signal"].iloc[0]) == 0
    assert int((signals["signal"] == 1).sum()) >= 1
    assert int((signals["signal"] == -1).sum()) == 0


def test_signed_range_turnover_trend_short_entry() -> None:
    candles = _signed_range_tape(body=-0.2, burst_body=-6.0)
    signals = _signals("signed_range_turnover_trend", candles, side=SignalSide.SHORT)
    assert int(signals["signal"].iloc[0]) == 0
    assert int((signals["signal"] == -1).sum()) >= 1
    assert int((signals["signal"] == 1).sum()) == 0


def test_signed_range_turnover_trend_not_ema_adx_clone() -> None:
    """Rising closes with red bodies go SHORT — EMA of close would stay long."""
    from research.validate import strategy_kit

    n = 80
    close = np.linspace(90.0, 130.0, n)
    # Quiet red bodies, then a heavy red burst. Close still rises, so an
    # EMA-of-close trend would stay long; this family must go short.
    open_ = close + 0.3
    open_[50:] = close[50:] + 6.0
    high = open_ + 0.3
    low = close - 0.3
    candles = _ohlcv(_hourly(n), close, high=high, low=low, open_=open_)
    turnover = np.full(n, 1_000.0)
    turnover[50:] = 20_000.0
    candles["turnover"] = turnover
    long_factory, long_base, space = strategy_kit(
        "signed_range_turnover_trend", SignalSide.LONG
    )
    assert "ema_fast" not in space
    assert "min_adx" not in space
    longs = long_factory(long_base).generate_signals(candles)
    assert int((longs["signal"] == 1).sum()) == 0
    shorts = _signals("signed_range_turnover_trend", candles, side=SignalSide.SHORT)
    assert int((shorts["signal"] == -1).sum()) >= 1
    with pytest.raises(ValueError, match="turnover"):
        long_factory(long_base).generate_signals(candles.drop(columns=["turnover"]))
    # Same bodies, tiny turnover: participation is gone, trend stays asleep.
    muted = candles.copy()
    muted["turnover"] = 1.0
    quiet = long_factory(long_base).generate_signals(muted)
    assert int((quiet["signal"] == 1).sum()) == 0


def _impulse_then_avwap_pullback(
    *,
    long_side: bool,
    n: int = 80,
    origin: float = 80.0,
    extreme: float = 120.0,
    swing_a: int = 10,
    swing_b: int = 25,
    pullback: int = 40,
) -> pd.DataFrame:
    """Plant two confirmed swings (left=3) then a pullback through AVWAP.

    Background highs and lows are strictly increasing so `confirmed_swings`
    cannot mint a later 101/99 pivot that overwrites the impulse. The
    pullback tags a band wide enough to cross any AVWAP between origin
    and extreme, which is also away from the 0.618 fib and the 1.618 ext.
    """
    drift = 0.01 * np.arange(n)
    close = 100.0 + drift
    high = 101.0 + drift
    low = 99.0 + drift
    open_ = 100.0 + drift
    if long_side:
        low[swing_a] = origin
        close[swing_a] = min(close[swing_a], origin + 1.0)
        high[swing_b] = extreme
        close[swing_b] = extreme - 2.0
        # Deep enough to tag AVWAP (~100) but not the origin (80).
        low[pullback] = 92.0
        high[pullback] = 108.0
        close[pullback] = 106.0
        open_[pullback] = 94.0
    else:
        high[swing_a] = extreme
        close[swing_a] = extreme - 2.0
        low[swing_b] = origin
        close[swing_b] = origin + 2.0
        high[pullback] = 108.0
        low[pullback] = 92.0
        close[pullback] = 94.0
        open_[pullback] = 106.0
    return _ohlcv(_hourly(n), close, high=high, low=low, open_=open_)


def test_swing_anchored_vwap_pullback_schema_and_long_entry() -> None:
    candles = _impulse_then_avwap_pullback(long_side=True)
    signals = _signals("swing_anchored_vwap_pullback", candles)
    for column in ("signal", "side", "score", "reason", "swing_high", "swing_low", "avwap"):
        assert column in signals.columns
    assert int(signals["signal"].iloc[0]) == 0
    assert int((signals["signal"] == 1).sum()) >= 1
    assert int((signals["signal"] == -1).sum()) == 0


def test_swing_anchored_vwap_pullback_short_entry() -> None:
    candles = _impulse_then_avwap_pullback(long_side=False)
    signals = _signals("swing_anchored_vwap_pullback", candles, side=SignalSide.SHORT)
    assert int(signals["signal"].iloc[0]) == 0
    assert int((signals["signal"] == -1).sum()) >= 1
    assert int((signals["signal"] == 1).sum()) == 0


def test_swing_anchored_vwap_pullback_from_confirmed_swings_not_fib() -> None:
    """AVWAP is Σturnover/Σvolume from the origin swing, not 0.618 or 1.618."""
    from core.strategy import indicators as ind

    candles = _impulse_then_avwap_pullback(long_side=True)
    signals = _signals("swing_anchored_vwap_pullback", candles)
    fired = signals.index[signals["signal"] == 1]
    assert len(fired) >= 1
    bar = fired[0]
    swing_high, swing_low = ind.confirmed_swings(candles["high"], candles["low"], left=3)
    start = swing_low.loc[bar]
    end = swing_high.loc[bar]
    low_changed = swing_low.notna() & swing_low.ne(swing_low.shift(1))
    era = low_changed.astype("int64").cumsum()
    expected = (
        candles["turnover"].groupby(era).cumsum()
        / candles["volume"].groupby(era).cumsum()
    )
    assert signals.loc[bar, "avwap"] == pytest.approx(float(expected.loc[bar]))
    assert signals.loc[bar, "swing_high"] == pytest.approx(float(end))
    assert signals.loc[bar, "swing_low"] == pytest.approx(float(start))
    assert signals.loc[bar, "last_event"] == pytest.approx(1.0)
    assert start == pytest.approx(80.0)
    assert end == pytest.approx(120.0)
    fib_618 = end - 0.618 * (end - start)
    fib_1618 = end + 0.618 * (end - start)
    assert signals.loc[bar, "avwap"] != pytest.approx(float(fib_618), abs=0.2)
    assert signals.loc[bar, "avwap"] != pytest.approx(float(fib_1618), abs=0.2)
    with pytest.raises(ValueError, match="turnover"):
        from research.validate import strategy_kit

        factory, base, space = strategy_kit("swing_anchored_vwap_pullback", SignalSide.LONG)
        assert "fib_ratio" not in space
        factory(base).generate_signals(candles.drop(columns=["turnover"]))


def _weekend_then_monday(n: int = 80) -> tuple[pd.DatetimeIndex, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Sat–Sun 99–101 box starting 2024-01-06, then Monday room to sweep it."""
    index = _hourly(n, start="2024-01-06")
    close = np.full(n, 100.0)
    high = np.full(n, 101.0)
    low = np.full(n, 99.0)
    open_ = np.full(n, 100.0)
    return index, close, high, low, open_


def _monday_london_iloc(index: pd.DatetimeIndex) -> int:
    stamp = pd.Timestamp("2024-01-08 08:00", tz="UTC")
    return int(index.get_loc(stamp))


def test_monday_range_sweep_reversal_schema_and_long_entry() -> None:
    index, close, high, low, open_ = _weekend_then_monday()
    bar = _monday_london_iloc(index)
    # Monday 08:00 London: wick through 99 by <1.5% and close back inside.
    low[bar] = 97.70
    close[bar] = 99.40
    open_[bar] = 100.0
    high[bar] = 100.20
    candles = _ohlcv(index, close, high=high, low=low, open_=open_)
    signals = _signals("monday_range_sweep_reversal", candles)
    for column in (
        "signal",
        "side",
        "score",
        "reason",
        "range_high",
        "range_low",
        "weekend_mid",
    ):
        assert column in signals.columns
    assert int(signals["signal"].iloc[0]) == 0
    assert int(signals["signal"].iloc[bar]) == 1
    assert int((signals["signal"] == 1).sum()) >= 1
    assert signals.loc[index[bar], "weekend_mid"] == pytest.approx(100.0)


def test_monday_range_sweep_reversal_short_entry() -> None:
    index, close, high, low, open_ = _weekend_then_monday()
    bar = _monday_london_iloc(index)
    high[bar] = 102.30
    close[bar] = 100.60
    open_[bar] = 100.0
    low[bar] = 99.80
    candles = _ohlcv(index, close, high=high, low=low, open_=open_)
    signals = _signals("monday_range_sweep_reversal", candles, side=SignalSide.SHORT)
    assert int(signals["signal"].iloc[0]) == 0
    assert int(signals["signal"].iloc[bar]) == -1
    assert int((signals["signal"] == -1).sum()) >= 1


def test_monday_range_sweep_reversal_ignores_real_breakout() -> None:
    """A poke of more than 1.5% is a break, not a failed sweep — do not fade it."""
    index, close, high, low, open_ = _weekend_then_monday()
    bar = _monday_london_iloc(index)
    low[bar] = 96.00
    close[bar] = 99.40
    open_[bar] = 100.0
    high[bar] = 100.20
    candles = _ohlcv(index, close, high=high, low=low, open_=open_)
    signals = _signals("monday_range_sweep_reversal", candles)
    assert int(signals["signal"].iloc[bar]) == 0


def test_monday_range_sweep_reversal_ignores_asian_monday_hour() -> None:
    """Monday 00:00–08:00 is not the trade window. That is session_liquidity_sweep."""
    index, close, high, low, open_ = _weekend_then_monday()
    asian = int(index.get_loc(pd.Timestamp("2024-01-08 02:00", tz="UTC")))
    low[asian] = 97.70
    close[asian] = 99.40
    open_[asian] = 100.0
    high[asian] = 100.20
    candles = _ohlcv(index, close, high=high, low=low, open_=open_)
    signals = _signals("monday_range_sweep_reversal", candles)
    assert int(signals["signal"].iloc[asian]) == 0


def test_monday_range_sweep_reversal_calendar_weekend_not_asian_box() -> None:
    """Range is Sat–Sun, not the 00:00–08:00 Asian box of the same Monday."""
    index, close, high, low, open_ = _weekend_then_monday()
    # Widen Saturday so the weekend high is 105, not the default 101.
    sat = int(index.get_loc(pd.Timestamp("2024-01-06 12:00", tz="UTC")))
    high[sat] = 105.0
    close[sat] = 104.0
    bar = _monday_london_iloc(index)
    high[bar] = 106.40
    close[bar] = 104.20
    open_[bar] = 100.0
    low[bar] = 100.00
    candles = _ohlcv(index, close, high=high, low=low, open_=open_)
    signals = _signals("monday_range_sweep_reversal", candles, side=SignalSide.SHORT)
    assert signals.loc[index[bar], "range_high"] == pytest.approx(105.0)
    assert int(signals["signal"].iloc[bar]) == -1
    # Asian 00–08 Monday box would still be ~101; fading that would be the dead family.
    assert signals.loc[index[bar], "range_high"] != pytest.approx(101.0)


def _imbalance_tape(n: int = 60) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    close = np.full(n, 100.0)
    high = np.full(n, 101.0)
    low = np.full(n, 99.0)
    open_ = np.full(n, 100.0)
    return close, high, low, open_


def test_volume_imbalance_delta_reversal_schema_and_long_entry() -> None:
    n = 60
    close, high, low, open_ = _imbalance_tape(n)
    # New 20-bar low; close near the high → selling share = 0.10 < 0.20.
    low[50] = 90.0
    high[50] = 100.0
    close[50] = 99.0
    open_[50] = 100.0
    candles = _ohlcv(_hourly(n), close, high=high, low=low, open_=open_)
    signals = _signals("volume_imbalance_delta_reversal", candles)
    for column in ("signal", "side", "score", "reason", "buy_share", "sell_share", "ema"):
        assert column in signals.columns
    assert int(signals["signal"].iloc[0]) == 0
    assert int(signals["signal"].iloc[50]) == 1
    assert int((signals["signal"] == 1).sum()) >= 1
    assert signals["buy_share"].iloc[50] == pytest.approx(0.90)
    assert signals["sell_share"].iloc[50] == pytest.approx(0.10)


def test_volume_imbalance_delta_reversal_short_entry() -> None:
    n = 60
    close, high, low, open_ = _imbalance_tape(n)
    # New 20-bar high; close near the low → buying share = 0.10 < 0.20.
    high[50] = 110.0
    low[50] = 100.0
    close[50] = 101.0
    open_[50] = 100.0
    candles = _ohlcv(_hourly(n), close, high=high, low=low, open_=open_)
    signals = _signals("volume_imbalance_delta_reversal", candles, side=SignalSide.SHORT)
    assert int(signals["signal"].iloc[0]) == 0
    assert int(signals["signal"].iloc[50]) == -1
    assert int((signals["signal"] == -1).sum()) >= 1
    assert signals["buy_share"].iloc[50] == pytest.approx(0.10)


def test_volume_imbalance_delta_reversal_requires_exhaustion() -> None:
    """A new high with healthy buying share is not a fade."""
    n = 60
    close, high, low, open_ = _imbalance_tape(n)
    high[50] = 110.0
    low[50] = 100.0
    close[50] = 109.0
    open_[50] = 100.0
    candles = _ohlcv(_hourly(n), close, high=high, low=low, open_=open_)
    signals = _signals("volume_imbalance_delta_reversal", candles, side=SignalSide.SHORT)
    assert signals["buy_share"].iloc[50] == pytest.approx(0.90)
    assert int(signals["signal"].iloc[50]) == 0


def test_volume_imbalance_delta_reversal_is_bar_level_not_cumsum() -> None:
    """buy_share is this bar only. A prior heavy-buy print must not leak in."""
    n = 60
    close, high, low, open_ = _imbalance_tape(n)
    # Prior bar looks like strong buying; current bar is the exhausted high.
    high[49] = 101.0
    low[49] = 99.0
    close[49] = 100.9
    high[50] = 110.0
    low[50] = 100.0
    close[50] = 101.0
    candles = _ohlcv(_hourly(n), close, high=high, low=low, open_=open_)
    signals = _signals("volume_imbalance_delta_reversal", candles, side=SignalSide.SHORT)
    assert signals["buy_share"].iloc[50] == pytest.approx(0.10)
    assert signals["buy_share"].iloc[49] == pytest.approx((100.9 - 99.0) / 2.0)
    assert int(signals["signal"].iloc[50]) == -1
    # Cumulative CLV would mix bar 49 into bar 50; this sleeve must not.
    assert "volume_force" not in signals.columns


def test_williams_fractal_break_long_entry() -> None:
    n = 24
    close = np.full(n, 100.0)
    high = np.full(n, 101.0)
    low = np.full(n, 99.0)
    high[8] = 110.0
    high[6] = 104.0
    high[7] = 105.0
    high[9] = 105.0
    high[10] = 104.0
    close[14] = 112.0
    high[14] = 113.0
    candles = _ohlcv(_hourly(n), close, high=high, low=low)
    signals = _signals("williams_fractal_break", candles)
    assert int((signals["signal"] == 1).sum()) >= 1


def test_prior_week_break_long() -> None:
    n = 24 * 10
    index = _hourly(n, start="2024-01-01")
    close = np.full(n, 100.0)
    high = np.full(n, 101.0)
    low = np.full(n, 99.0)
    # Second week starts 2024-01-08.
    second_monday = int(np.argmax(index.normalize() == pd.Timestamp("2024-01-08", tz="UTC")))
    close[second_monday] = 120.0
    high[second_monday] = 121.0
    candles = _ohlcv(index, close, high=high, low=low)
    signals = _signals("prior_week_high_break", candles)
    assert int(signals["signal"].iloc[second_monday]) == 1


def test_failed_lower_low_long() -> None:
    n = 48
    close = np.full(n, 100.0)
    high = np.full(n, 102.0)
    low = np.full(n, 98.0)
    low[10] = 90.0
    high[10] = 100.0
    close[10] = 99.0
    low[24] = 84.0
    high[24] = 100.0
    close[24] = 96.0
    close[30] = 97.0
    high[30] = 101.0
    low[30] = 95.0
    candles = _ohlcv(_hourly(n), close, high=high, low=low)
    signals = _signals("failed_higher_high", candles)
    assert int((signals["signal"] == 1).sum()) >= 1


def _utc_day_box_tape(n: int = 72) -> tuple[pd.DatetimeIndex, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Two UTC days. Day 0 plants H=110 / L=90 / last close=90 so floor R1≠H."""
    index = _hourly(n, start="2024-01-02")
    close = np.full(n, 100.0)
    high = np.full(n, 101.0)
    low = np.full(n, 99.0)
    open_ = np.full(n, 100.0)
    # Prior UTC day (Jan 2) box. Close the day at the low so P/R1/S1 ≠ H/L.
    high[5] = 110.0
    close[5] = 108.0
    low[8] = 90.0
    close[23] = 90.0
    low[23] = 90.0
    high[23] = 100.0
    open_[23] = 100.0
    return index, close, high, low, open_


def _day1_sweep_iloc(index: pd.DatetimeIndex) -> int:
    return int(index.get_loc(pd.Timestamp("2024-01-03 04:00", tz="UTC")))


def test_session_boundary_volume_fade_schema_and_long_entry() -> None:
    index, close, high, low, open_ = _utc_day_box_tape()
    bar = _day1_sweep_iloc(index)
    # Weak-volume sweep of prior day low. Close stays below daily VWAP.
    low[bar] = 85.0
    close[bar] = 88.0
    open_[bar] = 95.0
    high[bar] = 96.0
    candles = _ohlcv(index, close, high=high, low=low, open_=open_)
    candles.loc[candles.index[bar], "volume"] = 100.0
    signals = _signals("session_boundary_volume_fade", candles)
    for column in ("signal", "side", "score", "reason", "prior_high", "prior_low", "daily_vwap"):
        assert column in signals.columns
    assert int(signals["signal"].iloc[0]) == 0
    assert int(signals["signal"].iloc[bar]) == 1
    assert int((signals["signal"] == 1).sum()) >= 1
    assert signals["prior_high"].iloc[bar] == pytest.approx(110.0)
    assert signals["prior_low"].iloc[bar] == pytest.approx(90.0)


def test_session_boundary_volume_fade_short_entry() -> None:
    index, close, high, low, open_ = _utc_day_box_tape()
    bar = _day1_sweep_iloc(index)
    high[bar] = 115.0
    close[bar] = 112.0
    open_[bar] = 105.0
    low[bar] = 104.0
    candles = _ohlcv(index, close, high=high, low=low, open_=open_)
    candles.loc[candles.index[bar], "volume"] = 100.0
    signals = _signals("session_boundary_volume_fade", candles, side=SignalSide.SHORT)
    assert int(signals["signal"].iloc[0]) == 0
    assert int(signals["signal"].iloc[bar]) == -1
    assert int((signals["signal"] == -1).sum()) >= 1


def test_session_boundary_volume_fade_requires_weak_volume() -> None:
    """A high-volume sweep of the UTC day box is not this fade."""
    index, close, high, low, open_ = _utc_day_box_tape()
    bar = _day1_sweep_iloc(index)
    low[bar] = 85.0
    close[bar] = 88.0
    open_[bar] = 95.0
    high[bar] = 96.0
    candles = _ohlcv(index, close, high=high, low=low, open_=open_)
    candles.loc[candles.index[bar], "volume"] = 8_000.0
    signals = _signals("session_boundary_volume_fade", candles)
    assert int(signals["signal"].iloc[bar]) == 0


def test_session_boundary_volume_fade_is_day_box_not_floor_pivot() -> None:
    """Entry tags prior UTC day H/L, not P/R1/S1 of prior_day_pivot_breakout."""
    from core.strategy import indicators as ind

    index, close, high, low, open_ = _utc_day_box_tape()
    bar = _day1_sweep_iloc(index)
    low[bar] = 85.0
    close[bar] = 88.0
    open_[bar] = 95.0
    high[bar] = 96.0
    candles = _ohlcv(index, close, high=high, low=low, open_=open_)
    candles.loc[candles.index[bar], "volume"] = 100.0
    signals = _signals("session_boundary_volume_fade", candles)
    pivot, r1, s1 = ind.prior_day_floor_pivots(candles["high"], candles["low"], candles["close"])
    assert int(signals["signal"].iloc[bar]) == 1
    assert "pivot" not in signals.columns
    assert "r1" not in signals.columns
    # Day close=90 makes S1 < prior_low, so 85 is a day-box sweep not an S1 break.
    assert signals["prior_low"].iloc[bar] == pytest.approx(90.0)
    assert float(s1.iloc[bar]) < 90.0
    assert float(r1.iloc[bar]) != pytest.approx(110.0)


def _vwap_spread_tape(*, pull_vwap_down: bool, n: int = 90) -> pd.DataFrame:
    """Long flat range, then a short heavy-volume offset so VWAP leaves SMA."""
    close = np.full(n, 100.0)
    high = close + 1.0
    low = close - 1.0
    open_ = np.full(n, 100.0)
    volume = np.full(n, 100.0)
    level = 98.0 if pull_vwap_down else 102.0
    for i in range(70, 76):
        close[i] = level
        high[i] = level + 1.0
        low[i] = level - 1.0
        open_[i] = level
        volume[i] = 8_000.0
    volume[75] = 12_000.0
    if pull_vwap_down:
        close[75] = 97.5
        low[75] = 97.0
        high[75] = 99.0
    else:
        close[75] = 102.5
        high[75] = 103.0
        low[75] = 101.0
    candles = _ohlcv(_hourly(n), close, high=high, low=low, open_=open_)
    candles["volume"] = volume
    candles["turnover"] = volume * candles["close"].to_numpy()
    return candles


def test_vwap_spread_exhaustion_schema_and_long_entry() -> None:
    candles = _vwap_spread_tape(pull_vwap_down=True)
    signals = _signals("vwap_spread_exhaustion", candles)
    for column in ("signal", "side", "score", "reason", "rolling_vwap", "sma", "spread"):
        assert column in signals.columns
    assert int(signals["signal"].iloc[0]) == 0
    assert int((signals["signal"] == 1).sum()) >= 1
    fired = signals.index[signals["signal"] == 1]
    assert len(fired) >= 1
    bar = fired[0]
    assert candles.loc[bar, "close"] < signals.loc[bar, "rolling_vwap"]
    # Mean is rolling typical-price VWAP, not utc_session_vwap.
    from core.strategy import indicators as ind

    rolled = ind.rolling_vwap(
        candles["high"], candles["low"], candles["close"], candles["volume"], 20
    )
    assert signals.loc[bar, "rolling_vwap"] == pytest.approx(float(rolled.loc[bar]))


def test_vwap_spread_exhaustion_short_entry() -> None:
    candles = _vwap_spread_tape(pull_vwap_down=False)
    signals = _signals("vwap_spread_exhaustion", candles, side=SignalSide.SHORT)
    assert int(signals["signal"].iloc[0]) == 0
    assert int((signals["signal"] == -1).sum()) >= 1
    fired = signals.index[signals["signal"] == -1]
    assert candles.loc[fired[0], "close"] > signals.loc[fired[0], "rolling_vwap"]


def test_vwap_spread_exhaustion_requires_expanding_volume() -> None:
    candles = _vwap_spread_tape(pull_vwap_down=True)
    candles["volume"] = 100.0
    candles["turnover"] = 100.0 * candles["close"]
    signals = _signals("vwap_spread_exhaustion", candles)
    assert int((signals["signal"] == 1).sum()) == 0


def test_vwap_spread_exhaustion_kit_has_two_free_params_no_skip_bull() -> None:
    from research.validate import strategy_kit

    _factory, _base, space = strategy_kit("vwap_spread_exhaustion", SignalSide.LONG)
    extra = {k: v for k, v in space.items() if k not in {"take_profit_pct", "stop_loss_pct"}}
    assert set(extra) == {"extreme_lookback", "max_adx"}
    assert "skip_bull" not in space
    assert "skip_bear" not in space


def _vwap_band_squeeze_tape(*, long_side: bool, n: int = 160) -> pd.DataFrame:
    """Wide oscillation, then a tight range with volume skew so VWAP ≠ SMA."""
    idx = np.arange(n, dtype="float64")
    close = np.where(idx < 90, 100.0 + 6.0 * np.sin(idx / 3.0), 100.0)
    # Tight squeeze with a one-sided volume pulse so rolling VWAP leaves the SMA.
    for i in range(90, n):
        if i % 3 == 0:
            close[i] = 101.2
    high = close + 0.4
    low = close - 0.4
    open_ = close.copy()
    volume = np.full(n, 100.0)
    volume[90:] = np.where(np.arange(n)[90:] % 3 == 0, 8_000.0, 100.0)
    poke = 140
    if long_side:
        close[poke] = 97.0
        low[poke] = 96.0
        high[poke] = 98.5
        open_[poke] = 99.5
        volume[poke] = 100.0
    else:
        close[poke] = 103.0
        high[poke] = 104.0
        low[poke] = 101.5
        open_[poke] = 100.5
        volume[poke] = 100.0
    candles = _ohlcv(_hourly(n), close, high=high, low=low, open_=open_)
    candles["volume"] = volume
    candles["turnover"] = volume * candles["close"].to_numpy()
    return candles


def test_vwap_volatility_band_fade_schema_and_long_entry() -> None:
    candles = _vwap_band_squeeze_tape(long_side=True)
    signals = _signals("vwap_volatility_band_fade", candles)
    for column in ("signal", "side", "score", "reason", "rolling_vwap", "vwap_upper", "vwap_lower", "bb_width"):
        assert column in signals.columns
    assert int(signals["signal"].iloc[0]) == 0
    assert int((signals["signal"] == 1).sum()) >= 1


def test_vwap_volatility_band_fade_short_entry() -> None:
    candles = _vwap_band_squeeze_tape(long_side=False)
    signals = _signals("vwap_volatility_band_fade", candles, side=SignalSide.SHORT)
    assert int(signals["signal"].iloc[0]) == 0
    assert int((signals["signal"] == -1).sum()) >= 1


def test_vwap_volatility_band_fade_bands_are_vwap_not_bollinger() -> None:
    """Outer bands are VWAP ± σ, not the SMA Bollinger bands of the book row."""
    from core.strategy import indicators as ind

    candles = _vwap_band_squeeze_tape(long_side=True)
    signals = _signals("vwap_volatility_band_fade", candles)
    fired = signals.index[signals["signal"] == 1]
    assert len(fired) >= 1
    bar = fired[0]
    mid, bb_upper, bb_lower = ind.bollinger_bands(candles["close"], 20, 2.0)
    assert abs(float(signals.loc[bar, "rolling_vwap"]) - float(mid.loc[bar])) > 0.15
    assert abs(float(signals.loc[bar, "vwap_upper"]) - float(bb_upper.loc[bar])) > 0.15
    assert abs(float(signals.loc[bar, "vwap_lower"]) - float(bb_lower.loc[bar])) > 0.15


def test_vwap_volatility_band_fade_requires_bb_width_squeeze() -> None:
    """A VWAP-band touch outside the bottom-30% BB-width window is not an entry."""
    n = 160
    close = 100.0 + 6.0 * np.sin(np.arange(n) / 3.0)
    high = close + 0.4
    low = close - 0.4
    close[140] = 90.0
    low[140] = 89.0
    high[140] = 92.0
    candles = _ohlcv(_hourly(n), close, high=high, low=low)
    signals = _signals("vwap_volatility_band_fade", candles)
    assert int(signals["signal"].iloc[140]) == 0


def _london_close_iloc(index: pd.DatetimeIndex, day: str = "2024-01-03") -> int:
    return int(index.get_loc(pd.Timestamp(f"{day} 15:00", tz="UTC")))


def test_london_close_inventory_fade_schema_and_long_entry() -> None:
    n = 72
    index = _hourly(n)
    close = np.full(n, 100.0)
    high = np.full(n, 101.0)
    low = np.full(n, 99.0)
    open_ = np.full(n, 100.0)
    bar = _london_close_iloc(index)
    low[bar] = 90.0
    high[bar] = 110.0
    close[bar] = 92.0
    open_[bar] = 100.0
    candles = _ohlcv(index, close, high=high, low=low, open_=open_)
    candles["volume"] = 200.0
    candles.loc[candles.index[bar], "volume"] = 5_000.0
    signals = _signals("london_close_inventory_fade", candles)
    for column in ("signal", "side", "score", "reason", "london_vwap", "close_frac"):
        assert column in signals.columns
    assert int(signals["signal"].iloc[0]) == 0
    assert int(signals["signal"].iloc[bar]) == 1
    assert int((signals["signal"] == 1).sum()) >= 1
    assert float(signals["close_frac"].iloc[bar]) <= 0.20
    assert candles["close"].iloc[bar] < float(signals["london_vwap"].iloc[bar])


def test_london_close_inventory_fade_short_entry() -> None:
    n = 72
    index = _hourly(n)
    close = np.full(n, 100.0)
    high = np.full(n, 101.0)
    low = np.full(n, 99.0)
    open_ = np.full(n, 100.0)
    bar = _london_close_iloc(index)
    low[bar] = 90.0
    high[bar] = 110.0
    close[bar] = 108.0
    open_[bar] = 100.0
    candles = _ohlcv(index, close, high=high, low=low, open_=open_)
    candles["volume"] = 200.0
    candles.loc[candles.index[bar], "volume"] = 5_000.0
    signals = _signals("london_close_inventory_fade", candles, side=SignalSide.SHORT)
    assert int(signals["signal"].iloc[0]) == 0
    assert int(signals["signal"].iloc[bar]) == -1
    assert int((signals["signal"] == -1).sum()) >= 1


def test_london_close_inventory_fade_is_close_bar_not_london_breakout() -> None:
    """16:00 is london_session_breakout, not the inventory-close fade."""
    n = 72
    index = _hourly(n)
    close = np.full(n, 100.0)
    high = np.full(n, 101.0)
    low = np.full(n, 99.0)
    after = int(index.get_loc(pd.Timestamp("2024-01-03 16:00", tz="UTC")))
    close[after] = 120.0
    high[after] = 121.0
    candles = _ohlcv(index, close, high=high, low=low)
    candles["volume"] = 200.0
    candles.loc[candles.index[after], "volume"] = 5_000.0
    signals = _signals("london_close_inventory_fade", candles)
    assert int(signals["signal"].iloc[after]) == 0


def test_london_close_inventory_fade_requires_heavy_volume() -> None:
    n = 72
    index = _hourly(n)
    close = np.full(n, 100.0)
    high = np.full(n, 101.0)
    low = np.full(n, 99.0)
    bar = _london_close_iloc(index)
    low[bar] = 90.0
    high[bar] = 110.0
    close[bar] = 92.0
    candles = _ohlcv(index, close, high=high, low=low)
    candles["volume"] = 200.0
    signals = _signals("london_close_inventory_fade", candles)
    assert int(signals["signal"].iloc[bar]) == 0


def test_london_close_inventory_fade_4h_bar_is_1200_utc() -> None:
    """On 4h, the bar covering 15:00–16:00 is the open-labeled 12:00 bar."""
    n = 40
    index = pd.date_range("2024-01-02", periods=n, freq="4h", tz="UTC")
    close = np.full(n, 100.0)
    high = np.full(n, 101.0)
    low = np.full(n, 99.0)
    open_ = np.full(n, 100.0)
    bar = int(index.get_loc(pd.Timestamp("2024-01-07 12:00", tz="UTC")))
    low[bar] = 90.0
    high[bar] = 110.0
    close[bar] = 92.0
    candles = _ohlcv(index, close, high=high, low=low, open_=open_)
    candles["volume"] = 200.0
    candles.loc[candles.index[bar], "volume"] = 5_000.0
    signals = _signals("london_close_inventory_fade", candles)
    assert bar >= 24
    assert int(signals["signal"].iloc[bar]) == 1
    morning = int(index.get_loc(pd.Timestamp("2024-01-07 08:00", tz="UTC")))
    assert int(signals["signal"].iloc[morning]) == 0


def _utc_second_4h_iloc(index: pd.DatetimeIndex) -> int:
    return int(index.get_loc(pd.Timestamp("2024-01-03 07:00", tz="UTC")))


def test_utc_open_fail_reversion_schema_and_long_entry() -> None:
    n = 72
    index = _hourly(n)
    close = np.full(n, 100.0)
    high = np.full(n, 101.0)
    low = np.full(n, 99.0)
    open_ = np.full(n, 100.0)
    # Day-1 first 4h box 90–110.
    for hour in range(4):
        i = int(index.get_loc(pd.Timestamp(f"2024-01-03 {hour:02d}:00", tz="UTC")))
        high[i] = 110.0
        low[i] = 90.0
        close[i] = 100.0
    bar = _utc_second_4h_iloc(index)
    wick = int(index.get_loc(pd.Timestamp("2024-01-03 05:00", tz="UTC")))
    low[wick] = 85.0
    close[wick] = 95.0
    high[wick] = 100.0
    close[bar] = 100.0
    high[bar] = 101.0
    low[bar] = 99.0
    candles = _ohlcv(index, close, high=high, low=low, open_=open_)
    signals = _signals("utc_open_fail_reversion", candles)
    for column in ("signal", "side", "score", "reason", "box_high", "box_low", "box_mid"):
        assert column in signals.columns
    assert int(signals["signal"].iloc[0]) == 0
    assert int(signals["signal"].iloc[bar]) == 1
    assert signals["box_high"].iloc[bar] == pytest.approx(110.0)
    assert signals["box_low"].iloc[bar] == pytest.approx(90.0)
    assert signals["box_mid"].iloc[bar] == pytest.approx(100.0)


def test_utc_open_fail_reversion_short_entry() -> None:
    n = 72
    index = _hourly(n)
    close = np.full(n, 100.0)
    high = np.full(n, 101.0)
    low = np.full(n, 99.0)
    open_ = np.full(n, 100.0)
    for hour in range(4):
        i = int(index.get_loc(pd.Timestamp(f"2024-01-03 {hour:02d}:00", tz="UTC")))
        high[i] = 110.0
        low[i] = 90.0
        close[i] = 100.0
    bar = _utc_second_4h_iloc(index)
    wick = int(index.get_loc(pd.Timestamp("2024-01-03 05:00", tz="UTC")))
    high[wick] = 115.0
    close[wick] = 105.0
    low[wick] = 100.0
    close[bar] = 100.0
    candles = _ohlcv(index, close, high=high, low=low, open_=open_)
    signals = _signals("utc_open_fail_reversion", candles, side=SignalSide.SHORT)
    assert int(signals["signal"].iloc[0]) == 0
    assert int(signals["signal"].iloc[bar]) == -1


def test_utc_open_fail_reversion_ignores_held_breakout() -> None:
    """A second-4h close still outside the box is a break, not a fail."""
    n = 72
    index = _hourly(n)
    close = np.full(n, 100.0)
    high = np.full(n, 101.0)
    low = np.full(n, 99.0)
    for hour in range(4):
        i = int(index.get_loc(pd.Timestamp(f"2024-01-03 {hour:02d}:00", tz="UTC")))
        high[i] = 110.0
        low[i] = 90.0
    bar = _utc_second_4h_iloc(index)
    low[bar] = 80.0
    close[bar] = 84.0
    high[bar] = 95.0
    candles = _ohlcv(index, close, high=high, low=low)
    signals = _signals("utc_open_fail_reversion", candles)
    assert int(signals["signal"].iloc[bar]) == 0


def test_utc_open_fail_reversion_not_asian_or_midnight() -> None:
    """No entry on the first 4h bar or after 08:00 (Asian-range / midnight families)."""
    n = 72
    index = _hourly(n)
    close = np.full(n, 100.0)
    high = np.full(n, 101.0)
    low = np.full(n, 99.0)
    first = int(index.get_loc(pd.Timestamp("2024-01-03 00:00", tz="UTC")))
    low[first] = 80.0
    close[first] = 85.0
    after = int(index.get_loc(pd.Timestamp("2024-01-03 08:00", tz="UTC")))
    low[after] = 85.0
    close[after] = 95.0
    candles = _ohlcv(index, close, high=high, low=low)
    signals = _signals("utc_open_fail_reversion", candles)
    assert int(signals["signal"].iloc[first]) == 0
    assert int(signals["signal"].iloc[after]) == 0


def _compress_then_thrust(*, long_side: bool, n: int = 160, poke: int = 140) -> pd.DataFrame:
    close = np.full(n, 100.0)
    open_ = np.full(n, 100.0)
    high = np.full(n, 102.0)
    low = np.full(n, 98.0)
    # Wide early ranges lift ATR; later bars tighten so 20-ATR sits in the bottom 30%.
    high[40:poke] = 100.15
    low[40:poke] = 99.85
    volume = np.full(n, 200.0)
    if long_side:
        open_[poke] = 100.0
        close[poke] = 112.0
        high[poke] = 113.0
        low[poke] = 99.5
    else:
        open_[poke] = 100.0
        close[poke] = 88.0
        high[poke] = 100.5
        low[poke] = 87.0
    volume[poke] = 8_000.0
    candles = _ohlcv(_hourly(n), close, high=high, low=low, open_=open_)
    candles["volume"] = volume
    return candles


def test_range_compression_volume_thrust_schema_and_long_entry() -> None:
    candles = _compress_then_thrust(long_side=True)
    signals = _signals("range_compression_volume_thrust", candles)
    for column in ("signal", "side", "score", "reason", "atr", "true_range", "compressed"):
        assert column in signals.columns
    assert int(signals["signal"].iloc[0]) == 0
    assert int((signals["signal"] == 1).sum()) >= 1
    assert int((signals["signal"] == -1).sum()) == 0


def test_range_compression_volume_thrust_short_entry() -> None:
    candles = _compress_then_thrust(long_side=False)
    signals = _signals("range_compression_volume_thrust", candles, side=SignalSide.SHORT)
    assert int(signals["signal"].iloc[0]) == 0
    assert int((signals["signal"] == -1).sum()) >= 1
    assert int((signals["signal"] == 1).sum()) == 0


def test_range_compression_volume_thrust_requires_atr_squeeze() -> None:
    """A thrust outside ATR-percentile compression is not this family."""
    n = 160
    close = 100.0 + 6.0 * np.sin(np.arange(n) / 3.0)
    high = close + 2.0
    low = close - 2.0
    open_ = close.copy()
    open_[-1] = close[-1] - 8.0
    close[-1] = close[-1] + 8.0
    high[-1] = close[-1] + 1.0
    candles = _ohlcv(_hourly(n), close, high=high, low=low, open_=open_)
    candles["volume"] = 8_000.0
    signals = _signals("range_compression_volume_thrust", candles)
    assert int(signals["signal"].iloc[-1]) == 0


def test_range_compression_volume_thrust_not_nr7_or_bb_width() -> None:
    """Kit does not search NR7 lookback or BB width; compression is ATR percentile."""
    from research.validate import strategy_kit

    _factory, _base, space = strategy_kit("range_compression_volume_thrust", SignalSide.LONG)
    extra = {k for k in space if k not in {"take_profit_pct", "stop_loss_pct"}}
    assert extra == {"compress_pct", "thrust_mult"}
    assert "lookback" not in space
    assert "band_k" not in space
    assert "skip_bull" not in space


def test_turnover_climax_rejection_fade_schema_and_long_entry() -> None:
    n = 60
    close = np.full(n, 100.0)
    high = np.full(n, 101.0)
    low = np.full(n, 99.0)
    open_ = np.full(n, 100.0)
    low[50] = 90.0
    high[50] = 100.0
    close[50] = 99.0
    candles = _ohlcv(_hourly(n), close, high=high, low=low, open_=open_)
    candles["turnover"] = 1_000.0
    candles.loc[candles.index[50], "turnover"] = 50_000.0
    signals = _signals("turnover_climax_rejection_fade", candles)
    for column in ("signal", "side", "score", "reason", "prior_high", "prior_low", "close_frac", "climax"):
        assert column in signals.columns
    assert int(signals["signal"].iloc[0]) == 0
    assert int(signals["signal"].iloc[50]) == 1
    assert signals["close_frac"].iloc[50] == pytest.approx(0.90)
    assert int((signals["signal"] == 1).sum()) >= 1


def test_turnover_climax_rejection_fade_short_entry() -> None:
    n = 60
    close = np.full(n, 100.0)
    high = np.full(n, 101.0)
    low = np.full(n, 99.0)
    open_ = np.full(n, 100.0)
    high[50] = 110.0
    low[50] = 100.0
    close[50] = 101.0
    candles = _ohlcv(_hourly(n), close, high=high, low=low, open_=open_)
    candles["turnover"] = 1_000.0
    candles.loc[candles.index[50], "turnover"] = 50_000.0
    signals = _signals("turnover_climax_rejection_fade", candles, side=SignalSide.SHORT)
    assert int(signals["signal"].iloc[0]) == 0
    assert int(signals["signal"].iloc[50]) == -1
    assert signals["close_frac"].iloc[50] == pytest.approx(0.10)


def test_turnover_climax_rejection_fade_reads_turnover() -> None:
    n = 60
    close = np.full(n, 100.0)
    high = np.full(n, 101.0)
    low = np.full(n, 99.0)
    low[50] = 90.0
    high[50] = 100.0
    close[50] = 99.0
    candles = _ohlcv(_hourly(n), close, high=high, low=low)
    candles["turnover"] = 1_000.0
    candles.loc[candles.index[50], "turnover"] = 50_000.0
    from research.validate import strategy_kit

    factory, base, space = strategy_kit("turnover_climax_rejection_fade", SignalSide.LONG)
    extra = {k for k in space if k not in {"take_profit_pct", "stop_loss_pct"}}
    assert extra == {"lookback", "reject_frac"}
    sleeve = factory(base)
    with pytest.raises(ValueError, match="turnover"):
        sleeve.generate_signals(candles.drop(columns=["turnover"]))
    # Same price rejection without a turnover climax is not this fade.
    quiet = candles.copy()
    quiet["turnover"] = 1_000.0
    assert int(sleeve.generate_signals(quiet)["signal"].iloc[50]) == 0


def test_volume_dryup_range_break_schema_and_long_entry() -> None:
    n = 60
    close = np.full(n, 100.0)
    high = np.full(n, 101.0)
    low = np.full(n, 99.0)
    open_ = np.full(n, 100.0)
    close[49] = 108.0
    high[49] = 109.0
    candles = _ohlcv(_hourly(n), close, high=high, low=low, open_=open_)
    volume = np.full(n, 1_000.0)
    volume[46:49] = 50.0
    volume[49] = 8_000.0
    candles["volume"] = volume
    signals = _signals("volume_dryup_range_break", candles)
    for column in ("signal", "side", "score", "reason", "box_high", "box_low", "vol_mean"):
        assert column in signals.columns
    assert int(signals["signal"].iloc[0]) == 0
    assert int(signals["signal"].iloc[49]) == 1
    assert signals["box_high"].iloc[49] == pytest.approx(101.0)


def test_volume_dryup_range_break_short_entry() -> None:
    n = 60
    close = np.full(n, 100.0)
    high = np.full(n, 101.0)
    low = np.full(n, 99.0)
    open_ = np.full(n, 100.0)
    close[49] = 92.0
    low[49] = 91.0
    candles = _ohlcv(_hourly(n), close, high=high, low=low, open_=open_)
    volume = np.full(n, 1_000.0)
    volume[46:49] = 50.0
    volume[49] = 8_000.0
    candles["volume"] = volume
    signals = _signals("volume_dryup_range_break", candles, side=SignalSide.SHORT)
    assert int(signals["signal"].iloc[0]) == 0
    assert int(signals["signal"].iloc[49]) == -1


def test_volume_dryup_range_break_requires_three_dry_bars() -> None:
    n = 60
    close = np.full(n, 100.0)
    high = np.full(n, 101.0)
    low = np.full(n, 99.0)
    close[49] = 108.0
    high[49] = 109.0
    candles = _ohlcv(_hourly(n), close, high=high, low=low)
    volume = np.full(n, 1_000.0)
    volume[48] = 50.0
    volume[49] = 8_000.0
    candles["volume"] = volume
    signals = _signals("volume_dryup_range_break", candles)
    assert int(signals["signal"].iloc[49]) == 0


def test_body_efficiency_follow_schema_and_long_entry() -> None:
    n = 24
    close = np.full(n, 100.0)
    open_ = np.full(n, 100.0)
    high = np.full(n, 101.0)
    low = np.full(n, 99.0)
    volume = np.full(n, 1_000.0)
    # Two consecutive efficient up-bodies; second volume is not smaller.
    open_[12] = 100.0
    close[12] = 110.0
    high[12] = 111.0
    low[12] = 99.5
    volume[12] = 1_200.0
    open_[13] = 110.0
    close[13] = 121.0
    high[13] = 122.0
    low[13] = 109.5
    volume[13] = 1_500.0
    candles = _ohlcv(_hourly(n), close, high=high, low=low, open_=open_)
    candles["volume"] = volume
    signals = _signals("body_efficiency_follow", candles)
    for column in ("signal", "side", "score", "reason", "efficiency", "prev_efficiency"):
        assert column in signals.columns
    assert int(signals["signal"].iloc[0]) == 0
    assert int(signals["signal"].iloc[13]) == 1
    assert int((signals["signal"] == 1).sum()) >= 1
    assert int((signals["signal"] == -1).sum()) == 0
    assert float(signals["efficiency"].iloc[13]) >= 0.7
    assert float(signals["efficiency"].iloc[12]) >= 0.7


def test_body_efficiency_follow_short_entry() -> None:
    n = 24
    close = np.full(n, 100.0)
    open_ = np.full(n, 100.0)
    high = np.full(n, 101.0)
    low = np.full(n, 99.0)
    volume = np.full(n, 1_000.0)
    open_[12] = 100.0
    close[12] = 90.0
    high[12] = 100.5
    low[12] = 89.0
    volume[12] = 1_200.0
    open_[13] = 90.0
    close[13] = 79.0
    high[13] = 90.5
    low[13] = 78.0
    volume[13] = 1_500.0
    candles = _ohlcv(_hourly(n), close, high=high, low=low, open_=open_)
    candles["volume"] = volume
    signals = _signals("body_efficiency_follow", candles, side=SignalSide.SHORT)
    assert int(signals["signal"].iloc[0]) == 0
    assert int(signals["signal"].iloc[13]) == -1
    assert int((signals["signal"] == -1).sum()) >= 1
    assert int((signals["signal"] == 1).sum()) == 0


def test_body_efficiency_follow_not_engulf_or_three_bar_or_exhaustion() -> None:
    """Follow two efficient bodies. Not an engulf reverse, rest-break, or fade."""
    n = 24
    close = np.full(n, 100.0)
    open_ = np.full(n, 100.0)
    high = np.full(n, 101.0)
    low = np.full(n, 99.0)
    volume = np.full(n, 1_000.0)
    # Two up-bodies that do not engulf (second open is above first open).
    open_[12] = 100.0
    close[12] = 110.0
    high[12] = 111.0
    low[12] = 99.5
    volume[12] = 1_200.0
    open_[13] = 110.0
    close[13] = 121.0
    high[13] = 122.0
    low[13] = 109.5
    volume[13] = 1_500.0
    candles = _ohlcv(_hourly(n), close, high=high, low=low, open_=open_)
    candles["volume"] = volume
    follow = _signals("body_efficiency_follow", candles)
    engulf = _signals("engulfing_reversal", candles)
    play = _signals("three_bar_play", candles)
    fade = _signals("consecutive_bar_exhaustion", candles)
    assert int(follow["signal"].iloc[13]) == 1
    assert int(engulf["signal"].iloc[13]) == 0
    assert int(play["signal"].iloc[13]) == 0
    assert int(fade["signal"].iloc[13]) == 0
    # Second volume below the first is not this follow.
    quiet = candles.copy()
    quiet.loc[quiet.index[13], "volume"] = 800.0
    assert int(_signals("body_efficiency_follow", quiet)["signal"].iloc[13]) == 0


def _week_open_tape(*, long_side: bool, n: int = 80) -> tuple[pd.DatetimeIndex, pd.DataFrame, int]:
    """Monday 00:00 week open at 100, three wrong-side closes after vol warm-up, then reclaim."""
    index = _hourly(n, start="2024-01-01")
    close = np.full(n, 100.0)
    open_ = np.full(n, 100.0)
    high = np.full(n, 101.0)
    low = np.full(n, 99.0)
    volume = np.full(n, 200.0)
    # Past the 20-bar volume mean and min_bars. Same ISO week as Monday 00:00.
    wrong = [
        int(index.get_loc(pd.Timestamp("2024-01-02 00:00", tz="UTC"))),
        int(index.get_loc(pd.Timestamp("2024-01-02 04:00", tz="UTC"))),
        int(index.get_loc(pd.Timestamp("2024-01-02 08:00", tz="UTC"))),
    ]
    reclaim = int(index.get_loc(pd.Timestamp("2024-01-02 12:00", tz="UTC")))
    if long_side:
        for i in wrong:
            close[i] = 95.0
            high[i] = 96.0
            low[i] = 94.0
            open_[i] = 96.0
        close[reclaim] = 105.0
        open_[reclaim] = 96.0
        high[reclaim] = 106.0
        low[reclaim] = 95.5
    else:
        for i in wrong:
            close[i] = 105.0
            high[i] = 106.0
            low[i] = 104.0
            open_[i] = 104.0
        close[reclaim] = 95.0
        open_[reclaim] = 104.0
        high[reclaim] = 104.5
        low[reclaim] = 94.0
    volume[reclaim] = 8_000.0
    candles = _ohlcv(index, close, high=high, low=low, open_=open_)
    candles["volume"] = volume
    return index, candles, reclaim


def test_week_open_reclaim_schema_and_long_entry() -> None:
    index, candles, reclaim = _week_open_tape(long_side=True)
    signals = _signals("week_open_reclaim", candles)
    for column in ("signal", "side", "score", "reason", "week_open", "below_count", "vol_mean"):
        assert column in signals.columns
    assert int(signals["signal"].iloc[0]) == 0
    assert int(signals["signal"].iloc[reclaim]) == 1
    assert int((signals["signal"] == 1).sum()) >= 1
    monday = int(index.get_loc(pd.Timestamp("2024-01-01 00:00", tz="UTC")))
    assert signals["week_open"].iloc[reclaim] == pytest.approx(float(candles["open"].iloc[monday]))
    assert signals["week_open"].iloc[reclaim] == pytest.approx(100.0)


def test_week_open_reclaim_short_entry() -> None:
    _index, candles, reclaim = _week_open_tape(long_side=False)
    signals = _signals("week_open_reclaim", candles, side=SignalSide.SHORT)
    assert int(signals["signal"].iloc[0]) == 0
    assert int(signals["signal"].iloc[reclaim]) == -1
    assert int((signals["signal"] == -1).sum()) >= 1


def test_week_open_reclaim_needs_three_wrong_side_closes() -> None:
    index, candles, reclaim = _week_open_tape(long_side=True)
    # Only two wrong-side closes: wipe the 04:00 print back to the week open.
    first_wrong = int(index.get_loc(pd.Timestamp("2024-01-02 00:00", tz="UTC")))
    candles.loc[candles.index[first_wrong], "close"] = 100.0
    candles.loc[candles.index[first_wrong], "high"] = 101.0
    candles.loc[candles.index[first_wrong], "low"] = 99.0
    signals = _signals("week_open_reclaim", candles)
    assert int(signals["signal"].iloc[reclaim]) == 0


def test_week_open_reclaim_is_monday_open_not_weekend_or_prior_week() -> None:
    """Anchor is this week's Monday 00:00 open, not weekend H/L or prior-week high."""
    index, candles, reclaim = _week_open_tape(long_side=True)
    signals = _signals("week_open_reclaim", candles)
    monday = _signals("monday_range_sweep_reversal", candles)
    prior_week = _signals("prior_week_high_break", candles)
    assert int(signals["signal"].iloc[reclaim]) == 1
    assert int(monday["signal"].iloc[reclaim]) == 0
    assert int(prior_week["signal"].iloc[reclaim]) == 0
    assert "weekend_mid" not in signals.columns
    assert "week_high" not in signals.columns


def _session_mid_tape(*, long_side: bool, n: int = 72) -> tuple[pd.DatetimeIndex, pd.DataFrame, int]:
    """Day-1 00-08 session through one side of mid=100; reclaim after 08:00 on heavy volume."""
    index = _hourly(n, start="2024-01-02")
    close = np.full(n, 100.0)
    open_ = np.full(n, 100.0)
    high = np.full(n, 101.0)
    low = np.full(n, 99.0)
    volume = np.full(n, 200.0)
    # Session 00-08 on Jan 3 (after vol warm-up): H=110 / L=90 → mid=100.
    for hour in range(8):
        i = int(index.get_loc(pd.Timestamp(f"2024-01-03 {hour:02d}:00", tz="UTC")))
        high[i] = 110.0
        low[i] = 90.0
        close[i] = 100.0
    last = int(index.get_loc(pd.Timestamp("2024-01-03 07:00", tz="UTC")))
    reclaim = int(index.get_loc(pd.Timestamp("2024-01-03 10:00", tz="UTC")))
    if long_side:
        close[last] = 92.0
        high[last] = 110.0
        low[last] = 90.0
        close[reclaim] = 105.0
        open_[reclaim] = 96.0
        high[reclaim] = 106.0
        low[reclaim] = 95.0
    else:
        close[last] = 108.0
        high[last] = 110.0
        low[last] = 90.0
        close[reclaim] = 95.0
        open_[reclaim] = 104.0
        high[reclaim] = 105.0
        low[reclaim] = 94.0
    volume[reclaim] = 8_000.0
    candles = _ohlcv(index, close, high=high, low=low, open_=open_)
    candles["volume"] = volume
    return index, candles, reclaim


def test_prior_session_mid_reclaim_schema_and_long_entry() -> None:
    index, candles, reclaim = _session_mid_tape(long_side=True)
    signals = _signals("prior_session_mid_reclaim", candles)
    for column in (
        "signal",
        "side",
        "score",
        "reason",
        "session_high",
        "session_low",
        "session_mid",
        "session_close",
    ):
        assert column in signals.columns
    assert int(signals["signal"].iloc[0]) == 0
    assert int(signals["signal"].iloc[reclaim]) == 1
    assert int((signals["signal"] == 1).sum()) >= 1
    assert signals["session_mid"].iloc[reclaim] == pytest.approx(100.0)
    assert signals["session_high"].iloc[reclaim] == pytest.approx(110.0)
    assert signals["session_low"].iloc[reclaim] == pytest.approx(90.0)
    # During 00-08 the published box is the prior 16-24 session, not this one.
    during = int(index.get_loc(pd.Timestamp("2024-01-03 04:00", tz="UTC")))
    assert int(signals["signal"].iloc[during]) == 0
    assert signals["session_high"].iloc[during] == pytest.approx(101.0)
    assert signals["session_low"].iloc[during] == pytest.approx(99.0)


def test_prior_session_mid_reclaim_short_entry() -> None:
    _index, candles, reclaim = _session_mid_tape(long_side=False)
    signals = _signals("prior_session_mid_reclaim", candles, side=SignalSide.SHORT)
    assert int(signals["signal"].iloc[0]) == 0
    assert int(signals["signal"].iloc[reclaim]) == -1
    assert int((signals["signal"] == -1).sum()) >= 1


def test_prior_session_mid_reclaim_not_vwap_or_day_box_or_first4h() -> None:
    """8h session mid, not session VWAP, not UTC-day H/L, not first-4h fail."""
    index, candles, reclaim = _session_mid_tape(long_side=True)
    signals = _signals("prior_session_mid_reclaim", candles)
    boundary = _signals("session_boundary_volume_fade", candles)
    vwap = _signals("utc_session_vwap_reversion", candles)
    first4 = _signals("utc_open_fail_reversion", candles)
    assert int(signals["signal"].iloc[reclaim]) == 1
    assert int(boundary["signal"].iloc[reclaim]) == 0
    assert int(vwap["signal"].iloc[reclaim]) == 0
    assert int(first4["signal"].iloc[reclaim]) == 0
    assert "daily_vwap" not in signals.columns
    assert "box_high" not in signals.columns
    # Weak volume on the reclaim bar is not this family.
    quiet = candles.copy()
    quiet.loc[quiet.index[reclaim], "volume"] = 50.0
    assert int(_signals("prior_session_mid_reclaim", quiet)["signal"].iloc[reclaim]) == 0


def _clv_persistence_tape(*, long_side: bool, n: int = 50) -> pd.DataFrame:
    """Upper-quartile closes persist; body efficiency stays low; not a 20-bar extreme.

    Close sits in the top (bottom) 20% of a 2-point range so mean CLV is ~0.80
    (0.20). Open sits near mid-range so the lower wick is 0.5 — below the
    wick-rejection floor — and |close-open|/TR is well under 0.7.
    """
    close = np.full(n, 100.0)
    open_ = np.full(n, 100.0)
    high = np.full(n, 101.0)
    low = np.full(n, 99.0)
    if long_side:
        # Keep this close high inside the 20-bar window of the persistence bars.
        close[18] = 110.0
        high[18] = 111.0
        low[18] = 99.0
        open_[18] = 100.0
        for i in range(22, n):
            open_[i] = 100.0
            close[i] = 100.6
            high[i] = 101.0
            low[i] = 99.0
    else:
        close[18] = 90.0
        high[18] = 101.0
        low[18] = 89.0
        open_[18] = 100.0
        for i in range(22, n):
            open_[i] = 100.0
            close[i] = 99.4
            high[i] = 101.0
            low[i] = 99.0
    return _ohlcv(_hourly(n), close, high=high, low=low, open_=open_)


def test_close_location_persistence_schema_and_long_entry() -> None:
    candles = _clv_persistence_tape(long_side=True)
    signals = _signals("close_location_persistence", candles)
    for column in ("signal", "side", "score", "reason", "clv", "mean_clv", "close_high"):
        assert column in signals.columns
    assert int(signals["signal"].iloc[0]) == 0
    assert int((signals["signal"] == 1).sum()) >= 1
    assert int((signals["signal"] == -1).sum()) == 0
    fired = signals.index[signals["signal"] == 1]
    assert float(signals.loc[fired[0], "mean_clv"]) >= 0.75
    assert float(candles.loc[fired[0], "close"]) < float(signals.loc[fired[0], "close_high"])


def test_close_location_persistence_short_entry() -> None:
    candles = _clv_persistence_tape(long_side=False)
    signals = _signals("close_location_persistence", candles, side=SignalSide.SHORT)
    assert int(signals["signal"].iloc[0]) == 0
    assert int((signals["signal"] == -1).sum()) >= 1
    assert int((signals["signal"] == 1).sum()) == 0
    fired = signals.index[signals["signal"] == -1]
    assert float(signals.loc[fired[0], "mean_clv"]) <= 0.25


def test_close_location_persistence_not_body_efficiency_or_wick() -> None:
    """Mean CLV persist is not a two-bar efficient follow and not a wick fade."""
    from core.strategy import indicators as ind

    candles = _clv_persistence_tape(long_side=True)
    persist = _signals("close_location_persistence", candles)
    follow = _signals("body_efficiency_follow", candles)
    wick = _signals("wick_rejection_reversal", candles)
    fired = persist.index[persist["signal"] == 1]
    assert len(fired) >= 1
    bar = fired[0]
    assert int(persist.loc[bar, "signal"]) == 1
    assert int(follow.loc[bar, "signal"]) == 0
    assert int(wick.loc[bar, "signal"]) == 0
    clv = ind.close_location_value(candles["high"], candles["low"], candles["close"])
    eff = ind.body_efficiency(
        candles["open"], candles["high"], candles["low"], candles["close"]
    )
    assert float(clv.loc[bar]) >= 0.75
    assert float(eff.loc[bar]) < 0.7
    # A new 20-bar close high is not this family — that is a breakout.
    blocked = candles.copy()
    idx = blocked.index[30]
    blocked.loc[idx, "close"] = 120.0
    blocked.loc[idx, "high"] = 121.0
    blocked.loc[idx, "low"] = 99.0
    blocked.loc[idx, "open"] = 100.0
    quiet = _signals("close_location_persistence", blocked)
    assert int(quiet["signal"].iloc[30]) == 0


def _prior_range_fail_tape(*, long_side: bool, n: int = 24) -> tuple[pd.DataFrame, int]:
    """Mid-day adjacent-bar open-outside then close-back-inside. Not UTC 04:00."""
    close = np.full(n, 100.0)
    open_ = np.full(n, 100.0)
    high = np.full(n, 101.0)
    low = np.full(n, 99.0)
    bar = 12  # 12:00 UTC on a 2024-01-02 hourly tape.
    if long_side:
        open_[bar] = 90.0
        close[bar] = 100.0
        high[bar] = 101.0
        low[bar] = 89.0
    else:
        open_[bar] = 110.0
        close[bar] = 100.0
        high[bar] = 111.0
        low[bar] = 99.0
    candles = _ohlcv(_hourly(n, start="2024-01-02"), close, high=high, low=low, open_=open_)
    return candles, bar


def test_open_in_prior_range_fail_schema_and_long_entry() -> None:
    candles, bar = _prior_range_fail_tape(long_side=True)
    signals = _signals("open_in_prior_range_fail", candles)
    for column in ("signal", "side", "score", "reason", "prior_high", "prior_low", "prior_mid"):
        assert column in signals.columns
    assert int(signals["signal"].iloc[0]) == 0
    assert int(signals["signal"].iloc[bar]) == 1
    assert int((signals["signal"] == 1).sum()) >= 1
    assert int((signals["signal"] == -1).sum()) == 0
    assert signals["prior_high"].iloc[bar] == pytest.approx(101.0)
    assert signals["prior_low"].iloc[bar] == pytest.approx(99.0)
    assert signals["prior_mid"].iloc[bar] == pytest.approx(100.0)


def test_open_in_prior_range_fail_short_entry() -> None:
    candles, bar = _prior_range_fail_tape(long_side=False)
    signals = _signals("open_in_prior_range_fail", candles, side=SignalSide.SHORT)
    assert int(signals["signal"].iloc[0]) == 0
    assert int(signals["signal"].iloc[bar]) == -1
    assert int((signals["signal"] == -1).sum()) >= 1
    assert int((signals["signal"] == 1).sum()) == 0


def test_open_in_prior_range_fail_not_utc_first4h_or_ny_drive() -> None:
    """12:00 adjacent-bar fail is not the UTC first-4h box and not NY 13:00."""
    candles, bar = _prior_range_fail_tape(long_side=True)
    signals = _signals("open_in_prior_range_fail", candles)
    utc_fail = _signals("utc_open_fail_reversion", candles)
    ny = _signals("ny_cash_open_drive", candles)
    assert int(signals["signal"].iloc[bar]) == 1
    assert int(utc_fail["signal"].iloc[bar]) == 0
    assert int(ny["signal"].iloc[bar]) == 0
    assert "box_high" not in signals.columns
    # Close still outside the prior range is a held break, not a fail.
    held = candles.copy()
    held.loc[held.index[bar], "close"] = 88.0
    held.loc[held.index[bar], "low"] = 87.0
    assert int(_signals("open_in_prior_range_fail", held)["signal"].iloc[bar]) == 0


def _equal_restest_tape(*, long_side: bool, n: int = 50) -> tuple[pd.DataFrame, int]:
    """Two matching prior highs/lows, then this bar pokes through and fails back."""
    close = np.full(n, 100.0)
    open_ = np.full(n, 100.0)
    high = np.full(n, 101.0)
    low = np.full(n, 99.0)
    # Both touches sit inside the default lookback=12 prior window at `poke`.
    first, second, poke = 30, 36, 42
    if long_side:
        for i in (first, second):
            low[i] = 90.0
            close[i] = 92.0
            high[i] = 101.0
            open_[i] = 100.0
        low[poke] = 88.0
        close[poke] = 92.0
        high[poke] = 101.0
        open_[poke] = 100.0
    else:
        for i in (first, second):
            high[i] = 110.0
            close[i] = 108.0
            low[i] = 99.0
            open_[i] = 100.0
        high[poke] = 112.0
        close[poke] = 108.0
        low[poke] = 99.0
        open_[poke] = 100.0
    candles = _ohlcv(_hourly(n, start="2024-01-03"), close, high=high, low=low, open_=open_)
    return candles, poke


def test_equal_high_low_restest_fade_schema_and_long_entry() -> None:
    candles, poke = _equal_restest_tape(long_side=True)
    signals = _signals("equal_high_low_restest_fade", candles)
    for column in ("signal", "side", "score", "reason", "equal_high", "equal_low", "tol"):
        assert column in signals.columns
    assert int(signals["signal"].iloc[0]) == 0
    assert int(signals["signal"].iloc[poke]) == 1
    assert int((signals["signal"] == 1).sum()) >= 1
    assert int((signals["signal"] == -1).sum()) == 0
    assert signals["equal_low"].iloc[poke] == pytest.approx(90.0)


def test_equal_high_low_restest_fade_short_entry() -> None:
    candles, poke = _equal_restest_tape(long_side=False)
    signals = _signals("equal_high_low_restest_fade", candles, side=SignalSide.SHORT)
    assert int(signals["signal"].iloc[0]) == 0
    assert int(signals["signal"].iloc[poke]) == -1
    assert int((signals["signal"] == -1).sum()) >= 1
    assert int((signals["signal"] == 1).sum()) == 0
    assert signals["equal_high"].iloc[poke] == pytest.approx(110.0)


def test_equal_high_low_restest_fade_not_monday_or_session_sweep() -> None:
    """Rolling equal-high restest on a Wednesday is not a weekend or Asian box."""
    candles, poke = _equal_restest_tape(long_side=False)
    signals = _signals("equal_high_low_restest_fade", candles, side=SignalSide.SHORT)
    monday = _signals("monday_range_sweep_reversal", candles, side=SignalSide.SHORT)
    asian = _signals("session_liquidity_sweep", candles, side=SignalSide.SHORT)
    assert int(signals["signal"].iloc[poke]) == -1
    assert int(monday["signal"].iloc[poke]) == 0
    assert int(asian["signal"].iloc[poke]) == 0
    assert "weekend_mid" not in signals.columns
    assert "range_high" not in signals.columns
    # One isolated high is not an equal-high cluster — no fade.
    lonely = candles.copy()
    lonely.loc[lonely.index[30], "high"] = 101.0
    lonely.loc[lonely.index[30], "close"] = 100.0
    assert int(
        _signals("equal_high_low_restest_fade", lonely, side=SignalSide.SHORT)["signal"].iloc[poke]
    ) == 0


def _planted_swings_background(n: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Strictly rising background so confirmed_swings cannot mint 101/99 pivots."""
    drift = 0.01 * np.arange(n)
    close = 100.0 + drift
    high = 101.0 + drift
    low = 99.0 + drift
    open_ = 100.0 + drift
    return close, high, low, open_


def _double_bottom_tape(*, invalidate: bool, n: int = 90) -> tuple[pd.DataFrame, int]:
    """Two matched swing lows, intervening high, then neckline break or second-low fail."""
    close, high, low, open_ = _planted_swings_background(n)
    first_low, neck_bar, second_low, fire = 22, 34, 46, 58
    low[first_low] = 90.0
    close[first_low] = 91.0
    high[neck_bar] = 110.0
    close[neck_bar] = 108.0
    low[second_low] = 90.1
    close[second_low] = 91.0
    if invalidate:
        # Close through the second trough. Not a two-high neckline break.
        close[fire] = 88.0
        low[fire] = 87.0
        high[fire] = 91.0
        open_[fire] = 91.0
    else:
        # Confirmed close through the intervening high.
        close[fire] = 111.0
        high[fire] = 112.0
        low[fire] = 108.0
        open_[fire] = 108.0
    candles = _ohlcv(_hourly(n, start="2024-01-03"), close, high=high, low=low, open_=open_)
    return candles, fire


def test_double_bottom_neckline_break_schema_and_long_entry() -> None:
    candles, fire = _double_bottom_tape(invalidate=False)
    signals = _signals("double_bottom_neckline_break", candles)
    for column in ("signal", "side", "score", "reason", "first_low", "second_low", "neckline"):
        assert column in signals.columns
    assert int(signals["signal"].iloc[0]) == 0
    assert int(signals["signal"].iloc[fire]) == 1
    assert int((signals["signal"] == 1).sum()) >= 1
    assert int((signals["signal"] == -1).sum()) == 0
    assert signals["neckline"].iloc[fire] == pytest.approx(110.0)
    # Job 110 fades a failed restest. This bar closes through the neckline.
    restest = _signals("equal_high_low_restest_fade", candles)
    assert int(restest["signal"].iloc[fire]) == 0


def test_double_bottom_neckline_break_short_invalidation() -> None:
    candles, fire = _double_bottom_tape(invalidate=True)
    signals = _signals("double_bottom_neckline_break", candles, side=SignalSide.SHORT)
    assert int(signals["signal"].iloc[0]) == 0
    assert int(signals["signal"].iloc[fire]) == -1
    assert int((signals["signal"] == -1).sum()) >= 1
    assert int((signals["signal"] == 1).sum()) == 0
    assert signals["second_low"].iloc[fire] == pytest.approx(90.1)
    # Invalidation is not a double-top neckline break of two highs.
    double_top = _signals("double_top_neckline_break", candles, side=SignalSide.SHORT)
    assert int(double_top["signal"].iloc[fire]) == 0


def _double_top_tape(*, invalidate: bool, n: int = 90) -> tuple[pd.DataFrame, int]:
    """Two matched swing highs, intervening low, then neckline break or second-high fail."""
    close, high, low, open_ = _planted_swings_background(n)
    first_high, neck_bar, second_high, fire = 22, 34, 46, 58
    high[first_high] = 110.0
    close[first_high] = 108.0
    low[neck_bar] = 90.0
    close[neck_bar] = 92.0
    high[second_high] = 110.1
    close[second_high] = 108.0
    if invalidate:
        # Close through the second peak. Not a two-low neckline break.
        close[fire] = 112.0
        high[fire] = 113.0
        low[fire] = 108.0
        open_[fire] = 108.0
    else:
        # Confirmed close through the intervening low.
        close[fire] = 88.0
        low[fire] = 87.0
        high[fire] = 92.0
        open_[fire] = 92.0
    candles = _ohlcv(_hourly(n, start="2024-01-03"), close, high=high, low=low, open_=open_)
    return candles, fire


def test_double_top_neckline_break_schema_and_short_entry() -> None:
    candles, fire = _double_top_tape(invalidate=False)
    signals = _signals("double_top_neckline_break", candles, side=SignalSide.SHORT)
    for column in ("signal", "side", "score", "reason", "first_high", "second_high", "neckline"):
        assert column in signals.columns
    assert int(signals["signal"].iloc[0]) == 0
    assert int(signals["signal"].iloc[fire]) == -1
    assert int((signals["signal"] == -1).sum()) >= 1
    assert int((signals["signal"] == 1).sum()) == 0
    assert signals["neckline"].iloc[fire] == pytest.approx(90.0)
    restest = _signals("equal_high_low_restest_fade", candles, side=SignalSide.SHORT)
    assert int(restest["signal"].iloc[fire]) == 0
    # Distinct file/geometry: double-bottom does not fire SHORT on two-high neckline.
    bottom = _signals("double_bottom_neckline_break", candles, side=SignalSide.SHORT)
    assert int(bottom["signal"].iloc[fire]) == 0


def test_double_top_neckline_break_long_invalidation() -> None:
    candles, fire = _double_top_tape(invalidate=True)
    signals = _signals("double_top_neckline_break", candles)
    assert int(signals["signal"].iloc[0]) == 0
    assert int(signals["signal"].iloc[fire]) == 1
    assert int((signals["signal"] == 1).sum()) >= 1
    assert int((signals["signal"] == -1).sum()) == 0
    assert signals["second_high"].iloc[fire] == pytest.approx(110.1)
    # Invalidation is not a double-bottom neckline break of two lows.
    bottom = _signals("double_bottom_neckline_break", candles)
    assert int(bottom["signal"].iloc[fire]) == 0


def _ascending_triangle_tape(*, long_side: bool, n: int = 90) -> tuple[pd.DataFrame, int]:
    """Rising lows into a flat cap (LONG) or falling highs into a flat floor (SHORT)."""
    close, high, low, open_ = _planted_swings_background(n)
    a, b, c, d, fire = 24, 36, 48, 60, 66
    volume = np.full(n, 1_000.0)
    volume[fire] = 3_000.0
    if long_side:
        low[a] = 85.0
        close[a] = 86.0
        high[b] = 110.0
        close[b] = 108.0
        low[c] = 93.0
        close[c] = 94.0
        high[d] = 110.05
        close[d] = 108.0
        close[fire] = 111.5
        high[fire] = 112.5
        low[fire] = 108.0
        open_[fire] = 108.0
    else:
        high[a] = 115.0
        close[a] = 113.0
        low[b] = 90.0
        close[b] = 92.0
        high[c] = 107.0
        close[c] = 105.0
        low[d] = 90.05
        close[d] = 92.0
        close[fire] = 88.0
        low[fire] = 87.0
        high[fire] = 92.0
        open_[fire] = 92.0
    candles = _ohlcv(_hourly(n, start="2024-01-03"), close, high=high, low=low, open_=open_)
    candles["volume"] = volume
    candles["turnover"] = candles["volume"] * candles["close"]
    return candles, fire


def test_ascending_triangle_break_schema_and_long_entry() -> None:
    candles, fire = _ascending_triangle_tape(long_side=True)
    signals = _signals("ascending_triangle_break", candles)
    for column in ("signal", "side", "score", "reason", "cap", "floor", "vol_mean"):
        assert column in signals.columns
    assert int(signals["signal"].iloc[0]) == 0
    assert int(signals["signal"].iloc[fire]) == 1
    assert int((signals["signal"] == 1).sum()) >= 1
    assert int((signals["signal"] == -1).sum()) == 0
    assert signals["cap"].iloc[fire] == pytest.approx(110.05)
    # Quiet volume on the break bar is not a triangle break.
    quiet = candles.copy()
    quiet.loc[quiet.index[fire], "volume"] = 500.0
    quiet.loc[quiet.index[fire], "turnover"] = 500.0 * float(quiet["close"].iloc[fire])
    assert int(_signals("ascending_triangle_break", quiet)["signal"].iloc[fire]) == 0
    # Compression-then-thrust is a different family (no triangle geometry required).
    thrust = _signals("range_compression_volume_thrust", candles)
    assert int(thrust["signal"].iloc[fire]) == 0


def test_ascending_triangle_break_short_descending_entry() -> None:
    candles, fire = _ascending_triangle_tape(long_side=False)
    signals = _signals("ascending_triangle_break", candles, side=SignalSide.SHORT)
    assert int(signals["signal"].iloc[0]) == 0
    assert int(signals["signal"].iloc[fire]) == -1
    assert int((signals["signal"] == -1).sum()) >= 1
    assert int((signals["signal"] == 1).sum()) == 0
    assert signals["floor"].iloc[fire] == pytest.approx(90.0)
    inside = _signals("inside_bar_breakout", candles, side=SignalSide.SHORT)
    thrust = _signals("range_compression_volume_thrust", candles, side=SignalSide.SHORT)
    assert int(inside["signal"].iloc[fire]) == 0
    assert int(thrust["signal"].iloc[fire]) == 0
    nr7 = _signals("nr7_breakout", candles, side=SignalSide.SHORT)
    assert "nr7_high" not in signals.columns
    assert "cap" not in nr7.columns


def _prior_day_extreme_tape(*, long_side: bool, held_break: bool = False) -> tuple[pd.DataFrame, int]:
    """Prior UTC day box H=110 / L=90, then a next-day tag that closes back inside."""
    index, close, high, low, open_ = _utc_day_box_tape()
    bar = _day1_sweep_iloc(index)
    if long_side:
        # Tag prior-day low, close back inside the day box (not a held breakdown).
        low[bar] = 85.0
        close[bar] = 95.0
        open_[bar] = 96.0
        high[bar] = 97.0
        if held_break:
            close[bar] = 84.0
            high[bar] = 88.0
            open_[bar] = 88.0
    else:
        # Tag prior-day high, close back inside the day box (not a held breakout).
        high[bar] = 115.0
        close[bar] = 105.0
        open_[bar] = 104.0
        low[bar] = 103.0
        if held_break:
            close[bar] = 116.0
            low[bar] = 112.0
            open_[bar] = 112.0
    candles = _ohlcv(index, close, high=high, low=low, open_=open_)
    return candles, bar


def test_prior_day_extreme_reject_schema_and_long_entry() -> None:
    from research.validate import strategy_kit

    # Quant lock: close-inside is fixed True; only touch_tol_atr is searched.
    _factory, base, space = strategy_kit("prior_day_extreme_reject", SignalSide.LONG)
    assert base.require_close_inside is True
    assert space["touch_tol_atr"] == [0.0, 0.10]
    extra = {k for k in space if k not in {"take_profit_pct", "stop_loss_pct"}}
    assert extra == {"touch_tol_atr"}
    candles, fire = _prior_day_extreme_tape(long_side=True)
    signals = _signals("prior_day_extreme_reject", candles)
    for column in ("signal", "side", "score", "reason", "prior_high", "prior_low"):
        assert column in signals.columns
    assert "pivot" not in signals.columns
    assert "r1" not in signals.columns
    assert "s1" not in signals.columns
    assert int(signals["signal"].iloc[0]) == 0
    assert int(signals["signal"].iloc[fire]) == 1
    assert int((signals["signal"] == 1).sum()) >= 1
    assert int((signals["signal"] == -1).sum()) == 0
    assert signals["prior_high"].iloc[fire] == pytest.approx(110.0)
    assert signals["prior_low"].iloc[fire] == pytest.approx(90.0)
    # Held breakdown (close stays through the low) is not a reject.
    held, _ = _prior_day_extreme_tape(long_side=True, held_break=True)
    assert int(_signals("prior_day_extreme_reject", held)["signal"].iloc[fire]) == 0
    # Weak-volume UTC-day fade is a different family (no close-inside required).
    session = _signals("session_boundary_volume_fade", candles)
    assert int(session["signal"].iloc[fire]) == 0
    # Floor-pivot breakout trades P/R1/S1, not a failed H/L tag.
    pivot = _signals("prior_day_pivot_breakout", candles)
    assert int(pivot["signal"].iloc[fire]) == 0


def test_prior_day_extreme_reject_short_entry() -> None:
    candles, fire = _prior_day_extreme_tape(long_side=False)
    signals = _signals("prior_day_extreme_reject", candles, side=SignalSide.SHORT)
    assert int(signals["signal"].iloc[0]) == 0
    assert int(signals["signal"].iloc[fire]) == -1
    assert int((signals["signal"] == -1).sum()) >= 1
    assert int((signals["signal"] == 1).sum()) == 0
    assert signals["prior_high"].iloc[fire] == pytest.approx(110.0)
    held, _ = _prior_day_extreme_tape(long_side=False, held_break=True)
    assert int(
        _signals("prior_day_extreme_reject", held, side=SignalSide.SHORT)["signal"].iloc[fire]
    ) == 0
    # Wednesday tape is not a Monday weekend-box sweep or a Monday-open reclaim.
    monday = _signals("monday_range_sweep_reversal", candles, side=SignalSide.SHORT)
    week_open = _signals("week_open_reclaim", candles, side=SignalSide.SHORT)
    restest = _signals("equal_high_low_restest_fade", candles, side=SignalSide.SHORT)
    assert int(monday["signal"].iloc[fire]) == 0
    assert int(week_open["signal"].iloc[fire]) == 0
    assert int(restest["signal"].iloc[fire]) == 0
    assert "weekend_mid" not in signals.columns
    assert "equal_high" not in signals.columns
    assert "neckline" not in signals.columns


def _failed_range_break_tape(
    *,
    long_side: bool,
    held_break: bool = False,
    blow_through: bool = False,
    delay: int = 1,
) -> tuple[pd.DataFrame, int, int]:
    """Rolling 20-bar box 110/90 after a tight prior UTC day, then a close-through fail.

    Prior UTC day stays ~101/99 so this is not ``prior_day_extreme_reject``.
    Volume is flat so this is not a thrust / NR7-volume family.
    """
    n = 50
    index = _hourly(n, start="2024-01-02")
    close = np.full(n, 100.0)
    high = np.full(n, 101.0)
    low = np.full(n, 99.0)
    open_ = np.full(n, 100.0)
    # Jan 3 onwards: a wide rolling box distinct from yesterday's UTC H/L.
    high[24:] = 110.0
    low[24:] = 90.0
    break_i = 44
    fire = break_i + delay
    if long_side:
        # Close through the 20-bar low, then back above it (still inside the box).
        low[break_i] = 84.0
        close[break_i] = 85.0
        open_[break_i] = 92.0
        high[break_i] = 93.0
        # Stay through the low until `fire` so delay tests the fail window, not a first fade.
        for j in range(break_i + 1, min(fire, n)):
            close[j] = 84.0
            high[j] = 88.0
            low[j] = 82.0
            open_[j] = 86.0
        if fire < n:
            if held_break:
                close[fire] = 84.0
                high[fire] = 88.0
                low[fire] = 82.0
                open_[fire] = 86.0
            elif blow_through:
                close[fire] = 112.0
                high[fire] = 114.0
                low[fire] = 88.0
                open_[fire] = 88.0
            else:
                close[fire] = 95.0
                high[fire] = 97.0
                low[fire] = 88.0
                open_[fire] = 86.0
    else:
        high[break_i] = 116.0
        close[break_i] = 115.0
        open_[break_i] = 108.0
        low[break_i] = 107.0
        for j in range(break_i + 1, min(fire, n)):
            close[j] = 116.0
            high[j] = 118.0
            low[j] = 112.0
            open_[j] = 114.0
        if fire < n:
            if held_break:
                close[fire] = 116.0
                high[fire] = 118.0
                low[fire] = 112.0
                open_[fire] = 114.0
            elif blow_through:
                close[fire] = 85.0
                high[fire] = 108.0
                low[fire] = 84.0
                open_[fire] = 108.0
            else:
                close[fire] = 105.0
                high[fire] = 114.0
                low[fire] = 104.0
                open_[fire] = 114.0
    candles = _ohlcv(index, close, high=high, low=low, open_=open_)
    return candles, break_i, fire


def test_failed_range_break_reversion_schema_and_long_entry() -> None:
    from research.validate import strategy_kit

    _factory, base, space = strategy_kit("failed_range_break_reversion", SignalSide.LONG)
    assert base.require_close_inside is True
    assert space["lookback"] == [16, 20]
    assert space["max_bars_since_break"] == [2, 3]
    extra = {k for k in space if k not in {"take_profit_pct", "stop_loss_pct"}}
    assert extra == {"lookback", "max_bars_since_break"}
    assert "vol_lookback" not in extra
    assert "thrust_mult" not in extra
    candles, break_i, fire = _failed_range_break_tape(long_side=True)
    signals = _signals("failed_range_break_reversion", candles)
    for column in ("signal", "side", "score", "reason", "range_high", "range_low"):
        assert column in signals.columns
    assert "volume_ma" not in signals.columns
    assert "prior_high" not in signals.columns
    assert int(signals["signal"].iloc[0]) == 0
    assert int(signals["signal"].iloc[break_i]) == 0
    assert int(signals["signal"].iloc[fire]) == 1
    assert int((signals["signal"] == 1).sum()) >= 1
    assert int((signals["signal"] == -1).sum()) == 0
    assert signals["range_high"].iloc[break_i] == pytest.approx(110.0)
    assert signals["range_low"].iloc[break_i] == pytest.approx(90.0)
    held, _, held_fire = _failed_range_break_tape(long_side=True, held_break=True)
    assert int(_signals("failed_range_break_reversion", held)["signal"].iloc[held_fire]) == 0
    through, _, through_fire = _failed_range_break_tape(long_side=True, blow_through=True)
    assert int(
        _signals("failed_range_break_reversion", through)["signal"].iloc[through_fire]
    ) == 0
    late, _, late_fire = _failed_range_break_tape(long_side=True, delay=4)
    assert int(_signals("failed_range_break_reversion", late)["signal"].iloc[late_fire]) == 0
    # Heavy volume does not gate this family; thrust still needs compression.
    heavy = candles.copy()
    heavy.loc[heavy.index[fire], "volume"] = 50_000.0
    heavy.loc[heavy.index[fire], "turnover"] = 50_000.0 * float(heavy["close"].iloc[fire])
    assert int(_signals("failed_range_break_reversion", heavy)["signal"].iloc[fire]) == 1
    assert int(_signals("range_compression_volume_thrust", candles)["signal"].iloc[fire]) == 0
    assert int(_signals("prior_day_extreme_reject", candles)["signal"].iloc[fire]) == 0
    nr7 = _signals("nr7_breakout", candles)
    assert "nr7_high" not in signals.columns
    assert "box_high" not in nr7.columns


def test_failed_range_break_reversion_short_entry() -> None:
    candles, break_i, fire = _failed_range_break_tape(long_side=False)
    signals = _signals("failed_range_break_reversion", candles, side=SignalSide.SHORT)
    assert int(signals["signal"].iloc[0]) == 0
    assert int(signals["signal"].iloc[break_i]) == 0
    assert int(signals["signal"].iloc[fire]) == -1
    assert int((signals["signal"] == -1).sum()) >= 1
    assert int((signals["signal"] == 1).sum()) == 0
    assert signals["range_high"].iloc[break_i] == pytest.approx(110.0)
    held, _, held_fire = _failed_range_break_tape(long_side=False, held_break=True)
    assert int(
        _signals("failed_range_break_reversion", held, side=SignalSide.SHORT)["signal"].iloc[
            held_fire
        ]
    ) == 0
    through, _, through_fire = _failed_range_break_tape(long_side=False, blow_through=True)
    assert int(
        _signals("failed_range_break_reversion", through, side=SignalSide.SHORT)["signal"].iloc[
            through_fire
        ]
    ) == 0
    triangle = _signals("ascending_triangle_break", candles, side=SignalSide.SHORT)
    prior_day = _signals("prior_day_extreme_reject", candles, side=SignalSide.SHORT)
    donchian = _signals("donchian_breakout", candles, side=SignalSide.SHORT)
    assert int(triangle["signal"].iloc[fire]) == 0
    assert int(prior_day["signal"].iloc[fire]) == 0
    # Donchian follows the break bar, not the fail-back-inside bar.
    assert int(donchian["signal"].iloc[fire]) == 0
    assert int(signals["signal"].iloc[break_i]) == 0
    assert "neckline" not in signals.columns
    assert "vol_mean" not in signals.columns


def _asia_london_iloc(index: pd.DatetimeIndex, stamp: str) -> int:
    return int(index.get_loc(pd.Timestamp(stamp, tz="UTC")))


def _asia_range_london_tape(
    *,
    long_side: bool,
    held_break: bool = False,
    ny_hour: bool = False,
    asia_hour: bool = False,
    london_0700: bool = False,
) -> tuple[pd.DataFrame, int]:
    """Jan 3 Asia box 110/90 (00:00–08:00), then a London tag that closes back inside.

    Prior UTC day stays ~101/99 so this is not ``prior_day_extreme_reject``.
    The poke is deeper than 1% so ``session_liquidity_sweep`` does not fire.
    Volume is flat. Wednesday, not a Monday weekend sweep.
    """
    n = 48
    index = _hourly(n, start="2024-01-02")
    close = np.full(n, 100.0)
    high = np.full(n, 101.0)
    low = np.full(n, 99.0)
    open_ = np.full(n, 100.0)
    # Jan 3 Asia hours: a same-day session box distinct from yesterday's UTC H/L.
    asia_start = _asia_london_iloc(index, "2024-01-03 00:00")
    asia_end = _asia_london_iloc(index, "2024-01-03 08:00")
    high[asia_start:asia_end] = 110.0
    low[asia_start:asia_end] = 90.0
    close[asia_start:asia_end] = 100.0
    if asia_hour:
        fire = _asia_london_iloc(index, "2024-01-03 04:00")
    elif ny_hour:
        fire = _asia_london_iloc(index, "2024-01-03 16:00")
    elif london_0700:
        fire = _asia_london_iloc(index, "2024-01-03 07:00")
    else:
        fire = _asia_london_iloc(index, "2024-01-03 08:00")
    if long_side:
        # Deep poke of Asia low, close back inside the Asia box (not a held breakdown).
        low[fire] = 84.0
        close[fire] = 95.0
        open_[fire] = 96.0
        high[fire] = 97.0
        if held_break:
            close[fire] = 84.0
            high[fire] = 88.0
            open_[fire] = 88.0
    else:
        high[fire] = 116.0
        close[fire] = 105.0
        open_[fire] = 104.0
        low[fire] = 103.0
        if held_break:
            close[fire] = 116.0
            low[fire] = 112.0
            open_[fire] = 112.0
    candles = _ohlcv(index, close, high=high, low=low, open_=open_)
    return candles, fire


def test_asia_range_london_reject_schema_and_long_entry() -> None:
    from research.validate import strategy_kit

    from core.strategy.asia_range_london_reject import (
        ASIA_END_HOUR,
        ASIA_START_HOUR,
        LONDON_END_HOUR,
        LONDON_START_HOUR,
    )

    # Quant lock: close-inside and session bounds are fixed; only touch_tol_atr is searched.
    _factory, base, space = strategy_kit("asia_range_london_reject", SignalSide.LONG)
    assert base.require_close_inside is True
    assert space["touch_tol_atr"] == [0.0, 0.10]
    extra = {k for k in space if k not in {"take_profit_pct", "stop_loss_pct"}}
    assert extra == {"touch_tol_atr"}
    assert "vol_lookback" not in extra
    assert "max_sweep_pct" not in extra
    assert "end_hour" not in extra
    assert ASIA_START_HOUR == 0.0
    assert ASIA_END_HOUR == 8.0
    assert LONDON_START_HOUR == 7.0
    assert LONDON_END_HOUR == 16.0
    candles, fire = _asia_range_london_tape(long_side=True)
    signals = _signals("asia_range_london_reject", candles)
    for column in ("signal", "side", "score", "reason", "range_high", "range_low"):
        assert column in signals.columns
    assert "prior_high" not in signals.columns
    assert "max_sweep_pct" not in signals.columns
    assert int(signals["signal"].iloc[0]) == 0
    assert int(signals["signal"].iloc[fire]) == 1
    assert int((signals["signal"] == 1).sum()) >= 1
    assert int((signals["signal"] == -1).sum()) == 0
    assert signals["range_high"].iloc[fire] == pytest.approx(110.0)
    assert signals["range_low"].iloc[fire] == pytest.approx(90.0)
    # Held breakdown (close stays through the Asia low) is not a reject.
    held, _ = _asia_range_london_tape(long_side=True, held_break=True)
    assert int(_signals("asia_range_london_reject", held)["signal"].iloc[fire]) == 0
    # Deep poke is not session_liquidity_sweep (1% cap) and not an Asia close-through.
    assert int(_signals("session_liquidity_sweep", candles)["signal"].iloc[fire]) == 0
    assert int(_signals("asian_range_breakout", candles)["signal"].iloc[fire]) == 0
    assert int(_signals("prior_day_extreme_reject", candles)["signal"].iloc[fire]) == 0
    assert int(_signals("failed_range_break_reversion", candles)["signal"].iloc[fire]) == 0
    # Asia hours are still forming the box; 07:00 is in the London window but
    # the Asia box is not published until 08:00. NY 16:00 is not London.
    asia, asia_i = _asia_range_london_tape(long_side=True, asia_hour=True)
    early, early_i = _asia_range_london_tape(long_side=True, london_0700=True)
    ny, ny_i = _asia_range_london_tape(long_side=True, ny_hour=True)
    assert int(_signals("asia_range_london_reject", asia)["signal"].iloc[asia_i]) == 0
    assert int(_signals("asia_range_london_reject", early)["signal"].iloc[early_i]) == 0
    assert int(_signals("asia_range_london_reject", ny)["signal"].iloc[ny_i]) == 0


def test_asia_range_london_reject_short_entry() -> None:
    candles, fire = _asia_range_london_tape(long_side=False)
    signals = _signals("asia_range_london_reject", candles, side=SignalSide.SHORT)
    assert int(signals["signal"].iloc[0]) == 0
    assert int(signals["signal"].iloc[fire]) == -1
    assert int((signals["signal"] == -1).sum()) >= 1
    assert int((signals["signal"] == 1).sum()) == 0
    assert signals["range_high"].iloc[fire] == pytest.approx(110.0)
    held, _ = _asia_range_london_tape(long_side=False, held_break=True)
    assert int(
        _signals("asia_range_london_reject", held, side=SignalSide.SHORT)["signal"].iloc[fire]
    ) == 0
    # Wednesday tape is not a Monday weekend-box sweep. Held close-through is asian_range.
    monday = _signals("monday_range_sweep_reversal", candles, side=SignalSide.SHORT)
    asian = _signals("asian_range_breakout", candles, side=SignalSide.SHORT)
    sweep = _signals("session_liquidity_sweep", candles, side=SignalSide.SHORT)
    prior_day = _signals("prior_day_extreme_reject", candles, side=SignalSide.SHORT)
    failed = _signals("failed_range_break_reversion", candles, side=SignalSide.SHORT)
    assert int(monday["signal"].iloc[fire]) == 0
    assert int(asian["signal"].iloc[fire]) == 0
    assert int(sweep["signal"].iloc[fire]) == 0
    assert int(prior_day["signal"].iloc[fire]) == 0
    assert int(failed["signal"].iloc[fire]) == 0
    # Held close through Asia high is asian_range_breakout LONG, not this fade.
    held_asia = _asia_range_london_tape(long_side=False, held_break=True)[0]
    assert int(_signals("asian_range_breakout", held_asia)["signal"].iloc[fire]) == 1
    ny, ny_i = _asia_range_london_tape(long_side=False, ny_hour=True)
    assert int(
        _signals("asia_range_london_reject", ny, side=SignalSide.SHORT)["signal"].iloc[ny_i]
    ) == 0
    assert "weekend_mid" not in signals.columns
    assert "neckline" not in signals.columns


def test_asia_range_london_reject_4h_london_bar() -> None:
    """Open-labeled 4h at 08:00 is London (07:00–16:00); 00:00/04:00 is still Asia."""
    n = 24
    index = pd.date_range("2024-01-02", periods=n, freq="4h", tz="UTC")
    close = np.full(n, 100.0)
    high = np.full(n, 101.0)
    low = np.full(n, 99.0)
    open_ = np.full(n, 100.0)
    asia_00 = int(index.get_loc(pd.Timestamp("2024-01-04 00:00", tz="UTC")))
    asia_04 = int(index.get_loc(pd.Timestamp("2024-01-04 04:00", tz="UTC")))
    london = int(index.get_loc(pd.Timestamp("2024-01-04 08:00", tz="UTC")))
    high[asia_00] = 110.0
    high[asia_04] = 110.0
    low[asia_00] = 90.0
    low[asia_04] = 90.0
    low[london] = 84.0
    close[london] = 95.0
    open_[london] = 96.0
    high[london] = 97.0
    candles = _ohlcv(index, close, high=high, low=low, open_=open_)
    signals = _signals("asia_range_london_reject", candles)
    assert int(signals["signal"].iloc[asia_00]) == 0
    assert int(signals["signal"].iloc[asia_04]) == 0
    assert int(signals["signal"].iloc[london]) == 1
    assert signals["range_high"].iloc[london] == pytest.approx(110.0)
    assert signals["range_low"].iloc[london] == pytest.approx(90.0)


def _orb_fail_iloc(index: pd.DatetimeIndex, stamp: str) -> int:
    return int(index.get_loc(pd.Timestamp(stamp, tz="UTC")))


def _orb_fail_tape(
    *,
    long_side: bool,
    held_break: bool = False,
    blow_through: bool = False,
    delay: int = 1,
    orb_bars: int = 1,
) -> tuple[pd.DataFrame, int, int]:
    """4h tape: Jan 4 first-4h ORB 110/90, then a same-day close-through that fails back inside.

    Prior UTC day stays ~101/99 so this is not ``prior_day_extreme_reject``.
    Break bar *closes through* the ORB (held vs utc_open_fail's same-bar wick fail).
    Fail close 95 sits inside the ORB but not back through a rolling ~99 Donchian.
    Volume is flat. Wednesday, not a Monday weekend sweep.
    """
    n = 24
    index = pd.date_range("2024-01-02", periods=n, freq="4h", tz="UTC")
    close = np.full(n, 100.0)
    high = np.full(n, 101.0)
    low = np.full(n, 99.0)
    open_ = np.full(n, 100.0)
    orb_00 = _orb_fail_iloc(index, "2024-01-04 00:00")
    high[orb_00] = 110.0
    low[orb_00] = 90.0
    close[orb_00] = 100.0
    open_[orb_00] = 100.0
    if orb_bars >= 2:
        orb_04 = _orb_fail_iloc(index, "2024-01-04 04:00")
        high[orb_04] = 110.0
        low[orb_04] = 90.0
        close[orb_04] = 100.0
        open_[orb_04] = 100.0
        break_i = _orb_fail_iloc(index, "2024-01-04 08:00")
    else:
        break_i = _orb_fail_iloc(index, "2024-01-04 04:00")
    fire = break_i + delay
    if long_side:
        # Close through the ORB low, then back above it (still inside the box).
        low[break_i] = 84.0
        close[break_i] = 85.0
        open_[break_i] = 92.0
        high[break_i] = 93.0
        for j in range(break_i + 1, min(fire, n)):
            close[j] = 84.0
            high[j] = 88.0
            low[j] = 82.0
            open_[j] = 86.0
        if fire < n:
            if held_break:
                close[fire] = 84.0
                high[fire] = 88.0
                low[fire] = 82.0
                open_[fire] = 86.0
            elif blow_through:
                close[fire] = 112.0
                high[fire] = 114.0
                low[fire] = 88.0
                open_[fire] = 88.0
            else:
                close[fire] = 95.0
                high[fire] = 97.0
                low[fire] = 88.0
                open_[fire] = 86.0
    else:
        high[break_i] = 116.0
        close[break_i] = 115.0
        open_[break_i] = 108.0
        low[break_i] = 107.0
        for j in range(break_i + 1, min(fire, n)):
            close[j] = 116.0
            high[j] = 118.0
            low[j] = 112.0
            open_[j] = 114.0
        if fire < n:
            if held_break:
                close[fire] = 116.0
                high[fire] = 118.0
                low[fire] = 112.0
                open_[fire] = 114.0
            elif blow_through:
                close[fire] = 85.0
                high[fire] = 108.0
                low[fire] = 84.0
                open_[fire] = 108.0
            else:
                close[fire] = 105.0
                high[fire] = 108.0
                low[fire] = 104.0
                open_[fire] = 114.0
    candles = _ohlcv(index, close, high=high, low=low, open_=open_)
    return candles, break_i, fire


def test_orb_fail_reversion_schema_and_long_entry() -> None:
    from research.validate import strategy_kit

    from core.strategy.orb_fail_reversion import ORB_BAR_HOURS

    _factory, base, space = strategy_kit("orb_fail_reversion", SignalSide.LONG)
    assert base.require_close_inside is True
    assert base.orb_bars == 1
    assert space["orb_bars"] == [1, 2]
    assert space["max_bars_since_break"] == [2, 4]
    extra = {k for k in space if k not in {"take_profit_pct", "stop_loss_pct"}}
    assert extra == {"orb_bars", "max_bars_since_break"}
    assert "vol_lookback" not in extra
    assert "lookback" not in extra
    assert "touch_tol_atr" not in extra
    assert ORB_BAR_HOURS == 4.0
    candles, break_i, fire = _orb_fail_tape(long_side=True)
    signals = _signals("orb_fail_reversion", candles)
    for column in ("signal", "side", "score", "reason", "range_high", "range_low"):
        assert column in signals.columns
    assert "prior_high" not in signals.columns
    assert "box_high" not in signals.columns
    assert "lookback" not in signals.columns
    assert int(signals["signal"].iloc[0]) == 0
    assert int(signals["signal"].iloc[break_i]) == 0
    assert int(signals["signal"].iloc[fire]) == 1
    assert int((signals["signal"] == 1).sum()) >= 1
    assert int((signals["signal"] == -1).sum()) == 0
    assert signals["range_high"].iloc[fire] == pytest.approx(110.0)
    assert signals["range_low"].iloc[fire] == pytest.approx(90.0)
    # Held breakdown (close stays through the ORB low) is not a fail-reversion.
    held, _, held_fire = _orb_fail_tape(long_side=True, held_break=True)
    assert int(_signals("orb_fail_reversion", held)["signal"].iloc[held_fire]) == 0
    through, _, through_fire = _orb_fail_tape(long_side=True, blow_through=True)
    assert int(_signals("orb_fail_reversion", through)["signal"].iloc[through_fire]) == 0
    # 4h same-day window after 04:00 is only four bars; delay=3 with max_bars=2 is late.
    late, _, late_fire = _orb_fail_tape(long_side=True, delay=3)
    tight = _factory(
        base.__class__(side=SignalSide.LONG, orb_bars=1, max_bars_since_break=2)
    )
    assert int(tight.generate_signals(late)["signal"].iloc[late_fire]) == 0
    # Heavy volume does not gate this family.
    heavy = candles.copy()
    heavy.loc[heavy.index[fire], "volume"] = 50_000.0
    heavy.loc[heavy.index[fire], "turnover"] = 50_000.0 * float(heavy["close"].iloc[fire])
    assert int(_signals("orb_fail_reversion", heavy)["signal"].iloc[fire]) == 1
    # Independence: ORB follow, rolling Donchian fail, prior-day H/L, Asia/London.
    assert int(_signals("opening_range_breakout", candles)["signal"].iloc[fire]) == 0
    assert int(_signals("utc_open_fail_reversion", candles)["signal"].iloc[fire]) == 0
    assert int(_signals("failed_range_break_reversion", candles)["signal"].iloc[fire]) == 0
    assert int(_signals("prior_day_extreme_reject", candles)["signal"].iloc[fire]) == 0
    assert int(_signals("asia_range_london_reject", candles)["signal"].iloc[fire]) == 0
    # Breakout family follows the close-through bar, not the fail-back-inside bar.
    assert int(_signals("opening_range_breakout", candles, side=SignalSide.SHORT)["signal"].iloc[break_i]) == -1
    assert int(_signals("opening_range_breakout", candles, side=SignalSide.SHORT)["signal"].iloc[fire]) == 0


def test_orb_fail_reversion_short_entry() -> None:
    candles, break_i, fire = _orb_fail_tape(long_side=False)
    signals = _signals("orb_fail_reversion", candles, side=SignalSide.SHORT)
    assert int(signals["signal"].iloc[0]) == 0
    assert int(signals["signal"].iloc[break_i]) == 0
    assert int(signals["signal"].iloc[fire]) == -1
    assert int((signals["signal"] == -1).sum()) >= 1
    assert int((signals["signal"] == 1).sum()) == 0
    assert signals["range_high"].iloc[fire] == pytest.approx(110.0)
    held, _, held_fire = _orb_fail_tape(long_side=False, held_break=True)
    assert int(
        _signals("orb_fail_reversion", held, side=SignalSide.SHORT)["signal"].iloc[held_fire]
    ) == 0
    through, _, through_fire = _orb_fail_tape(long_side=False, blow_through=True)
    assert int(
        _signals("orb_fail_reversion", through, side=SignalSide.SHORT)["signal"].iloc[through_fire]
    ) == 0
    orb = _signals("opening_range_breakout", candles, side=SignalSide.LONG)
    utc_fail = _signals("utc_open_fail_reversion", candles, side=SignalSide.SHORT)
    failed = _signals("failed_range_break_reversion", candles, side=SignalSide.SHORT)
    prior_day = _signals("prior_day_extreme_reject", candles, side=SignalSide.SHORT)
    asia = _signals("asia_range_london_reject", candles, side=SignalSide.SHORT)
    assert int(orb["signal"].iloc[fire]) == 0
    assert int(orb["signal"].iloc[break_i]) == 1
    assert int(utc_fail["signal"].iloc[fire]) == 0
    assert int(failed["signal"].iloc[fire]) == 0
    assert int(prior_day["signal"].iloc[fire]) == 0
    assert int(asia["signal"].iloc[fire]) == 0
    assert "nr7_high" not in signals.columns
    assert "neckline" not in signals.columns
    assert "vol_mean" not in signals.columns


def test_orb_fail_reversion_orb_bars_two_not_first_4h() -> None:
    """orb_bars=2 publishes at 08:00; a 04:00 close-through is still inside the forming window."""
    from research.validate import strategy_kit

    candles, break_i, fire = _orb_fail_tape(long_side=True, orb_bars=1)
    factory, base, _space = strategy_kit("orb_fail_reversion", SignalSide.LONG)
    two = factory(base.__class__(side=SignalSide.LONG, orb_bars=2, max_bars_since_break=4))
    signals = two.generate_signals(candles)
    # Default orb_bars=1 fires at 08:00. Two-bar ORB is not published at 04:00.
    assert int(signals["signal"].iloc[break_i]) == 0
    assert int(signals["signal"].iloc[fire]) == 0
    wide, wide_break, wide_fire = _orb_fail_tape(long_side=True, orb_bars=2)
    wide_signals = two.generate_signals(wide)
    assert int(wide_signals["signal"].iloc[wide_break]) == 0
    assert int(wide_signals["signal"].iloc[wide_fire]) == 1
    assert wide_signals["range_high"].iloc[wide_fire] == pytest.approx(110.0)
    assert wide_signals["range_low"].iloc[wide_fire] == pytest.approx(90.0)


def _nr7_fail_tape(
    *,
    long_side: bool,
    held_break: bool = False,
    blow_through: bool = False,
    delay: int = 1,
) -> tuple[pd.DataFrame, int, int]:
    """Hourly tape: a locked NR7 bar, then a close-through that fails back inside.

    Prior/wide bars stay 102/98 so this is not a rolling 16-bar Donchian fail,
    not a UTC-day ORB fail, and not a prior-day H/L reject. Volume is flat.
    """
    n = 32
    index = _hourly(n, start="2024-01-02")
    close = np.full(n, 100.0)
    high = np.full(n, 102.0)
    low = np.full(n, 98.0)
    open_ = np.full(n, 100.0)
    nr7_i = 12
    # Narrowest of the last 7: range 0.4 vs prior 4.0.
    high[nr7_i] = 100.2
    low[nr7_i] = 99.8
    close[nr7_i] = 100.0
    open_[nr7_i] = 100.0
    break_i = nr7_i + 1
    fire = break_i + delay
    if long_side:
        # Close through the NR7 low, then back above it (still inside the box).
        low[break_i] = 98.5
        high[break_i] = 99.5
        close[break_i] = 99.0
        open_[break_i] = 100.0
        for j in range(break_i + 1, min(fire, n)):
            close[j] = 99.0
            high[j] = 99.5
            low[j] = 98.5
            open_[j] = 99.2
        if fire < n:
            if held_break:
                close[fire] = 99.0
                high[fire] = 99.5
                low[fire] = 98.5
                open_[fire] = 99.2
            elif blow_through:
                close[fire] = 100.8
                high[fire] = 101.2
                low[fire] = 99.0
                open_[fire] = 99.2
            else:
                close[fire] = 100.0
                high[fire] = 100.5
                low[fire] = 99.5
                open_[fire] = 99.2
    else:
        high[break_i] = 101.5
        low[break_i] = 100.5
        close[break_i] = 101.0
        open_[break_i] = 100.0
        for j in range(break_i + 1, min(fire, n)):
            close[j] = 101.0
            high[j] = 101.5
            low[j] = 100.5
            open_[j] = 100.8
        if fire < n:
            if held_break:
                close[fire] = 101.0
                high[fire] = 101.5
                low[fire] = 100.5
                open_[fire] = 100.8
            elif blow_through:
                close[fire] = 99.2
                high[fire] = 100.8
                low[fire] = 98.8
                open_[fire] = 100.8
            else:
                close[fire] = 100.0
                high[fire] = 100.5
                low[fire] = 99.5
                open_[fire] = 100.8
    candles = _ohlcv(index, close, high=high, low=low, open_=open_)
    return candles, break_i, fire


def test_nr7_fail_reversion_schema_and_long_entry() -> None:
    from research.validate import strategy_kit

    from core.strategy.nr7_fail_reversion import NR7_LOOKBACK

    _factory, base, space = strategy_kit("nr7_fail_reversion", SignalSide.LONG)
    assert base.require_close_inside is True
    assert NR7_LOOKBACK == 7
    assert space["max_bars_since_break"] == [1, 3]
    extra = {k for k in space if k not in {"take_profit_pct", "stop_loss_pct"}}
    assert extra == {"max_bars_since_break"}
    assert "lookback" not in extra
    assert "orb_bars" not in extra
    assert "vol_lookback" not in extra
    assert "touch_tol_atr" not in extra
    candles, break_i, fire = _nr7_fail_tape(long_side=True)
    signals = _signals("nr7_fail_reversion", candles)
    for column in ("signal", "side", "score", "reason", "nr7_high", "nr7_low"):
        assert column in signals.columns
    assert "volume_ma" not in signals.columns
    assert "range_high" not in signals.columns
    assert "prior_high" not in signals.columns
    assert int(signals["signal"].iloc[0]) == 0
    assert int(signals["signal"].iloc[break_i]) == 0
    assert int(signals["signal"].iloc[fire]) == 1
    assert int((signals["signal"] == 1).sum()) >= 1
    assert int((signals["signal"] == -1).sum()) == 0
    assert signals["break_low"].iloc[fire] == pytest.approx(99.8)
    assert signals["break_high"].iloc[fire] == pytest.approx(100.2)
    # Held breakdown (close stays through the NR7 low) is not a fail-reversion.
    held, _, held_fire = _nr7_fail_tape(long_side=True, held_break=True)
    assert int(_signals("nr7_fail_reversion", held)["signal"].iloc[held_fire]) == 0
    through, _, through_fire = _nr7_fail_tape(long_side=True, blow_through=True)
    assert int(_signals("nr7_fail_reversion", through)["signal"].iloc[through_fire]) == 0
    late, _, late_fire = _nr7_fail_tape(long_side=True, delay=4)
    tight = _factory(base.__class__(side=SignalSide.LONG, max_bars_since_break=3))
    assert int(tight.generate_signals(late)["signal"].iloc[late_fire]) == 0
    # Heavy volume does not gate this family.
    heavy = candles.copy()
    heavy.loc[heavy.index[fire], "volume"] = 50_000.0
    heavy.loc[heavy.index[fire], "turnover"] = 50_000.0 * float(heavy["close"].iloc[fire])
    assert int(_signals("nr7_fail_reversion", heavy)["signal"].iloc[fire]) == 1
    # Independence: NR7 follow, rolling Donchian fail, ORB fail, prior-day, Asia/London.
    assert int(_signals("nr7_breakout", candles, side=SignalSide.SHORT)["signal"].iloc[break_i]) == -1
    assert int(_signals("nr7_breakout", candles, side=SignalSide.SHORT)["signal"].iloc[fire]) == 0
    assert int(_signals("failed_range_break_reversion", candles)["signal"].iloc[fire]) == 0
    assert int(_signals("orb_fail_reversion", candles)["signal"].iloc[fire]) == 0
    assert int(_signals("prior_day_extreme_reject", candles)["signal"].iloc[fire]) == 0
    assert int(_signals("asia_range_london_reject", candles)["signal"].iloc[fire]) == 0
    assert int(_signals("range_compression_volume_thrust", candles)["signal"].iloc[fire]) == 0


def test_nr7_fail_reversion_short_entry() -> None:
    candles, break_i, fire = _nr7_fail_tape(long_side=False)
    signals = _signals("nr7_fail_reversion", candles, side=SignalSide.SHORT)
    assert int(signals["signal"].iloc[0]) == 0
    assert int(signals["signal"].iloc[break_i]) == 0
    assert int(signals["signal"].iloc[fire]) == -1
    assert int((signals["signal"] == -1).sum()) >= 1
    assert int((signals["signal"] == 1).sum()) == 0
    assert signals["break_high"].iloc[fire] == pytest.approx(100.2)
    held, _, held_fire = _nr7_fail_tape(long_side=False, held_break=True)
    assert int(
        _signals("nr7_fail_reversion", held, side=SignalSide.SHORT)["signal"].iloc[held_fire]
    ) == 0
    through, _, through_fire = _nr7_fail_tape(long_side=False, blow_through=True)
    assert int(
        _signals("nr7_fail_reversion", through, side=SignalSide.SHORT)["signal"].iloc[through_fire]
    ) == 0
    nr7 = _signals("nr7_breakout", candles, side=SignalSide.LONG)
    failed = _signals("failed_range_break_reversion", candles, side=SignalSide.SHORT)
    orb = _signals("orb_fail_reversion", candles, side=SignalSide.SHORT)
    prior_day = _signals("prior_day_extreme_reject", candles, side=SignalSide.SHORT)
    asia = _signals("asia_range_london_reject", candles, side=SignalSide.SHORT)
    assert int(nr7["signal"].iloc[break_i]) == 1
    assert int(nr7["signal"].iloc[fire]) == 0
    assert int(failed["signal"].iloc[fire]) == 0
    assert int(orb["signal"].iloc[fire]) == 0
    assert int(prior_day["signal"].iloc[fire]) == 0
    assert int(asia["signal"].iloc[fire]) == 0
    assert "range_high" not in signals.columns
    assert "neckline" not in signals.columns
    assert "vol_mean" not in signals.columns


def _ib_fail_iloc(index: pd.DatetimeIndex, stamp: str) -> int:
    return int(index.get_loc(pd.Timestamp(stamp, tz="UTC")))


def _ib_fail_tape(
    *,
    long_side: bool,
    held_break: bool = False,
    blow_through: bool = False,
    delay: int = 1,
    mother_stamp: str = "2024-01-04 08:00",
) -> tuple[pd.DataFrame, int, int]:
    """4h tape: first London 4h mother, inside bar, close-through, fail back inside.

    Prior UTC day and Asia 00:00/04:00 stay ~101/99 so this is not
    ``orb_fail_reversion``, ``asia_range_london_reject``, or
    ``prior_day_extreme_reject``. The inside bar is wide vs a 2-point
    background so it is not NR7. Volume is flat. Thursday, not a Monday
    weekend sweep.
    """
    n = 24
    index = pd.date_range("2024-01-02", periods=n, freq="4h", tz="UTC")
    close = np.full(n, 100.0)
    high = np.full(n, 101.0)
    low = np.full(n, 99.0)
    open_ = np.full(n, 100.0)
    mother_i = _ib_fail_iloc(index, mother_stamp)
    high[mother_i] = 110.0
    low[mother_i] = 90.0
    close[mother_i] = 100.0
    open_[mother_i] = 100.0
    inside_i = mother_i + 1
    high[inside_i] = 105.0
    low[inside_i] = 95.0
    close[inside_i] = 100.0
    open_[inside_i] = 100.0
    break_i = inside_i + 1
    fire = break_i + delay
    if long_side:
        # Close through the mother low, then back above it (still inside the box).
        low[break_i] = 84.0
        close[break_i] = 85.0
        open_[break_i] = 92.0
        high[break_i] = 93.0
        for j in range(break_i + 1, min(fire, n)):
            close[j] = 84.0
            high[j] = 88.0
            low[j] = 82.0
            open_[j] = 86.0
        if fire < n:
            if held_break:
                close[fire] = 84.0
                high[fire] = 88.0
                low[fire] = 82.0
                open_[fire] = 86.0
            elif blow_through:
                close[fire] = 112.0
                high[fire] = 114.0
                low[fire] = 88.0
                open_[fire] = 88.0
            else:
                close[fire] = 95.0
                high[fire] = 97.0
                low[fire] = 88.0
                open_[fire] = 86.0
    else:
        high[break_i] = 116.0
        close[break_i] = 115.0
        open_[break_i] = 108.0
        low[break_i] = 107.0
        for j in range(break_i + 1, min(fire, n)):
            close[j] = 116.0
            high[j] = 118.0
            low[j] = 112.0
            open_[j] = 114.0
        if fire < n:
            if held_break:
                close[fire] = 116.0
                high[fire] = 118.0
                low[fire] = 112.0
                open_[fire] = 114.0
            elif blow_through:
                close[fire] = 85.0
                high[fire] = 108.0
                low[fire] = 84.0
                open_[fire] = 108.0
            else:
                close[fire] = 105.0
                high[fire] = 108.0
                low[fire] = 104.0
                open_[fire] = 114.0
    candles = _ohlcv(index, close, high=high, low=low, open_=open_)
    return candles, break_i, fire


def test_ib_fail_reversion_schema_and_long_entry() -> None:
    from research.validate import strategy_kit

    from core.strategy.ib_fail_reversion import (
        LONDON_FIRST_BAR_HOURS,
        LONDON_IB_OPEN_END,
        LONDON_IB_OPEN_START,
    )

    _factory, base, space = strategy_kit("ib_fail_reversion", SignalSide.LONG)
    assert base.require_close_inside is True
    assert LONDON_IB_OPEN_START == 7.0
    assert LONDON_IB_OPEN_END == 11.0
    assert LONDON_FIRST_BAR_HOURS == 4.0
    assert space["max_bars_since_break"] == [2, 4]
    extra = {k for k in space if k not in {"take_profit_pct", "stop_loss_pct"}}
    assert extra == {"max_bars_since_break"}
    assert "lookback" not in extra
    assert "orb_bars" not in extra
    assert "vol_lookback" not in extra
    assert "touch_tol_atr" not in extra
    candles, break_i, fire = _ib_fail_tape(long_side=True)
    signals = _signals("ib_fail_reversion", candles)
    for column in ("signal", "side", "score", "reason", "mother_high", "mother_low"):
        assert column in signals.columns
    assert "nr7_high" not in signals.columns
    assert "range_high" not in signals.columns
    assert "prior_high" not in signals.columns
    assert int(signals["signal"].iloc[0]) == 0
    assert int(signals["signal"].iloc[break_i]) == 0
    assert int(signals["signal"].iloc[fire]) == 1
    assert int((signals["signal"] == 1).sum()) >= 1
    assert int((signals["signal"] == -1).sum()) == 0
    assert signals["break_low"].iloc[fire] == pytest.approx(90.0)
    assert signals["break_high"].iloc[fire] == pytest.approx(110.0)
    # Held breakdown (close stays through the mother low) is not a fail-reversion.
    held, _, held_fire = _ib_fail_tape(long_side=True, held_break=True)
    assert int(_signals("ib_fail_reversion", held)["signal"].iloc[held_fire]) == 0
    through, _, through_fire = _ib_fail_tape(long_side=True, blow_through=True)
    assert int(_signals("ib_fail_reversion", through)["signal"].iloc[through_fire]) == 0
    # delay=3 with max_bars=2 is late (grid floor is 2).
    late, _, late_fire = _ib_fail_tape(long_side=True, delay=3)
    tight = _factory(base.__class__(side=SignalSide.LONG, max_bars_since_break=2))
    assert int(tight.generate_signals(late)["signal"].iloc[late_fire]) == 0
    # Heavy volume does not gate this family.
    heavy = candles.copy()
    heavy.loc[heavy.index[fire], "volume"] = 50_000.0
    heavy.loc[heavy.index[fire], "turnover"] = 50_000.0 * float(heavy["close"].iloc[fire])
    assert int(_signals("ib_fail_reversion", heavy)["signal"].iloc[fire]) == 1
    # Independence: IB follow, NR7 fail, rolling Donchian, ORB, prior-day, Asia/London.
    assert int(_signals("inside_bar_breakout", candles, side=SignalSide.SHORT)["signal"].iloc[break_i]) == -1
    assert int(_signals("inside_bar_breakout", candles, side=SignalSide.SHORT)["signal"].iloc[fire]) == 0
    assert int(_signals("nr7_fail_reversion", candles)["signal"].iloc[fire]) == 0
    assert int(_signals("failed_range_break_reversion", candles)["signal"].iloc[fire]) == 0
    assert int(_signals("orb_fail_reversion", candles)["signal"].iloc[fire]) == 0
    assert int(_signals("prior_day_extreme_reject", candles)["signal"].iloc[fire]) == 0
    assert int(_signals("asia_range_london_reject", candles)["signal"].iloc[fire]) == 0
    assert int(_signals("engulfing_reversal", candles)["signal"].iloc[fire]) == 0
    # UTC-midnight / first-4h mother is not the locked London first 4h.
    utc_mother, _, utc_fire = _ib_fail_tape(long_side=True, mother_stamp="2024-01-04 00:00")
    assert int(_signals("ib_fail_reversion", utc_mother)["signal"].iloc[utc_fire]) == 0


def test_ib_fail_reversion_short_entry() -> None:
    candles, break_i, fire = _ib_fail_tape(long_side=False)
    signals = _signals("ib_fail_reversion", candles, side=SignalSide.SHORT)
    assert int(signals["signal"].iloc[0]) == 0
    assert int(signals["signal"].iloc[break_i]) == 0
    assert int(signals["signal"].iloc[fire]) == -1
    assert int((signals["signal"] == -1).sum()) >= 1
    assert int((signals["signal"] == 1).sum()) == 0
    assert signals["break_high"].iloc[fire] == pytest.approx(110.0)
    held, _, held_fire = _ib_fail_tape(long_side=False, held_break=True)
    assert int(
        _signals("ib_fail_reversion", held, side=SignalSide.SHORT)["signal"].iloc[held_fire]
    ) == 0
    through, _, through_fire = _ib_fail_tape(long_side=False, blow_through=True)
    assert int(
        _signals("ib_fail_reversion", through, side=SignalSide.SHORT)["signal"].iloc[through_fire]
    ) == 0
    ib = _signals("inside_bar_breakout", candles, side=SignalSide.LONG)
    nr7 = _signals("nr7_fail_reversion", candles, side=SignalSide.SHORT)
    failed = _signals("failed_range_break_reversion", candles, side=SignalSide.SHORT)
    orb = _signals("orb_fail_reversion", candles, side=SignalSide.SHORT)
    prior_day = _signals("prior_day_extreme_reject", candles, side=SignalSide.SHORT)
    asia = _signals("asia_range_london_reject", candles, side=SignalSide.SHORT)
    engulf = _signals("engulfing_reversal", candles, side=SignalSide.SHORT)
    assert int(ib["signal"].iloc[break_i]) == 1
    assert int(ib["signal"].iloc[fire]) == 0
    assert int(nr7["signal"].iloc[fire]) == 0
    assert int(failed["signal"].iloc[fire]) == 0
    assert int(orb["signal"].iloc[fire]) == 0
    assert int(prior_day["signal"].iloc[fire]) == 0
    assert int(asia["signal"].iloc[fire]) == 0
    assert int(engulf["signal"].iloc[fire]) == 0
    assert "nr7_high" not in signals.columns
    assert "neckline" not in signals.columns
    assert "vol_mean" not in signals.columns
    utc_mother, _, utc_fire = _ib_fail_tape(long_side=False, mother_stamp="2024-01-04 00:00")
    assert int(
        _signals("ib_fail_reversion", utc_mother, side=SignalSide.SHORT)["signal"].iloc[utc_fire]
    ) == 0


def _converging_wedge_tape(
    *,
    long_side: bool,
    held_break: bool = False,
    flat_upper: bool = False,
    n: int = 90,
) -> tuple[pd.DataFrame, int]:
    """HH+HL rising wedge (SHORT) or LH+LL falling wedge (LONG), 3 touches/rail.

    Pivots sit 8 bars apart so lookback 30 and 40 both see all six swings.
    ``held_break`` keeps the prior close already through the rail so the
    first-cross at ``fire`` does not print. ``flat_upper`` equalizes the
    three highs so one rail has zero slope (triangle geometry, not a wedge).
    """
    close, high, low, open_ = _planted_swings_background(n)
    h_i = (50, 58, 66)
    l_i = (54, 62, 70)
    fire = 76
    if long_side:
        for i, px in zip(h_i, (120.0, 114.0, 109.0)):
            high[i] = px
            close[i] = px - 2.0
            open_[i] = px - 3.0
        for i, px in zip(l_i, (92.0, 90.0, 88.5)):
            low[i] = px
            close[i] = px + 2.0
            open_[i] = px + 3.0
        if held_break:
            # Already through the upper rail on the bar before fire.
            close[fire - 1] = 104.5
            high[fire - 1] = 105.5
            low[fire - 1] = 103.5
            open_[fire - 1] = 103.8
            close[fire] = 105.0
            high[fire] = 106.0
            low[fire] = 104.0
            open_[fire] = 104.5
        else:
            close[fire] = 103.5
            high[fire] = 105.0
            low[fire] = 100.0
            open_[fire] = 100.8
    else:
        highs = (112.0, 112.0, 112.0) if flat_upper else (108.0, 112.0, 115.0)
        for i, px in zip(h_i, highs):
            high[i] = px
            close[i] = px - 2.0
            open_[i] = px - 3.0
        for i, px in zip(l_i, (85.0, 92.0, 98.0)):
            low[i] = px
            close[i] = px + 2.0
            open_[i] = px + 3.0
        if held_break:
            # Background close is already below the rising lower rail.
            close[fire] = 100.0
            high[fire] = 101.5
            low[fire] = 99.0
            open_[fire] = 100.8
        else:
            # Lift the prior bar inside the wedge, then close through the lower rail.
            # Keep the break bar from engulfing the prior body (not engulfing_reversal).
            close[fire - 1] = 110.0
            high[fire - 1] = 111.0
            low[fire - 1] = 109.0
            open_[fire - 1] = 109.0
            close[fire] = 101.5
            high[fire] = 103.8
            low[fire] = 100.5
            open_[fire] = 103.2
    candles = _ohlcv(_hourly(n, start="2024-01-03"), close, high=high, low=low, open_=open_)
    return candles, fire


def test_converging_wedge_break_schema_and_long_entry() -> None:
    from research.validate import strategy_kit

    from core.strategy.converging_wedge_break import MIN_TOUCHES, PIVOT_LEFT

    _factory, base, space = strategy_kit("converging_wedge_break", SignalSide.LONG)
    assert base.min_touches == MIN_TOUCHES == 3
    assert PIVOT_LEFT == 3
    assert space["lookback"] == [30, 40]
    extra = {k for k in space if k not in {"take_profit_pct", "stop_loss_pct"}}
    assert extra == {"lookback"}
    assert "min_touches" not in extra
    assert "atr_tol" not in extra
    assert "vol_lookback" not in extra
    assert "max_bars_since_break" not in extra
    candles, fire = _converging_wedge_tape(long_side=True)
    signals = _signals("converging_wedge_break", candles)
    for column in (
        "signal",
        "side",
        "score",
        "reason",
        "upper_rail",
        "lower_rail",
        "upper_slope",
        "lower_slope",
    ):
        assert column in signals.columns
    assert "cap" not in signals.columns
    assert "vol_mean" not in signals.columns
    assert "mother_high" not in signals.columns
    assert int(signals["signal"].iloc[0]) == 0
    assert int(signals["signal"].iloc[fire]) == 1
    assert int((signals["signal"] == 1).sum()) >= 1
    assert int((signals["signal"] == -1).sum()) == 0
    # Both rails slope down and converge (upper steeper / more negative).
    assert float(signals["upper_slope"].iloc[fire]) < 0.0
    assert float(signals["lower_slope"].iloc[fire]) < 0.0
    assert float(signals["upper_slope"].iloc[fire]) < float(signals["lower_slope"].iloc[fire])
    assert float(signals["upper_rail"].iloc[fire]) > float(signals["lower_rail"].iloc[fire])
    assert int(signals["n_highs"].iloc[fire]) >= 3
    assert int(signals["n_lows"].iloc[fire]) >= 3
    # Held breakout (already through on the prior bar) does not fire.
    held, held_fire = _converging_wedge_tape(long_side=True, held_break=True)
    assert int(_signals("converging_wedge_break", held)["signal"].iloc[held_fire]) == 0
    # No volume gate: quiet or heavy volume still fires.
    quiet = candles.copy()
    quiet.loc[quiet.index[fire], "volume"] = 50.0
    quiet.loc[quiet.index[fire], "turnover"] = 50.0 * float(quiet["close"].iloc[fire])
    assert int(_signals("converging_wedge_break", quiet)["signal"].iloc[fire]) == 1
    heavy = candles.copy()
    heavy.loc[heavy.index[fire], "volume"] = 50_000.0
    heavy.loc[heavy.index[fire], "turnover"] = 50_000.0 * float(heavy["close"].iloc[fire])
    assert int(_signals("converging_wedge_break", heavy)["signal"].iloc[fire]) == 1
    # Independence: not a flat-cap triangle, not IB/NR7/ORB/range fail.
    triangle = _signals("ascending_triangle_break", candles)
    assert int(triangle["signal"].iloc[fire]) == 0
    assert int(_signals("ib_fail_reversion", candles)["signal"].iloc[fire]) == 0
    assert int(_signals("nr7_fail_reversion", candles)["signal"].iloc[fire]) == 0
    assert int(_signals("orb_fail_reversion", candles)["signal"].iloc[fire]) == 0
    assert int(_signals("failed_range_break_reversion", candles)["signal"].iloc[fire]) == 0
    assert int(_signals("asia_range_london_reject", candles)["signal"].iloc[fire]) == 0
    assert int(_signals("prior_day_extreme_reject", candles)["signal"].iloc[fire]) == 0
    assert int(_signals("engulfing_reversal", candles)["signal"].iloc[fire]) == 0
    # A two-touch flat-cap triangle is not a both-rails-sloping wedge.
    tri_candles, tri_fire = _ascending_triangle_tape(long_side=True)
    assert int(_signals("converging_wedge_break", tri_candles)["signal"].iloc[tri_fire]) == 0


def test_converging_wedge_break_short_entry() -> None:
    candles, fire = _converging_wedge_tape(long_side=False)
    signals = _signals("converging_wedge_break", candles, side=SignalSide.SHORT)
    assert int(signals["signal"].iloc[0]) == 0
    assert int(signals["signal"].iloc[fire]) == -1
    assert int((signals["signal"] == -1).sum()) >= 1
    assert int((signals["signal"] == 1).sum()) == 0
    # Both rails slope up and converge (lows rising faster than highs).
    assert float(signals["upper_slope"].iloc[fire]) > 0.0
    assert float(signals["lower_slope"].iloc[fire]) > 0.0
    assert float(signals["upper_slope"].iloc[fire]) < float(signals["lower_slope"].iloc[fire])
    held, held_fire = _converging_wedge_tape(long_side=False, held_break=True)
    assert int(
        _signals("converging_wedge_break", held, side=SignalSide.SHORT)["signal"].iloc[held_fire]
    ) == 0
    # Flat upper rail is triangle geometry, not a rising wedge.
    flat, flat_fire = _converging_wedge_tape(long_side=False, flat_upper=True)
    assert int(
        _signals("converging_wedge_break", flat, side=SignalSide.SHORT)["signal"].iloc[flat_fire]
    ) == 0
    triangle = _signals("ascending_triangle_break", candles, side=SignalSide.SHORT)
    ib = _signals("ib_fail_reversion", candles, side=SignalSide.SHORT)
    failed = _signals("failed_range_break_reversion", candles, side=SignalSide.SHORT)
    orb = _signals("orb_fail_reversion", candles, side=SignalSide.SHORT)
    prior_day = _signals("prior_day_extreme_reject", candles, side=SignalSide.SHORT)
    asia = _signals("asia_range_london_reject", candles, side=SignalSide.SHORT)
    engulf = _signals("engulfing_reversal", candles, side=SignalSide.SHORT)
    assert int(triangle["signal"].iloc[fire]) == 0
    assert int(ib["signal"].iloc[fire]) == 0
    assert int(failed["signal"].iloc[fire]) == 0
    assert int(orb["signal"].iloc[fire]) == 0
    assert int(prior_day["signal"].iloc[fire]) == 0
    assert int(asia["signal"].iloc[fire]) == 0
    assert int(engulf["signal"].iloc[fire]) == 0
    assert "cap" not in signals.columns
    assert "vol_mean" not in signals.columns
    assert "neckline" not in signals.columns
    assert "nr7_high" not in signals.columns


def _engulfing_fail_tape(
    *,
    long_side: bool,
    held_break: bool = False,
    blow_through: bool = False,
    delay: int = 1,
    same_bar_fail: bool = False,
    wick_only_fail: bool = False,
) -> tuple[pd.DataFrame, int, int, int]:
    """Hourly tape: two-bar body engulf, continuation through the extreme, fail.

    Fail is a *close* back through the engulf open (not a wick tag of the
    open, not merely back inside the high/low). Early UTC-day bars stay
    110/90 so this is not an ORB fail, not a rolling 16-bar Donchian
    fail, and not a prior-day / Asia tag. The engulf bar is *wider* than
    the recent 4-point background so it is not NR7. Volume is flat.
    Midday event, not a London IB mother. No body-efficiency gate.
    """
    n = 32
    index = _hourly(n, start="2024-01-02")
    close = np.full(n, 100.0)
    high = np.full(n, 102.0)
    low = np.full(n, 98.0)
    open_ = np.full(n, 100.0)
    # Wide first-5h box so ORB / Donchian / Asia rails sit far from the event.
    for i in range(5):
        high[i] = 110.0
        low[i] = 90.0
        close[i] = 100.0
        open_[i] = 100.0
    prior_i = 15
    engulf_i = 16
    if long_side:
        # Small bullish *body* (so it can be engulfed) with background-width
        # wicks — a 1-point prior range would be NR7 and collide with 123.
        open_[prior_i] = 99.8
        close[prior_i] = 100.4
        high[prior_i] = 102.0
        low[prior_i] = 98.0
        open_[engulf_i] = 101.0
        close[engulf_i] = 98.8
        high[engulf_i] = 103.0
        low[engulf_i] = 97.0
    else:
        # Small bearish *body*, same wide wicks so this is not NR7.
        open_[prior_i] = 100.4
        close[prior_i] = 99.8
        high[prior_i] = 102.0
        low[prior_i] = 98.0
        open_[engulf_i] = 98.8
        close[engulf_i] = 101.0
        high[engulf_i] = 103.0
        low[engulf_i] = 97.0
    break_i = engulf_i + 1
    fire = break_i if same_bar_fail else break_i + delay
    if long_side:
        # Bearish engulf open is 101.0. Fail = close back above that open.
        if same_bar_fail:
            low[break_i] = 96.0
            close[break_i] = 101.5
            high[break_i] = 102.0
            open_[break_i] = 98.5
        else:
            low[break_i] = 96.0
            close[break_i] = 96.5
            high[break_i] = 98.0
            open_[break_i] = 98.5
            for j in range(break_i + 1, min(fire, n)):
                close[j] = 96.5
                high[j] = 98.0
                low[j] = 96.0
                open_[j] = 97.0
            if fire < n and fire != break_i:
                if held_break:
                    close[fire] = 96.5
                    high[fire] = 98.0
                    low[fire] = 96.0
                    open_[fire] = 97.0
                elif blow_through:
                    close[fire] = 104.0
                    high[fire] = 105.0
                    low[fire] = 99.0
                    open_[fire] = 97.5
                elif wick_only_fail:
                    # Wick through the open, close still below it — not a fail.
                    high[fire] = 101.5
                    close[fire] = 99.5
                    low[fire] = 98.0
                    open_[fire] = 97.5
                else:
                    close[fire] = 101.5
                    high[fire] = 102.5
                    low[fire] = 100.0
                    open_[fire] = 97.5
    else:
        # Bullish engulf open is 98.8. Fail = close back below that open.
        if same_bar_fail:
            high[break_i] = 104.0
            close[break_i] = 98.0
            low[break_i] = 97.5
            open_[break_i] = 101.5
        else:
            high[break_i] = 104.0
            close[break_i] = 103.5
            low[break_i] = 101.0
            open_[break_i] = 101.5
            for j in range(break_i + 1, min(fire, n)):
                close[j] = 103.5
                high[j] = 104.0
                low[j] = 101.0
                open_[j] = 102.5
            if fire < n and fire != break_i:
                if held_break:
                    close[fire] = 103.5
                    high[fire] = 104.0
                    low[fire] = 101.0
                    open_[fire] = 102.5
                elif blow_through:
                    close[fire] = 96.0
                    high[fire] = 100.0
                    low[fire] = 95.5
                    open_[fire] = 102.0
                elif wick_only_fail:
                    low[fire] = 98.0
                    close[fire] = 99.5
                    high[fire] = 101.0
                    open_[fire] = 102.0
                else:
                    close[fire] = 98.0
                    high[fire] = 99.0
                    low[fire] = 97.5
                    open_[fire] = 102.0
    candles = _ohlcv(index, close, high=high, low=low, open_=open_)
    return candles, engulf_i, break_i, fire


def test_engulfing_fail_reversion_schema_and_long_entry() -> None:
    from research.validate import strategy_kit

    _factory, base, space = strategy_kit("engulfing_fail_reversion", SignalSide.LONG)
    assert base.require_close_inside is True
    assert base.min_efficiency == 0.0
    assert base.max_bars_since_engulf == 2
    assert space["max_bars_since_engulf"] == [1, 2]
    extra = {k for k in space if k not in {"take_profit_pct", "stop_loss_pct"}}
    assert extra == {"max_bars_since_engulf"}
    assert "min_efficiency" not in extra
    assert "require_body_eff" not in extra
    assert "max_bars_since_break" not in extra
    assert "lookback" not in extra
    assert "orb_bars" not in extra
    assert "vol_lookback" not in extra
    candles, engulf_i, break_i, fire = _engulfing_fail_tape(long_side=True)
    signals = _signals("engulfing_fail_reversion", candles)
    for column in ("signal", "side", "score", "reason", "engulf_high", "engulf_low", "engulf_open"):
        assert column in signals.columns
    assert "volume_ma" not in signals.columns
    assert "range_high" not in signals.columns
    assert "nr7_high" not in signals.columns
    assert "mother_high" not in signals.columns
    assert int(signals["signal"].iloc[0]) == 0
    assert int(signals["signal"].iloc[engulf_i]) == 0
    assert int(signals["signal"].iloc[break_i]) == 0
    assert int(signals["signal"].iloc[fire]) == 1
    assert int((signals["signal"] == 1).sum()) >= 1
    assert int((signals["signal"] == -1).sum()) == 0
    assert signals["engulf_low"].iloc[fire] == pytest.approx(97.0)
    assert signals["engulf_high"].iloc[fire] == pytest.approx(103.0)
    assert signals["engulf_open"].iloc[fire] == pytest.approx(101.0)
    assert signals["bars_since_engulf"].iloc[fire] == pytest.approx(2.0)
    # Book engulfing_reversal fires ON the bearish engulf, not on the fail.
    assert int(_signals("engulfing_reversal", candles, side=SignalSide.SHORT)["signal"].iloc[engulf_i]) == -1
    assert int(_signals("engulfing_reversal", candles, side=SignalSide.SHORT)["signal"].iloc[fire]) == 0
    # Held breakdown (close stays through the engulf low) is not a fail.
    held, _, _, held_fire = _engulfing_fail_tape(long_side=True, held_break=True)
    assert int(_signals("engulfing_fail_reversion", held)["signal"].iloc[held_fire]) == 0
    through, _, _, through_fire = _engulfing_fail_tape(long_side=True, blow_through=True)
    assert int(_signals("engulfing_fail_reversion", through)["signal"].iloc[through_fire]) == 0
    # Wick through the engulf open without a close through it is not a fail.
    wick, _, _, wick_fire = _engulfing_fail_tape(long_side=True, wick_only_fail=True)
    assert int(_signals("engulfing_fail_reversion", wick)["signal"].iloc[wick_fire]) == 0
    late, _, _, late_fire = _engulfing_fail_tape(long_side=True, delay=3)
    tight = _factory(base.__class__(side=SignalSide.LONG, max_bars_since_engulf=2))
    assert int(tight.generate_signals(late)["signal"].iloc[late_fire]) == 0
    # max_bars_since_engulf=1: same-bar extreme wick + close through the open.
    same, _, same_break, _ = _engulfing_fail_tape(long_side=True, same_bar_fail=True)
    one_bar = _factory(base.__class__(side=SignalSide.LONG, max_bars_since_engulf=1))
    assert int(one_bar.generate_signals(same)["signal"].iloc[same_break]) == 1
    assert int(_signals("engulfing_fail_reversion", same)["signal"].iloc[same_break]) == 1
    # Heavy volume does not gate this family.
    heavy = candles.copy()
    heavy.loc[heavy.index[fire], "volume"] = 50_000.0
    heavy.loc[heavy.index[fire], "turnover"] = 50_000.0 * float(heavy["close"].iloc[fire])
    assert int(_signals("engulfing_fail_reversion", heavy)["signal"].iloc[fire]) == 1
    # Independence: rolling Donchian, ORB, NR7, IB, prior-day, Asia/London.
    assert int(_signals("failed_range_break_reversion", candles)["signal"].iloc[fire]) == 0
    assert int(_signals("orb_fail_reversion", candles)["signal"].iloc[fire]) == 0
    assert int(_signals("nr7_fail_reversion", candles)["signal"].iloc[fire]) == 0
    assert int(_signals("ib_fail_reversion", candles)["signal"].iloc[fire]) == 0
    assert int(_signals("prior_day_extreme_reject", candles)["signal"].iloc[fire]) == 0
    assert int(_signals("asia_range_london_reject", candles)["signal"].iloc[fire]) == 0
    assert int(_signals("converging_wedge_break", candles)["signal"].iloc[fire]) == 0


def test_engulfing_fail_reversion_short_entry() -> None:
    candles, engulf_i, break_i, fire = _engulfing_fail_tape(long_side=False)
    signals = _signals("engulfing_fail_reversion", candles, side=SignalSide.SHORT)
    assert int(signals["signal"].iloc[0]) == 0
    assert int(signals["signal"].iloc[engulf_i]) == 0
    assert int(signals["signal"].iloc[break_i]) == 0
    assert int(signals["signal"].iloc[fire]) == -1
    assert int((signals["signal"] == -1).sum()) >= 1
    assert int((signals["signal"] == 1).sum()) == 0
    assert signals["engulf_high"].iloc[fire] == pytest.approx(103.0)
    assert signals["engulf_low"].iloc[fire] == pytest.approx(97.0)
    assert signals["engulf_open"].iloc[fire] == pytest.approx(98.8)
    # Book engulfing_reversal fires ON the bullish engulf, not on the fail.
    assert int(_signals("engulfing_reversal", candles, side=SignalSide.LONG)["signal"].iloc[engulf_i]) == 1
    assert int(_signals("engulfing_reversal", candles, side=SignalSide.LONG)["signal"].iloc[fire]) == 0
    held, _, _, held_fire = _engulfing_fail_tape(long_side=False, held_break=True)
    assert int(
        _signals("engulfing_fail_reversion", held, side=SignalSide.SHORT)["signal"].iloc[held_fire]
    ) == 0
    through, _, _, through_fire = _engulfing_fail_tape(long_side=False, blow_through=True)
    assert int(
        _signals("engulfing_fail_reversion", through, side=SignalSide.SHORT)["signal"].iloc[through_fire]
    ) == 0
    wick, _, _, wick_fire = _engulfing_fail_tape(long_side=False, wick_only_fail=True)
    assert int(
        _signals("engulfing_fail_reversion", wick, side=SignalSide.SHORT)["signal"].iloc[wick_fire]
    ) == 0
    failed = _signals("failed_range_break_reversion", candles, side=SignalSide.SHORT)
    orb = _signals("orb_fail_reversion", candles, side=SignalSide.SHORT)
    nr7 = _signals("nr7_fail_reversion", candles, side=SignalSide.SHORT)
    ib = _signals("ib_fail_reversion", candles, side=SignalSide.SHORT)
    prior_day = _signals("prior_day_extreme_reject", candles, side=SignalSide.SHORT)
    asia = _signals("asia_range_london_reject", candles, side=SignalSide.SHORT)
    wedge = _signals("converging_wedge_break", candles, side=SignalSide.SHORT)
    assert int(failed["signal"].iloc[fire]) == 0
    assert int(orb["signal"].iloc[fire]) == 0
    assert int(nr7["signal"].iloc[fire]) == 0
    assert int(ib["signal"].iloc[fire]) == 0
    assert int(prior_day["signal"].iloc[fire]) == 0
    assert int(asia["signal"].iloc[fire]) == 0
    assert int(wedge["signal"].iloc[fire]) == 0
    assert "range_high" not in signals.columns
    assert "nr7_high" not in signals.columns
    assert "neckline" not in signals.columns
    assert "vol_mean" not in signals.columns


def _wyckoff_spring_tape(
    *,
    long_side: bool,
    held_break: bool = False,
    next_bar_reclaim: bool = False,
    late_reclaim: bool = False,
) -> tuple[pd.DataFrame, int, int, int]:
    """Flat range with one unique extreme, then a spring / upthrust.

    Unique low/high keeps this off equal_high_low_restest_fade. Same-bar
    wick reclaim is not a close-through, so failed_range_break_reversion
    stays flat. Setup is a held break (close stays through the old 95/105
    rail) so it is not itself a spring. Grab sits after 16:00 UTC so
    Asia/London session fades (118–126) do not share the fire bar.
    """
    n = 48
    index = _hourly(n, start="2024-01-02")
    close = np.full(n, 100.0)
    high = np.full(n, 105.0)
    low = np.full(n, 95.0)
    open_ = np.full(n, 100.0)
    # Jan 3 18:00 / 21:00 UTC — after London 07:00–16:00.
    setup = 42
    grab = 45
    fire = grab + 1 if (next_bar_reclaim or late_reclaim) else grab
    if late_reclaim:
        fire = grab + 2
    if long_side:
        # Held breakdown print: unique range low, close stays below 95.
        low[setup] = 90.0
        high[setup] = 104.0
        close[setup] = 91.0
        open_[setup] = 96.0
        if next_bar_reclaim or late_reclaim or held_break:
            low[grab] = 85.0
            close[grab] = 88.0
            high[grab] = 97.0
            open_[grab] = 96.0
            for j in range(grab + 1, min(fire, n)):
                close[j] = 88.0
                high[j] = 97.0
                low[j] = 86.0
                open_[j] = 88.5
            if fire < n and fire != grab:
                if held_break:
                    close[fire] = 88.0
                    high[fire] = 97.0
                    low[fire] = 86.0
                    open_[fire] = 88.5
                else:
                    close[fire] = 92.0
                    high[fire] = 93.5
                    low[fire] = 87.0
                    open_[fire] = 88.5
        else:
            # Same-bar wick spring: trade below 90, close back above it.
            low[grab] = 85.0
            close[grab] = 92.0
            high[grab] = 97.0
            open_[grab] = 96.0
    else:
        # Held breakout print: unique range high, close stays above 105.
        high[setup] = 110.0
        low[setup] = 96.0
        close[setup] = 109.0
        open_[setup] = 104.0
        if next_bar_reclaim or late_reclaim or held_break:
            high[grab] = 115.0
            close[grab] = 112.0
            low[grab] = 103.0
            open_[grab] = 104.0
            for j in range(grab + 1, min(fire, n)):
                close[j] = 112.0
                high[j] = 114.0
                low[j] = 103.0
                open_[j] = 111.5
            if fire < n and fire != grab:
                if held_break:
                    close[fire] = 112.0
                    high[fire] = 114.0
                    low[fire] = 103.0
                    open_[fire] = 111.5
                else:
                    close[fire] = 108.0
                    high[fire] = 113.0
                    low[fire] = 106.5
                    open_[fire] = 111.5
        else:
            high[grab] = 115.0
            close[grab] = 108.0
            low[grab] = 103.0
            open_[grab] = 104.0
    candles = _ohlcv(index, close, high=high, low=low, open_=open_)
    return candles, setup, grab, fire


def test_wyckoff_spring_reclaim_schema_and_long_entry() -> None:
    from dataclasses import replace

    from research.validate import strategy_kit

    factory, base, space = strategy_kit("wyckoff_spring_reclaim", SignalSide.LONG)
    assert base.lookback == 20
    assert base.hold_bars == 2
    assert space["lookback"] == [16, 20]
    assert space["hold_bars"] == [1, 2]
    extra = {k for k in space if k not in {"take_profit_pct", "stop_loss_pct"}}
    assert extra == {"lookback", "hold_bars"}
    assert "vol_lookback" not in extra
    assert "max_bars_since_break" not in extra
    candles, setup, grab, fire = _wyckoff_spring_tape(long_side=True)
    signals = _signals("wyckoff_spring_reclaim", candles)
    for column in ("signal", "side", "score", "reason", "swing_high", "swing_low"):
        assert column in signals.columns
    assert "volume_ma" not in signals.columns
    assert "range_high" not in signals.columns
    assert int(signals["signal"].iloc[0]) == 0
    assert int(signals["signal"].iloc[setup]) == 0
    assert int(signals["signal"].iloc[grab]) == 1
    assert int(signals["signal"].iloc[fire]) == 1
    assert int((signals["signal"] == 1).sum()) >= 1
    assert int((signals["signal"] == -1).sum()) == 0
    assert signals["swing_low"].iloc[grab] == pytest.approx(90.0)
    held, _, held_grab, held_fire = _wyckoff_spring_tape(long_side=True, held_break=True)
    held_sig = _signals("wyckoff_spring_reclaim", held)
    assert int(held_sig["signal"].iloc[held_grab]) == 0
    assert int(held_sig["signal"].iloc[held_fire]) == 0
    late, _, late_grab, late_fire = _wyckoff_spring_tape(long_side=True, late_reclaim=True)
    late_sig = _signals("wyckoff_spring_reclaim", late)
    assert int(late_sig["signal"].iloc[late_grab]) == 0
    assert int(late_sig["signal"].iloc[late_fire]) == 0
    nxt, _, nxt_grab, nxt_fire = _wyckoff_spring_tape(long_side=True, next_bar_reclaim=True)
    nxt_sig = _signals("wyckoff_spring_reclaim", nxt)
    assert int(nxt_sig["signal"].iloc[nxt_grab]) == 0
    assert int(nxt_sig["signal"].iloc[nxt_fire]) == 1
    tight = factory(replace(base, hold_bars=1)).generate_signals(nxt)
    assert int(tight["signal"].iloc[nxt_grab]) == 0
    assert int(tight["signal"].iloc[nxt_fire]) == 0
    same_tight = factory(replace(base, hold_bars=1)).generate_signals(candles)
    assert int(same_tight["signal"].iloc[grab]) == 1
    # Same-bar wick spring is not a close-through, so 119 stays flat.
    failed = _signals("failed_range_break_reversion", candles)
    prior_day = _signals("prior_day_extreme_reject", candles)
    asia = _signals("asia_range_london_reject", candles)
    orb = _signals("orb_fail_reversion", candles)
    nr7 = _signals("nr7_fail_reversion", candles)
    ib = _signals("ib_fail_reversion", candles)
    wedge = _signals("converging_wedge_break", candles)
    engulf = _signals("engulfing_fail_reversion", candles)
    assert int(failed["signal"].iloc[grab]) == 0
    assert int(prior_day["signal"].iloc[grab]) == 0
    assert int(asia["signal"].iloc[grab]) == 0
    assert int(orb["signal"].iloc[grab]) == 0
    assert int(nr7["signal"].iloc[grab]) == 0
    assert int(ib["signal"].iloc[grab]) == 0
    assert int(wedge["signal"].iloc[grab]) == 0
    assert int(engulf["signal"].iloc[grab]) == 0
    heavy = candles.copy()
    heavy.loc[heavy.index[grab], "volume"] = 50_000.0
    assert int(_signals("wyckoff_spring_reclaim", heavy)["signal"].iloc[grab]) == 1


def test_wyckoff_spring_reclaim_short_entry() -> None:
    candles, _setup, grab, fire = _wyckoff_spring_tape(long_side=False)
    signals = _signals("wyckoff_spring_reclaim", candles, side=SignalSide.SHORT)
    assert int(signals["signal"].iloc[grab]) == -1
    assert int(signals["signal"].iloc[fire]) == -1
    assert int((signals["signal"] == -1).sum()) >= 1
    assert int((signals["signal"] == 1).sum()) == 0
    assert signals["swing_high"].iloc[grab] == pytest.approx(110.0)
    held, _, held_grab, held_fire = _wyckoff_spring_tape(long_side=False, held_break=True)
    held_sig = _signals("wyckoff_spring_reclaim", held, side=SignalSide.SHORT)
    assert int(held_sig["signal"].iloc[held_grab]) == 0
    assert int(held_sig["signal"].iloc[held_fire]) == 0
    nxt, _, nxt_grab, nxt_fire = _wyckoff_spring_tape(long_side=False, next_bar_reclaim=True)
    nxt_sig = _signals("wyckoff_spring_reclaim", nxt, side=SignalSide.SHORT)
    assert int(nxt_sig["signal"].iloc[nxt_grab]) == 0
    assert int(nxt_sig["signal"].iloc[nxt_fire]) == -1
    failed = _signals("failed_range_break_reversion", candles, side=SignalSide.SHORT)
    prior_day = _signals("prior_day_extreme_reject", candles, side=SignalSide.SHORT)
    asia = _signals("asia_range_london_reject", candles, side=SignalSide.SHORT)
    orb = _signals("orb_fail_reversion", candles, side=SignalSide.SHORT)
    nr7 = _signals("nr7_fail_reversion", candles, side=SignalSide.SHORT)
    ib = _signals("ib_fail_reversion", candles, side=SignalSide.SHORT)
    wedge = _signals("converging_wedge_break", candles, side=SignalSide.SHORT)
    engulf = _signals("engulfing_fail_reversion", candles, side=SignalSide.SHORT)
    assert int(failed["signal"].iloc[grab]) == 0
    assert int(prior_day["signal"].iloc[grab]) == 0
    assert int(asia["signal"].iloc[grab]) == 0
    assert int(orb["signal"].iloc[grab]) == 0
    assert int(nr7["signal"].iloc[grab]) == 0
    assert int(ib["signal"].iloc[grab]) == 0
    assert int(wedge["signal"].iloc[grab]) == 0
    assert int(engulf["signal"].iloc[grab]) == 0
    assert "range_high" not in signals.columns
    assert "nr7_high" not in signals.columns
    assert "neckline" not in signals.columns
    assert "vol_mean" not in signals.columns


def _prior_close_magnet_tape(*, long_side: bool, drop: float = 3.0) -> tuple[pd.DataFrame, int]:
    """Flat 100-tape, then one close stretched ``drop`` away from the magnet."""
    n = 50
    fire = 40
    close = np.full(n, 100.0)
    high = np.full(n, 100.5)
    low = np.full(n, 99.5)
    if long_side:
        close[fire] = 100.0 - drop
        high[fire] = close[fire] + 0.5
        low[fire] = close[fire] - 0.5
    else:
        close[fire] = 100.0 + drop
        high[fire] = close[fire] + 0.5
        low[fire] = close[fire] - 0.5
    candles = _ohlcv(_hourly(n), close, high=high, low=low)
    return candles, fire


def test_prior_close_magnet_fade_schema_and_long_entry() -> None:
    from dataclasses import replace

    from research.validate import strategy_kit

    factory, base, space = strategy_kit("prior_close_magnet_fade", SignalSide.LONG)
    assert base.atr_n == 20
    assert base.k == pytest.approx(1.2)
    assert space["k"] == [1.2, 1.4]
    assert "atr_n" not in space
    extra = {k for k in space if k not in {"take_profit_pct", "stop_loss_pct"}}
    assert extra == {"k"}
    assert "vol_lookback" not in extra
    assert "lookback" not in extra
    candles, fire = _prior_close_magnet_tape(long_side=True, drop=3.0)
    signals = _signals("prior_close_magnet_fade", candles)
    for column in ("signal", "side", "score", "reason", "prior_close", "atr", "stretch"):
        assert column in signals.columns
    assert "volume_ma" not in signals.columns
    assert "rolling_vwap" not in signals.columns
    assert "week_open" not in signals.columns
    assert "mean_clv" not in signals.columns
    assert "swing_low" not in signals.columns
    assert int(signals["signal"].iloc[0]) == 0
    assert int(signals["signal"].iloc[fire]) == 1
    assert int((signals["signal"] == 1).sum()) >= 1
    assert int((signals["signal"] == -1).sum()) == 0
    assert signals["prior_close"].iloc[fire] == pytest.approx(100.0)
    assert float(signals["stretch"].iloc[fire]) <= -1.4
    # A 1.35-ATR-ish dip clears k=1.2 but not k=1.4.
    mild, mild_fire = _prior_close_magnet_tape(long_side=True, drop=1.35)
    mild_sig = _signals("prior_close_magnet_fade", mild)
    assert int(mild_sig["signal"].iloc[mild_fire]) == 1
    tight = factory(replace(base, k=1.4)).generate_signals(mild)
    assert int(tight["signal"].iloc[mild_fire]) == 0
    # Sub-threshold drift is not a magnet fade.
    tiny, tiny_fire = _prior_close_magnet_tape(long_side=True, drop=0.8)
    assert int(_signals("prior_close_magnet_fade", tiny)["signal"].iloc[tiny_fire]) == 0
    # Spent 118–127 families stay flat on a one-bar prior-close stretch.
    spent = (
        "prior_day_extreme_reject",
        "failed_range_break_reversion",
        "asia_range_london_reject",
        "orb_fail_reversion",
        "nr7_fail_reversion",
        "ib_fail_reversion",
        "converging_wedge_break",
        "engulfing_fail_reversion",
        "wyckoff_spring_reclaim",
    )
    for name in spent:
        assert int(_signals(name, candles)["signal"].iloc[fire]) == 0
    heavy = candles.copy()
    heavy.loc[heavy.index[fire], "volume"] = 50_000.0
    assert int(_signals("prior_close_magnet_fade", heavy)["signal"].iloc[fire]) == 1


def test_prior_close_magnet_fade_short_entry() -> None:
    from dataclasses import replace

    from research.validate import strategy_kit

    factory, base, _space = strategy_kit("prior_close_magnet_fade", SignalSide.SHORT)
    candles, fire = _prior_close_magnet_tape(long_side=False, drop=3.0)
    signals = _signals("prior_close_magnet_fade", candles, side=SignalSide.SHORT)
    assert int(signals["signal"].iloc[fire]) == -1
    assert int((signals["signal"] == -1).sum()) >= 1
    assert int((signals["signal"] == 1).sum()) == 0
    assert signals["prior_close"].iloc[fire] == pytest.approx(100.0)
    assert float(signals["stretch"].iloc[fire]) >= 1.4
    mild, mild_fire = _prior_close_magnet_tape(long_side=False, drop=1.35)
    mild_sig = _signals("prior_close_magnet_fade", mild, side=SignalSide.SHORT)
    assert int(mild_sig["signal"].iloc[mild_fire]) == -1
    tight = factory(replace(base, k=1.4)).generate_signals(mild)
    assert int(tight["signal"].iloc[mild_fire]) == 0
    tiny, tiny_fire = _prior_close_magnet_tape(long_side=False, drop=0.8)
    assert int(
        _signals("prior_close_magnet_fade", tiny, side=SignalSide.SHORT)["signal"].iloc[tiny_fire]
    ) == 0
    spent = (
        "prior_day_extreme_reject",
        "failed_range_break_reversion",
        "asia_range_london_reject",
        "orb_fail_reversion",
        "nr7_fail_reversion",
        "ib_fail_reversion",
        "converging_wedge_break",
        "engulfing_fail_reversion",
        "wyckoff_spring_reclaim",
    )
    for name in spent:
        assert int(_signals(name, candles, side=SignalSide.SHORT)["signal"].iloc[fire]) == 0


def _classic_floor_pivot_tape(
    *,
    long_side: bool,
    held_through_pivot: bool = False,
    miss_tag: bool = False,
) -> tuple[pd.DataFrame, int]:
    """Prior UTC day with R1/S1 ≠ raw H/L, then a next-day pivot reject.

    Bullish prior close (LONG): S1 sits above yesterday's low so a S1 tag is
    not a raw H/L reject. Bearish prior close (SHORT): R1 sits below
    yesterday's high so an R1 tag is not a raw H/L reject. Volume stays
    flat so session-mid / week-open reclaim families stay quiet.
    """
    n = 72
    index = _hourly(n, start="2024-01-02")
    close = np.full(n, 100.0)
    high = np.full(n, 102.0)
    low = np.full(n, 98.0)
    open_ = np.full(n, 100.0)
    # Prior UTC day (Jan 2) box H=110 / L=90. Close away from the mid so
    # floor R1/S1 separate from raw H/L.
    high[5] = 110.0
    low[8] = 90.0
    if long_side:
        # C=108 -> P=102.667, R1=115.333, S1=95.333 (S1 > L).
        close[23] = 108.0
        high[23] = 109.0
        low[23] = 107.0
        open_[23] = 107.5
        # Keep day-1 prints near P so this is not a prior-close magnet fade.
        day1 = index.normalize() == pd.Timestamp("2024-01-03", tz="UTC")
        close[day1] = 103.0
        high[day1] = 104.0
        low[day1] = 102.0
        open_[day1] = 103.0
    else:
        # C=90 -> P=96.667, R1=103.333, S1=83.333 (R1 < H).
        close[23] = 90.0
        high[23] = 91.0
        low[23] = 90.0
        open_[23] = 100.0
        day1 = index.normalize() == pd.Timestamp("2024-01-03", tz="UTC")
        close[day1] = 97.0
        high[day1] = 98.0
        low[day1] = 96.0
        open_[day1] = 97.0
    fire = _day1_sweep_iloc(index)
    if long_side:
        # Tag S1 (~95.33) without tagging prior-day low 90. Close back above P.
        low[fire] = 95.5 if miss_tag else 95.0
        close[fire] = 101.0 if held_through_pivot else 104.0
        high[fire] = 104.5
        open_[fire] = 103.0
    else:
        # Tag R1 (~103.33) without tagging prior-day high 110. Close back below P.
        high[fire] = 103.2 if miss_tag else 104.0
        close[fire] = 98.0 if held_through_pivot else 95.0
        low[fire] = 94.5
        open_[fire] = 97.0
    candles = _ohlcv(index, close, high=high, low=low, open_=open_)
    return candles, fire


def test_classic_floor_pivot_reject_schema_and_long_entry() -> None:
    from dataclasses import replace

    from research.validate import strategy_kit

    # Quant lock: P/R1/S1 formula is fixed; only touch_tol_atr is searched.
    factory, base, space = strategy_kit("classic_floor_pivot_reject", SignalSide.LONG)
    assert space["touch_tol_atr"] == [0.0, 0.10]
    assert "pivot" not in space
    assert "r1" not in space
    assert "s1" not in space
    extra = {k for k in space if k not in {"take_profit_pct", "stop_loss_pct"}}
    assert extra == {"touch_tol_atr"}
    candles, fire = _classic_floor_pivot_tape(long_side=True)
    signals = _signals("classic_floor_pivot_reject", candles)
    for column in ("signal", "side", "score", "reason", "pivot", "r1", "s1"):
        assert column in signals.columns
    assert "prior_high" not in signals.columns
    assert "week_open" not in signals.columns
    assert "session_mid" not in signals.columns
    assert "prior_close" not in signals.columns
    assert int(signals["signal"].iloc[0]) == 0
    assert int(signals["signal"].iloc[fire]) == 1
    assert int((signals["signal"] == 1).sum()) >= 1
    assert int((signals["signal"] == -1).sum()) == 0
    # Locked floor-trader formula from prior UTC day H=110, L=90, C=108.
    pivot = (110.0 + 90.0 + 108.0) / 3.0
    r1 = 2.0 * pivot - 90.0
    s1 = 2.0 * pivot - 110.0
    assert signals["pivot"].iloc[fire] == pytest.approx(pivot)
    assert signals["r1"].iloc[fire] == pytest.approx(r1)
    assert signals["s1"].iloc[fire] == pytest.approx(s1)
    assert pivot == pytest.approx((110.0 + 90.0 + 108.0) / 3.0)
    assert r1 == pytest.approx(2.0 * pivot - 90.0)
    assert s1 == pytest.approx(2.0 * pivot - 110.0)
    # Held through P (tagged S1 but close stays below P) is not a reject.
    held, _ = _classic_floor_pivot_tape(long_side=True, held_through_pivot=True)
    assert int(_signals("classic_floor_pivot_reject", held)["signal"].iloc[fire]) == 0
    # Near-miss of S1 stays flat at locked touch_tol=0; 0.10 ATR slack can tag it.
    miss, miss_fire = _classic_floor_pivot_tape(long_side=True, miss_tag=True)
    miss_sig = _signals("classic_floor_pivot_reject", miss)
    assert int(miss_sig["signal"].iloc[miss_fire]) == 0
    slack = factory(replace(base, touch_tol_atr=0.10)).generate_signals(miss)
    atr_prev = float(slack["atr"].iloc[miss_fire])
    assert atr_prev > 0.0
    s1_miss = float(slack["s1"].iloc[miss_fire])
    low_miss = float(miss["low"].iloc[miss_fire])
    if low_miss <= s1_miss + 0.10 * atr_prev:
        assert int(slack["signal"].iloc[miss_fire]) == 1
    # Neighbors stay flat: raw H/L reject, pivot breakout, session mid, week open, magnet.
    assert int(_signals("prior_day_extreme_reject", candles)["signal"].iloc[fire]) == 0
    assert int(_signals("prior_day_pivot_breakout", candles)["signal"].iloc[fire]) == 0
    assert int(_signals("prior_session_mid_reclaim", candles)["signal"].iloc[fire]) == 0
    assert int(_signals("week_open_reclaim", candles)["signal"].iloc[fire]) == 0
    assert int(_signals("prior_close_magnet_fade", candles)["signal"].iloc[fire]) == 0


def test_classic_floor_pivot_reject_short_entry() -> None:
    from dataclasses import replace

    from research.validate import strategy_kit

    factory, base, space = strategy_kit("classic_floor_pivot_reject", SignalSide.SHORT)
    extra = {k for k in space if k not in {"take_profit_pct", "stop_loss_pct"}}
    assert extra == {"touch_tol_atr"}
    assert space["touch_tol_atr"] == [0.0, 0.10]
    candles, fire = _classic_floor_pivot_tape(long_side=False)
    signals = _signals("classic_floor_pivot_reject", candles, side=SignalSide.SHORT)
    assert int(signals["signal"].iloc[0]) == 0
    assert int(signals["signal"].iloc[fire]) == -1
    assert int((signals["signal"] == -1).sum()) >= 1
    assert int((signals["signal"] == 1).sum()) == 0
    pivot = (110.0 + 90.0 + 90.0) / 3.0
    r1 = 2.0 * pivot - 90.0
    s1 = 2.0 * pivot - 110.0
    assert signals["pivot"].iloc[fire] == pytest.approx(pivot)
    assert signals["r1"].iloc[fire] == pytest.approx(r1)
    assert signals["s1"].iloc[fire] == pytest.approx(s1)
    held, _ = _classic_floor_pivot_tape(long_side=False, held_through_pivot=True)
    assert int(
        _signals("classic_floor_pivot_reject", held, side=SignalSide.SHORT)["signal"].iloc[fire]
    ) == 0
    miss, miss_fire = _classic_floor_pivot_tape(long_side=False, miss_tag=True)
    assert int(
        _signals("classic_floor_pivot_reject", miss, side=SignalSide.SHORT)["signal"].iloc[miss_fire]
    ) == 0
    slack = factory(replace(base, touch_tol_atr=0.10)).generate_signals(miss)
    atr_prev = float(slack["atr"].iloc[miss_fire])
    assert atr_prev > 0.0
    r1_miss = float(slack["r1"].iloc[miss_fire])
    high_miss = float(miss["high"].iloc[miss_fire])
    if high_miss >= r1_miss - 0.10 * atr_prev:
        assert int(slack["signal"].iloc[miss_fire]) == -1
    assert int(
        _signals("prior_day_extreme_reject", candles, side=SignalSide.SHORT)["signal"].iloc[fire]
    ) == 0
    assert int(
        _signals("prior_day_pivot_breakout", candles, side=SignalSide.SHORT)["signal"].iloc[fire]
    ) == 0
    assert int(
        _signals("prior_session_mid_reclaim", candles, side=SignalSide.SHORT)["signal"].iloc[fire]
    ) == 0
    assert int(_signals("week_open_reclaim", candles, side=SignalSide.SHORT)["signal"].iloc[fire]) == 0
    assert int(
        _signals("prior_close_magnet_fade", candles, side=SignalSide.SHORT)["signal"].iloc[fire]
    ) == 0
    # Inverse: a raw prior-day H/L reject that closes back inside the day box
    # but stays on the wrong side of P is not this family.
    extreme, extreme_fire = _prior_day_extreme_tape(long_side=False)
    assert int(
        _signals("classic_floor_pivot_reject", extreme, side=SignalSide.SHORT)["signal"].iloc[
            extreme_fire
        ]
    ) == 0


def test_classic_floor_pivot_reject_no_lookahead() -> None:
    candles, fire = _classic_floor_pivot_tape(long_side=True)
    signals = _signals("classic_floor_pivot_reject", candles)
    assert int(signals["signal"].iloc[fire]) == 1
    cut = fire + 1
    truncated = _signals("classic_floor_pivot_reject", candles.iloc[:cut])
    pd.testing.assert_series_equal(
        signals["signal"].iloc[:cut],
        truncated["signal"],
        check_names=False,
    )
    # Later bars of the fire day (and the next day) must not rewrite P/R1/S1.
    shocked = candles.copy()
    later = fire + 3
    shocked.iloc[later, shocked.columns.get_loc("high")] = 140.0
    shocked.iloc[later, shocked.columns.get_loc("low")] = 70.0
    shocked.iloc[later, shocked.columns.get_loc("close")] = 140.0
    after = _signals("classic_floor_pivot_reject", shocked)
    assert after["pivot"].iloc[fire] == pytest.approx(signals["pivot"].iloc[fire])
    assert after["r1"].iloc[fire] == pytest.approx(signals["r1"].iloc[fire])
    assert after["s1"].iloc[fire] == pytest.approx(signals["s1"].iloc[fire])
    assert int(after["signal"].iloc[fire]) == 1
    pd.testing.assert_series_equal(
        signals["signal"].iloc[:later],
        after["signal"].iloc[:later],
        check_names=False,
    )


def _failed_break_reclaim_tape(
    *,
    long_side: bool,
    held_break: bool = False,
    blow_through: bool = False,
    probe_bars: int = 2,
    single_probe: bool = False,
) -> tuple[pd.DataFrame, int, int]:
    """Rolling 20-bar box 110/90, then a multi-bar wick probe that reclaims.

    Probe bars wick beyond the *frozen* prior-bar range but do not close
    through it, so failed_range_break_reversion (119) stays flat. The first
    wick can be a Wyckoff spring/upthrust; later probe bars stay inside the
    rolling Donchian that the first wick lifted, so 127 does not re-fire
    on the reclaim bar. Prior UTC day stays ~101/99 so 118 stays flat.
    Fire sits at 21:00 UTC so London IB / Asia-London session fades do not
    share the bar.
    """
    n = 50
    index = _hourly(n, start="2024-01-02")
    close = np.full(n, 100.0)
    high = np.full(n, 101.0)
    low = np.full(n, 99.0)
    open_ = np.full(n, 100.0)
    # Jan 3 onwards: a wide rolling box distinct from yesterday's UTC H/L.
    high[24:] = 110.0
    low[24:] = 90.0
    first = 44
    n_probe = 1 if single_probe else max(2, int(probe_bars))
    fire = first + n_probe - 1
    if long_side:
        # First probe: unique wick below 90, close back inside (not a close-through).
        low[first] = 84.0
        high[first] = 97.0
        close[first] = 95.0
        open_[first] = 96.0
        for j in range(first + 1, min(fire + 1, n)):
            # Later probes stay below frozen 90 but above the first wick 84.
            low[j] = 88.0
            high[j] = 97.0
            close[j] = 95.0
            open_[j] = 94.0
        if fire < n:
            if held_break:
                close[fire] = 84.0
                high[fire] = 88.0
                low[fire] = 82.0
                open_[fire] = 86.0
            elif blow_through:
                close[fire] = 112.0
                high[fire] = 114.0
                low[fire] = 88.0
                open_[fire] = 88.0
            elif single_probe:
                low[fire] = 84.0
                high[fire] = 97.0
                close[fire] = 95.0
                open_[fire] = 96.0
    else:
        high[first] = 116.0
        low[first] = 103.0
        close[first] = 105.0
        open_[first] = 104.0
        for j in range(first + 1, min(fire + 1, n)):
            high[j] = 112.0
            low[j] = 103.0
            close[j] = 105.0
            open_[j] = 106.0
        if fire < n:
            if held_break:
                close[fire] = 116.0
                high[fire] = 118.0
                low[fire] = 112.0
                open_[fire] = 114.0
            elif blow_through:
                # Still a second probe high, but close blows through the far rail.
                close[fire] = 85.0
                high[fire] = 112.0
                low[fire] = 84.0
                open_[fire] = 108.0
            elif single_probe:
                high[fire] = 116.0
                low[fire] = 103.0
                close[fire] = 105.0
                open_[fire] = 104.0
    candles = _ohlcv(index, close, high=high, low=low, open_=open_)
    return candles, first, fire


def test_failed_break_reclaim_schema_and_long_entry() -> None:
    from dataclasses import replace

    from research.validate import strategy_kit

    from core.strategy.failed_break_reclaim import ATR_PERIOD

    factory, base, space = strategy_kit("failed_break_reclaim", SignalSide.LONG)
    assert ATR_PERIOD == 20
    assert base.require_close_inside is True
    assert base.lookback == 20
    assert base.min_probe_bars == 2
    assert space["lookback"] == [16, 20]
    assert space["min_probe_bars"] == [2, 3]
    extra = {k for k in space if k not in {"take_profit_pct", "stop_loss_pct"}}
    assert extra == {"lookback", "min_probe_bars"}
    assert "require_close_inside" not in extra
    assert "atr_n" not in extra
    assert "atr_period" not in extra
    assert "vol_lookback" not in extra
    assert "max_bars_since_break" not in extra
    assert "hold_bars" not in extra
    candles, first, fire = _failed_break_reclaim_tape(long_side=True)
    signals = _signals("failed_break_reclaim", candles)
    for column in ("signal", "side", "score", "reason", "range_high", "range_low", "probe_bars"):
        assert column in signals.columns
    assert "volume_ma" not in signals.columns
    assert "prior_high" not in signals.columns
    assert "pivot" not in signals.columns
    assert "swing_low" not in signals.columns
    assert int(signals["signal"].iloc[0]) == 0
    assert int(signals["signal"].iloc[first]) == 0
    assert int(signals["signal"].iloc[fire]) == 1
    assert int((signals["signal"] == 1).sum()) >= 1
    assert int((signals["signal"] == -1).sum()) == 0
    assert signals["range_high"].iloc[fire] == pytest.approx(110.0)
    assert signals["range_low"].iloc[fire] == pytest.approx(90.0)
    assert signals["probe_bars"].iloc[fire] == pytest.approx(2.0)
    held, _, held_fire = _failed_break_reclaim_tape(long_side=True, held_break=True)
    assert int(_signals("failed_break_reclaim", held)["signal"].iloc[held_fire]) == 0
    through, _, through_fire = _failed_break_reclaim_tape(long_side=True, blow_through=True)
    assert int(_signals("failed_break_reclaim", through)["signal"].iloc[through_fire]) == 0
    one, one_first, one_fire = _failed_break_reclaim_tape(long_side=True, single_probe=True)
    one_sig = _signals("failed_break_reclaim", one)
    assert int(one_sig["signal"].iloc[one_first]) == 0
    assert int(one_sig["signal"].iloc[one_fire]) == 0
    two_bar = candles
    tight = factory(replace(base, min_probe_bars=3)).generate_signals(two_bar)
    assert int(tight["signal"].iloc[first]) == 0
    assert int(tight["signal"].iloc[fire]) == 0
    three, _, three_fire = _failed_break_reclaim_tape(long_side=True, probe_bars=3)
    three_sig = factory(replace(base, min_probe_bars=3)).generate_signals(three)
    assert int(three_sig["signal"].iloc[three_fire]) == 1
    # Neighbors: 118 / 119 / 124 / 127 / 129 stay flat on the reclaim bar.
    spent = (
        "prior_day_extreme_reject",
        "failed_range_break_reversion",
        "ib_fail_reversion",
        "wyckoff_spring_reclaim",
        "classic_floor_pivot_reject",
    )
    for name in spent:
        assert int(_signals(name, candles)["signal"].iloc[fire]) == 0
    heavy = candles.copy()
    heavy.loc[heavy.index[fire], "volume"] = 50_000.0
    assert int(_signals("failed_break_reclaim", heavy)["signal"].iloc[fire]) == 1


def test_failed_break_reclaim_short_entry() -> None:
    from dataclasses import replace

    from research.validate import strategy_kit

    factory, base, space = strategy_kit("failed_break_reclaim", SignalSide.SHORT)
    extra = {k for k in space if k not in {"take_profit_pct", "stop_loss_pct"}}
    assert extra == {"lookback", "min_probe_bars"}
    assert space["lookback"] == [16, 20]
    assert space["min_probe_bars"] == [2, 3]
    assert base.require_close_inside is True
    candles, first, fire = _failed_break_reclaim_tape(long_side=False)
    signals = _signals("failed_break_reclaim", candles, side=SignalSide.SHORT)
    assert int(signals["signal"].iloc[0]) == 0
    assert int(signals["signal"].iloc[first]) == 0
    assert int(signals["signal"].iloc[fire]) == -1
    assert int((signals["signal"] == -1).sum()) >= 1
    assert int((signals["signal"] == 1).sum()) == 0
    assert signals["range_high"].iloc[fire] == pytest.approx(110.0)
    assert signals["range_low"].iloc[fire] == pytest.approx(90.0)
    held, _, held_fire = _failed_break_reclaim_tape(long_side=False, held_break=True)
    assert int(
        _signals("failed_break_reclaim", held, side=SignalSide.SHORT)["signal"].iloc[held_fire]
    ) == 0
    through, _, through_fire = _failed_break_reclaim_tape(long_side=False, blow_through=True)
    assert int(
        _signals("failed_break_reclaim", through, side=SignalSide.SHORT)["signal"].iloc[through_fire]
    ) == 0
    tight = factory(replace(base, min_probe_bars=3)).generate_signals(candles)
    assert int(tight["signal"].iloc[fire]) == 0
    spent = (
        "prior_day_extreme_reject",
        "failed_range_break_reversion",
        "ib_fail_reversion",
        "wyckoff_spring_reclaim",
        "classic_floor_pivot_reject",
    )
    for name in spent:
        assert int(_signals(name, candles, side=SignalSide.SHORT)["signal"].iloc[fire]) == 0
    assert "prior_high" not in signals.columns
    assert "nr7_high" not in signals.columns
    assert "pivot" not in signals.columns
    assert "swing_high" not in signals.columns


def test_failed_break_reclaim_no_lookahead() -> None:
    candles, _first, fire = _failed_break_reclaim_tape(long_side=True)
    signals = _signals("failed_break_reclaim", candles)
    assert int(signals["signal"].iloc[fire]) == 1
    cut = fire + 1
    truncated = _signals("failed_break_reclaim", candles.iloc[:cut])
    pd.testing.assert_series_equal(
        signals["signal"].iloc[:cut],
        truncated["signal"],
        check_names=False,
    )
    shocked = candles.copy()
    later = fire + 3
    shocked.iloc[later, shocked.columns.get_loc("high")] = 140.0
    shocked.iloc[later, shocked.columns.get_loc("low")] = 70.0
    shocked.iloc[later, shocked.columns.get_loc("close")] = 140.0
    after = _signals("failed_break_reclaim", shocked)
    assert after["range_high"].iloc[fire] == pytest.approx(signals["range_high"].iloc[fire])
    assert after["range_low"].iloc[fire] == pytest.approx(signals["range_low"].iloc[fire])
    assert int(after["signal"].iloc[fire]) == 1
    pd.testing.assert_series_equal(
        signals["signal"].iloc[:later],
        after["signal"].iloc[:later],
        check_names=False,
    )


def _expansion_fail_fade_tape(
    *,
    long_side: bool,
    expansion_tr: float = 4.0,
    heavy_fail_vol: bool = False,
    held_outside: bool = False,
) -> tuple[pd.DataFrame, int]:
    """Quiet ATR~1 tape, one ATR-expansion bar, then a next-bar close-inside.

    LONG: down expansion (close on the low side of the bar mid). SHORT: up
    expansion (close on the high side). Fail bar volume stays at the prior-20
    mean unless ``heavy_fail_vol``. ``held_outside`` keeps the fail close
    beyond the expansion rail so it is not a fade.
    """
    n = 50
    fire = 41
    exp = 40
    close = np.full(n, 100.0)
    high = np.full(n, 100.5)
    low = np.full(n, 99.5)
    open_ = np.full(n, 100.0)
    if long_side:
        # Down expansion: high stays near the quiet high, low stretches.
        high[exp] = 100.5
        low[exp] = 100.5 - expansion_tr
        close[exp] = low[exp] + 0.3
        open_[exp] = 100.0
        if held_outside:
            close[fire] = float(low[exp]) - 0.5
            high[fire] = close[fire] + 0.3
            low[fire] = close[fire] - 0.3
            open_[fire] = close[fire]
        else:
            close[fire] = 99.8
            high[fire] = 100.2
            low[fire] = 99.4
            open_[fire] = 97.0
    else:
        # Up expansion: low stays near the quiet low, high stretches.
        low[exp] = 99.5
        high[exp] = 99.5 + expansion_tr
        close[exp] = high[exp] - 0.3
        open_[exp] = 100.0
        if held_outside:
            close[fire] = float(high[exp]) + 0.5
            high[fire] = close[fire] + 0.3
            low[fire] = close[fire] - 0.3
            open_[fire] = close[fire]
        else:
            close[fire] = 100.2
            high[fire] = 100.6
            low[fire] = 99.8
            open_[fire] = 103.0
    candles = _ohlcv(_hourly(n), close, high=high, low=low, open_=open_)
    if heavy_fail_vol:
        candles.loc[candles.index[fire], "volume"] = 50_000.0
    return candles, fire


def test_expansion_fail_fade_schema_and_long_entry() -> None:
    from dataclasses import replace

    from research.validate import strategy_kit

    # Quant lock: atr_n and weak-vol stay fixed; only expansion_mult is searched.
    factory, base, space = strategy_kit("expansion_fail_fade", SignalSide.LONG)
    assert base.atr_n == 20
    assert base.vol_lookback == 20
    assert base.expansion_mult == pytest.approx(1.5)
    assert space["expansion_mult"] == [1.5, 2.0]
    assert "atr_n" not in space
    assert "vol_lookback" not in space
    assert "vol_period" not in space
    extra = {k for k in space if k not in {"take_profit_pct", "stop_loss_pct"}}
    assert extra == {"expansion_mult"}
    candles, fire = _expansion_fail_fade_tape(long_side=True)
    signals = _signals("expansion_fail_fade", candles)
    for column in (
        "signal",
        "side",
        "score",
        "reason",
        "atr",
        "atr_prev",
        "expansion_tr",
        "expansion_high",
        "expansion_low",
        "expansion_mid",
        "vol_mean",
    ):
        assert column in signals.columns
    assert "range_high" not in signals.columns
    assert "nr7_high" not in signals.columns
    assert "orb_high" not in signals.columns
    assert int(signals["signal"].iloc[0]) == 0
    assert int(signals["signal"].iloc[fire]) == 1
    assert int((signals["signal"] == 1).sum()) >= 1
    assert int((signals["signal"] == -1).sum()) == 0
    assert float(signals["expansion_tr"].iloc[fire]) == pytest.approx(4.0)
    assert float(signals["atr_prev"].iloc[fire]) > 0.0
    assert float(signals["expansion_tr"].iloc[fire]) > 2.0 * float(
        signals["atr_prev"].iloc[fire]
    )
    # Fail close sits inside the expansion box, toward the mid from the low.
    assert float(candles["close"].iloc[fire]) >= float(signals["expansion_low"].iloc[fire])
    assert float(candles["close"].iloc[fire]) <= float(signals["expansion_high"].iloc[fire])
    # A 1.7-ATR expansion clears 1.5 but not 2.0.
    mild, mild_fire = _expansion_fail_fade_tape(long_side=True, expansion_tr=1.7)
    mild_sig = _signals("expansion_fail_fade", mild)
    assert int(mild_sig["signal"].iloc[mild_fire]) == 1
    tight = factory(replace(base, expansion_mult=2.0)).generate_signals(mild)
    assert int(tight["signal"].iloc[mild_fire]) == 0
    # Close that holds outside the expansion box is not a fade.
    held, held_fire = _expansion_fail_fade_tape(long_side=True, held_outside=True)
    assert int(_signals("expansion_fail_fade", held)["signal"].iloc[held_fire]) == 0
    # Locked weak-vol: volume_t above the prior-20 mean blocks the fade.
    heavy, heavy_fire = _expansion_fail_fade_tape(long_side=True, heavy_fail_vol=True)
    assert int(_signals("expansion_fail_fade", heavy)["signal"].iloc[heavy_fire]) == 0
    # Wick-only expansion (close still inside the quiet 20-bar box) is not
    # a Donchian close-through and not a multi-bar probe reclaim.
    wick_n = 50
    wick_fire = 41
    wick_exp = 40
    wick_close = np.full(wick_n, 100.0)
    wick_high = np.full(wick_n, 100.5)
    wick_low = np.full(wick_n, 99.5)
    wick_open = np.full(wick_n, 100.0)
    wick_high[wick_exp] = 104.0
    wick_low[wick_exp] = 96.0
    wick_close[wick_exp] = 99.6
    wick_open[wick_exp] = 100.0
    wick_close[wick_fire] = 99.9
    wick_high[wick_fire] = 100.2
    wick_low[wick_fire] = 99.4
    wick_open[wick_fire] = 97.0
    wick = _ohlcv(_hourly(wick_n), wick_close, high=wick_high, low=wick_low, open_=wick_open)
    wick_sig = _signals("expansion_fail_fade", wick)
    assert int(wick_sig["signal"].iloc[wick_fire]) == 1
    assert int(_signals("failed_range_break_reversion", wick)["signal"].iloc[wick_fire]) == 0
    assert int(_signals("failed_break_reclaim", wick)["signal"].iloc[wick_fire]) == 0
    assert int(_signals("nr7_fail_reversion", wick)["signal"].iloc[wick_fire]) == 0


def test_expansion_fail_fade_short_entry() -> None:
    from dataclasses import replace

    from research.validate import strategy_kit

    factory, base, space = strategy_kit("expansion_fail_fade", SignalSide.SHORT)
    extra = {k for k in space if k not in {"take_profit_pct", "stop_loss_pct"}}
    assert extra == {"expansion_mult"}
    assert space["expansion_mult"] == [1.5, 2.0]
    assert "atr_n" not in space
    candles, fire = _expansion_fail_fade_tape(long_side=False)
    signals = _signals("expansion_fail_fade", candles, side=SignalSide.SHORT)
    assert int(signals["signal"].iloc[0]) == 0
    assert int(signals["signal"].iloc[fire]) == -1
    assert int((signals["signal"] == -1).sum()) >= 1
    assert int((signals["signal"] == 1).sum()) == 0
    assert float(signals["expansion_tr"].iloc[fire]) == pytest.approx(4.0)
    mild, mild_fire = _expansion_fail_fade_tape(long_side=False, expansion_tr=1.7)
    mild_sig = _signals("expansion_fail_fade", mild, side=SignalSide.SHORT)
    assert int(mild_sig["signal"].iloc[mild_fire]) == -1
    tight = factory(replace(base, expansion_mult=2.0)).generate_signals(mild)
    assert int(tight["signal"].iloc[mild_fire]) == 0
    held, held_fire = _expansion_fail_fade_tape(long_side=False, held_outside=True)
    assert int(
        _signals("expansion_fail_fade", held, side=SignalSide.SHORT)["signal"].iloc[held_fire]
    ) == 0
    heavy, heavy_fire = _expansion_fail_fade_tape(long_side=False, heavy_fail_vol=True)
    assert int(
        _signals("expansion_fail_fade", heavy, side=SignalSide.SHORT)["signal"].iloc[heavy_fire]
    ) == 0


def test_expansion_fail_fade_no_lookahead() -> None:
    candles, fire = _expansion_fail_fade_tape(long_side=True)
    signals = _signals("expansion_fail_fade", candles)
    assert int(signals["signal"].iloc[fire]) == 1
    cut = fire + 1
    truncated = _signals("expansion_fail_fade", candles.iloc[:cut])
    pd.testing.assert_series_equal(
        signals["signal"].iloc[:cut],
        truncated["signal"],
        check_names=False,
    )
    # Later bars must not rewrite the expansion box or the fail decision.
    shocked = candles.copy()
    later = fire + 3
    shocked.iloc[later, shocked.columns.get_loc("high")] = 140.0
    shocked.iloc[later, shocked.columns.get_loc("low")] = 70.0
    shocked.iloc[later, shocked.columns.get_loc("close")] = 140.0
    shocked.iloc[later, shocked.columns.get_loc("volume")] = 80_000.0
    after = _signals("expansion_fail_fade", shocked)
    assert after["expansion_high"].iloc[fire] == pytest.approx(signals["expansion_high"].iloc[fire])
    assert after["expansion_low"].iloc[fire] == pytest.approx(signals["expansion_low"].iloc[fire])
    assert after["atr_prev"].iloc[fire] == pytest.approx(signals["atr_prev"].iloc[fire])
    assert int(after["signal"].iloc[fire]) == 1
    pd.testing.assert_series_equal(
        signals["signal"].iloc[:later],
        after["signal"].iloc[:later],
        check_names=False,
    )


def _candle_reject_tape(
    *,
    lower_wick_frac: float = 0.60,
    upper_wick_frac: float = 0.12,
    body_frac: float | None = None,
    bullish: bool = True,
    fire: int = 12,
    n: int = 24,
) -> tuple[pd.DataFrame, int]:
    """Quiet tape plus one hammer / hanging-man print at ``fire``.

    Fractions must sum to 1.0. Quiet bars are small-range dojis so they
    cannot satisfy the locked non-doji floor or the lower-wick grid.
    """
    if body_frac is None:
        body_frac = 1.0 - lower_wick_frac - upper_wick_frac
    assert abs(lower_wick_frac + upper_wick_frac + body_frac - 1.0) < 1e-9
    close = np.full(n, 100.0)
    high = np.full(n, 101.0)
    low = np.full(n, 99.0)
    open_ = np.full(n, 100.0)
    bar_low = 90.0
    bar_high = 100.0
    bar_range = bar_high - bar_low
    body_low = bar_low + lower_wick_frac * bar_range
    body_high = bar_high - upper_wick_frac * bar_range
    if bullish:
        open_[fire] = body_low
        close[fire] = body_high
    else:
        open_[fire] = body_high
        close[fire] = body_low
    high[fire] = bar_high
    low[fire] = bar_low
    return _ohlcv(_hourly(n), close, high=high, low=low, open_=open_), fire


def test_candle_reject_reversal_schema_and_long_hammer() -> None:
    from dataclasses import replace

    from core.strategy.candle_reject_reversal import (
        MAX_UPPER_WICK_FRAC_LOCKED,
        MIN_BODY_FRAC_LOCKED,
    )
    from research.validate import strategy_kit

    # Quant lock: stub-upper, non-doji floor, close-upper-half stay fixed.
    factory, base, space = strategy_kit("candle_reject_reversal", SignalSide.LONG)
    assert base.min_lower_wick_frac == pytest.approx(0.55)
    assert base.max_body_frac == pytest.approx(0.35)
    assert base.max_upper_wick_frac == pytest.approx(MAX_UPPER_WICK_FRAC_LOCKED)
    assert base.min_body_frac == pytest.approx(MIN_BODY_FRAC_LOCKED)
    assert base.require_close_upper_half is True
    assert space["min_lower_wick_frac"] == [0.55, 0.65]
    assert space["max_body_frac"] == [0.20, 0.35]
    assert "max_upper_wick_frac" not in space
    assert "min_body_frac" not in space
    assert "require_close_upper_half" not in space
    assert "run_bars" not in space
    assert "max_body" not in space
    extra = {k for k in space if k not in {"take_profit_pct", "stop_loss_pct"}}
    assert extra == {"min_lower_wick_frac", "max_body_frac"}
    candles, fire = _candle_reject_tape(bullish=True)
    signals = _signals("candle_reject_reversal", candles)
    for column in (
        "signal",
        "side",
        "score",
        "reason",
        "lower_wick_frac",
        "upper_wick_frac",
        "body_frac",
        "bar_mid",
    ):
        assert column in signals.columns
    assert "doji" not in signals.columns
    assert "run_bars" not in signals.columns
    assert int(signals["signal"].iloc[0]) == 0
    assert int(signals["signal"].iloc[fire]) == 1
    assert int((signals["signal"] == 1).sum()) >= 1
    assert int((signals["signal"] == -1).sum()) == 0
    assert float(signals["lower_wick_frac"].iloc[fire]) == pytest.approx(0.60)
    assert float(signals["upper_wick_frac"].iloc[fire]) == pytest.approx(0.12)
    assert float(signals["body_frac"].iloc[fire]) == pytest.approx(0.28)
    assert float(candles["close"].iloc[fire]) >= float(signals["bar_mid"].iloc[fire])
    # A 0.60 lower wick clears 0.55 but not 0.65.
    tight_wick = factory(replace(base, min_lower_wick_frac=0.65)).generate_signals(candles)
    assert int(tight_wick["signal"].iloc[fire]) == 0
    # A 0.28 body clears 0.35 but not 0.20.
    tight_body = factory(replace(base, max_body_frac=0.20)).generate_signals(candles)
    assert int(tight_body["signal"].iloc[fire]) == 0
    # Doji body (~0.10) is doji_star territory, not this family.
    doji, doji_fire = _candle_reject_tape(
        lower_wick_frac=0.75, upper_wick_frac=0.15, body_frac=0.10
    )
    assert int(_signals("candle_reject_reversal", doji)["signal"].iloc[doji_fire]) == 0
    assert int(_signals("wick_rejection_reversal", doji)["signal"].iloc[doji_fire]) == 1
    # Fat upper wick is generic wick rejection, not a stub-upper hammer.
    fat, fat_fire = _candle_reject_tape(
        lower_wick_frac=0.60, upper_wick_frac=0.25, body_frac=0.15
    )
    assert int(_signals("candle_reject_reversal", fat)["signal"].iloc[fat_fire]) == 0
    assert int(_signals("wick_rejection_reversal", fat)["signal"].iloc[fat_fire]) == 1
    # Locked stub-upper still holds if a caller tries to loosen it.
    loose = factory(replace(base, max_upper_wick_frac=0.40)).generate_signals(fat)
    assert int(loose["signal"].iloc[fat_fire]) == 0
    # Shooting star (long upper) is not a hanging-man SHORT.
    star, star_fire = _candle_reject_tape(
        lower_wick_frac=0.12, upper_wick_frac=0.60, body_frac=0.28
    )
    assert int(
        _signals("candle_reject_reversal", star, side=SignalSide.SHORT)["signal"].iloc[star_fire]
    ) == 0
    # Same-bar hammer is not a doji-star confirm (that fires on the next bar).
    assert int(_signals("doji_star_reversal", candles)["signal"].iloc[fire]) == 0


def test_candle_reject_reversal_short_hanging_man() -> None:
    from dataclasses import replace

    from research.validate import strategy_kit

    factory, base, space = strategy_kit("candle_reject_reversal", SignalSide.SHORT)
    extra = {k for k in space if k not in {"take_profit_pct", "stop_loss_pct"}}
    assert extra == {"min_lower_wick_frac", "max_body_frac"}
    assert space["min_lower_wick_frac"] == [0.55, 0.65]
    assert space["max_body_frac"] == [0.20, 0.35]
    assert "run_bars" not in space
    assert "max_upper_wick_frac" not in space
    candles, fire = _candle_reject_tape(bullish=False)
    signals = _signals("candle_reject_reversal", candles, side=SignalSide.SHORT)
    assert int(signals["signal"].iloc[0]) == 0
    assert int(signals["signal"].iloc[fire]) == -1
    assert int((signals["signal"] == -1).sum()) >= 1
    assert int((signals["signal"] == 1).sum()) == 0
    assert float(signals["lower_wick_frac"].iloc[fire]) == pytest.approx(0.60)
    assert float(signals["upper_wick_frac"].iloc[fire]) == pytest.approx(0.12)
    assert float(signals["body_frac"].iloc[fire]) == pytest.approx(0.28)
    assert float(candles["close"].iloc[fire]) >= float(signals["bar_mid"].iloc[fire])
    tight_wick = factory(replace(base, min_lower_wick_frac=0.65)).generate_signals(candles)
    assert int(tight_wick["signal"].iloc[fire]) == 0
    tight_body = factory(replace(base, max_body_frac=0.20)).generate_signals(candles)
    assert int(tight_body["signal"].iloc[fire]) == 0
    doji, doji_fire = _candle_reject_tape(
        lower_wick_frac=0.75, upper_wick_frac=0.15, body_frac=0.10, bullish=False
    )
    assert int(
        _signals("candle_reject_reversal", doji, side=SignalSide.SHORT)["signal"].iloc[doji_fire]
    ) == 0


def test_candle_reject_reversal_no_lookahead() -> None:
    candles, fire = _candle_reject_tape(bullish=True)
    signals = _signals("candle_reject_reversal", candles)
    assert int(signals["signal"].iloc[fire]) == 1
    cut = fire + 1
    truncated = _signals("candle_reject_reversal", candles.iloc[:cut])
    pd.testing.assert_series_equal(
        signals["signal"].iloc[:cut],
        truncated["signal"],
        check_names=False,
    )
    # Later bars must not rewrite the hammer geometry or the fire decision.
    shocked = candles.copy()
    later = fire + 3
    shocked.iloc[later, shocked.columns.get_loc("high")] = 140.0
    shocked.iloc[later, shocked.columns.get_loc("low")] = 70.0
    shocked.iloc[later, shocked.columns.get_loc("close")] = 140.0
    shocked.iloc[later, shocked.columns.get_loc("open")] = 70.0
    after = _signals("candle_reject_reversal", shocked)
    assert after["lower_wick_frac"].iloc[fire] == pytest.approx(signals["lower_wick_frac"].iloc[fire])
    assert after["upper_wick_frac"].iloc[fire] == pytest.approx(signals["upper_wick_frac"].iloc[fire])
    assert after["body_frac"].iloc[fire] == pytest.approx(signals["body_frac"].iloc[fire])
    assert after["bar_mid"].iloc[fire] == pytest.approx(signals["bar_mid"].iloc[fire])
    assert int(after["signal"].iloc[fire]) == 1
    pd.testing.assert_series_equal(
        signals["signal"].iloc[:later],
        after["signal"].iloc[:later],
        check_names=False,
    )


def _rectangle_fail_reclaim_tape(
    *,
    long_side: bool,
    delay: int = 2,
    held_break: bool = False,
    blow_through: bool = False,
    single_touch: bool = False,
    sloped: bool = False,
    decoy: bool = True,
    upper_span: float = 0.0,
    n: int = 90,
) -> tuple[pd.DataFrame, int, int]:
    """Two-touch flat box (110/90), close-outside, then close back inside.

    First high publishes just outside a 24-bar window at the break so
    default lookback=32 fires and lookback=24 does not. A Donchian-only
    decoy wick (unpublished at the break) keeps jobs 119/130 off this
    reclaim: their channel is wider than the rectangle rails.
    """
    close, high, low, open_ = _planted_swings_background(n)
    high[38] = 110.0
    close[38] = 108.0
    if not single_touch:
        low[46] = 85.0 if sloped else 90.0
        close[46] = 92.0
        high[52] = (118.0 if sloped else 110.0) + upper_span
        close[52] = 108.0
        low[58] = 90.0
        close[58] = 92.0
    break_i = 66
    fire = break_i + delay
    if long_side:
        if decoy:
            # Wider than the rectangle floor, not a published swing yet.
            low[64] = 82.0
        close[break_i] = 85.0
        high[break_i] = 92.0
        low[break_i] = 84.0
        open_[break_i] = 92.0
        for j in range(break_i + 1, fire):
            close[j] = 84.0
            high[j] = 88.0
            low[j] = 83.0
            open_[j] = 85.0
        if held_break:
            close[fire] = 84.0
            high[fire] = 88.0
            low[fire] = 83.0
            open_[fire] = 85.0
        elif blow_through:
            close[fire] = 80.0
            high[fire] = 86.0
            low[fire] = 79.0
            open_[fire] = 85.0
        else:
            close[fire] = 100.0
            high[fire] = 102.0
            low[fire] = 98.0
            open_[fire] = 86.0
    else:
        if decoy:
            high[64] = 118.0
        close[break_i] = 115.0
        high[break_i] = 116.0
        low[break_i] = 108.0
        open_[break_i] = 108.0
        for j in range(break_i + 1, fire):
            close[j] = 116.0
            high[j] = 118.0
            low[j] = 112.0
            open_[j] = 115.0
        if held_break:
            close[fire] = 116.0
            high[fire] = 118.0
            low[fire] = 112.0
            open_[fire] = 115.0
        elif blow_through:
            close[fire] = 125.0
            high[fire] = 126.0
            low[fire] = 114.0
            open_[fire] = 116.0
        else:
            close[fire] = 100.0
            high[fire] = 102.0
            low[fire] = 98.0
            open_[fire] = 114.0
    candles = _ohlcv(_hourly(n, start="2024-01-03"), close, high=high, low=low, open_=open_)
    return candles, break_i, fire


def test_bullish_rectangle_fail_reclaim_schema_and_long_entry() -> None:
    from dataclasses import replace

    from core.strategy.bullish_rectangle_fail_reclaim import (
        ATR_PERIOD,
        MAX_BARS_OUTSIDE_LOCKED,
        MIN_TOUCHES_PER_RAIL,
        PIVOT_LEFT,
        REQUIRE_CLOSE_INSIDE_LOCKED,
    )
    from research.validate import strategy_kit

    factory, base, space = strategy_kit("bullish_rectangle_fail_reclaim", SignalSide.LONG)
    assert ATR_PERIOD == 20
    assert PIVOT_LEFT == 3
    assert MIN_TOUCHES_PER_RAIL == 2
    assert MAX_BARS_OUTSIDE_LOCKED == 2
    assert REQUIRE_CLOSE_INSIDE_LOCKED is True
    assert base.lookback == 32
    assert base.atr_tol == pytest.approx(0.15)
    assert base.max_bars_outside == 2
    assert base.require_close_inside is True
    assert base.min_touches_per_rail == 2
    assert space["lookback"] == [24, 32]
    assert space["atr_tol"] == [0.10, 0.15]
    extra = {k for k in space if k not in {"take_profit_pct", "stop_loss_pct"}}
    assert extra == {"lookback", "atr_tol"}
    assert "max_bars_outside" not in extra
    assert "require_close_inside" not in extra
    assert "min_touches_per_rail" not in extra
    assert "atr_n" not in extra
    assert "atr_period" not in extra
    assert "pivot_left" not in extra
    candles, break_i, fire = _rectangle_fail_reclaim_tape(long_side=True)
    signals = _signals("bullish_rectangle_fail_reclaim", candles)
    for column in (
        "signal",
        "side",
        "score",
        "reason",
        "upper_rail",
        "lower_rail",
        "n_highs",
        "n_lows",
        "bars_since_break",
    ):
        assert column in signals.columns
    assert "range_high" not in signals.columns
    assert "min_probe_bars" not in signals.columns
    assert "max_bars_since_break" not in signals.columns
    assert int(signals["signal"].iloc[0]) == 0
    assert int(signals["signal"].iloc[break_i]) == 0
    assert int(signals["signal"].iloc[fire]) == 1
    assert int((signals["signal"] == 1).sum()) >= 1
    assert int((signals["signal"] == -1).sum()) == 0
    assert signals["lower_rail"].iloc[break_i] == pytest.approx(90.0)
    assert signals["upper_rail"].iloc[break_i] == pytest.approx(110.0)
    assert signals["n_highs"].iloc[break_i] == pytest.approx(2.0)
    assert signals["n_lows"].iloc[break_i] == pytest.approx(2.0)
    assert signals["bars_since_break"].iloc[fire] == pytest.approx(2.0)
    assert signals["break_low"].iloc[fire] == pytest.approx(90.0)
    # First high sits outside the 24-bar publication window at the break.
    tight_lb = factory(replace(base, lookback=24)).generate_signals(candles)
    assert int(tight_lb["signal"].iloc[fire]) == 0
    assert tight_lb["n_highs"].iloc[break_i] == pytest.approx(1.0)
    # Locked max_bars_outside=2 even if a caller asks for 1.
    forced = factory(replace(base, max_bars_outside=1)).generate_signals(candles)
    assert int(forced["signal"].iloc[fire]) == 1
    held, _, held_fire = _rectangle_fail_reclaim_tape(long_side=True, held_break=True)
    assert int(_signals("bullish_rectangle_fail_reclaim", held)["signal"].iloc[held_fire]) == 0
    assert int((_signals("bullish_rectangle_fail_reclaim", held)["signal"] == 1).sum()) == 0
    through, _, through_fire = _rectangle_fail_reclaim_tape(long_side=True, blow_through=True)
    assert int(
        _signals("bullish_rectangle_fail_reclaim", through)["signal"].iloc[through_fire]
    ) == 0
    one, _, one_fire = _rectangle_fail_reclaim_tape(long_side=True, single_touch=True)
    assert int(_signals("bullish_rectangle_fail_reclaim", one)["signal"].iloc[one_fire]) == 0
    slope, _, slope_fire = _rectangle_fail_reclaim_tape(long_side=True, sloped=True)
    assert int(_signals("bullish_rectangle_fail_reclaim", slope)["signal"].iloc[slope_fire]) == 0
    late, _, late_fire = _rectangle_fail_reclaim_tape(long_side=True, delay=3)
    assert int(_signals("bullish_rectangle_fail_reclaim", late)["signal"].iloc[late_fire]) == 0
    # Neighbors: Donchian fail-reclaim families stay flat on this rectangle bar.
    assert int(_signals("failed_range_break_reversion", candles)["signal"].iloc[fire]) == 0
    assert int(_signals("failed_break_reclaim", candles)["signal"].iloc[fire]) == 0
    assert int(_signals("ascending_triangle_break", candles)["signal"].iloc[fire]) == 0
    assert int(_signals("converging_wedge_break", candles)["signal"].iloc[fire]) == 0
    assert int(_signals("donchian_breakout", candles)["signal"].iloc[fire]) == 0
    # A close-through that stays outside is a breakout, not this fade.
    breakout, _, bout_fire = _rectangle_fail_reclaim_tape(long_side=True, held_break=True)
    assert int(_signals("bullish_rectangle_fail_reclaim", breakout)["signal"].iloc[bout_fire]) == 0


def test_bullish_rectangle_fail_reclaim_short_entry() -> None:
    from dataclasses import replace

    from research.validate import strategy_kit

    factory, base, space = strategy_kit("bullish_rectangle_fail_reclaim", SignalSide.SHORT)
    extra = {k for k in space if k not in {"take_profit_pct", "stop_loss_pct"}}
    assert extra == {"lookback", "atr_tol"}
    assert space["lookback"] == [24, 32]
    assert space["atr_tol"] == [0.10, 0.15]
    assert "max_bars_outside" not in extra
    assert base.require_close_inside is True
    assert base.max_bars_outside == 2
    candles, break_i, fire = _rectangle_fail_reclaim_tape(long_side=False)
    signals = _signals("bullish_rectangle_fail_reclaim", candles, side=SignalSide.SHORT)
    assert int(signals["signal"].iloc[0]) == 0
    assert int(signals["signal"].iloc[break_i]) == 0
    assert int(signals["signal"].iloc[fire]) == -1
    assert int((signals["signal"] == -1).sum()) >= 1
    assert int((signals["signal"] == 1).sum()) == 0
    assert signals["upper_rail"].iloc[break_i] == pytest.approx(110.0)
    assert signals["lower_rail"].iloc[break_i] == pytest.approx(90.0)
    assert signals["bars_since_break"].iloc[fire] == pytest.approx(2.0)
    assert signals["break_high"].iloc[fire] == pytest.approx(110.0)
    tight_lb = factory(replace(base, lookback=24)).generate_signals(candles)
    assert int(tight_lb["signal"].iloc[fire]) == 0
    held, _, held_fire = _rectangle_fail_reclaim_tape(long_side=False, held_break=True)
    assert int(
        _signals("bullish_rectangle_fail_reclaim", held, side=SignalSide.SHORT)["signal"].iloc[
            held_fire
        ]
    ) == 0
    through, _, through_fire = _rectangle_fail_reclaim_tape(long_side=False, blow_through=True)
    assert int(
        _signals("bullish_rectangle_fail_reclaim", through, side=SignalSide.SHORT)["signal"].iloc[
            through_fire
        ]
    ) == 0
    assert int(
        _signals("failed_range_break_reversion", candles, side=SignalSide.SHORT)["signal"].iloc[fire]
    ) == 0
    assert int(
        _signals("failed_break_reclaim", candles, side=SignalSide.SHORT)["signal"].iloc[fire]
    ) == 0
    assert "range_high" not in signals.columns
    assert "nr7_high" not in signals.columns


def test_bullish_rectangle_fail_reclaim_kit_locks_and_atr_tol() -> None:
    from dataclasses import replace

    from research.validate import strategy_kit

    factory, base, space = strategy_kit("bullish_rectangle_fail_reclaim", SignalSide.LONG)
    extra = {k for k in space if k not in {"take_profit_pct", "stop_loss_pct"}}
    assert extra == {"lookback", "atr_tol"}
    assert space["lookback"] == [24, 32]
    assert space["atr_tol"] == [0.10, 0.15]
    # 0.50 high-span clears 0.15×ATR(20) on this tape but not 0.10×ATR(20).
    loose, _break_i, fire = _rectangle_fail_reclaim_tape(
        long_side=True, decoy=False, upper_span=0.50
    )
    assert int(factory(replace(base, atr_tol=0.15)).generate_signals(loose)["signal"].iloc[fire]) == 1
    assert int(factory(replace(base, atr_tol=0.10)).generate_signals(loose)["signal"].iloc[fire]) == 0
    # min_touches stays locked at 2 if a caller tries to drop to 1.
    lonely, _, lonely_fire = _rectangle_fail_reclaim_tape(long_side=True, single_touch=True)
    loosened = factory(replace(base, min_touches_per_rail=1)).generate_signals(lonely)
    assert int(loosened["signal"].iloc[lonely_fire]) == 0


def test_bullish_rectangle_fail_reclaim_no_lookahead() -> None:
    candles, _break_i, fire = _rectangle_fail_reclaim_tape(long_side=True)
    signals = _signals("bullish_rectangle_fail_reclaim", candles)
    assert int(signals["signal"].iloc[fire]) == 1
    cut = fire + 1
    truncated = _signals("bullish_rectangle_fail_reclaim", candles.iloc[:cut])
    pd.testing.assert_series_equal(
        signals["signal"].iloc[:cut],
        truncated["signal"],
        check_names=False,
    )
    shocked = candles.copy()
    later = fire + 3
    shocked.iloc[later, shocked.columns.get_loc("high")] = 140.0
    shocked.iloc[later, shocked.columns.get_loc("low")] = 70.0
    shocked.iloc[later, shocked.columns.get_loc("close")] = 140.0
    after = _signals("bullish_rectangle_fail_reclaim", shocked)
    assert after["upper_rail"].iloc[fire] == pytest.approx(signals["upper_rail"].iloc[fire])
    assert after["lower_rail"].iloc[fire] == pytest.approx(signals["lower_rail"].iloc[fire])
    assert after["break_low"].iloc[fire] == pytest.approx(signals["break_low"].iloc[fire])
    assert int(after["signal"].iloc[fire]) == 1
    pd.testing.assert_series_equal(
        signals["signal"].iloc[:later],
        after["signal"].iloc[:later],
        check_names=False,
    )


def test_inbox_walk_kits_max_two_free_params() -> None:
    from research.validate import strategy_kit

    for name, extra_keys in (
        ("london_close_inventory_fade", {"extreme_frac", "vol_lookback"}),
        ("utc_open_fail_reversion", set()),
        ("range_compression_volume_thrust", {"compress_pct", "thrust_mult"}),
        ("turnover_climax_rejection_fade", {"lookback", "reject_frac"}),
        ("volume_dryup_range_break", {"dry_bars", "vol_lookback"}),
        ("body_efficiency_follow", {"min_efficiency"}),
        ("week_open_reclaim", {"min_wrong_closes", "vol_lookback"}),
        ("prior_session_mid_reclaim", {"vol_lookback"}),
        ("close_location_persistence", {"lookback", "clv_threshold"}),
        ("open_in_prior_range_fail", set()),
        ("equal_high_low_restest_fade", {"lookback", "tol_atr"}),
        ("double_bottom_neckline_break", {"lookback", "atr_tol"}),
        ("double_top_neckline_break", {"lookback", "atr_tol"}),
        ("ascending_triangle_break", {"lookback", "atr_tol"}),
        ("prior_day_extreme_reject", {"touch_tol_atr"}),
        ("failed_range_break_reversion", {"lookback", "max_bars_since_break"}),
        ("asia_range_london_reject", {"touch_tol_atr"}),
        ("orb_fail_reversion", {"orb_bars", "max_bars_since_break"}),
        ("nr7_fail_reversion", {"max_bars_since_break"}),
        ("ib_fail_reversion", {"max_bars_since_break"}),
        ("converging_wedge_break", {"lookback"}),
        ("engulfing_fail_reversion", {"max_bars_since_engulf"}),
        ("wyckoff_spring_reclaim", {"lookback", "hold_bars"}),
        ("prior_close_magnet_fade", {"k"}),
        ("classic_floor_pivot_reject", {"touch_tol_atr"}),
        ("failed_break_reclaim", {"lookback", "min_probe_bars"}),
        ("expansion_fail_fade", {"expansion_mult"}),
        ("candle_reject_reversal", {"min_lower_wick_frac", "max_body_frac"}),
        ("bullish_rectangle_fail_reclaim", {"lookback", "atr_tol"}),
    ):
        _factory, _base, space = strategy_kit(name, SignalSide.LONG)
        extra = {k for k in space if k not in {"take_profit_pct", "stop_loss_pct"}}
        assert extra == extra_keys
        assert "skip_bull" not in space
        assert len(extra) <= 2


def test_session_boundary_and_vwap_band_kits_no_skip_bull() -> None:
    from research.validate import strategy_kit

    for name, extra_keys in (
        ("session_boundary_volume_fade", {"vol_period"}),
        ("vwap_volatility_band_fade", {"band_k"}),
        ("prior_day_extreme_reject", {"touch_tol_atr"}),
        ("failed_range_break_reversion", {"lookback", "max_bars_since_break"}),
        ("asia_range_london_reject", {"touch_tol_atr"}),
        ("orb_fail_reversion", {"orb_bars", "max_bars_since_break"}),
        ("nr7_fail_reversion", {"max_bars_since_break"}),
        ("ib_fail_reversion", {"max_bars_since_break"}),
        ("converging_wedge_break", {"lookback"}),
        ("engulfing_fail_reversion", {"max_bars_since_engulf"}),
        ("wyckoff_spring_reclaim", {"lookback", "hold_bars"}),
        ("prior_close_magnet_fade", {"k"}),
        ("classic_floor_pivot_reject", {"touch_tol_atr"}),
        ("failed_break_reclaim", {"lookback", "min_probe_bars"}),
        ("expansion_fail_fade", {"expansion_mult"}),
        ("candle_reject_reversal", {"min_lower_wick_frac", "max_body_frac"}),
        ("bullish_rectangle_fail_reclaim", {"lookback", "atr_tol"}),
    ):
        _factory, _base, space = strategy_kit(name, SignalSide.LONG)
        extra = {k for k in space if k not in {"take_profit_pct", "stop_loss_pct"}}
        assert extra == extra_keys
        assert "skip_bull" not in space
        assert len(extra) <= 2


@pytest.mark.parametrize("name", APPROVED)
def test_novel_no_lookahead_truncation(name: str) -> None:
    candles = _ohlcv(_hourly(80), np.linspace(100, 110, 80))
    cut = 50
    if name == "weekend_gap_fill":
        candles = _ohlcv(_hourly(120, start="2024-01-04"), np.full(120, 100.0))
    if name == "monday_range_sweep_reversal":
        candles = _ohlcv(_hourly(120, start="2024-01-04"), np.full(120, 100.0))
    if name == "week_open_reclaim":
        candles = _ohlcv(_hourly(120, start="2024-01-01"), np.full(120, 100.0))
    if name == "prior_week_high_break":
        candles = _ohlcv(_hourly(24 * 10, start="2024-01-01"), np.full(24 * 10, 100.0))
    if name == "connors_rsi_fade":
        candles = _ohlcv(_hourly(180), np.linspace(100, 110, 180))
        cut = 140
    if name == "range_compression_volume_thrust":
        candles = _ohlcv(_hourly(180), np.linspace(100, 110, 180))
        cut = 140
    signals_full = _signals(name, candles)
    truncated = _signals(name, candles.iloc[:cut])
    pd.testing.assert_series_equal(
        signals_full["signal"].iloc[:cut],
        truncated["signal"],
        check_names=False,
    )


@pytest.mark.parametrize("name", APPROVED)
def test_novel_future_shock_does_not_change_past(name: str) -> None:
    candles = _ohlcv(_hourly(80), np.linspace(100, 110, 80))
    if name == "weekend_gap_fill":
        candles = _ohlcv(_hourly(120, start="2024-01-04"), np.full(120, 100.0))
    if name == "monday_range_sweep_reversal":
        candles = _ohlcv(_hourly(120, start="2024-01-04"), np.full(120, 100.0))
    if name == "week_open_reclaim":
        candles = _ohlcv(_hourly(120, start="2024-01-01"), np.full(120, 100.0))
    if name == "prior_week_high_break":
        candles = _ohlcv(_hourly(24 * 10, start="2024-01-01"), np.full(24 * 10, 100.0))
    if name == "connors_rsi_fade":
        candles = _ohlcv(_hourly(180), np.linspace(100, 110, 180))
    if name == "range_compression_volume_thrust":
        candles = _ohlcv(_hourly(180), np.linspace(100, 110, 180))
    shocked = candles.copy()
    shocked.iloc[-1, shocked.columns.get_loc("close")] *= 1.5
    shocked.iloc[-1, shocked.columns.get_loc("high")] *= 1.6
    original = _signals(name, candles)["signal"].iloc[:-1]
    after = _signals(name, shocked)["signal"].iloc[:-1]
    pd.testing.assert_series_equal(original, after)
