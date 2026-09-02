"""Stale DeepSeek / kill-switch rows must not look like a live outage."""

from __future__ import annotations

from firm.health_filters import annotate_run, is_resolved_noise, is_transient_llm_error, llm_seat_briefing
from firm import memory
from firm.memory_models import ProposalKind, ProposalStatus


def test_retired_provider_key_errors_are_noise() -> None:
    assert is_resolved_noise("No API key for deepseek. Set DEEPSEEK_API_KEY.")
    assert is_resolved_noise("Skipped: set DEEPSEEK_API_KEY. This seat uses deepseek-chat.")
    assert is_resolved_noise("missing API keys (XAI and Deepseek)")
    assert is_resolved_noise("No API key for openai")
    assert is_resolved_noise(
        "gemini returned 429: You exceeded your current quota, please check your plan"
    )
    assert is_resolved_noise("Desk Head: Gemini rate limit (429 quota exceeded)")


def test_patched_killswitch_alias_is_noise() -> None:
    assert is_resolved_noise(
        "gather failed: 'KillSwitchState' object has no attribute 'is_tripped'"
    )
    assert is_resolved_noise("code bug in ops_engineer: KillSwitchState.is_tripped")


def test_live_failures_are_not_noise() -> None:
    assert not is_resolved_noise("gemini call failed: The read operation timed out")
    assert is_transient_llm_error("gemini call failed: The read operation timed out")
    assert not is_transient_llm_error("Skipped: set DEEPSEEK_API_KEY")
    assert not is_resolved_noise("BTCUSDT ticker returned no price")
    assert not is_resolved_noise("")


def test_later_success_supersedes_earlier_429() -> None:
    from firm.health_filters import mark_superseded_failures

    tagged = mark_superseded_failures(
        [
            {
                "agent": "quant_researcher",
                "status": "success",
                "started_at": "2026-08-31T05:38:39Z",
                "error": "",
            },
            {
                "agent": "quant_researcher",
                "status": "failed",
                "started_at": "2026-08-31T05:23:05Z",
                "error": "gemini returned 429: truncated",
            },
        ]
    )
    assert tagged[0].get("historical_noise") is not True
    assert tagged[1]["historical_noise"] is True


def test_annotate_run_tags_resolved_history() -> None:
    tagged = annotate_run(
        {"agent": "ops_engineer", "error": "gather failed: 'KillSwitchState' object has no attribute 'is_tripped'"}
    )
    assert tagged["historical_noise"] is True
    clean = annotate_run({"agent": "desk_head", "error": "gemini call failed: timeout"})
    assert "historical_noise" not in clean


def test_seat_briefing_points_at_gemini_not_deepseek() -> None:
    brief = llm_seat_briefing()
    providers = {seat["provider"] for seat in brief["active_employee_seats"]}
    assert "gemini" in providers
    assert "deepseek" not in providers
    assert "deepseek" in brief["retired_providers"]


def test_clear_resolved_health_noise_closes_stale_inbox(firm_db) -> None:
    memory.escalate(
        "desk_head",
        "Desk Head: Missing API keys for xai and deepseek",
        "Multiple critical agents skipping because DeepSeek has no key.",
        severity="warning",
    )
    memory.escalate(
        "ops_engineer",
        "Persistent Agent Failures: Code Bug in KillSwitchState Attribute",
        "gather failed: 'KillSwitchState' object has no attribute 'is_tripped'",
        severity="warning",
    )
    live = memory.escalate(
        "ops_engineer",
        "Bybit feed is stale",
        "newest 15m candle is 2 hours old",
        severity="critical",
    )
    stale_id = memory.record_proposal(
        agent="desk_head",
        kind=ProposalKind.OPERATIONAL,
        title="Desk Head: sit out",
        payload={"ok_to_trade": False},
        rationale="Severe degradation from missing DeepSeek keys and KillSwitchState.is_tripped.",
        confidence=0.9,
    )
    live_id = memory.record_proposal(
        agent="risk_officer",
        kind=ProposalKind.RISK,
        title="Veto BTCUSDT",
        payload={"action": "veto", "symbol": "BTCUSDT"},
        rationale="drawdown",
        confidence=0.8,
        symbol="BTCUSDT",
    )

    result = memory.clear_resolved_health_noise()
    assert result["acked"] == 2
    assert result["rejected"] == 1

    open_ids = {row["id"] for row in memory.open_escalations()}
    assert live in open_ids
    assert len(open_ids) == 1

    from core.db import session_scope
    from firm.memory_models import Proposal

    with session_scope() as session:
        assert session.get(Proposal, stale_id).status == ProposalStatus.REJECTED.value
        assert session.get(Proposal, live_id).status == ProposalStatus.PENDING.value
