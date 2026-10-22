"""Paper-only manual closes, picked up on the next exit check.

Drop a JSON file in ``data/close_requests/``. ``supervise_exits`` reads every
``*.json`` in that directory after stops and timeouts, and settles each open
paper position through ``TradingEngine._settle_paper_exit`` with reason
``manual_close``. The quote is taken before ``book_guard``. Settle takes
that lock itself after the observed-funding read, so the lock is not held
across the quote or the funding read.

A finished file is replaced by ``<name>.json.done`` carrying one result per
item: ``closed`` (with pnl), ``not_found``, ``already_closed``,
``opened_after_request``, or ``error``. A file that is not valid JSON, or
not the shape below, becomes ``<name>.json.error`` and the loop continues.
Live and testnet do not read the directory.

A symbol request is bound on first read to the position ids open for that
symbol at that moment. The binding, and the file mtime from before it is
written, are saved back into the same JSON before anything is settled. A
later retry or restart uses those ids and does not adopt a position opened
afterwards. A bound position opened more than one second after that
mtime is left open and recorded as ``opened_after_request``. The one
second absorbs filesystem mtime lagging the ledger clock, so a fill and
the file written in the same moment still close. Position ids named by the
operator are not rebound and are not subject to that mtime check.

Example (``data/close_requests/manual-close-xrp-chz-jup.json``)::

    {
      "request_id": "manual-close-xrp-chz-jup",
      "symbols": ["XRPUSDT", "CHZUSDT", "JUPUSDT"]
    }

Position ids are accepted as well, alone or with symbols::

    {
      "request_id": "manual-close-by-id",
      "position_ids": [101, 102]
    }

Write the file by renaming it into the directory so a reader never sees a
partial document. A request is processed once: the ``.json`` is removed
after ``.done`` is in place, and a restart will not settle it again.
"""

from __future__ import annotations

import json
import logging
import math
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select

from config.settings import PROJECT_ROOT, TradingMode, get_settings
from core.db import session_scope
from core.execution.paper import PaperBroker
from core.ledger.models import Position, PositionStatus, TradeRecord

logger = logging.getLogger(__name__)

PAPER_CLOSE_REQUESTS_DIR = PROJECT_ROOT / "data" / "close_requests"
MANUAL_CLOSE_REASON = "manual_close"

# One drain at a time. The 15s poll and the exit thread both call this.
# The loser skips the pass instead of writing a second result file.
_CLOSE_DRAIN = threading.Lock()

_OPEN = PositionStatus.OPEN.value
_CLOSED = PositionStatus.CLOSED.value


def process_paper_close_requests(engine: Any) -> int:
    """Settle pending paper close requests. Returns how many positions closed.

    A caller that finds a drain already in progress returns 0 and does not
    touch the directory. The in-progress drain writes the ``.done`` file.
    """
    if not _CLOSE_DRAIN.acquire(blocking=False):
        logger.info(
            "Paper close request drain already in progress; skipping this pass"
        )
        return 0
    try:
        return _drain_close_request_files(engine)
    finally:
        _CLOSE_DRAIN.release()


def _drain_close_request_files(engine: Any) -> int:
    """Read and settle the directory. Caller holds ``_CLOSE_DRAIN``.

    No-op unless the trading mode is paper and the broker is the paper
    broker. One bad file cannot prevent the rest of the directory, or the
    caller, from continuing.
    """
    if get_settings().trading_mode is not TradingMode.PAPER:
        return 0
    if not isinstance(getattr(engine, "broker", None), PaperBroker):
        return 0

    directory = Path(
        getattr(engine, "paper_close_requests_dir", None) or PAPER_CLOSE_REQUESTS_DIR
    )
    if not directory.is_dir():
        return 0

    try:
        paths = sorted(path for path in directory.glob("*.json") if path.is_file())
    except OSError:
        logger.exception("Could not list paper close requests in %s", directory)
        return 0

    closed = 0
    for path in paths:
        try:
            closed += _process_file(engine, path)
        except Exception:
            logger.exception("Paper close request %s failed", path.name)
            _reject(path, "internal error while processing")
    return closed


def _process_file(engine: Any, path: Path) -> int:
    done_path = Path(str(path) + ".done")
    if done_path.exists():
        # The result landed and the source survived a crash. Do not settle again.
        logger.info("Paper close request %s already completed; removing the json", path.name)
        _unlink(path)
        return 0

    payload, read_error = _read_json(path)
    if read_error is not None:
        _reject(path, read_error)
        return 0

    parsed = _parse_request(payload)
    if isinstance(parsed, str):
        request_id = payload.get("request_id") if isinstance(payload, dict) else None
        if not isinstance(request_id, str):
            request_id = None
        _reject(path, parsed, request_id=request_id)
        return 0

    request_id, targets = parsed
    if payload.get("symbols") and not isinstance(payload.get("symbol_bindings"), dict):
        payload = _attach_symbol_bindings(engine.ledger, payload, path)
        _atomic_write(path, payload)
        targets = _targets_from_payload(payload)
    elif isinstance(payload.get("symbol_bindings"), dict):
        targets = _targets_from_payload(payload)
    items: list[dict[str, Any]] = []
    closed = 0
    for target in targets:
        item = _settle_target(engine, request_id, target)
        items.append(item)
        if item["status"] == "closed":
            closed += 1

    body = {
        "request_id": request_id,
        "source": path.name,
        "processed_at": _now_iso(),
        "items": items,
    }
    try:
        _atomic_write(done_path, body)
    except Exception:
        logger.exception(
            "Paper close request %s settled but the .done file was not written; "
            "it will be recorded on the next exit check",
            path.name,
        )
        return closed
    _unlink(path)
    return closed


def _settle_target(engine: Any, request_id: str, target: dict[str, Any]) -> dict[str, Any]:
    if target.get("bound_absent"):
        located = _located(
            str(target.get("absent_status") or "not_found"),
            target.get("symbol"),
            target.get("position_id"),
            error=target.get("error"),
        )
        _log_item(request_id, located)
        return _public_item(located)

    located = _locate(engine.ledger, target)
    if _bound_position_is_too_new(target, located):
        item = _public_item(located, status="opened_after_request")
        _log_item(request_id, item)
        return item
    if located["status"] != "open":
        _log_item(request_id, located)
        return _public_item(located)

    quote = _quote(engine, str(located["symbol"]))
    if quote is None:
        item = _public_item(located, status="error", error="no quote")
        _log_item(request_id, item)
        return item

    # Price is already in hand. Re-check, then settle. ``_settle_paper_exit``
    # reads observed funding before it takes the book lock, and it uses this
    # quote instead of fetching another.
    located = _locate(engine.ledger, target)
    if _bound_position_is_too_new(target, located):
        item = _public_item(located, status="opened_after_request")
        _log_item(request_id, item)
        return item
    if located["status"] != "open":
        _log_item(request_id, located)
        return _public_item(located)
    try:
        closed_n = engine._settle_paper_exit(
            located["symbol"],
            MANUAL_CLOSE_REASON,
            at_mark=False,
            mark_price=quote,
        )
    except Exception as exc:
        logger.exception(
            "Manual paper close %s request %s failed",
            located["symbol"],
            request_id,
        )
        item = _public_item(located, status="error", error=str(exc) or "close failed")
        return item

    numbers = _trade_numbers(int(located["position_id"]))
    if numbers is not None and numbers["exit_reason"] == MANUAL_CLOSE_REASON:
        if closed_n:
            item = _public_item(
                located,
                status="closed",
                pnl=numbers["pnl"],
                fees=numbers["fees"],
                funding=numbers["funding"],
            )
        else:
            item = _public_item(located, status="already_closed")
        _log_item(request_id, item)
        return item
    if numbers is not None:
        item = _public_item(located, status="already_closed")
        _log_item(request_id, item)
        return item

    item = _public_item(located, status="error", error="close was not committed")
    _log_item(request_id, item)
    return item


def _quote(engine: Any, symbol: str) -> float | None:
    try:
        price = engine.broker.get_price(symbol)
    except Exception:
        logger.exception("Manual paper close %s quote failed", symbol)
        return None
    try:
        price_f = float(price)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(price_f) or price_f <= 0:
        return None
    return price_f


def _locate(ledger: Any, target: dict[str, Any]) -> dict[str, Any]:
    symbol = target.get("symbol")
    position_id = target.get("position_id")
    if position_id is not None:
        row = _position_by_id(int(position_id))
        if row is None or row["mode"] != ledger.mode:
            return _located("not_found", symbol, position_id)
        if symbol is not None and row["symbol"] != symbol:
            return _located(
                "error",
                symbol,
                position_id,
                error="symbol does not match position_id",
            )
        if row["status"] == _OPEN:
            return _located("open", row["symbol"], row["id"], opened_at=row.get("opened_at"))
        if row["status"] == _CLOSED:
            return _located(
                "already_closed",
                row["symbol"],
                row["id"],
                opened_at=row.get("opened_at"),
            )
        return _located(
            "error",
            row["symbol"],
            row["id"],
            error=f"position is {row['status']}",
            opened_at=row.get("opened_at"),
        )

    open_row = _open_by_symbol(ledger, str(symbol))
    if open_row is not None:
        return _located("open", open_row["symbol"], open_row["id"])
    latest = _latest_by_symbol(ledger, str(symbol))
    if latest is None:
        return _located("not_found", symbol, None)
    if latest["status"] == _CLOSED:
        return _located("already_closed", latest["symbol"], latest["id"])
    return _located(
        "error",
        latest["symbol"],
        latest["id"],
        error=f"position is {latest['status']}",
    )


def _located(
    status: str,
    symbol: str | None,
    position_id: int | None,
    *,
    error: str | None = None,
    opened_at: datetime | None = None,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "status": status,
        "symbol": symbol,
        "position_id": position_id,
    }
    if error is not None:
        item["error"] = error
    if opened_at is not None:
        item["opened_at"] = opened_at
    return item


def _public_item(located: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    item = {
        "symbol": located.get("symbol"),
        "position_id": located.get("position_id"),
        "status": located.get("status"),
    }
    if located.get("error"):
        item["error"] = located["error"]
    item.update(overrides)
    if item.get("status") != "error":
        item.pop("error", None)
    return item


def _log_item(request_id: str, item: dict[str, Any]) -> None:
    symbol = item.get("symbol") or "-"
    position_id = item.get("position_id")
    status = item.get("status")
    if status == "error":
        logger.error(
            "Manual paper close %s position %s request %s: error (%s)",
            symbol,
            position_id,
            request_id,
            item.get("error") or "",
        )
        return
    logger.info(
        "Manual paper close %s position %s request %s: %s",
        symbol,
        position_id,
        request_id,
        status,
    )


def _parse_request(payload: Any) -> tuple[str, list[dict[str, Any]]] | str:
    if not isinstance(payload, dict):
        return "request must be a JSON object"
    request_id = payload.get("request_id")
    if not isinstance(request_id, str) or not request_id.strip():
        return "request_id must be a non-empty string"
    if "symbols" in payload and not isinstance(payload.get("symbols"), list):
        return "symbols must be a list"
    if "position_ids" in payload and not isinstance(payload.get("position_ids"), list):
        return "position_ids must be a list"

    targets: list[dict[str, Any]] = []
    for symbol in payload.get("symbols") or []:
        if not isinstance(symbol, str) or not symbol.strip():
            return "symbols must be non-empty strings"
        targets.append({"symbol": symbol.strip(), "position_id": None})
    for raw_id in payload.get("position_ids") or []:
        if isinstance(raw_id, bool) or not isinstance(raw_id, int):
            return "position_ids must be integers"
        targets.append({"symbol": None, "position_id": int(raw_id)})
    if not targets:
        return "request lists no symbols or position ids"
    return request_id.strip(), targets


def _read_json(path: Path) -> tuple[Any, str | None]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, f"could not read request: {exc}"
    try:
        return json.loads(text), None
    except json.JSONDecodeError as exc:
        return None, f"malformed JSON: {exc.msg}"


def _reject(path: Path, reason: str, *, request_id: str | None = None) -> None:
    logger.error("Paper close request %s rejected: %s", path.name, reason)
    body = {
        "request_id": request_id,
        "source": path.name,
        "error": reason,
        "processed_at": _now_iso(),
    }
    try:
        _atomic_write(Path(str(path) + ".error"), body)
        _unlink(path)
    except Exception:
        logger.exception("Could not archive malformed close request %s", path.name)


def _atomic_write(dest: Path, body: dict[str, Any]) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    temporary = dest.with_name(f".{dest.name}.tmp")
    temporary.write_text(
        json.dumps(body, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, dest)


def _unlink(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        return


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _position_by_id(position_id: int) -> dict[str, Any] | None:
    with session_scope() as session:
        row = session.get(Position, int(position_id))
        if row is None:
            return None
        return _snap(row)


def _open_by_symbol(ledger: Any, symbol: str) -> dict[str, Any] | None:
    with session_scope() as session:
        row = session.scalars(
            select(Position).where(
                Position.symbol == symbol,
                Position.status == _OPEN,
                Position.mode == ledger.mode,
            )
        ).first()
        if row is None:
            return None
        return _snap(row)


def _latest_by_symbol(ledger: Any, symbol: str) -> dict[str, Any] | None:
    with session_scope() as session:
        row = session.scalars(
            select(Position)
            .where(Position.symbol == symbol, Position.mode == ledger.mode)
            .order_by(Position.id.desc())
        ).first()
        if row is None:
            return None
        return _snap(row)


def _snap(row: Position) -> dict[str, Any]:
    return {
        "id": int(row.id),
        "symbol": str(row.symbol),
        "status": str(row.status),
        "mode": str(row.mode),
        "opened_at": row.opened_at,
    }


def _attach_symbol_bindings(ledger: Any, payload: dict[str, Any], path: Path) -> dict[str, Any]:
    """Freeze each listed symbol to the position ids open right now.

    ``request_mtime`` is the file's mtime before this rewrite. A later read
    must keep using it: the rewrite itself moves the file's mtime.
    """
    request_mtime = path.stat().st_mtime
    bound: dict[str, Any] = {}
    for raw in payload.get("symbols") or []:
        symbol = str(raw).strip()
        opens = _open_rows(ledger, symbol)
        if opens:
            bound[symbol] = {"position_ids": [row["id"] for row in opens]}
            continue
        latest = _latest_by_symbol(ledger, symbol)
        if latest is None:
            bound[symbol] = {"position_ids": [], "status": "not_found"}
        elif latest["status"] == _CLOSED:
            bound[symbol] = {
                "position_ids": [],
                "status": "already_closed",
                "position_id": latest["id"],
            }
        else:
            bound[symbol] = {
                "position_ids": [],
                "status": "error",
                "position_id": latest["id"],
                "error": f"position is {latest['status']}",
            }
    updated = dict(payload)
    updated["symbol_bindings"] = {"request_mtime": request_mtime, "symbols": bound}
    return updated


def _targets_from_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Symbol targets come from the stored binding. Id targets are unchanged."""
    bindings = payload.get("symbol_bindings")
    if not isinstance(bindings, dict):
        parsed = _parse_request(payload)
        if isinstance(parsed, str):
            return []
        return parsed[1]
    symbols_map = bindings.get("symbols")
    if not isinstance(symbols_map, dict):
        symbols_map = {}
    try:
        request_mtime = float(bindings["request_mtime"])
    except (KeyError, TypeError, ValueError):
        request_mtime = None
    targets: list[dict[str, Any]] = []
    listed = payload.get("symbols") or list(symbols_map)
    for raw in listed:
        symbol = str(raw).strip()
        spec = symbols_map.get(symbol)
        if not isinstance(spec, dict):
            targets.append(
                {
                    "symbol": symbol,
                    "position_id": None,
                    "bound_absent": True,
                    "absent_status": "not_found",
                }
            )
            continue
        ids = spec.get("position_ids") or []
        if ids:
            for raw_id in ids:
                targets.append(
                    {
                        "symbol": symbol,
                        "position_id": int(raw_id),
                        "bound": True,
                        "request_mtime": request_mtime,
                    }
                )
        else:
            targets.append(
                {
                    "symbol": symbol,
                    "position_id": spec.get("position_id"),
                    "bound_absent": True,
                    "absent_status": spec.get("status") or "not_found",
                    "error": spec.get("error"),
                }
            )
    for raw_id in payload.get("position_ids") or []:
        targets.append({"symbol": None, "position_id": int(raw_id)})
    return targets


def _open_rows(ledger: Any, symbol: str) -> list[dict[str, Any]]:
    with session_scope() as session:
        rows = session.scalars(
            select(Position)
            .where(
                Position.symbol == symbol,
                Position.status == _OPEN,
                Position.mode == ledger.mode,
            )
            .order_by(Position.id)
        )
        return [_snap(row) for row in rows]


def _bound_position_is_too_new(target: dict[str, Any], located: dict[str, Any]) -> bool:
    """A symbol binding must not close a position opened after the request.

    A binding with no stored mtime fails closed: the position stays open.
    Operator-supplied position ids are not bindings and are never skipped here.
    """
    if not target.get("bound") or located.get("status") != "open":
        return False
    if target.get("request_mtime") is None:
        return True
    return _opened_after(located.get("opened_at"), target.get("request_mtime"))


def _opened_after(opened_at: datetime | None, request_mtime: Any) -> bool:
    """True when the position was opened after the request file.

    The ledger clock and the filesystem mtime are not one clock, and mtime
    can lag a fill that was recorded and then immediately followed by the
    file. A position counts as later only when its open time is more than
    one second past that mtime. A same-second open still closes.
    """
    if opened_at is None or request_mtime is None:
        return False
    try:
        mtime = float(request_mtime)
    except (TypeError, ValueError):
        return False
    moment = opened_at
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.timestamp() > mtime + 1.0


def _trade_numbers(position_id: int) -> dict[str, Any] | None:
    with session_scope() as session:
        trade = session.scalars(
            select(TradeRecord)
            .where(TradeRecord.position_id == int(position_id))
            .order_by(TradeRecord.id.desc())
        ).first()
        if trade is None:
            return None
        return {
            "pnl": float(trade.net_pnl),
            "fees": float(trade.fees),
            "funding": float(trade.funding),
            "exit_reason": str(trade.exit_reason or ""),
        }
