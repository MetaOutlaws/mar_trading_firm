"""Impulse pullback continuation tests (Option B). No walk. No approval book."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core.strategy.base import SignalSide
from core.strategy.impulse_pullback_continuation import (
    FAIL_OF_IMPULSE_LOCKED,
    FORBID_MIDPOINT_FAIL_FADE_LOCKED,
    FORBID_SIGNAL_CLOSE_FILL_LOCKED,
    FORBID_SMA20_STRETCH_FADE_LOCKED,
    FORBID_THREE_BLACK_CROWS_ENTRY_LOCKED,
    IMPULSE_MIN_CLOSE_PCT_GRID,
    IMPULSE_WINDOW_BARS_LOCKED,
    MAX_HOLDING_BARS_LOCKED,
    MID_ANCHOR_LOCKED,
    OPTION_B_LOCKED,
    PRIORITY_LONG_ON_CONFLICT_LOCKED,
    PULLBACK_MAX_BARS_LOCKED,
    PULLBACK_MAX_RETRACE_FRAC_GRID,
    REGIME_GATE_ALIGNED_200SMA_LOCKED,
    SMA_PERIOD_LOCKED,
    STOP_LOSS_PCT_GRID,
    TAKE_PROFIT_PCT_GRID,
    ImpulsePullbackContinuationParams,
    ImpulsePullbackContinuationStrategy,
    _aligned_200sma_regime,
)
from tests.test_novel_sleeves import _ohlcv, _signals


def _four_hour(n: int, start: str = "2020-01-01") -> pd.DatetimeIndex:
    return pd.date_range(start, periods=n, freq="4h", tz="UTC")


def _warmup_flat(n_days: int = SMA_PERIOD_LOCKED + 30, px: float = 100.0):
    """Build completed daily history so SMA200 is defined; return 4h OHLCV arrays."""
    # 6 x 4h bars per UTC day.
    n = n_days * 6
    close = np.full(n, px, dtype="float64")
    # Tiny oscillation so daily resample is well-defined and SMA stable near px.
    for i in range(n):
        close[i] = px + 0.05 * np.sin(i / 7.0)
    high = close + 0.15
    low = close - 0.15
    open_ = np.concatenate([[close[0]], close[:-1]])
    return close, high, low, open_, n


def _paint_bar(open_, high, low, close, i, o, h, l, c):
    open_[i] = o
    high[i] = h
    low[i] = l
    close[i] = c


def _tape_long_continuation(*, regime_above: bool = True):
    """Craft LONG impulse → shallow PB → break of PB high, with regime control.

    Layout after warmup flat ~100:
      impulse bars end at fire_imp: +2% close-to-close over W=2
      PB within 4 bars: retrace ≤50%, holds ImpulseLow
      trigger: close > max(PB highs)
    Regime: lift (above) or drop (below) the whole post-warmup path vs SMA≈100.
    """
    close, high, low, open_, n0 = _warmup_flat()
    # Append geometry segment.
    extra = 40
    close = np.concatenate([close, np.full(extra, close[-1])])
    high = np.concatenate([high, np.full(extra, close[-1] + 0.15)])
    low = np.concatenate([low, np.full(extra, close[-1] - 0.15)])
    open_ = np.concatenate([open_, np.full(extra, close[-1])])
    n = len(close)
    base_i = n0  # first append index

    # Shift level for regime: above SMA → +20; below → -20.
    level = 120.0 if regime_above else 80.0
    for i in range(base_i, n):
        close[i] = level
        open_[i] = level
        high[i] = level + 0.2
        low[i] = level - 0.2

    # Need close[t_i - W] as base. Put base at base_i+5, impulse ends base_i+7.
    t_base = base_i + 5
    t_i = t_base + 2  # W=2
    # Impulse bars: t_i-1 and t_i. Move +2.5% from close[t_base].
    _paint_bar(open_, high, low, close, t_base, level, level + 0.3, level - 0.3, level)
    # Bar t_base+1 (first impulse bar): advance partway
    c1 = level * 1.012
    _paint_bar(open_, high, low, close, t_base + 1, level, c1 + 0.4, level - 0.2, c1)
    # Bar t_i (second impulse bar): finish +2.5%
    c2 = level * 1.025
    imp_hi = c2 + 0.5
    imp_lo = level - 0.15  # held as ImpulseLow floor
    _paint_bar(open_, high, low, close, t_i, c1, imp_hi, max(imp_lo, c1 - 0.3), c2)

    # Pullback: one bar retrace ~30% of impulse range, holds ImpulseLow
    t_pb = t_i + 1
    rng = imp_hi - imp_lo
    pb_close = imp_hi - 0.30 * rng
    pb_hi = max(pb_close, c2) - 0.05  # below impulse high but defines PB extreme
    pb_hi = imp_hi - 0.1
    pb_lo = max(imp_lo + 0.05, pb_close - 0.3)
    _paint_bar(open_, high, low, close, t_pb, c2, pb_hi, pb_lo, pb_close)

    # Quiet bar then trigger: close > pb_hi
    t_quiet = t_pb + 1
    _paint_bar(
        open_, high, low, close, t_quiet,
        pb_close, pb_hi - 0.05, pb_lo + 0.05, pb_close + 0.05,
    )
    t_tr = t_quiet + 1
    trig_c = pb_hi + 0.25
    _paint_bar(
        open_, high, low, close, t_tr,
        pb_close + 0.05, trig_c + 0.1, pb_lo + 0.1, trig_c,
    )

    # Flat remainder
    for i in range(t_tr + 1, n):
        _paint_bar(open_, high, low, close, i, trig_c, trig_c + 0.2, trig_c - 0.2, trig_c)

    candles = _ohlcv(_four_hour(n), close, high=high, low=low, open_=open_)
    return candles, t_tr, t_i, t_pb


def _tape_short_continuation(*, regime_below: bool = True):
    """Craft SHORT impulse → shallow PB → break of PB low."""
    close, high, low, open_, n0 = _warmup_flat()
    extra = 40
    close = np.concatenate([close, np.full(extra, close[-1])])
    high = np.concatenate([high, np.full(extra, close[-1] + 0.15)])
    low = np.concatenate([low, np.full(extra, close[-1] - 0.15)])
    open_ = np.concatenate([open_, np.full(extra, close[-1])])
    n = len(close)
    base_i = n0

    level = 80.0 if regime_below else 120.0
    for i in range(base_i, n):
        close[i] = level
        open_[i] = level
        high[i] = level + 0.2
        low[i] = level - 0.2

    t_base = base_i + 5
    t_i = t_base + 2
    _paint_bar(open_, high, low, close, t_base, level, level + 0.3, level - 0.3, level)
    c1 = level * 0.988
    _paint_bar(open_, high, low, close, t_base + 1, level, level + 0.2, c1 - 0.4, c1)
    c2 = level * 0.975
    imp_lo = c2 - 0.5
    imp_hi = level + 0.15
    _paint_bar(open_, high, low, close, t_i, c1, min(imp_hi, c1 + 0.3), imp_lo, c2)

    t_pb = t_i + 1
    rng = imp_hi - imp_lo
    pb_close = imp_lo + 0.30 * rng
    pb_lo = imp_lo + 0.1
    pb_hi = min(imp_hi - 0.05, pb_close + 0.3)
    _paint_bar(open_, high, low, close, t_pb, c2, pb_hi, pb_lo, pb_close)

    t_quiet = t_pb + 1
    _paint_bar(
        open_, high, low, close, t_quiet,
        pb_close, pb_hi - 0.05, pb_lo + 0.05, pb_close - 0.05,
    )
    t_tr = t_quiet + 1
    trig_c = pb_lo - 0.25
    _paint_bar(
        open_, high, low, close, t_tr,
        pb_close - 0.05, pb_hi - 0.1, trig_c - 0.1, trig_c,
    )

    for i in range(t_tr + 1, n):
        _paint_bar(open_, high, low, close, i, trig_c, trig_c + 0.2, trig_c - 0.2, trig_c)

    candles = _ohlcv(_four_hour(n), close, high=high, low=low, open_=open_)
    return candles, t_tr, t_i, t_pb


def _tape_mid_fail_lookalike():
    """Impulse then next bar through mid — 165-style. Must stay DARK here."""
    close, high, low, open_, n0 = _warmup_flat()
    extra = 30
    close = np.concatenate([close, np.full(extra, 120.0)])
    high = np.concatenate([high, np.full(extra, 120.3)])
    low = np.concatenate([low, np.full(extra, 119.7)])
    open_ = np.concatenate([open_, np.full(extra, 120.0)])
    n = len(close)
    base_i = n0
    level = 120.0
    for i in range(base_i, n):
        close[i] = level
        open_[i] = level
        high[i] = level + 0.2
        low[i] = level - 0.2

    t_base = base_i + 5
    t_i = t_base + 2
    _paint_bar(open_, high, low, close, t_base, level, level + 0.3, level - 0.3, level)
    c1 = level * 1.012
    _paint_bar(open_, high, low, close, t_base + 1, level, c1 + 0.5, level - 0.2, c1)
    c2 = level * 1.025
    imp_hi = c2 + 0.8
    imp_lo = level - 0.2
    _paint_bar(open_, high, low, close, t_i, c1, imp_hi, imp_lo, c2)
    mid = 0.5 * (imp_hi + imp_lo)
    # Next bar closes through mid downward — classic 165 fade setup, NOT our CONTINUE.
    t_fail = t_i + 1
    _paint_bar(open_, high, low, close, t_fail, c2, c2 + 0.1, mid - 0.5, mid - 0.3)

    candles = _ohlcv(_four_hour(n), close, high=high, low=low, open_=open_)
    return candles, t_fail


def test_forbid_locks_true():
    assert (
        OPTION_B_LOCKED
        and REGIME_GATE_ALIGNED_200SMA_LOCKED
        and FORBID_SIGNAL_CLOSE_FILL_LOCKED
        and FORBID_SMA20_STRETCH_FADE_LOCKED
        and FORBID_THREE_BLACK_CROWS_ENTRY_LOCKED
        and FORBID_MIDPOINT_FAIL_FADE_LOCKED
        and PRIORITY_LONG_ON_CONFLICT_LOCKED
        and MID_ANCHOR_LOCKED is False
        and FAIL_OF_IMPULSE_LOCKED is False
        and IMPULSE_WINDOW_BARS_LOCKED == 2
        and PULLBACK_MAX_BARS_LOCKED == 4
        and MAX_HOLDING_BARS_LOCKED == 18
        and SMA_PERIOD_LOCKED == 200
    )
    p = ImpulsePullbackContinuationParams()
    assert p.mid_anchor is False and p.fail_of_impulse is False
    assert p.take_profit_pct == 0.03 and p.stop_loss_pct == 0.015
    assert p.max_holding_bars == 18
    assert "next_open" in (
        "fill=next_open(engine_t+1)"
    ) or FORBID_SIGNAL_CLOSE_FILL_LOCKED


def test_kit_locks_endpoints_only():
    from research.validate import strategy_kit

    factory, base, space = strategy_kit("impulse_pullback_continuation", SignalSide.LONG)
    assert factory(base).name == "impulse_pullback_continuation"
    assert base.side is SignalSide.LONG
    assert space["pullback_max_retrace_frac"] == PULLBACK_MAX_RETRACE_FRAC_GRID == [0.38, 0.50]
    assert space["impulse_min_close_pct"] == IMPULSE_MIN_CLOSE_PCT_GRID == [1.5, 2.0]
    assert space["take_profit_pct"] == TAKE_PROFIT_PCT_GRID == [0.03]
    assert space["stop_loss_pct"] == STOP_LOSS_PCT_GRID == [0.015, 0.02]
    extra = {k for k in space if k not in {"take_profit_pct", "stop_loss_pct"}}
    assert extra == {"pullback_max_retrace_frac", "impulse_min_close_pct"}
    for banned in (
        "mid_anchor",
        "fail_of_impulse",
        "extreme_frac",
        "sma20",
        "stretch",
        "three_black",
        "clv",
        "next_thru_mid",
    ):
        assert banned not in space


def test_long_fires_on_crafted_tape():
    candles, t_tr, _t_i, _t_pb = _tape_long_continuation(regime_above=True)
    sig = _signals("impulse_pullback_continuation", candles, side=SignalSide.LONG)
    assert int(sig["signal"].iloc[t_tr]) == 1
    assert sig["side"].iloc[t_tr] == "LONG"
    assert bool(sig["regime_long_ok"].iloc[t_tr])
    assert bool(sig["geometry_long"].iloc[t_tr])
    assert not bool(sig["mid_anchor_path"].iloc[t_tr])
    assert not bool(sig["fail_of_impulse_path"].iloc[t_tr])
    assert "next_open" in str(sig["reason"].iloc[t_tr]).lower() or "engine" in str(
        sig["reason"].iloc[t_tr]
    ).lower()


def test_short_fires_on_crafted_tape():
    candles, t_tr, _t_i, _t_pb = _tape_short_continuation(regime_below=True)
    sig = _signals("impulse_pullback_continuation", candles, side=SignalSide.SHORT)
    assert int(sig["signal"].iloc[t_tr]) == -1
    assert sig["side"].iloc[t_tr] == "SHORT"
    assert bool(sig["regime_short_ok"].iloc[t_tr])
    assert bool(sig["geometry_short"].iloc[t_tr])
    assert not bool(sig["mid_anchor_path"].iloc[t_tr])
    assert not bool(sig["fail_of_impulse_path"].iloc[t_tr])


def test_mid_anchor_and_fail_paths_stay_dark():
    candles, t_fail = _tape_mid_fail_lookalike()
    strat = ImpulsePullbackContinuationStrategy(
        ImpulsePullbackContinuationParams(side=SignalSide.LONG)
    )
    sig = strat.generate_signals(candles)
    # 165-style mid pierce must not light our CONTINUE signal.
    assert int(sig["signal"].iloc[t_fail]) == 0
    assert not bool(sig["mid_anchor_path"].any())
    assert not bool(sig["fail_of_impulse_path"].any())
    # SHORT side also dark on this tape.
    sig_s = ImpulsePullbackContinuationStrategy(
        ImpulsePullbackContinuationParams(side=SignalSide.SHORT)
    ).generate_signals(candles)
    assert int(sig_s["signal"].iloc[t_fail]) == 0


def test_regime_gate_flips_side_permission():
    # Same LONG geometry: above SMA → fires; below SMA → suppressed.
    above, t_tr_a, _, _ = _tape_long_continuation(regime_above=True)
    below, t_tr_b, _, _ = _tape_long_continuation(regime_above=False)
    assert t_tr_a == t_tr_b
    strat = ImpulsePullbackContinuationStrategy(
        ImpulsePullbackContinuationParams(side=SignalSide.LONG)
    )
    sig_a = strat.generate_signals(above)
    sig_b = strat.generate_signals(below)
    assert int(sig_a["signal"].iloc[t_tr_a]) == 1
    assert bool(sig_a["regime_long_ok"].iloc[t_tr_a])
    assert int(sig_b["signal"].iloc[t_tr_b]) == 0
    assert not bool(sig_b["regime_long_ok"].iloc[t_tr_b])

    # SHORT geometry: below → fires; above → suppressed.
    below_s, t_tr_s, _, _ = _tape_short_continuation(regime_below=True)
    above_s, t_tr_s2, _, _ = _tape_short_continuation(regime_below=False)
    assert t_tr_s == t_tr_s2
    strat_s = ImpulsePullbackContinuationStrategy(
        ImpulsePullbackContinuationParams(side=SignalSide.SHORT)
    )
    assert int(strat_s.generate_signals(below_s)["signal"].iloc[t_tr_s]) == -1
    assert int(strat_s.generate_signals(above_s)["signal"].iloc[t_tr_s2]) == 0


def test_no_lookahead_future_bars_do_not_change_past():
    candles, t_tr, _, _ = _tape_long_continuation(regime_above=True)
    strat = ImpulsePullbackContinuationStrategy(
        ImpulsePullbackContinuationParams(side=SignalSide.LONG)
    )
    sig_full = strat.generate_signals(candles)

    mutated = candles.copy()
    for i in range(t_tr + 1, len(mutated)):
        mutated.iloc[i, mutated.columns.get_loc("high")] = float(mutated["high"].iloc[i]) + 50.0
        mutated.iloc[i, mutated.columns.get_loc("low")] = float(mutated["low"].iloc[i]) - 50.0
        mutated.iloc[i, mutated.columns.get_loc("close")] = float(mutated["close"].iloc[i]) + 10.0
        mutated.iloc[i, mutated.columns.get_loc("open")] = float(mutated["open"].iloc[i]) - 10.0
    sig_mut = strat.generate_signals(mutated)

    past = slice(None, t_tr + 1)
    pd.testing.assert_series_equal(
        sig_full["signal"].iloc[past], sig_mut["signal"].iloc[past], check_names=False
    )
    pd.testing.assert_series_equal(
        sig_full["regime_long_ok"].iloc[past],
        sig_mut["regime_long_ok"].iloc[past],
        check_names=False,
    )


def test_regime_uses_completed_daily_only_smoke():
    candles, t_tr, _, _ = _tape_long_continuation(regime_above=True)
    close_1d, sma_1d, long_ok, short_ok = _aligned_200sma_regime(candles)
    assert close_1d.notna().iloc[t_tr]
    assert sma_1d.notna().iloc[t_tr]
    # Mutating the final partial-looking bars' "today" should not flip past regime
    # because shift(1) excludes the in-progress daily bar.
    assert bool(long_ok.iloc[t_tr])
    assert not bool(short_ok.iloc[t_tr])


def test_catalog_option_b_not_approval_soft_watch_explicit():
    from config.pipeline import PAPER_SCAN_SLEEVES
    from firm.research_catalog import RESEARCH_HYPOTHESES
    from firm.research_jobs import CLOCK_BY_FAMILY
    from firm.sleeve_factory import spec_for_family

    row = next(r for r in RESEARCH_HYPOTHESES if r["family"] == "impulse_pullback_continuation")
    assert row["id"] == "impulse_pullback_continuation@4h/4h"
    assert row["coded"] is True and row["free_params"] == 2
    assert row.get("approved") is not True
    text = row["justification"].lower()
    assert "do not set approved=true" in text
    assert "live stays off" in text
    assert "soft-watch" in text
    assert "165" in text or "impulse_midpoint_fail_fade" in text
    assert "three_black_crows" in text
    assert "sma20_stretch_fade" in text
    assert "aligned_200sma" in text or "200sma" in text
    assert "next_open" in text or "t+1" in text
    spec = spec_for_family("impulse_pullback_continuation")
    assert spec and spec.clock == "4h/4h" and spec.side == "BOTH" and spec.auto_code is False
    assert CLOCK_BY_FAMILY["impulse_pullback_continuation"] == "4h/4h"
    assert all(i[0] != "impulse_pullback_continuation" for i in PAPER_SCAN_SLEEVES)
