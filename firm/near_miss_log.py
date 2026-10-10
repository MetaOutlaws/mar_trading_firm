"""24-hour rolling near-miss log for the paper worker.

One JSON object per line under ``data/near_miss_log.jsonl``. Rows older than
24 hours are dropped on write and on read. The file is also capped so a busy
hour cannot grow it without bound. A failure here is logged and swallowed;
it must not change a scan, a gate, or an order.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from config.settings import PROJECT_ROOT

logger = logging.getLogger(__name__)

LOG_PATH = PROJECT_ROOT / "data" / "near_miss_log.jsonl"
RETENTION = timedelta(hours=24)
# Hard cap inside the window. Oldest rows go first.
MAX_ROWS = 2000


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
