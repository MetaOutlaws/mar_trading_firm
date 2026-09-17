"""
Paper replay surface for the F04 golden tape.

Live paper is a sampled mark against mainnet. That cannot reproduce an OHLC
path, so comparison runs drive ``PaperBroker`` through this replay instead:
the same next-bar-open fills, fill-based TP/SL, path-aware exits, timeout and
CostModel legs ``BacktestEngine`` uses.

The broker is the real paper broker (cash, fees, funding, one-position-per-
symbol). The tape is the clock and the quote. If research and this path
disagree on a fixture, the execution contract has drifted.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from core.execution.broker import Instrument
from core.execution.contract import (
    exit_fill_price,
    fill_in_tradable_window,
    find_exit_on_path,
    risk_levels,
    tape_trade_dict,
)
from core.execution.paper import PaperBroker
from core.strategy.base import SignalSide, Strategy
from research.engine import BacktestConfig, BacktestResult, Trade


class TapeFeed:
    """Deterministic last-price source. Replay points it at the active quote."""

    def __init__(self) -> None:
        self.prices: dict[str, float] = {}

    def latest_price(self, symbol: str) -> float | None:
        return self.prices.get(symbol)

    def set(self, symbol: str, price: float) -> None:
        self.prices[symbol] = float(price)

    def close(self) -> None:
        return None


#: Unrounded instrument so replay quantity matches research sizing.
#: Live paper still infers Bybit-like steps from price magnitude.
def _contract_instrument(symbol: str) -> Instrument:
    return Instrument(
        symbol=symbol,
        tick_size=0.0,
        qty_step=0.0,
        min_qty=0.0,
        min_notional=0.0,
    )


@dataclass
class _Clock:
    """Mutable broker clock so funding windows match bar timestamps."""

    now: datetime

    def __call__(self) -> datetime:
        return self.now


def run_paper_replay(
    symbol: str,
    candles: pd.DataFrame,
    strategy: Strategy,
    config: BacktestConfig | None = None,
    funding: object | None = None,
    *,
    tradable_start: datetime | None = None,
    tradable_end: datetime | None = None,
) -> BacktestResult:
    """Replay ``candles`` through PaperBroker under the F04 contract.

    Returns a ``BacktestResult`` so tests can compare field-for-field with
    ``BacktestEngine.run`` on the same inputs.
    """
    config = config or BacktestConfig()
    if candles.empty:
        return BacktestResult(
            symbol=symbol,
            strategy=strategy.name,
            side=getattr(getattr(strategy, "params", None), "side", SignalSide.FLAT).value
            if hasattr(getattr(strategy, "params", None), "side")
            else "BOTH",
            start=None,
            end=None,
            initial_capital=config.initial_capital,
            final_equity=config.initial_capital,
        )

    costs = config.costs
    feed = TapeFeed()
    broker = PaperBroker(
        starting_equity=config.initial_capital,
        costs=costs,
        data_source=feed,
        lock_cost_model=True,
    )
    broker._instruments[symbol] = _contract_instrument(symbol)
    clock = _Clock(datetime.now(timezone.utc))
    broker._now = clock  # type: ignore[method-assign]

    if funding is not None:
        broker.set_funding_history(symbol, funding)  # type: ignore[arg-type]

    signals = strategy.generate_signals(candles)
    signal_count = int((signals["signal"] != 0).sum())

    params = strategy.params
    take_profit_pct = params.take_profit_pct
    stop_loss_pct = params.stop_loss_pct
    max_holding = params.max_holding_bars

    opens = candles["open"].to_numpy(dtype="float64")
    highs = candles["high"].to_numpy(dtype="float64")
    lows = candles["low"].to_numpy(dtype="float64")
    closes = candles["close"].to_numpy(dtype="float64")
    timestamps = candles.index
    signal_values = signals["signal"].to_numpy(dtype="int64")
    scores = signals["score"].to_numpy(dtype="float64")
    reasons = signals["reason"].to_numpy(dtype=object)

    trades: list[Trade] = []
    equity = config.initial_capital
    equity_stamps: list[pd.Timestamp] = [timestamps[0]]
    equity_values: list[float] = [equity]

    bar = 0
    total_bars = len(candles)

    while bar < total_bars - 1:
        if signal_values[bar] == 0:
            bar += 1
            continue

        side = SignalSide.LONG if signal_values[bar] > 0 else SignalSide.SHORT
        entry_bar = bar + 1
        fill_time = timestamps[entry_bar]
        if not fill_in_tradable_window(fill_time, tradable_start, tradable_end):
            if tradable_end is not None and pd.Timestamp(fill_time) >= pd.Timestamp(
                tradable_end
            ):
                break
            bar += 1
            continue

        entry_quote = float(opens[entry_bar])
        if not np.isfinite(entry_quote) or entry_quote <= 0:
            bar += 1
            continue

        entry_price = costs.entry_price(entry_quote, side.value)
        sizing_base = equity if config.compound else config.initial_capital
        notional = sizing_base * config.position_fraction
        if notional <= 0:
            break
        quantity = notional / entry_price

        clock.now = _as_utc(fill_time)
        feed.set(symbol, entry_quote)
        opened = broker.place_market_order(
            symbol, side.value, quantity, expected_price=entry_quote
        )
        if not opened.success:
            # Cash/notional refusal is a paper-only constraint; treat as no fill
            # so a drift here fails the tape rather than inventing a research fill.
            break

        take_profit, stop_loss = risk_levels(
            opened.fill_price, side, take_profit_pct, stop_loss_pct
        )
        broker.set_stops(symbol, take_profit, stop_loss)

        exit_bar, exit_quote, reason = find_exit_on_path(
            entry_bar=entry_bar,
            total_bars=total_bars,
            side=side,
            opens=opens,
            highs=highs,
            lows=lows,
            closes=closes,
            take_profit=take_profit,
            stop_loss=stop_loss,
            max_holding=max_holding,
            pessimistic_intrabar=config.pessimistic_intrabar,
        )
        exit_price = exit_fill_price(costs, exit_quote, side, reason)
        exit_time = _as_utc(timestamps[exit_bar])
        clock.now = exit_time
        closed = broker.close_at_fill(symbol, exit_price, expected_price=exit_quote)
        if not closed.success:
            break

        entry_time = _as_utc(fill_time)
        qty = closed.filled_quantity or opened.filled_quantity
        fees = (opened.fee or 0.0) + (closed.fee or 0.0)
        funding_cost = float(closed.funding or 0.0)
        if side is SignalSide.LONG:
            gross = (closed.fill_price - opened.fill_price) * qty
        else:
            gross = (opened.fill_price - closed.fill_price) * qty
        net = gross - fees - funding_cost
        equity = broker.cash

        trades.append(
            Trade(
                symbol=symbol,
                side=side,
                entry_time=entry_time,
                entry_price=opened.fill_price,
                exit_time=exit_time,
                exit_price=closed.fill_price,
                quantity=qty,
                notional=opened.fill_price * qty,
                gross_pnl=gross,
                fees=fees,
                funding=funding_cost,
                net_pnl=net,
                return_pct=(net / (opened.fill_price * qty) * 100.0)
                if opened.fill_price * qty
                else 0.0,
                exit_reason=reason,
                bars_held=exit_bar - entry_bar,
                entry_score=float(scores[bar]),
                entry_reason=str(reasons[bar]),
                equity_after=equity,
            )
        )
        equity_stamps.append(timestamps[exit_bar])
        equity_values.append(equity)

        if equity <= config.initial_capital * 0.05:
            break
        bar = exit_bar + 1

    equity_curve = pd.Series(equity_values, index=pd.DatetimeIndex(equity_stamps))
    return BacktestResult(
        symbol=symbol,
        strategy=strategy.name,
        side=getattr(strategy.params, "side", SignalSide.FLAT).value
        if hasattr(strategy.params, "side")
        else "BOTH",
        start=timestamps[0].to_pydatetime(),
        end=timestamps[-1].to_pydatetime(),
        initial_capital=config.initial_capital,
        final_equity=equity,
        trades=trades,
        equity_curve=equity_curve,
        signals_generated=signal_count,
    )


def result_tape_rows(result: BacktestResult) -> list[dict[str, object]]:
    """Normalise a result onto the golden-tape trade schema."""
    rows = []
    for trade in result.trades:
        rows.append(
            tape_trade_dict(
                symbol=trade.symbol,
                side=trade.side,
                entry_time=trade.entry_time,
                entry_price=trade.entry_price,
                exit_time=trade.exit_time,
                exit_price=trade.exit_price,
                quantity=trade.quantity,
                notional=trade.notional,
                gross_pnl=trade.gross_pnl,
                fees=trade.fees,
                funding=trade.funding,
                net_pnl=trade.net_pnl,
                exit_reason=trade.exit_reason,
                bars_held=trade.bars_held,
            )
        )
    return rows


def _as_utc(value: datetime | pd.Timestamp) -> datetime:
    dt = value.to_pydatetime() if hasattr(value, "to_pydatetime") else value
    if not isinstance(dt, datetime):
        raise TypeError(f"expected datetime, got {type(value)!r}")
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
