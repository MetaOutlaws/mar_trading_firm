"""
Paper cash / event ledger (F02).

PaperBroker keeps cash, realised P&L and fees in RAM. The SQLite position
ledger already survives a restart, but cash does not: ``build_engine``
constructs a fresh broker at starting equity and ``hydrate`` only restores
open rows. Closed-trade P&L and entry fees on still-open positions then
vanish, so cash / equity / exposure jump while the book looks unchanged.

What is persisted (``data/paper_cash.json``)
-------------------------------------------
* ``events`` — append-only cash journal. Kinds:
    - ``capital``: external contribution or withdrawal. Not P&L.
    - ``open``:   entry fill; cash falls by the entry fee only (paper does
                  not reserve notional).
    - ``funding``: 8h funding step (F03). ``amount`` positive means paid;
                  cash falls by ``amount``. Not realised until close.
    - ``close``:  exit fill; cash changes by ``gross_pnl - fee`` (exit fee).
                  Realised P&L also subtracts ``entry_fee`` and ``funding``
                  when those fields are present (F03).
* Snapshot fields (``contributed_capital``, ``cash``, ``realised_pnl``,
  ``total_fees``, ``total_funding``) are derived from a replay.

What is *not* persisted here
----------------------------
Open positions stay in the SQLite ledger. Marks are not stored; equity and
exposure at a restart are recomputed from restored cash + the same marks.

Restore order
-------------
1. Replay this event ledger from an empty book (capital first, then fills).
   That restores cash, realised P&L, fees and contributed capital, including
   entry fees and funding still sitting on open positions.
2. Overlay open positions from SQLite. Position restore must not touch cash.

Do not reconstruct cash from ``trades`` rows alone. Replay this journal.
After F03, ``TradeRecord`` does include entry fees and funding, so a
closed book can also reconcile cash to sum(net_pnl).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config.settings import PROJECT_ROOT

logger = logging.getLogger(__name__)

#: Runtime cash journal. Back up alongside ``data/firm.db``.
PAPER_CASH_PATH = PROJECT_ROOT / "data" / "paper_cash.json"

LEDGER_VERSION = 1
KIND_CAPITAL = "capital"
KIND_OPEN = "open"
KIND_CLOSE = "close"
KIND_FUNDING = "funding"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class PaperCashState:
    """Balances produced by replaying the cash event ledger."""

    contributed_capital: float = 0.0
    cash: float = 0.0
    realised_pnl: float = 0.0
    total_fees: float = 0.0
    total_funding: float = 0.0
    #: Funding already taken from cash for symbols still open.
    open_funding: dict[str, float] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)


def replay_events(events: list[dict[str, Any]]) -> PaperCashState:
    """Apply every cash event from a zero book.

    ``funding`` events (F03) debit cash during a hold. Close events keep the
    F02 cash formula (``gross - exit fee``) and, when present, fold
    ``entry_fee`` + ``funding`` into realised P&L so a flat book satisfies
    cash - contributed == realised_pnl. Unknown kinds are still skipped.
    """
    contributed = 0.0
    cash = 0.0
    realised = 0.0
    fees = 0.0
    total_funding = 0.0
    open_funding: dict[str, float] = {}

    for event in events:
        kind = str(event.get("kind") or "")
        symbol = str(event.get("symbol") or "")
        if kind == KIND_CAPITAL:
            amount = float(event.get("amount") or 0.0)
            contributed += amount
            cash += amount
        elif kind == KIND_OPEN:
            fee = float(event.get("fee") or 0.0)
            cash -= fee
            fees += fee
        elif kind == KIND_FUNDING:
            amount = float(event.get("amount") or 0.0)
            cash -= amount
            if symbol:
                open_funding[symbol] = open_funding.get(symbol, 0.0) + amount
        elif kind == KIND_CLOSE:
            fee = float(event.get("fee") or 0.0)
            gross = float(event.get("gross_pnl") or 0.0)
            entry_fee = float(event.get("entry_fee") or 0.0)
            funding = float(event.get("funding") or 0.0)
            cash += gross - fee
            realised += gross - fee - entry_fee - funding
            fees += fee
            total_funding += funding
            if symbol:
                remaining = open_funding.get(symbol, 0.0) - funding
                if abs(remaining) < 1e-12:
                    open_funding.pop(symbol, None)
                else:
                    open_funding[symbol] = remaining
        else:
            logger.warning("Skipping unknown paper cash event kind %r", kind)

    return PaperCashState(
        contributed_capital=contributed,
        cash=cash,
        realised_pnl=realised,
        total_fees=fees,
        total_funding=total_funding,
        open_funding=open_funding,
        events=list(events),
    )


class PaperCashStore:
    """Append-only JSON cash journal with atomic replace."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or PAPER_CASH_PATH
        self._events: list[dict[str, Any]] = []
        self._load()

    def has_events(self) -> bool:
        return bool(self._events)

    def events(self) -> list[dict[str, Any]]:
        return list(self._events)

    def replay(self) -> PaperCashState:
        return replay_events(self._events)

    def record(self, event: dict[str, Any]) -> None:
        payload = dict(event)
        payload.setdefault("ts", _utcnow_iso())
        self._events.append(payload)
        self._persist()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"paper cash ledger unreadable at {self.path}: {exc}") from exc
        events = raw.get("events") if isinstance(raw, dict) else None
        if not isinstance(events, list):
            raise RuntimeError(f"paper cash ledger at {self.path} has no events array")
        self._events = [e for e in events if isinstance(e, dict)]

    def _persist(self) -> None:
        state = self.replay()
        payload = {
            "version": LEDGER_VERSION,
            "contributed_capital": state.contributed_capital,
            "cash": state.cash,
            "realised_pnl": state.realised_pnl,
            "total_fees": state.total_fees,
            "total_funding": state.total_funding,
            "events": self._events,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Write-then-rename so a crash cannot leave a truncated journal.
        temp = self.path.with_suffix(self.path.suffix + ".tmp")
        temp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temp.replace(self.path)
