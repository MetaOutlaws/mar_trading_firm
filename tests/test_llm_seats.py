"""Operator switch for Gemini/xAI employee seats.

``LLM_SEATS_ENABLED=false`` skips every paper-cycle LLM seat and must not
construct or call an HTTP client. Regime gating still reads the Soko trend
file from the server-side label job. Default stays on.
"""

from __future__ import annotations

import httpx
import pytest

from config.settings import get_settings
from firm.memory_models import RunStatus


class _NoHttp:
    """Stand-in client. Construction or a post is a failed test."""

    def __init__(self, *args, **kwargs) -> None:
        raise AssertionError("httpx.Client constructed while LLM seats are disabled")

    def post(self, *args, **kwargs):
        raise AssertionError("LLM HTTP post while LLM seats are disabled")

    def close(self) -> None:
        return None


def _disable(monkeypatch) -> None:
    monkeypatch.setenv("LLM_SEATS_ENABLED", "false")
    monkeypatch.setenv("GEMINI_API_KEY", "AQ.DO-NOT-CALL")
    monkeypatch.setenv("XAI_API_KEY", "xai-DO-NOT-CALL")
    get_settings.cache_clear()


def test_llm_seats_default_on(monkeypatch) -> None:
    monkeypatch.delenv("LLM_SEATS_ENABLED", raising=False)
    get_settings.cache_clear()
    try:
        assert get_settings().llm_seats_enabled is True
    finally:
        get_settings.cache_clear()


def test_disabled_seats_construct_no_client_and_make_no_call(monkeypatch, firm_db) -> None:
    """Paper-cycle seats, a direct completion, and a ping stay off the network."""
    _disable(monkeypatch)
    monkeypatch.setattr(httpx, "Client", _NoHttp)
    monkeypatch.setattr("firm.llm.httpx.Client", _NoHttp)
    monkeypatch.setattr("firm.continuity.fill_walk_forward_slots", lambda source="": None)

    from firm.employees.sentiment_analyst import SentimentAnalyst
    from firm.llm import LlmError, LlmRouter, ModelTier, Provider, reset_model_cooldowns
    from firm.orchestrator import Orchestrator
    from firm.runtime import AgentOutput

    reset_model_cooldowns()
    orch = Orchestrator()
    assert orch.router._client is None
    results = orch.run_due()
    names = {row.agent for row in results}
    assert {
        "strategy_advisor",
        "sleeve_engineer",
        "quant_researcher",
        "regime_analyst",
    } <= names
    assert all(row.status is RunStatus.SKIPPED for row in results)
    assert all("LLM_SEATS_ENABLED=false" in row.error for row in results)

    forced = orch.run_named([employee.name for employee in orch.employees])
    assert all(row.status is RunStatus.SKIPPED for row in forced)

    solo = SentimentAnalyst()
    assert solo.run().status is RunStatus.SKIPPED
    assert solo._router is None

    router = LlmRouter()
    assert router._client is None
    with pytest.raises(LlmError, match="LLM_SEATS_ENABLED=false"):
        router.complete(
            agent="regime_analyst",
            system="do not call",
            user="do not call",
            response_model=AgentOutput,
            tier=ModelTier.CHEAP,
        )
    ping = router.ping(Provider.GEMINI)
    assert ping["disabled"] is True
    assert ping["ok"] is False
    with pytest.raises(LlmError, match="LLM_SEATS_ENABLED=false"):
        router._call(
            "quant_researcher",
            router.catalogue[ModelTier.STRONG],
            [],
            0.2,
            8,
            False,
            None,
        )
    orch.close()
    router.close()
    get_settings.cache_clear()


def test_disabled_seat_card_says_disabled_not_failed(monkeypatch, firm_db) -> None:
    """A stored HTTP 402 must not keep the card on 'failed' once seats are off."""
    _disable(monkeypatch)
    monkeypatch.setattr("firm.llm.httpx.Client", _NoHttp)

    from firm import memory
    from firm.accountability import accountability_snapshot
    from firm.employees.regime_analyst import RegimeAnalyst
    from firm.llm import LlmRouter

    analyst = RegimeAnalyst(LlmRouter())
    run_id = memory.start_run(
        analyst.name, analyst.role, "four hourly", prompt_version=analyst.prompt_version
    )
    memory.finish_run(
        run_id,
        RunStatus.FAILED,
        error="gemini returned 402: Payment Required",
    )
    card = analyst.status_card()
    assert card["status"] == "disabled"
    assert card["llm_seats_enabled"] is False
    assert "402" not in (card.get("last_error") or "")
    assert "fail" not in card["status"]

    board = accountability_snapshot()
    duty = next(row for row in board["duties"] if row["id"] == "regime_analyst")
    assert duty["last_status"] == "disabled"
    assert "402" not in (duty.get("last_error") or "")
    assert board["llm_failures"] == []
    assert not any("Gemini failed" in str(slip.get("issue")) for slip in board["slips"])
    get_settings.cache_clear()


def _fingerprint(plan) -> tuple:
    entries = tuple(
        sorted(
            (
                entry.strategy.name,
                entry.symbol,
                entry.side.value,
                entry.timeframe,
                entry.activation_mode,
            )
            for entry in plan.entries
        )
    )
    sitouts = tuple(
        sorted(
            (
                row["strategy"],
                row["symbol"],
                row["side"],
                row["reason"],
                row["activation_mode"],
            )
            for row in plan.regime_sitouts
        )
    )
    return plan.soko_trend, entries, sitouts


def test_regime_gated_sleeves_match_with_seats_disabled(monkeypatch, tmp_path) -> None:
    """The Soko file, not the regime-analyst seat, decides regime-gated sleeves.

    Bull blocks the bull-listed sleeve and the bear-only filter. Chop does the
    opposite for those two. Both labels come from ``last_soko_trend.json``.
    Turning seats off does not change either plan, and does not open a client.
    """
    from core.data.soko_trend import read_live_soko_trend
    from core.execution.engine import build_plan
    from tests.test_soko_trend_freshness import _fresh_as_of, _memory, _patch_plan, _write

    dest = tmp_path / "last_soko_trend.json"
    _patch_plan(monkeypatch, dest)
    _memory(monkeypatch, {"regime": "chop", "recorded_at": _fresh_as_of(hours=48)})
    monkeypatch.setattr("firm.llm.httpx.Client", _NoHttp)

    def plan_for(flag: str, label: str):
        _write(dest, {"trend": label, "as_of": _fresh_as_of()})
        monkeypatch.setenv("LLM_SEATS_ENABLED", flag)
        get_settings.cache_clear()
        plan = build_plan(require_approval=False, candidates=["BTCUSDT"])
        assert read_live_soko_trend(dest) == label
        assert plan.soko_trend == label
        return _fingerprint(plan)

    try:
        bull_on = plan_for("true", "bull")
        bull_off = plan_for("false", "bull")
        assert bull_on == bull_off
        _trend, entries, sitouts = bull_off
        entry_names = {row[0] for row in entries}
        sitout_names = {row[0] for row in sitouts}
        assert "orb_fail_reversion" in entry_names
        assert "week_open_reclaim" in entry_names
        assert "atr_channel_breakout" in sitout_names
        assert "mama_fama_cross" in sitout_names
        assert any("bull" in row[3] and "blocked" in row[3] for row in sitouts)

        chop_on = plan_for("true", "chop")
        chop_off = plan_for("false", "chop")
        assert chop_on == chop_off
        assert chop_off != bull_off
        _trend, chop_entries, chop_sitouts = chop_off
        chop_entry_names = {row[0] for row in chop_entries}
        chop_sitout_names = {row[0] for row in chop_sitouts}
        assert "atr_channel_breakout" in chop_entry_names
        assert "mama_fama_cross" in chop_sitout_names
    finally:
        get_settings.cache_clear()
