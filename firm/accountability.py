"""
Who owns the current stall, and whether each seat is hitting its target.

LLM employees used to fail into SQLite and hope Desk Head noticed. That is how
a Gemini timeout became a 12-hour research freeze. This module is deterministic:
bottom flags (no work, failed call, paper mismatch), top checks every pipeline
tick, and the desk can see the owner without asking an LLM.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from firm.health_filters import is_resolved_noise, is_transient_llm_error
from firm.org import EMPLOYEE_MANDATES

logger = __import__("logging").getLogger(__name__)

RETRY_AFTER_TIMEOUT = timedelta(minutes=10)
GM_RECHECK = timedelta(minutes=30)
OPS_RECHECK = timedelta(minutes=15)
ADVISOR_RECHECK = timedelta(minutes=15)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _age(iso: str | None) -> timedelta | None:
    if not iso:
        return None
    try:
        stamp = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except ValueError:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return utcnow() - stamp


def live_llm_failures() -> list[dict[str, Any]]:
    """Timeouts that are still the latest run for that seat.

    A later success means Gemini recovered. Do not keep those rows on the
    duty board as 'live' for six hours.
    """
    from firm import memory

    latest: dict[str, dict[str, Any]] = {}
    for run in memory.recent_runs(limit=40):
        agent = str(run.get("agent") or "")
        if agent and agent not in latest:
            latest[agent] = run

    live: list[dict[str, Any]] = []
    for agent, run in latest.items():
        if str(run.get("status") or "") != "failed":
            continue
        error = str(run.get("error") or "")
        if not is_transient_llm_error(error) or is_resolved_noise(error):
            continue
        if (_age(run.get("started_at")) or timedelta.max) >= timedelta(hours=6):
            continue
        live.append(
            {
                "agent": agent,
                "error": error[:200],
                "when": run.get("started_at"),
            }
        )
    return live


def clear_recovered_timeout_alerts() -> int:
    """Ack timeout escalations once no seat's latest run is still a timeout."""
    from firm import memory

    acked = 0
    live = live_llm_failures()
    live_agents = {str(row.get("agent") or "") for row in live}
    for row in memory.open_escalations(limit=50):
        title = str(row.get("title") or "")
        detail = str(row.get("detail") or "")
        blob = f"{title} {detail}".lower()
        is_timeout = any(
            tok in blob
            for tok in (
                "llm timeout",
                "gemini timeout",
                "read timeout",
                "timed out",
                "read operation",
            )
        )
        if not is_timeout:
            continue
        if title.startswith("LLM timeout:"):
            agent = title.split(":", 1)[-1].strip()
            if agent in live_agents:
                continue
        elif live:
            continue
        if memory.resolve_escalation(int(row["id"])):
            acked += 1
    return acked


def notify_employee_failure(agent: str, error: str) -> dict[str, Any]:
    """Route a live failure to Ops and the duty board. Dedupes open alerts."""
    from firm import memory

    if is_resolved_noise(error):
        return {"alerted": False, "reason": "noise"}
    if not is_transient_llm_error(error):
        return {"alerted": False, "reason": "not_transient"}
    title = f"LLM timeout: {agent}"
    detail = (
        f"{agent} failed: {error}\n\n"
        "Owner: Ops Engineer (seat health / retry). "
        "Watcher: Desk Head (GM) via the duty board. "
        "This is not a research verdict and does not wait for a weekly cadence."
    )
    eid = memory.escalate_once(
        agent="ops_engineer",
        title=title,
        detail=detail,
        severity="warning",
        root_cause=f"llm_timeout:{agent}",
        owner_seat="ops_engineer",
    )
    try:
        from firm.events import emit

        emit("on_llm_timeout", {"agent": agent, "error": error[:300]})
    except Exception:
        logger.exception("Could not emit on_llm_timeout")
    try:
        from firm.continuity import fill_walk_forward_slots

        fill_walk_forward_slots(source="llm_timeout")
    except Exception:
        logger.exception("Could not keep research moving after %s LLM timeout", agent)
    return {"alerted": eid is not None, "escalation_id": eid, "transient": True}


def backfill_failure_alerts() -> list[str]:
    """Catch failures recorded before this routing existed.

    Only the latest run per seat counts. A timeout that later succeeded is
    recovered, not a live outage.
    """
    flagged: list[str] = []
    for fail in live_llm_failures():
        result = notify_employee_failure(str(fail.get("agent") or "employee"), str(fail.get("error") or ""))
        if result.get("alerted"):
            flagged.append(str(fail.get("agent")))
    clear_recovered_timeout_alerts()
    return flagged


def catalog_needs_replenish() -> bool:
    """True when Quant's catalog-depth duty is live, even if a walk-forward is running."""
    from config.pipeline import pipeline_config
    from firm.research_catalog import remaining_hypotheses

    return len(remaining_hypotheses()) < pipeline_config().catalog_min_unqueued


def quant_should_run_now() -> bool:
    """True when catalog depth is low, or the pipe is idle, or a Gemini call failed.

    Catalog replenishment does not wait for walk-forward to go quiet. That wait
    is how Quant slept while three tests ran and the catalog ticket aged.
    """
    from firm import memory
    from firm.research_jobs import open_code_mandates, refresh_job_liveness

    last = memory.recent_runs(agent="quant_researcher", limit=1)
    row = last[0] if last else None
    age = _age(row.get("started_at")) if row else None
    status = str((row or {}).get("status") or "")
    error = str((row or {}).get("error") or "")

    if catalog_needs_replenish():
        if not row:
            return True
        if status == "failed" and is_transient_llm_error(error):
            return age is None or age >= RETRY_AFTER_TIMEOUT
        if age is not None and age < timedelta(minutes=15):
            return False
        return True

    jobs = refresh_job_liveness()
    if any(j.get("status") in {"running", "queued"} for j in jobs):
        return False
    if open_code_mandates():
        return False
    for proposal in memory.pending_proposals(limit=40):
        payload = proposal.get("payload") if isinstance(proposal.get("payload"), dict) else {}
        if proposal.get("kind") == "strategy":
            return False
        if payload.get("action") in {"code_family", "walk_forward"}:
            return False

    if not row:
        return True
    if status == "failed" and is_transient_llm_error(error):
        return age is None or age >= RETRY_AFTER_TIMEOUT
    if status == "failed":
        return age is None or age >= timedelta(minutes=15)
    if age is not None and age < timedelta(hours=12):
        return False
    return True


def gm_should_run_now(last_run: datetime | None) -> bool:
    """Desk Head re-checks whenever the duty board has a slip, not just daily."""
    slips = accountability_snapshot().get("slips") or []
    if not slips:
        return False
    if last_run is None:
        return True
    return utcnow() - last_run >= GM_RECHECK


def ops_should_run_now(last_run: datetime | None) -> bool:
    """Ops re-checks live LLM failures on a short loop, not only the hourly slot."""
    live = live_llm_failures()
    if not live:
        return False
    if last_run is None:
        return True
    return utcnow() - last_run >= OPS_RECHECK


def sleeve_engineer_should_run_now(last_run: datetime | None) -> bool:
    """Fire on coding/standby pressure, not only on the hourly backstop."""
    from firm.pipeline_state import open_tickets
    from firm.research_jobs import implementation_gaps, open_code_mandates

    pressure = bool(implementation_gaps()) or any(
        m.get("phase") == "implement" for m in open_code_mandates()
    )
    pressure = pressure or any(
        t.get("owner") == "sleeve_engineer" for t in open_tickets()
    )
    if not pressure:
        return False
    if last_run is None:
        return True
    return utcnow() - last_run >= timedelta(minutes=15)


def advisor_should_run_now(last_run: datetime | None) -> bool:
    """Strategy Advisor re-checks whenever the GM is slipping or the pipe is idle."""
    snap = accountability_snapshot()
    gm_slipping = any(s.get("owner") == "desk_head" for s in (snap.get("slips") or []))
    idle = not snap.get("pipeline_moving")
    if not gm_slipping and not idle:
        return False
    if not gm_slipping:
        from core.strategy.registry import list_strategies
        from firm.research_catalog import next_catalog_step
        from firm.research_jobs import list_jobs

        tested = {
            str(j.get("family"))
            for j in list_jobs()
            if j.get("status") in {"done", "failed"} and j.get("family")
        }
        if next_catalog_step(tested=tested, coded=set(list_strategies())) is None:
            return False
    if last_run is None:
        return True
    return utcnow() - last_run >= ADVISOR_RECHECK


def accountability_snapshot() -> dict[str, Any]:
    """Operator-facing duty board: targets, slips, and live LLM failures."""
    from firm import memory
    from firm.integrity import certify_paper
    from firm.research_jobs import list_jobs, open_code_mandates
    from firm.research_catalog import next_catalog_step
    from core.strategy.registry import list_strategies

    jobs = list_jobs()
    running = [j for j in jobs if j.get("status") in {"running", "queued"}]
    inbox = memory.pending_proposals(limit=40)
    research_gate = [
        p
        for p in inbox
        if p.get("kind") == "strategy"
        or (
            isinstance(p.get("payload"), dict)
            and p["payload"].get("action") in {"code_family", "walk_forward", "catalog_review"}
        )
    ]
    mandates = open_code_mandates()
    coded = set(list_strategies())
    tested = {
        str(j.get("family"))
        for j in jobs
        if j.get("status") in {"done", "failed"} and j.get("family")
    }
    next_work = next_catalog_step(tested=tested, coded=coded)

    slips: list[dict[str, str]] = []

    implement = [m for m in mandates if m.get("phase") == "implement"]
    if implement:
        family = implement[0].get("family") or "strategy"
        slips.append(
            {
                "owner": "sleeve_engineer",
                "flagged_by": "integrity",
                "issue": (
                    f"{family} was approved for coding and is not in the registry. "
                    "No walk-forward is running. Elapsed wait is not progress."
                ),
                "expected": (
                    "Register the sleeve from a known template, or escalate a "
                    "novel family to Cursor. Do not LLM-write strategy files."
                ),
            }
        )

    if not running and not research_gate and not mandates:
        from firm.continuity import auto_advance_allowed
        from firm.research_catalog import remaining_hypotheses

        leftover = remaining_hypotheses(jobs)
        has_pass = any(int(j.get("pairs_approved") or 0) > 0 for j in jobs)
        allowed, why = auto_advance_allowed()
        launch = leftover[0] if leftover else None
        if launch is None and next_work and next_work.get("action") == "code_family":
            launch = next_work
        nxt_label = ""
        if launch:
            nxt_label = (
                f"{launch.get('action') or 'walk_forward'} {launch.get('family')} "
                f"{launch.get('clock') or ''} {launch.get('side') or ''}"
            ).strip()
        if leftover or (launch and launch.get("action") == "code_family"):
            if not allowed:
                slips.append(
                    {
                        "owner": "desk_head",
                        "flagged_by": "pipeline",
                        "issue": (
                            f"Auto-advance paused ({why})."
                            + (f" Next catalog step is {nxt_label}." if nxt_label else "")
                        ),
                        "expected": (
                            "Inspect the last 0/6. A different clock/side follow-up "
                            "must start the same tick; re-running the same grid stays paused."
                        ),
                    }
                )
            elif nxt_label:
                slips.append(
                    {
                        "owner": "desk_head",
                        "flagged_by": "pipeline",
                        "issue": (
                            f"No walk-forward, no Inbox gate, no coding mandate. "
                            f"Next catalog step is {nxt_label}."
                        ),
                        "expected": (
                            "Launch the next standby family the same tick. "
                            "Idle with catalog work is a GM miss. Filing Inbox is not the start."
                        ),
                    }
                )
        elif not has_pass:
            slips.append(
                {
                    "owner": "desk_head",
                    "flagged_by": "pipeline",
                    "issue": (
                        "No walk-forward, no Inbox gate. Every coded family has a "
                        "verdict and none passed. funding_fade still needs a feed."
                    ),
                    "expected": (
                        "File the catalog-review gate. Do not mark the GM on track "
                        "while no pair is approved."
                    ),
                }
            )

    last_quant = next(iter(memory.recent_runs(agent="quant_researcher", limit=1)), None)
    if last_quant and str(last_quant.get("status") or "") == "failed":
        error = str(last_quant.get("error") or "")
        age = _age(last_quant.get("started_at"))
        if is_transient_llm_error(error) and not research_gate and not running:
            waiting = age is not None and age < RETRY_AFTER_TIMEOUT
            slips.append(
                {
                    "owner": "quant_researcher",
                    "flagged_by": "runtime",
                    "issue": f"Quant Gemini failed: {error[:160]}",
                    "expected": (
                        "Retry after 10 minutes — this is not a weekly wait."
                        if not waiting
                        else "Retry armed. Ops is watching the seat."
                    ),
                }
            )
            slips.append(
                {
                    "owner": "ops_engineer",
                    "flagged_by": "runtime",
                    "issue": "Live LLM timeout on Quant. Escalation is on the board.",
                    "expected": "Confirm Gemini is reachable; do not treat this as historical noise.",
                }
            )

    try:
        paper = certify_paper()
    except Exception:
        paper = {"ok": True, "checks": []}
    sleeve_check = next(
        (c for c in (paper.get("checks") or []) if c.get("name") == "paper_sleeve"),
        None,
    )
    if sleeve_check and not sleeve_check.get("ok"):
        slips.append(
            {
                "owner": "ops_engineer",
                "flagged_by": "integrity",
                "issue": f"Paper sleeve mismatch: {sleeve_check.get('detail')}",
                "expected": (
                    "Engine rebuilds the paper plan every cycle. "
                    "If this persists, the paper process is running old code."
                ),
            }
        )

    gm_slipping_now = any(s.get("owner") == "desk_head" for s in slips)
    if gm_slipping_now:
        noticed = any(
            str(row.get("agent") or "") == "strategy_advisor"
            and (
                "GM continuity" in str(row.get("title") or "")
                or "GM miss" in str(row.get("title") or "")
            )
            for row in memory.open_escalations(limit=50)
        )
        if not noticed:
            slips.append(
                {
                    "owner": "strategy_advisor",
                    "flagged_by": "org",
                    "issue": (
                        "GM is idle with catalog work and the Strategy Advisor "
                        "has not flagged the miss."
                    ),
                    "expected": (
                        "Start the next standby family now. Escalating without "
                        "a launch is not enforcement. Inbox is not the Tier A start."
                    ),
                }
            )

    slip_owners = {s["owner"] for s in slips}
    llm_failures = live_llm_failures()

    duties = []
    for name, spec in EMPLOYEE_MANDATES.items():
        activity = memory.agent_activity(name)
        duties.append(
            {
                "id": name,
                "title": spec["title"],
                "goal": spec.get("goal") or spec["mandate"],
                "target": spec.get("target") or "",
                "kpi": spec.get("kpi") or "",
                "on_track": name not in slip_owners,
                "last_status": activity.get("status") or "never_run",
                "last_run_at": activity.get("last_run_at"),
                "last_error": (
                    ""
                    if is_resolved_noise(str(activity.get("last_error") or ""))
                    else (activity.get("last_error") or "")
                ),
            }
        )

    return {
        "slips": slips,
        "duties": duties,
        "llm_failures": llm_failures,
        "pipeline_moving": bool(
            running
            or research_gate
            or any(m.get("phase") == "start_test" for m in mandates)
        ),
        "note": (
            "Bottom flags (Quant timeout, idle pipeline, paper mismatch) write "
            "this board. Strategy Advisor watches the GM. Desk Head checks it "
            "every pipeline tick. Trust-ladder P&L is not the research KPI — "
            "these targets are."
        ),
    }
