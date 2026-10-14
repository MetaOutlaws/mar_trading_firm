"""Read-only snapshot of the paper box for the status page.

State comes from the SQLite book, ``paper_cash.json``, the scan-summary log,
the Soko regime file, the last-cycle file, the bar-eval poll state, and the
paper log. Worker liveness is the age of those heartbeats. This module does
not read the paper pid file: that pid belongs to the paper container's PID
namespace, and pid 1 in this container is the status process itself.
The database is opened with SQLite ``mode=ro`` and ``PRAGMA query_only``.
On the SGP1 read-only state mount that open cannot create the WAL ``-shm``
file, so the same connection falls back to ``immutable=1`` (still read-only).
This module does not import the paper worker, does not call ``init_db``, and
does not construct a trading engine.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from sqlalchemy import inspect, select
from sqlalchemy.orm import selectinload, sessionmaker
from sqlalchemy.pool import NullPool

from api.desk_status import _sha_token, soko_display
from api.status_auth import configured_token
from config.settings import PROJECT_ROOT, get_settings
from core.ledger.models import EquitySnapshot, PaperCashEvent, Position, PositionStatus, TradeRecord

# Same files the paper process writes. Kept here so this module does not
# import the engine. tests/test_status_page.py locks the paths together.
LAST_CYCLE_PATH = PROJECT_ROOT / "data" / "last_cycle.json"
PAPER_BAR_STATE_PATH = PROJECT_ROOT / "data" / "paper_bar_eval_state.json"
PAPER_LOG_PATH = PROJECT_ROOT / "logs" / "paper_trading.log"

# The paper loop's scan interval is 900s. A cycle plus the following sleep
# can pass before the next heartbeat, so two intervals plus a short margin
# is the default stale line. ``STATUS_WORKER_STALE_SECONDS`` overrides it.
_WORKER_CYCLE_SECONDS = 900
_WORKER_STALE_MARGIN_SECONDS = 120
_DEFAULT_WORKER_STALE_SECONDS = _WORKER_CYCLE_SECONDS * 2 + _WORKER_STALE_MARGIN_SECONDS

logger = logging.getLogger(__name__)

# Logged once. The fallback is per connection; the warning should not be.
_logged_immutable_fallback = False

_ERROR_LINE = re.compile(r"\|\s*(ERROR|CRITICAL)\s*\|")
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)(status_page_token\s*[=:]\s*|authorization:\s*bearer\s+)\S+"
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return _as_utc(parsed)


def _age_seconds(stamp: datetime | None, now: datetime) -> int | None:
    if stamp is None:
        return None
    return int((_as_utc(now) - _as_utc(stamp)).total_seconds())


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return _as_utc(value).isoformat()


def redact(text: str, secret: str | None = None) -> str:
    """Remove the status token and bearer assignments from a display string."""
    cleaned = text
    token = secret if secret is not None else configured_token()
    if token:
        cleaned = cleaned.replace(token, "[redacted]")
    cleaned = _SECRET_ASSIGNMENT.sub(r"\1[redacted]", cleaned)
    cleaned = re.sub(r"://[^@\s/]+@", "://[redacted]@", cleaned)
    return cleaned[:500]


def _public_error(exc: Exception) -> str:
    return redact(f"{type(exc).__name__}: {exc}")


def sqlite_path_from_url(database_url: str) -> Path | None:
    """Absolute SQLite path. Does not create the file or its parent."""
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        return None
    raw = database_url[len(prefix) :]
    if raw.startswith("file:"):
        body = raw[5:].split("?", 1)[0]
        return Path(body)
    path = Path(raw)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


def _readonly_filesystem(exc: sqlite3.OperationalError) -> bool:
    """True when SQLite failed because it could not write next to the file."""
    message = str(exc).lower()
    return "readonly" in message or "unable to open database file" in message


def _connect_immutable_sqlite(path: Path) -> sqlite3.Connection:
    """Read-only open that does not create the WAL ``-shm`` file."""
    global _logged_immutable_fallback
    conn = sqlite3.connect(
        f"file:{path}?mode=ro&immutable=1",
        uri=True,
        check_same_thread=False,
    )
    conn.execute("PRAGMA query_only=ON")
    if not _logged_immutable_fallback:
        logger.warning(
            "status database opened immutable and read-only; "
            "the state directory is not writable"
        )
        _logged_immutable_fallback = True
    return conn


def _connect_readonly_sqlite(path: Path) -> sqlite3.Connection:
    """Open ``path`` so the caller cannot write it.

    ``mode=ro`` takes the WAL read lock, which has to create or update the
    ``-shm`` file next to the database. That is the right open when the
    state directory is writable. ``connect()`` can return before that write
    happens; the ``sqlite_master`` probe is what forces it. The SGP1 compose
    file mounts ``/data/state/data`` at ``/app/data:ro``, and the probe then
    fails (``unable to open database file`` or ``attempt to write a readonly
    database``). ``immutable=1`` does not create ``-shm`` and does not lock,
    so a new connection can still see committed frames on that mount.
    ``PRAGMA query_only`` rejects writes on either open.
    """
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)
    except sqlite3.OperationalError as exc:
        if not _readonly_filesystem(exc):
            raise
        return _connect_immutable_sqlite(path)
    try:
        conn.execute("PRAGMA query_only=ON")
        # A real read, not ``SELECT 1``. WAL tries to create ``-shm`` here.
        conn.execute("SELECT name FROM sqlite_master LIMIT 1")
    except sqlite3.OperationalError as exc:
        conn.close()
        if not _readonly_filesystem(exc):
            raise
        return _connect_immutable_sqlite(path)
    return conn


def readonly_engine(database_url: str | None = None):
    """Engine that cannot write.

    SQLite uses a ``mode=ro`` URI plus ``PRAGMA query_only``, and falls
    back to an immutable read-only open when the state directory cannot
    host a WAL index. Other dialects set ``default_transaction_read_only``
    on connect. ``NullPool`` so a status request does not keep a
    writer-capable pool around.
    """
    from sqlalchemy import create_engine, event

    url = database_url if database_url is not None else get_settings().database_url
    path = sqlite_path_from_url(url)
    if path is not None:
        if not path.exists():
            raise FileNotFoundError(f"database file is missing: {path}")

        def creator() -> sqlite3.Connection:
            return _connect_readonly_sqlite(path)

        return create_engine("sqlite://", creator=creator, poolclass=NullPool, future=True)

    engine = create_engine(url, poolclass=NullPool, future=True)

    @event.listens_for(engine, "connect")
    def _read_only(dbapi_connection, _record) -> None:  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        cursor.execute("SET default_transaction_read_only = ON")
        cursor.close()

    return engine


def _sha_payload(
    token: str | None,
    source: str,
    path: str | None,
    checked: list[str],
) -> dict[str, Any]:
    return {
        "sha": token,
        "short": token[:12] if token else None,
        "source": source,
        "path": path,
        "checked": checked,
    }


def _read_sha_file(path: Path) -> str | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    return _sha_token(text)


def head_candidates(root: Path) -> list[Path]:
    """GIT_SHA files, in order, after the ``GIT_SHA`` environment variable."""
    return [Path("/app/GIT_SHA"), root / "GIT_SHA"]


def deployed_sha_candidates(root: Path) -> list[Path]:
    """DEPLOYED_SHA files. ``/app/data/DEPLOYED_SHA`` is the container path."""
    return [Path("/app/data/DEPLOYED_SHA"), root / "data" / "DEPLOYED_SHA"]


def _git_rev_parse(root: Path) -> str | None:
    try:
        sha = subprocess.check_output(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            text=True,
            timeout=2,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.SubprocessError):
        return None
    return _sha_token(sha)


def git_status(root: Path | None = None) -> dict[str, Any]:
    """HEAD and DEPLOYED_SHA, each resolved on its own.

    HEAD is ``GIT_SHA`` from the environment, then a ``GIT_SHA`` file, then
    ``git rev-parse HEAD``. DEPLOYED_SHA is only the deployed-sha file. One
    value is never copied into the other field.
    """
    repo = root or PROJECT_ROOT
    head_files = head_candidates(repo)
    head_checked = ["env:GIT_SHA", *[str(path) for path in head_files], f"git:{repo}"]
    env_sha = _sha_token(os.environ.get("GIT_SHA", ""))
    head: dict[str, Any]
    if env_sha:
        head = _sha_payload(env_sha, "env", None, head_checked)
        head["env"] = "GIT_SHA"
    else:
        head = _sha_payload(None, "missing", None, head_checked)
        for path in head_files:
            token = _read_sha_file(path)
            if token:
                head = _sha_payload(token, "file", str(path), head_checked)
                break
        else:
            git_sha = _git_rev_parse(repo)
            if git_sha:
                head = _sha_payload(git_sha, "git", str(repo), head_checked)
            else:
                head = _sha_payload(None, "unavailable", None, head_checked)

    deployed_files = deployed_sha_candidates(repo)
    deployed_checked = [str(path) for path in deployed_files]
    deployed = _sha_payload(None, "missing", None, deployed_checked)
    for path in deployed_files:
        token = _read_sha_file(path)
        if token:
            deployed = _sha_payload(token, "file", str(path), deployed_checked)
            break
    return {"head": head, "deployed_sha": deployed}


def worker_stale_seconds() -> int:
    """Seconds after which a heartbeat means the paper worker is dead.

    Default is two 900s cycles plus 120s (1920). ``STATUS_WORKER_STALE_SECONDS``
    overrides that. Blank, non-integer, and non-positive values keep the default
    so a bad setting does not take the page down.
    """
    raw = os.environ.get("STATUS_WORKER_STALE_SECONDS", "").strip()
    if not raw:
        return _DEFAULT_WORKER_STALE_SECONDS
    try:
        value = int(raw)
    except ValueError:
        return _DEFAULT_WORKER_STALE_SECONDS
    if value < 1:
        return _DEFAULT_WORKER_STALE_SECONDS
    return value


def _poll_heartbeat(path: Path) -> datetime | None:
    """Newest ``evaluated_at`` in the bar-eval state the 15s poll writes."""
    payload = _read_json_object(path)
    if not isinstance(payload, dict):
        return None
    sleeves = payload.get("sleeves")
    if not isinstance(sleeves, dict):
        return None
    newest: datetime | None = None
    for row in sleeves.values():
        if not isinstance(row, dict):
            continue
        stamp = _parse_time(row.get("evaluated_at"))
        if stamp is None:
            continue
        if newest is None or stamp > newest:
            newest = stamp
    return newest


def _heartbeat_candidates() -> list[tuple[str, datetime]]:
    """Timestamps the paper process writes into the read-only state dir."""
    from firm.scan_summary_log import LOG_PATH

    found: list[tuple[str, datetime]] = []
    cycle = _read_json_object(LAST_CYCLE_PATH)
    if isinstance(cycle, dict):
        stamp = _parse_time(cycle.get("started_at"))
        if stamp is not None:
            found.append(("last_cycle", stamp))
    scan = read_last_json_object(LOG_PATH)
    if isinstance(scan, dict):
        stamp = _parse_time(scan.get("logged_at"))
        if stamp is not None:
            found.append(("scan_summary", stamp))
    poll = _poll_heartbeat(PAPER_BAR_STATE_PATH)
    if poll is not None:
        found.append(("poll", poll))
    return found


def worker_status(now: datetime | None = None) -> dict[str, Any]:
    """Heartbeat age, last cycle clock, and recent errors. Read-only.

    ``alive`` is true only when the newest heartbeat is younger than
    ``worker_stale_seconds()``. No heartbeat is ``unknown`` and not alive.
    A pid file is ignored: inside this container that number is not the
    paper process.
    """
    moment = _as_utc(now or _utcnow())
    cycle = _read_json_object(LAST_CYCLE_PATH)
    cycle_started = _parse_time(cycle.get("started_at")) if isinstance(cycle, dict) else None
    errors = _recent_errors(cycle if isinstance(cycle, dict) else None)
    if cycle_started is not None:
        last_cycle_at = _iso(cycle_started)
    elif isinstance(cycle, dict) and isinstance(cycle.get("started_at"), str):
        last_cycle_at = cycle["started_at"]
    else:
        last_cycle_at = None

    threshold = worker_stale_seconds()
    candidates = _heartbeat_candidates()
    if not candidates:
        heartbeat_at: datetime | None = None
        source: str | None = None
        age: int | None = None
        state = "unknown"
        alive = False
    else:
        source, heartbeat_at = max(candidates, key=lambda item: item[1])
        age = _age_seconds(heartbeat_at, moment)
        # A timestamp slightly ahead of this clock is still a fresh write.
        if age is not None and age < 0:
            age = 0
        alive = age is not None and age < threshold
        state = "alive" if alive else "dead"
    return {
        "alive": alive,
        "state": state,
        "last_heartbeat_at": _iso(heartbeat_at),
        "age_seconds": age,
        "stale_after_seconds": threshold,
        "heartbeat_source": source,
        "last_cycle_at": last_cycle_at,
        "last_cycle_age_seconds": _age_seconds(cycle_started, moment),
        "halted": bool(cycle.get("halted")) if isinstance(cycle, dict) else None,
        "halt_reason": cycle.get("halt_reason") if isinstance(cycle, dict) else None,
        "recent_errors": errors,
        "cycle_path": str(LAST_CYCLE_PATH),
        "log_path": str(PAPER_LOG_PATH),
    }


def _recent_errors(cycle: dict[str, Any] | None, *, limit: int = 20) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if isinstance(cycle, dict):
        for item in cycle.get("errors") or []:
            text = item if isinstance(item, str) else str(item)
            text = redact(text).strip()
            if text:
                rows.append({"source": "last_cycle", "message": text})
    for line in _tail_error_lines(PAPER_LOG_PATH):
        rows.append({"source": "paper_log", "message": redact(line).strip()})
    return rows[-limit:]


def _tail_error_lines(path: Path, *, max_bytes: int = 256_000, limit: int = 20) -> list[str]:
    if not path.is_file():
        return []
    try:
        size = path.stat().st_size
        with path.open("rb") as handle:
            if size > max_bytes:
                handle.seek(size - max_bytes)
                handle.readline()
            raw = handle.read()
    except OSError:
        return []
    found: list[str] = []
    for line in raw.decode("utf-8", errors="replace").splitlines():
        if _ERROR_LINE.search(line):
            found.append(line.strip())
    return found[-limit:]


def _read_json_object(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def read_last_json_object(path: Path, *, max_bytes: int = 1_000_000) -> dict[str, Any] | None:
    """Last JSON object in a JSONL file. Reads from the end of a long log."""
    if not path.is_file():
        return None
    try:
        size = path.stat().st_size
        with path.open("rb") as handle:
            if size > max_bytes:
                handle.seek(size - max_bytes)
                handle.readline()
            raw = handle.read()
    except OSError:
        return None
    for line in reversed(raw.decode("utf-8", errors="replace").splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return None


def last_scan_summary() -> dict[str, Any]:
    """Latest #115/#116 scan card from the append-only summary log."""
    from firm.scan_summary_log import LOG_PATH

    record = read_last_json_object(LOG_PATH)
    if record is None:
        return {"present": False, "path": str(LOG_PATH), "summary": None}
    payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
    return {
        "present": True,
        "path": str(LOG_PATH),
        "logged_at": record.get("logged_at"),
        "action": record.get("action"),
        "title": record.get("title"),
        "rationale": record.get("rationale"),
        "summary": payload.get("summary"),
        "scan_type": payload.get("scan_type"),
        "bar_time": payload.get("bar_time"),
        "signals": payload.get("signals"),
        "entries_opened": payload.get("entries_opened"),
        "fills": payload.get("fills"),
        "exits": payload.get("exits"),
        "rejection_counts": payload.get("rejection_counts"),
        "dedupe_key": payload.get("dedupe_key"),
    }


def _strategy_fields(
    position: Any,
    *,
    strategy: str = "",
    entry_indicators: dict | None = None,
) -> dict[str, str]:
    """#119 blotter label. The helper only reads strings already stored."""
    from api.app import blotter_strategy_fields

    adapter = SimpleNamespace(
        position=position,
        strategy=strategy or getattr(position, "strategy", "") or "",
        entry_indicators=entry_indicators if entry_indicators is not None else {},
    )
    return blotter_strategy_fields(adapter)


def _position_row(position: Position) -> dict[str, Any]:
    identity = _strategy_fields(
        position,
        strategy=position.strategy,
        entry_indicators=position.entry_indicators or {},
    )
    return {
        "id": position.id,
        "symbol": position.symbol,
        "side": position.side,
        "quantity": position.quantity,
        "entry_price": position.entry_price,
        "notional": position.notional,
        "strategy": position.strategy,
        "timeframe": position.timeframe or "",
        "opened_at": _iso(position.opened_at),
        "strategy_id": identity["strategy_id"],
        "sleeve": identity["sleeve"],
        "strategy_version": identity["strategy_version"],
        "strategy_label": identity["strategy_label"],
    }


def _trade_row(trade: TradeRecord) -> dict[str, Any]:
    identity = _strategy_fields(
        trade.position,
        strategy=trade.strategy,
        entry_indicators=trade.entry_indicators or {},
    )
    return {
        "id": trade.id,
        "symbol": trade.symbol,
        "side": trade.side,
        "quantity": trade.quantity,
        "notional": trade.notional,
        "entry_price": trade.entry_price,
        "exit_price": trade.exit_price,
        "net_pnl": trade.net_pnl,
        "exit_reason": trade.exit_reason,
        "strategy": trade.strategy,
        "strategy_id": identity["strategy_id"],
        "sleeve": identity["sleeve"],
        "strategy_version": identity["strategy_version"],
        "strategy_label": identity["strategy_label"],
        "mode": trade.mode,
        "entry_time": _iso(trade.entry_time),
        "exit_time": _iso(trade.exit_time),
    }


def _equity_row(row: EquitySnapshot | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "recorded_at": _iso(row.recorded_at),
        "equity": row.equity,
        "realised_pnl": row.realised_pnl,
        "unrealised_pnl": row.unrealised_pnl,
        "exposure": row.exposure,
        "open_positions": row.open_positions,
        "peak_equity": row.peak_equity,
        "drawdown_pct": row.drawdown_pct,
    }


def _empty_equity_cash(error: str | None = None) -> dict[str, Any]:
    return {
        "journal_present": False,
        "cash": None,
        "contributed_capital": None,
        "closed_realised_pnl": None,
        "journal_path": None,
        "equity_snapshot": None,
        "error": error,
    }


def _cash_block(durable_events: list[dict[str, Any]]) -> dict[str, Any]:
    """Replay the cash journal in memory. Does not call ``PaperCashStore.record``."""
    from core.execution.paper_cash import (
        PAPER_CASH_PATH,
        PaperCashStore,
        merge_cash_events,
        replay_events,
    )

    file_events: list[dict[str, Any]] = []
    if PAPER_CASH_PATH.exists():
        file_events = PaperCashStore(PAPER_CASH_PATH).events()
    if not PAPER_CASH_PATH.exists() and not durable_events:
        block = _empty_equity_cash()
        block["journal_path"] = str(PAPER_CASH_PATH)
        return block
    state = replay_events(merge_cash_events(file_events, durable_events))
    return {
        "journal_present": True,
        "cash": state.cash,
        "contributed_capital": state.contributed_capital,
        "closed_realised_pnl": state.realised_pnl,
        "journal_path": str(PAPER_CASH_PATH),
        "equity_snapshot": None,
        "error": None,
    }


def _read_book(mode: str, *, trade_limit: int = 20) -> dict[str, Any]:
    """Positions, trades, the latest equity snapshot, and durable cash events."""
    engine = readonly_engine()
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    session = factory()
    try:
        positions = list(
            session.scalars(
                select(Position).where(
                    Position.status == PositionStatus.OPEN.value,
                    Position.mode == mode,
                )
            )
        )
        trades = list(
            session.scalars(
                select(TradeRecord)
                .options(selectinload(TradeRecord.position))
                .where(TradeRecord.mode == mode)
                .order_by(TradeRecord.exit_time.desc())
                .limit(trade_limit)
            )
        )
        snapshot = session.scalars(
            select(EquitySnapshot)
            .where(EquitySnapshot.mode == mode)
            .order_by(EquitySnapshot.recorded_at.desc())
            .limit(1)
        ).first()
        durable: list[dict[str, Any]] = []
        tables = set(inspect(session.get_bind()).get_table_names())
        rows = []
        if "paper_cash_events" in tables:
            rows = session.scalars(select(PaperCashEvent).order_by(PaperCashEvent.id)).all()
        for row in rows:
            if isinstance(row.payload, dict) and row.payload.get("event_id"):
                durable.append(dict(row.payload))
        # Build plain dicts before the session closes.
        return {
            "database": "ok",
            "open_positions": [_position_row(row) for row in positions],
            "recent_trades": [_trade_row(row) for row in trades],
            "equity_snapshot": _equity_row(snapshot),
            "durable_events": durable,
            "error": None,
        }
    finally:
        session.rollback()
        session.close()
        engine.dispose()


def build_snapshot(*, trade_limit: int = 20, now: datetime | None = None) -> dict[str, Any]:
    """Full status document. One section failing leaves the others in place."""
    moment = _as_utc(now or _utcnow())
    mode = get_settings().trading_mode.value
    try:
        book = _read_book(mode, trade_limit=trade_limit)
    except Exception as exc:
        logger.error("status book read failed (%s)", type(exc).__name__)
        book = {
            "database": "unavailable",
            "open_positions": [],
            "recent_trades": [],
            "equity_snapshot": None,
            "durable_events": [],
            "error": _public_error(exc),
        }

    try:
        equity_cash = _cash_block(book.get("durable_events") or [])
    except Exception as exc:
        equity_cash = _empty_equity_cash(_public_error(exc))
    equity_cash["equity_snapshot"] = book.get("equity_snapshot")
    equity_cash.pop("durable_events", None)

    try:
        scan = last_scan_summary()
    except Exception as exc:
        scan = {"present": False, "summary": None, "error": _public_error(exc)}

    try:
        regime = soko_display(now=moment)
    except Exception as exc:
        regime = {"label": None, "source": "unreadable", "error": _public_error(exc)}

    try:
        git = git_status()
    except Exception as exc:
        git = {
            "head": {"sha": None, "source": "unavailable"},
            "deployed_sha": {"sha": None},
            "error": _public_error(exc),
        }

    try:
        worker = worker_status(now=moment)
    except Exception as exc:
        worker = {
            "alive": False,
            "state": "unknown",
            "last_heartbeat_at": None,
            "age_seconds": None,
            "last_cycle_at": None,
            "recent_errors": [],
            "error": _public_error(exc),
        }

    database = book.get("database") or "unavailable"
    if database == "ok" and worker.get("alive"):
        health_status = "ok"
    else:
        health_status = "degraded"
    if worker.get("alive"):
        worker_health = "alive"
    elif worker.get("state") == "unknown":
        worker_health = "unknown"
    else:
        worker_health = "down"
    health = {
        "status": health_status,
        "database": database,
        "worker": worker_health,
        "read_only": True,
        "error": book.get("error"),
    }
    return {
        "service": "sgp1-status",
        "read_only": True,
        "generated_at": _iso(moment),
        "mode": mode,
        "health": health,
        "equity_cash": equity_cash,
        "open_positions": book.get("open_positions") or [],
        "recent_trades": book.get("recent_trades") or [],
        "last_scan_summary": scan,
        "regime": regime,
        "git": git,
        "worker": worker,
    }
