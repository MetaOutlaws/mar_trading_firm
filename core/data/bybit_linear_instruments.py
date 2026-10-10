"""Bybit linear instrument metadata for the F111 registry.

The public ``/v5/market/instruments-info`` endpoint is the only source. A
symbol that is missing, closed, or returned under a different ticker is
UNAVAILABLE. This module has no alias table: ``SHIB1000USDT`` is not rewritten
to ``1000SHIBUSDT``, and a renamed contract is not substituted.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import httpx

BYBIT_INSTRUMENTS_URL = "https://api.bybit.com/v5/market/instruments-info"
AVAILABLE = "AVAILABLE"
UNAVAILABLE = "UNAVAILABLE"
# Only this exchange status may be traded. PreLaunch, Settling, Closed, and
# anything else stay unavailable with that status as the reason.
TRADING_STATUS = "Trading"


@dataclass(frozen=True)
class InstrumentStatus:
    """One supplied symbol after a verified lookup. ``reason`` is always set."""

    symbol: str
    availability: str
    reason: str
    exchange_status: str | None = None
    tick_size: float | None = None
    qty_step: float | None = None
    min_qty: float | None = None
    min_notional: float | None = None
    returned_symbol: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def classify_instrument_response(
    requested: str,
    payload: dict | None,
    *,
    error: str | None = None,
) -> InstrumentStatus:
    """Turn one instruments-info body into an explicit status.

    ``payload`` is the parsed JSON. ``error`` is set when the HTTP call did
    not produce a usable body. Transport failure is UNAVAILABLE, not a guess
    that the contract trades.
    """
    if error:
        return InstrumentStatus(
            symbol=requested,
            availability=UNAVAILABLE,
            reason=f"instruments-info unreachable: {error}",
        )
    if not isinstance(payload, dict):
        return InstrumentStatus(
            symbol=requested,
            availability=UNAVAILABLE,
            reason="instruments-info unreachable: response was not JSON",
        )
    if int(payload.get("retCode") or 0) != 0:
        message = payload.get("retMsg") or "retCode"
        return InstrumentStatus(
            symbol=requested,
            availability=UNAVAILABLE,
            reason=f"instruments-info rejected the query: {message}",
        )
    rows = (payload.get("result") or {}).get("list") or []
    if not rows:
        return InstrumentStatus(
            symbol=requested,
            availability=UNAVAILABLE,
            reason="not listed on Bybit linear",
        )
    # A query by symbol should return that symbol. If Bybit hands back a
    # different contract, do not trade it under the requested name.
    info = None
    for row in rows:
        if str(row.get("symbol") or "") == requested:
            info = row
            break
    if info is None:
        other = str(rows[0].get("symbol") or "")
        return InstrumentStatus(
            symbol=requested,
            availability=UNAVAILABLE,
            reason=f"symbol mismatch; refusing alias {other or 'unknown'}",
            returned_symbol=other or None,
        )
    status = str(info.get("status") or "")
    price_filter = info.get("priceFilter") or {}
    lot_filter = info.get("lotSizeFilter") or {}
    try:
        tick = float(price_filter.get("tickSize"))
        qty_step = float(lot_filter.get("qtyStep"))
        min_qty = float(lot_filter.get("minOrderQty"))
        min_notional = float(lot_filter.get("minNotionalValue") or 0.0)
    except (TypeError, ValueError):
        return InstrumentStatus(
            symbol=requested,
            availability=UNAVAILABLE,
            reason="instruments-info missing tick, lot, or minimum quantity",
            exchange_status=status or None,
            returned_symbol=requested,
        )
    if status != TRADING_STATUS:
        return InstrumentStatus(
            symbol=requested,
            availability=UNAVAILABLE,
            reason=f"exchange status {status or 'missing'}",
            exchange_status=status or None,
            tick_size=tick,
            qty_step=qty_step,
            min_qty=min_qty,
            min_notional=min_notional,
            returned_symbol=requested,
        )
    return InstrumentStatus(
        symbol=requested,
        availability=AVAILABLE,
        reason=TRADING_STATUS,
        exchange_status=status,
        tick_size=tick,
        qty_step=qty_step,
        min_qty=min_qty,
        min_notional=min_notional,
        returned_symbol=requested,
    )


def fetch_linear_instrument(
    symbol: str,
    *,
    client: httpx.Client | None = None,
    url: str = BYBIT_INSTRUMENTS_URL,
) -> InstrumentStatus:
    """Query one linear symbol. The caller owns ``client`` when it is passed in."""
    owns = client is None
    http = client or httpx.Client(timeout=20.0, headers={"User-Agent": "mar-trading-firm/0.1"})
    try:
        try:
            response = http.get(url, params={"category": "linear", "symbol": symbol})
        except Exception as exc:
            return classify_instrument_response(symbol, None, error=f"{type(exc).__name__}: {exc}")
        if response.status_code != 200:
            return classify_instrument_response(
                symbol, None, error=f"HTTP {response.status_code}"
            )
        try:
            payload = response.json()
        except Exception as exc:
            return classify_instrument_response(symbol, None, error=f"invalid JSON: {exc}")
        return classify_instrument_response(symbol, payload)
    finally:
        if owns:
            http.close()


def fetch_registry(symbols: list[str] | tuple[str, ...], *, client: httpx.Client | None = None) -> list[InstrumentStatus]:
    """One status per supplied symbol, in the given order. No symbol is dropped."""
    owns = client is None
    http = client or httpx.Client(timeout=20.0, headers={"User-Agent": "mar-trading-firm/0.1"})
    try:
        return [fetch_linear_instrument(symbol, client=http) for symbol in symbols]
    finally:
        if owns:
            http.close()
