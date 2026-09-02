"""
Who does what, which gates need a human, and what "continuous work" means.

The desk is supposed to run with the operator at a few gates — not as the
person who has to notice that everyone stopped. This module is the written
org chart the Floor and Desk Head share.
"""

from __future__ import annotations

from typing import Any

# Human only has to act here. Research advancement is envelope-tiered.
OPERATOR_GATES: list[str] = [
    "Tier C Inbox: new symbol, venue, feed/API, any risk-parameter change.",
    "Paper → live (never timeout-approve; never because a test looks ok).",
    "Halt / kill switch.",
    "Veto a Tier B item within 24h if you do not want it auto-approved.",
    "Novel strategy: Inbox shows the proposal plus the full coding brief. Approve hands that brief to Cursor (research/coding_inbox/NOW.md).",
]

OPERATOR_DOES_NOT: list[str] = [
    "Start a Tier A walk-forward — standby launches on a free slot.",
    "Notice that Quant has been quiet and poke Wake Floor.",
    "Invent the next research idea because the catalog ran out of names.",
    "Audit whether the GM kept the pipeline moving — Strategy Advisor does.",
]

EMPLOYEE_MANDATES: dict[str, dict[str, str]] = {
    "strategy_advisor": {
        "title": "Strategy Advisor",
        "cadence": "daily, and within 15 minutes of a GM slip",
        "mandate": (
            "Advises you. Looks at the whole firm — catalog, Inbox, walk-forward, "
            "duty board — and holds the GM accountable when research sits idle. "
            "Cannot trade, cannot raise risk, cannot skip a Tier C gate."
        ),
        "does": (
            "On on_test_finished: within 15 minutes, confirm a walk-forward is "
            "running or a Tier B/C gate is in Inbox. Escalate dropped balls "
            "(empty standby, dropped events, uncoded novel family)."
        ),
        "does_not": (
            "Does not write strategy files, start validators, grant live, or "
            "replace Quant. Cannot skip paper-to-live."
        ),
        "goal": "No dropped ball after a test finishes.",
        "target": "Flag the GM the same cycle if a slot freed and nothing launched.",
        "kpi": "idle_cycles after a finished test with no running job or gate",
    },
    "desk_head": {
        "title": "Desk Head (GM)",
        "cadence": "daily, and on every walk-forward slot free (same tick)",
        "mandate": (
            "Runs daily ops. Owns walk-forward slots. on_walk_forward_slot_free "
            "launches the next standby family in the same tick. Does not wait "
            "for the daily cadence."
        ),
        "does": (
            "On on_walk_forward_slot_free (deadline: 0s): start the next "
            "launch-ready standby job up to configured parallelism. On "
            "on_inbox_empty (5 min): file Tier B/C or catalog-review. Writes "
            "the daily briefing."
        ),
        "does_not": (
            "Does not write core/strategy files, approve live, raise size, or "
            "invent families outside the catalog."
        ),
        "goal": "A free walk-forward slot never sits idle while standby is non-empty.",
        "target": "exactly the configured number of running validators when standby exists.",
        "kpi": "seconds from slot-free to next start (must be execution-bound)",
    },
    "sleeve_engineer": {
        "title": "Sleeve Engineer",
        "cadence": "hourly, and on on_coding_request_queued / on_standby_depth_low",
        "mandate": (
            "Converts an approved catalog family into a coded, registered sleeve "
            "and keeps launch-ready standby at floor 1 / target 2. Allowed "
            "templates become JSON specs. Novel families escalate to Cursor; "
            "this seat does not LLM-write strategy files."
        ),
        "does": (
            "On on_coding_request_queued (15 min): register a known sleeve or "
            "escalate a novel family. On on_standby_depth_low (15 min): stage "
            "the next ranked hypothesis into standby."
        ),
        "does_not": (
            "Does not propose families, approve tests, judge results, size "
            "positions, modify risk parameters, or touch live."
        ),
        "goal": "Zero approved-uncoded families older than one cycle; standby never empty.",
        "target": "standby depth >= 1, target 2, coding queue cap 5.",
        "kpi": "standby_depth and approved_uncoded_age",
    },
    "ops_engineer": {
        "title": "Ops Engineer",
        "cadence": "hourly, and within 15 minutes of on_llm_timeout",
        "mandate": (
            "Keeps the clock honest: data feed, hung agents, kill switch, LLM seats. "
            "Does not pick strategies."
        ),
        "does": (
            "On on_llm_timeout (15 min): retry or escalate with an aging ticket. "
            "Hung-job tickets (3x rolling median) are this seat's to inspect."
        ),
        "does_not": "Does not pick strategies, size trades, or own the research queue.",
        "goal": "A live Gemini timeout is retried or on Escalations within 15 minutes.",
        "target": "Timeouts age on the board until resolved; they do not vanish.",
        "kpi": "unresolved LLM timeout older than 60 minutes",
    },
    "quant_researcher": {
        "title": "Quant Researcher",
        "cadence": "when catalog depth is low or the pipeline is idle",
        "mandate": (
            "Owns catalog depth and new-family intake. When coded leftovers "
            "run out, proposing a NEW snake_case family (distinct math) is "
            "the job — not waiting a week, and not only cloning clocks."
        ),
        "does": (
            "On catalog_depth: land newly coded sleeves, keep near-miss "
            "param grids, and name new families that Cursor can code. Do not "
            "re-queue a clear-loss family under a new clock."
        ),
        "does_not": (
            "Does not grant trading rights, write strategy files, or start "
            "walk-forward. research.validate is the only approvals writer."
        ),
        "goal": "At least the configured number of ranked un-queued hypotheses.",
        "target": "Retry within 10 minutes after an LLM timeout.",
        "kpi": "catalog_depth",
    },
    "performance_auditor": {
        "title": "Performance Auditor",
        "cadence": "daily, and after every walk-forward (on_test_rejected: 15 min)",
        "mandate": (
            "Certifies that each walk-forward ran the intended family, clock, "
            "and costs. On every reject: write a post-mortem (why, pairs, "
            "disposition) that mutates catalog ranking. Also reviews closed trades."
        ),
        "does": (
            "On on_test_rejected (15 min): post-mortem with retire | "
            "re-parameterise | retest_under_different_regime. Flag sleeve "
            "mismatch vs the job ledger."
        ),
        "does_not": "Does not invent an edge, pick the next family, or promote anyone under 20 scored decisions.",
        "goal": "Paper scans the ledger's current family. Every reject has a post-mortem.",
        "target": "Flag a sleeve mismatch the same cycle it appears.",
        "kpi": "paper_mismatch_cycles and missing_postmortems",
    },
    "portfolio_manager": {
        "title": "Portfolio Manager",
        "cadence": "daily",
        "mandate": "Allocation opinions only. Cannot grant trading rights.",
        "does": (
            "When an approved pair exists: suggest size tilts. May only shrink "
            "size or sit out. Until then, report that allocation is idle."
        ),
        "does_not": "Cannot raise size above 1.0, add unapproved symbols, or unlock live.",
        "goal": "Allocation notes stay advisory.",
        "target": "Never grant trading rights or raise size.",
        "kpi": "proposals that stay inside advisory scope",
    },
    "regime_analyst": {
        "title": "Regime Analyst",
        "cadence": "four-hourly",
        "mandate": "Names the market regime the other seats condition on.",
        "does": (
            "On the four-hour cadence: post bull/bear/chop plus a volatility "
            "bucket before the next paper cycle that needs it."
        ),
        "does_not": "Does not place orders, pick a sleeve, or override walk-forward.",
        "goal": "A fresh regime reading on the four-hour cadence.",
        "target": "Post a regime before the next paper cycle that needs it.",
        "kpi": "hours since last successful regime post",
    },
    "risk_officer": {
        "title": "Risk Officer",
        "cadence": "hourly",
        "mandate": "Vetoes and size cuts. Last word stays with the risk engine.",
        "does": (
            "Hourly: review kill switch, open exposure, and rejected signals. "
            "Veto a symbol or cut size when the book is offside."
        ),
        "does_not": "Cannot raise limits, disable the kill switch, or enlarge a position.",
        "goal": "Veto or cut size when the book is offside. Cannot raise risk.",
        "target": "Hourly read of kill switch, exposure, and open risk.",
        "kpi": "unreviewed kill-switch or limit breach",
    },
    "sentiment_analyst": {
        "title": "Sentiment Analyst",
        "cadence": "four-hourly",
        "mandate": "Live search narrative. Dark without an xAI key, on purpose.",
        "does": (
            "When an xAI key is set: post narrative for the book on the "
            "four-hour cadence. Without a key, skip cleanly so research is not blocked."
        ),
        "does_not": "Does not trade, size, or own the research queue. A missing xAI key is not an outage.",
        "goal": "Narrative for the book when xAI is configured; stay dark if not.",
        "target": "Skip cleanly without a key. Do not block research.",
        "kpi": "false outages reported for a missing xAI key",
    },
}

def org_snapshot() -> dict[str, Any]:
    """Payload for Overview / Floor so the operator can see the org, not guess it."""
    return {
        "gm": "desk_head",
        "gm_title": EMPLOYEE_MANDATES["desk_head"]["title"],
        "gm_mandate": EMPLOYEE_MANDATES["desk_head"]["mandate"],
        "gates": OPERATOR_GATES,
        "not_your_job": OPERATOR_DOES_NOT,
        "employees": [
            {"id": name, **spec} for name, spec in EMPLOYEE_MANDATES.items()
        ],
        "note": (
            "Ten seats. Sleeve Engineer owns coding/standby. Desk Head launches "
            "walk-forward on a free slot the same tick. Quant owns catalog depth. "
            "Tier A research auto-advances; paper-to-live is still a hard human "
            "gate. Trust-ladder P&L is trading authority, not the research KPI."
        ),
    }
