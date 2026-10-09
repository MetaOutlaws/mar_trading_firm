"""Insert DESKTOP history onto the SGP1 book of record.

The input CSV is the merged backfill ledger (one row per DESKTOP trade).
Each row becomes an SGP1 trade. A cash-journal close and a
``paper_cash_events`` row are written only when the CSV says so. Trade 8,
the October XRP short, is a trade row only: that cash is already in the
SGP1 journal.

Keys are ``backfill-close:desktop:<id>``. A second run is a no-op when that
key is already on the trade, or when symbol, side, entry time (1 second),
and entry price (relative 1e-6) already match. ``position_id`` stays NULL.
Nothing here deletes a row or edits ``config/approved_strategies.json``.

Dry-run is the default. ``--variant B`` is DESKTOP trades 1–8.
``--variant A`` is all 14. Cash on the journal snapshot moves by each
posted ``cash_delta`` (the trade net). The file is written back with the
same indentation it already had.

Cash is not computed by summing ``paper_cash_events``. Those rows are the
commit record. The book reads the journal.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

from config.settings import PROJECT_ROOT, get_settings
from core.db import session_scope
from core.ledger.models import PaperCashEvent, Position, TradeRecord

STARTING_CAPITAL = 10_000.0
IDENTITY_EPSILON = 1e-6
AUDIT_NAME = "paper_consolidation_audit.jsonl"
# Natural-key window. Twins nine minutes apart stay two trades.
ENTRY_WINDOW_SECONDS = 1.0


@dataclass
class InputRow:
    """One DESKTOP trade from the backfill CSV. Fields stay as recorded."""

    backfill_key: str
    variant: str
    desktop_trade_id: int
    add_trade: bool
    add_journal: bool
    add_pce: bool
    existing_journal_ref: str
    symbol: str
    side: str
    mode: str
    strategy: str
    quantity: float
    notional: float
    entry_price: float
    exit_price: float
    entry_time_utc: str
    exit_time_utc: str
    entry_time: datetime
    exit_time: datetime
    gross_pnl: float
    fees: float
    entry_fees: float
    exit_fees: float
    funding: float
    net_pnl: float
    return_pct: float
    exit_reason: str
    entry_slippage_bps: float
    exit_slippage_bps: float
    contributing_agents: list[Any]
    entry_indicators: dict[str, Any]
    cash_delta: float
    source_db_sha256: str


@dataclass
class Planned:
    row: InputRow
    trade_action: str
    journal_action: str
    pce_action: str


@dataclass
class KnownTrade:
    cash_event_id: str | None
    symbol: str
    side: str
    entry_time: datetime
    entry_price: float


def _blank(value: Any) -> bool:
    return value is None or str(value).strip() == ""


def _parse_utc(value: str) -> datetime:
    """CSV stamps are UTC. A trailing Z is accepted; a naive stamp is UTC."""
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _json_cell(value: str, fallback: Any) -> Any:
    if _blank(value):
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def _require(raw: dict[str, str], key: str, symbol: str) -> str:
    if _blank(raw.get(key)):
        raise SystemExit(f"{symbol or 'row'} is missing {key}; not invented")
    return str(raw[key]).strip()


def load_input_rows(path: Path) -> list[InputRow]:
    """Read the backfill CSV. Prices and size are taken from the file."""
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise SystemExit(f"{path} has no header row")
        rows: list[InputRow] = []
        for raw in reader:
            symbol = str(raw.get("symbol") or "").strip()
            if not symbol:
                continue
            trade_id = int(float(_require(raw, "desktop_trade_id", symbol)))
            key = str(raw.get("backfill_key") or "").strip()
            if not key:
                key = f"backfill-close:desktop:{trade_id}"
            entry_stamp = _require(raw, "entry_time_utc", symbol)
            exit_stamp = _require(raw, "exit_time_utc", symbol)
            rows.append(
                InputRow(
                    backfill_key=key,
                    variant=str(raw.get("variant") or "").strip(),
                    desktop_trade_id=trade_id,
                    add_trade=str(raw.get("add_trade_row") or "Y").strip().upper() == "Y",
                    add_journal=str(raw.get("add_journal_close_json") or "").strip().upper() == "Y",
                    add_pce=str(raw.get("add_paper_cash_event") or "").strip().upper() == "Y",
                    existing_journal_ref=str(raw.get("existing_journal_ref") or "").strip(),
                    symbol=symbol,
                    side=str(raw.get("side") or "").strip().upper(),
                    mode=str(raw.get("mode") or "paper").strip() or "paper",
                    strategy=str(raw.get("strategy") or "").strip(),
                    quantity=float(_require(raw, "quantity", symbol)),
                    notional=float(_require(raw, "notional", symbol)),
                    entry_price=float(_require(raw, "entry_price", symbol)),
                    exit_price=float(_require(raw, "exit_price", symbol)),
                    entry_time_utc=entry_stamp,
                    exit_time_utc=exit_stamp,
                    entry_time=_parse_utc(entry_stamp),
                    exit_time=_parse_utc(exit_stamp),
                    gross_pnl=float(_require(raw, "gross_pnl", symbol)),
                    fees=float(_require(raw, "fees", symbol)),
                    entry_fees=float(raw.get("entry_fees") or 0.0),
                    exit_fees=float(raw.get("exit_fees") or 0.0),
                    funding=float(raw.get("funding") or 0.0),
                    net_pnl=float(_require(raw, "net_pnl", symbol)),
                    return_pct=float(raw.get("return_pct") or 0.0),
                    exit_reason=str(raw.get("exit_reason") or "").strip(),
                    entry_slippage_bps=float(raw.get("entry_slippage_bps") or 0.0),
                    exit_slippage_bps=float(raw.get("exit_slippage_bps") or 0.0),
                    contributing_agents=_json_cell(str(raw.get("contributing_agents") or ""), []),
                    entry_indicators=_json_cell(str(raw.get("entry_indicators") or ""), {}),
                    cash_delta=float(raw.get("cash_delta") or 0.0),
                    source_db_sha256=str(raw.get("source_db_sha256") or "").strip(),
                )
            )
    return rows


def select_variant(rows: list[InputRow], variant: str) -> list[InputRow]:
    """B is the pre-fork eight. A is every row in the file, in file order."""
    if variant == "A":
        return list(rows)
    return [row for row in rows if row.variant == "B"]


def _same_price(existing: float, incoming: float) -> bool:
    scale = abs(existing) if existing else 0.0
    return abs(existing - incoming) <= 1e-6 * scale


def _same_entry(known: KnownTrade, row: InputRow) -> bool:
    if known.symbol != row.symbol or known.side != row.side:
        return False
    gap = abs((known.entry_time - row.entry_time).total_seconds())
    if gap > ENTRY_WINDOW_SECONDS:
        return False
    return _same_price(known.entry_price, row.entry_price)


def trade_exists(known: list[KnownTrade], row: InputRow) -> bool:
    """True when this DESKTOP row is already an SGP1 trade.

    The backfill key wins. Otherwise symbol, side, entry time within one
    second, and entry price within one part per million.
    """
    for trade in known:
        if trade.cash_event_id and trade.cash_event_id == row.backfill_key:
            return True
        if _same_entry(trade, row):
            return True
    return False


def _load_known() -> list[KnownTrade]:
    with session_scope() as session:
        rows = session.scalars(select(TradeRecord)).all()
        return [
            KnownTrade(
                cash_event_id=row.cash_event_id,
                symbol=row.symbol,
                side=str(row.side or "").upper(),
                entry_time=row.entry_time,
                entry_price=float(row.entry_price),
            )
            for row in rows
        ]


def _load_pce_ids() -> set[str]:
    with session_scope() as session:
        ids = session.scalars(select(PaperCashEvent.event_id)).all()
        return {str(item) for item in ids if item}


def _book_counts() -> tuple[int, float, int]:
    """Trade count, sum of net, and positions that are not closed."""
    with session_scope() as session:
        count = int(session.scalar(select(func.count(TradeRecord.id))) or 0)
        total = session.scalar(select(func.coalesce(func.sum(TradeRecord.net_pnl), 0.0)))
        net = float(total or 0.0)
        opens = int(
            session.scalar(
                select(func.count(Position.id)).where(Position.status != "closed")
            )
            or 0
        )
    return count, net, opens


def _journal_action(row: InputRow, event_ids: set[str]) -> str:
    if not row.add_journal:
        ref = row.existing_journal_ref or "journal"
        return f"n/a(existing {ref})"
    if row.backfill_key in event_ids:
        return "skip(exists)"
    return "post"


def _pce_action(row: InputRow, pce_ids: set[str]) -> str:
    if not row.add_pce:
        return "n/a"
    if row.backfill_key in pce_ids:
        return "skip(exists)"
    return "insert"


def _close_event(
    row: InputRow,
    *,
    cash_after: float,
    realised: float,
    total_fees: float,
    total_funding: float,
    now: datetime,
) -> dict[str, Any]:
    """One journal close. ``entry_fee`` is 0 because there is no open event.

    ``fee`` is the recorded fee total, not a split we invented. ``funding``
    is the recorded funding. ``cash_after`` is the snapshot after ``cash_delta``.
    """
    return {
        "kind": "close",
        "event_id": row.backfill_key,
        "symbol": row.symbol,
        "side": row.side,
        "quantity": row.quantity,
        "fill_price": row.exit_price,
        "entry_price": row.entry_price,
        "fee": row.fees,
        "entry_fee": 0.0,
        "gross_pnl": row.gross_pnl,
        "funding": row.funding,
        "cash_after": cash_after,
        "realised_pnl": realised,
        "total_fees": total_fees,
        "total_funding": total_funding,
        "ts": now.isoformat(),
        "trade_exit_ts": row.exit_time_utc,
        "backfill": True,
        "source": "DESKTOP",
        "source_trade_id": row.desktop_trade_id,
        "source_db_sha256": row.source_db_sha256,
    }


def _insert_trade(session: Any, row: InputRow) -> None:
    session.add(
        TradeRecord(
            position_id=None,
            cash_event_id=row.backfill_key,
            symbol=row.symbol,
            side=row.side,
            mode=row.mode,
            strategy=row.strategy,
            quantity=row.quantity,
            notional=row.notional,
            entry_price=row.entry_price,
            exit_price=row.exit_price,
            entry_time=row.entry_time,
            exit_time=row.exit_time,
            gross_pnl=row.gross_pnl,
            fees=row.fees,
            entry_fees=row.entry_fees,
            exit_fees=row.exit_fees,
            funding=row.funding,
            net_pnl=row.net_pnl,
            return_pct=row.return_pct,
            exit_reason=row.exit_reason,
            entry_slippage_bps=row.entry_slippage_bps,
            exit_slippage_bps=row.exit_slippage_bps,
            contributing_agents=row.contributing_agents,
            entry_indicators=row.entry_indicators,
        )
    )


def _insert_pce(session: Any, row: InputRow, cash_after: float, now: datetime) -> None:
    """Commit record only. The book does not sum this table to get cash."""
    session.add(
        PaperCashEvent(
            event_id=row.backfill_key,
            kind="close",
            mode=row.mode or "paper",
            symbol=row.symbol,
            position_id=None,
            payload={
                "backfill": True,
                "source_trade_id": row.desktop_trade_id,
                "net": row.net_pnl,
                "cash_after": cash_after,
            },
            recorded_at=now,
        )
    )


def _indent_of(text: str) -> int | None:
    """2-space (or wider) indent, or None when the file is one line."""
    if "\n" not in text:
        return None
    for line in text.splitlines():
        if not line or line.lstrip(" ") == line:
            continue
        return len(line) - len(line.lstrip(" "))
    return 2


def _separators(text: str, indent: int | None) -> tuple[str, str] | None:
    """Keep a compact file's colon spacing. Pretty files use the default."""
    if indent is not None:
        return None
    if '": "' in text or ": " in text:
        return None
    return (",", ":")


def write_journal(path: Path, doc: dict[str, Any], original: str) -> None:
    """Replace the file in the indentation it already used.

    Existing keys stay in their order. No snapshot field is added, and the
    events already in the document are left as they were loaded.
    """
    indent = _indent_of(original)
    separators = _separators(original, indent)
    rendered = json.dumps(doc, indent=indent, separators=separators)
    if original.endswith("\n"):
        rendered += "\n"
    path.write_text(rendered, encoding="utf-8")


def _load_journal(path: Path) -> tuple[dict[str, Any], str]:
    original = path.read_text(encoding="utf-8")
    doc = json.loads(original)
    if not isinstance(doc, dict) or not isinstance(doc.get("events"), list):
        raise SystemExit(f"{path} is not a paper-cash journal")
    if "cash" not in doc:
        raise SystemExit(f"{path} has no cash field; cash is not summed from events")
    return doc, original


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


def _identity(cash: float, trades_net: float) -> str:
    gap = cash - (STARTING_CAPITAL + trades_net)
    mark = "OK" if abs(gap) < IDENTITY_EPSILON else "MISMATCH"
    return (
        f"cash {cash:.6f} vs 10000+sum_net {STARTING_CAPITAL + trades_net:.6f} "
        f"diff {gap:+.6f} {mark}"
    )


def _print_summary(
    *,
    apply: bool,
    variant: str,
    before: tuple[int, float, float, int],
    after: tuple[int, float, float, int],
) -> None:
    mode = "APPLY" if apply else "DRY-RUN"
    print(f"\nmode={mode} variant={variant}")
    print(
        f"before: trades={before[0]} sum_net={before[1]:.6f} "
        f"cash={before[2]:.6f} open_positions={before[3]}"
    )
    print(
        f"after : trades={after[0]} sum_net={after[1]:.6f} "
        f"cash={after[2]:.6f} open_positions={after[3]}"
    )
    print(f"identity before: {_identity(before[2], before[1])}")
    print(f"identity after: {_identity(after[2], after[1])}")


def run(
    *,
    source: Path,
    journal: Path,
    variant: str,
    apply: bool,
    operator: str,
    audit_path: Path,
) -> int:
    if variant not in {"A", "B"}:
        print(f"variant must be A or B, got {variant!r}")
        return 1
    if not source.exists():
        print(f"source file not found: {source}")
        return 1
    if not journal.exists():
        print(f"journal not found: {journal}")
        return 1

    selected = select_variant(load_input_rows(source), variant)
    doc, original = _load_journal(journal)
    event_ids = {str(event.get("event_id")) for event in doc["events"] if event.get("event_id")}
    known = _load_known()
    pce_ids = _load_pce_ids()
    plan = [
        Planned(
            row=row,
            trade_action="skip(exists)" if trade_exists(known, row) else "insert",
            journal_action=_journal_action(row, event_ids),
            pce_action=_pce_action(row, pce_ids),
        )
        for row in selected
        if row.add_trade
    ]

    count, net, opens = _book_counts()
    cash = float(doc["cash"])
    realised = float(doc.get("realised_pnl") or 0.0)
    total_fees = float(doc.get("total_fees") or 0.0)
    total_funding = float(doc.get("total_funding") or 0.0)
    before = (count, net, cash, opens)
    now = datetime.now(timezone.utc)
    running = cash
    new_events: list[dict[str, Any]] = []
    inserted = 0

    print(
        f"{'key':28} {'sym':9} {'side':5} {'trade':13} {'journal':16} "
        f"{'pce':8} {'cash_delta':>12} {'cash_after':>13}"
    )
    if apply and any(item.trade_action == "insert" or item.pce_action == "insert" for item in plan):
        backup = _backup_sqlite()
        if backup is not None:
            logging.info("sqlite backup %s", backup)

    with session_scope() as session:
        for item in plan:
            row = item.row
            delta = row.cash_delta if item.journal_action == "post" else 0.0
            running += delta
            print(
                f"{row.backfill_key:28} {row.symbol:9} {row.side:5} "
                f"{item.trade_action:13} {item.journal_action[:16]:16} "
                f"{item.pce_action:8} {delta:12.6f} {running:13.6f}"
            )
            if not apply:
                continue
            if item.trade_action == "insert":
                _insert_trade(session, row)
                inserted += 1
                known.append(
                    KnownTrade(
                        cash_event_id=row.backfill_key,
                        symbol=row.symbol,
                        side=row.side,
                        entry_time=row.entry_time,
                        entry_price=row.entry_price,
                    )
                )
            if item.journal_action == "post":
                realised += delta
                total_fees += row.fees
                total_funding += row.funding
                new_events.append(
                    _close_event(
                        row,
                        cash_after=running,
                        realised=realised,
                        total_fees=total_fees,
                        total_funding=total_funding,
                        now=now,
                    )
                )
                event_ids.add(row.backfill_key)
            if item.pce_action == "insert":
                _insert_pce(session, row, running, now)

    wrote = False
    if apply and (inserted or new_events):
        doc["events"].extend(new_events)
        doc["cash"] = running
        if "realised_pnl" in doc:
            doc["realised_pnl"] = realised
        if "total_fees" in doc:
            doc["total_fees"] = total_fees
        if "total_funding" in doc:
            doc["total_funding"] = total_funding
        write_journal(journal, doc, original)
        wrote = True

    if apply:
        count_after, net_after, opens_after = _book_counts()
        after = (count_after, net_after, running, opens_after)
    else:
        extra_net = sum(item.row.net_pnl for item in plan if item.trade_action == "insert")
        extra_count = sum(1 for item in plan if item.trade_action == "insert")
        after = (count + extra_count, net + extra_net, running, opens)

    _print_summary(apply=apply, variant=variant, before=before, after=after)
    if apply:
        _append_audit(
            audit_path,
            {
                "ts": now.isoformat(),
                "operator": operator,
                "git_sha": _git_sha(),
                "variant": variant,
                "source": str(source),
                "journal_rewritten": wrote,
                "inserted_trades": inserted,
                "posted_closes": len(new_events),
                "keys": [item.row.backfill_key for item in plan if item.trade_action == "insert"],
                "cash_before": before[2],
                "cash_after": after[2],
                "trades_before": before[0],
                "trades_after": after[0],
                "sum_net_before": before[1],
                "sum_net_after": after[1],
            },
        )
        print(f"audit: {audit_path}")
    return 0


def _append_audit(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", "--source", dest="source", required=True, type=Path)
    parser.add_argument("--journal", type=Path, default=None)
    parser.add_argument("--variant", default="B", choices=["A", "B"])
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
        variant=args.variant,
        apply=args.apply,
        operator=args.operator,
        audit_path=audit,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    raise SystemExit(main())
