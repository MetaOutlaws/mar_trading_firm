"""
Paper broker: simulated fills against live mainnet prices.

Why this exists alongside the Bybit testnet broker: testnet order books are
thin and their prices drift from mainnet, so testnet fills tell you little about
real slippage. This broker reads *mainnet* prices -- the ones you would actually
trade against -- and simulates the fill using the same cost model the backtester
uses. That makes paper results directly comparable to backtest results, which is
the whole point of the 60-day forward test.

What it does model: slippage, taker fees, TP/SL triggering, position state.
What it does not model: partial fills, order-book depth, exchange outages. The
Bybit testnet broker covers those; run both.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from core.data.ohlcv import BybitOHLCV
from core.execution.broker import (
    Broker,
    Instrument,
    InvalidOrder,
    OrderResult,
    PositionSnapshot,
)
from research.costs import DEFAULT_COSTS, CostModel

logger = logging.getLogger(__name__)


@dataclass
class PaperPosition:
    """Internal state for a simulated position."""

    symbol: str
    side: str
    quantity: float
    entry_price: float
    take_profit: float | None = None
    stop_loss: float | None = None
    opened_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def unrealised_pnl(self, mark_price: float) -> float:
        direction = 1.0 if self.side == "LONG" else -1.0
        return (mark_price - self.entry_price) * self.quantity * direction


class PaperBroker(Broker):
    """Simulated broker driven by live mainnet market data."""

    mode = "paper"

    def __init__(
        self,
        starting_equity: float = 10_000.0,
        costs: CostModel | None = None,
        data_source: BybitOHLCV | None = None,
    ) -> None:
        self.costs = costs or DEFAULT_COSTS
        self._data = data_source or BybitOHLCV()
        self._owns_data_source = data_source is None

        self._cash = starting_equity
        self._positions: dict[str, PaperPosition] = {}
        self._instruments: dict[str, Instrument] = {}

        #: Realised P&L, tracked separately so equity reconciles exactly.
        self.realised_pnl = 0.0
        self.total_fees = 0.0

    def close(self) -> None:
        if self._owns_data_source:
            self._data.close()

    # -- account -----------------------------------------------------------
    def get_balance(self) -> float:
        """Equity: cash plus unrealised P&L on open positions."""
        unrealised = 0.0
        for position in self._positions.values():
            price = self.get_price(position.symbol)
            if price:
                unrealised += position.unrealised_pnl(price)
        return self._cash + unrealised

    @property
    def cash(self) -> float:
        """Realised cash balance, excluding open-position marks."""
        return self._cash

    def get_positions(self) -> list[PositionSnapshot]:
        snapshots = []
        for position in self._positions.values():
            mark = self.get_price(position.symbol) or position.entry_price
            snapshots.append(
                PositionSnapshot(
                    symbol=position.symbol,
                    side=position.side,
                    quantity=position.quantity,
                    entry_price=position.entry_price,
                    mark_price=mark,
                    unrealised_pnl=position.unrealised_pnl(mark),
                    take_profit=position.take_profit,
                    stop_loss=position.stop_loss,
                )
            )
        return snapshots

    # -- market data -------------------------------------------------------
    def get_price(self, symbol: str) -> float | None:
        return self._data.latest_price(symbol)

    def get_instrument(self, symbol: str) -> Instrument:
        """Instrument rules, inferred from price magnitude.

        The real broker queries the exchange. Here a reasonable approximation
        suffices: precision scales inversely with price, which matches how
        exchanges actually set steps.
        """
        if symbol in self._instruments:
            return self._instruments[symbol]

        price = self.get_price(symbol) or 1.0
        if price >= 10_000:
            instrument = Instrument(symbol, tick_size=0.1, qty_step=0.001, min_qty=0.001)
        elif price >= 100:
            instrument = Instrument(symbol, tick_size=0.01, qty_step=0.01, min_qty=0.01)
        elif price >= 1:
            instrument = Instrument(symbol, tick_size=0.001, qty_step=0.1, min_qty=0.1)
        else:
            instrument = Instrument(symbol, tick_size=0.00001, qty_step=1.0, min_qty=1.0)

        self._instruments[symbol] = instrument
        return instrument

    # -- orders ------------------------------------------------------------
    def place_market_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        expected_price: float,
        reduce_only: bool = False,
    ) -> OrderResult:
        """Simulate a market fill with slippage and fees."""
        direction = self._normalise_side(side)
        price = self.get_price(symbol)

        if price is None:
            return OrderResult(
                success=False,
                symbol=symbol,
                side=direction,
                requested_quantity=quantity,
                expected_price=expected_price,
                error="no market price available",
            )

        instrument = self.get_instrument(symbol)
        quantity = instrument.round_quantity(quantity)
        tradable, why_not = instrument.is_tradable(quantity, price)
        if not tradable:
            return OrderResult(
                success=False,
                symbol=symbol,
                side=direction,
                requested_quantity=quantity,
                expected_price=expected_price,
                error=why_not,
            )

        # Fill worse than the quote, in the direction that hurts. Both
        # `entry_price` and `exit_price` take the *position* direction, so
        # `direction` is passed unchanged: closing a long sells below the quote.
        fill_price = (
            self.costs.exit_price(price, direction)
            if reduce_only
            else self.costs.entry_price(price, direction)
        )
        notional = quantity * fill_price
        fee = self.costs.fee_for(notional)

        if reduce_only:
            return self._apply_close(symbol, quantity, fill_price, fee, expected_price)
        return self._apply_open(
            symbol, direction, quantity, fill_price, fee, expected_price, notional
        )

    def _apply_open(
        self,
        symbol: str,
        direction: str,
        quantity: float,
        fill_price: float,
        fee: float,
        expected_price: float,
        notional: float,
    ) -> OrderResult:
        if symbol in self._positions:
            raise InvalidOrder(f"already holding {symbol}; close it before reopening")

        # Unlevered: the notional must be covered by cash.
        if notional > self._cash:
            return OrderResult(
                success=False,
                symbol=symbol,
                side=direction,
                requested_quantity=quantity,
                expected_price=expected_price,
                error=f"notional {notional:.2f} exceeds cash {self._cash:.2f}",
            )

        self._positions[symbol] = PaperPosition(
            symbol=symbol, side=direction, quantity=quantity, entry_price=fill_price
        )
        self._cash -= fee
        self.total_fees += fee

        result = OrderResult(
            success=True,
            order_id=f"paper-{uuid.uuid4().hex[:12]}",
            symbol=symbol,
            side=direction,
            requested_quantity=quantity,
            filled_quantity=quantity,
            expected_price=expected_price,
            fill_price=fill_price,
            fee=fee,
        )
        logger.info(
            "PAPER OPEN %s %s qty=%.6f @ %.6f (expected %.6f, slippage %.1f bps, fee %.4f)",
            direction, symbol, quantity, fill_price, expected_price, result.slippage_bps, fee,
        )
        return result

    def _apply_close(
        self,
        symbol: str,
        quantity: float,
        fill_price: float,
        fee: float,
        expected_price: float,
    ) -> OrderResult:
        position = self._positions.get(symbol)
        if position is None:
            return OrderResult(
                success=False,
                symbol=symbol,
                requested_quantity=quantity,
                expected_price=expected_price,
                error=f"no open position in {symbol}",
            )

        closing_quantity = min(quantity, position.quantity)
        direction = 1.0 if position.side == "LONG" else -1.0
        gross_pnl = (fill_price - position.entry_price) * closing_quantity * direction

        self._cash += gross_pnl - fee
        self.realised_pnl += gross_pnl - fee
        self.total_fees += fee

        if closing_quantity >= position.quantity - 1e-12:
            del self._positions[symbol]
        else:
            position.quantity -= closing_quantity

        result = OrderResult(
            success=True,
            order_id=f"paper-{uuid.uuid4().hex[:12]}",
            symbol=symbol,
            side="SELL" if position.side == "LONG" else "BUY",
            requested_quantity=quantity,
            filled_quantity=closing_quantity,
            expected_price=expected_price,
            fill_price=fill_price,
            fee=fee,
        )
        logger.info(
            "PAPER CLOSE %s qty=%.6f @ %.6f | gross P&L %.4f, fee %.4f, cash %.2f",
            symbol, closing_quantity, fill_price, gross_pnl, fee, self._cash,
        )
        return result

    def set_stops(
        self, symbol: str, take_profit: float | None, stop_loss: float | None
    ) -> bool:
        position = self._positions.get(symbol)
        if position is None:
            logger.warning("Cannot set stops: no open position in %s", symbol)
            return False
        position.take_profit = take_profit
        position.stop_loss = stop_loss
        logger.info("PAPER STOPS %s TP=%s SL=%s", symbol, take_profit, stop_loss)
        return True

    def close_position(self, symbol: str) -> OrderResult:
        position = self._positions.get(symbol)
        if position is None:
            return OrderResult(success=False, symbol=symbol, error="no open position")
        price = self.get_price(symbol) or position.entry_price
        return self.place_market_order(
            symbol, position.side, position.quantity, expected_price=price, reduce_only=True
        )

    # -- simulated stop monitoring ----------------------------------------
    def check_stops(self) -> list[tuple[str, str, OrderResult]]:
        """Trigger any TP/SL that the current price has reached.

        A real exchange enforces stops server-side; in paper mode the engine
        must poll. Stops are checked *before* take profits so that a price which
        has moved past both is resolved pessimistically, matching the
        backtester's intrabar assumption.
        """
        triggered: list[tuple[str, str, OrderResult]] = []

        for symbol, position in list(self._positions.items()):
            price = self.get_price(symbol)
            if price is None:
                continue

            hit_stop = False
            hit_target = False

            if position.side == "LONG":
                hit_stop = position.stop_loss is not None and price <= position.stop_loss
                hit_target = position.take_profit is not None and price >= position.take_profit
            else:
                hit_stop = position.stop_loss is not None and price >= position.stop_loss
                hit_target = position.take_profit is not None and price <= position.take_profit

            if hit_stop:
                triggered.append((symbol, "stop_loss", self.close_position(symbol)))
            elif hit_target:
                triggered.append((symbol, "take_profit", self.close_position(symbol)))

        return triggered

    # -- helpers -----------------------------------------------------------
    @staticmethod
    def _normalise_side(side: str) -> str:
        upper = side.upper()
        if upper in ("LONG", "BUY"):
            return "LONG"
        if upper in ("SHORT", "SELL"):
            return "SHORT"
        raise InvalidOrder(f"unrecognised side {side!r}")
