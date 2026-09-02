"""Research pipeline continuity: events launch work; cadences only catch drops.

This module is the enforcement the duty board was missing. Detecting an empty
Inbox after a rejected test is not enough — a free walk-forward slot must
start the next standby family in the same tick.

Does not place live orders, raise size caps, or unlock live. Paper-to-live
stays Tier C (human).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from statistics import median
from typing import Any

from config.pipeline import (
    APPROVED_RESEARCH_SYMBOLS,
    STAGE_OWNERS,
    pipeline_config,
)
from firm.envelope import classify_family_clock, classify_hypothesis
from firm.events import emit, mark_event_overdue
from firm.pipeline_state import (
    dropped_event_count,
    load_state,
    open_tickets,
    record_auto_advance,
    record_dropped_event,
    resolve_ticket,
    save_state,
    set_ledger_pointer,
    upsert_ticket,
)
from firm.research_catalog import remaining_hypotheses
from research.validate import DEFAULT_CRITERIA

logger = logging.getLogger(__name__)

LIVE_STATUSES = frozenset({"running", "queued"})
STANDBY_STATUS = "standby"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(iso: str | None) -> datetime | None:
    if not iso:
        return None
    try:
        stamp = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except ValueError:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.astimezone(timezone.utc)


def _age_seconds(iso: str | None) -> float | None:
    stamp = _parse_iso(iso)
    if stamp is None:
        return None
    return (_now() - stamp).total_seconds()


def live_jobs(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [j for j in jobs if j.get("status") in LIVE_STATUSES]


def standby_jobs(jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [j for j in jobs if j.get("status") == STANDBY_STATUS]


def stamp_ledger(
    job: dict[str, Any],
    *,
    stage: str,
    updated_by: str,
    next_action: str = "",
    next_action_owner: str = "",
    blocked_by: str = "",
) -> dict[str, Any]:
    """Write the canonical job fields every seat must read."""
    now = datetime.now(timezone.utc).isoformat()
    prev_stage = str(job.get("stage") or "")
    if prev_stage != stage or not job.get("entered_stage_at"):
        job["entered_stage_at"] = now
    job["stage"] = stage
    job["owner_seat"] = STAGE_OWNERS.get(stage, updated_by)
    job["blocked_by"] = blocked_by
    job["next_action"] = next_action
    job["next_action_owner"] = next_action_owner or STAGE_OWNERS.get(stage, updated_by)
    job["last_updated_by"] = updated_by
    job["last_updated_at"] = now
    set_ledger_pointer(
        family=str(job.get("family") or ""),
        stage=stage,
        job_id=int(job["id"]) if job.get("id") is not None else None,
        updated_by=updated_by,
    )
    return job


def hung_threshold_seconds(jobs: list[dict[str, Any]]) -> float:
    """3x rolling median of last N completed runs. Exclude manual interrupts.

    Used only to detect a wedged validator. Never used to schedule the next test.
    """
    cfg = pipeline_config()
    durations: list[float] = []
    for job in jobs:
        if job.get("status") not in {"done", "failed"}:
            continue
        if job.get("manual_interrupt") or job.get("operator_debug"):
            continue
        start = _parse_iso(str(job.get("started_at") or ""))
        end = _parse_iso(str(job.get("finished_at") or ""))
        if start is None or end is None:
            continue
        dur = (end - start).total_seconds()
        if dur > 30:
            durations.append(dur)
    sample = durations[-cfg.hung_median_n :]
    if len(sample) < 3:
        # Fallback only for hung detection when we lack a sample, not scheduling.
        return 90 * 60
    return float(cfg.hung_median_mult * median(sample))


def auto_advance_allowed() -> tuple[bool, str]:
    """Safety rails: global switch, budget, circuit breaker.

    Raw rails only. Callers that start validators must use
    `auto_advance_gate`, which still launches a *new* family@clock@side
    when the pause is a re-run brake, not a global halt.
    """
    cfg = pipeline_config()
    if not cfg.auto_advance:
        return False, "global override PIPELINE_AUTO_ADVANCE=false"
    state = load_state()
    if state.get("circuit_breaker_tripped"):
        return False, "circuit breaker: consecutive auto 0-pair rejects"
    cutoff = _now() - timedelta(hours=24)
    recent = 0
    for row in state.get("auto_advances") or []:
        stamp = _parse_iso(str(row.get("at") or ""))
        if stamp and stamp >= cutoff:
            recent += 1
    if recent >= cfg.auto_advance_budget_24h:
        return False, f"auto-advance budget {cfg.auto_advance_budget_24h}/24h exhausted"
    return True, "ok"


def _advance_key(
    family: str,
    clock: str,
    side: str = "BOTH",
    hypothesis_id: str = "",
) -> str:
    """Identity of one auto-advance. Tagged near-miss ids are not the base grid."""
    hid = str(hypothesis_id or "")
    if hid:
        return hid
    from firm.research_catalog import hypothesis_key

    return hypothesis_key(family, clock, side)


def _next_followup_key() -> str:
    """The hypothesis fill would start next: remaining catalog, else standby/gated."""
    leftover = remaining_hypotheses()
    if leftover:
        nxt = leftover[0]
        return _advance_key(
            str(nxt.get("family") or ""),
            str(nxt.get("clock") or ""),
            str(nxt.get("side") or "BOTH"),
            hypothesis_id=str(nxt.get("id") or ""),
        )
    from firm.research_jobs import list_jobs

    for job in list_jobs():
        if job.get("status") not in {"gated", STANDBY_STATUS}:
            continue
        key = _advance_key(
            str(job.get("family") or ""),
            str(job.get("clock") or ""),
            str(job.get("side") or "BOTH"),
            hypothesis_id=str(job.get("hypothesis_id") or ""),
        )
        if key:
            return key
    return ""


def _recent_auto_advance_keys(*, last_n: int | None = None, hours: float | None = 24.0) -> set[str]:
    state = load_state()
    rows = list(state.get("auto_advances") or [])
    if last_n is not None:
        rows = rows[-last_n:]
    elif hours is not None:
        cutoff = _now() - timedelta(hours=hours)
        kept: list[dict[str, Any]] = []
        for row in rows:
            stamp = _parse_iso(str(row.get("at") or ""))
            if stamp is None or stamp >= cutoff:
                kept.append(row)
        rows = kept
    keys: set[str] = set()
    for row in rows:
        keys.add(
            _advance_key(
                str(row.get("family") or ""),
                str(row.get("clock") or ""),
                str(row.get("side") or "BOTH"),
                hypothesis_id=str(row.get("hypothesis_id") or ""),
            )
        )
    return keys


def _followup_is_new(key: str) -> bool:
    """True when this family@clock@side was not auto-started in the last 24h."""
    if not key:
        return False
    return key not in _recent_auto_advance_keys(hours=24.0)


def auto_advance_gate() -> tuple[bool, str]:
    """Whether fill may start a validator this tick.

    Budget and the circuit breaker pause a silent re-run of the same grid.
    A different clock/side follow-up must start in the same tick — that is
    the duty-board rule, not an operator gate.
    """
    allowed, why = auto_advance_allowed()
    if allowed:
        return True, why
    key = _next_followup_key()
    if "circuit breaker" in why:
        if _release_breaker_for_new_followup():
            return True, "ok"
        return False, why
    if "budget" in why and _followup_is_new(key):
        logger.warning(
            "Budget pause skipped: next follow-up %s is a new clock/side, not a re-run",
            key,
        )
        return True, "ok"
    return False, why


def _flag_blocked_auto_advance(why: str, nxt_key: str) -> None:
    """Do not wait for the Strategy Advisor LLM call to name a GM miss."""
    try:
        from firm import memory

        memory.escalate_once(
            agent="strategy_advisor",
            title="GM continuity miss",
            detail=(
                f"Auto-advance blocked ({why}). Next follow-up "
                f"{nxt_key or '(none)'} is a re-run of a grid already "
                "auto-started, or there is no follow-up. Inspect the last "
                "0/6. Escalating without a launch is not the start — this "
                "row exists so the duty board does not wait on Gemini."
            ),
            severity="warning",
            root_cause="gm_continuity_miss",
            owner_seat="desk_head",
        )
    except Exception:
        logger.exception("Could not escalate blocked auto-advance")


def _restore_breaker_holds() -> int:
    """Put circuit-breaker/budget gated jobs back on standby when auto-advance is on."""
    from firm.research_jobs import list_jobs, stamp_job

    restored = 0
    for job in list_jobs():
        if job.get("status") != "gated":
            continue
        blocked = str(job.get("blocked_by") or "")
        if "circuit breaker" not in blocked and "budget" not in blocked:
            continue
        stamp_job(
            int(job["id"]),
            status=STANDBY_STATUS,
            stage="standby",
            updated_by="desk_head",
            blocked_by="",
            next_action="wait_for_slot",
            next_action_owner="desk_head",
        )
        restored += 1
    return restored


def _release_breaker_for_new_followup() -> bool:
    """Circuit breaker blocks a silent re-run of the same 0/6 grid, not a new clock/side.

    Strategy Advisor / Desk Head enforcement: if the next remaining hypothesis
    is a different family@clock@side than the last auto-advances, clear the
    trip and start. Same-grid follow-ups stay paused for a human look.
    """
    state = load_state()
    if not state.get("circuit_breaker_tripped"):
        return False
    nxt_key = _next_followup_key()
    if not nxt_key:
        return False
    streak_n = max(int(state.get("consecutive_auto_rejects") or 0), 3)
    recent = _recent_auto_advance_keys(last_n=streak_n, hours=None)
    if nxt_key in recent:
        return False
    state["circuit_breaker_tripped"] = False
    state["consecutive_auto_rejects"] = 0
    save_state(state)
    resolve_ticket("circuit_breaker")
    logger.warning(
        "Circuit breaker released: next follow-up %s is not a re-run of the last auto-advances",
        nxt_key,
    )
    return True


def _note_auto_reject(pairs_approved: int) -> None:
    cfg = pipeline_config()
    state = load_state()
    if pairs_approved > 0:
        state["consecutive_auto_rejects"] = 0
        save_state(state)
        return
    n = int(state.get("consecutive_auto_rejects") or 0) + 1
    state["consecutive_auto_rejects"] = n
    if n >= cfg.circuit_breaker_rejects:
        state["circuit_breaker_tripped"] = True
        upsert_ticket(
            {
                "id": "circuit_breaker",
                "invariant": "auto_advance_circuit",
                "owner": "desk_head",
                "severity": "critical",
                "sla": "immediate",
                "next_action": (
                    "Inspect the last auto-advanced 0/6 results. Auto-advance "
                    "is paused until you clear data/pipeline_state.json "
                    "circuit_breaker_tripped."
                ),
                "detail": f"{n} consecutive auto-advanced families approved 0 pairs.",
            }
        )
        try:
            from firm import memory

            memory.escalate_once(
                agent="desk_head",
                title="Auto-advance paused: consecutive 0-pair rejects",
                detail=(
                    f"{n} auto-advanced walk-forwards approved 0 pairs. "
                    "Acceptance thresholds are reachable (PF>=1.15, fold "
                    "stability, expectancy CI). This is not an unreachable bar. "
                    "Auto-advance is paused."
                ),
                severity="critical",
                root_cause="auto_advance_circuit_breaker",
                owner_seat="desk_head",
            )
        except Exception:
            logger.exception("Could not escalate circuit breaker")
    save_state(state)


def _consume_matching_inbox(family: str, clock: str, decided_by: str) -> None:
    """Close a pending walk-forward gate we just auto-started so Inbox is not a second gate."""
    try:
        from firm import memory
    except Exception:
        return
    for proposal in memory.pending_proposals(limit=40):
        payload = proposal.get("payload") if isinstance(proposal.get("payload"), dict) else {}
        action = str(payload.get("action") or "")
        # Novel coding briefs stay in Inbox until the operator approves them.
        # Auto-starting a walk-forward must not swallow those tickets.
        if action == "code_family" or payload.get("novel"):
            continue
        if action not in {"walk_forward"} and proposal.get("kind") != "strategy":
            continue
        prop_family = str(payload.get("family") or payload.get("name") or "")
        prop_clock = str(payload.get("clock") or "")
        if prop_family != family:
            continue
        if prop_clock and clock and prop_clock != clock:
            continue
        pid = int(proposal.get("id") or 0)
        if not pid:
            continue
        memory.decide_proposal(
            pid,
            approved=True,
            decided_by=decided_by,
            reason=f"auto-advanced {family} {clock}",
        )


def stage_standby(source: str = "sleeve_engineer") -> list[int]:
    """Ensure launch-ready standby jobs exist. Does not start validators."""
    from firm.research_catalog import promote_remaining_into_top5
    from firm.research_jobs import _record_job, list_jobs, stamp_job

    cfg = pipeline_config()
    jobs = list_jobs()
    promote_remaining_into_top5(jobs)
    staged: list[int] = []
    while len(standby_jobs(jobs)) < cfg.standby_target:
        remaining = remaining_hypotheses(jobs)
        hypo = next(
            (
                h
                for h in remaining
                if classify_hypothesis(h, jobs=jobs).get("tier") == "A"
            ),
            None,
        )
        if hypo is None:
            break
        envelope = classify_hypothesis(hypo, jobs=jobs)
        job = _record_job(
            family=str(hypo["family"]),
            symbols=list(APPROVED_RESEARCH_SYMBOLS),
            side=str(hypo.get("side") or "BOTH"),
            timeframe="",
            clock=str(hypo.get("clock") or "4h/4h"),
            status=STANDBY_STATUS,
            hypothesis_id=str(hypo.get("id") or ""),
            envelope_tier=envelope["tier"],
            param_change=dict(hypo.get("param_change") or {}),
            detail=(
                f"Standby: {hypo.get('name')} ({hypo.get('clock')}). "
                f"Tier {envelope['tier']}. Will start when a walk-forward slot frees."
            ),
        )
        stamp_job(
            job["id"],
            stage="standby",
            updated_by=source,
            next_action="wait_for_slot",
            next_action_owner="desk_head",
        )
        staged.append(int(job["id"]))
        jobs = list_jobs()
        emit("on_sleeve_registered", {"job_id": job["id"], "family": job.get("family")})
    if staged:
        emit("on_coding_request_queued", {"staged": staged})
    return staged


def fill_walk_forward_slots(*, source: str = "event") -> dict[str, Any]:
    """Start validators up to configured parallelism from standby.

    Called on on_walk_forward_slot_free in the same process/tick. A cadenced
    caller must pass source='backstop' so a successful fill is a dropped-event
    defect, not a healthy sweep.
    """
    from firm.research_jobs import list_jobs, stamp_job, start_job

    cfg = pipeline_config()
    jobs = list_jobs()
    live = live_jobs(jobs)
    slots = max(0, cfg.wf_parallelism - len(live))
    started: list[int] = []
    skipped: list[str] = []
    if slots == 0:
        resolve_ticket("wf_parallelism")
        return {"started": started, "slots": 0, "skipped": skipped}

    allowed, why = auto_advance_gate()
    if not allowed:
        # Leave standby as standby. Gating every follow-up drains the catalog
        # into Inbox while the pause is the actual block. Same-grid re-runs
        # stay paused; a new clock/side is exempt inside auto_advance_gate.
        _flag_blocked_auto_advance(why, _next_followup_key())
        return {
            "started": started,
            "slots": slots,
            "skipped": [why],
            "idle": "",
            "blocked": why,
        }

    _restore_breaker_holds()
    stage_standby(source="fill_slots")
    jobs = list_jobs()

    idle_note = ""
    if not standby_jobs(jobs) and slots > 0:
        idle_note = "standby empty when a walk-forward slot freed"
        upsert_ticket(
            {
                "id": "standby_empty_on_slot_free",
                "invariant": "standby_floor",
                "owner": "sleeve_engineer",
                "severity": "warning",
                "sla": "same cycle",
                "next_action": "Stage a coded envelope-cleared hypothesis into standby",
                "detail": idle_note,
                "idle_seconds": 0,
            }
        )

    while len(live_jobs(list_jobs())) < cfg.wf_parallelism:
        jobs = list_jobs()
        pool = standby_jobs(jobs)
        if not pool:
            stage_standby(source="fill_slots")
            pool = standby_jobs(list_jobs())
        if not pool:
            break
        job = pool[0]
        family = str(job.get("family") or "")
        clock = str(job.get("clock") or "")
        side = str(job.get("side") or "BOTH")
        from firm.research_catalog import family_blocked_from_replenish, family_primary_clock

        # Do not spend a slot on 1h clones of a sleeve whose first clock already
        # finished 0-for-6. Those rows used to sneak in as "still-open family".
        if (
            family
            and clock
            and clock != family_primary_clock(family)
            and family_blocked_from_replenish(family, list_jobs())
        ):
            stamp_job(
                int(job["id"]),
                status="gated",
                stage="standby",
                updated_by="desk_head",
                blocked_by="primary_clock_failed",
                next_action="code_or_test_new_family",
                next_action_owner="desk_head",
            )
            skipped.append(f"{family} {clock} primary already 0/6")
            continue
        envelope = classify_family_clock(
            family,
            clock,
            side=side,
            jobs=list_jobs(),
            hypothesis_id=str(job.get("hypothesis_id") or ""),
        )
        tier = envelope["tier"]
        if tier == "C":
            stamp_job(
                int(job["id"]),
                status="gated",
                stage="standby",
                updated_by="desk_head",
                blocked_by="tier_c",
                next_action="wait_human",
                next_action_owner="operator",
                envelope_tier=tier,
            )
            _file_inbox_gate(job, envelope, reason="Tier C hard human gate")
            skipped.append(f"{family} {clock} Tier C")
            continue
        if tier == "A" and not allowed:
            stamp_job(
                int(job["id"]),
                status="gated",
                stage="standby",
                updated_by="desk_head",
                blocked_by=why,
                next_action="wait_human_or_breaker",
                next_action_owner="operator",
                envelope_tier=tier,
            )
            skipped.append(f"{family} {clock} auto-advance blocked: {why}")
            _file_inbox_gate(job, envelope, reason=why)
            continue
        if tier == "B" and source != "tier_b_timeout":
            stamp_job(
                int(job["id"]),
                status="gated",
                stage="standby",
                updated_by="desk_head",
                blocked_by="tier_b_inbox",
                next_action="wait_24h_or_approve",
                next_action_owner="operator",
                envelope_tier=tier,
            )
            _file_inbox_gate(job, envelope, reason="Tier B waits 24h unless you approve")
            skipped.append(f"{family} {clock} Tier B inbox")
            continue
        stamp_job(
            int(job["id"]),
            status="queued",
            stage="walk_forward",
            updated_by="desk_head",
            next_action="run_validator",
            next_action_owner="desk_head",
            envelope_tier=tier,
            auto_advanced=True,
        )
        ok = start_job(int(job["id"]))
        if ok:
            started.append(int(job["id"]))
            record_auto_advance(
                {
                    "job_id": job["id"],
                    "family": family,
                    "clock": clock,
                    "side": side,
                    "hypothesis_id": str(job.get("hypothesis_id") or ""),
                    "tier": tier,
                    "checks": envelope.get("checks"),
                    "source": source,
                    "seat": "desk_head",
                }
            )
            _consume_matching_inbox(family, clock, decided_by="desk_head")
        else:
            skipped.append(f"{family} spawn failed")
            break

    if source == "backstop" and started:
        record_dropped_event(
            "on_walk_forward_slot_free",
            f"Backstop started jobs {started}; the event handler should have.",
            source,
        )
        mark_event_overdue(
            "on_walk_forward_slot_free",
            f"Cadenced sweep started {started}. That is a dropped-event defect.",
        )
    return {"started": started, "slots": slots, "skipped": skipped, "idle": idle_note}


def _file_inbox_gate(job: dict[str, Any], envelope: dict[str, Any], *, reason: str) -> None:
    from firm import memory
    from firm.memory_models import ProposalKind
    from firm.research_jobs import _already_pending_next

    family = str(job.get("family") or "")
    clock = str(job.get("clock") or "")
    if _already_pending_next("walk_forward", family):
        return
    ttl_hours = pipeline_config().tier_b_hours if envelope.get("tier") == "B" else 14 * 24
    memory.record_proposal(
        agent="research_pipeline",
        kind=ProposalKind.STRATEGY,
        title=f"Next: walk-forward {family} at {clock} (Tier {envelope.get('tier')})",
        payload={
            "name": family,
            "family": family,
            "action": "walk_forward",
            "clock": clock,
            "side": job.get("side") or "BOTH",
            "hypothesis_id": job.get("hypothesis_id"),
            "tier": envelope.get("tier"),
            "operator_next": envelope.get("tier") != "A",
            "from_job_id": job.get("id"),
        },
        rationale=f"{reason}. Checks: {envelope.get('checks')}. {'; '.join(envelope.get('reasons') or [])}",
        confidence=0.9,
        ttl=timedelta(hours=ttl_hours),
    )


def default_approve_tier_b() -> list[int]:
    """Silence advances Tier B after the timeout. Operator can veto before then."""
    from firm import memory
    from firm.research_jobs import on_operator_approved

    cfg = pipeline_config()
    approved_ids: list[int] = []
    cutoff = _now() - timedelta(hours=cfg.tier_b_hours)
    for proposal in memory.pending_proposals(limit=40):
        payload = proposal.get("payload") if isinstance(proposal.get("payload"), dict) else {}
        if str(payload.get("tier") or "") != "B":
            continue
        if str(payload.get("action") or "") != "walk_forward":
            continue
        created = _parse_iso(str(proposal.get("created_at") or ""))
        if created is None or created > cutoff:
            continue
        pid = int(proposal.get("id") or 0)
        if not pid:
            continue
        ok = memory.decide_proposal(
            pid,
            approved=True,
            decided_by="tier_b_timeout",
            reason="Tier B default-approve after timeout; operator did not veto",
        )
        if not ok:
            continue
        on_operator_approved(memory.get_proposal(pid) or proposal)
        approved_ids.append(pid)
    return approved_ids


def on_job_finished(job: dict[str, Any]) -> dict[str, Any]:
    """Same-tick handler: post-mortem, then fill the freed slot from standby."""
    pairs = int(job.get("pairs_approved") or 0)
    rejected = pairs <= 0 or str(job.get("status") or "") == "failed"
    emit("on_test_finished", {"job_id": job.get("id"), "family": job.get("family")})
    postmortem = None
    if rejected:
        emit("on_test_rejected", {"job_id": job.get("id"), "family": job.get("family")})
        try:
            from firm.postmortem import write_postmortem
            from firm.research_jobs import _verdict_blurb

            postmortem = write_postmortem(job, pair_blurbs=_verdict_blurb(job))
        except Exception:
            logger.exception("Post-mortem failed for job %s", job.get("id"))
        if job.get("envelope_tier") == "A" or job.get("auto_advanced"):
            _note_auto_reject(pairs)
    emit("on_walk_forward_slot_free", {"freed_by": job.get("id")})
    fill = fill_walk_forward_slots(source="event")
    evaluate_invariants()
    return {"postmortem": postmortem, "fill": fill}


def evaluate_invariants() -> list[dict[str, Any]]:
    """Open/resolve watchdog tickets. Called on every event and backstop sweep."""
    from core.strategy.registry import list_strategies
    from firm.research_catalog import remaining_hypotheses
    from firm.research_jobs import implementation_gaps, list_jobs, open_code_mandates

    cfg = pipeline_config()
    jobs = list_jobs()
    live = live_jobs(jobs)
    standby = standby_jobs(jobs)
    remaining = remaining_hypotheses(jobs)
    uncoded = [m for m in open_code_mandates() if m.get("phase") == "implement"]
    coded = set(list_strategies())
    uncoded = [u for u in uncoded if str(u.get("family") or "") not in coded]
    uncoded.extend(implementation_gaps())

    # Catalog depth: un-queued ranked hypotheses. Replenish before ticketing.
    # Always compact remaining into ranks 1–5: post-mortems vacate that window
    # and a full catalog at seed ranks 6+ never auto-starts.
    catalog_depth = len(remaining)
    try:
        from firm.research_catalog import promote_remaining_into_top5, replenish_catalog

        added: list[dict[str, Any]] = []
        if catalog_depth < cfg.catalog_min_unqueued:
            added = replenish_catalog(jobs=jobs)
            if added:
                emit("on_catalog_depth_low", {"added": [r.get("id") for r in added]})
        else:
            promote_remaining_into_top5(jobs)
        remaining = remaining_hypotheses(jobs)
        catalog_depth = len(remaining)
        from firm.cursor_coding import enqueue_next_novel_if_catalog_empty

        enqueue_next_novel_if_catalog_empty()
    except Exception:
        logger.exception("Catalog replenish/promote failed")

    # Tickets are not launches. If a slot is free and a coded family is waiting,
    # start it here — Quant Gemini must not be the thing that keeps research idle.
    try:
        fill_walk_forward_slots(source="invariants")
    except Exception:
        logger.exception("Invariant fill failed to start a walk-forward")

    jobs = list_jobs()
    live = live_jobs(jobs)
    standby = standby_jobs(jobs)
    remaining = remaining_hypotheses(jobs)
    catalog_depth = len(remaining)
    if catalog_depth < cfg.catalog_min_unqueued:
        upsert_ticket(
            {
                "id": "catalog_depth",
                "invariant": "catalog_min_unqueued",
                "owner": "quant_researcher",
                "severity": "warning",
                "sla": "this cycle",
                "next_action": (
                    "Land newly coded families, then near-miss param grids. "
                    "If the coded catalog is empty, Quant names a new family "
                    "and Cursor codes it — do not only clone clocks."
                ),
                "detail": (
                    f"Catalog depth {catalog_depth} < {cfg.catalog_min_unqueued} "
                    "un-queued hypotheses."
                ),
            }
        )
    else:
        resolve_ticket("catalog_depth")

    uncoded_n = len({str(u.get("family")) for u in uncoded})
    if uncoded_n > cfg.coding_queue_cap:
        upsert_ticket(
            {
                "id": "coding_cap",
                "invariant": "coding_queue_cap",
                "owner": "sleeve_engineer",
                "severity": "warning",
                "sla": "this cycle",
                "next_action": "Stop accepting new coding requests until the queue is under the cap.",
                "detail": f"{uncoded_n} approved-uncoded families > cap {cfg.coding_queue_cap}.",
            }
        )
    else:
        resolve_ticket("coding_cap")
    if uncoded_n > 0:
        upsert_ticket(
            {
                "id": "coding_sla",
                "invariant": "coding_sla",
                "owner": "sleeve_engineer",
                "severity": "warning",
                "sla": "one cycle",
                "next_action": (
                    "Register the sleeve from a known template, or escalate a "
                    "novel family to Cursor. Do not LLM-write strategy files."
                ),
                "detail": f"{uncoded_n} approved-uncoded families waiting: "
                + ", ".join(sorted({str(u.get('family')) for u in uncoded})),
            }
        )
    else:
        resolve_ticket("coding_sla")

    if cfg.coding_queue_floor and uncoded_n < cfg.coding_queue_floor:
        upsert_ticket(
            {
                "id": "coding_floor",
                "invariant": "coding_queue_floor",
                "owner": "sleeve_engineer",
                "severity": "info",
                "sla": "advisory",
                "next_action": "Brief asked for a floor of uncoded work; default floor is 0.",
                "detail": f"uncoded={uncoded_n} floor={cfg.coding_queue_floor}",
            }
        )
    else:
        resolve_ticket("coding_floor")

    eligible = len(standby) + len(remaining)
    allowed, why = auto_advance_gate()
    if len(live) >= cfg.wf_parallelism:
        resolve_ticket("wf_parallelism")
    elif len(live) < cfg.wf_parallelism and len(standby) > 0 and allowed:
        upsert_ticket(
            {
                "id": "wf_parallelism",
                "invariant": "wf_running",
                "owner": "desk_head",
                "severity": "warning",
                "sla": "same tick",
                "next_action": "Launch the next standby family now.",
                "detail": (
                    f"{len(live)} running, {len(standby)} standby, "
                    f"parallelism {cfg.wf_parallelism}."
                ),
            }
        )
    elif not allowed and len(live) < cfg.wf_parallelism:
        upsert_ticket(
            {
                "id": "wf_parallelism",
                "invariant": "wf_running",
                "owner": "desk_head",
                "severity": "warning",
                "sla": "paused",
                "next_action": "Clear the auto-advance block before the next start.",
                "detail": why,
            }
        )
    else:
        resolve_ticket("wf_parallelism")

    if len(standby) < cfg.standby_floor and eligible >= cfg.standby_floor:
        upsert_ticket(
            {
                "id": "standby_floor",
                "invariant": "standby_floor",
                "owner": "sleeve_engineer",
                "severity": "warning",
                "sla": "this cycle",
                "next_action": "Stage the next ranked hypothesis into standby.",
                "detail": f"standby={len(standby)} floor={cfg.standby_floor}",
            }
        )
        emit("on_standby_depth_low", {"standby": len(standby)})
    elif len(standby) < cfg.standby_floor:
        upsert_ticket(
            {
                "id": "standby_floor",
                "invariant": "standby_floor",
                "owner": "quant_researcher",
                "severity": "warning",
                "sla": "this cycle",
                "next_action": "Catalog has no envelope-cleared follow-up to stage.",
                "detail": f"standby={len(standby)} remaining_hypotheses={len(remaining)}",
            }
        )
    else:
        resolve_ticket("standby_floor")

    _flag_hung_jobs(jobs)
    return open_tickets()


def _flag_hung_jobs(jobs: list[dict[str, Any]]) -> None:
    threshold = hung_threshold_seconds(jobs)
    any_hung = False
    for job in live_jobs(jobs):
        elapsed = _age_seconds(str(job.get("started_at") or job.get("created_at") or ""))
        if elapsed is None or elapsed < threshold:
            continue
        any_hung = True
        upsert_ticket(
            {
                "id": f"hung_job_{job.get('id')}",
                "invariant": "hung_job",
                "owner": "ops_engineer",
                "severity": "warning",
                "sla": f"{int(threshold)}s (3x rolling median)",
                "next_action": "Inspect the validator log; do not treat elapsed time as progress.",
                "detail": (
                    f"Job {job.get('id')} {job.get('family')} running "
                    f"{int(elapsed)}s; hung threshold {int(threshold)}s."
                ),
            }
        )
    if not any_hung:
        for t in open_tickets():
            if str(t.get("id") or "").startswith("hung_job_"):
                resolve_ticket(str(t["id"]))


def backstop_sweep(source: str = "advance_pipeline") -> dict[str, Any]:
    """Cadenced sweep. Finding work the event layer should have handled is a defect."""
    from firm.research_jobs import list_jobs

    cfg = pipeline_config()
    jobs = list_jobs()
    try:
        from firm.postmortem import postmortem_for_job, write_postmortem
        from firm.research_jobs import _verdict_blurb

        for job in jobs:
            if job.get("status") not in {"done", "failed"}:
                continue
            if int(job.get("pairs_approved") or 0) > 0:
                continue
            jid = job.get("id")
            if jid is None:
                continue
            if postmortem_for_job(int(jid)) is None:
                write_postmortem(job, pair_blurbs=_verdict_blurb(job))
    except Exception:
        logger.exception("Post-mortem backfill failed")
    live = live_jobs(jobs)
    work_found = False
    dropped: list[str] = []
    if len(live) < cfg.wf_parallelism and standby_jobs(jobs):
        work_found = True
        dropped.append("on_walk_forward_slot_free")
    fill = fill_walk_forward_slots(source="backstop")
    if fill.get("started"):
        work_found = True
    tier_b = default_approve_tier_b()
    tickets = evaluate_invariants()
    try:
        from firm import memory

        if not memory.pending_proposals(limit=5) and not live_jobs(list_jobs()):
            emit("on_inbox_empty", {"source": source})
    except Exception:
        logger.exception("inbox empty emit failed")
    return {
        "source": source,
        "work_found": work_found,
        "dropped_events": dropped,
        "fill": fill,
        "tier_b_approved": tier_b,
        "tickets": len(tickets),
        "healthy": not work_found,
    }


def throughput_metrics(jobs: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Research KPIs while 0 pairs are approved. Hit%/PnL are the wrong scoreboard."""
    from firm.research_jobs import list_jobs

    if jobs is None:
        jobs = list_jobs()
    week_ago = _now() - timedelta(days=7)
    entered = 0
    stage_durations: dict[str, list[float]] = {}
    for job in jobs:
        started = _parse_iso(str(job.get("started_at") or job.get("created_at") or ""))
        if started and started >= week_ago and job.get("status") in {
            "running",
            "queued",
            "done",
            "failed",
            "standby",
        }:
            if job.get("status") != "standby":
                entered += 1
        stage = str(job.get("stage") or job.get("status") or "")
        entered_at = _parse_iso(str(job.get("entered_stage_at") or job.get("created_at") or ""))
        left = _parse_iso(str(job.get("finished_at") or "")) or _now()
        if entered_at and stage:
            stage_durations.setdefault(stage, []).append((left - entered_at).total_seconds())
    median_stage = {
        stage: int(median(vals)) if vals else 0 for stage, vals in stage_durations.items()
    }
    state = load_state()
    esc_open = open_tickets()
    cfg = pipeline_config()
    criteria = DEFAULT_CRITERIA
    return {
        "families_entering_wf_per_week": entered,
        "median_time_in_stage_seconds": median_stage,
        "catalog_depth": len(remaining_hypotheses(jobs)),
        "coding_queue_depth": len(
            {str(j.get("family")) for j in jobs if j.get("stage") == "coding"}
        ),
        "standby_depth": len(standby_jobs(jobs)),
        "running": len(live_jobs(jobs)),
        "open_invariant_violations": len(esc_open),
        "dropped_event_count": dropped_event_count(),
        "circuit_breaker_tripped": bool(state.get("circuit_breaker_tripped")),
        "consecutive_auto_rejects": int(state.get("consecutive_auto_rejects") or 0),
        "auto_advances_24h": sum(
            1
            for row in (state.get("auto_advances") or [])
            if (_parse_iso(str(row.get("at") or "")) or _now()) >= _now() - timedelta(hours=24)
        ),
        "thresholds": {
            "min_profit_factor": criteria.min_profit_factor,
            "min_oos_trades": criteria.min_oos_trades,
            "min_profitable_fold_ratio": criteria.min_profitable_fold_ratio,
            "max_parameter_cv": criteria.max_parameter_cv,
            "max_drawdown_pct": criteria.max_drawdown_pct,
            "note": (
                "0/6 is a real reject against these gates (ATR 4h shorts reached "
                "PF 1.20-1.27). The bar is reachable; auto-advance will not "
                "mask an unreachable threshold."
            ),
        },
        "config": cfg.snapshot(),
        "tickets": esc_open,
        "stage_owners": STAGE_OWNERS,
    }


def code_pending_sleeves() -> dict[str, Any]:
    """Register template specs as coded sleeves; escalate novel families.

    Template clones become JSON under config/sleeves. Does not write
    `core/strategy/*.py`. Novel math/feeds become a Cursor coding request.
    """
    from core.strategy.registry import list_strategies
    from firm.research_jobs import implementation_gaps, open_code_mandates
    from firm.sleeve_factory import materialize_pending_specs, spec_for_family

    coded_work = materialize_pending_specs()
    coded = set(list_strategies())
    novel: list[str] = list(coded_work.get("novel") or [])
    registered = stage_standby(source="sleeve_engineer")
    for row in open_code_mandates() + implementation_gaps():
        family = str(row.get("family") or "")
        if not family or family in coded:
            continue
        spec = spec_for_family(family)
        if spec is not None and spec.auto_code:
            from firm.sleeve_factory import materialize_spec

            materialize_spec(spec)
            coded.add(family)
            continue
        if family not in novel:
            novel.append(family)
        try:
            from firm import memory

            memory.escalate_once(
                agent="sleeve_engineer",
                title=f"Novel sleeve needs Cursor: {family}",
                detail=(
                    f"{family} is not an allowed template. Brief is under "
                    f"research/coding_requests/{family}.md. Sleeve Engineer "
                    "will not LLM-write core/strategy files."
                ),
                severity="warning",
                root_cause=f"novel_sleeve:{family}",
                owner_seat="sleeve_engineer",
            )
        except Exception:
            logger.exception("Could not escalate novel sleeve %s", family)
    evaluate_invariants()
    return {
        "standby_staged": registered,
        "novel": novel,
        "materialized": coded_work.get("materialized") or [],
        "coded_registry": sorted(list_strategies()),
    }
