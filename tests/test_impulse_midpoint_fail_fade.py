"""Impulse midpoint fail fade: two-bar geometry, locks, and independence.

Option B. The signal is the bar that closes through the impulse midpoint.
Fill stays the engine t+1 open. These tests do not start a walk and do not
touch the approval book.
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from core.strategy.base import SignalSide
from core.strategy.impulse_midpoint_fail_fade import (
    ATR_N_LOCKED,
    EXTREME_FRAC_GRID,
    MIN_RANGE_ATR_GRID,
    OPTION_B_LOCKED,
    REQUIRE_NEXT_CLOSE_THROUGH_MID_LOCKED,
)
from tests.test_novel_sleeves import _hourly, _ohlcv, _signals


def _tape(
    *,
    bullish: bool = True,
    impulse_range: float = 1.8,
    close_frac: float = 0.85,
    fail_mode: str = "beyond",
) -> tuple[pd.DataFrame, int]:
    """Quiet ATR~1 tape with one impulse at ``fire - 1``.

    ``fail_mode``
        beyond: next close through the mid and past the opposite rail
        inside: next close through the mid but still inside the impulse bar
        on_mid: next close sits on the midpoint
        hold: next close stays on the impulse side of the midpoint
    The bar before the impulse overlaps on one rail only, so the impulse
    is not an outside bar.
    """
    n = 50
    fire = 42
    impulse_i = fire - 1
    pre_i = fire - 2
    close = np.full(n, 100.0)
    high = np.full(n, 100.5)
    low = np.full(n, 99.5)
    open_ = np.full(n, 100.0)
    # One-sided overlap with the impulse so this is not outside-bar containment.
    if bullish:
        low_i = 100.0
        high_i = low_i + impulse_range
        high[pre_i] = high_i - 0.6
        low[pre_i] = low_i - 1.2
    else:
        high_i = 100.0
        low_i = high_i - impulse_range
        high[pre_i] = high_i + 1.2
        low[pre_i] = low_i + 0.6
    close[pre_i] = (high[pre_i] + low[pre_i]) / 2.0
    open_[pre_i] = close[pre_i]
    # Keep the impulse close inside its own high-low at the requested fraction.
    frac = float(np.clip(close_frac, 0.02, 0.98))
    impulse_close = low_i + frac * impulse_range
    high[impulse_i] = high_i
    low[impulse_i] = low_i
    close[impulse_i] = impulse_close
    open_[impulse_i] = impulse_close
    mid = (high_i + low_i) / 2.0
    if fail_mode == "on_mid":
        fail_close = mid
        fail_high = max(mid + 0.15, high_i - 0.05)
        fail_low = min(mid - 0.15, low_i + 0.05)
    elif fail_mode == "hold":
        # Stay on the impulse side of the midpoint. Not a fail.
        if bullish:
            fail_close = mid + 0.25
        else:
            fail_close = mid - 0.25
        fail_high = fail_close + 0.1
        fail_low = fail_close - 0.1
    elif fail_mode == "inside":
        # Through the mid, still strictly inside the impulse high-low.
        if bullish:
            fail_close = (low_i + mid) / 2.0
        else:
            fail_close = (high_i + mid) / 2.0
        fail_high = max(impulse_close, fail_close) + 0.05
        fail_low = min(impulse_close, fail_close) - 0.05
        fail_high = min(fail_high, high_i - 0.02)
        fail_low = max(fail_low, low_i + 0.02)
    else:
        # Beyond the opposite rail. Expansion / outside require a close
        # that stays inside the prior bar, so this print is not their fail.
        if bullish:
            fail_close = low_i - 0.25
        else:
            fail_close = high_i + 0.25
        fail_high = fail_close + 0.2
        fail_low = fail_close - 0.2
    high[fire] = fail_high
    low[fire] = fail_low
    close[fire] = fail_close
    open_[fire] = fail_close
    # Later bars are too narrow, and close in the middle, to be a second impulse.
    for i in range(fire + 1, n):
        high[i] = 100.2
        low[i] = 99.8
        close[i] = 100.0
        open_[i] = 100.0
    index = _hourly(n)
    candles = _ohlcv(index, close, high=high, low=low, open_=open_)
    return candles, fire


def test_kit_locks_endpoints_only() -> None:
    from research.validate import strategy_kit

    assert OPTION_B_LOCKED is True
    factory, base, space = strategy_kit("impulse_midpoint_fail_fade", SignalSide.SHORT)
    sleeve = factory(base)
    assert sleeve.name == "impulse_midpoint_fail_fade"
    assert base.side is SignalSide.SHORT
    assert base.atr_n == ATR_N_LOCKED == 20
    assert base.min_range_atr == pytest.approx(1.5)
    assert base.extreme_frac == pytest.approx(0.25)
    assert base.require_next_close_through_mid is REQUIRE_NEXT_CLOSE_THROUGH_MID_LOCKED
    assert space["min_range_atr"] == MIN_RANGE_ATR_GRID == [1.5, 2.0]
    assert space["extreme_frac"] == EXTREME_FRAC_GRID == [0.25, 0.35]
    assert "atr_n" not in space
    assert "require_next_close_through_mid" not in space
    extra = {k for k in space if k not in {"take_profit_pct", "stop_loss_pct"}}
    assert extra == {"min_range_atr", "extreme_frac"}
    assert len(extra) <= 2
    long_factory, long_base, long_space = strategy_kit(
        "impulse_midpoint_fail_fade", SignalSide.LONG
    )
    assert long_factory(long_base).name == "impulse_midpoint_fail_fade"
    assert long_base.side is SignalSide.LONG
    assert long_space["min_range_atr"] == [1.5, 2.0]
    assert long_space["extreme_frac"] == [0.25, 0.35]


def test_short_after_bullish_impulse_fail() -> None:
    from research.validate import strategy_kit

    candles, fire = _tape(bullish=True, close_frac=0.85, fail_mode="beyond")
    signals = _signals("impulse_midpoint_fail_fade", candles, side=SignalSide.SHORT)
    assert bool(signals["bullish_impulse"].iloc[fire])
    assert not bool(signals["bearish_impulse"].iloc[fire])
    assert bool(signals["sized"].iloc[fire])
    assert bool(signals["through_down"].iloc[fire])
    assert signals["impulse_close_frac"].iloc[fire] >= 0.75
    assert signals["range_atr"].iloc[fire] >= 1.5
    assert signals["range_atr"].iloc[fire] < 2.0
    assert int(signals["signal"].iloc[fire]) == -1
    assert signals["side"].iloc[fire] == "SHORT"
    # The impulse bar itself is not the entry. Fill is the next open.
    assert int(signals["signal"].iloc[fire - 1]) == 0
    assert int((signals["signal"] != 0).sum()) == 1
    assert signals["score"].iloc[fire] > 0
    # Stricter range floor on the same tape does not invent an interior.
    factory, base, _space = strategy_kit("impulse_midpoint_fail_fade", SignalSide.SHORT)
    wider = factory(replace(base, min_range_atr=2.0)).generate_signals(candles)
    assert int(wider["signal"].iloc[fire]) == 0
    long_on_short = _signals("impulse_midpoint_fail_fade", candles, side=SignalSide.LONG)
    assert int(long_on_short["signal"].iloc[fire]) == 0


def test_long_after_bearish_impulse_fail() -> None:
    candles, fire = _tape(bullish=False, close_frac=0.12, fail_mode="beyond")
    signals = _signals("impulse_midpoint_fail_fade", candles, side=SignalSide.LONG)
    assert bool(signals["bearish_impulse"].iloc[fire])
    assert not bool(signals["bullish_impulse"].iloc[fire])
    assert bool(signals["through_up"].iloc[fire])
    assert signals["impulse_close_frac"].iloc[fire] <= 0.25
    assert int(signals["signal"].iloc[fire]) == 1
    assert signals["side"].iloc[fire] == "LONG"
    assert int(signals["signal"].iloc[fire - 1]) == 0
    short_on_long = _signals("impulse_midpoint_fail_fade", candles, side=SignalSide.SHORT)
    assert int(short_on_long["signal"].iloc[fire]) == 0


def test_extreme_frac_grid_is_the_only_location_gate() -> None:
    """0.35 accepts a close the 0.25 endpoint rejects. No interior is searched."""
    from research.validate import strategy_kit

    candles, fire = _tape(bullish=True, close_frac=0.68, fail_mode="beyond")
    factory, base, _space = strategy_kit("impulse_midpoint_fail_fade", SignalSide.SHORT)
    tight = factory(base).generate_signals(candles)
    loose = factory(replace(base, extreme_frac=0.35)).generate_signals(candles)
    frac = float(tight["impulse_close_frac"].iloc[fire])
    assert 0.65 <= frac < 0.75
    assert int(tight["signal"].iloc[fire]) == 0
    assert int(loose["signal"].iloc[fire]) == -1


def test_close_on_mid_or_same_side_does_not_fail() -> None:
    from research.validate import strategy_kit

    on_mid, fire = _tape(bullish=True, fail_mode="on_mid")
    held, held_fire = _tape(bullish=True, fail_mode="hold")
    assert int(
        _signals("impulse_midpoint_fail_fade", on_mid, side=SignalSide.SHORT)["signal"].iloc[
            fire
        ]
    ) == 0
    assert int(
        _signals("impulse_midpoint_fail_fade", held, side=SignalSide.SHORT)["signal"].iloc[
            held_fire
        ]
    ) == 0
    # The through-mid lock stays on even if a caller tries to turn it off.
    factory, base, _space = strategy_kit("impulse_midpoint_fail_fade", SignalSide.SHORT)
    forced = factory(replace(base, require_next_close_through_mid=False)).generate_signals(
        on_mid
    )
    assert int(forced["signal"].iloc[fire]) == 0
    happy, happy_fire = _tape(bullish=True, fail_mode="beyond")
    still = factory(replace(base, require_next_close_through_mid=False)).generate_signals(
        happy
    )
    assert int(still["signal"].iloc[happy_fire]) == -1


def test_inside_close_through_mid_still_fades() -> None:
    """Through-mid does not also require a close outside the impulse bar."""
    candles, fire = _tape(bullish=True, fail_mode="inside")
    # A volume spike keeps expansion_fail_fade dark (it demands weak volume).
    # This family has no volume gate.
    candles = candles.copy()
    candles.iloc[fire, candles.columns.get_loc("volume")] = 50_000.0
    candles["turnover"] = candles["volume"] * candles["close"]
    signals = _signals("impulse_midpoint_fail_fade", candles, side=SignalSide.SHORT)
    assert bool(signals["through_down"].iloc[fire])
    assert candles["close"].iloc[fire] > candles["low"].iloc[fire - 1]
    assert candles["close"].iloc[fire] < signals["impulse_mid"].iloc[fire]
    assert int(signals["signal"].iloc[fire]) == -1
    assert int(
        _signals("expansion_fail_fade", candles, side=SignalSide.SHORT)["signal"].iloc[fire]
    ) == 0


def test_atr_known_before_impulse_and_no_lookahead() -> None:
    from core.strategy import indicators as ind

    candles, fire = _tape(bullish=True, fail_mode="beyond")
    signals = _signals("impulse_midpoint_fail_fade", candles, side=SignalSide.SHORT)
    atr20 = ind.atr(candles["high"], candles["low"], candles["close"], ATR_N_LOCKED)
    assert signals["atr_known"].iloc[fire] == pytest.approx(float(atr20.iloc[fire - 2]))
    assert int(signals["signal"].iloc[fire]) == -1

    # Widening the impulse must not change the ATR that sized it.
    fat = candles.copy()
    fat.iloc[fire - 1, fat.columns.get_loc("high")] = float(candles["high"].iloc[fire - 1]) + 3.0
    fat_sig = _signals("impulse_midpoint_fail_fade", fat, side=SignalSide.SHORT)
    assert fat_sig["atr_known"].iloc[fire] == pytest.approx(signals["atr_known"].iloc[fire])

    cut = fire + 1
    truncated = _signals(
        "impulse_midpoint_fail_fade", candles.iloc[:cut], side=SignalSide.SHORT
    )
    pd.testing.assert_series_equal(
        signals["signal"].iloc[:cut],
        truncated["signal"],
        check_names=False,
    )
    shocked = candles.copy()
    later = fire + 3
    shocked.iloc[later, shocked.columns.get_loc("high")] = 140.0
    shocked.iloc[later, shocked.columns.get_loc("low")] = 60.0
    shocked.iloc[later, shocked.columns.get_loc("close")] = 60.0
    after = _signals("impulse_midpoint_fail_fade", shocked, side=SignalSide.SHORT)
    assert int(after["signal"].iloc[fire]) == -1
    assert after["atr_known"].iloc[fire] == pytest.approx(signals["atr_known"].iloc[fire])
    pd.testing.assert_series_equal(
        signals["signal"].iloc[:later],
        after["signal"].iloc[:later],
        check_names=False,
    )


def test_atr_period_lock_ignores_caller_override() -> None:
    from core.strategy import indicators as ind
    from research.validate import strategy_kit

    candles, fire = _tape(bullish=True, fail_mode="beyond")
    factory, base, _space = strategy_kit("impulse_midpoint_fail_fade", SignalSide.SHORT)
    signals = factory(replace(base, atr_n=7)).generate_signals(candles)
    atr20 = ind.atr(candles["high"], candles["low"], candles["close"], 20)
    atr7 = ind.atr(candles["high"], candles["low"], candles["close"], 7)
    assert signals["atr"].iloc[fire] == pytest.approx(float(atr20.iloc[fire]))
    assert signals["atr"].iloc[fire] != pytest.approx(float(atr7.iloc[fire]))


def test_independent_of_thrust_expansion_reject_and_outside() -> None:
    """This entry is not Job 151 and not the other stamped siblings."""
    from tests.test_novel_sleeves import _thrust_bar_fail_reversion_tape

    candles, fire = _tape(bullish=True, fail_mode="beyond")
    assert int(
        _signals("impulse_midpoint_fail_fade", candles, side=SignalSide.SHORT)["signal"].iloc[
            fire
        ]
    ) == -1
    for sibling in (
        "thrust_bar_fail_reversion",
        "expansion_fail_fade",
        "candle_reject_reversal",
        "key_reversal_bar",
        "outside_bar_fail_reversion",
        "three_push_exhaustion_fail",
    ):
        assert int(_signals(sibling, candles, side=SignalSide.SHORT)["signal"].iloc[fire]) == 0, (
            sibling
        )

    # Job 151 fires on its own same-bar thrust. That bar is not this family:
    # the prior bar is not an extreme-close impulse.
    thrust, thrust_fire = _thrust_bar_fail_reversion_tape(long_side=False)
    assert int(
        _signals("thrust_bar_fail_reversion", thrust, side=SignalSide.SHORT)["signal"].iloc[
            thrust_fire
        ]
    ) == -1
    assert int(
        _signals("impulse_midpoint_fail_fade", thrust, side=SignalSide.SHORT)["signal"].iloc[
            thrust_fire
        ]
    ) == 0

    # A wide bar that closes in the middle is not an impulse, even if the
    # next close goes through its midpoint.
    mid_close, mid_fire = _tape(bullish=True, close_frac=0.50, fail_mode="beyond")
    mid_sig = _signals("impulse_midpoint_fail_fade", mid_close, side=SignalSide.SHORT)
    assert not bool(mid_sig["bullish_impulse"].iloc[mid_fire])
    assert not bool(mid_sig["bearish_impulse"].iloc[mid_fire])
    assert int(mid_sig["signal"].iloc[mid_fire]) == 0


def test_catalog_is_option_b_and_not_an_approval() -> None:
    from firm.research_catalog import RESEARCH_HYPOTHESES
    from firm.sleeve_factory import spec_for_family

    row = next(
        r
        for r in RESEARCH_HYPOTHESES
        if r["family"] == "impulse_midpoint_fail_fade"
    )
    assert row["id"] == "impulse_midpoint_fail_fade@4h/4h"
    assert row["clock"] == "4h/4h"
    assert row["side"] == "BOTH"
    assert row["coded"] is True
    assert row["free_params"] == 2
    text = row["justification"].lower()
    assert "do not set approved=true" in text
    assert "live stays off" in text
    assert "walk-forward is not started" in text
    spec = spec_for_family("impulse_midpoint_fail_fade")
    assert spec is not None
    assert spec.clock == "4h/4h"
    assert spec.side == "BOTH"
    assert spec.auto_code is False
