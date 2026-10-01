"""Garman-Klass OHLC vol spike fade tests (Option B). No walk. No approval book."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from core.strategy.base import SignalSide
from core.strategy.garman_klass_vol_spike_fade import (
    CAUSAL_Z_PRIOR_LOOKBACK_LOCKED,
    EPS_LOCKED,
    FADE_SPIKE_BAR_BODY_LOCKED,
    FORBID_CLV_LOCKED,
    FORBID_COMPRESSION_LOCKED,
    FORBID_DONCHIAN_LOCKED,
    FORBID_EXTREME_FRAC_LOCKED,
    FORBID_NEXT_THRU_MID_LOCKED,
    FORBID_VOLUME_IN_SIGNAL_LOCKED,
    FORBID_WICK_FRAC_LOCKED,
    LOOKBACK_GRID,
    OHLC_ONLY_GARMAN_KLASS_LOCKED,
    OPTION_B_LOCKED,
    Z_MIN_GRID,
    GarmanKlassVolSpikeFadeParams,
    GarmanKlassVolSpikeFadeStrategy,
    _garman_klass,
)
from tests.test_novel_sleeves import _hourly, _ohlcv, _signals


def _tape(*, short_side=True, mode="spike", lookback=20, z_min=2.0):
    """Craft a Garman-Klass z-spike on an up (SHORT) or down (LONG) bar.

    Layout:
      warmup: tight ranges -> modest GK base with nonzero std
      fire: huge range (large hl) -> z >> z_min; body matches side
    """
    n = 80
    fire = 50
    assert fire > lookback + 3

    close = np.full(n, 100.0)
    high = np.full(n, 100.3)
    low = np.full(n, 99.7)
    open_ = np.full(n, 100.0)
    volume = np.full(n, 1_000.0)

    # Varied small ranges so prior GK mean/std are healthy & nonzero.
    for i in range(1, fire):
        open_[i] = 100.0 + (0.05 if i % 2 == 0 else -0.05)
        close[i] = 100.0 + (-0.04 if i % 2 == 0 else 0.04)
        # Alternating mild range so GK has variance.
        span = 0.4 + 0.15 * (i % 5)
        mid = (open_[i] + close[i]) / 2.0
        high[i] = mid + span / 2.0
        low[i] = mid - span / 2.0
        volume[i] = 800.0 + 50.0 * (i % 7)

    # Fire bar: huge range -> GK spike; body matches side.
    open_[fire] = close[fire - 1]
    if short_side:
        if mode == "spike":
            close[fire] = open_[fire] + 0.5  # up body
            high[fire] = open_[fire] + 8.0   # huge range
            low[fire] = open_[fire] - 7.5
            volume[fire] = 5.0  # volume changed shouldn't matter
        elif mode == "no_spike":
            close[fire] = open_[fire] + 0.05
            high[fire] = max(open_[fire], close[fire]) + 0.2
            low[fire] = min(open_[fire], close[fire]) - 0.2
            volume[fire] = 1_000.0
        elif mode == "wrong_body":
            # High z but down body -> SHORT must stay dark
            close[fire] = open_[fire] - 0.5
            high[fire] = open_[fire] + 7.5
            low[fire] = open_[fire] - 8.0
            volume[fire] = 5.0
        else:
            raise ValueError(mode)
    else:
        if mode == "spike":
            close[fire] = open_[fire] - 0.5  # down body
            high[fire] = open_[fire] + 7.5
            low[fire] = open_[fire] - 8.0
            volume[fire] = 5.0
        elif mode == "no_spike":
            close[fire] = open_[fire] - 0.05
            high[fire] = max(open_[fire], close[fire]) + 0.2
            low[fire] = min(open_[fire], close[fire]) - 0.2
            volume[fire] = 1_000.0
        elif mode == "wrong_body":
            close[fire] = open_[fire] + 0.5
            high[fire] = open_[fire] + 8.0
            low[fire] = open_[fire] - 7.5
            volume[fire] = 5.0
        else:
            raise ValueError(mode)

    for i in range(fire + 1, n):
        open_[i] = close[i] = close[fire]
        high[i] = close[i] + 0.3
        low[i] = close[i] - 0.3
        volume[i] = 1_000.0

    candles = _ohlcv(_hourly(n), close, high=high, low=low, open_=open_)
    candles["volume"] = volume
    candles["turnover"] = volume * candles["close"].to_numpy()
    return candles, fire


def test_forbid_locks_true():
    assert (
        OPTION_B_LOCKED
        and FADE_SPIKE_BAR_BODY_LOCKED
        and CAUSAL_Z_PRIOR_LOOKBACK_LOCKED
        and FORBID_EXTREME_FRAC_LOCKED
        and FORBID_NEXT_THRU_MID_LOCKED
        and FORBID_CLV_LOCKED
        and FORBID_VOLUME_IN_SIGNAL_LOCKED
        and FORBID_WICK_FRAC_LOCKED
        and FORBID_DONCHIAN_LOCKED
        and FORBID_COMPRESSION_LOCKED
        and OHLC_ONLY_GARMAN_KLASS_LOCKED
    )


def test_gk_formula_smoke_known_bar():
    """Known OHLC bar: open=100, high=110, low=90, close=105."""
    o = pd.Series([100.0])
    h = pd.Series([110.0])
    l = pd.Series([90.0])
    c = pd.Series([105.0])
    hl = math.log(110.0 / 90.0)
    co = math.log(105.0 / 100.0)
    expected = 0.5 * hl * hl - (2.0 * math.log(2.0) - 1.0) * co * co
    got = float(_garman_klass(o, h, l, c).iloc[0])
    assert got == pytest.approx(expected, rel=1e-12)
    assert got > EPS_LOCKED


def test_kit_locks_endpoints_only():
    from research.validate import strategy_kit

    factory, base, space = strategy_kit("garman_klass_vol_spike_fade", SignalSide.SHORT)
    assert factory(base).name == "garman_klass_vol_spike_fade"
    assert base.side is SignalSide.SHORT
    assert space["lookback"] == LOOKBACK_GRID == [20, 40]
    assert space["z_min"] == Z_MIN_GRID == [2.0, 2.5]
    extra = {k for k in space if k not in {"take_profit_pct", "stop_loss_pct"}}
    assert extra == {"lookback", "z_min"}
    for banned in (
        "extreme_frac",
        "clv",
        "next_thru_mid",
        "wick_frac",
        "volume",
        "turnover",
        "donchian",
        "compression",
        "atr_frac",
        "amihud",
    ):
        assert banned not in space
        assert not hasattr(base, banned)


def test_short_fires_on_crafted_tape():
    candles, fire = _tape(short_side=True, mode="spike")
    sig = _signals("garman_klass_vol_spike_fade", candles, side=SignalSide.SHORT)
    assert int(sig["signal"].iloc[fire]) == -1
    assert sig["side"].iloc[fire] == "SHORT"
    assert bool(sig["spike"].iloc[fire])
    assert bool(sig["up_bar"].iloc[fire])
    assert float(sig["z"].iloc[fire]) >= 2.0


def test_long_fires_on_crafted_tape():
    candles, fire = _tape(short_side=False, mode="spike")
    sig = _signals("garman_klass_vol_spike_fade", candles, side=SignalSide.LONG)
    assert int(sig["signal"].iloc[fire]) == 1
    assert sig["side"].iloc[fire] == "LONG"
    assert bool(sig["spike"].iloc[fire])
    assert bool(sig["down_bar"].iloc[fire])
    assert float(sig["z"].iloc[fire]) >= 2.0


def test_volume_unused_in_signal_path():
    """Volume column present: changing volume must not change signals (OHLC-only)."""
    candles, fire = _tape(short_side=True, mode="spike")
    strat = GarmanKlassVolSpikeFadeStrategy(
        GarmanKlassVolSpikeFadeParams(side=SignalSide.SHORT, lookback=20, z_min=2.0)
    )
    assert "volume" in candles.columns and "turnover" in candles.columns
    sig_a = strat.generate_signals(candles)

    alt = candles.copy()
    alt["volume"] = candles["volume"] * 1_000.0 + 999.0
    alt["turnover"] = alt["volume"] * alt["close"]
    # Also inject quote_volume to ensure unused.
    alt["quote_volume"] = alt["turnover"] * 2.0
    sig_b = strat.generate_signals(alt)

    pd.testing.assert_series_equal(sig_a["signal"], sig_b["signal"], check_names=False)
    pd.testing.assert_series_equal(sig_a["z"], sig_b["z"], check_names=False)
    pd.testing.assert_series_equal(sig_a["gk"], sig_b["gk"], check_names=False)
    assert int(sig_a["signal"].iloc[fire]) == -1


def test_no_lookahead_future_bars_do_not_change_past():
    candles, fire = _tape(short_side=True, mode="spike")
    strat = GarmanKlassVolSpikeFadeStrategy(
        GarmanKlassVolSpikeFadeParams(side=SignalSide.SHORT, lookback=20, z_min=2.0)
    )
    sig_full = strat.generate_signals(candles)

    mutated = candles.copy()
    # Mutate future bars after fire -- past signals through fire must match.
    for i in range(fire + 1, len(mutated)):
        mutated.iloc[i, mutated.columns.get_loc("high")] = float(mutated["high"].iloc[i]) + 50.0
        mutated.iloc[i, mutated.columns.get_loc("low")] = float(mutated["low"].iloc[i]) - 50.0
        mutated.iloc[i, mutated.columns.get_loc("close")] = float(mutated["close"].iloc[i]) + 10.0
        mutated.iloc[i, mutated.columns.get_loc("open")] = float(mutated["open"].iloc[i]) - 10.0
    sig_mut = strat.generate_signals(mutated)

    past = slice(None, fire + 1)
    pd.testing.assert_series_equal(
        sig_full["signal"].iloc[past], sig_mut["signal"].iloc[past], check_names=False
    )
    pd.testing.assert_series_equal(
        sig_full["z"].iloc[past], sig_mut["z"].iloc[past], check_names=False
    )
    pd.testing.assert_series_equal(
        sig_full["gk"].iloc[past], sig_mut["gk"].iloc[past], check_names=False
    )


def test_no_spike_and_wrong_body_stay_dark():
    candles, fire = _tape(short_side=True, mode="no_spike")
    sig = _signals("garman_klass_vol_spike_fade", candles, side=SignalSide.SHORT)
    assert not bool(sig["spike"].iloc[fire])
    assert int(sig["signal"].iloc[fire]) == 0

    wrong, wf = _tape(short_side=True, mode="wrong_body")
    wsig = _signals("garman_klass_vol_spike_fade", wrong, side=SignalSide.SHORT)
    assert bool(wsig["spike"].iloc[wf])  # z still high
    assert bool(wsig["down_bar"].iloc[wf])  # but wrong body for SHORT
    assert int(wsig["signal"].iloc[wf]) == 0


def test_catalog_option_b_not_approval_soft_watch_172():
    from config.pipeline import PAPER_SCAN_SLEEVES
    from firm.research_catalog import RESEARCH_HYPOTHESES
    from firm.research_jobs import CLOCK_BY_FAMILY
    from firm.sleeve_factory import spec_for_family

    row = next(r for r in RESEARCH_HYPOTHESES if r["family"] == "garman_klass_vol_spike_fade")
    assert row["id"] == "garman_klass_vol_spike_fade@4h/4h"
    assert row["coded"] is True and row["free_params"] == 2
    assert row.get("approved") is not True
    text = row["justification"].lower()
    assert "do not set approved=true" in text
    assert "live stays off" in text
    assert "soft-watch" in text and "172" in text
    assert "amihud" in text  # independence note vs 172
    assert "volume" in text  # FORBID volume-in-signal note
    spec = spec_for_family("garman_klass_vol_spike_fade")
    assert spec and spec.clock == "4h/4h" and spec.side == "BOTH" and spec.auto_code is False
    assert CLOCK_BY_FAMILY["garman_klass_vol_spike_fade"] == "4h/4h"
    assert all(i[0] != "garman_klass_vol_spike_fade" for i in PAPER_SCAN_SLEEVES)
