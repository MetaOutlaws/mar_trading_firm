"""Live paper-book read. Six labels, kept separate.

Equity is cash plus marked unrealised P&L. It is not contributed capital
plus a single "realised" figure. Closed realised P&L is only the net of
round trips that have already closed. Open entry fees and funding still on
open positions have already moved cash and are not inside that net.

This module only reads. It does not update equity snapshots, trades,
positions, cash balances, or approval files, and it does not insert the
historical October close.
"""

from __future__ import annotations

import hashlib
import threading
from pathlib import Path
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


# ``/api/risk`` builds the live statement on every desk poll. The journal
# parse is kept until the file or the sqlite sidecar changes. A matching
# sha256 after a touch does not parse again. This is the display read;
# ``PaperCashStore.record`` still writes the file the engine uses.
_JOURNAL_LOCK = threading.Lock()
_JOURNAL_CACHE: dict[str, Any] = {"token": None, "digest": "", "events": None}


def clear_journal_cache() -> None:
    """Drop the cached cash journal. Tests use this after a path swap."""
    with _JOURNAL_LOCK:
        _JOURNAL_CACHE["token"] = None
        _JOURNAL_CACHE["digest"] = ""
        _JOURNAL_CACHE["events"] = None


def _stat_token(path: Path) -> tuple[str, int, int, int] | None:
    try:
        st = path.stat()
    except OSError:
        return None
    return (str(path), int(st.st_ino), int(st.st_mtime_ns), int(st.st_size))


def load_journal_events() -> list[dict[str, Any]]:
    """JSON journal plus durable closes not yet in that file. Read-only.

    The path is read from ``paper_cash`` at call time so a test can point the
    live read at a throwaway journal without touching production cash. A poll
    that sees the same inode, mtime, and size does not parse the file. A
    changed mtime hashes the bytes and reuses the parsed events when the
    sha256 is unchanged.
    """
    from core.execution import paper_cash
    from core.execution.paper_settle import _sqlite_path, load_durable_close_payloads

    path = Path(paper_cash.PAPER_CASH_PATH)
    db = _sqlite_path()
    db_path = Path(db) if db is not None else None
    wal = Path(str(db_path) + "-wal") if db_path is not None else None
    token = (
        _stat_token(path),
        _stat_token(db_path) if db_path is not None else None,
        _stat_token(wal) if wal is not None else None,
    )
    with _JOURNAL_LOCK:
        cached = _JOURNAL_CACHE["events"]
        if _JOURNAL_CACHE["token"] == token and isinstance(cached, list):
            return list(cached)
    digest = ""
    raw: bytes | None = None
    if path.is_file():
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
    with _JOURNAL_LOCK:
        cached = _JOURNAL_CACHE["events"]
        # Same bytes and the same database token: a touch of the JSON file
        # does not rebuild the event list. A database change still misses.
        if (
            isinstance(cached, list)
            and _JOURNAL_CACHE["digest"] == digest
            and _JOURNAL_CACHE["token"] is not None
            and _JOURNAL_CACHE["token"][1:] == token[1:]
        ):
            _JOURNAL_CACHE["token"] = token
            return list(cached)
    events: list[dict[str, Any]] = []
    if raw is not None:
        # PaperCashStore parses the path itself. The bytes were only hashed
        # here; a content change falls through to that one parse.
        events = paper_cash.PaperCashStore(path).events()
    merged = merge_cash_events(events, load_durable_close_payloads())
    with _JOURNAL_LOCK:
        _JOURNAL_CACHE["token"] = token
        _JOURNAL_CACHE["digest"] = digest
        _JOURNAL_CACHE["events"] = merged
    return list(merged)


def live_book_statement(
    mode: str,
    positions: list[Any],
    marks: dict[str, float | None],
) -> dict[str, Any]:
    """The dashboard/API book. Does not read equity_snapshot.realised_pnl."""
    return book_statement(
        load_journal_events(),
        positions,
        marks,
        trades_net_pnl=_trades_net(mode),
    )
