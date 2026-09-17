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

Fill timing, TP/SL origin, holding expiry and stop-slippage live in
``core.execution.contract`` (F04). This engine is the research implementation
of that contract; ``core.execution.replay.run_paper_replay`` is the paper one.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime

import numpy as np
import pandas as pd

from core.data.funding import FundingHistory
from core.execution.contract import (
    ExitReason,
    exit_fill_price,
    fill_in_tradable_window,
    find_exit_on_path,
    risk_levels,
)
from core.strategy.base import SignalSide, Strategy
from research.costs import DEFAULT_COSTS, CostModel

logger = logging.getLogger(__name__)

# Re-exported so walk-forward, tests and the golden tape keep a stable import.
__all__ = [
    "BacktestConfig",
    "BacktestEngine",
    "BacktestResult",
    "ExitReason",
    "Trade",
    "fill_in_tradable_window",
]


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
        *,
        tradable_start: datetime | None = None,
        tradable_end: datetime | None = None,
    ) -> BacktestResult:
        """Run the simulation.

        Args:
            symbol: Traded symbol, for labelling and cost lookup.
            candles: Canonical OHLCV frame. May include warmup bars before
                `tradable_start`; those bars seed indicators only.
            strategy: Any `Strategy`. Signals come from the same code the live
                engine uses.
            funding: Funding history for realistic perp carry. Falls back to the
                cost model's default rate when omitted.
            tradable_start: Inclusive start of eligible *entry fill* times.
                Signals may fire earlier (last warmup bar → first-window fill).
            tradable_end: Exclusive end of eligible entry fill times. A fill
                at exactly `tradable_end` is not in this window.

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
            fill_time = timestamps[entry_bar]
            # Gate on fill time, not signal time. A last-warmup-bar signal
            # that fills at/after tradable_start is a valid window entry;
            # a fill before tradable_start is F01 warmup contamination.
            if not fill_in_tradable_window(fill_time, tradable_start, tradable_end):
                if tradable_end is not None and pd.Timestamp(fill_time) >= pd.Timestamp(
                    tradable_end
                ):
                    break
                bar += 1
                continue

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

            # ---- target levels off the actual fill (F04 contract) --------
            take_profit, stop_loss = risk_levels(
                entry_price, side, take_profit_pct, stop_loss_pct
            )

            # ---- walk forward to an exit ---------------------------------
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
