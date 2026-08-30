"""
The LLM router: model selection, structured outputs, and a hard budget ceiling.

Every LLM call in the firm goes through `LlmRouter`. That single choke point is
what makes the $100-300/month budget enforceable rather than aspirational: cost
is metered per call into `llm_spend`, and the router refuses to spend past the
ceiling regardless of which employee is asking.

Three ideas do the real work here:

* **Tiers, not model names.** Employees request a capability tier (cheap /
  standard / strong / search). Which concrete model serves a tier is
  configuration, so a model deprecation is an env change rather than a code
  change. Provider model names churn constantly -- DeepSeek retired
  `deepseek-chat` in July 2026, xAI retired `grok-4-0709` in May 2026 -- so
  hardcoding them anywhere but here would be a maintenance trap.

* **Budget posture, not a single switch.** At 80% of budget the router silently
  downgrades non-essential agents to the cheap tier; at 100% it pauses
  everything except the two employees whose job is to notice things going wrong
  (Risk Officer and Ops Engineer). Losing observability to save $5 would be a
  bad trade.

* **Structured outputs.** Agents return Pydantic models, never free text. A
  malformed response gets exactly one repair attempt and is then a failure. An
  agent whose output cannot be parsed has not produced a decision, and guessing
  at its intent is worse than skipping it.

Costs are charged at each provider's *peak* rate. Under-estimating spend would
let the firm quietly overrun the ceiling, so the arithmetic is deliberately
pessimistic.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError
from sqlalchemy import func, select

from config.settings import get_settings
from core.db import session_scope
from firm.memory_models import LlmSpend

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class ModelTier(str, Enum):
    """Capability tiers employees can request.

    Assigned by cadence and stakes rather than by preference: an agent that runs
    hourly must be cheap or it dominates the budget, while one that runs weekly
    and decides what the firm trades should use the strongest model available.
    """

    CHEAP = "cheap"  # hourly agents: Regime, Ops, Risk Officer
    STANDARD = "standard"  # daily agents: Desk Head, Auditor, Portfolio Manager
    STRONG = "strong"  # weekly: Quant Researcher
    SEARCH = "search"  # Grok with live X/web access: Sentiment Analyst


class Provider(str, Enum):
    """Supported API surfaces. Both are OpenAI chat-completions compatible."""

    XAI = "xai"
    DEEPSEEK = "deepseek"


#: $5 per 1,000 tool calls for xAI's `x_search` / `web_search`, billed on top of
#: tokens. The Sentiment Analyst is the only employee that uses them, and it
#: batches the whole watchlist into one call precisely because of this.
SEARCH_TOOL_COST_USD = 0.005


@dataclass(frozen=True)
class ModelSpec:
    """A concrete model, its endpoint, and what it costs."""

    tier: ModelTier
    provider: Provider
    model: str
    input_per_mtok: float
    output_per_mtok: float
    #: Whether this model can search X and the web. Only xAI Grok can, which is
    #: why the Sentiment Analyst is pinned to the SEARCH tier.
    supports_search: bool = False

    def cost_usd(self, tokens_in: int, tokens_out: int, search_calls: int = 0) -> float:
        """Cost of one call. Peak rates, no cache-hit discount assumed."""
        return (
            tokens_in / 1_000_000 * self.input_per_mtok
            + tokens_out / 1_000_000 * self.output_per_mtok
            + search_calls * SEARCH_TOOL_COST_USD
        )


#: Default tier assignments, current as of August 2026. Every entry is
#: overridable through `.env` (e.g. `LLM_MODEL_STRONG=grok-4.6`) so a model
#: retirement never requires a code change.
DEFAULT_CATALOGUE: dict[ModelTier, ModelSpec] = {
    ModelTier.CHEAP: ModelSpec(
        tier=ModelTier.CHEAP,
        provider=Provider.DEEPSEEK,
        model="deepseek-v4-flash",
        input_per_mtok=0.44,
        output_per_mtok=1.32,
    ),
    ModelTier.STANDARD: ModelSpec(
        tier=ModelTier.STANDARD,
        provider=Provider.DEEPSEEK,
        model="deepseek-v4-pro",
        input_per_mtok=1.32,
        output_per_mtok=3.96,
    ),
    ModelTier.STRONG: ModelSpec(
        tier=ModelTier.STRONG,
        provider=Provider.XAI,
        model="grok-4.6",
        input_per_mtok=2.00,
        output_per_mtok=6.00,
    ),
    ModelTier.SEARCH: ModelSpec(
        tier=ModelTier.SEARCH,
        provider=Provider.XAI,
        # Grok 4.3 has a 1M context at half the flagship price, which suits a
        # single batched sweep over the whole watchlist.
        model="grok-4.3",
        input_per_mtok=1.25,
        output_per_mtok=2.50,
        supports_search=True,
    ),
}

PROVIDER_ENDPOINTS: dict[Provider, str] = {
    Provider.XAI: "https://api.x.ai/v1/chat/completions",
    Provider.DEEPSEEK: "https://api.deepseek.com/chat/completions",
}

#: Employees exempt from the budget pause. Both exist to detect problems; muting
#: them when spend runs high is exactly when it would hurt most.
ESSENTIAL_AGENTS = frozenset({"risk_officer", "ops_engineer"})

#: Fraction of budget at which non-essential agents are downgraded.
DEGRADE_AT = 0.80


class BudgetPosture(str, Enum):
    NORMAL = "normal"
    DEGRADED = "degraded"  # >= 80% spent: non-essential agents forced to CHEAP
    PAUSED = "paused"  # >= 100% spent: only essential agents may call


class LlmError(RuntimeError):
    """An LLM call failed in a way the caller must handle."""


class BudgetExhausted(LlmError):
    """The monthly ceiling blocks this call."""


@dataclass
class LlmResult:
    """One completed LLM call: its parsed output and what it cost."""

    content: str
    model: str
    tier: ModelTier
    tokens_in: int
    tokens_out: int
    cost_usd: float
    latency_ms: int
    parsed: BaseModel | None = None
    #: Source URLs returned by search-enabled calls, so sentiment claims are
    #: checkable rather than asserted.
    citations: list[str] = field(default_factory=list)


def billing_month(moment: datetime | None = None) -> str:
    """Current billing month as "YYYY-MM"."""
    return (moment or datetime.now(timezone.utc)).strftime("%Y-%m")


class BudgetGuard:
    """Tracks monthly LLM spend and decides what is still affordable."""

    def __init__(self, monthly_budget_usd: float | None = None) -> None:
        settings = get_settings()
        self.budget = monthly_budget_usd or settings.llm_monthly_budget_usd

    def month_to_date(self) -> float:
        """Total spend recorded for the current billing month."""
        with session_scope() as session:
            total = session.scalar(
                select(func.sum(LlmSpend.cost_usd)).where(
                    LlmSpend.billing_month == billing_month()
                )
            )
        return float(total or 0.0)

    def posture(self) -> BudgetPosture:
        spent = self.month_to_date()
        if spent >= self.budget:
            return BudgetPosture.PAUSED
        if spent >= self.budget * DEGRADE_AT:
            return BudgetPosture.DEGRADED
        return BudgetPosture.NORMAL

    def resolve(self, agent: str, tier: ModelTier) -> ModelTier:
        """Return the tier this agent may actually use right now.

        Raises:
            BudgetExhausted: when the agent may not call at all.
        """
        posture = self.posture()
        essential = agent in ESSENTIAL_AGENTS

        if posture is BudgetPosture.PAUSED and not essential:
            raise BudgetExhausted(
                f"monthly LLM budget of ${self.budget:.2f} is exhausted "
                f"(${self.month_to_date():.2f} spent); {agent} is paused until "
                "the next billing month or a budget increase"
            )

        # SEARCH is exempt from downgrade because no cheap model can read X.
        # Degrading it would not save money, it would silently change what the
        # output means.
        if posture is BudgetPosture.DEGRADED and not essential and tier not in (
            ModelTier.SEARCH,
            ModelTier.CHEAP,
        ):
            logger.warning(
                "Budget at %.0f%%: downgrading %s from %s to cheap.",
                self.month_to_date() / self.budget * 100, agent, tier.value,
            )
            return ModelTier.CHEAP

        return tier

    def record(
        self, agent: str, model: str, tokens_in: int, tokens_out: int, cost_usd: float
    ) -> None:
        """Persist the cost of one call."""
        with session_scope() as session:
            session.add(
                LlmSpend(
                    agent=agent,
                    model=model,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    cost_usd=cost_usd,
                    billing_month=billing_month(),
                )
            )

    def snapshot(self) -> dict[str, Any]:
        """Budget state for the dashboard."""
        spent = self.month_to_date()
        return {
            "billing_month": billing_month(),
            "budget_usd": round(self.budget, 2),
            "spent_usd": round(spent, 4),
            "remaining_usd": round(max(0.0, self.budget - spent), 4),
            "utilisation_pct": round(spent / self.budget * 100, 2) if self.budget else 0.0,
            "posture": self.posture().value,
        }


class LlmRouter:
    """Routes tier requests to concrete models, meters cost, parses outputs."""

    def __init__(
        self,
        catalogue: dict[ModelTier, ModelSpec] | None = None,
        budget: BudgetGuard | None = None,
        timeout: float = 120.0,
    ) -> None:
        self.settings = get_settings()
        self.catalogue = catalogue or self._catalogue_from_env()
        self.budget = budget or BudgetGuard()
        self._client = httpx.Client(timeout=timeout)

    @staticmethod
    def _catalogue_from_env() -> dict[ModelTier, ModelSpec]:
        """Apply `LLM_MODEL_<TIER>` overrides to the default catalogue."""
        catalogue = dict(DEFAULT_CATALOGUE)
        for tier, spec in DEFAULT_CATALOGUE.items():
            override = os.environ.get(f"LLM_MODEL_{tier.value.upper()}")
            if override and override != spec.model:
                logger.info("Tier %s overridden to %s", tier.value, override)
                catalogue[tier] = ModelSpec(
                    tier=spec.tier,
                    provider=spec.provider,
                    model=override,
                    input_per_mtok=spec.input_per_mtok,
                    output_per_mtok=spec.output_per_mtok,
                    supports_search=spec.supports_search,
                )
        return catalogue

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "LlmRouter":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    # -----------------------------------------------------------------
    # Credentials
    # -----------------------------------------------------------------
    def api_key_for(self, provider: Provider) -> str:
        if provider is Provider.XAI:
            return self.settings.xai_api_key
        return self.settings.deepseek_api_key

    def is_configured(self, tier: ModelTier) -> bool:
        """Whether a tier has credentials, so callers can degrade gracefully."""
        spec = self.catalogue.get(tier)
        return bool(spec and self.api_key_for(spec.provider))

    # -----------------------------------------------------------------
    # Completion
    # -----------------------------------------------------------------
    def complete(
        self,
        agent: str,
        system: str,
        user: str,
        response_model: type[T],
        tier: ModelTier = ModelTier.CHEAP,
        temperature: float = 0.2,
        max_tokens: int = 4_000,
        enable_search: bool = False,
        search_sources: list[dict[str, Any]] | None = None,
    ) -> LlmResult:
        """Run one structured completion.

        Args:
            agent: Employee name, for cost attribution and budget policy.
            system: System prompt. Should state the role and the output contract.
            user: The task payload.
            response_model: Pydantic model the reply must satisfy.
            tier: Requested capability tier; may be downgraded by the budget.
            temperature: Low by default -- these are analytical tasks, not
                creative ones, and reproducibility matters for auditing.
            max_tokens: Output cap.
            enable_search: Request live X/web search. Requires a search-capable
                model, and costs $5 per 1,000 calls on top of tokens.
            search_sources: xAI source filters, e.g. `[{"type": "x"}]`.

        Returns:
            An `LlmResult` whose `parsed` field holds the validated model.

        Raises:
            BudgetExhausted: the budget blocks this call.
            LlmError: no credentials, transport failure, or unparseable output.
        """
        effective_tier = self.budget.resolve(agent, tier)
        spec = self.catalogue[effective_tier]

        if enable_search and not spec.supports_search:
            raise LlmError(
                f"{agent} requested search but tier {effective_tier.value} "
                f"({spec.model}) cannot search. Use ModelTier.SEARCH."
            )

        api_key = self.api_key_for(spec.provider)
        if not api_key:
            raise LlmError(
                f"No API key for {spec.provider.value}. Set "
                f"{spec.provider.value.upper()}_API_KEY in .env."
            )

        schema = response_model.model_json_schema()
        messages = [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": (
                    f"{user}\n\n"
                    "Reply with a single JSON object matching this schema. "
                    "No prose, no markdown fences.\n"
                    f"{json.dumps(schema)}"
                ),
            },
        ]

        result = self._call(
            agent, spec, messages, temperature, max_tokens, enable_search, search_sources
        )

        parsed, error = self._parse(response_model, result.content)
        if error:
            logger.warning("%s: output failed validation; attempting one repair.", agent)
            messages.append({"role": "assistant", "content": result.content})
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "That response did not validate against the schema. "
                        f"Error: {error}. Reply with corrected JSON only."
                    ),
                }
            )
            retry = self._call(
                agent, spec, messages, temperature, max_tokens, enable_search, search_sources
            )
            parsed, still_failing = self._parse(response_model, retry.content)

            # The repair attempt costs money whether or not it worked, so fold
            # the first call's usage into the reported total.
            retry.cost_usd += result.cost_usd
            retry.tokens_in += result.tokens_in
            retry.tokens_out += result.tokens_out
            result = retry

            if still_failing:
                raise LlmError(
                    f"{agent}: output did not validate after repair: {still_failing}"
                )

        result.parsed = parsed
        return result

    def _call(
        self,
        agent: str,
        spec: ModelSpec,
        messages: list[dict[str, Any]],
        temperature: float,
        max_tokens: int,
        enable_search: bool,
        search_sources: list[dict[str, Any]] | None,
    ) -> LlmResult:
        """Issue one HTTP request, meter its cost, and return the raw content."""
        payload: dict[str, Any] = {
            "model": spec.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            # `json_object` rather than `json_schema`: it is supported by both
            # providers, and the response is validated against the Pydantic
            # model afterwards regardless.
            "response_format": {"type": "json_object"},
        }

        if enable_search:
            payload["search_parameters"] = {
                "mode": "on",
                "sources": search_sources or [{"type": "x"}],
                "return_citations": True,
            }

        started = time.perf_counter()
        try:
            response = self._client.post(
                PROVIDER_ENDPOINTS[spec.provider],
                headers={
                    "Authorization": f"Bearer {self.api_key_for(spec.provider)}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            body = response.json()
        except httpx.HTTPStatusError as exc:
            raise LlmError(
                f"{spec.provider.value} returned {exc.response.status_code}: "
                f"{exc.response.text[:400]}"
            ) from exc
        except Exception as exc:
            raise LlmError(f"{spec.provider.value} call failed: {exc}") from exc

        latency_ms = int((time.perf_counter() - started) * 1000)

        usage = body.get("usage") or {}
        tokens_in = int(usage.get("prompt_tokens", 0))
        tokens_out = int(usage.get("completion_tokens", 0))
        search_calls = int(usage.get("num_sources_used", 0)) if enable_search else 0

        choices = body.get("choices") or []
        if not choices:
            raise LlmError(f"{spec.provider.value} returned no choices")
        content = (choices[0].get("message") or {}).get("content") or ""

        cost = spec.cost_usd(tokens_in, tokens_out, search_calls)
        self.budget.record(agent, spec.model, tokens_in, tokens_out, cost)

        logger.info(
            "%s -> %s | %d in / %d out tokens | $%.5f | %d ms",
            agent, spec.model, tokens_in, tokens_out, cost, latency_ms,
        )

        return LlmResult(
            content=content,
            model=spec.model,
            tier=spec.tier,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=cost,
            latency_ms=latency_ms,
            citations=list(body.get("citations") or []),
        )

    @staticmethod
    def _parse(model: type[T], content: str) -> tuple[T | None, str]:
        """Validate `content` against `model`.

        Returns (parsed, "") on success or (None, error) on failure.
        """
        text = _strip_fences(content)
        try:
            return model.model_validate_json(text), ""
        except ValidationError as exc:
            return None, str(exc)[:500]
        except Exception as exc:
            return None, f"not valid JSON: {exc}"


def _strip_fences(content: str) -> str:
    """Remove markdown code fences some models add despite instructions."""
    text = content.strip()
    if not text.startswith("```"):
        return text
    lines = [line for line in text.splitlines() if not line.strip().startswith("```")]
    return "\n".join(lines).strip()


__all__ = [
    "BudgetExhausted",
    "BudgetGuard",
    "BudgetPosture",
    "LlmError",
    "LlmResult",
    "LlmRouter",
    "ModelSpec",
    "ModelTier",
    "Provider",
]
