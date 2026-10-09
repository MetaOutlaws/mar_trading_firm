"""Live paper-book read. Six labels, kept separate.

Equity is cash plus marked unrealised P&L. It is not contributed capital
plus a single "realised" figure. Closed realised P&L is only the net of
round trips that have already closed. Open entry fees and funding still on
open positions have already moved cash and are not inside that net.

This module only reads. It does not update equity snapshots, trades,
positions, cash balances, or approval files, and it does not insert the
historical October close. The live book names both unmatched directions
(a trade with no journal close, a journal close with no trade) so the
dashboard banner can say which rows disagree.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import func, select

from core.db import session_scope
from core.execution.paper_cash import merge_cash_events, replay_events
from core.ledger.models import TradeRecord

# Shown on the live read so a client cannot collapse these into one P&L.
BOOK_DEFINITIONS: dict[str, str] = {
    "contributed_capital": (
        "External deposits and withdrawals. Not trading P&L and not a "
        "reset of an earlier epoch."
    ),
    "cash": (
        "Journal cash: contributed capital, plus closed gross P&L, minus "
        "every entry and exit fee, plus every funding cash effect."
    ),
    "closed_realised_pnl": (
        "Net P&L of closed round trips only: gross minus entry fee, exit "
        "fee, and funding on those closes. Not equity minus capital."
    ),
    "open_entry_costs": (
        "Entry fees still sitting on open positions. Cash has already paid "
        "them. They are not inside closed realised P&L."
    ),
    "accrued_funding": (
        "Sum of every funding journal amount, including funding still on "
        "open positions. Positive means the account paid; a credit is negative. "
        "Closed-position funding alone is not this figure."
    ),
    "marked_unrealised_pnl": (
        "Open price P&L at marks: (mark - entry) times quantity, signed by "
        "side. Equity equals cash plus this when every open position has a mark."
    ),
}


def _empty_book(*, trades_net_pnl: float | None = None) -> dict[str, Any]:
    """No cash journal. Do not invent capital or call equity minus capital realised."""
    return {
        "journal_present": False,
        "contributed_capital": None,
        "cash": None,
        "closed_realised_pnl": None,
        "open_entry_costs": None,
        "accrued_funding": None,
        "open_funding": None,
        "closed_funding": None,
        "marked_unrealised_pnl": None,
        "equity": None,
        "marks_complete": False,
        "unmarked_symbols": [],
        "equity_identity": "cash_plus_marked_unrealised",
        "cash_bridge": None,
        "trades_net_pnl": trades_net_pnl,
        "definitions": dict(BOOK_DEFINITIONS),
    }


def _position_unrealised(side: str, quantity: float, entry_price: float, mark: float) -> float:
    direction = 1.0 if str(side).upper() == "LONG" else -1.0
    return (float(mark) - float(entry_price)) * float(quantity) * direction


def book_statement(
    events: list[dict[str, Any]],
    positions: list[Any],
    marks: dict[str, float | None],
    *,
    trades_net_pnl: float | None = None,
) -> dict[str, Any]:
    """Split the live book. ``events`` are the cash journal, oldest first.

    ``positions`` need ``symbol``, ``side``, ``quantity``, and ``entry_price``.
    A missing mark is left blank for that symbol. Equity is published only
    when every open position has a mark, because equity is cash plus marks.

    Cash is this replay. It is not a sum of rows in ``paper_cash_events``.
    That table records commits; a payload without an event id is not cash.
    """
    if not events:
        return _empty_book(trades_net_pnl=trades_net_pnl)

    state = replay_events(events)
    open_funding = float(sum(state.open_funding.values()))
    open_entry_costs = float(sum(state.open_entry_fees.values()))
    unmarked: list[str] = []
    known_unrealised = 0.0
    known_marks = 0

    for position in positions:
        symbol = str(getattr(position, "symbol", "") or "")
        mark = marks.get(symbol)
        if mark is None:
            if symbol:
                unmarked.append(symbol)
            continue
        known_marks += 1
        known_unrealised += _position_unrealised(
            str(getattr(position, "side", "LONG")),
            float(getattr(position, "quantity", 0.0) or 0.0),
            float(getattr(position, "entry_price", 0.0) or 0.0),
            float(mark),
        )

    if not positions:
        marked: float | None = 0.0
        marks_complete = True
    elif unmarked and known_marks == 0:
        marked = None
        marks_complete = False
    else:
        marked = known_unrealised
        marks_complete = not unmarked

    equity = (state.cash + marked) if marks_complete and marked is not None else None
    cash_bridge = (
        state.contributed_capital
        + state.realised_pnl
        - open_entry_costs
        - open_funding
    )
    return {
        "journal_present": True,
        "contributed_capital": state.contributed_capital,
        "cash": state.cash,
        "closed_realised_pnl": state.realised_pnl,
        "open_entry_costs": open_entry_costs,
        "accrued_funding": state.accrued_funding,
        "open_funding": open_funding,
        "closed_funding": state.total_funding,
        "marked_unrealised_pnl": marked,
        "equity": equity,
        "marks_complete": marks_complete,
        "unmarked_symbols": unmarked,
        "equity_identity": "cash_plus_marked_unrealised",
        "cash_bridge": cash_bridge,
        "trades_net_pnl": trades_net_pnl,
        "definitions": dict(BOOK_DEFINITIONS),
    }


def _trades_net(mode: str) -> float:
    with session_scope() as session:
        total = session.scalar(
            select(func.coalesce(func.sum(TradeRecord.net_pnl), 0.0)).where(
                TradeRecord.mode == mode
            )
        )
    return float(total or 0.0)


def load_journal_events() -> list[dict[str, Any]]:
    """JSON journal plus durable closes not yet in that file. Read-only.

    The path is read from ``paper_cash`` at call time so a test can point the
    live read at a throwaway journal without touching production cash.
    """
    from core.execution import paper_cash
    from core.execution.paper_settle import load_durable_close_payloads

    events: list[dict[str, Any]] = []
    path = paper_cash.PAPER_CASH_PATH
    if path.exists():
        events = paper_cash.PaperCashStore(path).events()
    return merge_cash_events(events, load_durable_close_payloads())


def live_book_statement(
    mode: str,
    positions: list[Any],
    marks: dict[str, float | None],
) -> dict[str, Any]:
    """The dashboard/API book. Does not read equity_snapshot.realised_pnl.

    ``reconcile`` lists trade ids that have no journal close and journal
    closes that have no trade, with the amount on each row. It does not
    insert or delete either side.
    """
    from core.ledger.reconcile import load_mode_trades, reconcile_closes

    events = load_journal_events()
    book = book_statement(
        events,
        positions,
        marks,
        trades_net_pnl=_trades_net(mode),
    )
    book["reconcile"] = reconcile_closes(events, load_mode_trades(mode))
    return book
