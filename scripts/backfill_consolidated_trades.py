"""Consolidate DESKTOP history onto the SGP1 book.

SGP1 is the book of record since inception. The input CSV is a merged
ledger of historical trades (the DESKTOP backup) that are missing from
SGP1's ``trades`` table. For each row this command:

* inserts the trade when no SGP1 row has the same backfill key or the
  same symbol, side, entry time, and entry price
* posts one cash-journal close when the journal does not already have
  that close

The October XRP short is the second case: the journal already has the
close, so only the trade row is inserted and cash does not move again.

Pre-F03 rows have no fee split and no funding. The close uses the
recorded ``fees`` total as its exit fee and stores entry fee 0 and
funding 0. Those numbers are not invented and not split.

Dry-run is the default. ``--apply`` writes the SQLite trade (and, when
needed, the SQLite cash event, then the JSON journal), an audit line,
and a timestamped copy of the database. A second apply is a no-op.

Nothing here deletes a row, posts an open or a funding event, or edits
``config/approved_strategies.json``.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select

from config.settings import PROJECT_ROOT, get_settings
from core.db import session_scope
from core.execution.paper_cash import PaperCashStore, replay_events
from core.ledger.models import PaperCashEvent, TradeRecord
from core.ledger.reconcile import (
    close_net,
    load_mode_trades,
    same_entry_identity,
    source_matches_journal_close,
)

# Gulf Standard Time, no daylight saving. Recon stamps are GST; the journal is UTC.
GST = timezone(timedelta(hours=4))
IDENTITY_EPSILON = 1e-4
STARTING_CAPITAL = 10_000.0
AUDIT_NAME = "paper_consolidation_audit.jsonl"


@dataclass
class SourceRow:
    """One historical trade from the merged ledger. Not yet an SGP1 row."""

    source_trade_id: int | None
    source_position_id: int | None
    symbol: str
    side: str
    strategy: str
    exit_reason: str
    entry_time: datetime
    exit_time: datetime
    gross_pnl: float
    fees: float
    entry_fees: float
    exit_fees: float
    funding: float
    net_pnl: float
    quantity: float | None
    entry_price: float | None
    exit_price: float | None
    notional: float | None

    def match_dict(self, quantity: float | None = None) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "side": self.side,
            "net_pnl": self.net_pnl,
            "exit_time": self.exit_time.isoformat(),
            "quantity": self.quantity if quantity is None else quantity,
        }

    def entry_dict(self, entry_price: float | None) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "side": self.side,
            "entry_time": self.entry_time.isoformat(),
            "entry_price": entry_price,
        }


@dataclass
class Plan:
    """A trade insert, plus a journal close when SGP1 does not have one."""

    source: SourceRow
    key: str
    post_close: bool
    quantity: float
    entry_price: float
    exit_price: float
    notional: float
    journal_ref: str | None
    payload: dict[str, Any] | None


@dataclass
class Blocked:
    source: SourceRow
    reason: str


def backfill_key(source: SourceRow) -> str:
    """Stable id. A second run finds this id and does not insert again."""
    if source.source_trade_id is not None:
        return f"backfill-close:trade:{int(source.source_trade_id)}"
    stamp = source.entry_time.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    price = "na" if source.entry_price is None else f"{source.entry_price:.8f}"
    return f"backfill-close:trade:{source.symbol}:{source.side}:{stamp}:{price}"


def journal_fee_fields(source: SourceRow) -> tuple[float, float, float]:
    """Fee, entry fee, and funding stored on a backfill close.

    When the source has no fee split, the whole recorded ``fees`` number
    is the close fee and the entry fee stays 0. Funding is the recorded
    value, which is 0 on pre-F03 trades. Nothing here is estimated.
    """
    if source.entry_fees == 0.0 and source.exit_fees == 0.0:
        return source.fees, 0.0, source.funding
    return source.exit_fees, source.entry_fees, source.funding


def close_payload(
    source: SourceRow,
    key: str,
    quantity: float,
    entry_price: float,
    exit_price: float,
) -> dict[str, Any]:
    fee, entry_fee, funding = journal_fee_fields(source)
    return {
        "kind": "close",
        "event_id": key,
        "symbol": source.symbol,
        "side": source.side,
        "quantity": quantity,
        "fill_price": exit_price,
        "entry_price": entry_price,
        "gross_pnl": source.gross_pnl,
        "fee": fee,
        "entry_fee": entry_fee,
        "funding": funding,
        "backfill": True,
        "source_trade_id": source.source_trade_id,
        "ts": source.exit_time.astimezone(timezone.utc).isoformat(),
    }


def close_cash_delta(payload: dict[str, Any]) -> float:
    """Cash movement of one close. Replay adds gross minus the exit fee."""
    return float(payload.get("gross_pnl") or 0.0) - float(payload.get("fee") or 0.0)


def _blank(value: Any) -> bool:
    return value is None or str(value).strip() == ""


def _num(raw: dict[str, str], *keys: str) -> float | None:
    for key in keys:
        if key not in raw or _blank(raw.get(key)):
            continue
        return float(str(raw[key]).strip())
    return None


def _parse_gst(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z") or "+" in text[10:]:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    else:
        parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=GST)
    return parsed.astimezone(timezone.utc)


def _time_from_row(raw: dict[str, str], *keys: str) -> datetime | None:
    for key in keys:
        if not _blank(raw.get(key)):
            return _parse_gst(str(raw[key]))
    return None


def load_source_rows(path: Path) -> list[SourceRow]:
    """Read the merged ledger. GST columns are converted to UTC."""
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise SystemExit(f"{path} has no header row")
        rows: list[SourceRow] = []
        for raw in reader:
            symbol = str(raw.get("symbol") or "").strip()
            if not symbol or symbol.lower() == "symbol":
                continue
            # A recon file may also list journal-only lines. Those are not trades.
            if str(raw.get("source") or "").strip().lower() == "journal_only":
                continue
            entry_time = _time_from_row(raw, "open_gst", "entry_gst", "entry_time", "open_time")
            exit_time = _time_from_row(raw, "close_gst", "exit_gst", "exit_time", "close_time")
            if entry_time is None or exit_time is None:
                raise SystemExit(f"{symbol} source row is missing open or close time")
            gross = _num(raw, "gross", "gross_pnl")
            entry_fees = _num(raw, "entry_fees", "entry_fee") or 0.0
            exit_fees = _num(raw, "exit_fees", "exit_fee") or 0.0
            funding = _num(raw, "funding") or 0.0
            fees = _num(raw, "fees")
            net = _num(raw, "trades_net", "net_pnl", "net")
            if gross is None:
                raise SystemExit(f"{symbol} source row is missing gross")
            if fees is None:
                fees = entry_fees + exit_fees
            if net is None:
                net = gross - fees - funding
            trade_id = _num(raw, "trade_id", "id")
            position_id = _num(raw, "position_id")
            rows.append(
                SourceRow(
                    source_trade_id=int(trade_id) if trade_id is not None else None,
                    source_position_id=int(position_id) if position_id is not None else None,
                    symbol=symbol,
                    side=str(raw.get("side") or "").strip().upper(),
                    strategy=str(raw.get("strategy") or "").strip(),
                    exit_reason=str(raw.get("exit_reason") or "").strip(),
                    entry_time=entry_time,
                    exit_time=exit_time,
                    gross_pnl=gross,
                    fees=fees,
                    entry_fees=entry_fees,
                    exit_fees=exit_fees,
                    funding=funding,
                    net_pnl=net,
                    quantity=_num(raw, "quantity", "qty"),
                    entry_price=_num(raw, "entry_price"),
                    exit_price=_num(raw, "exit_price", "fill_price"),
                    notional=_num(raw, "notional"),
                )
            )
    return rows


def _derive_exit(side: str, entry_price: float, gross: float, quantity: float) -> float:
    """Exit implied by the recorded gross, entry, and size."""
    direction = 1.0 if side == "LONG" else -1.0
    return entry_price + (gross / (quantity * direction))


def _find_trade(
    trades: list[dict[str, Any]],
    key: str,
    source: SourceRow,
    entry_price: float | None,
) -> dict[str, Any] | None:
    for trade in trades:
        if trade.get("cash_event_id") == key:
            return trade
    if entry_price is None:
        return None
    ident = source.entry_dict(entry_price)
    for trade in trades:
        if same_entry_identity(ident, trade):
            return trade
    return None


def _find_close(
    closes: list[dict[str, Any]],
    key: str,
    source: SourceRow,
    claimed: set[str],
) -> dict[str, Any] | None | str:
    """The journal close for this row, ``None`` if there is not one, or ``ambiguous``."""
    for close in closes:
        if close.get("event_id") == key and close["ref"] not in claimed:
            return close
    hits = [
        close
        for close in closes
        if close["ref"] not in claimed
        and source_matches_journal_close(source.match_dict(), close)
    ]
    if not hits:
        return None
    if len(hits) > 1:
        return "ambiguous"
    return hits[0]


def _resolve_prices(
    source: SourceRow,
    close: dict[str, Any] | None,
) -> tuple[float, float, float, float] | str:
    """Size and prices from the CSV, then from a journal close that is already there.

    Entry price and quantity are never guessed. Exit may be the price the
    recorded gross implies once entry and size are known.
    """
    quantity = source.quantity if source.quantity is not None else (
        None if close is None else close.get("quantity")
    )
    entry_price = source.entry_price if source.entry_price is not None else (
        None if close is None else close.get("entry_price")
    )
    exit_price = source.exit_price if source.exit_price is not None else (
        None if close is None else close.get("fill_price")
    )
    if quantity is None or quantity <= 0 or entry_price is None:
        return "missing entry price or quantity; not invented"
    if exit_price is None:
        exit_price = _derive_exit(
            source.side, float(entry_price), source.gross_pnl, float(quantity)
        )
    notional = source.notional
    if notional is None:
        notional = float(quantity) * float(entry_price)
    return float(quantity), float(entry_price), float(exit_price), float(notional)


def plan_book(
    sources: list[SourceRow],
    events: list[dict[str, Any]],
    trades: list[dict[str, Any]],
) -> tuple[list[Plan], list[str], list[Blocked]]:
    """Decide inserts and closes. Does not write."""
    closes = [
        {
            "ref": str(event.get("event_id")) if event.get("event_id") else f"journal:{index}",
            "event_id": str(event["event_id"]) if event.get("event_id") else None,
            "symbol": str(event.get("symbol") or ""),
            "side": str(event.get("side") or "").upper(),
            "quantity": event.get("quantity"),
            "ts": event.get("ts"),
            "net": close_net(event),
            "entry_price": event.get("entry_price"),
            "fill_price": event.get("fill_price"),
        }
        for index, event in enumerate(events)
        if str(event.get("kind") or "") == "close"
    ]
    plans: list[Plan] = []
    already: list[str] = []
    blocked: list[Blocked] = []
    claimed: set[str] = set()

    for source in sources:
        key = backfill_key(source)
        prior = _find_trade(trades, key, source, source.entry_price)
        close = _find_close(closes, key, source, claimed)
        if close == "ambiguous":
            blocked.append(Blocked(source, "ambiguous journal close"))
            continue
        if prior is None and isinstance(close, dict):
            prior = _find_trade(trades, key, source, close.get("entry_price"))
        if prior is not None:
            already.append(
                f"source={source.source_trade_id} {source.symbol} {source.side} "
                f"already trade #{prior.get('trade_id')}"
            )
            if isinstance(close, dict):
                claimed.add(str(close["ref"]))
            continue
        resolved = _resolve_prices(source, close if isinstance(close, dict) else None)
        if isinstance(resolved, str):
            blocked.append(Blocked(source, resolved))
            continue
        quantity, entry_price, exit_price, notional = resolved
        post_close = close is None
        payload = None
        journal_ref = None
        if isinstance(close, dict):
            claimed.add(str(close["ref"]))
            journal_ref = str(close["ref"])
        if post_close:
            payload = close_payload(source, key, quantity, entry_price, exit_price)
        plans.append(
            Plan(
                source=source,
                key=key,
                post_close=post_close,
                quantity=quantity,
                entry_price=entry_price,
                exit_price=exit_price,
                notional=notional,
                journal_ref=journal_ref,
                payload=payload,
            )
        )
    return plans, already, blocked


def _sqlite_file() -> Path | None:
    url = get_settings().database_url
    prefix = "sqlite:///"
    if not url.startswith(prefix):
        return None
    path = Path(url[len(prefix) :])
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


def _backup_sqlite() -> Path | None:
    path = _sqlite_file()
    if path is None or not path.exists():
        return None
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest = path.with_name(f"{path.name}.pre-consolidation-{stamp}")
    shutil.copy2(path, dest)
    return dest


def _git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _identity(cash: float, trades_net: float, contributed: float) -> str:
    gap = cash - (STARTING_CAPITAL + trades_net)
    text = f"cash {cash:.6f} == 10000 + {trades_net:.6f}"
    if abs(contributed - STARTING_CAPITAL) > IDENTITY_EPSILON:
        text += f" (journal contributed {contributed:.6f})"
    if abs(gap) <= IDENTITY_EPSILON:
        return text + " -> holds"
    return text + f" -> gap {gap:.6f}"


def _insert(plan: Plan, mode: str) -> int:
    """Insert the trade and, when requested, the SQLite cash event. No JSON yet."""
    source = plan.source
    return_pct = (source.net_pnl / plan.notional * 100.0) if plan.notional else 0.0
    with session_scope() as session:
        existing = session.scalar(select(TradeRecord).where(TradeRecord.cash_event_id == plan.key))
        if existing is None:
            trade = TradeRecord(
                position_id=None,
                cash_event_id=plan.key,
                symbol=source.symbol,
                side=source.side,
                mode=mode,
                strategy=source.strategy,
                quantity=plan.quantity,
                notional=plan.notional,
                entry_price=plan.entry_price,
                exit_price=plan.exit_price,
                entry_time=source.entry_time,
                exit_time=source.exit_time,
                gross_pnl=source.gross_pnl,
                fees=source.fees,
                entry_fees=source.entry_fees,
                exit_fees=source.exit_fees,
                funding=source.funding,
                net_pnl=source.net_pnl,
                return_pct=return_pct,
                exit_reason=source.exit_reason,
                entry_indicators={
                    "backfill": True,
                    "source_trade_id": source.source_trade_id,
                    "source_position_id": source.source_position_id,
                    "journal_ref": plan.journal_ref,
                    "posted_cash": plan.post_close,
                    "entry_key": {
                        "symbol": source.symbol,
                        "side": source.side,
                        "entry_time": source.entry_time.isoformat(),
                        "entry_price": plan.entry_price,
                    },
                    "note": (
                        "Consolidated from the DESKTOP ledger. "
                        "Cash was posted only when the journal had no close."
                    ),
                },
            )
            session.add(trade)
            session.flush()
            trade_id = int(trade.id)
        else:
            trade_id = int(existing.id)
        if plan.post_close and plan.payload is not None:
            event = session.scalar(
                select(PaperCashEvent).where(PaperCashEvent.event_id == plan.key)
            )
            if event is None:
                session.add(
                    PaperCashEvent(
                        event_id=plan.key,
                        kind="close",
                        mode=mode,
                        symbol=source.symbol,
                        position_id=None,
                        payload=plan.payload,
                    )
                )
        return trade_id


def _append_json(journal: Path, plans: list[Plan]) -> int:
    """Append close payloads that are not already in the JSON journal."""
    store = PaperCashStore(journal)
    before = {str(event.get("event_id")) for event in store.events() if event.get("event_id")}
    written = 0
    for plan in plans:
        if not plan.post_close or plan.payload is None:
            continue
        if plan.key in before:
            continue
        store.record(dict(plan.payload))
        before.add(plan.key)
        written += 1
    return written


def _append_audit(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def _print_report(
    *,
    mode_label: str,
    operator: str,
    git_sha: str,
    source: Path,
    cash_before: float,
    cash_after: float,
    contributed: float,
    count_before: int,
    count_after: int,
    nets_before: float,
    nets_after: float,
    plans: list[Plan],
    already: list[str],
    blocked: list[Blocked],
    posted_ids: list[int],
    posted_closes: int,
) -> None:
    print(f"mode: {mode_label}")
    print(f"operator: {operator}")
    print(f"git_sha: {git_sha}")
    print(f"source: {source}")
    print(f"trade_count_before: {count_before}")
    print(f"trade_count_after: {count_after}")
    print(f"trades_net_before: {nets_before:.6f}")
    print(f"trades_net_after: {nets_after:.6f}")
    print(f"cash_before: {cash_before:.6f}")
    print(f"cash_after: {cash_after:.6f}")
    print(f"contributed: {contributed:.6f}")
    print(f"identity_before: {_identity(cash_before, nets_before, contributed)}")
    print(f"identity_after: {_identity(cash_after, nets_after, contributed)}")
    print(f"planned_trades: {len(plans)}")
    print(f"planned_closes: {sum(1 for plan in plans if plan.post_close)}")
    for plan in plans:
        delta = close_cash_delta(plan.payload) if plan.payload is not None else 0.0
        action = "insert+close" if plan.post_close else "insert"
        print(
            f"  {action} source={plan.source.source_trade_id} {plan.source.symbol} "
            f"{plan.source.side} net={plan.source.net_pnl:.6f} "
            f"cash_delta={delta:.6f} key={plan.key}"
        )
    print(f"already: {len(already)}")
    for line in already:
        print(f"  {line}")
    print(f"blocked: {len(blocked)}")
    for item in blocked:
        print(
            f"  source={item.source.source_trade_id} {item.source.symbol} "
            f"{item.source.side} {item.reason}"
        )
    print(f"posted_trades: {len(posted_ids)}")
    print(f"posted_closes: {posted_closes}")
    if posted_ids:
        print("posted_trade_ids: " + ",".join(str(item) for item in posted_ids))


def run(
    *,
    source: Path,
    journal: Path,
    mode: str,
    operator: str,
    apply: bool,
    audit_path: Path,
) -> int:
    if not source.exists():
        print(f"source file not found: {source}", file=sys.stderr)
        return 1
    if not journal.exists():
        print(f"journal not found: {journal}", file=sys.stderr)
        return 1

    sources = load_source_rows(source)
    events = PaperCashStore(journal).events()
    state = replay_events(events)
    trades = load_mode_trades(mode)
    plans, already, blocked = plan_book(sources, events, trades)

    count_before = len(trades)
    nets_before = sum(float(trade["net_pnl"]) for trade in trades)
    planned_net = sum(plan.source.net_pnl for plan in plans)
    planned_cash = sum(close_cash_delta(plan.payload) for plan in plans if plan.payload)
    count_after = count_before + len(plans)
    nets_after = nets_before + planned_net
    cash_after = state.cash + planned_cash
    git_sha = _git_sha()
    posted_ids: list[int] = []
    posted_closes = 0

    # A blocked row is missing a price or size we will not invent.
    # Applying the rest would leave the consolidation half-done.
    if apply and not blocked:
        if plans:
            backup = _backup_sqlite()
            if backup is not None:
                print(f"sqlite_backup: {backup}")
            for plan in plans:
                posted_ids.append(_insert(plan, mode))
            posted_closes = _append_json(journal, plans)
            refreshed = load_mode_trades(mode)
            count_after = len(refreshed)
            nets_after = sum(float(trade["net_pnl"]) for trade in refreshed)
            cash_after = replay_events(PaperCashStore(journal).events()).cash
        _append_audit(
            audit_path,
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "operator": operator,
                "git_sha": git_sha,
                "source": str(source),
                "posted_trade_ids": posted_ids,
                "keys": [plan.key for plan in plans],
                "posted_closes": posted_closes,
                "trade_count_before": count_before,
                "trade_count_after": count_after,
                "trades_net_before": nets_before,
                "trades_net_after": nets_after,
                "cash_before": state.cash,
                "cash_after": cash_after,
                "contributed": state.contributed_capital,
            },
        )

    _print_report(
        mode_label="apply" if apply and not blocked else ("apply-refused" if apply else "dry-run"),
        operator=operator,
        git_sha=git_sha,
        source=source,
        cash_before=state.cash,
        cash_after=cash_after if not (apply and blocked) else state.cash,
        contributed=state.contributed_capital,
        count_before=count_before,
        count_after=count_after if not (apply and blocked) else count_before,
        nets_before=nets_before,
        nets_after=nets_after if not (apply and blocked) else nets_before,
        plans=plans,
        already=already,
        blocked=blocked,
        posted_ids=posted_ids,
        posted_closes=posted_closes,
    )
    if apply and not blocked:
        print(f"audit: {audit_path}")
    if apply and blocked:
        print("apply refused: blocked rows would be skipped", file=sys.stderr)
        return 2
    if blocked and not apply:
        return 2
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path, help="Merged ledger CSV")
    parser.add_argument("--journal", type=Path, default=None, help="Paper cash JSON")
    parser.add_argument("--mode", default="paper")
    parser.add_argument("--operator", default=os.environ.get("USER") or "unknown")
    parser.add_argument("--audit", type=Path, default=None)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write trades and any missing closes. Without this flag, only print.",
    )
    args = parser.parse_args(argv)
    from core.execution.paper_cash import PAPER_CASH_PATH

    journal = args.journal or PAPER_CASH_PATH
    audit = args.audit or (PROJECT_ROOT / "data" / AUDIT_NAME)
    return run(
        source=args.source,
        journal=journal,
        mode=args.mode,
        operator=args.operator,
        apply=args.apply,
        audit_path=audit,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    raise SystemExit(main())
