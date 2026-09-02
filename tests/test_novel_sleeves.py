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


@pytest.mark.parametrize("name", APPROVED)
def test_novel_no_lookahead_truncation(name: str) -> None:
    candles = _ohlcv(_hourly(80), np.linspace(100, 110, 80))
    cut = 50
    if name == "weekend_gap_fill":
        candles = _ohlcv(_hourly(120, start="2024-01-04"), np.full(120, 100.0))
    if name == "prior_week_high_break":
        candles = _ohlcv(_hourly(24 * 10, start="2024-01-01"), np.full(24 * 10, 100.0))
    if name == "connors_rsi_fade":
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
    if name == "prior_week_high_break":
        candles = _ohlcv(_hourly(24 * 10, start="2024-01-01"), np.full(24 * 10, 100.0))
    if name == "connors_rsi_fade":
        candles = _ohlcv(_hourly(180), np.linspace(100, 110, 180))
    shocked = candles.copy()
    shocked.iloc[-1, shocked.columns.get_loc("close")] *= 1.5
    shocked.iloc[-1, shocked.columns.get_loc("high")] *= 1.6
    original = _signals(name, candles)["signal"].iloc[:-1]
    after = _signals(name, shocked)["signal"].iloc[:-1]
    pd.testing.assert_series_equal(original, after)
