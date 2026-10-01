"""Two-bar run mid fail tests (Option B). No walk. No approval book."""

from __future__ import annotations

import numpy as np
import pytest

from core.strategy.base import SignalSide
from core.strategy.two_bar_run_mid_fail import (
    ATR_N_LOCKED,
    FORBID_EXTREME_FRAC_LOCKED,
    FORBID_SINGLE_BAR_MID_LOCKED,
    MIN_RANGE_ATR_GRID,
    OPTION_B_LOCKED,
    REQUIRE_MONOTONIC_RUN_LOCKED,
    REQUIRE_TWO_BAR_ENVELOPE_MID_LOCKED,
    REQUIRE_TWO_SAME_COLOR_LOCKED,
)
from tests.test_novel_sleeves import _hourly, _ohlcv, _signals


def _tape(*, short_side=True, mode="fail", min_range=1.0, atr_level=1.0):
    """Craft a two-bar same-color monotonic run then a mid-fail close.

    Layout (SHORT fail):
      warmup: flat ~100 with ATR-ish ranges
      t-2 = fire-2: bullish close (green), mid-high
      t-1 = fire-1: bullish close higher (monotonic), higher high
      fire: close below two-bar envelope mid → SHORT
    """
    n = 50
    fire = 42
    t2, t1 = fire - 2, fire - 1
    assert t2 > ATR_N_LOCKED

    close = np.full(n, 100.0)
    high = np.full(n, 100.0 + 0.5 * atr_level)
    low = np.full(n, 100.0 - 0.5 * atr_level)
    open_ = np.full(n, 100.0)

    for i in range(t2):
        high[i] = 100.0 + 0.5 * atr_level
        low[i] = 100.0 - 0.5 * atr_level
        close[i] = open_[i] = 100.0

    # Two-bar envelope sized to clear min_range * ATR (~1.0).
    # Envelope range target ≈ min_range * atr_level + margin.
    env_span = max(min_range * atr_level + 0.2, 1.3)

    if short_side:
        # Bull run: two green closes, monotonic up.
        open_[t2] = 99.4
        close[t2] = 100.2
        low[t2] = 99.3
        high[t2] = 100.3
        open_[t1] = 100.1
        close[t1] = 100.8
        low[t1] = 100.0
        high[t1] = 99.3 + env_span  # so H-L = env_span
        H = max(high[t2], high[t1])
        L = min(low[t2], low[t1])
        mid = (H + L) / 2.0
        assert close[t2] > open_[t2] and close[t1] > open_[t1] and close[t1] > close[t2]
        assert (H - L) >= min_range * atr_level - 1e-9
        if mode == "fail":
            open_[fire] = mid + 0.05
            close[fire] = mid - 0.15  # through envelope mid down
            high[fire] = max(open_[fire], close[fire]) + 0.05
            low[fire] = min(open_[fire], close[fire]) - 0.05
        elif mode == "hold_above_mid":
            open_[fire] = mid + 0.2
            close[fire] = mid + 0.1  # stays above mid → DARK
            high[fire] = close[fire] + 0.05
            low[fire] = mid + 0.02
        elif mode == "tiny_range":
            # Shrink envelope well below min_range*ATR (~1.0); keep fail close.
            high[t2] = 100.15
            low[t2] = 99.85
            high[t1] = 100.20
            low[t1] = 100.00
            # preserve bull run colors/monotonic closes already set
            H = max(high[t2], high[t1])
            L = min(low[t2], low[t1])
            mid = (H + L) / 2.0
            assert (H - L) < 0.5  # clearly under 1.0 * ATR≈1
            open_[fire] = mid + 0.02
            close[fire] = mid - 0.05
            high[fire] = open_[fire] + 0.01
            low[fire] = close[fire] - 0.01
        else:
            raise ValueError(mode)
    else:
        # Bear run: two red closes, monotonic down.
        open_[t2] = 100.6
        close[t2] = 99.8
        high[t2] = 100.7
        low[t2] = 99.7
        open_[t1] = 99.9
        close[t1] = 99.2  # < close t-2
        high[t1] = 100.0
        low[t1] = 100.7 - env_span  # so H-L = env_span
        H = max(high[t2], high[t1])
        L = min(low[t2], low[t1])
        mid = (H + L) / 2.0
        assert close[t2] < open_[t2] and close[t1] < open_[t1] and close[t1] < close[t2]
        assert (H - L) >= min_range * atr_level - 1e-9
        if mode == "fail":
            open_[fire] = mid - 0.05
            close[fire] = mid + 0.15  # through envelope mid up
            high[fire] = max(open_[fire], close[fire]) + 0.05
            low[fire] = min(open_[fire], close[fire]) - 0.05
        elif mode == "hold_below_mid":
            open_[fire] = mid - 0.2
            close[fire] = mid - 0.1
            low[fire] = close[fire] - 0.05
            high[fire] = mid - 0.02
        else:
            raise ValueError(mode)

    for i in range(fire + 1, n):
        high[i] = 100.0 + 0.5 * atr_level
        low[i] = 100.0 - 0.5 * atr_level
        close[i] = open_[i] = 100.0

    return _ohlcv(_hourly(n), close, high=high, low=low, open_=open_), fire


def test_kit_locks_endpoints_only():
    from research.validate import strategy_kit

    assert (
        OPTION_B_LOCKED
        and REQUIRE_TWO_SAME_COLOR_LOCKED
        and REQUIRE_MONOTONIC_RUN_LOCKED
        and REQUIRE_TWO_BAR_ENVELOPE_MID_LOCKED
        and FORBID_EXTREME_FRAC_LOCKED
        and FORBID_SINGLE_BAR_MID_LOCKED
    )
    factory, base, space = strategy_kit("two_bar_run_mid_fail", SignalSide.SHORT)
    assert factory(base).name == "two_bar_run_mid_fail"
    assert base.side is SignalSide.SHORT and base.atr_n == ATR_N_LOCKED == 20
    assert space["min_range_atr"] == MIN_RANGE_ATR_GRID == [1.0, 1.5]
    extra = {k for k in space if k not in {"take_profit_pct", "stop_loss_pct"}}
    assert extra == {"min_range_atr"}
    assert "extreme_frac" not in space
    assert not hasattr(base, "extreme_frac")


def test_short_fires_on_crafted_tape():
    candles, fire = _tape(short_side=True, mode="fail")
    sig = _signals("two_bar_run_mid_fail", candles, side=SignalSide.SHORT)
    assert int(sig["signal"].iloc[fire]) == -1
    assert sig["side"].iloc[fire] == "SHORT"
    assert bool(sig["bull_run"].iloc[fire])
    assert bool(sig["through_down"].iloc[fire])
    assert bool(sig["sized"].iloc[fire])
    # Geometry uses TWO-BAR envelope mid, not a single-bar mid.
    assert float(sig["env_mid"].iloc[fire]) == pytest.approx(
        (float(sig["env_high"].iloc[fire]) + float(sig["env_low"].iloc[fire])) / 2.0
    )


def test_long_fires_on_crafted_tape():
    candles, fire = _tape(short_side=False, mode="fail")
    sig = _signals("two_bar_run_mid_fail", candles, side=SignalSide.LONG)
    assert int(sig["signal"].iloc[fire]) == 1
    assert sig["side"].iloc[fire] == "LONG"
    assert bool(sig["bear_run"].iloc[fire])
    assert bool(sig["through_up"].iloc[fire])


def test_hold_mid_and_tiny_range_stay_dark():
    candles, fire = _tape(short_side=True, mode="hold_above_mid")
    sig = _signals("two_bar_run_mid_fail", candles, side=SignalSide.SHORT)
    assert bool(sig["bull_run"].iloc[fire])
    assert not bool(sig["through_down"].iloc[fire])
    assert int(sig["signal"].iloc[fire]) == 0

    tiny, tf = _tape(short_side=True, mode="tiny_range")
    tsig = _signals("two_bar_run_mid_fail", tiny, side=SignalSide.SHORT)
    assert not bool(tsig["sized"].iloc[tf])
    assert int(tsig["signal"].iloc[tf]) == 0


def test_catalog_option_b_not_approval_soft_watch_165():
    from config.pipeline import PAPER_SCAN_SLEEVES
    from firm.research_catalog import RESEARCH_HYPOTHESES
    from firm.research_jobs import CLOCK_BY_FAMILY
    from firm.sleeve_factory import spec_for_family

    row = next(r for r in RESEARCH_HYPOTHESES if r["family"] == "two_bar_run_mid_fail")
    assert row["id"] == "two_bar_run_mid_fail@4h/4h"
    assert row["coded"] is True and row["free_params"] == 1
    assert row.get("approved") is not True
    text = row["justification"].lower()
    assert "do not set approved=true" in text
    assert "live stays off" in text
    assert "soft-watch" in text and "165" in text
    assert "extreme_frac" in text  # independence note vs 165
    spec = spec_for_family("two_bar_run_mid_fail")
    assert spec and spec.clock == "4h/4h" and spec.side == "BOTH" and spec.auto_code is False
    assert CLOCK_BY_FAMILY["two_bar_run_mid_fail"] == "4h/4h"
    assert all(i[0] != "two_bar_run_mid_fail" for i in PAPER_SCAN_SLEEVES)


def test_independence_vs_impulse_midpoint_fail_fade_165():
    """Soft independence note: 165 uses extreme_frac + single-bar mid; we do not."""
    from core.strategy import impulse_midpoint_fail_fade as job165
    from core.strategy import two_bar_run_mid_fail as ours

    assert hasattr(job165, "EXTREME_FRAC_GRID")
    assert not hasattr(ours, "EXTREME_FRAC_GRID")
    assert "extreme_frac" not in ours.__all__
    assert FORBID_EXTREME_FRAC_LOCKED and FORBID_SINGLE_BAR_MID_LOCKED
