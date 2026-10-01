"""Donchian N fail reversion tests (Option B). No walk. No approval book."""

from __future__ import annotations

import numpy as np
import pytest

from core.strategy.base import SignalSide
from core.strategy.donchian_n_fail_reversion import (
    ATR_N_LOCKED,
    DONCHIAN_EXCLUDE_T_LOCKED,
    FORBID_CLV_LOCKED,
    FORBID_EXTREME_FRAC_LOCKED,
    FORBID_MULTI_TOUCH_FLAT_BAND_LOCKED,
    FORBID_NEXT_THRU_MID_LOCKED,
    N_GRID,
    OPTION_B_LOCKED,
    PIERCE_TOL_ATR_GRID,
    REQUIRE_WICK_PIERCE_CLOSE_INSIDE_LOCKED,
)
from tests.test_novel_sleeves import _hourly, _ohlcv, _signals


def _tape(*, short_side=True, mode="fail", n=10, pierce_tol=0.0, atr_level=1.0):
    """Craft a same-bar Donchian wick pierce + close inside + body confirm.

    Layout (SHORT fail):
      warmup: flat ~100 with ATR-ish ranges so atr.shift(1) ≈ atr_level
      prior n bars: highs capped at DHigh=100.5, lows at 99.5
      fire: high pierces above DHigh (+ pierce*ATR), close < DHigh, red body
    """
    length = 60
    fire = 45
    assert fire > max(ATR_N_LOCKED, n) + 2

    close = np.full(length, 100.0)
    high = np.full(length, 100.0 + 0.5 * atr_level)
    low = np.full(length, 100.0 - 0.5 * atr_level)
    open_ = np.full(length, 100.0)

    for i in range(fire):
        high[i] = 100.0 + 0.5 * atr_level
        low[i] = 100.0 - 0.5 * atr_level
        close[i] = open_[i] = 100.0

    d_high = 100.0 + 0.5 * atr_level  # 100.5 with atr_level=1
    d_low = 100.0 - 0.5 * atr_level   # 99.5
    thresh = pierce_tol * atr_level

    if short_side:
        # Ensure prior n highs sit at d_high so rolling DHigh is exact.
        for i in range(fire - n, fire):
            high[i] = d_high
            low[i] = d_low
            open_[i] = close[i] = 100.0
        if mode == "fail":
            # Pierce above DHigh+thresh, close back below DHigh, bear body.
            open_[fire] = d_high - 0.05
            close[fire] = d_high - 0.20  # < DHigh and < open
            high[fire] = d_high + thresh + 0.25
            low[fire] = close[fire] - 0.05
            assert high[fire] > d_high + thresh
            assert close[fire] < d_high and close[fire] < open_[fire]
        elif mode == "no_pierce":
            open_[fire] = d_high - 0.05
            close[fire] = d_high - 0.20
            high[fire] = d_high  # tag only, no pierce
            low[fire] = close[fire] - 0.05
        elif mode == "close_outside":
            # Pierce but close stays above DHigh → dark (not inside).
            open_[fire] = d_high + thresh + 0.30
            close[fire] = d_high + 0.05  # still > DHigh
            high[fire] = d_high + thresh + 0.40
            low[fire] = d_high - 0.10
            assert high[fire] > d_high + thresh
            assert close[fire] > d_high
        elif mode == "wrong_body":
            # Pierce + close inside but bull body → SHORT dark.
            open_[fire] = d_high - 0.25
            close[fire] = d_high - 0.05  # close < DHigh but close > open
            high[fire] = d_high + thresh + 0.25
            low[fire] = open_[fire] - 0.05
            assert close[fire] < d_high and close[fire] > open_[fire]
        else:
            raise ValueError(mode)
    else:
        for i in range(fire - n, fire):
            high[i] = d_high
            low[i] = d_low
            open_[i] = close[i] = 100.0
        if mode == "fail":
            open_[fire] = d_low + 0.05
            close[fire] = d_low + 0.20  # > DLow and > open
            low[fire] = d_low - thresh - 0.25
            high[fire] = close[fire] + 0.05
            assert low[fire] < d_low - thresh
            assert close[fire] > d_low and close[fire] > open_[fire]
        elif mode == "no_pierce":
            open_[fire] = d_low + 0.05
            close[fire] = d_low + 0.20
            low[fire] = d_low  # tag only
            high[fire] = close[fire] + 0.05
        elif mode == "wrong_body":
            open_[fire] = d_low + 0.25
            close[fire] = d_low + 0.05  # close > DLow but close < open
            low[fire] = d_low - thresh - 0.25
            high[fire] = open_[fire] + 0.05
            assert close[fire] > d_low and close[fire] < open_[fire]
        else:
            raise ValueError(mode)

    for i in range(fire + 1, length):
        high[i] = 100.0 + 0.5 * atr_level
        low[i] = 100.0 - 0.5 * atr_level
        close[i] = open_[i] = 100.0

    return _ohlcv(_hourly(length), close, high=high, low=low, open_=open_), fire


def test_kit_locks_endpoints_only():
    from research.validate import strategy_kit

    assert (
        OPTION_B_LOCKED
        and DONCHIAN_EXCLUDE_T_LOCKED
        and REQUIRE_WICK_PIERCE_CLOSE_INSIDE_LOCKED
        and FORBID_MULTI_TOUCH_FLAT_BAND_LOCKED
        and FORBID_NEXT_THRU_MID_LOCKED
        and FORBID_EXTREME_FRAC_LOCKED
        and FORBID_CLV_LOCKED
    )
    factory, base, space = strategy_kit("donchian_n_fail_reversion", SignalSide.SHORT)
    assert factory(base).name == "donchian_n_fail_reversion"
    assert base.side is SignalSide.SHORT and base.atr_n == ATR_N_LOCKED == 20
    assert space["n"] == N_GRID == [10, 20]
    assert space["pierce_tol_atr"] == PIERCE_TOL_ATR_GRID == [0.0, 0.10]
    extra = {k for k in space if k not in {"take_profit_pct", "stop_loss_pct"}}
    assert extra == {"n", "pierce_tol_atr"}
    # FORBID mid/CLV/extreme_frac/touch-count in search space and on params.
    for banned in (
        "extreme_frac",
        "clv",
        "next_thru_mid",
        "thru_mid",
        "min_touches",
        "touch_tol_atr",
        "max_bars_since_break",
        "reject_frac",
    ):
        assert banned not in space
        assert not hasattr(base, banned)


def test_short_fires_on_crafted_tape():
    candles, fire = _tape(short_side=True, mode="fail")
    sig = _signals("donchian_n_fail_reversion", candles, side=SignalSide.SHORT)
    assert int(sig["signal"].iloc[fire]) == -1
    assert sig["side"].iloc[fire] == "SHORT"
    assert bool(sig["pierce_up"].iloc[fire])
    assert bool(sig["close_below_dhigh"].iloc[fire])
    assert bool(sig["bear_body"].iloc[fire])
    # Causal Donchian: DHigh is prior-n max, not including fire bar.
    assert float(sig["d_high"].iloc[fire]) == pytest.approx(100.5)


def test_long_fires_on_crafted_tape():
    candles, fire = _tape(short_side=False, mode="fail")
    sig = _signals("donchian_n_fail_reversion", candles, side=SignalSide.LONG)
    assert int(sig["signal"].iloc[fire]) == 1
    assert sig["side"].iloc[fire] == "LONG"
    assert bool(sig["pierce_dn"].iloc[fire])
    assert bool(sig["close_above_dlow"].iloc[fire])
    assert bool(sig["bull_body"].iloc[fire])
    assert float(sig["d_low"].iloc[fire]) == pytest.approx(99.5)


def test_no_pierce_close_outside_wrong_body_stay_dark():
    candles, fire = _tape(short_side=True, mode="no_pierce")
    sig = _signals("donchian_n_fail_reversion", candles, side=SignalSide.SHORT)
    assert not bool(sig["pierce_up"].iloc[fire])
    assert int(sig["signal"].iloc[fire]) == 0

    outside, of = _tape(short_side=True, mode="close_outside")
    osig = _signals("donchian_n_fail_reversion", outside, side=SignalSide.SHORT)
    assert bool(osig["pierce_up"].iloc[of])
    assert not bool(osig["close_below_dhigh"].iloc[of])
    assert int(osig["signal"].iloc[of]) == 0

    wrong, wf = _tape(short_side=True, mode="wrong_body")
    wsig = _signals("donchian_n_fail_reversion", wrong, side=SignalSide.SHORT)
    assert bool(wsig["pierce_up"].iloc[wf])
    assert bool(wsig["close_below_dhigh"].iloc[wf])
    assert not bool(wsig["bear_body"].iloc[wf])
    assert int(wsig["signal"].iloc[wf]) == 0


def test_catalog_option_b_not_approval_soft_watch_119_167():
    from config.pipeline import PAPER_SCAN_SLEEVES
    from firm.research_catalog import RESEARCH_HYPOTHESES
    from firm.research_jobs import CLOCK_BY_FAMILY
    from firm.sleeve_factory import spec_for_family

    row = next(r for r in RESEARCH_HYPOTHESES if r["family"] == "donchian_n_fail_reversion")
    assert row["id"] == "donchian_n_fail_reversion@4h/4h"
    assert row["coded"] is True and row["free_params"] == 2
    assert row.get("approved") is not True
    text = row["justification"].lower()
    assert "do not set approved=true" in text
    assert "live stays off" in text
    assert "soft-watch" in text and "119" in text and "167" in text
    assert "min_touches" in text  # independence note vs 167
    assert "same-bar" in text or "same bar" in text  # independence vs 119
    spec = spec_for_family("donchian_n_fail_reversion")
    assert spec and spec.clock == "4h/4h" and spec.side == "BOTH" and spec.auto_code is False
    assert CLOCK_BY_FAMILY["donchian_n_fail_reversion"] == "4h/4h"
    assert all(i[0] != "donchian_n_fail_reversion" for i in PAPER_SCAN_SLEEVES)


def test_independence_vs_failed_range_119_and_horizontal_167():
    """Soft independence: ≠119 delayed reclaim; ≠167 min_touches flat band."""
    from core.strategy import donchian_n_fail_reversion as ours
    from core.strategy import failed_range_break_reversion as job119
    from core.strategy import horizontal_liquidity_reject as job167

    # 119 carries max_bars_since_break (delayed reclaim); ours must not.
    assert "max_bars_since_break" in job119.FailedRangeBreakReversionParams.__dataclass_fields__
    assert "max_bars_since_break" not in ours.DonchianNFailReversionParams.__dataclass_fields__

    # 167 carries min_touches; ours must not.
    assert "min_touches" in job167.HorizontalLiquidityRejectParams.__dataclass_fields__
    assert "min_touches" not in ours.DonchianNFailReversionParams.__dataclass_fields__
    assert not hasattr(ours, "MIN_TOUCHES_GRID") and "min_touches" not in ours.__all__
    assert FORBID_MULTI_TOUCH_FLAT_BAND_LOCKED
    assert FORBID_EXTREME_FRAC_LOCKED and FORBID_NEXT_THRU_MID_LOCKED and FORBID_CLV_LOCKED
