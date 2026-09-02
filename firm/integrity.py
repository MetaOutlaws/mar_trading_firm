"""
Test and trade integrity: did the firm actually run the setup it claimed?

Walk-forward prints hundreds of OOS trades. That is not verification. This
module checks the job log, the catalog clock, the cost model, and the
approvals file against each other so a 15m run cannot be mistaken for a 4h
one, and paper cannot scan a different sleeve than research is testing.

The Performance Auditor *owns* this pack. The LLM may explain it; it may not
invent a pass.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from config.settings import PROJECT_ROOT
from config.universe import APPROVALS_PATH, parse_approval_key
from research.costs import DEFAULT_COSTS

logger = logging.getLogger(__name__)

LAST_CYCLE_PATH = PROJECT_ROOT / "data" / "last_cycle.json"

_LONG_CLOCK = re.compile(r"LONG:\s+(\d+)\s+symbols on\s+(\S+)\s+candles")
_SHORT_CLOCK = re.compile(r"SHORT:\s+(\d+)\s+symbols on\s+(\S+)\s+candles")
_STRATEGY = re.compile(r"strategy=(\S+)")
_APPROVED_LINE = re.compile(r"Approved:\s+(\d+)\s+of\s+(\d+)")
_SLIPPAGE = re.compile(r"slippage\s+([\d.]+)\s+bps")
_PAIR_BAR = re.compile(
    r"(BTCUSDT|ETHUSDT|SOLUSDT)\s+(LONG|SHORT)\s+(\S+):\s+(\d+)\s+bars"
)


def _check(name: str, ok: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "ok": bool(ok), "detail": detail}


def parse_job_log(log_path: str | Path) -> dict[str, Any]:
    """Pull the setup the validator actually ran from its log."""
    path = Path(log_path)
    out: dict[str, Any] = {
        "exists": path.exists(),
        "family": "",
        "long_tf": "",
        "short_tf": "",
        "long_n": 0,
        "short_n": 0,
        "approved": None,
        "tested": None,
        "slippage_bps": [],
        "pair_bars": [],
    }
    if not path.exists():
        return out
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return out
    if m := _STRATEGY.search(text):
        out["family"] = m.group(1)
    if m := _LONG_CLOCK.search(text):
        out["long_n"] = int(m.group(1))
        out["long_tf"] = m.group(2)
    if m := _SHORT_CLOCK.search(text):
        out["short_n"] = int(m.group(1))
        out["short_tf"] = m.group(2)
    if m := _APPROVED_LINE.search(text):
        out["approved"] = int(m.group(1))
        out["tested"] = int(m.group(2))
    out["slippage_bps"] = [float(x) for x in _SLIPPAGE.findall(text)]
    out["pair_bars"] = [
        {"symbol": a, "side": b, "timeframe": c, "bars": int(d)}
        for a, b, c, d in _PAIR_BAR.findall(text)
    ]
    return out


def _expected_clock(job: dict[str, Any]) -> str:
    from firm.research_jobs import CLOCK_BY_FAMILY

    family = str(job.get("family") or "")
    return str(job.get("clock") or CLOCK_BY_FAMILY.get(family) or "")


def _catalog_clock(family: str) -> str:
    from firm.research_jobs import CLOCK_BY_FAMILY

    return str(CLOCK_BY_FAMILY.get(family) or "")


def _observed_clock(parsed: dict[str, Any]) -> str:
    long_tf = str(parsed.get("long_tf") or "")
    short_tf = str(parsed.get("short_tf") or "")
    if long_tf and short_tf:
        return f"{long_tf}/{short_tf}"
    return long_tf or short_tf


def _load_approvals() -> dict[str, Any]:
    if not APPROVALS_PATH.exists():
        return {}
    try:
        raw = json.loads(APPROVALS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return {k: v for k, v in raw.items() if isinstance(v, dict)}


def certify_job(job: dict[str, Any]) -> dict[str, Any]:
    """Certificate for one walk-forward: setup, costs, and written verdicts."""
    family = str(job.get("family") or "")
    symbols = [str(s) for s in (job.get("symbols") or [])]
    side = str(job.get("side") or "BOTH").upper()
    parsed = parse_job_log(str(job.get("log_path") or ""))
    expected = _expected_clock(job)
    catalog = _catalog_clock(family)
    observed = _observed_clock(parsed)
    checks: list[dict[str, Any]] = []
    warnings: list[str] = []

    checks.append(
        _check(
            "log_exists",
            parsed["exists"],
            str(job.get("log_path") or "no log_path"),
        )
    )
    checks.append(
        _check(
            "strategy_in_log",
            bool(parsed["family"]) and parsed["family"] == family,
            f"job={family} log={parsed['family'] or 'missing'}",
        )
    )
    checks.append(
        _check(
            "clock_matches_job",
            bool(observed) and observed == expected,
            f"job={expected or 'unset'} log={observed or 'unset'}",
        )
    )
    if catalog and expected and catalog != expected:
        warnings.append(
            f"{family} ran {expected}; catalog clock is {catalog}. "
            "The test is still valid for the clock it ran, but it was not the catalog default."
        )

    expect_n = len(symbols) * (2 if side == "BOTH" else 1)
    tested = parsed.get("tested")
    checks.append(
        _check(
            "pair_count",
            tested == expect_n if tested is not None else False,
            f"log tested {tested} pairs, job expected {expect_n}",
        )
    )

    expected_bps = round(DEFAULT_COSTS.slippage * 10_000, 2)
    slips = parsed.get("slippage_bps") or []
    checks.append(
        _check(
            "costs_charged",
            bool(slips) and all(abs(s - expected_bps) < 0.5 or s >= expected_bps for s in slips),
            (
                f"slippage in log={slips[:6]} expected>={expected_bps} bps; "
                f"funding default include={DEFAULT_COSTS.include_funding}"
            ),
        )
    )
    checks.append(
        _check(
            "enough_history",
            all(int(row.get("bars") or 0) >= 500 for row in parsed.get("pair_bars") or [])
            if parsed.get("pair_bars")
            else False,
            f"{len(parsed.get('pair_bars') or [])} pair slices logged",
        )
    )

    approvals = _load_approvals()
    missing_rows: list[str] = []
    tf_by_side = {}
    if "/" in (observed or expected or "/"):
        parts = (observed or expected).split("/", 1)
        tf_by_side = {"LONG": parts[0], "SHORT": parts[-1]}
    sides = ["LONG", "SHORT"] if side == "BOTH" else [side]
    for symbol in symbols:
        for rec_side in sides:
            tf = tf_by_side.get(rec_side, "")
            found = False
            for key, record in approvals.items():
                parsed_key = parse_approval_key(key)
                if parsed_key is None:
                    continue
                rec_family, rec_symbol, rec_s = parsed_key
                rec_tf = str(record.get("timeframe") or "")
                rec_strat = str(record.get("strategy") or rec_family)
                if (
                    rec_strat == family
                    and rec_symbol == symbol
                    and rec_s == rec_side
                    and (not tf or rec_tf == tf)
                ):
                    found = True
                    break
            if not found:
                missing_rows.append(f"{family}:{symbol}:{rec_side}:{tf or '?'}")
    checks.append(
        _check(
            "verdicts_written",
            not missing_rows,
            "all pairs in approvals file"
            if not missing_rows
            else "missing " + ", ".join(missing_rows),
        )
    )

    ok = all(c["ok"] for c in checks)
    occurred = job.get("finished_at") or job.get("last_updated_at") or job.get("started_at")
    return {
        "job_id": job.get("id"),
        "family": family,
        "clock": observed or expected,
        "ok": ok,
        "checks": checks,
        "warnings": warnings,
        "oos_pairs": tested,
        "pairs_approved": parsed.get("approved"),
        "finished_at": job.get("finished_at") or occurred,
        "started_at": job.get("started_at"),
        "created_at": job.get("created_at"),
        "occurred_at": occurred,
    }


def _row_expected_clock(row: dict[str, Any], scan_family: str, scan_clock: str) -> str:
    """Catalog clock for this plan row: scan family or that sleeve's approval clock."""
    from core.data.ohlcv import normalise_timeframe
    from firm.research_jobs import CLOCK_BY_FAMILY

    name = str(row.get("strategy") or "")
    side = str(row.get("side") or "").upper()
    symbol = str(row.get("symbol") or "")
    rec_tf = str(row.get("timeframe") or "")
    from config.pipeline import is_paper_scan_sleeve

    if is_paper_scan_sleeve(name, symbol, side, rec_tf):
        return rec_tf
    if name != scan_family:
        from config.universe import get_universe

        universe = get_universe()
        for key, rec in universe.approvals.items():
            if not isinstance(rec, dict) or rec.get("approved") is not True:
                continue
            parsed = parse_approval_key(key)
            if parsed is None:
                continue
            rec_name, rec_symbol, rec_side = parsed
            if rec_name == name and rec_symbol == symbol and rec_side == side:
                tf = str(rec.get("timeframe") or "")
                try:
                    return normalise_timeframe(tf) if tf else tf
                except (ValueError, TypeError, KeyError):
                    return tf
    blob = scan_clock if name == scan_family else (CLOCK_BY_FAMILY.get(name) or "")
    if "/" not in (blob or ""):
        return str(row.get("timeframe") or "")
    long_tf, short_tf = blob.split("/", 1)
    return long_tf if side == "LONG" else short_tf


def certify_paper() -> dict[str, Any]:
    """Did the last paper cycle scan approved pairs plus the research sleeve?"""
    from config.universe import get_universe
    from firm.research_jobs import CLOCK_BY_FAMILY, paper_scan_family

    family = paper_scan_family()
    clock = CLOCK_BY_FAMILY.get(family) or ""
    checks: list[dict[str, Any]] = []
    cycle: dict[str, Any] = {}
    if LAST_CYCLE_PATH.exists():
        try:
            loaded = json.loads(LAST_CYCLE_PATH.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                cycle = loaded
        except (json.JSONDecodeError, OSError):
            cycle = {}
    plan = cycle.get("plan") if isinstance(cycle.get("plan"), list) else []
    names = {str(row.get("strategy") or "") for row in plan if isinstance(row, dict)}
    universe = get_universe()
    approved_names = set()
    for key, rec in universe.approvals.items():
        if not isinstance(rec, dict) or rec.get("approved") is not True:
            continue
        parsed = parse_approval_key(key)
        if parsed is not None:
            approved_names.add(parsed[0])
    override_names = set()
    for key, _rec in universe.paper_override_records:
        parsed = parse_approval_key(key)
        if parsed is not None:
            override_names.add(parsed[0])
    from config.pipeline import PAPER_SCAN_SLEEVES

    # Research clock family + live-gated sleeves + operator paper vetoes
    # + named paper candidates (ATR 1h on BNB/XRP/AVAX).
    allowed = {family} | approved_names | override_names | {n for n, *_ in PAPER_SCAN_SLEEVES}
    approved_pairs = set(universe.approved_pairs)
    plan_pairs = {
        (str(row.get("symbol") or ""), str(row.get("side") or "").upper())
        for row in plan
        if isinstance(row, dict)
    }
    missing_approved = sorted(approved_pairs - plan_pairs)
    sleeve_ok = bool(plan) and names <= allowed and not missing_approved
    checks.append(
        _check(
            "paper_sleeve",
            sleeve_ok,
            (
                f"scan_family={family} plan={sorted(names) or 'empty'}"
                + (f" missing_approved={missing_approved}" if missing_approved else "")
            ),
        )
    )
    tf_ok = True
    tf_detail = []
    for row in plan:
        if not isinstance(row, dict):
            continue
        want = _row_expected_clock(row, family, clock)
        rec_tf = str(row.get("timeframe") or "")
        tf_detail.append(f"{row.get('symbol')} {row.get('side')} {rec_tf} (want {want})")
        if rec_tf != want:
            tf_ok = False
    checks.append(_check("paper_clock", bool(plan) and tf_ok, "; ".join(tf_detail[:6]) or "no plan"))
    errors = cycle.get("errors") if isinstance(cycle.get("errors"), list) else []
    recon_ok = not any("reconcil" in str(e).lower() for e in errors)
    checks.append(
        _check(
            "broker_ledger",
            recon_ok,
            "no reconciliation errors" if recon_ok else str(errors[:3]),
        )
    )
    return {
        "ok": all(c["ok"] for c in checks) if checks else False,
        "scan_family": family,
        "clock": clock,
        "last_cycle_at": cycle.get("started_at"),
        "orders_placed": cycle.get("orders_placed"),
        "signals_found": cycle.get("signals_found"),
        "checks": checks,
    }


def certify_implementation() -> dict[str, Any]:
    """Did an approved coding mandate actually land in the registry?

    Finished-job certificates cannot catch work that never started. This is
    the check that missed trend_pullback_htf: Inbox empty, mandate approved,
    no file, no validator.
    """
    from firm.research_jobs import implementation_gaps

    gaps = implementation_gaps()
    if not gaps:
        return {
            "ok": True,
            "checks": [
                _check(
                    "approved_sleeve_coded",
                    True,
                    "No approved coding mandate is waiting on a missing file.",
                )
            ],
        }
    details = []
    for row in gaps:
        family = row.get("family") or "strategy"
        details.append(
            f"{family} approved but not in list_strategies(); no walk-forward can start"
        )
    return {
        "ok": False,
        "checks": [
            _check("approved_sleeve_coded", False, "; ".join(details)),
        ],
    }


def integrity_snapshot() -> dict[str, Any]:
    """Operator-facing pack: every finished job plus the paper clock."""
    from firm.research_jobs import list_jobs

    jobs = [j for j in list_jobs() if j.get("status") in {"done", "failed"}]
    certificates = []
    for job in jobs:
        cert = job.get("integrity") if isinstance(job.get("integrity"), dict) else None
        if cert is None or not cert.get("checks"):
            cert = certify_job(job)
        else:
            cert = dict(cert)
        occurred = (
            job.get("finished_at")
            or job.get("last_updated_at")
            or job.get("started_at")
            or job.get("created_at")
        )
        cert["finished_at"] = cert.get("finished_at") or job.get("finished_at") or occurred
        cert["started_at"] = cert.get("started_at") or job.get("started_at")
        cert["created_at"] = cert.get("created_at") or job.get("created_at")
        cert["occurred_at"] = cert.get("occurred_at") or occurred
        certificates.append(cert)
    paper = certify_paper()
    implementation = certify_implementation()
    failed = [c for c in certificates if not c.get("ok")]
    return {
        "ok": (not failed) and paper.get("ok") is True and implementation.get("ok") is True,
        "auditor": "performance_auditor",
        "jobs": certificates,
        "paper": paper,
        "implementation": implementation,
        "failed_jobs": [c.get("job_id") for c in failed],
        "note": (
            "Performance Auditor owns this pack. OOS trade counts on Strategies "
            "are the walk-forward output; these checks certify the setup that "
            "produced them (family, clock, costs, written verdicts), that "
            "paper is scanning that same sleeve, and that an approved coding "
            "mandate actually has a file in the registry."
        ),
    }


def certify_and_store_job(job: dict[str, Any]) -> dict[str, Any]:
    """Write the certificate onto the job row and escalate if it failed."""
    from firm import research_jobs

    cert = certify_job(job)
    jobs = research_jobs._load()
    for row in jobs:
        if row.get("id") == job.get("id"):
            row["integrity"] = cert
    research_jobs._save(jobs)
    if not cert.get("ok"):
        from firm import memory

        fails = [c["detail"] for c in cert.get("checks") or [] if not c.get("ok")]
        memory.escalate(
            agent="performance_auditor",
            title=f"Integrity failed: {job.get('family')} job {job.get('id')}",
            detail="; ".join(fails)[:800],
            severity="warning",
        )
    return cert
