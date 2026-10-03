"""Commit a paper close and its trade row in one SQLite transaction.

The cash journal used to be a JSON rename, and the trade insert was a later
SQLite commit. A crash between them left the close in the journal and no
``trades`` row. JSON and SQLite cannot share a transaction, so the durable
close is this SQLite commit. The JSON file is updated only afterwards, and
a repeated ``event_id`` does not debit cash or insert another trade.

Nothing here rewrites existing snapshots, historical trades, cash balances,
or approval files. The October journal close is not backfilled.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from sqlalchemy import select

from config.settings import PROJECT_ROOT, get_settings
from core.db import session_scope
from core.ledger.models import PaperCashEvent, Position, PositionStatus, TradeRecord
from core.ledger.store import Ledger

logger = logging.getLogger(__name__)


class CloseSettlementError(RuntimeError):
    """The close was refused. The transaction rolls back, so cash is unchanged."""


@dataclass(frozen=True)
class SettleResult:
    """What the committed close looks like. ``already`` means this was a replay."""

    already: bool
    payload: dict[str, Any]
    trade_id: int | None


def paper_close_event_id(
    *,
    position_id: int,
    symbol: str,
    reason: str,
    quantity: float,
    fill_price: float,
) -> str:
    """Stable identity for one close. A retry of the same fill reuses it."""
    return (
        f"paper-close:{int(position_id)}:{symbol}:{reason}:"
        f"{float(quantity):.8f}:{float(fill_price):.8f}"
    )


def _sqlite_path() -> Path | None:
    """SQLite file from settings, without creating it."""
    url = get_settings().database_url
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        return None
    raw = url[len(prefix) :]
    path = Path(raw)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


def load_durable_close_payloads() -> list[dict[str, Any]]:
    """Committed close payloads. Empty when the database or table is absent.

    Does not create a database and does not write the JSON journal.
    """
    path = _sqlite_path()
    if path is not None and not path.exists():
        return []
    try:
        from sqlalchemy import inspect

        from core.db import get_engine

        engine = get_engine()
        if "paper_cash_events" not in set(inspect(engine).get_table_names()):
            return []
        with session_scope() as session:
            rows = session.scalars(select(PaperCashEvent).order_by(PaperCashEvent.id)).all()
            payloads: list[dict[str, Any]] = []
            for row in rows:
                if isinstance(row.payload, dict) and row.payload.get("event_id"):
                    payloads.append(dict(row.payload))
            return payloads
    except Exception:
        logger.warning("Could not read durable paper cash events", exc_info=True)
        return []


def find_durable_close_payload(
    *,
    symbol: str,
    quantity: float,
    entry_price: float,
) -> dict[str, Any] | None:
    """Close payload that matches a still-open broker row, if one was committed.

    Match is symbol, quantity, and entry price. A different open position on
    the same symbol is not treated as this close.
    """
    for payload in reversed(load_durable_close_payloads()):
        if str(payload.get("symbol") or "") != symbol:
            continue
        if str(payload.get("kind") or "close") != "close":
            continue
        try:
            same_qty = abs(float(payload.get("quantity") or 0.0) - float(quantity)) <= 1e-6
            same_entry = abs(float(payload.get("entry_price") or 0.0) - float(entry_price)) <= 1e-6
        except (TypeError, ValueError):
            continue
        if same_qty and same_entry:
            return payload
    return None


def settle_paper_close(
    *,
    ledger: Ledger,
    event_id: str,
    payload: dict[str, Any],
    position_id: int,
    exit_price: float,
    expected_exit_price: float,
    exit_reason: str,
    entry_fees: float,
    exit_fees: float,
    funding: float,
    before_commit: Callable[[], None] | None = None,
) -> SettleResult:
    """Insert the cash event and the closed trade, then commit both.

    ``before_commit`` runs inside the transaction so a crash test can roll
    both writes back. A second call with the same ``event_id`` returns the
    original payload and does not insert again.
    """
    body = dict(payload)
    body["event_id"] = event_id
    body.setdefault("kind", "close")

    with session_scope() as session:
        existing = session.scalar(
            select(PaperCashEvent).where(PaperCashEvent.event_id == event_id)
        )
        if existing is not None:
            trade_id = session.scalar(
                select(TradeRecord.id).where(TradeRecord.cash_event_id == event_id)
            )
            return SettleResult(
                already=True,
                payload=dict(existing.payload or body),
                trade_id=int(trade_id) if trade_id is not None else None,
            )

        position = session.get(Position, position_id)
        if position is None or position.status != PositionStatus.OPEN.value:
            prior = session.scalars(
                select(PaperCashEvent)
                .where(PaperCashEvent.position_id == position_id)
                .order_by(PaperCashEvent.id.desc())
            ).first()
            if prior is not None:
                trade_id = session.scalar(
                    select(TradeRecord.id).where(TradeRecord.cash_event_id == prior.event_id)
                )
                return SettleResult(
                    already=True,
                    payload=dict(prior.payload or {}),
                    trade_id=int(trade_id) if trade_id is not None else None,
                )
            raise CloseSettlementError(
                f"position {position_id} is not open; refusing a cash close without a trade"
            )

        session.add(
            PaperCashEvent(
                event_id=event_id,
                kind="close",
                mode=ledger.mode,
                symbol=str(body.get("symbol") or position.symbol),
                position_id=position_id,
                payload=body,
            )
        )
        trade = ledger._close_in_session(
            session,
            position_id=position_id,
            exit_price=exit_price,
            expected_exit_price=expected_exit_price,
            exit_reason=exit_reason,
            entry_fees=entry_fees,
            exit_fees=exit_fees,
            funding=funding,
            cash_event_id=event_id,
        )
        if trade is None:
            raise CloseSettlementError(
                f"position {position_id} did not produce a trade; cash event rolled back"
            )
        if before_commit is not None:
            before_commit()
        return SettleResult(already=False, payload=body, trade_id=int(trade.id))
