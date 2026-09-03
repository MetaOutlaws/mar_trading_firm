"""
Research work queue: what happens after you approve a hypothesis.

Inbox approve used to only flip a SQLite flag. This module records the next
step, starts a walk-forward when the family is coded, and exposes a pipeline
the desk can draw so the operator is not left guessing.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

from config.pipeline import APPROVED_RESEARCH_SYMBOLS
from config.settings import PROJECT_ROOT
from core.strategy.registry import list_strategies
from firm.locks import pid_alive
from firm.research_catalog import FAMILIES_NEEDING_FEED, RESEARCH_FAMILIES, next_catalog_step

logger = logging.getLogger(__name__)

JOBS_PATH = PROJECT_ROOT / "data" / "research_jobs.json"
# Last successfully parsed ledger. A truncated rewrite must not look like a
# greenfield start (ids 1-N) and then auto-advance CLOCK_BY_FAMILY leftovers.
_LAST_GOOD_JOBS: list[dict[str, Any]] | None = None
DEFAULT_MAJORS = list(APPROVED_RESEARCH_SYMBOLS)
CLOCK_BY_FAMILY = {
    "donchian_breakout": "1h/4h",
    "rsi_trend": "15m/4h",
    "ema_adx_trend": "4h/4h",
    "funding_fade": "4h/4h",
    "bollinger_mean_reversion": "4h/4h",
    "trend_pullback_htf": "1h/1h",
    "atr_channel_breakout": "4h/4h",
    "bb_squeeze_breakout": "4h/4h",
    "rsi_fade_chop": "4h/4h",
    "macd_trend_pullback": "4h/4h",
    "atr_fade_chop": "4h/4h",
    "volume_climax_fade": "4h/4h",
    "opening_range_breakout": "1h/1h",
    "utc_session_vwap_reversion": "1h/1h",
    "asian_range_breakout": "1h/1h",
    "inside_bar_breakout": "4h/4h",
    "swing_failure_reversal": "4h/4h",
    "consecutive_bar_exhaustion": "4h/4h",
    "wick_rejection_reversal": "1h/1h",
    "prior_day_pivot_breakout": "1h/1h",
    "weekend_gap_fill": "4h/4h",
    "engulfing_reversal": "4h/4h",
    "utc_midnight_gap_fill": "1h/1h",
    "london_session_breakout": "1h/1h",
    "ny_cash_open_drive": "1h/1h",
    "three_bar_play": "4h/4h",
    "outside_bar_reversal": "4h/4h",
    "doji_star_reversal": "4h/4h",
    "round_number_fade": "1h/1h",
    "prior_week_high_break": "4h/4h",
    "utc_session_twap_reversion": "1h/1h",
    "failed_higher_high": "4h/4h",
    "nr7_breakout": "4h/4h",
    "stochastic_fade": "4h/4h",
    "cci_reversion": "4h/4h",
    "supertrend_flip": "4h/4h",
    "heikin_ashi_trend": "4h/4h",
    "williams_r_fade": "4h/4h",
    "obv_break": "4h/4h",
    "ichimoku_tk_cross": "4h/4h",
    "mfi_fade": "4h/4h",
    "aroon_crossover": "4h/4h",
    "awesome_oscillator_saucer": "4h/4h",
    "force_index_fade": "4h/4h",
    "trix_cross": "4h/4h",
    "dpo_cycle_fade": "4h/4h",
    "vortex_cross": "4h/4h",
    "chande_momentum_fade": "4h/4h",
    "chaikin_oscillator_cross": "4h/4h",
    "ppo_cross": "4h/4h",
    "ultimate_oscillator_fade": "4h/4h",
    "kst_cross": "4h/4h",
    "tsi_cross": "4h/4h",
    "fisher_transform_cross": "4h/4h",
    "hull_ma_trend": "4h/4h",
    "elder_ray_fade": "4h/4h",
    "schaff_trend_cross": "4h/4h",
    "mass_index_reversal": "4h/4h",
    "ease_of_movement_fade": "4h/4h",
    "coppock_curve_cross": "4h/4h",
    "qstick_cross": "4h/4h",
    "relative_vigor_cross": "4h/4h",
    "klinger_volume_cross": "4h/4h",
    "kaufman_efficiency_trend": "4h/4h",
    "demarker_fade": "4h/4h",
    "choppiness_index_break": "4h/4h",
    "connors_rsi_fade": "4h/4h",
    "mama_fama_cross": "4h/4h",
    "center_of_gravity_cross": "4h/4h",
    "parabolic_sar_flip": "4h/4h",
    "twiggs_money_flow_fade": "4h/4h",
    "balance_of_power_cross": "4h/4h",
    "volume_price_trend_break": "4h/4h",
    "kairi_relative_fade": "4h/4h",
    "linreg_slope_cross": "4h/4h",
    "ehlers_decycler_cross": "4h/4h",
    "psychological_line_cross": "4h/4h",
    "rsi_laguerre_fade": "4h/4h",
    "vidya_trend": "4h/4h",
    "t3_trend": "4h/4h",
    "chaikin_money_flow_fade": "4h/4h",
    "accumulation_distribution_break": "4h/4h",
    "zero_lag_ema_cross": "4h/4h",
    "smi_fade": "4h/4h",
    "elder_impulse_trend": "4h/4h",
    "rainbow_oscillator_cross": "4h/4h",
    "laguerre_filter_cross": "4h/4h",
    "gator_oscillator_cross": "4h/4h",
    "williams_fractal_break": "4h/4h",
    "kama_trend": "4h/4h",
    "dema_cross": "4h/4h",
    "tema_cross": "4h/4h",
    "alma_trend": "4h/4h",
    "keltner_break": "4h/4h",
    "stochrsi_fade": "4h/4h",
    "chandelier_exit_flip": "4h/4h",
    "mcginley_dynamic_cross": "4h/4h",
    "super_smoother_cross": "4h/4h",
    "roofing_filter_cross": "4h/4h",
    "squeeze_momentum_break": "4h/4h",
    "volume_weighted_macd_cross": "4h/4h",
    "volume_force_divergence": "4h/4h",
    "session_liquidity_sweep": "1h/1h",
    "bar_vwap_inflow_surge": "4h/4h",
    "fib_retracement_bounce": "4h/4h",
    "fib_extension_break": "4h/4h",
    "measured_move_break": "4h/4h",
    "up_down_turnover_imbalance": "4h/4h",
    "signed_range_turnover_trend": "4h/4h",
    "swing_anchored_vwap_pullback": "4h/4h",
}
# Re-exported so callers that imported from this module keep working.


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def infer_family(payload: dict[str, Any] | None, title: str = "") -> str:
    """Map a Quant hypothesis name onto a catalog family id."""
    payload = payload or {}
    explicit = str(payload.get("family") or "").strip().lower()
    if explicit and explicit not in {"unknown", "strategy"}:
        return explicit
    blob = " ".join(
        [
            str(payload.get("name") or ""),
            title,
        ]
    ).lower()
    if "donchian" in blob:
        return "donchian_breakout"
    if "opening" in blob and "range" in blob:
        return "opening_range_breakout"
    if "funding" in blob:
        return "funding_fade"
    if "ema" in blob and "adx" in blob:
        return "ema_adx_trend"
    if "bollinger" in blob or "mean rev" in blob or "mean_rev" in blob:
        return "bollinger_mean_reversion"
    if "atr" in blob and "breakout" in blob:
        return "atr_channel_breakout"
    if "pullback" in blob or "two_time" in blob or "two-time" in blob:
        return "trend_pullback_htf"
    if "rsi" in blob or "golden" in blob:
        return "rsi_trend"
    return str((payload or {}).get("name") or "unknown")


def _jobs_lock_path() -> Path:
    return JOBS_PATH.with_suffix(JOBS_PATH.suffix + ".lock")


@contextmanager
def _jobs_file_lock() -> Iterator[None]:
    """Serialize ledger reads/writes so two ticks cannot clobber the file."""
    path = _jobs_lock_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+")
    try:
        try:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        except (ImportError, OSError):
            pass
        yield
    finally:
        try:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except (ImportError, OSError):
            pass
        handle.close()


def _parse_jobs_blob(raw_text: str) -> list[dict[str, Any]] | None:
    try:
        raw = json.loads(raw_text)
    except json.JSONDecodeError:
        return None
    if not isinstance(raw, dict):
        return None
    jobs = raw.get("jobs")
    if jobs is None:
        return []
    if not isinstance(jobs, list):
        return None
    return [row for row in jobs if isinstance(row, dict)]


def _read_jobs_path(path: Path) -> list[dict[str, Any]] | None:
    if not path.exists():
        return None
    try:
        return _parse_jobs_blob(path.read_text(encoding="utf-8"))
    except OSError:
        return None


def _atomic_write_jobs(jobs: list[dict[str, Any]]) -> None:
    JOBS_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {"updated_at": utcnow_iso(), "jobs": jobs}
    tmp = JOBS_PATH.with_suffix(JOBS_PATH.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    bak = JOBS_PATH.with_suffix(JOBS_PATH.suffix + ".bak")
    if JOBS_PATH.exists():
        try:
            os.replace(JOBS_PATH, bak)
        except OSError:
            logger.exception("Could not rotate research_jobs.bak")
    os.replace(tmp, JOBS_PATH)


def _merge_jobs_by_id(
    incoming: list[dict[str, Any]], on_disk: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Never drop ledger rows. Incoming updates win for the same id."""
    merged: dict[int, dict[str, Any]] = {}
    for row in on_disk:
        try:
            jid = int(row.get("id") or 0)
        except (TypeError, ValueError):
            jid = 0
        if jid:
            merged[jid] = dict(row)
    for row in incoming:
        try:
            jid = int(row.get("id") or 0)
        except (TypeError, ValueError):
            jid = 0
        if jid:
            merged[jid] = dict(row)
    return [merged[k] for k in sorted(merged)]


def _load() -> list[dict[str, Any]]:
    global _LAST_GOOD_JOBS
    with _jobs_file_lock():
        parsed = _read_jobs_path(JOBS_PATH)
        if parsed is not None:
            _LAST_GOOD_JOBS = parsed
            return parsed
        if not JOBS_PATH.exists():
            _LAST_GOOD_JOBS = None
            return []
        bak = _read_jobs_path(JOBS_PATH.with_suffix(JOBS_PATH.suffix + ".bak"))
        if bak is not None:
            logger.error("research_jobs.json unreadable; restored from .bak")
            _LAST_GOOD_JOBS = bak
            return bak
        if _LAST_GOOD_JOBS is not None:
            logger.error(
                "research_jobs.json unreadable; keeping last good snapshot "
                "(%s jobs) instead of resetting to empty",
                len(_LAST_GOOD_JOBS),
            )
            return list(_LAST_GOOD_JOBS)
        if JOBS_PATH.exists() and JOBS_PATH.stat().st_size > 0:
            logger.error(
                "research_jobs.json unreadable and no snapshot; refusing to "
                "treat a non-empty file as an empty ledger"
            )
            return []
        return []


def _save(jobs: list[dict[str, Any]]) -> None:
    global _LAST_GOOD_JOBS
    with _jobs_file_lock():
        on_disk = _read_jobs_path(JOBS_PATH) or []
        if not on_disk:
            on_disk = _read_jobs_path(JOBS_PATH.with_suffix(JOBS_PATH.suffix + ".bak")) or []
        if not jobs and on_disk:
            logger.error("Refusing to wipe research_jobs.json (%s rows on disk)", len(on_disk))
            return
        merged = _merge_jobs_by_id(jobs, on_disk)
        # A process that loaded a stale 32-row snapshot must not replace a
        # 220-row ledger. Keep the larger id set; incoming updates still apply.
        if on_disk and len(merged) < len(on_disk):
            logger.error(
                "Refusing jobs ledger shrink %s -> %s",
                len(on_disk),
                len(merged),
            )
            merged = _merge_jobs_by_id(jobs, on_disk)
        _atomic_write_jobs(merged)
        _LAST_GOOD_JOBS = merged


def _pid_alive(pid: int | None) -> bool:
    return pid_alive(pid)


def refresh_job_liveness(jobs: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """If a spawned validator died, mark the job failed so the desk does not spin."""
    rows = jobs if jobs is not None else _load()
    changed = False
    for job in rows:
        if job.get("status") != "running":
            continue
        pid = job.get("pid")
        if pid and not _pid_alive(int(pid)):
            job["status"] = "failed"
            job["finished_at"] = utcnow_iso()
            job["detail"] = (
                job.get("detail") or ""
            ) + " Process exited before writing a verdict; check logs/research_jobs."
            changed = True
            try:
                from firm.research_catalog import record_finished_walk_forward

                record_finished_walk_forward(job)
            except Exception:
                logger.exception("Could not record finished grid for dead job %s", job.get("id"))
    if changed:
        _save(rows)
    return rows


def list_jobs() -> list[dict[str, Any]]:
    return refresh_job_liveness()


def paper_scan_family() -> str:
    """Sleeve the paper clock should scan. Reads the job ledger only.

    Running job wins, then queued, then the pipeline_state pointer, then the
    latest finished coded job. Seats must not reconstruct this independently.
    """
    from firm.pipeline_state import load_state

    coded = set(list_strategies())
    jobs = list_jobs()
    for status in ("running", "queued"):
        hits = [j for j in jobs if j.get("status") == status and j.get("family") in coded]
        if hits:
            return str(hits[-1].get("family") or "rsi_trend")
    for job in reversed(jobs):
        family = str(job.get("family") or "")
        if family in coded and job.get("status") in {"done", "failed", "standby", "gated"}:
            return family
    pointer = str((load_state() or {}).get("current_family") or "")
    if pointer in coded:
        return pointer
    return "rsi_trend"


def _active_job_for(family: str) -> dict[str, Any] | None:
    for job in refresh_job_liveness():
        if job.get("family") == family and job.get("status") in {"queued", "running"}:
            return job
    return None


def ensure_family_ready_to_test(family: str) -> dict[str, Any]:
    """On approve: materialize a template, or write/escalate a Cursor brief.

    Template families become JSON under config/sleeves and land in the registry
    in this call. Novel families get a coding request; Sleeve Engineer will not
    LLM-write core/strategy Python. If that Python already exists, this is a no-op.
    """
    from firm.sleeve_factory import (
        materialize_spec,
        spec_for_family,
        write_coding_request,
        _escalate_novel,
    )
    from core.strategy.spec_sleeve import load_spec_sleeves

    slug = (family or "").strip().lower()
    if not slug:
        return {"family": slug, "coded": False, "action": "unknown"}
    if slug in set(list_strategies()):
        return {"family": slug, "coded": True, "action": "already_coded"}
    spec = spec_for_family(slug)
    if spec is None:
        return {"family": slug, "coded": False, "action": "unknown"}
    if spec.auto_code:
        materialize_spec(spec)
        load_spec_sleeves()
        return {
            "family": slug,
            "coded": slug in set(list_strategies()),
            "action": "materialized",
        }
    path = write_coding_request(spec)
    _escalate_novel(spec)
    return {
        "family": slug,
        "coded": slug in set(list_strategies()),
        "action": "coding_request",
        "brief": str(path),
    }


def on_operator_approved(proposal: dict[str, Any]) -> dict[str, Any]:
    """Route an Inbox (or Research-tab) approve onto the next real piece of work.

    The operator's gate is the approve. After that the floor must continue:
    template family → materialize JSON then walk-forward; novel family already
    in the registry → walk-forward; novel still uncoded → coding request, and
    catch-up starts walk-forward the moment the sleeve is registered.
    """
    payload = proposal.get("payload") if isinstance(proposal.get("payload"), dict) else {}
    action = str(payload.get("action") or "")
    kind = str(proposal.get("kind") or "")
    title = str(proposal.get("title") or "")

    if kind == "strategy" or action == "walk_forward":
        routed = dict(proposal)
        routed["kind"] = "strategy"
        if action == "walk_forward" and not payload.get("name"):
            routed["payload"] = {**payload, "name": payload.get("family") or infer_family(payload, title)}
        return on_strategy_approved(routed)

    if action == "catalog_review":
        return {
            "queued": False,
            "family": "funding_fade",
            "next_step": (
                "Recorded. This does not start a walk-forward. funding_fade still "
                "needs a feed. Name a new family to code, add that feed, or pause. "
                "Approving this gate is not a live-trading decision."
            ),
        }

    if action == "code_family":
        family = str(payload.get("family") or infer_family(payload, title))
        ready = ensure_family_ready_to_test(family)
        if family in set(list_strategies()):
            clock = str(CLOCK_BY_FAMILY.get(family) or payload.get("clock") or "4h/4h")
            result = on_strategy_approved(
                {
                    "id": proposal.get("id"),
                    "kind": "strategy",
                    "title": title or f"Test {family}",
                    "payload": {**payload, "name": family, "clock": clock},
                    "status": "approved",
                }
            )
            if result.get("queued"):
                how = ready.get("action") or "already_coded"
                suffix = (
                    " Template JSON just landed in the registry."
                    if how == "materialized"
                    else ""
                )
                result["next_step"] = (
                    f"Approved. {family} is coded, so walk-forward is starting now. "
                    f"You do not need to approve a second time.{suffix}"
                )
            result["coding"] = ready
            return result
        brief = ready.get("brief") or f"research/coding_requests/{family}.md"
        brief_text = str(payload.get("brief") or "")
        if not brief_text:
            md_path = PROJECT_ROOT / "research" / "coding_requests" / f"{family}.md"
            if md_path.exists():
                brief_text = md_path.read_text(encoding="utf-8")
        from firm.cursor_coding import enqueue_approved

        enqueue_approved(
            family=family,
            brief=brief_text,
            brief_path=str(brief),
            proposal_id=int(proposal.get("id") or 0) or None,
        )
        return {
            "queued": False,
            "family": family,
            "mandate": "implement",
            "handed_to_cursor": True,
            "coding": ready,
            "next_step": (
                f"Approved. The brief for {family} is now the Cursor ticket "
                f"(research/coding_inbox/NOW.md). Open a Cursor agent on this repo — "
                f"it is required to implement that file. Walk-forward starts by itself "
                f"when the sleeve is in the registry."
            ),
        }

    return {
        "queued": False,
        "next_step": "Decision recorded. This was not a research-pipeline approve.",
    }


def on_strategy_approved(proposal: dict[str, Any]) -> dict[str, Any]:
    """Called after a human approves an inbox strategy proposal."""
    kind = str(proposal.get("kind") or "")
    if kind != "strategy":
        return {
            "queued": False,
            "next_step": "Decision recorded. This was not a strategy test, so nothing is queued.",
        }

    payload = proposal.get("payload") if isinstance(proposal.get("payload"), dict) else {}
    title = str(proposal.get("title") or "")
    family = infer_family(payload, title)
    coded = family in set(list_strategies())

    from firm import memory

    memory.mark_research_status(
        family,
        status="queued" if coded else "proposed",
        verdict=(
            "Queued for walk-forward on majors."
            if coded
            else "Approved in principle, but this family is not coded yet."
        ),
    )

    if not coded:
        return {
            "queued": False,
            "family": family,
            "next_step": (
                f"Approved, but {family} is not coded yet, so no walk-forward was started. "
                "That is a catalog item to implement, not a test. "
                "It does not block the pipeline."
            ),
        }

    # Inbox clock wins so a follow-up (ATR 1h after 4h) is not forced back to the default.
    requested_clock = str(payload.get("clock") or CLOCK_BY_FAMILY.get(family) or "15m/4h")
    tested = _clocks_tested(family)
    if requested_clock in tested and not payload.get("force_retest"):
        return {
            "queued": False,
            "family": family,
            "next_step": (
                f"{family} already finished walk-forward at {requested_clock}. "
                "We will not silently run it again. The next catalog step is in Inbox."
            ),
        }

    existing = _active_job_for(family)
    if existing:
        ids = list(existing.get("proposal_ids") or [])
        if proposal.get("id") not in ids:
            ids.append(proposal.get("id"))
            existing["proposal_ids"] = ids
            jobs = _load()
            for row in jobs:
                if row.get("id") == existing["id"]:
                    row["proposal_ids"] = ids
            _save(jobs)
        return {
            "queued": True,
            "job_id": existing["id"],
            "family": family,
            "next_step": (
                f"Already in motion: walk-forward for {family} is {existing.get('status')}. "
                "Watch the pipeline on Overview / Floor."
            ),
        }

    symbols = list(DEFAULT_MAJORS)
    side = str(payload.get("side") or "BOTH").upper() or "BOTH"
    timeframe = ""
    clock = requested_clock

    job = _record_job(
        family=family,
        proposal_id=proposal.get("id"),
        symbols=symbols,
        side=side,
        timeframe=timeframe,
        clock=clock,
        status="queued",
        hypothesis_id=payload.get("hypothesis_id") or "",
        envelope_tier=payload.get("tier") or "",
        stage="walk_forward",
        owner_seat="desk_head",
        last_updated_by="operator",
        detail=f"Starting walk-forward validator ({clock}).",
    )
    started = start_job(job["id"])
    status = "running" if started else "queued"
    return {
        "queued": True,
        "job_id": job["id"],
        "family": family,
        "next_step": (
            (
                f"Walk-forward started for {family} on {', '.join(symbols)} ({side}). "
                "This takes several minutes. The pipeline on Overview will move to "
                "Testing, then a verdict appears on Strategies."
            )
            if started
            else f"Queued {family}, but the validator process did not start. Check logs."
        ),
        "status": status,
    }


def _record_job(**fields: Any) -> dict[str, Any]:
    from firm.research_catalog import history_max_job_id, note_job_id

    jobs = _load()
    now = utcnow_iso()
    next_id = max(
        max((int(j.get("id") or 0) for j in jobs), default=0),
        history_max_job_id(),
    ) + 1
    job = {
        "id": next_id,
        "created_at": now,
        "finished_at": None,
        "pid": None,
        "proposal_ids": [fields.get("proposal_id")] if fields.get("proposal_id") else [],
        "log_path": "",
        "stage": fields.get("stage") or fields.get("status") or "queued",
        "owner_seat": fields.get("owner_seat") or "",
        "entered_stage_at": now,
        "blocked_by": fields.get("blocked_by") or "",
        "next_action": fields.get("next_action") or "",
        "next_action_owner": fields.get("next_action_owner") or "",
        "last_updated_by": fields.get("last_updated_by") or "research_pipeline",
        **{k: v for k, v in fields.items() if k != "proposal_id"},
    }
    jobs.append(job)
    _save(jobs)
    try:
        note_job_id(int(job["id"]))
    except Exception:
        logger.exception("Could not persist walk-forward job id sequencer")
    return job


def stamp_job(job_id: int, **fields: Any) -> dict[str, Any] | None:
    """Patch one ledger row and write canonical stage ownership fields."""
    from firm.continuity import stamp_ledger

    jobs = _load()
    for job in jobs:
        if int(job.get("id") or 0) != int(job_id):
            continue
        stage = str(fields.pop("stage", job.get("stage") or job.get("status") or "queued"))
        updated_by = str(fields.pop("updated_by", job.get("last_updated_by") or "research_pipeline"))
        next_action = str(fields.pop("next_action", job.get("next_action") or ""))
        next_action_owner = str(
            fields.pop("next_action_owner", job.get("next_action_owner") or "")
        )
        blocked_by = str(fields.pop("blocked_by", job.get("blocked_by") or ""))
        job.update(fields)
        stamp_ledger(
            job,
            stage=stage,
            updated_by=updated_by,
            next_action=next_action,
            next_action_owner=next_action_owner,
            blocked_by=blocked_by,
        )
        _save(jobs)
        return job
    return None


def start_job(job_id: int) -> bool:
    """Spawn `scripts/validate_strategy.py` for a queued job."""
    from config.pipeline import pipeline_config

    jobs = _load()
    job = next((j for j in jobs if j.get("id") == job_id), None)
    if job is None:
        return False
    running_only = [j for j in jobs if j.get("status") == "running"]
    cap = pipeline_config().wf_parallelism
    if len(running_only) >= cap:
        job["status"] = "standby"
        job["detail"] = (
            f"Walk-forward cap {cap} is full. This job waits in standby."
        )
        job["stage"] = "standby"
        _save(jobs)
        return False
    family = str(job.get("family") or "rsi_trend")
    symbols = [str(s) for s in (job.get("symbols") or DEFAULT_MAJORS)]
    side = str(job.get("side") or "BOTH")
    log_dir = PROJECT_ROOT / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"research_job_{job_id}.log"
    cmd = [
        sys.executable,
        str(PROJECT_ROOT / "scripts" / "validate_strategy.py"),
        "--strategy",
        family,
        "--side",
        side,
        "--job-id",
        str(job_id),
        "--symbols",
        *symbols,
    ]
    timeframe = _validator_timeframe(str(job.get("clock") or job.get("timeframe") or ""))
    if timeframe:
        cmd.extend(["--timeframe", timeframe])
    try:
        handle = log_path.open("w", encoding="utf-8")
        kwargs: dict[str, Any] = {
            "cwd": str(PROJECT_ROOT),
            "stdout": handle,
            "stderr": subprocess.STDOUT,
        }
        if os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]
        proc = subprocess.Popen(cmd, **kwargs)
    except OSError as exc:
        logger.exception("Could not start research job %s", job_id)
        job["status"] = "failed"
        job["detail"] = f"spawn failed: {exc}"
        job["finished_at"] = utcnow_iso()
        _save(jobs)
        return False

    job["status"] = "running"
    job["pid"] = proc.pid
    job["log_path"] = str(log_path)
    job["detail"] = f"Validator pid {proc.pid} on {family}."
    job["started_at"] = utcnow_iso()
    job["stage"] = "walk_forward"
    job["owner_seat"] = "desk_head"
    job["last_updated_by"] = "desk_head"
    job["next_action"] = "collect_verdicts"
    job["next_action_owner"] = "desk_head"
    _save(jobs)
    logger.info("Research job %s started pid=%s cmd=%s", job_id, proc.pid, cmd)
    return True


def finish_job(job_id: int, summary: str, ok: bool, pairs_approved: int | None = None) -> None:
    jobs = _load()
    for job in jobs:
        if job.get("id") != job_id:
            continue
        job["status"] = "done" if ok else "failed"
        job["finished_at"] = utcnow_iso()
        job["detail"] = summary
        job["pid"] = None
        if pairs_approved is not None:
            job["pairs_approved"] = pairs_approved
    _save(jobs)
    from firm import memory

    job = next((j for j in jobs if j.get("id") == job_id), None)
    if job:
        try:
            from firm.research_catalog import record_finished_walk_forward

            record_finished_walk_forward(job)
        except Exception:
            logger.exception("Could not record finished walk-forward for job %s", job_id)
        if not ok:
            research_status = "rejected"
        elif pairs_approved == 0:
            research_status = "rejected"
        else:
            research_status = "validated"
        memory.mark_research_status(
            str(job.get("family") or ""),
            status=research_status,
            verdict=summary,
        )
        try:
            _notify_job_complete(job)
        except Exception:
            logger.exception("Inbox update failed for research job %s", job_id)
        try:
            from firm.integrity import certify_and_store_job

            certify_and_store_job(job)
        except Exception:
            logger.exception("Integrity certificate failed for research job %s", job_id)
        try:
            from firm.continuity import on_job_finished, stamp_ledger

            stamp_ledger(
                job,
                stage="postmortem" if (pairs_approved or 0) == 0 else "verdict",
                updated_by="performance_auditor",
                next_action="fill_slot",
                next_action_owner="desk_head",
            )
            jobs = _load()
            for row in jobs:
                if row.get("id") == job_id:
                    row.update(job)
            _save(jobs)
            on_job_finished(job)
        except Exception:
            logger.exception("Continuity handler failed for research job %s", job_id)


def _validator_timeframe(clock: str) -> str:
    """If both sides share a clock (1h/1h, 4h/4h), pass that as --timeframe."""
    parts = [p.strip() for p in str(clock or "").split("/") if p.strip()]
    if len(parts) == 2 and parts[0] == parts[1]:
        return parts[0]
    return ""


def _clocks_tested(family: str) -> set[str]:
    """Which timeframe clocks this family has already finished.

    Includes the durable history and paper book so a jobs-ledger reset cannot
    make CLOCK_BY_FAMILY look like an untested default clock.
    """
    from firm.research_catalog import durable_tested_keys

    out: set[str] = set()
    for job in _load():
        if job.get("family") != family:
            continue
        if job.get("status") not in {"done", "failed"}:
            continue
        _backfill_clock(job)
        if job.get("clock"):
            out.add(str(job["clock"]))
    prefix = f"{family}@"
    for key in durable_tested_keys(_load()):
        if not str(key).startswith(prefix):
            continue
        clock = str(key)[len(prefix) :].split("@")[0]
        if clock:
            out.add(clock)
    return out


def _backfill_clock(job: dict[str, Any]) -> None:
    if job.get("clock"):
        return
    detail = str(job.get("detail") or "")
    if "15m" in detail:
        job["clock"] = "15m/4h"
    elif "1h" in detail:
        job["clock"] = "1h/4h"
    else:
        job["clock"] = CLOCK_BY_FAMILY.get(str(job.get("family") or ""), "15m/4h")


def _verdict_blurb(job: dict[str, Any]) -> str:
    path = Path(str(job.get("log_path") or ""))
    if path.exists():
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            lines = []
        heads = []
        for line in lines:
            if "VERDICT:" not in line:
                continue
            snippet = line.split("VERDICT:", 1)[-1].strip()
            heads.append(snippet.split("(")[0].strip())
        if heads:
            return "; ".join(heads)
    return str(job.get("detail") or "Walk-forward finished.")


def _next_step_spec(job: dict[str, Any]) -> dict[str, Any] | None:
    """What should run next. Continuity auto-starts Tier A; Inbox is for B/C."""
    from firm.research_catalog import remaining_hypotheses

    remaining = remaining_hypotheses()
    if remaining:
        row = remaining[0]
        fid = str(row["family"])
        name = str(row.get("name") or fid)
        clock = str(row.get("clock") or "4h/4h")
        return {
            "kind": "strategy",
            "title": f"Next: walk-forward {name}",
            "family": fid,
            "action": "walk_forward",
            "clock": clock,
            "side": row.get("side") or "BOTH",
            "hypothesis_id": row.get("id"),
            "rationale": str(row.get("justification") or ""),
        }
    # Do not invent a CLOCK_BY_FAMILY leftover (including Donchian 1h/4h)
    # just because remaining is empty. Idle is the correct next step.
    tested = _tested_families()
    family = str(job.get("family") or "")
    if family:
        tested.add(family)
    return next_catalog_step(tested=tested, coded=set(list_strategies()))


def _tested_families() -> set[str]:
    """Families that already have a finished (or failed) walk-forward."""
    return {
        str(j.get("family"))
        for j in _load()
        if j.get("status") in {"done", "failed"} and j.get("family")
    }


def _already_pending_next(action: str, family: str) -> bool:
    from firm import memory

    for proposal in memory.pending_proposals(limit=100):
        payload = proposal.get("payload") if isinstance(proposal.get("payload"), dict) else {}
        if payload.get("action") == action and (
            payload.get("family") == family or payload.get("name") == family
        ):
            return True
        title = str(proposal.get("title") or "")
        if action == "walk_forward" and title.lower().startswith("next: walk-forward"):
            blob = title.lower()
            if family and family.replace("_", " ") in blob.replace("-", " "):
                return True
        if action == "catalog_review" and "catalog exhausted" in title.lower():
            return True
    return False


def _already_decided_catalog_review() -> bool:
    """Do not re-file the exhaustion gate after the operator already answered."""
    from sqlalchemy import select

    from core.db import session_scope
    from firm.memory_models import Proposal, ProposalStatus

    decided = {ProposalStatus.APPROVED.value, ProposalStatus.REJECTED.value}
    with session_scope() as session:
        rows = session.scalars(
            select(Proposal)
            .where(Proposal.status.in_(decided))
            .order_by(Proposal.created_at.desc())
            .limit(40)
        )
        for proposal in rows:
            payload = proposal.payload if isinstance(proposal.payload, dict) else {}
            if payload.get("action") == "catalog_review":
                return True
            if "catalog exhausted" in str(proposal.title or "").lower():
                return True
    return False


def _catalog_review_spec(job: dict[str, Any]) -> dict[str, Any]:
    """Human gate when every coded family has a verdict and none passed."""
    family = str(job.get("family") or "strategy")
    return {
        "kind": "operational",
        "title": "Catalog exhausted - funding fade still needs a feed",
        "family": "funding_fade",
        "action": "catalog_review",
        "clock": "",
        "rationale": (
            f"{family} did not pass walk-forward. Every coded catalog family "
            "now has a verdict (none approved a pair). funding_fade is next in "
            "rank but has no feed — approving this does not start a test. "
            "Name a new family to code, add a funding feed, or pause research. "
            "Empty Inbox here is a GM miss."
        ),
    }


def _notify_job_complete(job: dict[str, Any]) -> None:
    """Inbox: a verdict to read. Next-step gates are for Tier B/C only."""
    if job.get("inbox_posted"):
        return
    from config.pipeline import pipeline_config
    from firm import memory
    from firm.memory_models import ProposalKind

    _backfill_clock(job)
    family = str(job.get("family") or "strategy")
    clock = str(job.get("clock") or "")
    pairs = job.get("pairs_approved")
    passed = int(pairs or 0) > 0
    blurb = _verdict_blurb(job)
    outcome = "passed" if passed else "rejected"
    memory.escalate(
        agent="research_pipeline",
        title=f"Verdict: {family} {clock} {outcome} ({pairs if pairs is not None else '?'} pairs)",
        detail=(
            f"{job.get('detail') or ''}\n\n"
            f"Pair results: {blurb}\n\n"
            "Tier A follow-ups start from standby in this tick. Paper-to-live "
            "still needs you. This alert is a verdict, not a go-live grant."
        )[:2000],
        severity="warning" if not passed else "info",
    )
    # Continuity auto-starts Tier A. Only file Inbox when auto-advance is off.
    if not pipeline_config().auto_advance:
        nxt = _next_step_spec(job)
        if nxt and not _already_pending_next(str(nxt["action"]), str(nxt["family"])):
            kind = ProposalKind.STRATEGY if nxt["kind"] == "strategy" else ProposalKind.OPERATIONAL
            memory.record_proposal(
                agent="research_pipeline",
                kind=kind,
                title=nxt["title"],
                payload={
                    "name": nxt["family"],
                    "family": nxt["family"],
                    "action": nxt["action"],
                    "clock": nxt.get("clock") or "",
                    "operator_next": True,
                    "from_job_id": job.get("id"),
                },
                rationale=nxt["rationale"],
                confidence=0.9,
                ttl=timedelta(days=14),
            )
    job["inbox_posted"] = True
    jobs = _load()
    for row in jobs:
        if row.get("id") == job.get("id"):
            row["inbox_posted"] = True
            if job.get("clock"):
                row["clock"] = job["clock"]
    _save(jobs)


def notify_finished_jobs() -> list[int]:
    """Catch up Inbox updates for jobs that finished before this path existed."""
    posted: list[int] = []
    for job in _load():
        if job.get("status") not in {"done", "failed"}:
            continue
        if job.get("inbox_posted"):
            continue
        if str(job.get("family") or "") not in set(list_strategies()):
            continue
        _notify_job_complete(job)
        posted.append(int(job["id"]))
    return posted


def open_code_mandates() -> list[dict[str, Any]]:
    """Approved 'code this family' items that are not yet a finished walk-forward.

    This is the stall the desk used to hide: Inbox empty, mandate approved,
    family not in the registry, GM reporting idle. Phase is `implement` until
    the sleeve is registered, then `start_test` until catch-up spawns a job.
    """
    from firm import memory

    coded = set(list_strategies())
    jobs = _load()
    open_rows: list[dict[str, Any]] = []
    for proposal in memory.approved_code_mandates(limit=20):
        family = infer_family(proposal.get("payload") or {}, proposal.get("title") or "")
        if not family or family == "rsi_trend":
            continue
        has_job = any(
            j.get("family") == family
            and j.get("status") in {"done", "running", "queued", "failed"}
            for j in jobs
        )
        if has_job:
            continue
        phase = "start_test" if family in coded else "implement"
        open_rows.append({**proposal, "family": family, "phase": phase})
    return open_rows


def implementation_gaps() -> list[dict[str, Any]]:
    """Approved coding mandates whose sleeve is still not in the registry.

    Catch-up can start walk-forward the moment the file exists. Nothing in the
    running firm writes `core/strategy/*.py`. An open implement mandate is a
    miss, not a green 'in progress' bar.
    """
    return [row for row in open_code_mandates() if row.get("phase") == "implement"]


def flag_implementation_gap() -> list[str]:
    """Escalate as soon as an approved sleeve is missing, not after the operator notices."""
    from firm import memory

    flagged: list[str] = []
    for row in implementation_gaps():
        family = str(row.get("family") or "strategy")
        eid = memory.escalate_once(
            agent="desk_head",
            title=f"Implementation overdue: {family}",
            detail=(
                f"{family} was approved for coding and is not in the strategy "
                "registry. No walk-forward is running. No employee writes "
                "strategy files — catch-up only starts the validator after the "
                "sleeve exists. Elapsed wait time is not completion. Code the "
                "file; the next paper cycle will start the test."
            ),
            severity="warning",
        )
        if eid is not None:
            flagged.append(family)
    return flagged


def catch_up_approved_proposals() -> dict[str, Any]:
    """Start work for approvals that landed while the sleeve was still uncoded."""
    from firm import memory

    started: list[int] = []
    seen_ids: set[int] = set()
    rows = list(memory.decided_strategy_proposals(limit=20))
    rows.extend(memory.approved_code_mandates(limit=20))
    for proposal in rows:
        pid = int(proposal.get("id") or 0)
        if pid and pid in seen_ids:
            continue
        if pid:
            seen_ids.add(pid)
        if proposal.get("status") != "approved":
            continue
        family = infer_family(proposal.get("payload") or {}, proposal.get("title") or "")
        ensure_family_ready_to_test(family)
        coded = set(list_strategies())
        if family == "rsi_trend":
            continue
        if family not in coded:
            # Operator already approved. Hand the brief to Cursor; do not wait
            # for a second click. Walk-forward starts once the sleeve is registered.
            on_operator_approved(proposal)
            continue
        if _active_job_for(family):
            continue
        existing_done = any(
            j.get("family") == family
            and j.get("status") in {"done", "running", "queued", "failed"}
            for j in _load()
        )
        if existing_done:
            continue
        payload = proposal.get("payload") if isinstance(proposal.get("payload"), dict) else {}
        from firm.research_catalog import auto_advance_grid_spent

        clock = str(payload.get("clock") or CLOCK_BY_FAMILY.get(family) or "4h/4h")
        side = str(payload.get("side") or "BOTH")
        if auto_advance_grid_spent(
            {"family": family, "clock": clock, "side": side},
            jobs=_load(),
        ) and not payload.get("force_retest"):
            continue
        result = on_operator_approved(proposal)
        if result.get("job_id"):
            started.append(int(result["job_id"]))
    return {"started": started}


def _already_approved_code_family(family: str) -> bool:
    from firm import memory

    for proposal in memory.approved_code_mandates(limit=20):
        found = infer_family(proposal.get("payload") or {}, proposal.get("title") or "")
        if found == family:
            return True
    return False


def file_novel_coding_inbox() -> dict[str, Any]:
    """Put every ready novel family in Inbox with the full Cursor brief.

    One pending 'Next: code …' used to block every other family. Each novel
    gets its own proposal. Approve hands that brief to Cursor.
    """
    from firm import memory
    from firm.memory_models import ProposalKind
    from firm.sleeve_factory import CODING_REQUESTS_DIR, ready_novel_specs, write_coding_request

    filed: list[dict[str, Any]] = []
    skipped: list[str] = []
    for spec in ready_novel_specs():
        path = write_coding_request(spec)
        md_path = CODING_REQUESTS_DIR / f"{spec.name}.md"
        brief = md_path.read_text(encoding="utf-8") if md_path.exists() else spec.summary
        if _already_pending_next("code_family", spec.name) or _already_approved_code_family(
            spec.name
        ):
            skipped.append(spec.name)
            continue
        pid = memory.record_proposal(
            agent="sleeve_engineer",
            kind=ProposalKind.OPERATIONAL,
            title=f"Code {spec.name}: {spec.summary}"[:200],
            payload={
                "action": "code_family",
                "family": spec.name,
                "name": spec.name,
                "clock": spec.clock,
                "side": spec.side,
                "novel": True,
                "brief": brief,
                "brief_path": f"research/coding_requests/{spec.name}.md",
                "instruction": (
                    "Approve to hand this brief to Cursor. Sleeve Engineer "
                    "will not write core/strategy Python."
                ),
            },
            rationale=brief,
            confidence=0.9,
            ttl=timedelta(days=21),
        )
        filed.append({"family": spec.name, "proposal_id": pid, "brief_path": str(path)})
    return {
        "filed": filed,
        "skipped": skipped,
        "ready": [s.name for s in ready_novel_specs()],
    }


def ensure_next_gate() -> dict[str, Any]:
    """Backstop: if events dropped a catalog-review or Tier B/C gate, file it.

    Tier A starts from continuity.fill_walk_forward_slots, not Inbox.
    """
    jobs = refresh_job_liveness()
    if any(j.get("status") in {"running", "queued"} for j in jobs):
        return {"filed": False, "reason": "busy"}
    if open_code_mandates():
        return {"filed": False, "reason": "mandate_open"}
    from config.pipeline import pipeline_config
    from firm import memory
    from firm.memory_models import ProposalKind
    from firm.research_catalog import remaining_hypotheses

    if pipeline_config().auto_advance and remaining_hypotheses(jobs):
        return {"filed": False, "reason": "continuity_owns_tier_a"}
    for proposal in memory.pending_proposals(limit=100):
        payload = proposal.get("payload") if isinstance(proposal.get("payload"), dict) else {}
        if proposal.get("kind") == "strategy" or payload.get("action") in {
            "code_family",
            "walk_forward",
            "catalog_review",
        }:
            return {"filed": False, "reason": "inbox_has_gate"}
    coded = set(list_strategies())
    done = [j for j in jobs if j.get("status") == "done" and j.get("family") in coded]
    if not done:
        return {"filed": False, "reason": "no_done_job"}
    job = done[-1]
    nxt = _next_step_spec(job)
    if not nxt:
        if any(int(j.get("pairs_approved") or 0) > 0 for j in jobs):
            return {"filed": False, "reason": "approvals_exist_catalog_drained"}
        nxt = _catalog_review_spec(job)
    family = str(nxt["family"])
    if _already_pending_next(str(nxt["action"]), family) or (
        nxt["action"] == "code_family" and _already_approved_code_family(family)
    ):
        return {"filed": False, "reason": "already_gated", "family": family}
    if nxt["action"] == "catalog_review" and _already_decided_catalog_review():
        return {"filed": False, "reason": "catalog_review_already_decided"}
    kind = ProposalKind.STRATEGY if nxt["kind"] == "strategy" else ProposalKind.OPERATIONAL
    memory.record_proposal(
        agent="research_pipeline",
        kind=kind,
        title=nxt["title"],
        payload={
            "name": family,
            "family": family,
            "action": nxt["action"],
            "clock": nxt.get("clock") or "",
            "operator_next": True,
            "from_job_id": job.get("id"),
        },
        rationale=nxt["rationale"],
        confidence=0.9,
        ttl=timedelta(days=14),
    )
    logger.info("GM filed next gate: %s %s", nxt["action"], family)
    return {"filed": True, "family": family, "action": nxt["action"]}


def advance_pipeline() -> dict[str, Any]:
    """Keep research moving. Called every paper cycle and on API startup.

    This is the GM function Desk Head is accountable for. It does not need an
    LLM: refresh jobs, post verdicts, start walk-forwards for approved coded
    families, and file the next Inbox gate if the last test finished with
    nothing waiting. Quant is woken separately when the pipeline is idle.
    """
    refresh_job_liveness()
    posted = notify_finished_jobs()
    started = catch_up_approved_proposals()
    impl_flags: list[str] = []
    try:
        impl_flags = flag_implementation_gap()
    except Exception:
        logger.exception("Implementation-gap flag failed")
    novel_inbox: dict[str, Any] = {}
    try:
        novel_inbox = file_novel_coding_inbox()
    except Exception:
        logger.exception("Novel coding inbox file failed")
    gate = ensure_next_gate()
    failure_alerts: list[str] = []
    try:
        from firm.accountability import backfill_failure_alerts

        failure_alerts = backfill_failure_alerts()
    except Exception:
        logger.exception("Failure-alert backfill failed")
    certified: list[int] = []
    try:
        from firm.integrity import certify_and_store_job

        for job in _load():
            if job.get("status") not in {"done", "failed"}:
                continue
            if isinstance(job.get("integrity"), dict) and job["integrity"].get("checks"):
                continue
            certify_and_store_job(job)
            certified.append(int(job.get("id") or 0))
    except Exception:
        logger.exception("Integrity backfill failed")
    sweep: dict[str, Any] = {}
    try:
        from firm.continuity import backstop_sweep

        sweep = backstop_sweep(source="advance_pipeline")
    except Exception:
        logger.exception("Continuity backstop failed")
    return {
        "posted_inbox": posted,
        "started_jobs": started.get("started") or [],
        "certified_jobs": certified,
        "next_gate": gate,
        "novel_inbox": novel_inbox,
        "quant_due": quant_should_run_now(),
        "open_mandates": [m.get("family") for m in open_code_mandates()],
        "failure_alerts": failure_alerts,
        "implementation_flags": impl_flags,
        "continuity": sweep,
    }


def quant_should_run_now() -> bool:
    """True when the catalog has idle work and Quant should not wait a week.

    A Gemini timeout is not a completed weekly slot. Accountability owns the
    retry window so a failed call cannot freeze research for 12 hours.
    """
    from firm.accountability import quant_should_run_now as _quant_due

    return _quant_due()


def _age_hours(iso: str) -> float | None:
    if not iso:
        return None
    try:
        stamp = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            stamp = stamp.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - stamp).total_seconds() / 3600.0
    except ValueError:
        return None


def _age_seconds(iso: str | None) -> float | None:
    hours = _age_hours(str(iso or ""))
    return None if hours is None else hours * 3600.0


def _quant_progress(run: dict[str, Any] | None) -> dict[str, Any]:
    """Elapsed vs typical Gemini-strong call so a hang is visible."""
    if not run:
        return {"progress": None, "progress_label": "", "stalled": False}
    status = str(run.get("status") or "")
    typical = 90.0
    latency = run.get("latency_ms")
    if isinstance(latency, (int, float)) and latency > 0 and status != "running":
        typical = max(45.0, float(latency) / 1000.0)
    elapsed = _age_seconds(run.get("started_at"))
    if status == "running":
        seconds = elapsed or 0.0
        pct = min(99, int(100 * seconds / typical))
        stalled = seconds > typical * 2.5
        return {
            "progress": pct,
            "progress_label": (
                f"STALLED at {int(seconds)}s (typical ~{int(typical)}s)"
                if stalled
                else f"{int(seconds)}s / ~{int(typical)}s typical"
            ),
            "stalled": stalled,
        }
    if status == "failed":
        return {"progress": 100, "progress_label": "Failed — retry is armed", "stalled": True}
    if status == "success":
        return {"progress": 100, "progress_label": "Posted", "stalled": False}
    return {"progress": None, "progress_label": "", "stalled": False}


def walkforward_progress(job: dict[str, Any] | None) -> dict[str, Any]:
    """Pair-verdict progress from the validator log."""
    if not job:
        return {"progress": None, "progress_label": "", "stalled": False}
    symbols = list(job.get("symbols") or [])
    side = str(job.get("side") or "BOTH").upper()
    sides = 2 if side in {"", "BOTH"} else 1
    expected = max(len(symbols) * sides, 1)
    path = Path(str(job.get("log_path") or ""))
    verdicts = 0
    last = ""
    if path.exists():
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            lines = []
        for line in lines:
            if "VERDICT:" in line:
                verdicts += 1
                last = line.split("VERDICT:", 1)[-1].strip()[:80]
            elif "Fetching" in line or "strategy=" in line:
                last = (line.split("|")[-1] if "|" in line else line).strip()[:80]
    status = str(job.get("status") or "")
    if status == "done":
        return {
            "progress": 100,
            "progress_label": f"{verdicts}/{expected} pairs finished",
            "stalled": False,
        }
    if status in {"running", "queued"}:
        pct = min(99, int(100 * verdicts / expected))
        elapsed = _age_seconds(job.get("started_at") or job.get("created_at")) or 0.0
        hung_after = 90 * 60
        try:
            from firm.continuity import hung_threshold_seconds

            hung_after = hung_threshold_seconds(_load())
        except Exception:
            pass
        stalled = (verdicts == 0 and elapsed > 20 * 60) or elapsed > hung_after
        label = f"{verdicts}/{expected} pair verdicts"
        if last:
            label = f"{label} · {last}"
        if stalled:
            label = "STALLED · " + label
        return {"progress": pct, "progress_label": label, "stalled": stalled}
    return {"progress": None, "progress_label": str(job.get("detail") or "")[:80], "stalled": False}


def _mark_current_stage(stages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Exactly one live box. A running walk-forward beats a stale Quant fail."""
    by_id = {s.get("id"): s for s in stages}
    test = by_id.get("test") or {}
    propose = by_id.get("propose") or {}
    current_id = None
    if test.get("state") == "active":
        current_id = "test"
    elif propose.get("state") == "active":
        current_id = "propose"
    else:
        order = ("test", "propose", "approve", "verdict", "trade")
        for sid in order:
            stage = by_id.get(sid)
            if stage and stage.get("state") in {"active", "bad"}:
                current_id = sid
                break
    for stage in stages:
        stage["current"] = stage.get("id") == current_id
    return stages


def pipeline_snapshot() -> dict[str, Any]:
    """Operator-facing workflow: catalog → propose → approve → test → verdict → trade."""
    from firm import memory
    from config.universe import get_universe

    jobs = refresh_job_liveness()
    inbox = memory.pending_proposals(limit=100)
    strategy_inbox = [p for p in inbox if p.get("kind") == "strategy"]
    board = memory.research_board(limit=20)
    get_universe.cache_clear()
    universe = get_universe()
    latest = _headline_job(jobs)
    if latest:
        _backfill_clock(latest)
    test_state = "idle"
    test_detail = "No walk-forward is queued. Approve a coded hypothesis in Inbox to start one."
    if latest:
        test_state = str(latest.get("status") or "idle")
        test_detail = str(latest.get("detail") or "")
        family = latest.get("family") or ""
        symbols = ", ".join(latest.get("symbols") or [])
        if family:
            test_detail = f"{family} on {symbols or 'majors'}: {test_detail}"
        if _is_code_crash(latest) and test_state == "failed":
            live = [j for j in jobs if j.get("status") in {"running", "queued", "standby"}]
            if live:
                latest = live[-1]
                _backfill_clock(latest)
                test_state = str(latest.get("status") or "idle")
                test_detail = (
                    f"{latest.get('family')} on "
                    f"{', '.join(latest.get('symbols') or [])}: "
                    f"{latest.get('detail') or ''}"
                )
            else:
                test_state = "done"
                test_detail = (
                    "Last validator crash is historical. The next family auto-starts "
                    "from standby. Paper still scans approved pairs."
                )

    quant = next(
        (r for r in memory.recent_runs(agent="quant_researcher", limit=1)),
        None,
    )
    propose_state = "wait"
    propose_detail = "Quant posts when the pipeline is idle — not on a weekly wait."
    quant_bar = {"progress": None, "progress_label": "", "stalled": False}
    if quant:
        qstatus = str(quant.get("status") or "")
        if qstatus == "running":
            propose_state = "active"
        elif qstatus == "failed":
            live_wf = any(j.get("status") in {"running", "queued"} for j in jobs)
            if live_wf or universe.approved_pairs:
                propose_state = "done"
                propose_detail = (
                    "Last Gemini call failed; retry is armed. "
                    "Walk-forward and paper are not waiting on it."
                )
            else:
                propose_state = "bad"
        else:
            propose_state = "done"
        propose_detail = (quant.get("reasoning") or quant.get("task") or "")[:220]
        if propose_detail.lower().startswith("quant researcher weekly"):
            propose_detail = "Propose the next catalog family (idle pipeline)."
        quant_bar = _quant_progress(quant)

    coded = set(list_strategies())
    families = [
        {
            "id": f["id"],
            "name": f["name"],
            "status": f["status"],
            "coded": f["id"] in coded,
        }
        for f in RESEARCH_FAMILIES
    ]
    mandates = open_code_mandates()
    implement_bar: dict[str, Any] | None = None
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
    if mandates and test_state not in {"running", "queued"}:
        mandate = mandates[0]
        elapsed = _age_seconds(mandate.get("created_at") or mandate.get("decided_at"))
        age_min = int((elapsed or 0) / 60)
        age_label = f"{age_min}m ago" if elapsed else "just now"
        if mandate.get("phase") == "start_test":
            test_state = "queued"
            test_detail = (
                f"{mandate.get('family')}: you already approved coding {age_label}. "
                "Walk-forward is starting now."
            )
            implement_bar = {
                "progress": 0,
                "progress_label": "Starting walk-forward — 0 pair verdicts yet",
                "stalled": False,
            }
        else:
            # Do not paint Walk-forward as 99% complete. Nothing is running.
            test_state = "blocked"
            test_detail = (
                f"{mandate.get('family')} is approved but not in the registry. "
                f"Waited {age_label}. No validator is running. Elapsed time is "
                "not completion."
            )
            implement_bar = {
                "progress": 0,
                "progress_label": (
                    f"0% — no validator. {mandate.get('family')} is not coded. "
                    f"{age_min}m waiting is stall time, not progress."
                ),
                "stalled": True,
            }

    latest_name = (latest or {}).get("family") or "none"
    n_coded = sum(1 for row in families if row["coded"])
    if mandates:
        approve_detail = (
            f"You already approved {mandates[0].get('family')}. "
            "Inbox is empty because that gate is decided."
        )
        approve_state = "done"
    elif strategy_inbox:
        approve_detail = f"{len(strategy_inbox)} strategy proposal(s) waiting in Inbox."
        approve_state = "wait"
    elif code_inbox:
        approve_detail = (
            f"{len(code_inbox)} novel brief(s) on file. Cursor codes them; "
            "Inbox is not the research gate."
        )
        approve_state = "done"
    elif review_inbox:
        approve_detail = (
            "Catalog review waiting in Inbox: every coded family has a verdict."
        )
        approve_state = "wait"
    else:
        approve_detail = "Tier A auto-starts from standby. Inbox is only for Tier B/C."
        approve_state = "done"

    if test_state in {"running", "queued"}:
        approve_state = "done"
        approve_detail = "Tier A auto-starts from standby. Inbox is only for Tier B/C."

    if latest and str(latest.get("status") or "") in {"running", "queued"}:
        test_bar = walkforward_progress(latest)
    elif implement_bar:
        test_bar = implement_bar
    else:
        test_bar = {"progress": None, "progress_label": "", "stalled": False}

    stages = [
        {
            "id": "catalog",
            "label": "Catalog",
            "state": "done",
            "detail": f"{n_coded} coded families. Latest test: {latest_name}.",
            "progress": 100,
            "progress_label": "",
            "stalled": False,
        },
        {
            "id": "propose",
            "label": "Quant proposes",
            "state": propose_state,
            "detail": propose_detail,
            **quant_bar,
        },
        {
            "id": "approve",
            "label": "Human gate",
            "state": "active" if approve_state == "wait" else approve_state,
            "detail": approve_detail,
            "progress": 100 if approve_state == "done" else (0 if approve_state == "wait" else None),
            "progress_label": "Waiting on Inbox" if approve_state == "wait" else "",
            "stalled": False,
        },
        {
            "id": "test",
            "label": "Walk-forward",
            "state": {
                "running": "active",
                "queued": "active",
                "done": "done",
                "failed": "bad",
                "blocked": "bad",
            }.get(test_state, "wait"),
            "detail": test_detail,
            **test_bar,
        },
        {
            "id": "verdict",
            "label": "Verdict",
            "state": "done" if universe.approved_pairs else "wait",
            "detail": (
                f"{len(universe.approved_pairs)} pair(s) research-approved (live gate). "
                f"{len(universe.paper_override_records)} on paper by operator veto."
                if universe.approved_pairs or universe.paper_override_records
                else (
                    f"{latest.get('family')} {latest.get('clock') or ''} finished with "
                    f"{latest.get('pairs_approved', 0)} pairs approved. Live stays locked."
                    if latest and latest.get("status") == "done"
                    else "No pair has passed walk-forward. Live stays locked; paper may still scan."
                )
            ),
            "progress": 100 if universe.approved_pairs else None,
            "progress_label": "",
            "stalled": False,
        },
        {
            "id": "trade",
            "label": "Paper / live",
            "state": "wait",
            "detail": (
                "Paper scans research-approved pairs plus operator paper vetoes. "
                "Live needs an approved pair and the go-live gates."
            ),
            "progress": None,
            "progress_label": "",
            "stalled": False,
        },
    ]
    stages = _mark_current_stage(stages)

    return {
        "stages": stages,
        "jobs": [
            j
            for j in jobs
            if j.get("family") and j.get("family") != "unknown"
        ][-8:],
        "families": families,
        "hypotheses": [
            {
                "id": r.get("id"),
                "status": r.get("status"),
                "hypothesis": r.get("hypothesis"),
            }
            for r in board[:6]
        ],
        "note": (
            "Tier A walk-forwards start from standby when a slot frees — no Inbox. "
            "Paper-to-live is still a hard human gate. 0/6 is a real reject against "
            "PF 1.15 / fold stability / expectancy CI, not an unreachable bar."
        ),
        "now": _now_banner(
            latest,
            test_state,
            test_detail,
            strategy_inbox,
            propose_state,
            mandates,
            code_inbox,
            quant_bar,
            review_inbox,
        ),
        "continuity": _continuity_snapshot(jobs),
    }


def _continuity_snapshot(jobs: list[dict[str, Any]]) -> dict[str, Any]:
    try:
        from firm.continuity import throughput_metrics
        from firm.pipeline_state import load_state, open_tickets

        metrics = throughput_metrics(jobs)
        state = load_state()
        return {
            **metrics,
            "current_family": state.get("current_family"),
            "current_stage": state.get("current_stage"),
            "last_updated_by": state.get("last_updated_by"),
            "tickets": open_tickets(),
        }
    except Exception:
        logger.exception("Continuity snapshot failed")
        return {"tickets": [], "dropped_event_count": 0}


def _is_code_crash(job: dict[str, Any]) -> bool:
    """True when the validator died on a bug, not a measured 0/6 reject."""
    if str(job.get("status") or "") != "failed":
        return False
    detail = str(job.get("detail") or "").lower()
    markers = (
        "nameerror",
        "is not defined",
        "_novel_kit",
        "spawn failed",
        "importerror",
        "modulenotfound",
    )
    return any(marker in detail for marker in markers)


def _headline_job(jobs: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Prefer a live coded test. Yesterday's crash is not the desk.

    A NameError from last night must not outrank a running validator or an
    approved pair. Failed is only the headline when it is the latest *measured*
    finish and nothing is in motion.
    """
    coded = set(list_strategies())
    useful = [j for j in jobs if j.get("family") in coded]
    for status in ("running", "queued", "standby"):
        hits = [j for j in useful if j.get("status") == status]
        if hits:
            return hits[-1]
    approved = [
        j
        for j in useful
        if j.get("status") == "done" and int(j.get("pairs_approved") or 0) > 0
    ]
    if approved:
        return max(approved, key=lambda j: int(j.get("id") or 0))
    measured = [j for j in useful if j.get("status") in {"done", "failed"} and not _is_code_crash(j)]
    measured.sort(key=lambda j: (str(j.get("finished_at") or ""), int(j.get("id") or 0)))
    if measured:
        return measured[-1]
    finished = [j for j in useful if j.get("status") in {"done", "failed"}]
    finished.sort(key=lambda j: (str(j.get("finished_at") or ""), int(j.get("id") or 0)))
    if finished:
        return finished[-1]
    return useful[-1] if useful else None


def _now_banner(
    latest: dict[str, Any] | None,
    test_state: str,
    test_detail: str,
    strategy_inbox: list[dict[str, Any]],
    propose_state: str,
    mandates: list[dict[str, Any]] | None = None,
    code_inbox: list[dict[str, Any]] | None = None,
    quant_bar: dict[str, Any] | None = None,
    review_inbox: list[dict[str, Any]] | None = None,
) -> dict[str, str]:
    """One sentence for the desk: what is happening right now."""
    live_job = (latest or {}).get("status") in {"running", "queued"}
    if live_job:
        family = (latest or {}).get("family") or "strategy"
        return {
            "label": f"Testing {family} — walk-forward is {(latest or {}).get('status')}",
            "state": "active",
            "detail": test_detail,
        }
    if propose_state == "active":
        extra = (quant_bar or {}).get("progress_label") or ""
        return {
            "label": "Quant is writing the next catalog family",
            "state": "active",
            "detail": extra or "When it files, the proposal lands in Inbox for you.",
        }
    if test_state == "failed":
        try:
            from config.universe import get_universe

            n_approved = len(get_universe().approved_pairs)
        except Exception:
            n_approved = 0
        if n_approved or _is_code_crash(latest or {}):
            label = (
                f"{n_approved} pair(s) approved — paper is the live clock"
                if n_approved
                else "Walk-forward crash was recorded; the next family auto-starts"
            )
            return {
                "label": label,
                "state": "active" if n_approved else "wait",
                "detail": (
                    "A code crash is historical. Paper scans approved pairs. "
                    "Live still needs you. The next ranked family starts from standby."
                    if _is_code_crash(latest or {})
                    else (
                        "Paper scans the approved pairs every 15m. Live still needs you. "
                        f"Last crash ({(latest or {}).get('family')}) is historical."
                    )
                ),
            }
        return {
            "label": "Walk-forward failed",
            "state": "bad",
            "detail": test_detail,
        }
    if mandates:
        mandate = mandates[0]
        family = str(mandate.get("family") or "strategy")
        if mandate.get("phase") == "implement":
            return {
                "label": f"BLOCKED: {family} approved but not coded — no walk-forward",
                "state": "bad",
                "detail": (
                    "No employee writes strategy files. Catch-up starts the "
                    "validator only after the sleeve is in the registry. "
                    "Elapsed wait is not 99% complete."
                ),
            }
        return {
            "label": f"Starting walk-forward for {family} — you already approved",
            "state": "active",
            "detail": "Catch-up will spawn the validator. You do not need to re-approve.",
        }
    if test_state == "blocked":
        return {
            "label": "Approved, but this family is not coded yet",
            "state": "wait",
            "detail": test_detail,
        }
    if strategy_inbox:
        return {
            "label": f"{len(strategy_inbox)} strategy proposal(s) waiting in Inbox",
            "state": "wait",
            "detail": "Approve to queue walk-forward. Reject to drop it.",
        }
    if review_inbox:
        return {
            "label": "Catalog exhausted — the next decision is in Inbox",
            "state": "wait",
            "detail": (
                "Every coded family has a walk-forward verdict. funding_fade "
                "still needs a feed. Approve/reject the catalog review."
            ),
        }
    if test_state == "done":
        family = (latest or {}).get("family") or "strategy"
        pairs = (latest or {}).get("pairs_approved")
        try:
            from config.universe import get_universe

            n_approved = len(get_universe().approved_pairs)
        except Exception:
            n_approved = 0
        if n_approved:
            return {
                "label": f"{n_approved} pair(s) approved — paper is today's clock",
                "state": "active",
                "detail": (
                    "No walk-forward is running. Paper scans ATR BTC/ETH shorts 4h "
                    "and doji SOL short 1h every 15m. Live still needs you. "
                    "Do not launch utc_midnight / engulfing clock clones."
                ),
            }
        if pairs == 0:
            return {
                "label": (
                    f"{family} finished — rejected. Inbox is empty: that is a "
                    "GM miss, not a finished pipeline."
                ),
                "state": "bad",
                "detail": test_detail,
            }
        return {
            "label": "Walk-forward finished — open Strategies for the verdict",
            "state": "done",
            "detail": test_detail,
        }
    return {
        "label": "Waiting — next ranked hypothesis should auto-start from standby",
        "state": "wait",
        "detail": "Catalog → standby → walk-forward. Inbox is only for Tier B/C.",
    }
