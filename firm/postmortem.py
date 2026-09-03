"""Rejection post-mortems: why a family failed, and how the catalog must change.

A 0/6 result that does not mutate ranking is how Quant keeps proposing from a
stale order. Disposition is retire | re-parameterise | retest_under_different_regime.

0 pairs after costs retires this hypothesis. SHORT is not a follow-up unless
the BOTH run showed shorts as a near-miss (PF >= 1.15 or positive expectancy).
Re-queueing the same family@clock@params without a written justification is
blocked by the envelope cooldown rule.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config.settings import PROJECT_ROOT
from firm.research_catalog import hypothesis_key, ranked_hypotheses

POSTMORTEM_DIR = PROJECT_ROOT / "research" / "artifacts"
RANKING_PATH = PROJECT_ROOT / "data" / "catalog_ranking.json"

_PF_RE = re.compile(r"(?:PF|profit factor)\s+(\d+(?:\.\d+)?)", re.IGNORECASE)
_EXP_POS_RE = re.compile(r"Exp\s+\+", re.IGNORECASE)


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_ranking() -> dict[str, Any]:
    if not RANKING_PATH.exists():
        return {
            "ranks": {},
            "retired": [],
            "retired_families": [],
            "justifications": {},
            "dispositions": {},
        }
    try:
        raw = json.loads(RANKING_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {
            "ranks": {},
            "retired": [],
            "retired_families": [],
            "justifications": {},
            "dispositions": {},
        }
    if not isinstance(raw, dict):
        return {
            "ranks": {},
            "retired": [],
            "retired_families": [],
            "justifications": {},
            "dispositions": {},
        }
    raw.setdefault("ranks", {})
    raw.setdefault("retired", [])
    raw.setdefault("retired_families", [])
    raw.setdefault("justifications", {})
    raw.setdefault("dispositions", {})
    return raw


def _save_ranking(data: dict[str, Any]) -> None:
    RANKING_PATH.parent.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = utcnow_iso()
    RANKING_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def shorts_were_near_miss(pair_blurbs: str) -> bool:
    """True when a SHORT slice cleared PF 1.15 or printed positive expectancy."""
    blob = pair_blurbs or ""
    chunks = re.split(r"[;\n]", blob)
    hits = [chunk for chunk in chunks if "SHORT" in chunk.upper()]
    if not hits:
        hits = [blob] if "SHORT" in blob.upper() else []
    for chunk in hits:
        pf_match = _PF_RE.search(chunk)
        if pf_match and float(pf_match.group(1)) >= 1.15:
            return True
        if _EXP_POS_RE.search(chunk):
            return True
    return False


def infer_disposition(job: dict[str, Any], pair_blurbs: str) -> str:
    """Cheap deterministic disposition from the verdict, not an LLM guess."""
    pairs = int(job.get("pairs_approved") or 0)
    side = str(job.get("side") or "BOTH").upper()
    if pairs == 0:
        if side == "BOTH" and shorts_were_near_miss(pair_blurbs):
            return "retest_under_different_regime"
        return "retire"
    blob = f"{job.get('detail') or ''} {pair_blurbs}".lower()
    if "overtrad" in blob or "1173" in blob or "oos trades" in blob:
        return "retest_under_different_regime"
    if "unstable" in blob or "min_adx" in blob or "cv=" in blob:
        return "re-parameterise"
    if "profit factor" in blob or "expectancy" in blob:
        return "re-parameterise"
    clock = str(job.get("clock") or "")
    if clock.startswith("15m"):
        return "retest_under_different_regime"
    return "re-parameterise"


def write_postmortem(job: dict[str, Any], *, pair_blurbs: str = "") -> dict[str, Any]:
    """Record why this job failed and retire or demote the hypothesis."""
    family = str(job.get("family") or "")
    clock = str(job.get("clock") or "")
    side = str(job.get("side") or "BOTH")
    hid = str(job.get("hypothesis_id") or hypothesis_key(family, clock, side))
    pairs = int(job.get("pairs_approved") or 0)
    disposition = infer_disposition(job, pair_blurbs)
    keep_short = (
        disposition == "retest_under_different_regime"
        and (side or "BOTH").upper() == "BOTH"
        and shorts_were_near_miss(pair_blurbs)
        # Advisor: no BNB/SHORT clone of monday_range_sweep_reversal.
        and family != "monday_range_sweep_reversal"
    )
    report = {
        "job_id": job.get("id"),
        "family": family,
        "clock": clock,
        "side": side,
        "hypothesis_id": hid,
        "pairs_approved": pairs,
        "disposition": disposition,
        "keep_short_followup": keep_short,
        "why": str(job.get("detail") or "")[:1500],
        "pairs": pair_blurbs[:2000],
        "written_at": utcnow_iso(),
        "owner_seat": "performance_auditor",
    }
    POSTMORTEM_DIR.mkdir(parents=True, exist_ok=True)
    path = POSTMORTEM_DIR / f"postmortem_job_{job.get('id')}.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    ranking = _load_ranking()
    ranking["dispositions"][hid] = disposition
    ranking["justifications"][hid] = (
        f"{disposition}: {pairs} pairs approved at {clock}. {report['why'][:400]}"
    )
    retired = set(ranking.get("retired") or [])
    if disposition == "retire":
        retired.add(hid)
        if (side or "BOTH").upper() == "BOTH" and not keep_short:
            retired.add(hypothesis_key(family, clock, "SHORT"))
        ranking["retired"] = sorted(retired)
        _maybe_retire_family(ranking, job, family)
    else:
        current = {
            str(r.get("id")): (
                int(r["rank"]) if r.get("rank") is not None and r.get("rank") != "" else 99
            )
            for r in ranked_hypotheses()
        }
        current[hid] = max(current.values() or [15]) + 1
        ranking["ranks"][hid] = current[hid]
        if keep_short:
            short_hid = hypothesis_key(family, clock, "SHORT")
            ranking["justifications"][short_hid] = (
                "shorts were a near-miss on the BOTH run; keep one SHORT follow-up"
            )
    _save_ranking(ranking)
    report["ranking_path"] = str(RANKING_PATH)
    report["artifact"] = str(path)
    return report


def _maybe_retire_family(ranking: dict[str, Any], job: dict[str, Any], family: str) -> None:
    """If 4h and 1h both failed with zero approvals, stop cloning this family."""
    if not family:
        return
    try:
        from firm.research_catalog import family_has_approval, primary_clocks_failed
        from firm.research_jobs import list_jobs

        jobs = list_jobs()
    except Exception:
        jobs = [job]
    if family_has_approval(jobs, family):
        return
    if not primary_clocks_failed(jobs, family):
        return
    families = set(ranking.get("retired_families") or [])
    families.add(family)
    ranking["retired_families"] = sorted(families)


def postmortem_for_job(job_id: int) -> dict[str, Any] | None:
    path = POSTMORTEM_DIR / f"postmortem_job_{job_id}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
