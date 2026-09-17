"""
F01: walk-forward OOS warmup must not contaminate the OOS ledger.

The reviewed defect (docs/MAR_Trading_Firm_Review_2026-09-12.md):
`_slice_with_warmup` prepends history, `walk_forward` handed that whole frame
to `BacktestEngine.run()`, and strategy `min_bars` was treated as the trade
start. ATR's min_bars is 54 and doji's is 12 against a 300-bar prefix, so
fills landed before fold.test_start.

These tests reconstruct that ungated path (they must observe pre-test fills)
and assert the gated walk-forward path never records them.
"""

from __future__ import annotations

from datetime import timedelta

import pandas as pd
import pytest

from core.strategy.atr_channel_breakout import AtrChannelBreakoutStrategy, AtrChannelParams
from core.strategy.base import SignalSide, Strategy, StrategyParams
from research.costs import FRICTIONLESS
from research.engine import BacktestConfig, BacktestEngine, fill_in_tradable_window
from research.walkforward import (
    RESEARCH_VERSION,
    _slice_with_warmup,
    assert_oos_ledger_invariants,
    walk_forward,
)


class ScriptedStrategy(Strategy):
    """Signal at chosen bar positions. min_bars=0 so warmup is fully tradable."""

    name = "scripted"
    min_bars = 0

    def __init__(
        self,
        entries: dict[int, int] | None = None,
        params: StrategyParams | None = None,
        *,
        every_bar: int = 0,
    ) -> None:
        super().__init__(params or StrategyParams(max_holding_bars=1))
        self.entries = entries or {}
        self.every_bar = every_bar

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        signals = self.empty_signals(candles)
        loc = signals.columns.get_loc("signal")
        side_loc = signals.columns.get_loc("side")
        score_loc = signals.columns.get_loc("score")
        reason_loc = signals.columns.get_loc("reason")
        if self.every_bar:
            signals.iloc[:, loc] = self.every_bar
            signals.iloc[:, side_loc] = (
                SignalSide.LONG.value if self.every_bar > 0 else SignalSide.SHORT.value
            )
            signals.iloc[:, score_loc] = 1.0
            signals.iloc[:, reason_loc] = "scripted"
        for position, direction in self.entries.items():
            if 0 <= position < len(signals):
                signals.iloc[position, loc] = direction
                signals.iloc[position, side_loc] = (
                    SignalSide.LONG.value if direction > 0 else SignalSide.SHORT.value
                )
                signals.iloc[position, score_loc] = 1.0
                signals.iloc[position, reason_loc] = "scripted"
        return signals


class TimestampScriptedStrategy(Strategy):
    """Signal on named timestamps so tests can target the last warmup bar."""

    name = "scripted_ts"
    min_bars = 0

    def __init__(self, signal_times: set[pd.Timestamp], params: StrategyParams | None = None) -> None:
        super().__init__(params or StrategyParams(max_holding_bars=1))
        self.signal_times = {pd.Timestamp(t) for t in signal_times}

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        signals = self.empty_signals(candles)
        loc = signals.columns.get_loc("signal")
        side_loc = signals.columns.get_loc("side")
        score_loc = signals.columns.get_loc("score")
        reason_loc = signals.columns.get_loc("reason")
        for ts in candles.index:
            if pd.Timestamp(ts) in self.signal_times:
                i = candles.index.get_loc(ts)
                signals.iloc[i, loc] = 1
                signals.iloc[i, side_loc] = SignalSide.LONG.value
                signals.iloc[i, score_loc] = 1.0
                signals.iloc[i, reason_loc] = "scripted"
        return signals


def _hourly_candles(n: int, start: str = "2024-01-01") -> pd.DataFrame:
    index = pd.date_range(start, periods=n, freq="1h", tz="UTC")
    price = 100.0
    rows = []
    for _ in range(n):
        rows.append((price, price + 1.0, price - 1.0, price, 1_000.0, 100_000.0))
        price += 0.01
    frame = pd.DataFrame(
        rows,
        columns=["open", "high", "low", "close", "volume", "turnover"],
        index=index,
    )
    frame.index.name = "timestamp"
    return frame


def _downtrend_hourly(n: int, start: str = "2024-01-01") -> pd.DataFrame:
    """A persistent downtrend so ATR-channel shorts fire after min_bars."""
    index = pd.date_range(start, periods=n, freq="1h", tz="UTC")
    close = 10_000.0
    opens, highs, lows, closes, volumes = [], [], [], [], []
    for _ in range(n):
        nxt = close * 0.998  # ~0.2% down each hour
        opens.append(close)
        highs.append(close * 1.0005)
        lows.append(nxt * 0.999)
        closes.append(nxt)
        volumes.append(5_000.0)
        close = nxt
    frame = pd.DataFrame(
        {
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes,
            "turnover": [o * v for o, v in zip(opens, volumes)],
        },
        index=index,
    )
    frame.index.name = "timestamp"
    return frame


def _frictionless() -> BacktestConfig:
    return BacktestConfig(
        initial_capital=10_000.0,
        position_fraction=0.10,
        compound=False,
        costs=FRICTIONLESS,
    )


def _legacy_closed_slice(candles: pd.DataFrame, start, end, warmup_bars: int) -> pd.DataFrame:
    """Pre-F01 slice: closed interval, includes a bar whose timestamp equals `end`."""
    start_index = candles.index.searchsorted(pd.Timestamp(start))
    end_index = candles.index.searchsorted(pd.Timestamp(end), side="right")
    return candles.iloc[max(0, start_index - warmup_bars) : end_index]


def _run_walk(
    candles: pd.DataFrame,
    factory,
    params: StrategyParams,
    *,
    train_days: int = 8,
    test_days: int = 4,
    warmup_bars: int = 24,
):
    return walk_forward(
        symbol="TEST",
        candles=candles,
        strategy_factory=factory,
        base_params=params,
        search_space={},
        config=_frictionless(),
        train_days=train_days,
        test_days=test_days,
        warmup_bars=warmup_bars,
    )


# ---------------------------------------------------------------------------
# Research version
# ---------------------------------------------------------------------------
def test_research_version_is_a_stable_f01_key() -> None:
    assert RESEARCH_VERSION == "wf-f01-oos-window-v1"
    from research import RESEARCH_VERSION as exported

    assert exported == RESEARCH_VERSION


def test_walk_forward_stamps_research_version_on_the_result() -> None:
    candles = _hourly_candles(20 * 24)
    params = StrategyParams(max_holding_bars=1)
    wf = _run_walk(candles, lambda p: ScriptedStrategy(every_bar=1, params=p), params)
    assert wf.research_version == RESEARCH_VERSION
    assert wf.summary()["research_version"] == RESEARCH_VERSION


# ---------------------------------------------------------------------------
# Half-open slicing
# ---------------------------------------------------------------------------
def test_slice_with_warmup_is_half_open_and_keeps_prefix() -> None:
    candles = _hourly_candles(10)
    start = candles.index[4].to_pydatetime()
    end = candles.index[8].to_pydatetime()
    warmed = _slice_with_warmup(candles, start, end, warmup_bars=2)

    assert warmed.index[0] == candles.index[2]  # two warmup bars
    assert warmed.index[2] == candles.index[4]  # start inclusive
    assert candles.index[8] not in warmed.index  # end exclusive
    assert warmed.index[-1] == candles.index[7]


def test_legacy_closed_slice_includes_the_end_bar_that_half_open_drops() -> None:
    """The inclusive-endpoint bug: a bar at `end` sat in two adjacent folds."""
    candles = _hourly_candles(10)
    start = candles.index[4].to_pydatetime()
    end = candles.index[8].to_pydatetime()
    legacy = _legacy_closed_slice(candles, start, end, warmup_bars=0)
    current = _slice_with_warmup(candles, start, end, warmup_bars=0)
    assert candles.index[8] in legacy.index
    assert candles.index[8] not in current.index


# ---------------------------------------------------------------------------
# Engine tradable window
# ---------------------------------------------------------------------------
def test_engine_skips_pre_window_fills_and_takes_the_first_in_window_entry() -> None:
    """Gating at fill time, not post-filtering the ledger.

    A warmup fill that stays open would occupy the book and hide the real OOS
    entry. Dropping it after the fact would also drop that later fill. The
    engine must refuse the pre-test fill so the in-window signal can trade.
    """
    candles = _hourly_candles(40)
    tradable_start = candles.index[10].to_pydatetime()
    tradable_end = candles.index[30].to_pydatetime()
    params = StrategyParams(
        take_profit_pct=0.50, stop_loss_pct=0.50, max_holding_bars=20
    )
    # Signal on bar 0 → fill bar 1 (before window). Signal on bar 10 → fill 11.
    strategy = ScriptedStrategy({0: 1, 10: 1}, params)

    ungated = BacktestEngine(_frictionless()).run("TEST", candles, strategy)
    assert ungated.total_trades == 1
    assert ungated.trades[0].entry_time == candles.index[1].to_pydatetime()

    gated = BacktestEngine(_frictionless()).run(
        "TEST",
        candles,
        strategy,
        tradable_start=tradable_start,
        tradable_end=tradable_end,
    )
    assert gated.total_trades == 1
    assert gated.trades[0].entry_time == candles.index[11].to_pydatetime()
    assert fill_in_tradable_window(
        gated.trades[0].entry_time, tradable_start, tradable_end
    )


def test_engine_rejects_a_fill_at_the_exclusive_end() -> None:
    candles = _hourly_candles(6)
    # Signal on bar 3 → fill bar 4, whose timestamp is tradable_end.
    strategy = ScriptedStrategy({3: 1}, StrategyParams(max_holding_bars=1))
    result = BacktestEngine(_frictionless()).run(
        "TEST",
        candles,
        strategy,
        tradable_start=candles.index[1].to_pydatetime(),
        tradable_end=candles.index[4].to_pydatetime(),
    )
    assert result.total_trades == 0


# ---------------------------------------------------------------------------
# Walk-forward OOS ledger
# ---------------------------------------------------------------------------
def test_ungated_warmed_slice_reproduces_f01_pre_test_fills() -> None:
    """Without a tradable window the warmed OOS slice *does* leak pre-test fills.

    This is the regression that would have failed on the old walk_forward: it
    asserts contamination exists on the ungated path, then that gated
    walk-forward records none of those fills.
    """
    warmup_bars = 24
    train_days, test_days = 8, 4
    candles = _hourly_candles(20 * 24)
    params = StrategyParams(max_holding_bars=1)

    def factory(p):
        return ScriptedStrategy(every_bar=1, params=p)

    history_start = candles.index[0].to_pydatetime()
    test_start = history_start + timedelta(days=train_days)
    test_end = test_start + timedelta(days=test_days)

    legacy_slice = _legacy_closed_slice(candles, test_start, test_end, warmup_bars)
    ungated = BacktestEngine(_frictionless()).run("TEST", legacy_slice, factory(params))
    pretest = [
        t
        for t in ungated.trades
        if pd.Timestamp(t.entry_time) < pd.Timestamp(test_start)
    ]
    assert pretest, "fixture must reproduce F01 warmup contamination"
    assert pd.Timestamp(ungated.trades[0].entry_time) < pd.Timestamp(test_start)

    wf = _run_walk(
        candles, factory, params, train_days=train_days, test_days=test_days, warmup_bars=warmup_bars
    )
    assert wf.folds, "need at least one fold"
    oos = wf.oos_trades
    assert oos, "always-long script should trade in-window"
    for fold in wf.folds:
        if fold.test_result is None:
            continue
        for trade in fold.test_result.trades:
            assert fold.entry_in_oos_window(trade.entry_time), (
                f"fold {fold.index} pre-test or past-end fill "
                f"{trade.entry_time} vs {fold.summary()['oos_entry_window']}"
            )
            assert pd.Timestamp(trade.entry_time) >= pd.Timestamp(fold.test_start)
            assert pd.Timestamp(trade.entry_time) < pd.Timestamp(fold.test_end)


def test_all_oos_trades_fall_inside_declared_half_open_windows() -> None:
    candles = _hourly_candles(24 * 24)
    params = StrategyParams(max_holding_bars=2)
    wf = _run_walk(
        candles,
        lambda p: ScriptedStrategy(every_bar=1, params=p),
        params,
        train_days=6,
        test_days=3,
        warmup_bars=12,
    )
    assert_oos_ledger_invariants(wf)
    assert wf.total_oos_trades > 0
    windows = [f.summary()["oos_entry_window"] for f in wf.folds]
    assert all(w.startswith("[") and w.endswith(")") for w in windows)

    # Adjacent folds must not share an entry timestamp (half-open tiling).
    by_time = [pd.Timestamp(t.entry_time) for t in wf.oos_trades]
    assert len(by_time) == len(set(by_time))


def test_last_warmup_bar_signal_may_fill_at_test_start() -> None:
    """Eligible signal times include the last warmup bar; eligible fills start at test_start."""
    warmup_bars = 24
    train_days, test_days = 8, 4
    candles = _hourly_candles(16 * 24 + 12)
    history_start = candles.index[0].to_pydatetime()
    test_start = history_start + timedelta(days=train_days)
    # Last warmup bar is the hour before test_start.
    signal_ts = pd.Timestamp(test_start) - pd.Timedelta(hours=1)
    params = StrategyParams(max_holding_bars=1)

    def factory(p):
        return TimestampScriptedStrategy({signal_ts}, p)

    wf = _run_walk(
        candles, factory, params, train_days=train_days, test_days=test_days, warmup_bars=warmup_bars
    )
    fold = wf.folds[0]
    assert fold.test_result is not None
    assert fold.test_result.total_trades == 1
    assert fold.test_result.trades[0].entry_time == pd.Timestamp(test_start).to_pydatetime()
    assert fold.entry_in_oos_window(fold.test_result.trades[0].entry_time)


def test_train_fills_are_also_gated_to_the_half_open_train_window() -> None:
    candles = _hourly_candles(20 * 24)
    params = StrategyParams(max_holding_bars=1)
    wf = _run_walk(
        candles,
        lambda p: ScriptedStrategy(every_bar=1, params=p),
        params,
        train_days=8,
        test_days=4,
        warmup_bars=24,
    )
    for fold in wf.folds:
        if fold.train_result is None:
            continue
        for trade in fold.train_result.trades:
            assert fill_in_tradable_window(trade.entry_time, fold.train_start, fold.train_end), (
                f"fold {fold.index} train fill {trade.entry_time} outside "
                f"[{fold.train_start}, {fold.train_end})"
            )


def test_grid_search_path_still_gates_oos_fills() -> None:
    """F01 applies when folds optimise, not only the empty-grid evaluate path."""
    candles = _hourly_candles(20 * 24)
    params = StrategyParams(max_holding_bars=1, take_profit_pct=0.50, stop_loss_pct=0.50)

    def factory(p):
        return ScriptedStrategy(every_bar=1, params=p)

    wf = walk_forward(
        symbol="TEST",
        candles=candles,
        strategy_factory=factory,
        base_params=params,
        search_space={"take_profit_pct": [0.50]},
        config=_frictionless(),
        train_days=8,
        test_days=4,
        warmup_bars=24,
    )
    assert wf.folds
    assert_oos_ledger_invariants(wf)
    assert wf.oos_trades


def test_atr_channel_warmup_contamination_is_gated() -> None:
    """Same family the review used: min_bars=54 vs a longer walk-forward prefix."""
    warmup_bars = 80
    train_days, test_days = 10, 5
    # ~40 days hourly so several folds exist after 10+5.
    candles = _downtrend_hourly(45 * 24)
    params = AtrChannelParams(
        side=SignalSide.SHORT,
        min_adx=0.0,
        take_profit_pct=0.04,
        stop_loss_pct=0.02,
        max_holding_bars=8,
    )
    strategy = AtrChannelBreakoutStrategy(params)
    assert strategy.min_bars == 54
    assert warmup_bars > strategy.min_bars

    history_start = candles.index[0].to_pydatetime()
    test_start = history_start + timedelta(days=train_days)
    test_end = test_start + timedelta(days=test_days)
    legacy_slice = _legacy_closed_slice(candles, test_start, test_end, warmup_bars)
    ungated = BacktestEngine(_frictionless()).run("TEST", legacy_slice, strategy)
    pretest = [
        t
        for t in ungated.trades
        if pd.Timestamp(t.entry_time) < pd.Timestamp(test_start)
    ]
    # The downtrend fixture is built so ATR shorts fire during the prefix.
    assert pretest, (
        "ATR fixture must reproduce the review's pre-test fills; "
        "otherwise this is not a regression for F01"
    )

    wf = _run_walk(
        candles,
        lambda p: AtrChannelBreakoutStrategy(p),
        params,
        train_days=train_days,
        test_days=test_days,
        warmup_bars=warmup_bars,
    )
    assert_oos_ledger_invariants(wf)
    for trade in wf.oos_trades:
        owning = [f for f in wf.folds if f.test_result and trade in f.test_result.trades]
        assert owning
        assert owning[0].entry_in_oos_window(trade.entry_time)


def test_invariants_raise_on_a_pre_test_fill() -> None:
    from research.engine import ExitReason, Trade
    from research.walkforward import Fold, WalkForwardResult

    start = pd.Timestamp("2024-02-01", tz="UTC").to_pydatetime()
    end = pd.Timestamp("2024-03-01", tz="UTC").to_pydatetime()
    bogus = Trade(
        symbol="TEST",
        side=SignalSide.LONG,
        entry_time=(pd.Timestamp(start) - pd.Timedelta(days=2)).to_pydatetime(),
        entry_price=100.0,
        exit_time=start,
        exit_price=101.0,
        quantity=1.0,
        notional=100.0,
        gross_pnl=1.0,
        fees=0.0,
        funding=0.0,
        net_pnl=1.0,
        return_pct=1.0,
        exit_reason=ExitReason.TIMEOUT,
        bars_held=1,
        entry_score=1.0,
        entry_reason="bogus",
        equity_after=10_001.0,
    )
    fold = Fold(index=0, train_start=start, train_end=start, test_start=start, test_end=end)
    fold.test_result = type("R", (), {"trades": [bogus], "total_trades": 1})()
    result = WalkForwardResult(symbol="TEST", strategy="x", side="LONG", folds=[fold])
    with pytest.raises(RuntimeError, match="OOS window violation"):
        assert_oos_ledger_invariants(result)
