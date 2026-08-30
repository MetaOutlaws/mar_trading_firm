"""
Event-driven backtest engine.

Design choices that determine whether results are honest:

**Next-bar-open fills.** A signal computed from bar `t`'s close is filled at bar
`t+1`'s open. The legacy engine filled at bar `t`'s close, which assumes you can
trade at a price the instant it is determined. That single assumption inflates
results for any strategy whose signal correlates with short-term reversal --
which is exactly what an RSI pullback strategy is.

**Pessimistic intrabar resolution.** When a bar's range spans both the take
profit and the stop loss, we cannot know from OHLC data which came first. This
engine assumes the *stop* filled. Assuming the target instead manufactures
free profit on every volatile bar; over hundreds of trades that difference alone
can invert a strategy's verdict.

**Stops fill at the stop price, gaps fill worse.** If a bar opens beyond the
stop, the fill is the open, not the stop level. Real stops do not protect
against gaps.

**Full cost charging.** Taker fees both legs, slippage both legs, and funding
for every 8-hour settlement inside the holding period.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

import numpy as np
import pandas as pd

from core.data.funding import FundingHistory
from core.strategy.base import SignalSide, Strategy
from research.costs import DEFAULT_COSTS, CostModel

logger = logging.getLogger(__name__)


class ExitReason(str, Enum):
    """Why a position was closed."""

    TAKE_PROFIT = "take_profit"
    STOP_LOSS = "stop_loss"
    TIMEOUT = "timeout"
    END_OF_DATA = "end_of_data"


@dataclass
class BacktestConfig:
    """Simulation settings."""

    initial_capital: float = 10_000.0

    #: Fraction of equity committed per trade. 0.10 with 5% stops risks ~0.5%
    #: of equity per trade, which is conservative and survivable.
    position_fraction: float = 0.10

    #: Cap on simultaneously open positions in a single-symbol run.
    max_concurrent: int = 1

    #: Compound gains, or size every trade off the starting capital.
    compound: bool = True

    #: When a bar spans both TP and SL, assume the stop filled.
    pessimistic_intrabar: bool = True

    costs: CostModel = field(default_factory=lambda: DEFAULT_COSTS)


@dataclass
class Trade:
    """One completed round trip."""

    symbol: str
    side: SignalSide
    entry_time: datetime
    entry_price: float
    exit_time: datetime
    exit_price: float
    quantity: float
    notional: float
    gross_pnl: float
    fees: float
    funding: float
    net_pnl: float
    return_pct: float
    exit_reason: ExitReason
    bars_held: int
    entry_score: float
    entry_reason: str
    equity_after: float

    @property
    def is_win(self) -> bool:
        """A trade wins only if it is profitable *after* all costs."""
        return self.net_pnl > 0

    def to_dict(self) -> dict[str, object]:
        return {
            "symbol": self.symbol,
            "side": self.side.value,
            "entry_time": self.entry_time.isoformat(),
            "entry_price": round(self.entry_price, 8),
            "exit_time": self.exit_time.isoformat(),
            "exit_price": round(self.exit_price, 8),
            "quantity": round(self.quantity, 8),
            "notional": round(self.notional, 2),
            "gross_pnl": round(self.gross_pnl, 4),
            "fees": round(self.fees, 4),
            "funding": round(self.funding, 4),
            "net_pnl": round(self.net_pnl, 4),
            "return_pct": round(self.return_pct, 4),
            "exit_reason": self.exit_reason.value,
            "bars_held": self.bars_held,
            "entry_score": round(self.entry_score, 3),
            "entry_reason": self.entry_reason,
            "equity_after": round(self.equity_after, 2),
        }


@dataclass
class BacktestResult:
    """Metrics and trade list from one simulation run."""

    symbol: str
    strategy: str
    side: str
    start: datetime | None
    end: datetime | None
    initial_capital: float
    final_equity: float
    trades: list[Trade] = field(default_factory=list)
    equity_curve: pd.Series = field(default_factory=lambda: pd.Series(dtype="float64"))
    signals_generated: int = 0

    # -- headline metrics ---------------------------------------------------
    @property
    def total_trades(self) -> int:
        return len(self.trades)

    @property
    def wins(self) -> list[Trade]:
        return [t for t in self.trades if t.is_win]

    @property
    def losses(self) -> list[Trade]:
        return [t for t in self.trades if not t.is_win]

    @property
    def win_rate(self) -> float:
        """Percentage of trades profitable after costs."""
        if not self.trades:
            return 0.0
        return len(self.wins) / len(self.trades) * 100.0

    @property
    def gross_profit(self) -> float:
        return sum(t.net_pnl for t in self.wins)

    @property
    def gross_loss(self) -> float:
        return abs(sum(t.net_pnl for t in self.losses))

    @property
    def profit_factor(self) -> float:
        """Gross profit divided by gross loss.

        Returns infinity when there are no losses at all, which in practice
        signals too small a sample rather than a perfect strategy.
        """
        if self.gross_loss == 0:
            return float("inf") if self.gross_profit > 0 else 0.0
        return self.gross_profit / self.gross_loss

    @property
    def total_return_pct(self) -> float:
        return (self.final_equity / self.initial_capital - 1.0) * 100.0

    @property
    def net_pnl(self) -> float:
        return self.final_equity - self.initial_capital

    @property
    def total_fees(self) -> float:
        return sum(t.fees for t in self.trades)

    @property
    def total_funding(self) -> float:
        return sum(t.funding for t in self.trades)

    @property
    def expectancy_pct(self) -> float:
        """Average return per trade, as a percentage of notional."""
        if not self.trades:
            return 0.0
        return float(np.mean([t.return_pct for t in self.trades]))

    @property
    def max_drawdown_pct(self) -> float:
        """Largest peak-to-trough decline in the equity curve."""
        if self.equity_curve.empty:
            return 0.0
        running_peak = self.equity_curve.cummax()
        drawdown = (self.equity_curve - running_peak) / running_peak
        return abs(float(drawdown.min())) * 100.0

    @property
    def sharpe_ratio(self) -> float:
        """Annualised Sharpe of per-trade returns.

        Computed on trade returns rather than calendar returns because trade
        frequency varies widely between symbols. Annualisation assumes the
        observed trade cadence continues.
        """
        if len(self.trades) < 2:
            return 0.0
        returns = np.array([t.return_pct / 100.0 for t in self.trades])
        if returns.std(ddof=1) == 0:
            return 0.0

        span_days = self._span_days()
        trades_per_year = (len(self.trades) / span_days * 365.0) if span_days > 0 else 0.0
        return float(returns.mean() / returns.std(ddof=1) * np.sqrt(max(trades_per_year, 1e-9)))

    @property
    def sortino_ratio(self) -> float:
        """Like Sharpe but penalising only downside deviation."""
        if len(self.trades) < 2:
            return 0.0
        returns = np.array([t.return_pct / 100.0 for t in self.trades])
        downside = returns[returns < 0]
        if downside.size == 0 or downside.std(ddof=1) == 0:
            return 0.0

        span_days = self._span_days()
        trades_per_year = (len(self.trades) / span_days * 365.0) if span_days > 0 else 0.0
        return float(returns.mean() / downside.std(ddof=1) * np.sqrt(max(trades_per_year, 1e-9)))

    @property
    def max_consecutive_losses(self) -> int:
        """Longest losing streak. Drives the psychological survivability question."""
        worst = current = 0
        for trade in self.trades:
            if trade.is_win:
                current = 0
            else:
                current += 1
                worst = max(worst, current)
        return worst

    @property
    def avg_bars_held(self) -> float:
        if not self.trades:
            return 0.0
        return float(np.mean([t.bars_held for t in self.trades]))

    @property
    def exit_breakdown(self) -> dict[str, int]:
        """Count of trades by exit reason.

        A strategy exiting mostly on timeout is not doing what its TP/SL
        parameters claim.
        """
        counts: dict[str, int] = {}
        for trade in self.trades:
            counts[trade.exit_reason.value] = counts.get(trade.exit_reason.value, 0) + 1
        return counts

    def _span_days(self) -> float:
        if not self.start or not self.end:
            return 0.0
        return max((self.end - self.start).total_seconds() / 86400.0, 0.0)

    def summary(self) -> dict[str, object]:
        """Flat metric dictionary for reports, JSON artifacts and the dashboard."""
        return {
            "symbol": self.symbol,
            "strategy": self.strategy,
            "side": self.side,
            "start": self.start.isoformat() if self.start else None,
            "end": self.end.isoformat() if self.end else None,
            "days": round(self._span_days(), 1),
            "signals_generated": self.signals_generated,
            "total_trades": self.total_trades,
            "win_rate": round(self.win_rate, 2),
            "profit_factor": (
                round(self.profit_factor, 3) if np.isfinite(self.profit_factor) else None
            ),
            "total_return_pct": round(self.total_return_pct, 3),
            "net_pnl": round(self.net_pnl, 2),
            "expectancy_pct": round(self.expectancy_pct, 4),
            "max_drawdown_pct": round(self.max_drawdown_pct, 2),
            "sharpe_ratio": round(self.sharpe_ratio, 3),
            "sortino_ratio": round(self.sortino_ratio, 3),
            "max_consecutive_losses": self.max_consecutive_losses,
            "avg_bars_held": round(self.avg_bars_held, 1),
            "total_fees": round(self.total_fees, 2),
            "total_funding": round(self.total_funding, 2),
            "exit_breakdown": self.exit_breakdown,
            "initial_capital": self.initial_capital,
            "final_equity": round(self.final_equity, 2),
        }

    def __str__(self) -> str:
        pf = f"{self.profit_factor:.2f}" if np.isfinite(self.profit_factor) else "inf"
        return (
            f"{self.symbol} {self.side} | {self.total_trades} trades | "
            f"WR {self.win_rate:.1f}% | PF {pf} | "
            f"Ret {self.total_return_pct:+.2f}% | DD {self.max_drawdown_pct:.1f}%"
        )


class BacktestEngine:
    """Simulates a single strategy on a single symbol."""

    def __init__(self, config: BacktestConfig | None = None) -> None:
        self.config = config or BacktestConfig()

    def run(
        self,
        symbol: str,
        candles: pd.DataFrame,
        strategy: Strategy,
        funding: FundingHistory | None = None,
    ) -> BacktestResult:
        """Run the simulation.

        Args:
            symbol: Traded symbol, for labelling and cost lookup.
            candles: Canonical OHLCV frame.
            strategy: Any `Strategy`. Signals come from the same code the live
                engine uses.
            funding: Funding history for realistic perp carry. Falls back to the
                cost model's default rate when omitted.

        Returns:
            A `BacktestResult` with trades, equity curve and metrics.
        """
        config = self.config
        costs = config.costs

        if candles.empty:
            return self._empty_result(symbol, strategy)

        signals = strategy.generate_signals(candles)
        signal_count = int((signals["signal"] != 0).sum())

        params = strategy.params
        take_profit_pct = params.take_profit_pct
        stop_loss_pct = params.stop_loss_pct
        max_holding = params.max_holding_bars

        # Positional numpy views: the inner loop runs over hundreds of thousands
        # of bars during optimisation sweeps, where .iloc lookups dominate.
        opens = candles["open"].to_numpy(dtype="float64")
        highs = candles["high"].to_numpy(dtype="float64")
        lows = candles["low"].to_numpy(dtype="float64")
        closes = candles["close"].to_numpy(dtype="float64")
        timestamps = candles.index

        signal_values = signals["signal"].to_numpy(dtype="int64")
        scores = signals["score"].to_numpy(dtype="float64")
        reasons = signals["reason"].to_numpy(dtype=object)

        equity = config.initial_capital
        trades: list[Trade] = []
        equity_stamps: list[pd.Timestamp] = [timestamps[0]]
        equity_values: list[float] = [equity]

        bar = 0
        total_bars = len(candles)

        while bar < total_bars - 1:
            if signal_values[bar] == 0:
                bar += 1
                continue

            side = SignalSide.LONG if signal_values[bar] > 0 else SignalSide.SHORT

            # ---- entry: next bar's open, never this bar's close ----------
            entry_bar = bar + 1
            entry_quote = opens[entry_bar]
            if not np.isfinite(entry_quote) or entry_quote <= 0:
                bar += 1
                continue

            entry_price = costs.entry_price(entry_quote, side.value)

            sizing_base = equity if config.compound else config.initial_capital
            notional = sizing_base * config.position_fraction
            if notional <= 0:
                break
            quantity = notional / entry_price

            # ---- target levels off the actual fill -----------------------
            if side is SignalSide.LONG:
                take_profit = entry_price * (1.0 + take_profit_pct)
                stop_loss = entry_price * (1.0 - stop_loss_pct)
            else:
                take_profit = entry_price * (1.0 - take_profit_pct)
                stop_loss = entry_price * (1.0 + stop_loss_pct)

            # ---- walk forward to an exit ---------------------------------
            exit_bar, exit_quote, reason = self._find_exit(
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
            )

            exit_price = (
                costs.exit_price(exit_quote, side.value)
                if reason not in (ExitReason.STOP_LOSS,)
                else exit_quote  # stop fills already reflect the adverse level
            )

            # ---- P&L -----------------------------------------------------
            if side is SignalSide.LONG:
                gross_pnl = (exit_price - entry_price) * quantity
            else:
                gross_pnl = (entry_price - exit_price) * quantity

            exit_notional = exit_price * quantity
            fees = costs.round_trip_fees(notional, exit_notional)

            entry_time = timestamps[entry_bar].to_pydatetime()
            exit_time = timestamps[exit_bar].to_pydatetime()
            funding_cost = costs.funding_cost(
                side.value, entry_time, exit_time, notional, funding
            )

            net_pnl = gross_pnl - fees - funding_cost
            equity += net_pnl

            trades.append(
                Trade(
                    symbol=symbol,
                    side=side,
                    entry_time=entry_time,
                    entry_price=entry_price,
                    exit_time=exit_time,
                    exit_price=exit_price,
                    quantity=quantity,
                    notional=notional,
                    gross_pnl=gross_pnl,
                    fees=fees,
                    funding=funding_cost,
                    net_pnl=net_pnl,
                    return_pct=net_pnl / notional * 100.0,
                    exit_reason=reason,
                    bars_held=exit_bar - entry_bar,
                    entry_score=float(scores[bar]),
                    entry_reason=str(reasons[bar]),
                    equity_after=equity,
                )
            )

            equity_stamps.append(timestamps[exit_bar])
            equity_values.append(equity)

            # Ruin check: stop simulating a blown account.
            if equity <= config.initial_capital * 0.05:
                logger.warning("%s: equity fell below 5%% of capital; halting run.", symbol)
                break

            # No pyramiding: resume scanning after the exit bar.
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

    def _find_exit(
        self,
        *,
        entry_bar: int,
        total_bars: int,
        side: SignalSide,
        opens: np.ndarray,
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
        take_profit: float,
        stop_loss: float,
        max_holding: int,
    ) -> tuple[int, float, ExitReason]:
        """Locate the exit bar, fill price and reason.

        Resolution order within a bar, most to least adverse:
          1. Gap through the stop at the open -> fill at the open.
          2. Both TP and SL inside the bar's range -> assume the stop
             (`pessimistic_intrabar`).
          3. Stop touched -> fill at the stop level.
          4. Target touched -> fill at the target level.
        """
        pessimistic = self.config.pessimistic_intrabar
        last_bar = min(entry_bar + max_holding, total_bars - 1)

        for bar in range(entry_bar, last_bar + 1):
            bar_open = opens[bar]
            bar_high = highs[bar]
            bar_low = lows[bar]

            if side is SignalSide.LONG:
                # A gap below the stop fills at the open, not the stop.
                if bar > entry_bar and bar_open <= stop_loss:
                    return bar, bar_open, ExitReason.STOP_LOSS

                hit_stop = bar_low <= stop_loss
                hit_target = bar_high >= take_profit

                if hit_stop and hit_target:
                    if pessimistic:
                        return bar, stop_loss, ExitReason.STOP_LOSS
                    return bar, take_profit, ExitReason.TAKE_PROFIT
                if hit_stop:
                    return bar, stop_loss, ExitReason.STOP_LOSS
                if hit_target:
                    return bar, take_profit, ExitReason.TAKE_PROFIT
            else:
                # A gap above the stop fills at the open.
                if bar > entry_bar and bar_open >= stop_loss:
                    return bar, bar_open, ExitReason.STOP_LOSS

                hit_stop = bar_high >= stop_loss
                hit_target = bar_low <= take_profit

                if hit_stop and hit_target:
                    if pessimistic:
                        return bar, stop_loss, ExitReason.STOP_LOSS
                    return bar, take_profit, ExitReason.TAKE_PROFIT
                if hit_stop:
                    return bar, stop_loss, ExitReason.STOP_LOSS
                if hit_target:
                    return bar, take_profit, ExitReason.TAKE_PROFIT

        # Neither level touched inside the holding window.
        reason = (
            ExitReason.TIMEOUT if last_bar < total_bars - 1 else ExitReason.END_OF_DATA
        )
        return last_bar, closes[last_bar], reason

    def _empty_result(self, symbol: str, strategy: Strategy) -> BacktestResult:
        return BacktestResult(
            symbol=symbol,
            strategy=strategy.name,
            side=getattr(strategy.params, "side", SignalSide.FLAT).value
            if hasattr(strategy.params, "side")
            else "BOTH",
            start=None,
            end=None,
            initial_capital=self.config.initial_capital,
            final_equity=self.config.initial_capital,
        )
