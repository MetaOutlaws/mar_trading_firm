"""
Backtest engine tests.

These verify the assumptions that decide whether a backtest is honest:
next-bar-open fills, pessimistic intrabar resolution, gap handling, and full
cost charging. A bug in any of them would silently manufacture profit.

Scenarios are hand-built with exact prices so expected P&L is computed by hand
rather than by re-running the code under test.
"""

from __future__ import annotations

import pandas as pd
import pytest

from core.strategy.base import SignalSide, Strategy, StrategyParams
from research.costs import FRICTIONLESS, CostModel
from research.engine import BacktestConfig, BacktestEngine, ExitReason


class ScriptedStrategy(Strategy):
    """Emits signals at predetermined bar positions.

    Lets the engine be tested in isolation from signal generation, so a failure
    here is unambiguously an execution-modelling bug.
    """

    name = "scripted"
    min_bars = 0

    def __init__(self, entries: dict[int, int], params: StrategyParams | None = None) -> None:
        super().__init__(params or StrategyParams())
        self.entries = entries

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        signals = self.empty_signals(candles)
        for position, direction in self.entries.items():
            if position < len(signals):
                signals.iloc[position, signals.columns.get_loc("signal")] = direction
                signals.iloc[position, signals.columns.get_loc("side")] = (
                    SignalSide.LONG.value if direction > 0 else SignalSide.SHORT.value
                )
                signals.iloc[position, signals.columns.get_loc("score")] = 1.0
                signals.iloc[position, signals.columns.get_loc("reason")] = "scripted"
        return signals


def build_candles(bars: list[tuple[float, float, float, float]]) -> pd.DataFrame:
    """Build candles from a list of (open, high, low, close) tuples."""
    index = pd.date_range("2024-01-01", periods=len(bars), freq="1h", tz="UTC")
    frame = pd.DataFrame(
        {
            "open": [b[0] for b in bars],
            "high": [b[1] for b in bars],
            "low": [b[2] for b in bars],
            "close": [b[3] for b in bars],
            "volume": [1000.0] * len(bars),
            "turnover": [100_000.0] * len(bars),
        },
        index=index,
    )
    frame.index.name = "timestamp"
    return frame


def frictionless_config(**overrides) -> BacktestConfig:
    """Zero-cost config so price mechanics can be checked without cost noise."""
    defaults = dict(
        initial_capital=10_000.0,
        position_fraction=1.0,  # whole account, so P&L maths is transparent
        compound=False,
        costs=FRICTIONLESS,
    )
    defaults.update(overrides)
    return BacktestConfig(**defaults)


# ---------------------------------------------------------------------------
# Entry timing
# ---------------------------------------------------------------------------
def test_entry_fills_at_next_bar_open_not_signal_bar_close():
    """The defining anti-lookahead property of the engine.

    Signal at bar 0 (close 100). Bar 1 opens at 110. The fill must be 110.
    Filling at 100 would be trading on a price known only in hindsight.
    """
    candles = build_candles(
        [
            (100, 101, 99, 100),  # bar 0: signal here
            (110, 111, 109, 110),  # bar 1: entry fills at this open
            (110, 111, 109, 110),
        ]
    )
    strategy = ScriptedStrategy({0: 1}, StrategyParams(max_holding_bars=1))
    result = BacktestEngine(frictionless_config()).run("TEST", candles, strategy)

    assert result.total_trades == 1
    assert result.trades[0].entry_price == pytest.approx(110.0)
    assert result.trades[0].entry_time == candles.index[1].to_pydatetime()


def test_signal_on_final_bar_is_never_traded():
    """With no following bar there is no fill price, so the signal is dropped."""
    candles = build_candles([(100, 101, 99, 100)] * 3)
    strategy = ScriptedStrategy({2: 1})
    result = BacktestEngine(frictionless_config()).run("TEST", candles, strategy)
    assert result.total_trades == 0


# ---------------------------------------------------------------------------
# Exit resolution
# ---------------------------------------------------------------------------
def test_long_take_profit_exit():
    """Entry 100, +5% target = 105. Bar 2 trades up to 106, so TP fills at 105."""
    candles = build_candles(
        [
            (100, 100, 100, 100),
            (100, 100, 100, 100),  # entry at open 100
            (100, 106, 99, 105),  # high 106 crosses the 105 target
        ]
    )
    params = StrategyParams(take_profit_pct=0.05, stop_loss_pct=0.05, max_holding_bars=10)
    result = BacktestEngine(frictionless_config()).run(
        "TEST", candles, ScriptedStrategy({0: 1}, params)
    )

    trade = result.trades[0]
    assert trade.exit_reason is ExitReason.TAKE_PROFIT
    assert trade.exit_price == pytest.approx(105.0)
    assert trade.net_pnl == pytest.approx(500.0)  # 5% of 10,000


def test_long_stop_loss_exit():
    """Entry 100, -5% stop = 95. Bar 2 trades down to 94, so the stop fills at 95."""
    candles = build_candles(
        [
            (100, 100, 100, 100),
            (100, 100, 100, 100),
            (100, 101, 94, 96),  # low 94 breaches the 95 stop
        ]
    )
    params = StrategyParams(take_profit_pct=0.05, stop_loss_pct=0.05, max_holding_bars=10)
    result = BacktestEngine(frictionless_config()).run(
        "TEST", candles, ScriptedStrategy({0: 1}, params)
    )

    trade = result.trades[0]
    assert trade.exit_reason is ExitReason.STOP_LOSS
    assert trade.exit_price == pytest.approx(95.0)
    assert trade.net_pnl == pytest.approx(-500.0)


def test_bar_spanning_both_levels_assumes_the_stop():
    """The single most result-distorting assumption in any backtester.

    Bar 2 spans 94 to 106, touching both the 95 stop and the 105 target. OHLC
    data cannot say which came first, so the engine must assume the stop.
    Assuming the target instead would fabricate profit on every volatile bar.
    """
    candles = build_candles(
        [
            (100, 100, 100, 100),
            (100, 100, 100, 100),
            (100, 106, 94, 100),  # spans both levels
        ]
    )
    params = StrategyParams(take_profit_pct=0.05, stop_loss_pct=0.05, max_holding_bars=10)

    pessimistic = BacktestEngine(frictionless_config(pessimistic_intrabar=True)).run(
        "TEST", candles, ScriptedStrategy({0: 1}, params)
    )
    assert pessimistic.trades[0].exit_reason is ExitReason.STOP_LOSS
    assert pessimistic.trades[0].net_pnl < 0

    optimistic = BacktestEngine(frictionless_config(pessimistic_intrabar=False)).run(
        "TEST", candles, ScriptedStrategy({0: 1}, params)
    )
    assert optimistic.trades[0].exit_reason is ExitReason.TAKE_PROFIT
    assert optimistic.trades[0].net_pnl > 0

    # The gap between the two is the size of the illusion being avoided.
    assert optimistic.trades[0].net_pnl > pessimistic.trades[0].net_pnl


def test_gap_through_stop_fills_at_open_not_stop_price():
    """Real stops do not protect against gaps.

    Entry 100, stop 95, but bar 2 opens at 80. The fill is 80, a 20% loss --
    not the 5% the stop nominally promised.
    """
    candles = build_candles(
        [
            (100, 100, 100, 100),
            (100, 100, 100, 100),
            (80, 82, 78, 81),  # gaps far below the stop
        ]
    )
    params = StrategyParams(take_profit_pct=0.05, stop_loss_pct=0.05, max_holding_bars=10)
    result = BacktestEngine(frictionless_config()).run(
        "TEST", candles, ScriptedStrategy({0: 1}, params)
    )

    trade = result.trades[0]
    assert trade.exit_reason is ExitReason.STOP_LOSS
    assert trade.exit_price == pytest.approx(80.0)
    assert trade.return_pct == pytest.approx(-20.0)


def test_timeout_exit_when_neither_level_is_touched():
    """A quiet market exits at the close of the final permitted bar."""
    candles = build_candles([(100, 100.5, 99.5, 100)] * 10)
    params = StrategyParams(take_profit_pct=0.05, stop_loss_pct=0.05, max_holding_bars=3)
    result = BacktestEngine(frictionless_config()).run(
        "TEST", candles, ScriptedStrategy({0: 1}, params)
    )

    trade = result.trades[0]
    assert trade.exit_reason is ExitReason.TIMEOUT
    assert trade.bars_held == 3


def test_short_take_profit_and_stop_are_mirrored():
    """A short profits as price falls and stops out as it rises."""
    params = StrategyParams(take_profit_pct=0.05, stop_loss_pct=0.05, max_holding_bars=10)

    winning = build_candles(
        [(100, 100, 100, 100), (100, 100, 100, 100), (100, 101, 94, 95)]
    )
    result = BacktestEngine(frictionless_config()).run(
        "TEST", winning, ScriptedStrategy({0: -1}, params)
    )
    assert result.trades[0].exit_reason is ExitReason.TAKE_PROFIT
    assert result.trades[0].net_pnl == pytest.approx(500.0)

    losing = build_candles(
        [(100, 100, 100, 100), (100, 100, 100, 100), (100, 106, 99, 105)]
    )
    result = BacktestEngine(frictionless_config()).run(
        "TEST", losing, ScriptedStrategy({0: -1}, params)
    )
    assert result.trades[0].exit_reason is ExitReason.STOP_LOSS
    assert result.trades[0].net_pnl == pytest.approx(-500.0)


# ---------------------------------------------------------------------------
# Costs
# ---------------------------------------------------------------------------
def test_costs_reduce_pnl_versus_frictionless():
    """The same winning trade must be worth less once costs are charged."""
    candles = build_candles(
        [(100, 100, 100, 100), (100, 100, 100, 100), (100, 106, 99, 105)]
    )
    params = StrategyParams(take_profit_pct=0.05, stop_loss_pct=0.05, max_holding_bars=10)
    strategy = ScriptedStrategy({0: 1}, params)

    free = BacktestEngine(frictionless_config()).run("TEST", candles, strategy)
    costed = BacktestEngine(
        frictionless_config(costs=CostModel(slippage=0.001, include_funding=True))
    ).run("TEST", candles, strategy)

    assert costed.trades[0].net_pnl < free.trades[0].net_pnl
    assert costed.total_fees > 0


def test_slippage_worsens_both_legs():
    """A buyer pays above the quote and sells below it."""
    costs = CostModel(taker_fee=0.0, maker_fee=0.0, slippage=0.01, include_funding=False)
    assert costs.entry_price(100.0, "LONG") == pytest.approx(101.0)
    assert costs.exit_price(100.0, "LONG") == pytest.approx(99.0)
    assert costs.entry_price(100.0, "SHORT") == pytest.approx(99.0)
    assert costs.exit_price(100.0, "SHORT") == pytest.approx(101.0)


def test_funding_is_charged_to_longs_and_credited_to_shorts():
    """With a positive funding rate, longs pay and shorts receive."""
    from datetime import datetime, timezone

    costs = CostModel(taker_fee=0.0, maker_fee=0.0, slippage=0.0, include_funding=True)
    entry = datetime(2024, 1, 1, tzinfo=timezone.utc)
    exit_at = datetime(2024, 1, 2, tzinfo=timezone.utc)  # 24h => 3 settlements

    long_cost = costs.funding_cost("LONG", entry, exit_at, 1000.0)
    short_cost = costs.funding_cost("SHORT", entry, exit_at, 1000.0)

    assert long_cost > 0
    assert short_cost == pytest.approx(-long_cost)


def test_win_requires_profit_after_costs():
    """A trade whose gross gain is smaller than its costs is not a win.

    Counting gross winners inflates win rate while the account shrinks -- the
    exact way a strategy can look good and lose money.
    """
    # +0.1% target against ~0.31% round-trip costs: gross positive, net negative.
    candles = build_candles(
        [(100, 100, 100, 100), (100, 100, 100, 100), (100, 100.5, 99.9, 100.2)]
    )
    params = StrategyParams(take_profit_pct=0.001, stop_loss_pct=0.05, max_holding_bars=10)
    result = BacktestEngine(
        frictionless_config(costs=CostModel(slippage=0.001, include_funding=False))
    ).run("TEST", candles, ScriptedStrategy({0: 1}, params))

    trade = result.trades[0]
    assert trade.exit_reason is ExitReason.TAKE_PROFIT
    assert trade.net_pnl < 0
    assert not trade.is_win
    assert result.win_rate == 0.0


# ---------------------------------------------------------------------------
# Bookkeeping
# ---------------------------------------------------------------------------
def test_no_signal_means_no_trades_and_flat_equity():
    candles = build_candles([(100, 101, 99, 100)] * 20)
    result = BacktestEngine(frictionless_config()).run("TEST", candles, ScriptedStrategy({}))
    assert result.total_trades == 0
    assert result.final_equity == pytest.approx(result.initial_capital)
    assert result.win_rate == 0.0
    assert result.max_drawdown_pct == pytest.approx(0.0)


def test_no_pyramiding_while_a_position_is_open():
    """Signals during an open position are ignored; one position at a time."""
    candles = build_candles([(100, 100.2, 99.8, 100)] * 30)
    params = StrategyParams(take_profit_pct=0.05, stop_loss_pct=0.05, max_holding_bars=10)
    # Bars 0, 1 and 2 all signal, but the first trade holds for 10 bars.
    result = BacktestEngine(frictionless_config()).run(
        "TEST", candles, ScriptedStrategy({0: 1, 1: 1, 2: 1}, params)
    )
    assert result.total_trades <= 2
    assert result.trades[0].bars_held == 10


def test_equity_curve_tracks_realised_pnl():
    candles = build_candles(
        [(100, 100, 100, 100), (100, 100, 100, 100), (100, 106, 99, 105)]
    )
    params = StrategyParams(take_profit_pct=0.05, stop_loss_pct=0.05, max_holding_bars=10)
    result = BacktestEngine(frictionless_config()).run(
        "TEST", candles, ScriptedStrategy({0: 1}, params)
    )

    assert result.equity_curve.iloc[0] == pytest.approx(10_000.0)
    assert result.equity_curve.iloc[-1] == pytest.approx(10_500.0)
    assert result.final_equity == pytest.approx(10_500.0)


def test_profit_factor_and_drawdown_are_computed():
    """A mixed win/loss sequence should produce sane aggregate metrics."""
    # Win, then loss, with the position sized small enough to survive both.
    candles = build_candles(
        [
            (100, 100, 100, 100),
            (100, 100, 100, 100),
            (100, 106, 99, 105),  # +5% win
            (100, 100, 100, 100),
            (100, 100, 100, 100),
            (100, 101, 94, 95),  # -5% loss
        ]
    )
    params = StrategyParams(take_profit_pct=0.05, stop_loss_pct=0.05, max_holding_bars=2)
    result = BacktestEngine(
        frictionless_config(position_fraction=0.5, compound=True)
    ).run("TEST", candles, ScriptedStrategy({0: 1, 3: 1}, params))

    assert result.total_trades == 2
    assert len(result.wins) == 1
    assert len(result.losses) == 1
    assert result.win_rate == pytest.approx(50.0)
    assert result.profit_factor > 0
    assert result.max_drawdown_pct > 0


def test_empty_candles_return_an_empty_result():
    from core.data.ohlcv import empty_frame

    result = BacktestEngine(frictionless_config()).run(
        "TEST", empty_frame(), ScriptedStrategy({})
    )
    assert result.total_trades == 0
    assert result.start is None


def test_summary_is_serialisable():
    import json

    candles = build_candles(
        [(100, 100, 100, 100), (100, 100, 100, 100), (100, 106, 99, 105)]
    )
    params = StrategyParams(take_profit_pct=0.05, stop_loss_pct=0.05, max_holding_bars=10)
    result = BacktestEngine(frictionless_config()).run(
        "TEST", candles, ScriptedStrategy({0: 1}, params)
    )

    payload = json.dumps(result.summary())
    assert "win_rate" in payload
    assert json.dumps(result.trades[0].to_dict())
