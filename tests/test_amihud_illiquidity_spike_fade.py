"""Amihud illiquidity spike fade tests (Option B). No walk. No approval book."""

from __future__ import annotations

import numpy as np
import pytest

from core.strategy.base import SignalSide
from core.strategy.amihud_illiquidity_spike_fade import (
    CAUSAL_Z_PRIOR_LOOKBACK_LOCKED,
    FADE_SPIKE_BAR_BODY_LOCKED,
    FORBID_CLV_LOCKED,
    FORBID_EXTREME_FRAC_LOCKED,
    FORBID_NEXT_THRU_MID_LOCKED,
    LOOKBACK_GRID,
    OPTION_B_LOCKED,
    USE_EXISTING_TURNOVER_OR_VOLUME_X_CLOSE_LOCKED,
    Z_MIN_GRID,
)
from tests.test_novel_sleeves import _hourly, _ohlcv, _signals


def _tape(*, short_side=True, mode="spike", lookback=20, z_min=2.0):
    """Craft an Amihud z-spike on an up (SHORT) or down (LONG) bar.

    Layout:
      warmup: small alternating |ret| with normal turnover → modest amihud base
      fire: large |ret| on tiny turnover → z >> z_min; body matches side
    """
    n = 80
    fire = 50
    assert fire > lookback + 3

    close = np.full(n, 100.0)
    high = np.full(n, 100.5)
    low = np.full(n, 99.5)
    open_ = np.full(n, 100.0)
    volume = np.full(n, 1_000.0)

    # Varied moves + volumes so prior amihud mean/std are healthy & nonzero.
    steps = [0.05, -0.08, 0.12, -0.06, 0.09, -0.11, 0.07, -0.10]
    vols = [800.0, 1200.0, 900.0, 1500.0, 700.0, 1100.0, 950.0, 1300.0]
    for i in range(1, fire):
        step = steps[i % len(steps)]
        open_[i] = close[i - 1]
        close[i] = close[i - 1] + step
        high[i] = max(open_[i], close[i]) + 0.05
        low[i] = min(open_[i], close[i]) - 0.05
        volume[i] = vols[i % len(vols)]

    # Fire bar: large body move, tiny turnover → Amihud spike.
    open_[fire] = close[fire - 1]
    if short_side:
        # Up bar: fade SHORT
        if mode == "spike":
            close[fire] = open_[fire] + 5.0  # ~5% ret
            volume[fire] = 5.0  # tiny quote proxy
        elif mode == "no_spike":
            close[fire] = open_[fire] + 0.05  # tiny ret, normal volume
            volume[fire] = 1_000.0
        elif mode == "wrong_body":
            # High z but down body → SHORT must stay dark
            close[fire] = open_[fire] - 5.0
            volume[fire] = 5.0
        else:
            raise ValueError(mode)
    else:
        # Down bar: fade LONG
        if mode == "spike":
            close[fire] = open_[fire] - 5.0
            volume[fire] = 5.0
        elif mode == "no_spike":
            close[fire] = open_[fire] - 0.05
            volume[fire] = 1_000.0
        elif mode == "wrong_body":
            close[fire] = open_[fire] + 5.0
            volume[fire] = 5.0
        else:
            raise ValueError(mode)

    high[fire] = max(open_[fire], close[fire]) + 0.1
    low[fire] = min(open_[fire], close[fire]) - 0.1

    for i in range(fire + 1, n):
        open_[i] = close[i] = close[fire]
        high[i] = close[i] + 0.5
        low[i] = close[i] - 0.5
        volume[i] = 1_000.0

    candles = _ohlcv(_hourly(n), close, high=high, low=low, open_=open_)
    # _ohlcv sets turnover = volume * close by default using volume=1000;
    # override volume + turnover to match the crafted quote proxy.
    candles["volume"] = volume
    candles["turnover"] = volume * candles["close"].to_numpy()
    return candles, fire


def test_kit_locks_endpoints_only():
    from research.validate import strategy_kit

    assert (
        OPTION_B_LOCKED
        and FADE_SPIKE_BAR_BODY_LOCKED
        and CAUSAL_Z_PRIOR_LOOKBACK_LOCKED
        and FORBID_EXTREME_FRAC_LOCKED
        and FORBID_NEXT_THRU_MID_LOCKED
        and FORBID_CLV_LOCKED
        and USE_EXISTING_TURNOVER_OR_VOLUME_X_CLOSE_LOCKED
    )
    factory, base, space = strategy_kit("amihud_illiquidity_spike_fade", SignalSide.SHORT)
    assert factory(base).name == "amihud_illiquidity_spike_fade"
    assert base.side is SignalSide.SHORT
    assert space["lookback"] == LOOKBACK_GRID == [20, 40]
    assert space["z_min"] == Z_MIN_GRID == [2.0, 2.5]
    extra = {k for k in space if k not in {"take_profit_pct", "stop_loss_pct"}}
    assert extra == {"lookback", "z_min"}
    # FORBID mid/CLV/extreme_frac in search space and on params.
    for banned in ("extreme_frac", "clv", "next_thru_mid", "reject_frac", "thru_mid"):
        assert banned not in space
        assert not hasattr(base, banned)


def test_short_fires_on_crafted_tape():
    candles, fire = _tape(short_side=True, mode="spike")
    sig = _signals("amihud_illiquidity_spike_fade", candles, side=SignalSide.SHORT)
    assert int(sig["signal"].iloc[fire]) == -1
    assert sig["side"].iloc[fire] == "SHORT"
    assert bool(sig["spike"].iloc[fire])
    assert bool(sig["up_bar"].iloc[fire])
    assert float(sig["z"].iloc[fire]) >= 2.0


def test_long_fires_on_crafted_tape():
    candles, fire = _tape(short_side=False, mode="spike")
    sig = _signals("amihud_illiquidity_spike_fade", candles, side=SignalSide.LONG)
    assert int(sig["signal"].iloc[fire]) == 1
    assert sig["side"].iloc[fire] == "LONG"
    assert bool(sig["spike"].iloc[fire])
    assert bool(sig["down_bar"].iloc[fire])
    assert float(sig["z"].iloc[fire]) >= 2.0


def test_no_spike_and_wrong_body_stay_dark():
    candles, fire = _tape(short_side=True, mode="no_spike")
    sig = _signals("amihud_illiquidity_spike_fade", candles, side=SignalSide.SHORT)
    assert not bool(sig["spike"].iloc[fire])
    assert int(sig["signal"].iloc[fire]) == 0

    wrong, wf = _tape(short_side=True, mode="wrong_body")
    wsig = _signals("amihud_illiquidity_spike_fade", wrong, side=SignalSide.SHORT)
    assert bool(wsig["spike"].iloc[wf])  # z still high
    assert bool(wsig["down_bar"].iloc[wf])  # but wrong body for SHORT
    assert int(wsig["signal"].iloc[wf]) == 0


def test_catalog_option_b_not_approval_soft_watch_103():
    from config.pipeline import PAPER_SCAN_SLEEVES
    from firm.research_catalog import RESEARCH_HYPOTHESES
    from firm.research_jobs import CLOCK_BY_FAMILY
    from firm.sleeve_factory import spec_for_family

    row = next(r for r in RESEARCH_HYPOTHESES if r["family"] == "amihud_illiquidity_spike_fade")
    assert row["id"] == "amihud_illiquidity_spike_fade@4h/4h"
    assert row["coded"] is True and row["free_params"] == 2
    assert row.get("approved") is not True
    text = row["justification"].lower()
    assert "do not set approved=true" in text
    assert "live stays off" in text
    assert "soft-watch" in text and "103" in text
    assert "reject_frac" in text  # independence note vs 103
    spec = spec_for_family("amihud_illiquidity_spike_fade")
    assert spec and spec.clock == "4h/4h" and spec.side == "BOTH" and spec.auto_code is False
    assert CLOCK_BY_FAMILY["amihud_illiquidity_spike_fade"] == "4h/4h"
    assert all(i[0] != "amihud_illiquidity_spike_fade" for i in PAPER_SCAN_SLEEVES)


def test_independence_vs_turnover_climax_rejection_fade_103():
    """Soft independence: 103 uses climax+prior H/L break+reject_frac; we do not."""
    from core.strategy import amihud_illiquidity_spike_fade as ours
    from core.strategy import turnover_climax_rejection_fade as job103

    assert hasattr(job103, "TurnoverClimaxRejectionFadeParams")
    # 103 params carry reject_frac; ours must not.
    assert "reject_frac" in job103.TurnoverClimaxRejectionFadeParams.__dataclass_fields__
    assert "reject_frac" not in ours.AmihudIlliquiditySpikeFadeParams.__dataclass_fields__
    assert not hasattr(ours, "REJECT_FRAC") and "reject_frac" not in ours.__all__
    assert FORBID_EXTREME_FRAC_LOCKED and FORBID_NEXT_THRU_MID_LOCKED and FORBID_CLV_LOCKED
