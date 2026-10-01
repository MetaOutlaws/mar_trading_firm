"""Body gap fail reversion tests (Option B). No walk. No approval book."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from core.strategy.base import SignalSide
from core.strategy.body_gap_fail_reversion import (
    ATR_N_LOCKED,
    FORBID_FOLLOW_CONTINUATION_LOCKED,
    MIN_GAP_ATR_GRID,
    MIN_PRIOR_RANGE_ATR_GRID,
    OPTION_B_LOCKED,
    REQUIRE_CLOSE_RECLAIM_INSIDE_LOCKED,
)
from tests.test_novel_sleeves import _hourly, _ohlcv, _signals


def _tape(*, short_side=True, gap_atr=0.20, prior_range=1.0, mode="reclaim", atr_level=1.0):
    n, fire = 50, 42
    prior_i = fire - 1
    close = np.full(n, 100.0)
    high = np.full(n, 100.0 + 0.5 * atr_level)
    low = np.full(n, 100.0 - 0.5 * atr_level)
    open_ = np.full(n, 100.0)
    mid, half = 100.0, prior_range / 2.0
    high[prior_i], low[prior_i] = mid + half, mid - half
    close[prior_i] = open_[prior_i] = mid
    for i in range(prior_i):
        high[i], low[i] = 100.0 + 0.5 * atr_level, 100.0 - 0.5 * atr_level
        close[i] = open_[i] = 100.0
    ph, pl = float(high[prior_i]), float(low[prior_i])
    gap = gap_atr * atr_level
    open_fire = (ph + gap) if short_side else (pl - gap)
    if mode == "follow":
        close_fire = (ph + gap * 0.5) if short_side else (pl - gap * 0.5)
    elif mode == "tiny_gap":
        open_fire = (ph + 0.05 * atr_level) if short_side else (pl - 0.05 * atr_level)
        close_fire = mid
    elif mode == "flat_prior":
        high[prior_i], low[prior_i] = mid + 0.05, mid - 0.05
        ph, pl = float(high[prior_i]), float(low[prior_i])
        open_fire = (ph + gap) if short_side else (pl - gap)
        close_fire = mid
    else:
        close_fire = mid
    open_[fire], close[fire] = open_fire, close_fire
    high[fire] = max(open_fire, close_fire, ph) + 0.02
    low[fire] = min(open_fire, close_fire, pl) - 0.02
    for i in range(fire + 1, n):
        high[i], low[i] = 100.0 + 0.5 * atr_level, 100.0 - 0.5 * atr_level
        close[i] = open_[i] = 100.0
    return _ohlcv(_hourly(n), close, high=high, low=low, open_=open_), fire


def test_kit_locks_endpoints_only():
    from research.validate import strategy_kit
    assert OPTION_B_LOCKED and REQUIRE_CLOSE_RECLAIM_INSIDE_LOCKED and FORBID_FOLLOW_CONTINUATION_LOCKED
    factory, base, space = strategy_kit("body_gap_fail_reversion", SignalSide.SHORT)
    assert factory(base).name == "body_gap_fail_reversion"
    assert base.side is SignalSide.SHORT and base.atr_n == ATR_N_LOCKED == 20
    assert space["min_gap_atr"] == MIN_GAP_ATR_GRID == [0.10, 0.25]
    assert space["min_prior_range_atr"] == MIN_PRIOR_RANGE_ATR_GRID == [0.5, 1.0]
    extra = {k for k in space if k not in {"take_profit_pct", "stop_loss_pct"}}
    assert extra == {"min_gap_atr", "min_prior_range_atr"}


def test_short_and_long_reclaim():
    candles, fire = _tape(short_side=True, mode="reclaim")
    sig = _signals("body_gap_fail_reversion", candles, side=SignalSide.SHORT)
    assert int(sig["signal"].iloc[fire]) == -1
    assert sig["side"].iloc[fire] == "SHORT"
    assert bool(sig["close_inside"].iloc[fire]) and not bool(sig["follow_up"].iloc[fire])
    candles, fire = _tape(short_side=False, mode="reclaim")
    sig = _signals("body_gap_fail_reversion", candles, side=SignalSide.LONG)
    assert int(sig["signal"].iloc[fire]) == 1


def test_follow_forbidden_and_tiny_gap_dark():
    from research.validate import strategy_kit
    candles, fire = _tape(short_side=True, mode="follow")
    sig = _signals("body_gap_fail_reversion", candles, side=SignalSide.SHORT)
    assert bool(sig["follow_up"].iloc[fire]) and int(sig["signal"].iloc[fire]) == 0
    factory, base, _ = strategy_kit("body_gap_fail_reversion", SignalSide.SHORT)
    forced = factory(replace(base, forbid_follow_continuation=False)).generate_signals(candles)
    assert int(forced["signal"].iloc[fire]) == 0
    tiny, tf = _tape(short_side=True, mode="tiny_gap")
    assert int(_signals("body_gap_fail_reversion", tiny, side=SignalSide.SHORT)["signal"].iloc[tf]) == 0
    assert int(_signals("open_in_prior_range_fail", tiny, side=SignalSide.SHORT)["signal"].iloc[tf]) == -1


def test_catalog_option_b_not_approval():
    from config.pipeline import PAPER_SCAN_SLEEVES
    from firm.research_catalog import RESEARCH_HYPOTHESES
    from firm.research_jobs import CLOCK_BY_FAMILY
    from firm.sleeve_factory import spec_for_family
    row = next(r for r in RESEARCH_HYPOTHESES if r["family"] == "body_gap_fail_reversion")
    assert row["id"] == "body_gap_fail_reversion@4h/4h"
    assert row["coded"] is True and row["free_params"] == 2
    assert row.get("approved") is not True
    text = row["justification"].lower()
    assert "do not set approved=true" in text and "live stays off" in text
    spec = spec_for_family("body_gap_fail_reversion")
    assert spec and spec.clock == "4h/4h" and spec.side == "BOTH" and spec.auto_code is False
    assert CLOCK_BY_FAMILY["body_gap_fail_reversion"] == "4h/4h"
    assert all(i[0] != "body_gap_fail_reversion" for i in PAPER_SCAN_SLEEVES)
