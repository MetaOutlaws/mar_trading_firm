"""UTC opening-range breakout: schema, no lookahead, at least one entry."""

from __future__ import annotations

import numpy as np
import pandas as pd

from core.strategy.base import SignalSide
from core.strategy.opening_range_breakout import (
    OpeningRangeBreakoutStrategy,
    OpeningRangeParams,
)
from core.strategy.registry import list_strategies


def _frame(*, n: int = 72, break_hour: int = 29) -> pd.DataFrame:
    """1h bars starting at UTC midnight. Hour `break_hour` closes through the range high.

    Default 29 is 05:00 on the second UTC day, after min_bars warmup.
    """
    index = pd.date_range("2024-01-02", periods=n, freq="h", tz="UTC")
    close = np.full(n, 100.0)
    high = np.full(n, 101.0)
    low = np.full(n, 99.0)
    close[break_hour] = 110.0
    high[break_hour] = 111.0
    low[break_hour] = 109.0
    frame = pd.DataFrame(
        {
            "open": np.concatenate([[close[0]], close[:-1]]),
            "high": high,
            "low": low,
            "close": close,
            "volume": np.full(n, 1_000.0),
        },
        index=index,
    )
    frame.index.name = "timestamp"
    return frame


def test_opening_range_is_registered() -> None:
    assert "opening_range_breakout" in list_strategies()


def test_opening_range_schema_and_long_entry() -> None:
    strategy = OpeningRangeBreakoutStrategy(
        OpeningRangeParams(side=SignalSide.LONG, range_hours=1)
    )
    candles = _frame()
    signals = strategy.generate_signals(candles)
    pd.testing.assert_index_equal(signals.index, candles.index)
    for column in ("signal", "side", "score", "reason", "range_high", "range_low"):
        assert column in signals.columns
    assert int(signals["signal"].iloc[0]) == 0
    fired = signals[signals["signal"] == 1]
    assert not fired.empty
    assert int(signals["signal"].iloc[29]) == 1
    # One shot: a later tag the same day does not fire again.
    assert int((signals["signal"] == 1).sum()) == 1


def test_opening_range_short_entry() -> None:
    index = pd.date_range("2024-01-02", periods=72, freq="h", tz="UTC")
    close = np.full(72, 100.0)
    high = np.full(72, 101.0)
    low = np.full(72, 99.0)
    close[29] = 90.0
    high[29] = 91.0
    low[29] = 89.0
    frame = pd.DataFrame(
        {
            "open": np.concatenate([[close[0]], close[:-1]]),
            "high": high,
            "low": low,
            "close": close,
            "volume": np.full(72, 1_000.0),
        },
        index=index,
    )
    frame.index.name = "timestamp"
    strategy = OpeningRangeBreakoutStrategy(
        OpeningRangeParams(side=SignalSide.SHORT, range_hours=1)
    )
    signals = strategy.generate_signals(frame)
    assert int(signals["signal"].iloc[29]) == -1


def test_opening_range_no_lookahead_truncation() -> None:
    strategy = OpeningRangeBreakoutStrategy(
        OpeningRangeParams(side=SignalSide.LONG, range_hours=1)
    )
    candles = _frame(n=80)
    full = strategy.generate_signals(candles)
    cut = 50
    truncated = strategy.generate_signals(candles.iloc[:cut])
    pd.testing.assert_series_equal(
        full["signal"].iloc[:cut],
        truncated["signal"],
        check_names=False,
    )


def test_opening_range_future_shock_does_not_change_past() -> None:
    strategy = OpeningRangeBreakoutStrategy(
        OpeningRangeParams(side=SignalSide.LONG, range_hours=1)
    )
    candles = _frame(n=80)
    shocked = candles.copy()
    shocked.iloc[-1, shocked.columns.get_loc("close")] *= 1.5
    shocked.iloc[-1, shocked.columns.get_loc("high")] *= 1.6
    original = strategy.generate_signals(candles)["signal"].iloc[:-1]
    after = strategy.generate_signals(shocked)["signal"].iloc[:-1]
    pd.testing.assert_series_equal(original, after)


def test_opening_range_live_path_matches_backtest() -> None:
    strategy = OpeningRangeBreakoutStrategy(
        OpeningRangeParams(side=SignalSide.LONG, range_hours=1)
    )
    candles = _frame()
    signals = strategy.generate_signals(candles)
    latest = strategy.latest_signal("BTCUSDT", candles)
    last = signals.iloc[-1]
    if int(last["signal"]) == 0:
        assert latest is None
    else:
        assert latest is not None
        assert latest.side.value == last["side"]


def test_opening_range_kit_is_not_rsi() -> None:
    from research.validate import strategy_kit

    factory, base, space = strategy_kit("opening_range_breakout", SignalSide.LONG)
    sleeve = factory(base)
    assert sleeve.name == "opening_range_breakout"
    assert "range_hours" in space
    assert "rsi_min" not in space
