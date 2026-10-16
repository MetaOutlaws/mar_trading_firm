"""Read-only status for isolated paper observers.

The hourly blotter, positions, and strategy book are not read or written
here. F111 is reshaped from its existing census. BL8 is a separate process
with its own ``status.json`` and SQLite ledger (PR #130 / #131). When those
files are not mounted on this API process, the card says so and leaves the
numbers empty.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from api.desk_status import (
    _age_seconds,
    _as_utc,
    _count_reasons,
    _hour_floor,
    _number,
    _utcnow,
    f111_status,
)

# The verifier treats a heartbeat older than 30s, or one from the future, as
# a failed check. The desk uses the same window.
_HEARTBEAT_FRESH_MS = 30_000
_ERROR_ROW_CAP = 5000
_BLOTTER_CAP = 30

# Bybit retCodes the BL8 public client treats as "slow down", plus the
# exception name it stores once the attempt cap is used up.
_RATE_RETCODES = frozenset({"10006", "10018"})
_RETCODE_TEXT = re.compile(r"(?:retCode|ret_code)\D{0,8}(\d+)", re.IGNORECASE)
_BARE_RETCODE = re.compile(r"\b(10006|10018)\b")

OBSERVER_IDS = ("f111", "bl8")

# Default BL8 state lives beside the hourly mount, not inside it. Override
# with BL8_STATE_DIR / BL8_STATUS_PATH / BL8_DB_PATH / BL8_CONFIG_PATH when
# the desk process cannot see /data/state/bl8-paper.
_DEFAULT_BL8_STATE_DIR = Path("/data/state/bl8-paper")


def _ms_to_dt(value: Any) -> datetime | None:
    ms = _number(value)
    if ms is None:
        return None
    try:
        return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None


def _iso(stamp: datetime | None) -> str | None:
    if stamp is None:
        return None
    return _as_utc(stamp).isoformat()


def _short_sha(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if len(text) < 7:
        return None
    return text[:12]


def _empty_pnl(basis: str) -> dict[str, Any]:
    return {
        "cash_usdt": None,
        "equity_usdt": None,
        "unrealized_usdt": None,
        "realized_usdt": None,
        "basis": basis,
    }


def _empty_rejections(now: datetime) -> dict[str, Any]:
    day_start = _as_utc(now) - timedelta(hours=24)
    return {
        "latest_hour": {"hour_start": None, "rows": 0, "by_reason": {}},
        "last_24h": {"since": day_start.isoformat(), "rows": 0, "by_reason": {}},
    }


def _bucket_reasons(
    stamped: list[tuple[str, datetime]],
    now: datetime,
) -> dict[str, Any]:
    """Same hour split as the F111 panel: latest hour that has a row, plus 24h."""
    moment = _as_utc(now)
    day_start = moment - timedelta(hours=24)
    latest_hour_start: datetime | None = None
    latest_rows: list[dict[str, Any]] = []
    if stamped:
        latest_hour_start = _hour_floor(max(stamp for _reason, stamp in stamped))
        latest_end = latest_hour_start + timedelta(hours=1)
        latest_rows = [
            {"rejection_reason": reason}
            for reason, stamp in stamped
            if latest_hour_start <= stamp < latest_end
        ]
    day_rows = [
        {"rejection_reason": reason}
        for reason, stamp in stamped
        if stamp >= day_start
    ]
    return {
        "latest_hour": {
            "hour_start": _iso(latest_hour_start),
            "rows": len(latest_rows),
            "by_reason": _count_reasons(latest_rows),
        },
        "last_24h": {
            "since": day_start.isoformat(),
            "rows": len(day_rows),
            "by_reason": _count_reasons(day_rows),
        },
    }


def _coverage_text(coverage: dict[str, Any], *, unavailable: bool) -> str:
    if unavailable:
        return "unavailable"
    available = coverage.get("available")
    scanned = coverage.get("scanned")
    expected = coverage.get("expected")
    shown = available if available is not None else scanned
    if shown is None and expected is None:
        return "—"
    if expected is None:
        return str(shown)
    if shown is None:
        return "—/" + str(expected)
    return f"{shown}/{expected}"


def _pulse(card: dict[str, Any]) -> dict[str, Any]:
    scan = card.get("scan") if isinstance(card.get("scan"), dict) else None
    complete = scan.get("complete") if scan else None
    health = str(card.get("health") or "unavailable")
    tone = health
    if complete is False and health == "ok":
        tone = "warn"
    positions = card.get("open_positions_count")
    return {
        "id": card.get("id"),
        "label": card.get("label"),
        "mode": "paper",
        "coverage_text": _coverage_text(
            card.get("coverage") or {},
            unavailable=health == "unavailable",
        ),
        "open_positions": positions,
        "health": health,
        "tone": tone,
        "degraded": bool(card.get("degraded")),
        "scan_complete": complete,
    }


def _shell(
    *,
    observer_id: str,
    label: str,
    health: str,
    health_hint: str,
    degraded: bool,
    degraded_reason: str | None,
    sizing_policy: str | None,
    release_sha: str | None,
    coverage: dict[str, Any],
    last_scan: str | None,
    last_scan_age_seconds: int | None,
    open_positions: list[dict[str, Any]] | None,
    paper_pnl: dict[str, Any],
    census: dict[str, Any],
    rejections: dict[str, Any],
    blotter: list[dict[str, Any]],
    banner: dict[str, Any],
    paths: dict[str, Any],
    scan: dict[str, Any] | None = None,
    extras: list[dict[str, Any]] | None = None,
    detail: dict[str, Any] | None = None,
    why_no_trade: dict[str, Any] | None = None,
) -> dict[str, Any]:
    # None means the book was not readable. An empty list is a real flat book.
    count = None if open_positions is None else len(open_positions)
    shown_blotter = None if blotter is None else blotter[-_BLOTTER_CAP:]
    return {
        "id": observer_id,
        "label": label,
        "paper_only": True,
        "isolated": True,
        "live_book": False,
        "available": health != "unavailable",
        "degraded": degraded,
        "degraded_reason": degraded_reason,
        "health": health,
        "health_hint": health_hint,
        "sizing_policy": sizing_policy,
        "release_sha": release_sha,
        "release_short": _short_sha(release_sha),
        "coverage": coverage,
        "last_scan": last_scan,
        "last_scan_age_seconds": last_scan_age_seconds,
        "open_positions_count": count,
        "open_positions": open_positions,
        "paper_pnl": paper_pnl,
        "census": census,
        "rejections": rejections,
        "blotter": shown_blotter,
        "banner": banner,
        "scan": scan,
        "why_no_trade": why_no_trade,
        "extras": extras or [],
        "paths": paths,
        "detail": detail or {},
    }


def f111_observer(
    *,
    now: datetime | None = None,
    telemetry_path: Path | None = None,
    state_path: Path | None = None,
) -> dict[str, Any]:
    """F111 census in the shared observer shape. Same files as ``/api/f111``."""
    moment = _as_utc(now or _utcnow())
    panel = f111_status(now=moment, telemetry_path=telemetry_path, state_path=state_path)
    registry = panel.get("registry") or {}
    telemetry_present = bool(panel.get("telemetry_present"))
    missing: list[str] = []
    if not telemetry_present:
        missing.append("telemetry")
    if panel.get("state_error") == "missing":
        missing.append("state")
    config_error = panel.get("config_error")
    state_error = panel.get("state_error")
    hard_state_error = bool(state_error) and state_error != "missing"
    # Census comes from telemetry. Both files missing is an empty card, not a
    # real zero book. A missing state file alone still shows the census.
    if not telemetry_present and state_error == "missing":
        health = "unavailable"
    elif config_error or hard_state_error or not telemetry_present:
        health = "degraded"
    else:
        health = "ok"
    reasons: list[str] = []
    if config_error:
        reasons.append("config " + str(config_error))
    if missing:
        reasons.append("missing " + ", ".join(missing))
    if hard_state_error:
        reasons.append("state " + str(state_error))
    degraded = health != "ok" or bool(missing)
    expected = panel.get("expected_sleeves")
    evaluated = registry.get("evaluated") if telemetry_present else None
    title = f"{expected if expected is not None else '—'} sleeves"
    if health == "unavailable":
        body = "F111 telemetry and state are not on this process. No counts are filled in."
    else:
        body = (
            f"Latest census evaluated {evaluated if evaluated is not None else 0}. "
            f"Available {registry.get('available') if registry.get('available') is not None else 0} · "
            f"closed {registry.get('closed') if registry.get('closed') is not None else 0}. "
            "Display only — this panel does not scan or order."
        )
    tone = "ok" if evaluated == expected and health == "ok" else "warn"
    if health == "unavailable":
        tone = "bad"
    hint = "Attached F111 paper scan. " + (panel.get("strategy_version") or "paper")
    if degraded and reasons:
        hint = hint + ". " + "; ".join(reasons)
    return _shell(
        observer_id="f111",
        label="F111",
        health=health,
        health_hint=hint,
        degraded=degraded,
        degraded_reason="; ".join(reasons) or None,
        sizing_policy=panel.get("sizing_policy"),
        release_sha=panel.get("configuration_sha256"),
        coverage={
            "available": registry.get("available") if telemetry_present else None,
            "closed": registry.get("closed") if telemetry_present else None,
            "expected": expected,
            "scanned": evaluated if telemetry_present else None,
        },
        last_scan=panel.get("last_bar_close_evaluation"),
        last_scan_age_seconds=panel.get("last_scan_age_seconds"),
        open_positions=None if health == "unavailable" else list(panel.get("open_positions") or []),
        paper_pnl=panel.get("paper_pnl") or _empty_pnl("no realised F111 exits in telemetry"),
        census={
            "evaluated": registry.get("evaluated") if telemetry_present else None,
            "available": registry.get("available") if telemetry_present else None,
            "closed": registry.get("closed") if telemetry_present else None,
            "closed_by_reason": (registry.get("closed_by_reason") or {}) if telemetry_present else {},
        },
        rejections=panel.get("rejections") or _empty_rejections(moment),
        blotter=None if health == "unavailable" else list(panel.get("blotter") or []),
        banner={"tone": tone, "title": title, "body": body},
        paths={
            "telemetry": panel.get("telemetry_path"),
            "state": panel.get("state_path"),
            "missing": missing,
        },
        scan=None,
        extras=[
            {
                "label": "Pending retests",
                "value": panel.get("pending_retests"),
                "hint": "watching or scheduled",
            },
            {
                "label": "Protection",
                "value": panel.get("protection"),
                "hint": "open floors",
            },
        ],
        detail={
            "expected_sleeves": expected,
            "pending_retests": panel.get("pending_retests"),
            "protection": panel.get("protection"),
            "config_error": config_error,
            "state_error": state_error,
            "closed_by_reason": (registry.get("closed_by_reason") or {}),
        },
        why_no_trade=panel.get("why_no_trade"),
    )


def bl8_paths(
    *,
    status_path: Path | None = None,
    db_path: Path | None = None,
    config_path: Path | None = None,
) -> dict[str, Path | None]:
    """Explicit paths win, then env, then ``/data/state/bl8-paper``.

    Tests pass paths in so a developer machine's ``BL8_*`` variables cannot
    leak into the assertion.
    """
    state_dir = Path(os.environ.get("BL8_STATE_DIR") or _DEFAULT_BL8_STATE_DIR)
    status = status_path or Path(os.environ.get("BL8_STATUS_PATH") or (state_dir / "status.json"))
    database = db_path or Path(os.environ.get("BL8_DB_PATH") or (state_dir / "paper.db"))
    if config_path is not None:
        config: Path | None = Path(config_path)
    else:
        raw_config = os.environ.get("BL8_CONFIG_PATH", "").strip()
        config = Path(raw_config) if raw_config else None
    return {"status": Path(status), "database": Path(database), "config": config}


def _read_status_file(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.exists():
        return None, "missing"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, str(exc)
    if not isinstance(payload, dict):
        return None, "status.json is not a JSON object"
    return payload, None


def _load_bl8_config(path: Path | None) -> tuple[dict[str, Any] | None, str | None]:
    if path is None:
        return None, "not configured"
    if not path.exists():
        return None, "missing"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, str(exc)
    if not isinstance(payload, dict):
        return None, "config is not a JSON object"
    return payload, None


def _rate_limit_code(payload: dict[str, Any]) -> str | None:
    """Return a retCode when this error is a Bybit rate limit, else None."""
    for key in ("ret_code", "retCode"):
        number = _number(payload.get(key))
        if number is None:
            continue
        code = str(int(number))
        if code in _RATE_RETCODES:
            return code
    text = str(payload.get("error") or "")
    lowered = text.lower()
    named = (
        "ratelimited" in lowered
        or "rate limit" in lowered
        or "too many" in lowered
        or "too frequent" in lowered
    )
    match = _RETCODE_TEXT.search(text) or _BARE_RETCODE.search(text)
    if match and (named or match.group(1) in _RATE_RETCODES):
        return match.group(1)
    if named:
        return "rate_limit"
    return None


def _json_object(raw: Any) -> dict[str, Any] | None:
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str) or not raw:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _query_bl8(db: sqlite3.Connection, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
    return list(db.execute(sql, params))


def _latest_context(db: sqlite3.Connection) -> list[tuple[datetime | None, dict[str, Any]]]:
    """One context payload per symbol: the newest observation id."""
    try:
        rows = _query_bl8(
            db,
            """
            SELECT o.t, o.payload
            FROM observations o
            JOIN (
                SELECT json_extract(payload, '$.symbol') AS symbol, MAX(id) AS id
                FROM observations
                WHERE kind = 'context'
                  AND json_extract(payload, '$.symbol') IS NOT NULL
                GROUP BY symbol
            ) latest ON latest.id = o.id
            """,
        )
    except sqlite3.Error:
        rows = _query_bl8(
            db,
            "SELECT t, payload FROM observations WHERE kind = 'context' ORDER BY id",
        )
        latest: dict[str, tuple[Any, dict[str, Any]]] = {}
        for row in rows:
            payload = _json_object(row["payload"])
            if payload is None:
                continue
            symbol = payload.get("symbol")
            if not isinstance(symbol, str) or not symbol:
                continue
            latest[symbol] = (row["t"], payload)
        return [(_ms_to_dt(stamp), payload) for stamp, payload in latest.values()]
    out: list[tuple[datetime | None, dict[str, Any]]] = []
    for row in rows:
        payload = _json_object(row["payload"])
        if payload is None:
            continue
        out.append((_ms_to_dt(row["t"]), payload))
    return out


def _run_start_ms(
    db: sqlite3.Connection,
    *,
    started_ms: float | None,
    release: str | None,
) -> float | None:
    """Start of the release in ``status.json``.

    The isolated ledger keeps every prior pin. A startup row records that
    pin's release. Rate-limit rows from an earlier pin stay in the table and
    must not be counted as this run.
    """
    matched: float | None = None
    wanted = release.strip() if isinstance(release, str) else ""
    for row in _query_bl8(
        db,
        "SELECT t, payload FROM observations WHERE kind = 'startup' ORDER BY id",
    ):
        payload = _json_object(row["payload"]) or {}
        stamp = _number(row["t"])
        pinned = payload.get("release")
        if stamp is None or not isinstance(pinned, str) or not wanted:
            continue
        if pinned.strip() != wanted:
            continue
        matched = stamp if matched is None else max(matched, stamp)
    if started_ms is not None and matched is not None:
        return max(started_ms, matched)
    if started_ms is not None:
        return started_ms
    return matched


def _read_bl8_db(
    path: Path,
    *,
    now: datetime,
    started_ms: float | None,
    release: str | None = None,
) -> dict[str, Any]:
    """Open the BL8 ledger read-only. A lock or a missing table degrades."""
    result: dict[str, Any] = {
        "ok": False,
        "error": None,
        "contexts": [],
        "rejections": [],
        "errors": [],
        "run_started_ms": None,
        "open_positions": [],
        "blotter": [],
        "cash_usdt": None,
    }
    if not path.exists():
        result["error"] = "missing"
        return result
    uri = path.resolve().as_uri() + "?mode=ro"
    try:
        db = sqlite3.connect(uri, uri=True, timeout=2)
    except sqlite3.Error as exc:
        result["error"] = str(exc)
        return result
    try:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA query_only=ON")
        tables = {
            str(row[0])
            for row in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        required = {"observations", "positions", "events"}
        absent = sorted(required - tables)
        if absent:
            result["error"] = "missing tables " + ", ".join(absent)
            return result
        # Sit-out and gate rows stay on the rolling day. Rate-limit counts do
        # not: the same book holds the previous pin's 10006 burst.
        day_ms = (now - timedelta(hours=24)).timestamp() * 1000.0
        rejection_since = day_ms
        if started_ms is not None:
            rejection_since = min(day_ms, started_ms)
        run_start = _run_start_ms(db, started_ms=started_ms, release=release)
        result["run_started_ms"] = run_start
        result["contexts"] = _latest_context(db)
        result["rejections"] = _rejection_events(db, since_ms=rejection_since)
        if started_ms is None and not (isinstance(release, str) and release.strip()):
            result["errors"] = _error_events(db, since_ms=day_ms)
        elif run_start is None:
            result["errors"] = []
        else:
            result["errors"] = _error_events(db, since_ms=run_start)
        result["open_positions"] = _position_rows(db, "open")
        result["closed_positions"] = _position_rows(db, "closed")
        result["blotter"] = _closed_blotter(db)
        result["entry_rejected"] = _entry_rejected_rows(db)
        result["signals"] = _signal_rows(db)
        cash = db.execute("SELECT coalesce(sum(amount), 0) FROM events").fetchone()
        result["cash_usdt"] = _number(cash[0]) if cash is not None else None
        result["ok"] = True
        return result
    except sqlite3.Error as exc:
        result["error"] = str(exc)
        return result
    finally:
        db.close()


def _rejection_events(db: sqlite3.Connection, *, since_ms: float) -> list[tuple[str, datetime]]:
    """Entry rejects, plus context sit-outs. A passing fill gate is not a reject."""
    stamped: list[tuple[str, datetime]] = []
    for row in _query_bl8(
        db,
        "SELECT t, payload FROM observations WHERE kind = 'entry_rejected' AND t >= ?",
        (since_ms,),
    ):
        payload = _json_object(row["payload"]) or {}
        reason = payload.get("reason")
        stamp = _ms_to_dt(row["t"])
        if isinstance(reason, str) and reason and stamp is not None:
            stamped.append((reason, stamp))
    for row in _query_bl8(
        db,
        "SELECT t, payload FROM observations WHERE kind = 'context' AND t >= ?",
        (since_ms,),
    ):
        payload = _json_object(row["payload"]) or {}
        reason = payload.get("reason")
        stamp = _ms_to_dt(row["t"])
        if not isinstance(reason, str) or not reason or stamp is None:
            continue
        if reason == "candidate_requires_fill_gate":
            continue
        stamped.append((reason, stamp))
    return stamped


def _error_events(db: sqlite3.Connection, *, since_ms: float) -> list[dict[str, Any]]:
    rows = _query_bl8(
        db,
        """
        SELECT t, payload FROM observations
        WHERE kind = 'error' AND t >= ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (since_ms, _ERROR_ROW_CAP),
    )
    out: list[dict[str, Any]] = []
    for row in rows:
        payload = _json_object(row["payload"]) or {}
        code = _rate_limit_code(payload)
        out.append(
            {
                "t": _iso(_ms_to_dt(row["t"])),
                "symbol": payload.get("identity") or payload.get("symbol"),
                "operation": payload.get("operation"),
                "error": str(payload.get("error") or "")[:240],
                "rate_limit": code is not None,
                "ret_code": code,
            }
        )
    return out


def _entry_rejected_rows(db: sqlite3.Connection) -> list[dict[str, Any]]:
    """Raw entry rejects for the why panel. The day bucket above is separate."""
    rows = _query_bl8(
        db,
        "SELECT t, payload FROM observations WHERE kind = 'entry_rejected'",
    )
    out: list[dict[str, Any]] = []
    for row in rows:
        payload = _json_object(row["payload"])
        if payload is None:
            continue
        out.append({"t": _number(row["t"]), "payload": payload})
    return out


def _signal_rows(db: sqlite3.Connection) -> list[dict[str, Any]]:
    """Signal rows when the ledger has them. A book without the table is empty."""
    try:
        rows = _query_bl8(db, "SELECT symbol, status, payload FROM signals")
    except sqlite3.Error:
        return []
    out: list[dict[str, Any]] = []
    for row in rows:
        payload = _json_object(row["payload"]) or {}
        out.append(
            {
                "symbol": row["symbol"],
                "status": row["status"],
                "payload": payload,
            }
        )
    return out


def _position_rows(db: sqlite3.Connection, status: str) -> list[dict[str, Any]]:
    rows = _query_bl8(db, "SELECT payload FROM positions WHERE status = ?", (status,))
    out: list[dict[str, Any]] = []
    for row in rows:
        payload = _json_object(row["payload"])
        if payload is not None:
            out.append(payload)
    return out


def _closed_blotter(db: sqlite3.Connection) -> list[dict[str, Any]]:
    cash_by_uid: dict[str, float] = {}
    for row in _query_bl8(db, "SELECT uid, coalesce(sum(amount), 0) AS net FROM events GROUP BY uid"):
        uid = row["uid"]
        net = _number(row["net"])
        if isinstance(uid, str) and net is not None:
            cash_by_uid[uid] = net
    closed = _position_rows(db, "closed")
    blotter: list[dict[str, Any]] = []
    for payload in closed:
        entry = _number(payload.get("entry_price"))
        exit_price = _number(payload.get("exit_price"))
        gross = _number(payload.get("gross_pnl"))
        entry_fee = _number(payload.get("entry_fee")) or 0.0
        exit_fee = _number(payload.get("exit_fee")) or 0.0
        uid = payload.get("uid")
        if isinstance(uid, str) and uid in cash_by_uid:
            net = cash_by_uid[uid]
        elif gross is not None:
            net = gross - entry_fee - exit_fee
        else:
            net = None
        blotter.append(
            {
                "symbol": payload.get("symbol"),
                "side": payload.get("side") or "LONG",
                "quantity": _number(payload.get("quantity")),
                "entry_price": entry,
                "exit_price": exit_price,
                "closed_at": _iso(_ms_to_dt(payload.get("exit_ms"))),
                "exit_ms": _number(payload.get("exit_ms")) or 0,
                "net_pnl": net,
                "reason": payload.get("exit_reason"),
            }
        )
    blotter.sort(key=lambda row: row.get("exit_ms") or 0)
    for row in blotter:
        row.pop("exit_ms", None)
    return blotter


def _bl8_open_positions(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """BL8 entries are long-only. Mark-to-entry uses the stored bid, when present."""
    out: list[dict[str, Any]] = []
    for payload in rows:
        qty = _number(payload.get("quantity"))
        entry = _number(payload.get("entry_price"))
        mark = _number(payload.get("mark_price"))
        unrealised = None
        if qty is not None and entry is not None and mark is not None:
            unrealised = qty * (mark - entry)
        out.append(
            {
                "symbol": payload.get("symbol"),
                "side": payload.get("side") or "LONG",
                "quantity": qty,
                "entry_price": entry,
                "mark_price": mark,
                "stop": _number(payload.get("stop")),
                "target": _number(payload.get("target")),
                "opened_at": _iso(_ms_to_dt(payload.get("entry_ms"))),
                "unrealised_pnl": unrealised,
                "reason": None,
            }
        )
    return out


def _census_from_context(
    contexts: list[tuple[datetime | None, dict[str, Any]]],
    expected_symbols: list[str] | None,
) -> dict[str, Any]:
    available = 0
    closed_by: dict[str, int] = {}
    for _stamp, payload in contexts:
        instrument = payload.get("instrument")
        trading = isinstance(instrument, dict) and instrument.get("status") == "Trading"
        if trading:
            available += 1
            continue
        reason = payload.get("reason")
        if not isinstance(reason, str) or not reason:
            status = instrument.get("status") if isinstance(instrument, dict) else None
            reason = f"instrument {status}" if status else "instrument_unavailable"
        closed_by[reason] = closed_by.get(reason, 0) + 1
    closed = sum(closed_by.values())
    expected = len(expected_symbols) if expected_symbols is not None else None
    return {
        "evaluated": len(contexts),
        "available": available,
        "closed": closed,
        "expected": expected,
        "closed_by_reason": dict(sorted(closed_by.items(), key=lambda item: (-item[1], item[0]))),
    }


def _scan_block(
    errors: list[dict[str, Any]],
    complete: bool | None,
    *,
    run_started_at: str | None = None,
) -> dict[str, Any]:
    retcodes: dict[str, int] = {}
    rate_limit = 0
    for row in errors:
        if not row.get("rate_limit"):
            continue
        rate_limit += 1
        code = str(row.get("ret_code") or "rate_limit")
        retcodes[code] = retcodes.get(code, 0) + 1
    if complete is True:
        label = "complete"
    elif complete is False:
        label = "incomplete"
    else:
        label = "unknown"
    recent = list(reversed(errors[:8]))
    return {
        "complete": complete,
        "label": label,
        "rate_limit_errors": rate_limit,
        "error_count": len(errors),
        "retcodes": dict(sorted(retcodes.items(), key=lambda item: (-item[1], item[0]))),
        "recent_errors": recent,
        "truncated": len(errors) >= _ERROR_ROW_CAP,
        # Errors in this block are from this release's run, not earlier pins.
        "run_started_at": run_started_at,
    }


def bl8_observer(
    *,
    now: datetime | None = None,
    status_path: Path | None = None,
    db_path: Path | None = None,
    config_path: Path | None = None,
) -> dict[str, Any]:
    """BL8 paper observer. Reads status.json and the ledger. Writes nothing."""
    moment = _as_utc(now or _utcnow())
    paths = bl8_paths(status_path=status_path, db_path=db_path, config_path=config_path)
    status_file = paths["status"]
    database = paths["database"]
    config_file = paths["config"]
    assert isinstance(status_file, Path) and isinstance(database, Path)

    status, status_error = _read_status_file(status_file)
    config, config_error = _load_bl8_config(config_file if isinstance(config_file, Path) else None)
    started_ms = _number((status or {}).get("started_ms")) if status else None
    release_pin = status.get("release") if status and isinstance(status.get("release"), str) else None
    db_view = _read_bl8_db(
        database,
        now=moment,
        started_ms=started_ms,
        release=release_pin,
    )

    missing: list[str] = []
    if status is None and status_error == "missing":
        missing.append(str(status_file))
    if not database.exists():
        missing.append(str(database))
    if config_file is not None and config is None and config_error == "missing":
        missing.append(str(config_file))

    universe = None
    if config and isinstance(config.get("universe"), list):
        universe = [str(symbol) for symbol in config["universe"]]
    expected = len(universe) if universe is not None else None
    sizing = config.get("sizing_policy") if config else None
    if sizing is not None and not isinstance(sizing, str):
        sizing = None

    equity = status.get("equity") if status and isinstance(status.get("equity"), dict) else None
    paper_pnl = _empty_pnl("no BL8 equity published")
    if equity:
        paper_pnl = {
            "cash_usdt": _number(equity.get("cash_pnl_usdt")),
            "equity_usdt": _number(equity.get("account_equity_usdt")),
            "unrealized_usdt": _number(equity.get("unrealized_pnl_usdt")),
            "realized_usdt": _number(equity.get("cash_pnl_usdt")),
            "basis": "status.json equity on the isolated BL8 book",
        }
    elif db_view.get("ok") and db_view.get("cash_usdt") is not None:
        paper_pnl = {
            "cash_usdt": db_view.get("cash_usdt"),
            "equity_usdt": None,
            "unrealized_usdt": None,
            "realized_usdt": db_view.get("cash_usdt"),
            "basis": "sum of BL8 ledger events; account equity needs status.json",
        }

    census_raw = {"evaluated": 0, "available": 0, "closed": 0, "expected": expected, "closed_by_reason": {}}
    rejections = _empty_rejections(moment)
    open_positions: list[dict[str, Any]] | None = None
    blotter: list[dict[str, Any]] | None = None
    errors: list[dict[str, Any]] = []
    if db_view.get("ok"):
        census_raw = _census_from_context(db_view["contexts"], universe)
        rejections = _bucket_reasons(db_view["rejections"], moment)
        open_positions = _bl8_open_positions(db_view["open_positions"])
        blotter = db_view["blotter"]
        errors = db_view["errors"]

    # Latest scan flag from the running process. Historical 10006 rows do not
    # change it.
    complete = status.get("universe_scan_complete") if status else None
    if not isinstance(complete, bool):
        complete = None
    run_started_at = _iso(_ms_to_dt(db_view.get("run_started_ms"))) if db_view.get("ok") else None
    scan = (
        _scan_block(errors, complete, run_started_at=run_started_at)
        if (status is not None or db_view.get("ok"))
        else _scan_block([], None)
    )
    if not db_view.get("ok"):
        # An unread ledger cannot report a zero error count.
        scan["rate_limit_errors"] = None
        scan["error_count"] = None
        scan["retcodes"] = {}
        scan["recent_errors"] = []

    from api.why_no_trade import build_bl8_why, unavailable_why

    if db_view.get("ok"):
        why_no_trade = build_bl8_why(
            db_view.get("contexts") or [],
            entry_rejected=db_view.get("entry_rejected") or [],
            errors=errors,
            signals=db_view.get("signals") or [],
            positions=(db_view.get("open_positions") or []) + (db_view.get("closed_positions") or []),
        )
    else:
        why_no_trade = unavailable_why("This observer's scan was not readable.")

    heartbeat = _ms_to_dt(status.get("heartbeat_ms")) if status else None
    heartbeat_age_ms = None
    if heartbeat is not None:
        heartbeat_age_ms = int((moment - heartbeat).total_seconds() * 1000)
    fresh = heartbeat_age_ms is not None and 0 <= heartbeat_age_ms <= _HEARTBEAT_FRESH_MS
    paused = (status_file.parent / "entries_disabled").exists() if status_file.parent else False

    if status is None and not db_view.get("ok"):
        health = "unavailable"
    elif status is not None and not fresh:
        health = "stale"
    elif not db_view.get("ok") or status_error not in (None, "missing"):
        health = "degraded"
    else:
        health = "ok"

    reasons: list[str] = []
    if status is None:
        reasons.append("status.json " + str(status_error or "missing"))
    elif not fresh:
        if heartbeat_age_ms is None:
            reasons.append("status.json has no heartbeat_ms")
        elif heartbeat_age_ms < 0:
            reasons.append("heartbeat is in the future")
        else:
            reasons.append(f"heartbeat {heartbeat_age_ms // 1000}s old")
    if not db_view.get("ok"):
        reasons.append("paper.db " + str(db_view.get("error") or "unavailable"))
    if paused:
        reasons.append("entries_disabled is set")
    degraded = health != "ok" or bool(reasons)

    release = status.get("release") if status else None
    if not isinstance(release, str) or not release.strip():
        release = None

    last_scan = heartbeat
    coverage = {
        "available": census_raw["available"] if db_view.get("ok") else None,
        "closed": census_raw["closed"] if db_view.get("ok") else None,
        "expected": expected,
        "scanned": census_raw["evaluated"] if db_view.get("ok") else None,
    }
    if health == "unavailable":
        open_positions = None

    scan_label = scan.get("label") or "unknown"
    rate_bit = ""
    if isinstance(scan.get("rate_limit_errors"), int):
        rate_bit = f" Rate-limit errors {scan['rate_limit_errors']}."
    title = "BL8 paper"
    if coverage["available"] is not None and expected is not None:
        title = f"BL8 {coverage['available']}/{expected}"
    elif health == "unavailable":
        title = "BL8 unavailable"
    body = (
        f"Scan {scan_label}.{rate_bit} "
        "Isolated public-data observer. Display only — nothing here scans, orders, or touches the hourly book."
    )
    if health == "unavailable":
        tone = "bad"
    elif health in {"stale", "degraded"} or complete is False:
        tone = "warn"
    else:
        tone = "ok"
    hint_bits = ["mar-bl8-shadow.service"]
    if fresh and heartbeat_age_ms is not None:
        hint_bits.append(f"heartbeat {max(heartbeat_age_ms // 1000, 0)}s ago")
    elif heartbeat_age_ms is not None and heartbeat_age_ms >= 0:
        hint_bits.append(f"heartbeat {heartbeat_age_ms // 1000}s old")
    if paused:
        hint_bits.append("entries paused")
    if reasons and health != "ok":
        hint_bits.append("; ".join(reasons))

    return _shell(
        observer_id="bl8",
        label="BL8",
        health=health,
        health_hint=" · ".join(hint_bits),
        degraded=degraded,
        degraded_reason="; ".join(reasons) or None,
        sizing_policy=sizing if isinstance(sizing, str) else None,
        release_sha=release,
        coverage=coverage,
        last_scan=_iso(last_scan),
        last_scan_age_seconds=_age_seconds(last_scan, moment),
        open_positions=open_positions,
        paper_pnl=paper_pnl,
        census={
            "evaluated": census_raw["evaluated"] if db_view.get("ok") else 0,
            "available": census_raw["available"] if db_view.get("ok") else 0,
            "closed": census_raw["closed"] if db_view.get("ok") else 0,
            "closed_by_reason": census_raw["closed_by_reason"] if db_view.get("ok") else {},
        },
        rejections=rejections,
        blotter=blotter,
        banner={"tone": tone, "title": title, "body": body.strip()},
        paths={
            "status": str(status_file),
            "database": str(database),
            "config": str(config_file) if config_file else None,
            "missing": missing,
        },
        scan=scan,
        extras=[],
        detail={
            "config_sha": status.get("config_sha") if status else None,
            "paper_only": True if status is None else status.get("paper_only"),
            "jobs": status.get("jobs") if status else None,
            "entries_disabled": paused,
            "config_error": None if config_error == "not configured" else config_error,
        },
        why_no_trade=why_no_trade,
    )


def observer_status(observer_id: str, **kwargs: Any) -> dict[str, Any]:
    """One observer card. Unknown ids raise ``KeyError``."""
    key = str(observer_id or "").strip().lower()
    if key == "f111":
        return f111_observer(
            now=kwargs.get("now"),
            telemetry_path=kwargs.get("telemetry_path"),
            state_path=kwargs.get("state_path"),
        )
    if key == "bl8":
        return bl8_observer(
            now=kwargs.get("now"),
            status_path=kwargs.get("status_path"),
            db_path=kwargs.get("db_path"),
            config_path=kwargs.get("config_path"),
        )
    raise KeyError(key)


def _failed_card(observer_id: str, exc: BaseException) -> dict[str, Any]:
    """A read blew up. Keep the card shape and do not invent a flat book."""
    label = {"f111": "F111", "bl8": "BL8"}.get(observer_id, observer_id.upper())
    reason = f"{type(exc).__name__}: {exc}"[:240]
    now = _utcnow()
    scan = None
    if observer_id == "bl8":
        scan = _scan_block([], None)
        scan["rate_limit_errors"] = None
        scan["error_count"] = None
        scan["retcodes"] = {}
        scan["recent_errors"] = []
    return _shell(
        observer_id=observer_id,
        label=label,
        health="unavailable",
        health_hint=reason,
        degraded=True,
        degraded_reason=reason,
        sizing_policy=None,
        release_sha=None,
        coverage={"available": None, "closed": None, "expected": None, "scanned": None},
        last_scan=None,
        last_scan_age_seconds=None,
        open_positions=None,
        paper_pnl=_empty_pnl("observer read failed"),
        census={"evaluated": None, "available": None, "closed": None, "closed_by_reason": {}},
        rejections=_empty_rejections(now),
        blotter=None,
        banner={"tone": "bad", "title": f"{label} unavailable", "body": reason},
        paths={"missing": [reason]},
        scan=scan,
        why_no_trade={
            "ok": False,
            "reason": reason,
            "summary": reason,
            "scan_at": None,
            "funnel": [],
            "closest_misses": [],
            "attempts": [],
            "unavailable": [],
            "unavailable_count": None,
            "attempts_truncated": False,
            "unavailable_truncated": False,
        },
    )


def list_observers(**kwargs: Any) -> dict[str, Any]:
    """Both cards plus the deskbar pulses, from the short desk cache.

    A warm request with the same book and scan id does not rebuild either
    card. One observer failing to read still does not drop the other card.
    """
    from api.dashboard_cache import observers_cache_key, panel_cache

    key = observers_cache_key(
        telemetry_path=kwargs.get("telemetry_path"),
        state_path=kwargs.get("state_path"),
        status_path=kwargs.get("status_path"),
        db_path=kwargs.get("db_path"),
        config_path=kwargs.get("config_path"),
    )
    return panel_cache.fetch(
        "observers",
        key,
        lambda: _list_observers_uncached(**kwargs),
    )


def _list_observers_uncached(**kwargs: Any) -> dict[str, Any]:
    """Build both cards. Read-only. The cache in ``list_observers`` calls this."""
    cards: list[dict[str, Any]] = []
    for observer_id in OBSERVER_IDS:
        try:
            cards.append(observer_status(observer_id, **kwargs))
        except Exception as exc:
            cards.append(_failed_card(observer_id, exc))
    return {
        "ok": True,
        "observers": cards,
        "pulses": [_pulse(card) for card in cards],
    }
