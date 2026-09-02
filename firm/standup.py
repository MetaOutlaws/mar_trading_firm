"""Daily operator briefing: where we are, what needs you, what is next.

Computed from live files and SQLite — not an LLM summary — so it cannot
invent progress. The Overview tab is the home for this; Health still has
the long diagnosis.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from config.settings import get_settings
from config.universe import get_universe
from core.risk.killswitch import KillSwitch
from firm.locks import PAPER_PID_PATH, read_pidfile
from firm.research_catalog import next_catalog_step


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _age_minutes(iso: str | None) -> float | None:
    if not iso:
        return None
    try:
        stamp = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return (utcnow() - stamp).total_seconds() / 60.0


def _job_progress(job: dict[str, Any]) -> str:
    """Last useful line from the validator log, so the desk is not a black box."""
    path = Path(str(job.get("log_path") or ""))
    if path.exists():
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            lines = []
        interesting = []
        for line in lines:
            if "VERDICT:" in line or "Fetching" in line or "strategy=" in line:
                snippet = line.split("|")[-1].strip() if "|" in line else line.strip()
                interesting.append(snippet)
        if interesting:
            return interesting[-1][:220]
    return str(job.get("detail") or "Job recorded, no log yet.")


def build_standup() -> dict[str, Any]:
    """One briefing payload for Overview. Safe to call on every desk poll."""
    from core.execution.engine import load_last_cycle
    from firm import memory
    from firm.llm import provider_status
    from firm.research_jobs import list_jobs, open_code_mandates, paper_scan_family, pipeline_snapshot
    from firm.accountability import accountability_snapshot
    from core.strategy.registry import list_strategies

    settings = get_settings()
    get_universe.cache_clear()
    universe = get_universe()
    kill = KillSwitch().read()
    cycle = load_last_cycle() or {}
    jobs = list_jobs()
    pipeline = pipeline_snapshot()
    inbox = memory.pending_proposals(limit=40)
    strategy_inbox = [p for p in inbox if p.get("kind") == "strategy"]
    review_inbox = [
        p
        for p in inbox
        if isinstance(p.get("payload"), dict)
        and p["payload"].get("action") == "catalog_review"
    ]
    other_inbox = [
        p
        for p in inbox
        if p.get("kind") != "strategy" and p not in review_inbox
    ]
    escalations = memory.open_escalations(limit=20)
    providers = provider_status()
    gemini_ok = bool((providers.get("providers") or {}).get("gemini", {}).get("configured"))
    xai_ok = bool((providers.get("providers") or {}).get("xai", {}).get("configured"))
    paper = read_pidfile(PAPER_PID_PATH)
    scan_family = paper_scan_family()
    approved_n = len(universe.approved_pairs)
    mode = settings.trading_mode.value
    killed = bool(kill.tripped)

    happening: list[str] = []
    needs_you: list[str] = []
    taken: list[str] = []
    nxt: list[str] = []
    blockers: list[dict[str, str]] = []

    running = [j for j in jobs if j.get("status") in {"running", "queued"}]
    mandates = open_code_mandates()
    if running:
        job = running[-1]
        happening.append(
            f"Walk-forward {job.get('status')} for {job.get('family')} on "
            f"{', '.join(job.get('symbols') or [])} ({job.get('side') or 'BOTH'}). "
            f"{_job_progress(job)}"
        )
        nxt.append(
            "Let this test finish. The verdict will appear on Strategies — "
            "Inbox approve already happened."
        )
        if job.get("family") == "donchian_breakout":
            nxt.append(
                "This run uses the RSI clock (LONG 15m / SHORT 4h). The catalog "
                "asked for Donchian at 1h/4h. If 15m rejects, the next honest test is 1h."
            )
    elif mandates:
        mandate = mandates[0]
        family = mandate.get("family") or "the next family"
        if mandate.get("phase") == "implement":
            happening.append(
                f"BLOCKED: {family} is approved but not coded. No employee "
                "writes strategy files. Walk-forward cannot start."
            )
            needs_you.append(
                f"Code {family} into core/strategy so it appears in the registry. "
                "Catch-up starts the test automatically after that — not before."
            )
            blockers.append(
                {
                    "level": "blocking",
                    "text": (
                        f"{family} approved, not in registry. Integrity check "
                        "approved_sleeve_coded fails until the file exists."
                    ),
                }
            )
            nxt.append(
                f"Do not wait for someone to notice. Implementation of {family} "
                "is the open gate."
            )
        else:
            happening.append(
                f"You already approved {family}. Walk-forward is starting — no second click."
            )
            nxt.append(
                f"Nothing else is needed from you until the {family} walk-forward finishes."
            )
    else:
        happening.append("No walk-forward is running.")

    try:
        duty = accountability_snapshot()
    except Exception:
        duty = {"slips": []}
    for slip in duty.get("slips") or []:
        happening.append(
            f"Slip — {slip.get('owner')}: {slip.get('issue')}"
        )
        blockers.append(
            {
                "level": "waiting",
                "text": f"{slip.get('owner')}: {slip.get('expected')}",
            }
        )

    cycle_age = _age_minutes(str(cycle.get("started_at") or ""))
    if paper.get("alive"):
        happening.append(
            f"Paper clock is up (pid {paper.get('pid')}), scanning {scan_family} "
            f"on an unapproved pool. Last cycle: {int(cycle.get('symbols_scanned') or 0)} pairs, "
            f"{int(cycle.get('signals_found') or 0)} signals, "
            f"{int(cycle.get('orders_placed') or 0)} orders"
            + (f" ({int(cycle_age)}m ago)." if cycle_age is not None else ".")
        )
    elif cycle_age is not None and cycle_age < 20:
        happening.append(
            f"Paper wrote a cycle {int(cycle_age)}m ago but has no lock file. "
            "Restart paper trading so a second loop cannot start."
        )
        blockers.append(
            {
                "level": "blocking",
                "text": "Paper is running without a single-instance lock. Restart it.",
            }
        )
        needs_you.append("Stop extra paper loops, then start exactly one: python scripts/run_paper_trading.py")
    else:
        happening.append("Paper clock is not running. No new scans, no 60-day evidence.")
        blockers.append({"level": "blocking", "text": "Paper trading is stopped."})
        needs_you.append("Start paper: python scripts/run_paper_trading.py")

    if cycle_age is not None and cycle_age > 20 and paper.get("alive"):
        blockers.append(
            {
                "level": "blocking",
                "text": f"Paper pid is alive but the last cycle is {int(cycle_age)}m old — it may be stuck.",
            }
        )
        needs_you.append("Check logs/paper_trading.log; restart the paper loop if it is wedged.")

    if scan_family == "rsi_trend" and any(j.get("family") == "donchian_breakout" for j in jobs):
        blockers.append(
            {
                "level": "waiting",
                "text": "Paper is still scanning rsi_trend while Donchian is the research family.",
            }
        )

    if killed:
        blockers.append({"level": "blocking", "text": "Kill switch is tripped. No new risk."})
        needs_you.append("Investigate, then reset with the exact acknowledgement phrase.")

    if not gemini_ok:
        blockers.append({"level": "blocking", "text": "Gemini key missing — employees will skip."})
        needs_you.append("Set GEMINI_API_KEY in .env and restart the API.")
    else:
        happening.append("Gemini seats are configured for cheap/standard/strong employees.")

    if not xai_ok:
        blockers.append(
            {
                "level": "waiting",
                "text": "No XAI_API_KEY — Sentiment stays dark. Paper and walk-forward do not need it.",
            }
        )

    if approved_n == 0:
        happening.append("Live is locked: no pair has passed walk-forward.")
        blockers.append(
            {
                "level": "waiting",
                "text": "No research-approved pairs. Stay in paper until Strategies shows a pass.",
            }
        )
    else:
        happening.append(f"{approved_n} pair(s) are approved to trade.")

    if strategy_inbox:
        needs_you.append(
            f"{len(strategy_inbox)} strategy proposal(s) in Inbox. Approve queues a test; "
            "reject drops it. Quant proposing is not the test."
        )
    if review_inbox:
        needs_you.append(
            "Catalog is exhausted. Inbox has a catalog-review gate: funding_fade "
            "still needs a feed. Approve records that you have seen it; it does "
            "not start a test."
        )
    if other_inbox:
        needs_you.append(f"{len(other_inbox)} non-strategy item(s) in Inbox (risk/ops/auditor).")
    if escalations:
        needs_you.append(f"{len(escalations)} open escalation(s). Ack on Inbox when you have read them.")

    for job in jobs[-6:]:
        created = str(job.get("created_at") or "")
        age = _age_minutes(created) or 999
        if age <= 24 * 60:
            taken.append(
                f"{job.get('family')}: walk-forward {job.get('status')} "
                f"({', '.join(job.get('symbols') or [])})."
            )
    if running:
        fam = running[-1].get("family") or "strategy"
        taken.append(f"Inbox approve queued the {fam} walk-forward (approve is not a trade).")

    taken = list(dict.fromkeys(taken))[:6]

    coded = set(list_strategies())
    tested = {
        str(j.get("family"))
        for j in jobs
        if j.get("status") in {"done", "failed"} and j.get("family")
    }
    next_work = next_catalog_step(tested=tested, coded=coded)
    latest_done = next(
        (j for j in reversed(jobs) if j.get("status") in {"done", "failed"}),
        None,
    )
    if not running:
        if mandates:
            pass  # already appended under happening
        elif latest_done:
            nxt.append(
                f"{latest_done.get('family')} walk-forward finished "
                f"({latest_done.get('pairs_approved', 0)} pairs). "
                "If Inbox is empty, Desk Head files the next catalog gate. "
                "Strategy Advisor flags the GM if that does not happen."
            )
            if next_work:
                nxt.append(
                    f"Next catalog step is {next_work['action']} {next_work['family']}."
                )
        elif next_work:
            nxt.append(
                f"Next catalog step is {next_work['action']} {next_work['family']}. "
                "Approve in Inbox; once it is coded the test starts without a second click."
            )
    if mode != "paper":
        nxt.append(f"Mode is {mode}. Live/testnet only trade approved pairs.")
    else:
        nxt.append("Do not flip TRADING_MODE=live. Go-live gates are not met.")

    if not needs_you:
        if running:
            needs_you.append("Nothing waiting on you. Let the walk-forward finish; do not restart it.")
        elif mandates and mandates[0].get("phase") == "implement":
            family = mandates[0].get("family") or "the next family"
            needs_you.append(
                f"Code {family}. Empty Inbox does not mean the floor coded it."
            )
        elif mandates:
            needs_you.append(
                "Nothing waiting on you. Walk-forward should start from the approved coded sleeve."
            )
        elif next_work:
            needs_you.append(
                f"Approve {next_work['action']} for {next_work['family']} in Inbox. "
                "Empty Inbox with catalog work is a GM miss — Strategy Advisor is watching."
            )
        else:
            needs_you.append(
                "Every coded family has a verdict (none passed). funding_fade "
                "still needs a feed. That decision belongs in Inbox as a catalog "
                "review — not 'nothing waiting on you'."
            )

    if killed:
        headline = "Halted. Kill switch is tripped."
        posture = "halted"
    elif running:
        headline = (
            f"Paper. Testing {running[-1].get('family')} now. Live locked."
        )
        posture = "testing"
    elif mandates:
        phase = mandates[0].get("phase")
        family = mandates[0].get("family")
        if phase == "implement":
            headline = (
                f"Paper. BLOCKED: {family} approved but not coded. Live locked."
            )
            posture = "blocked"
        else:
            headline = (
                f"Paper. Next work is {family} ({phase}). Live locked."
            )
            posture = "testing"
    elif approved_n:
        headline = f"Paper. {approved_n} approved pair(s). Live still needs go-live gates."
        posture = "approved_paper"
    else:
        headline = "Paper. No sleeve has passed walk-forward. Live locked."
        posture = "paper"

    now_banner = (pipeline.get("now") or {}).get("label") or headline

    return {
        "as_of": utcnow().isoformat(),
        "headline": headline,
        "now_label": now_banner,
        "posture": posture,
        "mode": mode,
        "happening_now": happening,
        "needs_you": needs_you,
        "taken": taken or ["No operator actions recorded in the research queue yet."],
        "next": nxt,
        "blockers": blockers,
        "scan_family": scan_family,
        "paper": paper,
        "approved_pairs": approved_n,
        "coded_families": sorted(coded),
    }
