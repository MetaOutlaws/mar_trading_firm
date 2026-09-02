"""Operator-approved novel sleeves become a Cursor coding ticket.

Inbox approve does not LLM-write Python. It writes the brief onto a queue
that the next Cursor agent is required to implement. Walk-forward starts
when the sleeve lands in the registry.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config.settings import PROJECT_ROOT

logger = logging.getLogger(__name__)

QUEUE_PATH = PROJECT_ROOT / "data" / "cursor_coding_queue.json"
INBOX_DIR = PROJECT_ROOT / "research" / "coding_inbox"
NOW_PATH = INBOX_DIR / "NOW.md"


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load() -> dict[str, Any]:
    if not QUEUE_PATH.exists():
        return {"jobs": []}
    try:
        raw = json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"jobs": []}
    if not isinstance(raw, dict):
        return {"jobs": []}
    raw.setdefault("jobs", [])
    return raw


def _save(data: dict[str, Any]) -> None:
    QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = utcnow_iso()
    QUEUE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def enqueue_approved(
    *,
    family: str,
    brief: str,
    brief_path: str,
    proposal_id: int | None = None,
) -> dict[str, Any]:
    """Record that the operator approved this brief for Cursor to implement."""
    data = _load()
    jobs = list(data.get("jobs") or [])
    for row in jobs:
        if str(row.get("family")) == family and row.get("status") == "approved":
            row["brief"] = brief
            row["brief_path"] = brief_path
            row["proposal_id"] = proposal_id
            row["approved_at"] = utcnow_iso()
            data["jobs"] = jobs
            _save(data)
            _write_now(row)
            return row
    job = {
        "family": family,
        "status": "approved",
        "brief": brief,
        "brief_path": brief_path,
        "proposal_id": proposal_id,
        "approved_at": utcnow_iso(),
        "done_at": None,
    }
    jobs.append(job)
    data["jobs"] = jobs
    _save(data)
    _write_now(job)
    logger.info("Handed %s to Cursor coding queue", family)
    return job


def pending_jobs() -> list[dict[str, Any]]:
    return [j for j in (_load().get("jobs") or []) if j.get("status") == "approved"]


def next_pending() -> dict[str, Any] | None:
    waiting = pending_jobs()
    return waiting[0] if waiting else None


def enqueue_next_novel_if_catalog_empty() -> dict[str, Any] | None:
    """Keep one novel Cursor ticket so coding runs beside walk-forward.

    Paper-to-live stays an Inbox gate. Research coding does not wait for the
    catalog to drain or for a Gemini call.
    """
    if pending_jobs():
        return None
    from firm.sleeve_factory import ready_novel_specs, write_coding_request

    specs = ready_novel_specs()
    if not specs:
        return None
    spec = specs[0]
    path = write_coding_request(spec)
    md_path = path.with_suffix(".md")
    brief = md_path.read_text(encoding="utf-8") if md_path.exists() else spec.summary
    return enqueue_approved(
        family=spec.name,
        brief=brief,
        brief_path=str(md_path),
    )


def mark_done(family: str) -> None:
    data = _load()
    for row in data.get("jobs") or []:
        if str(row.get("family")) == family and row.get("status") == "approved":
            row["status"] = "done"
            row["done_at"] = utcnow_iso()
    _save(data)
    try:
        from firm.research_catalog import land_coded_family

        land_coded_family(family, added_by="cursor")
    except Exception:
        logger.exception("Could not land %s on the research catalog after coding", family)
    try:
        from firm.continuity import fill_walk_forward_slots

        fill_walk_forward_slots(source="cursor_coded")
    except Exception:
        logger.exception("Could not start walk-forward after coding %s", family)
    try:
        enqueue_next_novel_if_catalog_empty()
    except Exception:
        logger.exception("Could not queue the next novel after coding %s", family)
    nxt = next_pending()
    if nxt:
        _write_now(nxt)
    elif NOW_PATH.exists():
        NOW_PATH.write_text(
            "# No approved coding ticket\n\nInbox is the gate. Approve a novel brief to fill this file.\n",
            encoding="utf-8",
        )


def agent_instruction() -> str:
    """Text injected into a Cursor session when an approved ticket is waiting."""
    job = next_pending()
    if job is None:
        return ""
    family = str(job.get("family") or "")
    brief = str(job.get("brief") or "")
    path = str(job.get("brief_path") or f"research/coding_requests/{family}.md")
    return (
        "OPERATOR APPROVED A NOVEL SLEEVE. Implement it in this session. "
        "Do not ask whether to proceed. Do not rewrite a rejected family and rename it.\n\n"
        f"Family: `{family}`\n"
        f"Brief file: `{path}`\n\n"
        f"{brief}\n\n"
        f"When `core/strategy/{family}.py` is registered, mark the Cursor coding "
        "queue item done (firm.cursor_coding.mark_done) so walk-forward can start."
    )


def _write_now(job: dict[str, Any]) -> None:
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    family = str(job.get("family") or "")
    NOW_PATH.write_text(
        "\n".join(
            [
                f"# Approved for Cursor: `{family}`",
                "",
                "The operator approved this brief in Inbox. Implement it now.",
                "",
                str(job.get("brief") or ""),
                "",
                f"Source: `{job.get('brief_path') or ''}`",
                "",
            ]
        ),
        encoding="utf-8",
    )
