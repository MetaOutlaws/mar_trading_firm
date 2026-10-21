"""24-hour rolling near-miss log for the paper worker.

One JSON object per line under ``data/near_miss_log.jsonl``. Rows older than
24 hours are dropped on write and on read. The file is also capped so a busy
hour cannot grow it without bound. A failure here is logged and swallowed;
it must not change a scan, a gate, or an order.

Paper capacity rejections (sector cap, daily trade count, gross exposure)
do not use that rolling file. The Oct 20 rally post-mortem lost the first
hour because the rolling window was only a few hundred rows. Those
rejections are appended to a daily JSONL under ``data/near_miss_risk/``,
capped per day far above the rolling window. Writing one is report-only:
it does not change a limit, a size, or a verdict.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from config.settings import PROJECT_ROOT
from core.risk.engine import (
    PortfolioState,
    RiskDecision,
    RiskEngine,
    RiskVerdict,
    TradeIntent,
)
from core.risk.limits import RiskLimits

logger = logging.getLogger(__name__)

LOG_PATH = PROJECT_ROOT / "data" / "near_miss_log.jsonl"
RETENTION = timedelta(hours=24)
# Hard cap inside the window. Oldest rows go first.
MAX_ROWS = 2000

# Capacity rejections are not part of the rolling window above. One file
# per UTC day, append-only, same directory family as the near-miss log.
# 10_000 is the safety cap for a single day. It is not the 240-row window
# that dropped the first hour of 2026-10-20.
RISK_REJECTION_DIR = PROJECT_ROOT / "data" / "near_miss_risk"
RISK_REJECTION_MAX_ROWS = 10_000
# Portfolio checks the paper book asked to keep. A row is written only when
# at least one of these failed. Other checks on the same decision are still
# listed, so a multi-reason rejection is not reduced to the first hit.
TARGET_CAPACITY_REASONS = frozenset({
    "sector_cap",
    "max_daily_trades",
    "max_total_exposure_pct",
})


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _parse_time(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return _as_utc(value)
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return _as_utc(parsed)


def _row_key(row: dict[str, Any]) -> tuple[str, str, str, str, str]:
    """One bar, one sleeve, one condition. A later poll replaces the earlier line."""
    return (
        str(row.get("scan_type") or ""),
        str(row.get("bar_time") or ""),
        str(row.get("symbol") or ""),
        str(row.get("side") or ""),
        str(row.get("condition") or row.get("gate") or ""),
    )


def _load(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        try:
            item = json.loads(text)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _prune(rows: list[dict[str, Any]], now: datetime) -> list[dict[str, Any]]:
    cutoff = _as_utc(now) - RETENTION
    kept: list[dict[str, Any]] = []
    for row in rows:
        logged = _parse_time(row.get("logged_at"))
        if logged is None or logged < cutoff:
            continue
        kept.append(row)
    if len(kept) > MAX_ROWS:
        kept = kept[-MAX_ROWS:]
    return kept


def _write(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(json.dumps(row, separators=(",", ":"), default=str) + "\n" for row in rows)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(payload, encoding="utf-8")
    os.replace(temporary, path)


def append_near_misses(
    rows: list[dict[str, Any]] | None,
    *,
    scan_type: str,
    bar_time: datetime | str,
    now: datetime | None = None,
    path: Path | None = None,
) -> int:
    """Append this pass's numeric misses and drop anything older than 24 hours.

    Returns how many rows remain. Never raises.
    """
    try:
        return _append(rows, scan_type=scan_type, bar_time=bar_time, now=now, path=path)
    except Exception:
        logger.exception("Near-miss log was not written; the scan summary stands")
        return 0


def _append(
    rows: list[dict[str, Any]] | None,
    *,
    scan_type: str,
    bar_time: datetime | str,
    now: datetime | None,
    path: Path | None,
) -> int:
    target = path or LOG_PATH
    moment = _as_utc(now or datetime.now(timezone.utc))
    bar = bar_time.isoformat() if isinstance(bar_time, datetime) else str(bar_time)
    existing = _prune(_load(target), moment)
    incoming: list[dict[str, Any]] = []
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        if row.get("normalized") is None or row.get("gap") is None:
            continue
        item = dict(row)
        item["scan_type"] = scan_type
        item["bar_time"] = bar
        item["logged_at"] = moment.replace(microsecond=0).isoformat()
        incoming.append(item)
    by_key = {_row_key(row): row for row in existing}
    for row in incoming:
        key = _row_key(row)
        previous = by_key.get(key)
        if previous is not None and previous.get("logged_at"):
            # A later poll of the same bar refreshes the distance, not the clock.
            row["logged_at"] = previous["logged_at"]
        by_key[key] = row
    merged = _prune(list(by_key.values()), moment)
    merged.sort(key=lambda row: str(row.get("logged_at") or ""))
    _write(target, merged)
    return len(merged)


def read_near_misses(
    *,
    now: datetime | None = None,
    limit: int = 100,
    path: Path | None = None,
) -> dict[str, Any]:
    """The rolling window, nearest-recent first within the cap. Prunes the file."""
    target = path or LOG_PATH
    moment = _as_utc(now or datetime.now(timezone.utc))
    try:
        rows = _prune(_load(target), moment)
        if target.exists() or rows:
            _write(target, rows)
    except Exception:
        logger.exception("Near-miss log could not be read")
        rows = []
    rows = list(reversed(rows))
    cap = max(0, int(limit))
    shown = rows[:cap]
    return {
        "retention_hours": int(RETENTION.total_seconds() // 3600),
        "max_rows": MAX_ROWS,
        "count": len(rows),
        "rows": shown,
    }


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def capacity_reason_codes(
    intent: TradeIntent,
    state: PortfolioState,
    limits: RiskLimits,
) -> list[str]:
    """Every portfolio limit that currently fails, in risk-engine order.

    The comparisons match ``RiskEngine._check_portfolio_limits``. This
    function is not called by the risk engine. It does not change a verdict,
    a size, or the order of checks. All failing checks are returned, not the
    first one.
    """
    codes: list[str] = []
    if len(state.open_positions) >= limits.max_concurrent_positions:
        codes.append("max_concurrent_positions")
    if state.trades_today >= limits.max_daily_trades:
        codes.append("max_daily_trades")
    if state.has_position(intent.symbol) and limits.max_positions_per_symbol <= 1:
        codes.append("duplicate_position")
    if state.positions_in_sector(intent.sector) >= limits.max_positions_per_sector:
        codes.append("sector_cap")
    if state.exposure_pct >= limits.max_total_exposure_pct:
        codes.append("max_total_exposure_pct")
    return codes


def build_capacity_rejection_record(
    *,
    intent: TradeIntent,
    state: PortfolioState,
    limits: RiskLimits,
    decision: RiskDecision,
    sleeve: str,
    rule: str,
    clock: str,
    proposed_notional: float,
    now: datetime | None = None,
) -> dict[str, Any] | None:
    """Structured near-miss for a fired entry the risk layer rejected.

    Returns None unless the verdict is REJECTED and at least one of
    sector_cap, max_daily_trades, or max_total_exposure_pct failed. The
    ``reasons`` list is every portfolio check that failed on this snapshot.
    ``reason_text`` is the risk engine's own reason list, unchanged.
    """
    if decision.verdict is not RiskVerdict.REJECTED:
        return None
    codes = capacity_reason_codes(intent, state, limits)
    if not TARGET_CAPACITY_REASONS.intersection(codes):
        return None
    moment = _as_utc(now or _utcnow()).replace(microsecond=0)
    equity = float(state.equity)
    if equity > 0:
        notional_limit = equity * float(limits.max_total_exposure_pct)
    else:
        notional_limit = 0.0
    return {
        "kind": "capacity_rejection",
        "ts": moment.isoformat(),
        "symbol": str(intent.symbol),
        "sleeve": str(sleeve or ""),
        "rule": str(rule or ""),
        "clock": str(clock or ""),
        "side": str(intent.side),
        "reasons": list(codes),
        "reason_text": [str(item) for item in decision.reasons],
        # Same string the risk check counted. Callers set it from
        # Universe.sector_of, which reads SECTOR_OVERRIDES after SECTORS.
        "sector": str(intent.sector),
        "sector_count": int(state.positions_in_sector(intent.sector)),
        "sector_limit": int(limits.max_positions_per_sector),
        "daily_trade_count": int(state.trades_today),
        "daily_trade_limit": int(limits.max_daily_trades),
        "utc_day": str(state.day),
        "gross_exposure": float(state.total_exposure),
        "proposed_notional": float(proposed_notional),
        "notional_limit": float(notional_limit),
        "equity": equity,
    }


def note_paper_capacity_rejection(
    *,
    risk: RiskEngine,
    intent: TradeIntent,
    state: PortfolioState,
    decision: RiskDecision,
    sleeve: str,
    rule: str,
    clock: str,
    now: datetime | None = None,
    directory: Path | None = None,
) -> None:
    """Record a fired paper entry the risk layer already rejected.

    Reads the decision and the sizer. Does not assign either result back
    onto ``decision``, so the verdict, quantity, and notional stay as the
    risk engine left them. Never raises.
    """
    try:
        if decision.verdict is not RiskVerdict.REJECTED:
            return
        codes = capacity_reason_codes(intent, state, risk.limits)
        if not TARGET_CAPACITY_REASONS.intersection(codes):
            return
        # Index 1 is the notional. ``_size_position`` does not mutate the
        # intent, the book, or the decision.
        proposed = risk._size_position(intent, state)[1]
        record_capacity_rejection(
            intent=intent,
            state=state,
            limits=risk.limits,
            decision=decision,
            sleeve=sleeve,
            rule=rule,
            clock=clock,
            proposed_notional=float(proposed),
            now=now,
            directory=directory,
        )
    except Exception:
        logger.warning(
            "Paper capacity near-miss was not written; the rejection stands",
            exc_info=True,
        )


def record_capacity_rejection(
    *,
    intent: TradeIntent,
    state: PortfolioState,
    limits: RiskLimits,
    decision: RiskDecision,
    sleeve: str,
    rule: str,
    clock: str,
    proposed_notional: float,
    now: datetime | None = None,
    directory: Path | None = None,
) -> bool:
    """Append one capacity rejection. Never raises. Never edits the decision."""
    try:
        record = build_capacity_rejection_record(
            intent=intent,
            state=state,
            limits=limits,
            decision=decision,
            sleeve=sleeve,
            rule=rule,
            clock=clock,
            proposed_notional=proposed_notional,
            now=now,
        )
        if record is None:
            return False
        _append_capacity_rejection(record, directory=directory)
        return True
    except Exception:
        logger.warning(
            "Capacity near-miss was not written; the rejection stands",
            exc_info=True,
        )
        return False


def _append_capacity_rejection(
    record: dict[str, Any],
    *,
    directory: Path | None = None,
) -> None:
    """Append one JSON line to the UTC day's file. May raise; the caller swallows."""
    if not isinstance(record, dict):
        return
    moment = _parse_time(record.get("ts")) or _utcnow()
    day = moment.strftime("%Y-%m-%d")
    root = directory or RISK_REJECTION_DIR
    path = root / f"{day}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, separators=(",", ":"), default=str, ensure_ascii=False) + "\n"
    # O_APPEND, same as the scan-summary log: a second writer cannot truncate
    # a line the first one already wrote. The rolling near-miss rewrite does
    # not touch this file.
    fd = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o644)
    try:
        os.write(fd, line.encode("utf-8"))
    finally:
        os.close(fd)
    _trim_capacity_file(path)


def _trim_capacity_file(path: Path) -> None:
    """Drop the oldest rows only after the per-day cap. The cap is 10_000."""
    rows = _load(path)
    max_rows = int(RISK_REJECTION_MAX_ROWS)
    if max_rows < 1 or len(rows) <= max_rows:
        return
    _write(path, rows[-max_rows:])


def read_capacity_rejections(
    *,
    day: str | None = None,
    directory: Path | None = None,
) -> list[dict[str, Any]]:
    """Daily capacity-rejection rows, oldest first. Does not prune the rolling log."""
    root = directory or RISK_REJECTION_DIR
    if day is not None:
        paths = [root / f"{day}.jsonl"]
    elif root.exists():
        paths = sorted(
            path
            for path in root.glob("*.jsonl")
            if len(path.stem) == 10 and path.stem[4] == "-" and path.stem[7] == "-"
        )
    else:
        paths = []
    rows: list[dict[str, Any]] = []
    for path in paths:
        rows.extend(_load(path))
    return rows
