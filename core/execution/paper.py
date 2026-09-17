"""
Paper broker: simulated fills against live mainnet prices.

Why this exists alongside the Bybit testnet broker: testnet order books are
thin and their prices drift from mainnet, so testnet fills tell you little about
real slippage. This broker reads *mainnet* prices -- the ones you would actually
trade against -- and simulates the fill using the same cost model the backtester
uses. That makes paper results directly comparable to backtest results, which is
the whole point of the 60-day forward test.

What it does model: slippage, taker fees on *both* legs, 8h funding accrual
via the same ``CostModel`` the backtester uses (including ``for_symbol``),
TP/SL triggering, position state.
Cash, realised P&L, fees and funding persist across process restarts
(see ``paper_cash.py``). Open positions still come from the SQLite ledger.
What it does not model: partial fills, order-book depth, exchange outages. The
Bybit testnet broker covers those; run both.

Entry fees hit cash on the open and are stored on the position so the ledger
can write a round-trip ``TradeRecord`` (F03). Funding is accrued into cash as
settlements elapse, journaled as ``funding`` events (F02 store), and realised
onto the close.

F04 comparison runs do not poll live marks. ``close_at_fill`` plus
``core.execution.replay.run_paper_replay`` drive this broker over the same
OHLC tape ``BacktestEngine`` uses (next-bar open, fill-based TP/SL, no extra
stop slippage, ``max_holding_bars``).
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from core.data.funding import FundingHistory
from core.data.ohlcv import BybitOHLCV
from core.execution.broker import (
    Broker,
    Instrument,
    InvalidOrder,
    OrderResult,
    PositionSnapshot,
)
from core.execution.paper_cash import (
    KIND_CAPITAL,
    KIND_CLOSE,
    KIND_FUNDING,
    KIND_OPEN,
    PaperCashStore,
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
    #: Taker fee paid on the entry fill. Cash already deducted this; the
    #: ledger stores it so close P&L includes both legs.
    entry_fee: float = 0.0
    #: Funding already taken from cash for this hold (CostModel.funding_cost
    #: from opened_at through the last accrue). Close realises the total.
    funding_accrued: float = 0.0

    def unrealised_pnl(self, mark_price: float) -> float:
        direction = 1.0 if self.side == "LONG" else -1.0
        return (mark_price - self.entry_price) * self.quantity * direction

    @property
    def notional(self) -> float:
        """Entry notional — the same base research uses for funding."""
        return self.quantity * self.entry_price


class PaperBroker(Broker):
    """Simulated broker driven by live mainnet market data."""

    mode = "paper"

    def __init__(
        self,
        starting_equity: float = 10_000.0,
        costs: CostModel | None = None,
        data_source: BybitOHLCV | None = None,
        cash_store: PaperCashStore | None = None,
        lock_cost_model: bool = False,
    ) -> None:
        self.costs = costs or DEFAULT_COSTS
        self._data = data_source or BybitOHLCV()
        self._owns_data_source = data_source is None
        self._cash_store = cash_store

        #: Constructor argument is the *first* capital contribution only when
        #: no cash journal exists yet. Restarts replay persisted capital.
        self._starting_equity = starting_equity
        self._contributed_capital = starting_equity
        self._cash = starting_equity
        self._positions: dict[str, PaperPosition] = {}
        self._instruments: dict[str, Instrument] = {}
        #: When True, ``costs_for`` returns ``self.costs`` unchanged. Golden-tape
        #: replay locks the same CostModel instance the backtest used so a second
        #: ``for_symbol`` pass cannot silently re-scale slippage.
        self._lock_cost_model = lock_cost_model
        #: Optional per-symbol funding history for CostModel parity with research.
        #: Missing symbols fall back to CostModel.default_funding_rate.
        self._funding: dict[str, FundingHistory] = {}
        #: Per-symbol funding already in cash for still-open rows (journal replay).
        self._open_funding: dict[str, float] = {}

        #: Realised P&L, tracked separately so equity reconciles exactly.
        #: Closed-book identity: cash - contributed_capital == realised_pnl ==
        #: sum(TradeRecord.net_pnl), with entry fees and funding included.
        self.realised_pnl = 0.0
        self.total_fees = 0.0
        self.total_funding = 0.0

    def close(self) -> None:
        if self._owns_data_source:
            self._data.close()

    def hydrate(self, positions: list[object]) -> None:
        """Restore cash, then open positions, after a process restart.

        Restore order (do not invert):

        1. Replay the cash/event ledger. That puts cash, realised P&L, fees
           and contributed capital back, including entry fees and funding on
           still-open positions. A missing journal seeds one ``capital`` event
           from ``starting_equity`` so later fills have a contribution to replay.
        2. Overlay open SQLite rows onto the RAM book. Paper never deducts
           notional from cash, so this step must not change cash. Entry fee
           comes from the SQLite row (F03); funding already in cash is copied
           from the journal so the next accrue does not double-charge.

        Without step 1, a restart resets cash to starting equity while the
        position ledger still shows the closed-trade loss (F02). Without
        step 2, an empty RAM book against open SQLite rows trips the kill
        switch.
        """
        self._restore_cash()
        restored = 0
        for row in positions:
            symbol = str(getattr(row, "symbol", "") or "")
            if not symbol:
                continue
            opened = getattr(row, "opened_at", None)
            self._positions[symbol] = PaperPosition(
                symbol=symbol,
                side=self._normalise_side(str(getattr(row, "side", "LONG"))),
                quantity=float(getattr(row, "quantity", 0.0) or 0.0),
                entry_price=float(getattr(row, "entry_price", 0.0) or 0.0),
                take_profit=getattr(row, "take_profit_price", None),
                stop_loss=getattr(row, "stop_loss_price", None),
                opened_at=opened if isinstance(opened, datetime) else datetime.now(timezone.utc),
                entry_fee=float(getattr(row, "entry_fee", 0.0) or 0.0),
                funding_accrued=float(self._open_funding.get(symbol, 0.0)),
            )
            restored += 1
        if restored:
            logger.warning(
                "Paper broker hydrated %d open position(s) from the ledger",
                restored,
            )

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

    @property
    def contributed_capital(self) -> float:
        """External deposits/withdrawals. Never mixed into realised P&L."""
        return self._contributed_capital

    def exposure(self, marks: dict[str, float] | None = None) -> float:
        """Gross notional of open positions at ``marks`` (else live marks)."""
        total = 0.0
        for position in self._positions.values():
            price = (marks or {}).get(position.symbol)
            if price is None:
                price = self.get_price(position.symbol) or position.entry_price
            total += abs(position.quantity * price)
        return total

    def contribute_capital(self, amount: float) -> None:
        """Record an external deposit (+) or withdrawal (-), not trading P&L."""
        if amount == 0.0:
            return
        self._cash += amount
        self._contributed_capital += amount
        self._record_cash_event(
            {
                "kind": KIND_CAPITAL,
                "amount": amount,
                "cash_after": self._cash,
                "contributed_capital": self._contributed_capital,
            }
        )

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

    def costs_for(self, symbol: str) -> CostModel:
        """Per-symbol schedule — same ``for_symbol`` research validation uses.

        Golden-tape replay passes ``lock_cost_model=True`` so this returns the
        CostModel the backtest was given, without a second sector multiplier.
        """
        if self._lock_cost_model:
            return self.costs
        return self.costs.for_symbol(symbol)

    def set_funding_history(self, symbol: str, history: FundingHistory) -> None:
        """Attach a research-style funding series for one symbol."""
        self._funding[symbol] = history

    def _now(self) -> datetime:
        """Clock seam so tests can freeze the funding hold window."""
        return datetime.now(timezone.utc)

    def _funding_cost(self, position: PaperPosition, now: datetime) -> float:
        """Funding for [opened_at, now] via the shared CostModel formula."""
        costs = self.costs_for(position.symbol)
        history = self._funding.get(position.symbol)
        return costs.funding_cost(
            position.side,
            position.opened_at,
            now,
            position.notional,
            history,
        )

    def accrue_funding(self, now: datetime | None = None) -> float:
        """Move cash by funding since the last accrue. Returns net cash delta.

        Positive delta means cash increased (shorts receiving a positive rate).
        Uses ``CostModel.funding_cost`` so a closed paper trade matches a
        research run with the same model, window, notional and history.
        Each non-zero step is appended to the F02 cash journal as ``funding``.
        """
        now = now or self._now()
        cash_delta = 0.0
        for position in self._positions.values():
            target = self._funding_cost(position, now)
            step = target - position.funding_accrued
            if abs(step) < 1e-12:
                continue
            self._cash -= step
            position.funding_accrued = target
            cash_delta -= step
            self._record_cash_event(
                {
                    "kind": KIND_FUNDING,
                    "symbol": position.symbol,
                    "amount": step,
                    "cash_after": self._cash,
                    "funding_accrued": position.funding_accrued,
                }
            )
        return cash_delta

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

        costs = self.costs_for(symbol)
        # Fill worse than the quote, in the direction that hurts. Both
        # `entry_price` and `exit_price` take the *position* direction, so
        # `direction` is passed unchanged: closing a long sells below the quote.
        fill_price = (
            costs.exit_price(price, direction)
            if reduce_only
            else costs.entry_price(price, direction)
        )
        notional = quantity * fill_price
        fee = costs.fee_for(notional)

        if reduce_only:
            # Settle funding through this instant before the exit fill.
            self.accrue_funding()
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
            symbol=symbol,
            side=direction,
            quantity=quantity,
            entry_price=fill_price,
            opened_at=self._now(),
            entry_fee=fee,
        )
        self._cash -= fee
        self.total_fees += fee
        self._record_cash_event(
            {
                "kind": KIND_OPEN,
                "symbol": symbol,
                "side": direction,
                "quantity": quantity,
                "fill_price": fill_price,
                "fee": fee,
                "notional": notional,
                "cash_after": self._cash,
                "realised_pnl": self.realised_pnl,
                "total_fees": self.total_fees,
            }
        )

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
        fraction = closing_quantity / position.quantity if position.quantity else 1.0
        direction = 1.0 if position.side == "LONG" else -1.0
        gross_pnl = (fill_price - position.entry_price) * closing_quantity * direction
        entry_fee_share = position.entry_fee * fraction
        # Accrue already brought funding_accrued up to `_now()` for the full
        # size. Realise the closed slice; leftover stays on the stub.
        funding_share = position.funding_accrued * fraction
        position_side = position.side

        # Entry fee already left cash on the open. Close moves cash by
        # gross minus the *exit* fee; funding for this slice is already in cash
        # via accrue_funding. realised_pnl gets every cost so a flat book
        # satisfies cash - contributed == realised_pnl.
        self._cash += gross_pnl - fee
        self.realised_pnl += gross_pnl - entry_fee_share - fee - funding_share
        self.total_fees += fee
        self.total_funding += funding_share
        self._record_cash_event(
            {
                "kind": KIND_CLOSE,
                "symbol": symbol,
                "side": position_side,
                "quantity": closing_quantity,
                "fill_price": fill_price,
                "fee": fee,
                "entry_fee": entry_fee_share,
                "gross_pnl": gross_pnl,
                "funding": funding_share,
                "cash_after": self._cash,
                "realised_pnl": self.realised_pnl,
                "total_fees": self.total_fees,
                "total_funding": self.total_funding,
            }
        )

        if closing_quantity >= position.quantity - 1e-12:
            del self._positions[symbol]
        else:
            position.quantity -= closing_quantity
            position.entry_fee -= entry_fee_share
            position.funding_accrued -= funding_share

        result = OrderResult(
            success=True,
            order_id=f"paper-{uuid.uuid4().hex[:12]}",
            symbol=symbol,
            side="SELL" if position_side == "LONG" else "BUY",
            requested_quantity=quantity,
            filled_quantity=closing_quantity,
            expected_price=expected_price,
            fill_price=fill_price,
            fee=fee,
            funding=funding_share,
        )
        logger.info(
            "PAPER CLOSE %s qty=%.6f @ %.6f | gross P&L %.4f, exit fee %.4f, "
            "entry fee %.4f, funding %.4f, cash %.2f",
            symbol, closing_quantity, fill_price, gross_pnl, fee,
            entry_fee_share, funding_share, self._cash,
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

    def close_at_fill(
        self, symbol: str, fill_price: float, expected_price: float
    ) -> OrderResult:
        """Close at an already-resolved contract fill (no extra slip).

        Replay uses this after ``exit_fill_price`` so a stop does not take a
        second ``CostModel.exit_price`` tick. Live ``close_position`` still
        applies exit slippage to a sampled mark — that path is not the tape.
        """
        position = self._positions.get(symbol)
        if position is None:
            return OrderResult(
                success=False, symbol=symbol, error=f"no open position in {symbol}"
            )
        costs = self.costs_for(symbol)
        quantity = position.quantity
        fee = costs.fee_for(quantity * fill_price)
        self.accrue_funding()
        return self._apply_close(symbol, quantity, fill_price, fee, expected_price)

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
                # Sampled last-price poll: fill at the last mark without a
                # second exit-slippage tick (F04). Replay uses OHLC +
                # ``close_at_fill`` and does not come through here.
                triggered.append(
                    (
                        symbol,
                        "stop_loss",
                        self.close_at_fill(symbol, price, position.stop_loss or price),
                    )
                )
            elif hit_target:
                # TP: contract applies exit slippage to the target level. The
                # sampled mark may already be through the target; still fill
                # at that mark (live limitation) but charge exit slip once.
                triggered.append((symbol, "take_profit", self.close_position(symbol)))

        return triggered

    # -- cash journal ------------------------------------------------------
    def _restore_cash(self) -> None:
        """Step 1 of hydrate: replay persisted events or seed starting capital."""
        if self._cash_store is None:
            return
        if self._cash_store.has_events():
            state = self._cash_store.replay()
            self._contributed_capital = state.contributed_capital
            self._cash = state.cash
            self.realised_pnl = state.realised_pnl
            self.total_fees = state.total_fees
            self.total_funding = state.total_funding
            self._open_funding = dict(state.open_funding)
            logger.warning(
                "Paper cash replayed from %s: cash=%.4f realised=%.4f "
                "fees=%.4f funding=%.4f contributed=%.4f (%d events)",
                self._cash_store.path,
                self._cash,
                self.realised_pnl,
                self.total_fees,
                self.total_funding,
                self._contributed_capital,
                len(state.events),
            )
            return
        self._seed_starting_capital()

    def _seed_starting_capital(self) -> None:
        """First persist: starting equity is a capital contribution, not P&L."""
        if self._cash_store is None or self._cash_store.has_events():
            return
        self._contributed_capital = self._starting_equity
        self._cash = self._starting_equity
        self.realised_pnl = 0.0
        self.total_fees = 0.0
        self.total_funding = 0.0
        self._open_funding = {}
        self._cash_store.record(
            {
                "kind": KIND_CAPITAL,
                "amount": self._starting_equity,
                "cash_after": self._cash,
                "contributed_capital": self._contributed_capital,
            }
        )

    def _record_cash_event(self, event: dict) -> None:
        if self._cash_store is None:
            return
        # A fill before hydrate still needs a capital event to replay.
        self._seed_starting_capital()
        self._cash_store.record(event)

    # -- helpers -----------------------------------------------------------
    @staticmethod
    def _normalise_side(side: str) -> str:
        upper = side.upper()
        if upper in ("LONG", "BUY"):
            return "LONG"
        if upper in ("SHORT", "SELL"):
            return "SHORT"
        raise InvalidOrder(f"unrecognised side {side!r}")
