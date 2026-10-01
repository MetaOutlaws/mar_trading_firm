"""Broken swing retest reject tests (Option B). No walk. No approval book."""

from __future__ import annotations

import numpy as np
import pytest

from core.strategy.base import SignalSide
from core.strategy.broken_swing_retest_reject import (
    ATR_N_LOCKED,
    CONTINUATION_ONLY_LOCKED,
    FORBID_CLOSE_THROUGH_SWING_LOCKED,
    OPTION_B_LOCKED,
    PIVOT_33_LOCKED,
    REQUIRE_PRIOR_CLOSE_BREAK_LOCKED,
    REQUIRE_REJECT_CLOSE_LOCKED,
    RETEST_BARS_GRID,
    SWING_LOOKBACK_GRID,
)
from tests.test_novel_sleeves import _hourly, _ohlcv, _signals


def _tape(*, short_side=True, mode="reject", lookback=5, retest_lag=2):
    """Craft a prior close-break then a retest bar.

    Layout (SHORT reject):
      bars 0..fire-lookback-2: flat ~100
      swing window ends just before break_i
      break_i: close above swing_high
      fire = break_i + retest_lag: low tags swing, close stays above (upper half)
    """
    n = 60
    atr_level = 1.0
    break_i = 40
    fire = break_i + retest_lag
    assert fire < n - 2
    assert retest_lag >= 1

    close = np.full(n, 100.0)
    high = np.full(n, 100.0 + 0.4 * atr_level)
    low = np.full(n, 100.0 - 0.4 * atr_level)
    open_ = np.full(n, 100.0)

    # Build a clear swing_high / swing_low over the lookback window before break.
    # For SHORT: swing_high comes from highs in [break_i-lookback, break_i).
    swing_level = 101.0 if short_side else 99.0
    for i in range(break_i - lookback, break_i):
        if short_side:
            high[i] = swing_level
            low[i] = swing_level - 1.0
            close[i] = open_[i] = swing_level - 0.3
        else:
            low[i] = swing_level
            high[i] = swing_level + 1.0
            close[i] = open_[i] = swing_level + 0.3

    # Warmup ATR with modest ranges.
    for i in range(0, break_i - lookback):
        high[i] = 100.0 + 0.5 * atr_level
        low[i] = 100.0 - 0.5 * atr_level
        close[i] = open_[i] = 100.0

    # Close-break bar.
    if short_side:
        open_[break_i] = swing_level + 0.1
        close[break_i] = swing_level + 0.8  # close > swing_high
        high[break_i] = close[break_i] + 0.1
        low[break_i] = swing_level + 0.05
    else:
        open_[break_i] = swing_level - 0.1
        close[break_i] = swing_level - 0.8  # close < swing_low
        low[break_i] = close[break_i] - 0.1
        high[break_i] = swing_level - 0.05

    # Bars between break and fire: stay on break side, no retest yet.
    for i in range(break_i + 1, fire):
        if short_side:
            open_[i] = close[i] = swing_level + 0.6
            high[i] = swing_level + 0.9
            low[i] = swing_level + 0.3  # above swing — no tag yet
        else:
            open_[i] = close[i] = swing_level - 0.6
            low[i] = swing_level - 0.9
            high[i] = swing_level - 0.3

    # Fire / alternate modes on the signal bar.
    if mode == "reject":
        if short_side:
            # Retest from above: low tags swing_high; close stays above; upper half.
            open_[fire] = swing_level + 0.4
            low[fire] = swing_level - 0.05  # tags
            high[fire] = swing_level + 0.7
            close[fire] = swing_level + 0.55  # >= swing, upper half
        else:
            open_[fire] = swing_level - 0.4
            high[fire] = swing_level + 0.05  # tags
            low[fire] = swing_level - 0.7
            close[fire] = swing_level - 0.55  # <= swing, lower half
    elif mode == "close_through_153":
        # Same retest tag but close goes back through the swing (=153 geometry).
        if short_side:
            open_[fire] = swing_level + 0.3
            high[fire] = swing_level + 0.5
            low[fire] = swing_level - 0.4
            close[fire] = swing_level - 0.25  # close < swing_high → DARK
        else:
            open_[fire] = swing_level - 0.3
            low[fire] = swing_level - 0.5
            high[fire] = swing_level + 0.4
            close[fire] = swing_level + 0.25  # close > swing_low → DARK
    elif mode == "no_reject_char":
        # Tags and stays on side, but close in wrong half (no reject character).
        if short_side:
            open_[fire] = swing_level + 0.5
            high[fire] = swing_level + 0.55
            low[fire] = swing_level - 0.05
            close[fire] = swing_level + 0.05  # lower half, still >= swing
        else:
            open_[fire] = swing_level - 0.5
            low[fire] = swing_level - 0.55
            high[fire] = swing_level + 0.05
            close[fire] = swing_level - 0.05  # upper half, still <= swing
    else:
        raise ValueError(mode)

    for i in range(fire + 1, n):
        high[i] = 100.0 + 0.5 * atr_level
        low[i] = 100.0 - 0.5 * atr_level
        close[i] = open_[i] = 100.0

    return _ohlcv(_hourly(n), close, high=high, low=low, open_=open_), fire, swing_level


def test_kit_locks_endpoints_only():
    from research.validate import strategy_kit

    assert (
        OPTION_B_LOCKED
        and REQUIRE_REJECT_CLOSE_LOCKED
        and CONTINUATION_ONLY_LOCKED
        and FORBID_CLOSE_THROUGH_SWING_LOCKED
        and REQUIRE_PRIOR_CLOSE_BREAK_LOCKED
        and PIVOT_33_LOCKED
    )
    factory, base, space = strategy_kit("broken_swing_retest_reject", SignalSide.SHORT)
    assert factory(base).name == "broken_swing_retest_reject"
    assert base.side is SignalSide.SHORT and base.atr_n == ATR_N_LOCKED == 20
    assert space["swing_lookback"] == SWING_LOOKBACK_GRID == [5, 8]
    assert space["retest_bars"] == RETEST_BARS_GRID == [3, 6]
    extra = {k for k in space if k not in {"take_profit_pct", "stop_loss_pct"}}
    assert extra == {"swing_lookback", "retest_bars"}


def test_short_fires_on_crafted_tape():
    candles, fire, _ = _tape(short_side=True, mode="reject", lookback=5, retest_lag=2)
    sig = _signals("broken_swing_retest_reject", candles, side=SignalSide.SHORT)
    assert int(sig["signal"].iloc[fire]) == -1
    assert sig["side"].iloc[fire] == "SHORT"
    assert bool(sig["stay_above"].iloc[fire])
    assert bool(sig["reject_upper_half"].iloc[fire])
    assert not bool(sig["close_through_high"].iloc[fire])


def test_long_fires_on_crafted_tape():
    candles, fire, _ = _tape(short_side=False, mode="reject", lookback=5, retest_lag=2)
    sig = _signals("broken_swing_retest_reject", candles, side=SignalSide.LONG)
    assert int(sig["signal"].iloc[fire]) == 1
    assert sig["side"].iloc[fire] == "LONG"
    assert bool(sig["stay_below"].iloc[fire])
    assert bool(sig["reject_lower_half"].iloc[fire])
    assert not bool(sig["close_through_low"].iloc[fire])


def test_close_through_153_style_stays_dark():
    candles, fire, _ = _tape(
        short_side=True, mode="close_through_153", lookback=5, retest_lag=2
    )
    sig = _signals("broken_swing_retest_reject", candles, side=SignalSide.SHORT)
    assert bool(sig["close_through_high"].iloc[fire])
    assert int(sig["signal"].iloc[fire]) == 0

    candles, fire, _ = _tape(
        short_side=False, mode="close_through_153", lookback=5, retest_lag=2
    )
    sig = _signals("broken_swing_retest_reject", candles, side=SignalSide.LONG)
    assert bool(sig["close_through_low"].iloc[fire])
    assert int(sig["signal"].iloc[fire]) == 0


def test_no_reject_character_stays_dark():
    candles, fire, _ = _tape(
        short_side=True, mode="no_reject_char", lookback=5, retest_lag=2
    )
    sig = _signals("broken_swing_retest_reject", candles, side=SignalSide.SHORT)
    assert bool(sig["stay_above"].iloc[fire])
    assert not bool(sig["reject_upper_half"].iloc[fire])
    assert int(sig["signal"].iloc[fire]) == 0


def test_catalog_option_b_not_approval():
    from config.pipeline import PAPER_SCAN_SLEEVES
    from firm.research_catalog import RESEARCH_HYPOTHESES
    from firm.research_jobs import CLOCK_BY_FAMILY
    from firm.sleeve_factory import spec_for_family

    row = next(r for r in RESEARCH_HYPOTHESES if r["family"] == "broken_swing_retest_reject")
    assert row["id"] == "broken_swing_retest_reject@4h/4h"
    assert row["coded"] is True and row["free_params"] == 2
    assert row.get("approved") is not True
    text = row["justification"].lower()
    assert "do not set approved=true" in text
    assert "live stays off" in text
    assert "soft-watch" in text and "153" in text
    spec = spec_for_family("broken_swing_retest_reject")
    assert spec and spec.clock == "4h/4h" and spec.side == "BOTH" and spec.auto_code is False
    assert CLOCK_BY_FAMILY["broken_swing_retest_reject"] == "4h/4h"
    assert all(i[0] != "broken_swing_retest_reject" for i in PAPER_SCAN_SLEEVES)
