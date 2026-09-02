"""Event names and overdue tracking. Handlers live in continuity so a free
walk-forward slot can launch in the same tick, not on a seat's next cadence.
"""

from __future__ import annotations

from typing import Any

from config.pipeline import EVENT_OWNERS
from firm.pipeline_state import record_event, upsert_ticket


def emit(event: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Record that an event fired. Same-tick handlers are called by continuity."""
    body = dict(payload or {})
    owner, sla_s = EVENT_OWNERS.get(event, ("desk_head", 300))
    record_event(event, {"owner": owner, "sla_seconds": sla_s, **body})
    return {"event": event, "owner": owner, "sla_seconds": sla_s}


def mark_event_overdue(event: str, detail: str) -> None:
    owner, sla_s = EVENT_OWNERS.get(event, ("desk_head", 300))
    upsert_ticket(
        {
            "id": f"event_overdue:{event}",
            "invariant": "event_sla",
            "owner": owner,
            "severity": "warning",
            "sla": f"{sla_s}s",
            "next_action": f"Handle {event} now",
            "detail": detail,
        }
    )
