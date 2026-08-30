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
    # 1M in + 1M out at peak flash rates.
    assert cheap.cost_usd(1_000_000, 1_000_000) == 1.76
