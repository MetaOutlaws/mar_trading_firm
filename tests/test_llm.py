"""Budget guard: the monthly ceiling is a hard stop, not a suggestion."""

from __future__ import annotations

from firm.llm import BudgetExhausted, BudgetGuard, BudgetPosture, ModelTier
from firm.memory_models import LlmSpend
from core.db import session_scope
from firm.llm import billing_month


def _spend(usd: float, agent: str = "desk_head") -> None:
    with session_scope() as session:
        session.add(
            LlmSpend(
                agent=agent,
                model="test",
                tokens_in=100,
                tokens_out=50,
                cost_usd=usd,
                billing_month=billing_month(),
            )
        )


def test_normal_posture_under_80_percent(firm_db) -> None:
    guard = BudgetGuard(monthly_budget_usd=100.0)
    _spend(10.0)
    assert guard.posture() is BudgetPosture.NORMAL
    assert guard.resolve("desk_head", ModelTier.STANDARD) is ModelTier.STANDARD


def test_degrades_non_essential_at_80_percent(firm_db) -> None:
    guard = BudgetGuard(monthly_budget_usd=100.0)
    _spend(80.0)
    assert guard.posture() is BudgetPosture.DEGRADED
    assert guard.resolve("desk_head", ModelTier.STANDARD) is ModelTier.CHEAP
    # Essential agents keep their requested tier.
    assert guard.resolve("risk_officer", ModelTier.STANDARD) is ModelTier.STANDARD
    # Search is not silently replaced with a model that cannot read X.
    assert guard.resolve("sentiment_analyst", ModelTier.SEARCH) is ModelTier.SEARCH


def test_pause_blocks_everyone_except_ops_and_risk(firm_db) -> None:
    guard = BudgetGuard(monthly_budget_usd=100.0)
    _spend(100.0)
    assert guard.posture() is BudgetPosture.PAUSED
    try:
        guard.resolve("desk_head", ModelTier.CHEAP)
        raise AssertionError("non-essential agent should have been paused")
    except BudgetExhausted:
        pass
    assert guard.resolve("ops_engineer", ModelTier.CHEAP) is ModelTier.CHEAP
    assert guard.resolve("risk_officer", ModelTier.CHEAP) is ModelTier.CHEAP


def test_model_cost_uses_peak_rates() -> None:
    from firm.llm import DEFAULT_CATALOGUE

    cheap = DEFAULT_CATALOGUE[ModelTier.CHEAP]
    # 1M in + 1M out at gemini-3.5-flash-lite peak rates.
    assert cheap.cost_usd(1_000_000, 1_000_000) == 2.80


def test_cheap_standard_strong_use_gemini() -> None:
    """Employee seats route through Gemini after OpenAI ran out of credit."""
    from firm.llm import DEFAULT_CATALOGUE, Provider

    for tier in (ModelTier.CHEAP, ModelTier.STANDARD, ModelTier.STRONG):
        spec = DEFAULT_CATALOGUE[tier]
        assert spec.provider is Provider.GEMINI
        assert spec.model.startswith("gemini-")
    search = DEFAULT_CATALOGUE[ModelTier.SEARCH]
    assert search.provider.value == "xai"
    assert search.supports_search


def test_provider_status_never_leaks_the_key(monkeypatch) -> None:
    from config.settings import get_settings
    from firm.llm import provider_status

    monkeypatch.setenv("GEMINI_API_KEY", "AQ.UNITTEST-SECRET-SHOULD-NOT-LEAK")
    get_settings.cache_clear()
    snap = provider_status()
    blob = str(snap)
    assert "UNITTEST-SECRET" not in blob
    assert snap["providers"]["gemini"]["configured"] is True
    assert snap["providers"]["gemini"]["prefix"] == "AQ."
    cheap = next(t for t in snap["tiers"] if t["tier"] == "cheap")
    assert cheap["provider"] == "gemini"
    assert cheap["configured"] is True
    get_settings.cache_clear()


def test_timeout_trips_cooldown_without_retry(monkeypatch) -> None:
    """A Gemini socket timeout must not wait a second 5-minute attempt."""
    import httpx

    from firm.llm import (
        LlmError,
        LlmRouter,
        ModelTier,
        Provider,
        model_cooldown_remaining,
        reset_model_cooldowns,
    )

    reset_model_cooldowns()
    router = LlmRouter()
    calls = {"n": 0}

    def boom(*args, **kwargs):
        calls["n"] += 1
        raise httpx.TimeoutException("The read operation timed out")

    monkeypatch.setattr(router._client, "post", boom)
    monkeypatch.setattr(router, "api_key_for", lambda provider: "test-key")
    spec = router.catalogue[ModelTier.STRONG]
    try:
        router._call("quant_researcher", spec, [], 0.2, 100, False, None)
        raise AssertionError("expected LlmError")
    except LlmError as exc:
        assert "timed out" in str(exc).lower()
    assert calls["n"] == 1
    assert model_cooldown_remaining(Provider.GEMINI, spec.model) > 0

    try:
        router._call("desk_head", spec, [], 0.2, 100, False, None)
        raise AssertionError("expected cooldown skip")
    except LlmError as exc:
        assert "cooling down" in str(exc)
    assert calls["n"] == 1

    lite = router.catalogue[ModelTier.CHEAP]
    assert lite.model != spec.model
    try:
        router._call("ops_engineer", lite, [], 0.2, 100, False, None)
        raise AssertionError("lite should still attempt HTTP")
    except LlmError:
        pass
    assert calls["n"] == 2
    reset_model_cooldowns()


def test_orchestrator_skips_cooling_flash_not_lite(monkeypatch) -> None:
    """Desk Head / Quant extra-due must not re-hang Flash while Ops Lite still runs."""
    from datetime import datetime, timezone

    from firm.llm import Provider, reset_model_cooldowns, trip_model_timeout
    from firm.orchestrator import Orchestrator

    reset_model_cooldowns()
    monkeypatch.setattr("firm.research_jobs.quant_should_run_now", lambda: True)
    monkeypatch.setattr("firm.accountability.gm_should_run_now", lambda last: True)
    monkeypatch.setattr("firm.accountability.advisor_should_run_now", lambda last: False)
    monkeypatch.setattr("firm.accountability.ops_should_run_now", lambda last: True)
    monkeypatch.setattr("firm.accountability.sleeve_engineer_should_run_now", lambda last: False)
    orch = Orchestrator()
    flash = orch.router.catalogue[orch.employee("quant_researcher").tier]
    trip_model_timeout(Provider.GEMINI, flash.model, seconds=600)
    due_names = {e.name for e in orch.due(datetime.now(timezone.utc))}
    assert "quant_researcher" not in due_names
    assert "desk_head" not in due_names
    assert "ops_engineer" in due_names
    reset_model_cooldowns()
    orch.close()
