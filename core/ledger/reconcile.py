"""Match paper trades to cash-journal closes. Read-only.

Two books can disagree in either direction:

* a ``trades`` row whose close never landed in the journal
* a journal close with no ``trades`` row (the SGP1 orphan copied from the
  DESKTOP journal)

Matching does not insert, delete, or rewrite either side. A close is the
same economic event when it shares ``event_id`` / ``cash_event_id``, or,
for a legacy journal row that has no id, when symbol, side, quantity, and
exit time (within 60 seconds) agree.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from core.db import session_scope
from core.ledger.models import TradeRecord

# Legacy JSON closes were stamped a few seconds after the trade's minute.
MATCH_WINDOW_SECONDS = 60.0
QTY_TOLERANCE = 1e-6


def close_net(event: dict[str, Any]) -> float:
    """Realised contribution of one close. Same formula as the cash replay.

    ``fee`` is the exit fee. Entry fee and funding are included when the
    event carries them, which is how a flat book's close nets line up with
    ``TradeRecord.net_pnl``. Funding is not added a second time.
    """
    gross = float(event.get("gross_pnl") or 0.0)
    fee = float(event.get("fee") or 0.0)
    entry_fee = float(event.get("entry_fee") or 0.0)
    funding = float(event.get("funding") or 0.0)
    return gross - fee - entry_fee - funding


def parse_time(value: Any) -> datetime | None:
    """UTC timestamp from an ISO string or a datetime. Naive values are UTC."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _field(row: Any, key: str, default: Any = None) -> Any:
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


def _quantity(value: Any) -> float | None:
    """Positive quantity, or None when the row does not know its size."""
    if value is None or value == "":
        return None
    try:
        qty = float(value)
    except (TypeError, ValueError):
        return None
    if qty == 0.0:
        return None
    return qty


def _trade_view(row: Any) -> dict[str, Any]:
    exit_time = parse_time(_field(row, "exit_time"))
    entry_time = parse_time(_field(row, "entry_time"))
    trade_id = _field(row, "trade_id", _field(row, "id"))
    return {
        "trade_id": int(trade_id) if trade_id is not None else None,
        "cash_event_id": _field(row, "cash_event_id") or None,
        "symbol": str(_field(row, "symbol") or ""),
        "side": str(_field(row, "side") or "").upper(),
        "quantity": _quantity(_field(row, "quantity")),
        "entry_time": entry_time.isoformat() if entry_time is not None else None,
        "entry_price": _known_price(_field(row, "entry_price")),
        "exit_time": exit_time.isoformat() if exit_time is not None else None,
        "net_pnl": float(_field(row, "net_pnl") or 0.0),
    }


def _close_view(index: int, event: dict[str, Any]) -> dict[str, Any]:
    event_id = event.get("event_id") or None
    ts = parse_time(event.get("ts"))
    side = str(event.get("side") or "").upper()
    return {
        "ref": str(event_id) if event_id else f"journal:{index}",
        "event_index": index,
        "event_id": str(event_id) if event_id else None,
        "symbol": str(event.get("symbol") or ""),
        "side": side,
        "quantity": _quantity(event.get("quantity")),
        "ts": ts.isoformat() if ts is not None else None,
        "net": close_net(event),
        "entry_price": _optional_float(event.get("entry_price")),
        "fill_price": _optional_float(event.get("fill_price")),
    }


def _known_price(value: Any) -> float | None:
    """A fill price. Zero is treated as unknown so it cannot key a match."""
    price = _optional_float(value)
    if price is None or price == 0.0:
        return None
    return price


def same_entry_price(left: float | None, right: float | None) -> bool:
    """Entry prices name the same fill. Missing on either side does not match."""
    if left is None or right is None:
        return False
    scale = max(abs(left), abs(right), 1.0)
    return abs(left - right) <= max(1e-6, 1e-8 * scale)


def same_entry_identity(left: dict[str, Any], right: dict[str, Any]) -> bool:
    """True when two rows are the same open: symbol, side, entry time, entry price.

    This is how a DESKTOP backup row is recognised as an SGP1 trade that is
    already on the book. A missing price or time does not match.
    """
    if str(left.get("symbol") or "") != str(right.get("symbol") or ""):
        return False
    left_side = str(left.get("side") or "")
    right_side = str(right.get("side") or "")
    if not left_side or not right_side or left_side.upper() != right_side.upper():
        return False
    if not _times_within(left.get("entry_time"), right.get("entry_time")):
        return False
    return same_entry_price(
        _known_price(left.get("entry_price")),
        _known_price(right.get("entry_price")),
    )


def _optional_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _same_qty(left: float | None, right: float | None) -> bool:
    """Quantity agrees. Unknown on either side does not reject the match."""
    if left is None or right is None:
        return True
    return abs(left - right) <= QTY_TOLERANCE


def _same_side(left: str, right: str) -> bool:
    if not left or not right:
        return True
    return left.upper() == right.upper()


def _times_within(left: str | None, right: str | None) -> bool:
    a = parse_time(left)
    b = parse_time(right)
    if a is None or b is None:
        return False
    return abs((a - b).total_seconds()) <= MATCH_WINDOW_SECONDS


# CSV nets are rounded to about 1e-6. A cent is already a different trade.
NET_TOLERANCE = 0.01


def source_matches_journal_close(source: dict[str, Any], close: dict[str, Any]) -> bool:
    """True when a DESKTOP source row is the same close as this journal orphan.

    Symbol, side, net, and exit time must agree. Quantity is required only
    when both sides know it, so a CSV that has no size can still match.
    """
    if str(source.get("symbol") or "") != str(close.get("symbol") or ""):
        return False
    if not _same_side(str(source.get("side") or ""), str(close.get("side") or "")):
        return False
    try:
        source_net = float(source.get("net_pnl"))
        close_net = float(close.get("net"))
    except (TypeError, ValueError):
        return False
    if abs(source_net - close_net) > NET_TOLERANCE:
        return False
    if not _times_within(source.get("exit_time"), close.get("ts")):
        return False
    return _same_qty(_quantity(source.get("quantity")), _quantity(close.get("quantity")))


def _seconds_apart(left: str | None, right: str | None) -> float:
    a = parse_time(left)
    b = parse_time(right)
    if a is None or b is None:
        return MATCH_WINDOW_SECONDS + 1.0
    return abs((a - b).total_seconds())


def _legacy_match(trade: dict[str, Any], close: dict[str, Any]) -> bool:
    """Symbol + side + size + exit time, for a journal close with no event id."""
    if not trade["symbol"] or trade["symbol"] != close["symbol"]:
        return False
    if not _same_side(trade["side"], close["side"]):
        return False
    if not _same_qty(trade["quantity"], close["quantity"]):
        return False
    return _times_within(trade["exit_time"], close["ts"])


def reconcile_closes(
    events: list[dict[str, Any]],
    trades: list[Any],
) -> dict[str, Any]:
    """Name every trade without a journal close, and every close without a trade.

    ``event_id`` wins. Anything left is paired on symbol, side, quantity, and
    exit time within :data:`MATCH_WINDOW_SECONDS`. Each row is used once.
    When two closes are equally close in time, neither is paired: the banner
    should show the ambiguity rather than pick one.
    """
    trade_views = [_trade_view(row) for row in trades]
    close_views = [
        _close_view(index, event)
        for index, event in enumerate(events)
        if str(event.get("kind") or "") == "close"
    ]

    unmatched_trades = list(trade_views)
    unmatched_closes = list(close_views)
    matched = 0

    still_trades: list[dict[str, Any]] = []
    for trade in unmatched_trades:
        event_id = trade["cash_event_id"]
        if not event_id:
            still_trades.append(trade)
            continue
        partner = next(
            (close for close in unmatched_closes if close["event_id"] == str(event_id)),
            None,
        )
        if partner is None:
            still_trades.append(trade)
            continue
        unmatched_closes.remove(partner)
        matched += 1

    leftover_trades: list[dict[str, Any]] = []
    for trade in still_trades:
        candidates = [close for close in unmatched_closes if _legacy_match(trade, close)]
        if not candidates:
            leftover_trades.append(trade)
            continue
        if len(candidates) > 1:
            ranked = sorted(
                candidates,
                key=lambda close: _seconds_apart(close["ts"], trade["exit_time"]),
            )
            gap0 = _seconds_apart(ranked[0]["ts"], trade["exit_time"])
            gap1 = _seconds_apart(ranked[1]["ts"], trade["exit_time"])
            if gap0 == gap1:
                leftover_trades.append(trade)
                continue
            candidates = [ranked[0]]
        unmatched_closes.remove(candidates[0])
        matched += 1

    return {
        "matched": matched,
        "trades_without_journal_close": leftover_trades,
        "journal_closes_without_trade": unmatched_closes,
    }


def load_mode_trades(mode: str) -> list[dict[str, Any]]:
    """Paper (or other mode) trade rows as plain dicts. Does not write."""
    with session_scope() as session:
        rows = session.scalars(select(TradeRecord).where(TradeRecord.mode == mode)).all()
        return [_trade_view(row) for row in rows]
