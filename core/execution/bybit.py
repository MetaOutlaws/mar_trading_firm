"""
Bybit broker for linear perpetuals, covering both testnet and live.

Safety properties, in response to the predecessor project keeping live keys in
source with `testnet=False`:

* Credentials come only from `config.settings`. There are no literals here.
* Constructing a live broker requires `Settings` to already have passed its
  live-mode guard, which needs the explicit confirmation phrase.
* Instrument rules are fetched from the exchange rather than assumed, so
  precision errors surface as clear rejections rather than silent no-ops.
* Every write operation retries transient failures and returns a structured
  result, so the engine can distinguish "the exchange said no" from "the
  network is down" -- only the latter should trip the kill switch.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from pybit.unified_trading import HTTP

from config.settings import TradingMode, get_settings
from core.execution.broker import (
    Broker,
    BrokerError,
    Instrument,
    OrderResult,
    PositionSnapshot,
)

logger = logging.getLogger(__name__)

CATEGORY = "linear"
MAX_RETRIES = 3


class BybitBroker(Broker):
    """Live or testnet Bybit broker."""

    def __init__(self, mode: TradingMode | None = None) -> None:
        settings = get_settings()
        resolved = mode or settings.trading_mode

        if resolved is TradingMode.PAPER:
            raise BrokerError(
                "BybitBroker cannot run in paper mode. Use PaperBroker, which "
                "simulates fills without submitting orders."
            )

        api_key, api_secret = (
            (settings.bybit_live_api_key, settings.bybit_live_api_secret)
            if resolved is TradingMode.LIVE
            else (settings.bybit_testnet_api_key, settings.bybit_testnet_api_secret)
        )

        if not api_key or not api_secret:
            raise BrokerError(
                f"Missing Bybit credentials for {resolved.value} mode. "
                f"Set BYBIT_{resolved.value.upper()}_API_KEY and _API_SECRET in .env."
            )

        self.mode = resolved.value
        self._is_testnet = resolved is TradingMode.TESTNET
        self._session = HTTP(
            testnet=self._is_testnet, api_key=api_key, api_secret=api_secret
        )
        self._instruments: dict[str, Instrument] = {}

        logger.warning(
            "BybitBroker initialised in %s mode (testnet=%s). "
            "Orders placed here are REAL on this network.",
            self.mode, self._is_testnet,
        )

    # -- request plumbing --------------------------------------------------
    def _call(self, method_name: str, **params: Any) -> dict:
        """Invoke a pybit method with retries on transient failure.

        Bybit signals business rejections through `retCode`, which is returned
        rather than raised so the caller can react appropriately. Only transport
        failures raise.
        """
        method = getattr(self._session, method_name)
        last_error: Exception | None = None

        for attempt in range(MAX_RETRIES):
            try:
                response = method(**params)
                if not isinstance(response, dict):
                    raise BrokerError(f"{method_name} returned {type(response)}")
                return response
            except Exception as exc:
                last_error = exc
                backoff = 2**attempt
                logger.warning(
                    "%s failed (attempt %d/%d): %s - retrying in %ds",
                    method_name, attempt + 1, MAX_RETRIES, exc, backoff,
                )
                time.sleep(backoff)

        raise BrokerError(f"{method_name} failed after {MAX_RETRIES} attempts: {last_error}")

    # -- account -----------------------------------------------------------
    def get_balance(self) -> float:
        """Total USDT equity in the unified trading account."""
        response = self._call("get_wallet_balance", accountType="UNIFIED", coin="USDT")
        if response.get("retCode") != 0:
            raise BrokerError(f"balance query failed: {response.get('retMsg')}")

        accounts = response.get("result", {}).get("list", [])
        if not accounts:
            return 0.0

        # Prefer the coin-level equity; fall back to the account total.
        for coin in accounts[0].get("coin", []):
            if coin.get("coin") == "USDT":
                value = coin.get("equity") or coin.get("walletBalance") or 0
                return float(value)

        return float(accounts[0].get("totalEquity") or 0.0)

    def get_positions(self) -> list[PositionSnapshot]:
        response = self._call("get_positions", category=CATEGORY, settleCoin="USDT")
        if response.get("retCode") != 0:
            raise BrokerError(f"position query failed: {response.get('retMsg')}")

        snapshots: list[PositionSnapshot] = []
        for entry in response.get("result", {}).get("list", []):
            size = float(entry.get("size") or 0)
            if size == 0:
                continue  # Bybit reports flat symbols too

            snapshots.append(
                PositionSnapshot(
                    symbol=entry["symbol"],
                    side="LONG" if entry.get("side") == "Buy" else "SHORT",
                    quantity=size,
                    entry_price=float(entry.get("avgPrice") or 0),
                    mark_price=float(entry.get("markPrice") or 0),
                    unrealised_pnl=float(entry.get("unrealisedPnl") or 0),
                    take_profit=_optional_float(entry.get("takeProfit")),
                    stop_loss=_optional_float(entry.get("stopLoss")),
                    leverage=float(entry.get("leverage") or 1),
                )
            )
        return snapshots

    def get_price(self, symbol: str) -> float | None:
        response = self._call("get_tickers", category=CATEGORY, symbol=symbol)
        if response.get("retCode") != 0:
            logger.warning("Ticker query failed for %s: %s", symbol, response.get("retMsg"))
            return None
        entries = response.get("result", {}).get("list", [])
        return float(entries[0]["lastPrice"]) if entries else None

    def get_instrument(self, symbol: str) -> Instrument:
        """Fetch and cache exchange trading rules for a symbol."""
        if symbol in self._instruments:
            return self._instruments[symbol]

        response = self._call("get_instruments_info", category=CATEGORY, symbol=symbol)
        entries = response.get("result", {}).get("list", []) if response.get("retCode") == 0 else []

        if not entries:
            raise BrokerError(f"no instrument info for {symbol}")

        info = entries[0]
        price_filter = info.get("priceFilter", {})
        lot_filter = info.get("lotSizeFilter", {})

        instrument = Instrument(
            symbol=symbol,
            tick_size=float(price_filter.get("tickSize") or 0.01),
            qty_step=float(lot_filter.get("qtyStep") or 0.001),
            min_qty=float(lot_filter.get("minOrderQty") or 0.001),
            min_notional=float(lot_filter.get("minNotionalValue") or 5.0),
            max_leverage=float(info.get("leverageFilter", {}).get("maxLeverage") or 10),
        )
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
        """Submit a market order and report the realised fill."""
        bybit_side = _to_bybit_side(side, reduce_only)
        instrument = self.get_instrument(symbol)
        quantity = instrument.round_quantity(quantity)

        reference_price = expected_price or self.get_price(symbol) or 0.0
        tradable, why_not = instrument.is_tradable(quantity, reference_price)
        if not tradable:
            return OrderResult(
                success=False,
                symbol=symbol,
                side=bybit_side,
                requested_quantity=quantity,
                expected_price=expected_price,
                error=why_not,
            )

        params: dict[str, Any] = {
            "category": CATEGORY,
            "symbol": symbol,
            "side": bybit_side,
            "orderType": "Market",
            "qty": _format_quantity(quantity, instrument.qty_step),
        }
        if reduce_only:
            params["reduceOnly"] = True

        response = self._call("place_order", **params)

        if response.get("retCode") != 0:
            error = f"retCode={response.get('retCode')}: {response.get('retMsg')}"
            logger.error("Order rejected for %s: %s", symbol, error)
            return OrderResult(
                success=False,
                symbol=symbol,
                side=bybit_side,
                requested_quantity=quantity,
                expected_price=expected_price,
                error=error,
                raw=response,
            )

        order_id = response.get("result", {}).get("orderId", "")
        fill_price, fill_quantity, fee = self._resolve_fill(symbol, order_id, reference_price, quantity)

        result = OrderResult(
            success=True,
            order_id=order_id,
            symbol=symbol,
            side=bybit_side,
            requested_quantity=quantity,
            filled_quantity=fill_quantity,
            expected_price=expected_price,
            fill_price=fill_price,
            fee=fee,
            raw=response,
        )
        logger.info(
            "%s ORDER %s %s qty=%s @ %.6f (expected %.6f, slippage %.1f bps)",
            self.mode.upper(), bybit_side, symbol, params["qty"],
            fill_price, expected_price, result.slippage_bps,
        )
        return result

    def _resolve_fill(
        self, symbol: str, order_id: str, fallback_price: float, fallback_quantity: float
    ) -> tuple[float, float, float]:
        """Look up the actual execution price, quantity and fee.

        Market orders fill almost immediately but not synchronously, so this
        polls briefly. Without the real fill price, measured slippage would just
        be the assumption echoed back, defeating the purpose.
        """
        if not order_id:
            return fallback_price, fallback_quantity, 0.0

        for _ in range(5):
            time.sleep(0.4)
            try:
                response = self._call(
                    "get_executions", category=CATEGORY, symbol=symbol, orderId=order_id, limit=50
                )
            except BrokerError:
                break

            if response.get("retCode") != 0:
                continue

            executions = response.get("result", {}).get("list", [])
            if not executions:
                continue

            total_quantity = sum(float(e.get("execQty") or 0) for e in executions)
            total_value = sum(
                float(e.get("execQty") or 0) * float(e.get("execPrice") or 0) for e in executions
            )
            total_fee = sum(float(e.get("execFee") or 0) for e in executions)

            if total_quantity > 0:
                return total_value / total_quantity, total_quantity, total_fee

        logger.warning(
            "Could not confirm fill for order %s on %s; using reference price. "
            "Slippage measurement for this trade is unreliable.",
            order_id, symbol,
        )
        return fallback_price, fallback_quantity, 0.0

    def set_stops(
        self, symbol: str, take_profit: float | None, stop_loss: float | None
    ) -> bool:
        """Attach exchange-side TP/SL to an open position.

        Exchange-side stops matter: they survive this process dying, which
        broker-side protection cannot if stops are only tracked locally.
        """
        instrument = self.get_instrument(symbol)
        params: dict[str, Any] = {
            "category": CATEGORY,
            "symbol": symbol,
            "tpslMode": "Full",
            "positionIdx": 0,
        }
        if take_profit:
            params["takeProfit"] = str(instrument.round_price(take_profit))
        if stop_loss:
            params["stopLoss"] = str(instrument.round_price(stop_loss))

        response = self._call("set_trading_stop", **params)
        if response.get("retCode") != 0:
            logger.error(
                "Failed to set stops on %s: %s. Position is UNPROTECTED.",
                symbol, response.get("retMsg"),
            )
            return False

        logger.info("Stops set on %s: TP=%s SL=%s", symbol, take_profit, stop_loss)
        return True

    def close_position(self, symbol: str) -> OrderResult:
        """Close an open position at market."""
        matches = [p for p in self.get_positions() if p.symbol == symbol]
        if not matches:
            return OrderResult(success=False, symbol=symbol, error="no open position")

        position = matches[0]
        return self.place_market_order(
            symbol=symbol,
            side=position.side,
            quantity=position.quantity,
            expected_price=position.mark_price,
            reduce_only=True,
        )

    def set_leverage(self, symbol: str, leverage: float) -> bool:
        """Set leverage for a symbol. Kept at 1x unless deliberately raised."""
        response = self._call(
            "set_leverage",
            category=CATEGORY,
            symbol=symbol,
            buyLeverage=str(leverage),
            sellLeverage=str(leverage),
        )
        # 110043 means leverage is already at the requested value.
        if response.get("retCode") not in (0, 110043):
            logger.warning("Could not set leverage on %s: %s", symbol, response.get("retMsg"))
            return False
        return True


def _to_bybit_side(side: str, reduce_only: bool) -> str:
    """Map our direction vocabulary onto Bybit's Buy/Sell.

    Closing inverts: exiting a LONG is a Sell.
    """
    upper = side.upper()
    if upper in ("BUY", "SELL"):
        return upper.capitalize()

    if upper == "LONG":
        return "Sell" if reduce_only else "Buy"
    if upper == "SHORT":
        return "Buy" if reduce_only else "Sell"

    raise BrokerError(f"unrecognised side {side!r}")


def _format_quantity(quantity: float, step: float) -> str:
    """Format a quantity with exactly the precision the step implies.

    Bybit rejects orders with more decimal places than the step allows, and a
    float repr like 0.30000000000000004 is a common cause.
    """
    if step >= 1:
        return str(int(quantity))
    decimals = max(0, len(f"{step:.10f}".rstrip("0").split(".")[1]))
    return f"{quantity:.{decimals}f}"


def _optional_float(value: Any) -> float | None:
    """Bybit returns "" or "0" for unset stops; both mean absent."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None
