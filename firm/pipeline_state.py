"""Persisted continuity state: tickets, auto-advances, dropped events, ledger pointer.

Seats must not cache their own copy of pipeline stage. This file plus
`data/research_jobs.json` is the record. Disagreement with a seat report
is an integrity failure.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from config.settings import PROJECT_ROOT

STATE_PATH = PROJECT_ROOT / "data" / "pipeline_state.json"


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _empty() -> dict[str, Any]:
    return {
        "updated_at": utcnow_iso(),
        "current_family": "",
        "current_stage": "",
        "current_job_id": None,
        "last_updated_by": "",
        "tickets": [],
        "dropped_events": [],
        "auto_advances": [],
        "consecutive_auto_rejects": 0,
        "circuit_breaker_tripped": False,
        "last_slot_free_at": None,
        "idle_since_slot_free_seconds": 0.0,
        "events": [],
        "slot_idle_log": [],
    }


def load_state() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return _empty()
    try:
        raw = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return _empty()
    if not isinstance(raw, dict):
        return _empty()
    base = _empty()
    base.update(raw)
    return base


def save_state(state: dict[str, Any]) -> None:
    state["updated_at"] = utcnow_iso()
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def set_ledger_pointer(
    *,
    family: str,
    stage: str,
    job_id: int | None,
    updated_by: str,
) -> None:
    state = load_state()
    state["current_family"] = family
    state["current_stage"] = stage
    state["current_job_id"] = job_id
    state["last_updated_by"] = updated_by
    save_state(state)


def record_dropped_event(event: str, detail: str, source: str) -> None:
    state = load_state()
    rows = list(state.get("dropped_events") or [])
    rows.append(
        {
            "at": utcnow_iso(),
            "event": event,
            "detail": detail,
            "source": source,
        }
    )
    state["dropped_events"] = rows[-200:]
    save_state(state)


def record_auto_advance(entry: dict[str, Any]) -> None:
    state = load_state()
    rows = list(state.get("auto_advances") or [])
    rows.append({"at": utcnow_iso(), **entry})
    state["auto_advances"] = rows[-200:]
    save_state(state)


def record_event(event: str, payload: dict[str, Any]) -> None:
    state = load_state()
    rows = list(state.get("events") or [])
    rows.append({"at": utcnow_iso(), "event": event, **payload})
    state["events"] = rows[-200:]
    save_state(state)


def upsert_ticket(ticket: dict[str, Any]) -> dict[str, Any]:
    """Open or refresh a watchdog ticket keyed by invariant id. Persist until resolved."""
    state = load_state()
    tickets = list(state.get("tickets") or [])
    key = str(ticket.get("id") or "")
    now = utcnow_iso()
    found = False
    for row in tickets:
        if str(row.get("id") or "") == key:
            row["last_seen_at"] = now
            row["occurrence_count"] = int(row.get("occurrence_count") or 1) + 1
            row["detail"] = ticket.get("detail") or row.get("detail")
            row["next_action"] = ticket.get("next_action") or row.get("next_action")
            row["idle_seconds"] = ticket.get("idle_seconds", row.get("idle_seconds"))
            row["status"] = "open"
            found = True
            break
    if not found:
        tickets.append(
            {
                **ticket,
                "status": "open",
                "created_at": now,
                "last_seen_at": now,
                "occurrence_count": 1,
            }
        )
    state["tickets"] = tickets
    save_state(state)
    return ticket


def resolve_ticket(ticket_id: str) -> bool:
    state = load_state()
    tickets = list(state.get("tickets") or [])
    changed = False
    for row in tickets:
        if str(row.get("id") or "") == ticket_id and row.get("status") != "resolved":
            row["status"] = "resolved"
            row["resolved_at"] = utcnow_iso()
            changed = True
    if changed:
        state["tickets"] = tickets
        save_state(state)
    return changed


def open_tickets() -> list[dict[str, Any]]:
    return [t for t in (load_state().get("tickets") or []) if t.get("status") != "resolved"]


def dropped_event_count() -> int:
    return len(load_state().get("dropped_events") or [])
