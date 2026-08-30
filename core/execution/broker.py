"""
The Broker interface.

One abstraction with three implementations -- paper, Bybit testnet, Bybit live --
so the trading engine has no idea which it is talking to. That matters because
the code path exercised during 60 days of paper trading must be the same one
that later trades real money; otherwise paper trading validates the wrong thing.

Instrument metadata (tick size, quantity step, minimum order value) is part of
the interface because rounding a quantity to the wrong precision is one of the
most common causes of silently rejected orders, and it is exactly the class of
bug paper trading is supposed to catch.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone


class BrokerError(Exception):
    """A broker operation failed."""


class InsufficientBalance(BrokerError):
    """Not enough balance to place the order."""


class InvalidOrder(BrokerError):
    """The order was malformed or violated an exchange constraint."""


@dataclass(frozen=True)
class Instrument:
    """Exchange trading rules for one symbol.

    Sourced from the exchange rather than assumed: quantity steps differ by
    orders of magnitude between BTC (0.001) and 1000PEPE (10).
    """

    symbol: str
    tick_size: float = 0.01  # minimum price increment
    qty_step: float = 0.001  # minimum quantity increment
    min_qty: float = 0.001
    min_notional: float = 5.0
    max_leverage: float = 10.0

    def round_price(self, price: float) -> float:
        """Round a price down to a valid tick."""
        if self.tick_size <= 0:
            return price
        return math.floor(price / self.tick_size) * self.tick_size

    def round_quantity(self, quantity: float) -> float:
        """Round a quantity *down* to a valid step.

        Always down: rounding up could exceed a risk limit that was computed
        against the exact figure.
        """
        if self.qty_step <= 0:
            return quantity
        steps = math.floor(quantity / self.qty_step)
        return steps * self.qty_step

    def is_tradable(self, quantity: float, price: float) -> tuple[bool, str]:
        """Whether an order meets the exchange's minimums."""
        if quantity < self.min_qty:
            return False, f"quantity {quantity} below minimum {self.min_qty}"
        notional = quantity * price
        if notional < self.min_notional:
            return False, f"notional {notional:.2f} below minimum {self.min_notional}"
        return True, ""


@dataclass
class OrderResult:
    """Outcome of an order submission."""

    success: bool
    order_id: str = ""
    symbol: str = ""
    side: str = ""
    requested_quantity: float = 0.0
    filled_quantity: float = 0.0
    #: Price the strategy expected, used to measure slippage.
    expected_price: float = 0.0
    #: Price actually received.
    fill_price: float = 0.0
    fee: float = 0.0
    submitted_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    error: str = ""
    raw: dict = field(default_factory=dict)

    @property
    def slippage_bps(self) -> float:
        """Realised slippage in basis points, positive meaning unfavourable."""
        if not self.expected_price or not self.fill_price:
            return 0.0
        difference = (self.fill_price - self.expected_price) / self.expected_price
        direction = 1.0 if self.side.upper() in ("BUY", "LONG") else -1.0
        return difference * direction * 10_000


@dataclass
class PositionSnapshot:
    """A position as reported by the broker."""

    symbol: str
    side: str  # LONG / SHORT
    quantity: float
    entry_price: float
    mark_price: float
    unrealised_pnl: float
    take_profit: float | None = None
    stop_loss: float | None = None
    leverage: float = 1.0

    @property
    def notional(self) -> float:
        return abs(self.quantity) * self.mark_price


class Broker(ABC):
    """Abstract broker.

    Implementations must be safe to call repeatedly and must never raise for
    ordinary business outcomes (a rejected order returns
    `OrderResult(success=False)`). Exceptions are reserved for genuine failures
    such as a dead connection, which is what the kill switch reacts to.
    """

    #: Label recorded on every position and trade, e.g. "paper" or "live".
    mode: str = "unknown"

    @abstractmethod
    def get_balance(self) -> float:
        """Available account equity in USDT."""

    @abstractmethod
    def get_positions(self) -> list[PositionSnapshot]:
        """All currently open positions."""

    @abstractmethod
    def get_price(self, symbol: str) -> float | None:
        """Latest traded price, or None if unavailable."""

    @abstractmethod
    def get_instrument(self, symbol: str) -> Instrument:
        """Trading rules for a symbol."""

    @abstractmethod
    def place_market_order(
        self,
        symbol: str,
        side: str,
        quantity: float,
        expected_price: float,
        reduce_only: bool = False,
    ) -> OrderResult:
        """Submit a market order.

        Args:
            symbol: Trading symbol.
            side: "LONG"/"SHORT" for opening, or "BUY"/"SELL" directly.
            quantity: Base-asset quantity, already risk-approved.
            expected_price: Price the decision was based on, for slippage
                measurement.
            reduce_only: True when closing, so the order cannot flip the position.
        """

    @abstractmethod
    def set_stops(
        self, symbol: str, take_profit: float | None, stop_loss: float | None
    ) -> bool:
        """Attach take-profit and stop-loss levels to an open position."""

    @abstractmethod
    def close_position(self, symbol: str) -> OrderResult:
        """Close a position at market."""

    def health_check(self) -> tuple[bool, str]:
        """Whether the broker connection is usable.

        Default probes the balance endpoint. The Ops Engineer employee calls
        this, and a failure trips the kill switch rather than trading blind.
        """
        try:
            balance = self.get_balance()
            if balance is None:
                return False, "balance query returned nothing"
            return True, f"ok (equity {balance:.2f} USDT)"
        except Exception as exc:
            return False, f"broker unreachable: {exc}"
