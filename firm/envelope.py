"""Three-tier research envelope: what may auto-advance vs what needs a human.

Tier A: auto-advance, no Inbox.
Tier B: Inbox, default-approve after PIPELINE_TIER_B_HOURS unless vetoed.
Tier C: hard human gate — new symbol/venue/feed, any risk-param change,
        any paper-to-live. Never times out into approval.

Criteria 5 (param count) and 6 (standard walk-forward windows) are the
overfitting guards. Do not loosen those two first.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from config.pipeline import (
    APPROVED_RESEARCH_SYMBOLS,
    STANDARD_TEST_DAYS,
    STANDARD_TRAIN_DAYS,
    SUPPORTED_TIMEFRAMES,
    pipeline_config,
)
from firm.research_catalog import FAMILIES_NEEDING_FEED, is_param_variant, ranked_hypotheses


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


def _clock_supported(clock: str) -> bool:
    parts = [p.strip() for p in str(clock or "").split("/") if p.strip()]
    if len(parts) != 2:
        return False
    return all(p in SUPPORTED_TIMEFRAMES for p in parts)


def _last_reject_at(family: str, jobs: list[dict[str, Any]]) -> datetime | None:
    latest: datetime | None = None
    for job in jobs:
        if str(job.get("family") or "") != family:
            continue
        if job.get("status") not in {"done", "failed"}:
            continue
        if int(job.get("pairs_approved") or 0) > 0:
            continue
        stamp = _parse_iso(str(job.get("finished_at") or job.get("created_at") or ""))
        if stamp and (latest is None or stamp > latest):
            latest = stamp
    return latest


def _auditor_flag(family: str, *, clock: str = "") -> bool:
    """True when this family (and clock, if given) has a failed certificate.

    A clock mismatch on one setup must not freeze every other clock/side of
    the same sleeve — that is how a 1h/4h log warning parked 1h shorts.
    """
    try:
        from firm.integrity import integrity_snapshot

        pack = integrity_snapshot()
    except Exception:
        return False
    for row in pack.get("jobs") or []:
        if str(row.get("family") or "") != family:
            continue
        if row.get("ok") is not False:
            continue
        row_clock = str(row.get("clock") or "")
        if clock and row_clock and row_clock != clock:
            continue
        return True
    return False


def classify_hypothesis(
    hypo: dict[str, Any],
    *,
    jobs: list[dict[str, Any]] | None = None,
    train_days: int = STANDARD_TRAIN_DAYS,
    test_days: int = STANDARD_TEST_DAYS,
) -> dict[str, Any]:
    """Return tier A/B/C plus the criteria checklist. Never grants live."""
    cfg = pipeline_config()
    jobs = jobs or []
    family = str(hypo.get("family") or "")
    clock = str(hypo.get("clock") or "")
    symbols = list(hypo.get("symbols") or APPROVED_RESEARCH_SYMBOLS)
    hid = str(hypo.get("id") or f"{family}@{clock}")
    raw_rank = hypo.get("rank")
    rank = int(raw_rank) if raw_rank is not None and raw_rank != "" else 99
    free_params = int(hypo.get("free_params") or 99)
    disposition = str(hypo.get("disposition") or "")
    justification = str(hypo.get("justification") or "").strip()
    param_change = hypo.get("param_change") or {}

    reasons: list[str] = []
    checks: dict[str, bool] = {}

    checks["top5"] = rank <= 5
    if not checks["top5"]:
        reasons.append(f"rank {rank} is outside top 5")

    allowed = set(APPROVED_RESEARCH_SYMBOLS)
    checks["existing_universe"] = bool(symbols) and all(s in allowed for s in symbols)
    if not checks["existing_universe"]:
        reasons.append("uses a symbol outside the current 12 pairs")

    needs_feed = bool(hypo.get("needs_feed")) or family in FAMILIES_NEEDING_FEED
    checks["existing_feed"] = not needs_feed
    if needs_feed:
        reasons.append("needs a new data feed")

    flagged = _auditor_flag(family, clock=clock)
    # A frozen-grid retest is not the job that failed integrity. Blocking it
    # behind Inbox overnight stalls paper research, not live risk.
    if is_param_variant(hypo):
        flagged = False
    checks["no_auditor_flag"] = not flagged
    if flagged:
        reasons.append("open Performance Auditor integrity flag")

    checks["param_count"] = free_params <= cfg.max_free_params
    if not checks["param_count"]:
        reasons.append(f"{free_params} free parameters > {cfg.max_free_params}")

    checks["standard_windows"] = (
        train_days == STANDARD_TRAIN_DAYS and test_days == STANDARD_TEST_DAYS
    )
    if not checks["standard_windows"]:
        reasons.append("custom walk-forward windows")

    checks["supported_timeframe"] = _clock_supported(clock)
    if not checks["supported_timeframe"]:
        reasons.append(f"clock {clock} is not a supported runner timeframe")

    rejected_at = _last_reject_at(family, jobs)
    cooldown = timedelta(days=cfg.reject_cooldown_days)
    recently_rejected = bool(
        rejected_at and datetime.now(timezone.utc) - rejected_at < cooldown
    )
    changed = bool(param_change) or bool(justification)
    reparam_ok = (
        disposition in {"re-parameterise", "retest_under_different_regime"}
        and changed
        and bool(justification)
    )
    checks["reject_cooldown"] = (not recently_rejected) or reparam_ok
    if recently_rejected and not reparam_ok:
        reasons.append(
            f"{family} rejected within {cfg.reject_cooldown_days}d without "
            "re-parameterise/regime disposition + written justification"
        )

    # Tier C red lines — never auto, never timeout-approve.
    tier_c = False
    if needs_feed:
        tier_c = True
        reasons.append("Tier C: new feed")
    if hypo.get("new_venue") or hypo.get("paper_to_live") or hypo.get("risk_param_change"):
        tier_c = True
        reasons.append("Tier C: venue, live, or risk-parameter change")
    if not checks["existing_universe"]:
        tier_c = True

    if tier_c:
        tier = "C"
    elif all(checks.values()):
        tier = "A"
    else:
        tier = "B"

    return {
        "hypothesis_id": hid,
        "family": family,
        "clock": clock,
        "tier": tier,
        "checks": checks,
        "reasons": reasons,
        "rank": rank,
        "auto": tier == "A",
    }


def classify_family_clock(
    family: str,
    clock: str,
    *,
    side: str = "BOTH",
    jobs: list[dict[str, Any]] | None = None,
    hypothesis_id: str = "",
) -> dict[str, Any]:
    """Match a family+clock to a catalog hypothesis, or build a conservative row.

    Prefer `hypothesis_id` so a frozen-grid retest is not classified as the
    already-rejected base clock of the same sleeve.
    """
    hid = str(hypothesis_id or "")
    if hid:
        for row in ranked_hypotheses():
            if str(row.get("id") or "") == hid:
                return classify_hypothesis(row, jobs=jobs)
    for row in ranked_hypotheses():
        if str(row.get("family")) == family and str(row.get("clock")) == clock:
            if str(row.get("side") or "BOTH").upper() == (side or "BOTH").upper():
                return classify_hypothesis(row, jobs=jobs)
    return classify_hypothesis(
        {
            "id": f"{family}@{clock}",
            "family": family,
            "clock": clock,
            "side": side,
            "rank": 99,
            "free_params": 99,
            "disposition": "",
            "justification": "",
            "param_change": {},
        },
        jobs=jobs,
    )
