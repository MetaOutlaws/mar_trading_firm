"""Floor-tab process view: who owns each stage, what is now, what is next.

Display only. Does not start walk-forwards, write approvals, or change
paper-to-live gates. The validator job list stays on Research.
"""

from __future__ import annotations

import re
from typing import Any

# CEO-approved Floor strip. Owner names are desk labels, not LLM seat ids.
WORKFLOW_STAGES: tuple[dict[str, str], ...] = (
    {"id": "hyp", "label": "Hypothesis", "owner": "Shumba"},
    {"id": "score", "label": "Score", "owner": "Munha"},
    {"id": "coo", "label": "COO ONE", "owner": "Marcus"},
    {"id": "ceo", "label": "CEO YES", "owner": "Brian"},
    {"id": "stamp", "label": "Stamp", "owner": "Garwe"},
    {"id": "code", "label": "Code", "owner": "Chiremba"},
    {"id": "walk", "label": "Walk", "owner": "Mukanya"},
    {"id": "harvest", "label": "Harvest", "owner": "Mukanya"},
    {"id": "review", "label": "Review", "owner": "Marcus"},
    {"id": "book", "label": "Book", "owner": "paper"},
    {"id": "activate", "label": "Activate", "owner": "Soko"},
)

_STAGE_IDS = tuple(s["id"] for s in WORKFLOW_STAGES)
_PAIR_RATIO = re.compile(r"(\d+)\s*/\s*(\d+)")


def workflow_snapshot(
    *,
    jobs: list[dict[str, Any]] | None = None,
    remaining: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Operator-facing firm process. Safe to call on every desk poll."""
    from config.settings import get_settings
    from config.universe import get_universe
    from firm.research_jobs import (
        _headline_job,
        open_code_mandates,
        paper_scan_family,
        refresh_job_liveness,
        walkforward_progress,
    )

    if jobs is None:
        jobs = refresh_job_liveness()
    if remaining is None:
        from firm.research_catalog import remaining_hypotheses

        remaining = remaining_hypotheses(jobs)

    if hasattr(get_universe, "cache_clear"):
        get_universe.cache_clear()
    universe = get_universe()
    settings = get_settings()
    mode = str(getattr(settings.trading_mode, "value", settings.trading_mode) or "paper")
    live_off = mode != "live"

    latest = _headline_job(jobs)
    mandates = open_code_mandates()
    inbox = _inbox_rows()
    strategy_inbox = [p for p in inbox if p.get("kind") == "strategy"]
    code_inbox = [
        p
        for p in inbox
        if isinstance(p.get("payload"), dict) and p["payload"].get("action") == "code_family"
    ]
    review_inbox = [
        p
        for p in inbox
        if isinstance(p.get("payload"), dict) and p["payload"].get("action") == "catalog_review"
    ]
    quant_running = _quant_is_running()
    walk_bar = walkforward_progress(latest) if latest else {
        "progress": None,
        "progress_label": "",
        "stalled": False,
    }
    stalled_walk = bool(
        latest
        and str(latest.get("status") or "") in {"running", "queued"}
        and walk_bar.get("stalled")
    )

    idx, live_state = _pointer(
        latest=latest,
        walk_bar=walk_bar,
        mandates=mandates,
        strategy_inbox=strategy_inbox,
        code_inbox=code_inbox,
        review_inbox=review_inbox,
        quant_running=quant_running,
        remaining=remaining,
    )
    family = _current_family(latest, mandates, remaining)
    stages = _paint_stages(
        idx,
        live_state,
        family=family,
        latest=latest,
        stalled_walk=stalled_walk,
        live_off=live_off,
        walk_bar=walk_bar,
    )
    current = _current_job_card(
        latest, mandates, walk_bar, paper_scan_family(), stages, family=family
    )
    nxt, then = _buffer_cards(remaining, jobs, current.get("family") if current else None)
    blockers = _blockers(
        latest=latest,
        stalled_walk=stalled_walk,
        mandates=mandates,
    )
    return {
        "stages": stages,
        "current": current,
        "next": nxt,
        "then": then,
        "blockers": blockers,
        "who_waits": _who_waits(stages),
        "book": {
            "approved_count": len(universe.approved_pairs),
            "paper_override_count": len(universe.paper_override_records),
            "live": "OFF" if live_off else "ON",
            "mode": mode,
        },
        "note": (
            "Floor is the firm process, not the validator console. "
            "Walk-forward job cards live on Research. Live stays a hard human gate."
        ),
    }


def high_level_progress(job: dict[str, Any] | None, bar: dict[str, Any] | None = None) -> dict[str, Any]:
    """Pair-count progress only — no validator log / cell dump."""
    from firm.research_jobs import walkforward_progress

    if not job:
        return {"progress": None, "progress_label": "", "stalled": False}
    raw = dict(bar or walkforward_progress(job))
    label = str(raw.get("progress_label") or "")
    match = _PAIR_RATIO.search(label)
    symbols = list(job.get("symbols") or [])
    side = str(job.get("side") or "BOTH").upper()
    sides = 2 if side in {"", "BOTH"} else 1
    expected = max(len(symbols) * sides, 1)
    if match:
        clean = f"{match.group(1)}/{match.group(2)} pairs"
    elif str(job.get("status") or "") in {"running", "queued"}:
        clean = f"0/{expected} pairs"
    elif str(job.get("status") or "") == "done":
        approved = job.get("pairs_approved")
        clean = f"{approved}/{expected} approved" if approved is not None else "done"
    else:
        clean = ""
    if raw.get("stalled"):
        clean = f"STALLED · {clean}".strip(" ·")
    raw["progress_label"] = clean
    return raw


def _inbox_rows() -> list[dict[str, Any]]:
    from firm import memory

    return list(memory.pending_proposals(limit=100) or [])


def _quant_is_running() -> bool:
    from firm import memory

    quant = next(iter(memory.recent_runs(agent="quant_researcher", limit=1) or []), None)
    return bool(quant) and str(quant.get("status") or "") == "running"


def _pointer(
    *,
    latest: dict[str, Any] | None,
    walk_bar: dict[str, Any],
    mandates: list[dict[str, Any]],
    strategy_inbox: list[dict[str, Any]],
    code_inbox: list[dict[str, Any]],
    review_inbox: list[dict[str, Any]],
    quant_running: bool,
    remaining: list[dict[str, Any]],
) -> tuple[int, str]:
    """Index into WORKFLOW_STAGES plus the live box state."""
    status = str((latest or {}).get("status") or "")
    if status in {"running", "queued"}:
        return _STAGE_IDS.index("walk"), "bad" if walk_bar.get("stalled") else "active"
    if mandates:
        mandate = mandates[0]
        if mandate.get("phase") == "implement":
            return _STAGE_IDS.index("code"), "bad"
        return _STAGE_IDS.index("walk"), "active"
    if review_inbox:
        return _STAGE_IDS.index("review"), "wait"
    if strategy_inbox:
        return _STAGE_IDS.index("coo"), "wait"
    if code_inbox:
        return _STAGE_IDS.index("code"), "wait"
    if quant_running:
        return _STAGE_IDS.index("hyp"), "active"
    if status == "done":
        return _STAGE_IDS.index("book"), "active"
    if remaining:
        row = remaining[0]
        # Research next_tests omit `coded`; those rows are already-coded leftovers.
        coded = bool(row["coded"]) if "coded" in row else True
        return _STAGE_IDS.index("walk" if coded else "code"), "wait"
    return _STAGE_IDS.index("hyp"), "wait"


def _current_family(
    latest: dict[str, Any] | None,
    mandates: list[dict[str, Any]],
    remaining: list[dict[str, Any]],
) -> str:
    status = str((latest or {}).get("status") or "")
    if latest and status in {"running", "queued", "standby"}:
        return str(latest.get("family") or "")
    if mandates:
        return str(mandates[0].get("family") or "")
    if remaining:
        return str(remaining[0].get("family") or "")
    if latest and latest.get("family"):
        return str(latest.get("family") or "")
    return ""


def _paint_stages(
    idx: int,
    live_state: str,
    *,
    family: str,
    latest: dict[str, Any] | None,
    stalled_walk: bool,
    live_off: bool,
    walk_bar: dict[str, Any],
) -> list[dict[str, Any]]:
    clock = str((latest or {}).get("clock") or "")
    side = str((latest or {}).get("side") or "BOTH")
    high = high_level_progress(latest, walk_bar)
    # Keep strip cells short — the current-job card holds the family name.
    details = {
        "hyp": "Catalog intake" if family else "Waiting on Shumba",
        "score": "Ranked queue" if family else "Waiting on Munha",
        "coo": "Marcus ONE",
        "ceo": "Brian YES",
        "stamp": "Garwe lock",
        "code": "Coding" if family else "Idle",
        "walk": " ".join(p for p in (clock, side) if p) or "Idle",
        "harvest": "Results in" if str((latest or {}).get("status") or "") in {"done", "failed"} else "Waiting",
        "review": "Marcus review",
        "book": "Paper book",
        "activate": "Live OFF" if live_off else "Live",
    }
    out: list[dict[str, Any]] = []
    for i, spec in enumerate(WORKFLOW_STAGES):
        stage = dict(spec)
        if i < idx:
            stage["state"] = "done"
            stage["current"] = False
        elif i == idx:
            stage["state"] = live_state
            stage["current"] = True
        else:
            stage["state"] = "wait"
            stage["current"] = False
        if spec["id"] == "activate" and live_off and i != idx:
            stage["state"] = "wait"
        stalled = bool(spec["id"] == "walk" and stalled_walk and i == idx)
        stage["stalled"] = stalled
        stage["detail"] = details.get(spec["id"] or "", "")
        if spec["id"] == "walk" and i == idx:
            stage["progress"] = high.get("progress")
            stage["progress_label"] = high.get("progress_label") or ""
        else:
            stage["progress"] = 100 if stage["state"] == "done" else None
            stage["progress_label"] = ""
        out.append(stage)
    return out


def _current_job_card(
    latest: dict[str, Any] | None,
    mandates: list[dict[str, Any]],
    walk_bar: dict[str, Any],
    scan_family: str | None,
    stages: list[dict[str, Any]],
    family: str = "",
) -> dict[str, Any] | None:
    live = next((s for s in stages if s.get("current")), None)
    phase = str((live or {}).get("id") or "walk")
    live_status = str((latest or {}).get("status") or "")
    # A finished reject is not the Floor hero. Walk-wait shows the next family.
    show_job = live_status in {"running", "queued", "standby"} or (
        live_status in {"done", "failed"} and phase in {"harvest", "review", "book"}
    )
    if latest and show_job:
        high = high_level_progress(latest, walk_bar)
        return {
            "family": latest.get("family") or "",
            "clock": latest.get("clock") or "",
            "side": latest.get("side") or "BOTH",
            "status": latest.get("status") or "",
            "phase": phase,
            "progress": high.get("progress"),
            "progress_label": high.get("progress_label") or "",
            "stalled": bool(high.get("stalled")),
        }
    if mandates:
        mandate = mandates[0]
        return {
            "family": mandate.get("family") or "",
            "clock": mandate.get("clock") or "",
            "side": mandate.get("side") or "BOTH",
            "status": "blocked" if mandate.get("phase") == "implement" else "queued",
            "phase": phase,
            "progress": 0,
            "progress_label": "coding" if mandate.get("phase") == "implement" else "starting",
            "stalled": mandate.get("phase") == "implement",
        }
    if phase == "code" and family:
        return {
            "family": family,
            "clock": str((latest or {}).get("clock") or ""),
            "side": str((latest or {}).get("side") or "BOTH"),
            "status": "coding",
            "phase": "code",
            "progress": None,
            "progress_label": "coding",
            "stalled": False,
        }
    if family:
        return {
            "family": family,
            "clock": str((latest or {}).get("clock") or ""),
            "side": str((latest or {}).get("side") or "BOTH"),
            "status": "queued",
            "phase": phase,
            "progress": None,
            "progress_label": "",
            "stalled": False,
        }
    if scan_family:
        return {
            "family": scan_family,
            "clock": "",
            "side": "",
            "status": "paper",
            "phase": "book",
            "progress": None,
            "progress_label": "paper scan",
            "stalled": False,
        }
    return None


def _buffer_cards(
    remaining: list[dict[str, Any]],
    jobs: list[dict[str, Any]],
    current_family: str | None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """NEXT / THEN — the two families behind the current job, not a job dump."""
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    current = (current_family or "").strip()
    if current:
        seen.add(current)
    for row in remaining:
        family = str(row.get("family") or "")
        if not family or family in seen:
            continue
        seen.add(family)
        rows.append(
            {
                "family": family,
                "name": row.get("name") or family,
                "clock": row.get("clock") or "",
                "side": row.get("side") or "BOTH",
                "coded": bool(row["coded"]) if "coded" in row else True,
            }
        )
        if len(rows) >= 2:
            break
    if len(rows) < 2:
        for job in jobs:
            if str(job.get("status") or "") not in {"standby", "gated"}:
                continue
            family = str(job.get("family") or "")
            if not family or family in seen:
                continue
            seen.add(family)
            rows.append(
                {
                    "family": family,
                    "name": family,
                    "clock": job.get("clock") or "",
                    "side": job.get("side") or "BOTH",
                    "coded": True,
                }
            )
            if len(rows) >= 2:
                break
    nxt = rows[0] if rows else None
    then = rows[1] if len(rows) > 1 else None
    if nxt:
        nxt["slot"] = "NEXT"
        nxt["letter"] = "E"
    if then:
        then["slot"] = "THEN"
        then["letter"] = "F"
    return nxt, then


def _blockers(
    *,
    latest: dict[str, Any] | None,
    stalled_walk: bool,
    mandates: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """Only paint when something is actually stuck. Empty means hide the banner."""
    from core.risk.killswitch import KillSwitch
    from firm.pipeline_state import load_state

    rows: list[dict[str, str]] = []
    kill = KillSwitch().read()
    if getattr(kill, "tripped", False):
        rows.append({"level": "blocking", "text": "Kill switch is tripped. No new risk."})
    state = load_state()
    if state.get("circuit_breaker_tripped"):
        rows.append({"level": "blocking", "text": "Pipeline circuit breaker is tripped."})
    if stalled_walk and latest:
        rows.append(
            {
                "level": "blocking",
                "text": f"Walk-forward stalled on {latest.get('family') or 'the current job'}.",
            }
        )
    if mandates and mandates[0].get("phase") == "implement":
        family = mandates[0].get("family") or "family"
        rows.append(
            {
                "level": "blocking",
                "text": f"{family} is approved but not coded — no validator is running.",
            }
        )
    return rows


def _who_waits(stages: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Owners downstream of the live box. Hidden by the UI when empty."""
    past_current = False
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for stage in stages:
        if not past_current:
            if stage.get("current"):
                past_current = True
            continue
        owner = str(stage.get("owner") or "")
        if not owner or owner in seen:
            continue
        seen.add(owner)
        out.append(
            {
                "owner": owner,
                "stage": str(stage.get("label") or ""),
                "detail": str(stage.get("detail") or "waiting"),
            }
        )
    return out
