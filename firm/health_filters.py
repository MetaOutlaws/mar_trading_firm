"""
What counts as a live ops problem versus leftover history.

Desk Head and Ops Engineer read SQLite. After a provider swap or a patched
bug, the last failed rows stay in the table forever. Without a filter they
re-diagnose yesterday's DeepSeek skip as today's outage, then escalate, then
read their own escalation on the next cycle.
"""

from __future__ import annotations

from typing import Any

#: Providers that used to serve employee seats and no longer do.
RETIRED_PROVIDERS = ("deepseek", "openai")


def is_transient_llm_error(text: str) -> bool:
    """True for a live Gemini/xAI timeout or brief outage — not retired-key noise."""
    if is_resolved_noise(text):
        return False
    lowered = (text or "").lower()
    return any(
        token in lowered
        for token in (
            "timed out",
            "timeout",
            "read operation",
            "connecterror",
            "temporarily unavailable",
        )
    )


def is_resolved_noise(text: str) -> bool:
    """True when a log line is a known-fixed or retired-provider artifact."""
    lowered = (text or "").lower()
    if not lowered:
        return False

    compact = lowered.replace(" ", "").replace("_", "")
    if "killswitchstate" in compact and "istripped" in compact:
        return True
    if "is_tripped" in lowered and "killswitch" in compact:
        return True

    if "generate_content_free_tier_requests" in lowered:
        return True
    # Truncated 429 bodies often drop the free_tier metric name.
    if "429" in lowered and ("quota" in lowered or "rate limit" in lowered):
        return True

    mentions_retired = any(name in lowered for name in RETIRED_PROVIDERS)
    if mentions_retired and (
        "api key" in lowered
        or "apikey" in compact
        or "skipped" in lowered
        or "missing" in lowered
    ):
        return True
    return False


def mark_superseded_failures(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Tag older failures once the same employee later succeeded.

    Desk Head reads the last twenty runs. Without this, a 09:23 free-tier 429
    stays 'current' even after Quant completed at 09:38.
    """
    latest_success_at: dict[str, str] = {}
    for run in runs:
        agent = str(run.get("agent") or "")
        if (
            agent
            and run.get("status") == "success"
            and agent not in latest_success_at
        ):
            latest_success_at[agent] = str(run.get("started_at") or "")

    tagged: list[dict[str, Any]] = []
    for run in runs:
        item = annotate_run(run)
        agent = str(run.get("agent") or "")
        started = str(run.get("started_at") or "")
        succeeded_at = latest_success_at.get(agent)
        if (
            succeeded_at
            and started
            and started < succeeded_at
            and run.get("status") in {"failed", "skipped"}
        ):
            item = dict(item)
            item["historical_noise"] = True
            item["operator_note"] = (
                "Superseded: this employee later completed successfully. "
                "Do not escalate or sit out because of this row."
            )
        tagged.append(item)
    return tagged


def annotate_run(run: dict[str, Any]) -> dict[str, Any]:
    """Tag a run so an LLM will not treat a patched error as current."""
    blob = " ".join(
        str(run.get(key) or "")
        for key in ("error", "reasoning", "task")
    )
    if not is_resolved_noise(blob):
        return run
    tagged = dict(run)
    tagged["historical_noise"] = True
    tagged["operator_note"] = (
        "Resolved history. DeepSeek/OpenAI are retired; employee seats use "
        "Gemini. The KillSwitchState.is_tripped alias is patched. Do not "
        "escalate or sit out because of this row."
    )
    return tagged


def llm_seat_briefing() -> dict[str, Any]:
    """Current seats, in language Desk Head and Ops can quote without guessing."""
    from firm.llm import LlmRouter, ModelTier, provider_status

    catalogue = LlmRouter._catalogue_from_env()
    snapshot = provider_status(catalogue=catalogue)
    active: list[dict[str, Any]] = []
    optional: list[dict[str, Any]] = []
    for row in snapshot.get("tiers") or []:
        entry = {
            "tier": row.get("tier"),
            "provider": row.get("provider"),
            "model": row.get("model"),
            "configured": bool(row.get("configured")),
        }
        if row.get("tier") == ModelTier.SEARCH.value:
            entry["note"] = (
                "Sentiment Analyst only. A missing xAI key is expected and "
                "does not degrade cheap/standard/strong employees."
            )
            optional.append(entry)
        else:
            active.append(entry)
    employee_ok = all(seat.get("configured") for seat in active)
    return {
        "employee_seats_ok": employee_ok,
        "active_employee_seats": active,
        "optional_seats": optional,
        "retired_providers": list(RETIRED_PROVIDERS),
        "note": (
            "Cheap, standard, and strong seats use Gemini. DeepSeek and "
            "OpenAI are retired leftovers. Do not report a missing DeepSeek "
            "key as operational degradation."
        ),
    }
