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
    """Supported API surfaces. All four expose an OpenAI chat-completions path."""

    XAI = "xai"
    OPENAI = "openai"
    DEEPSEEK = "deepseek"
    GEMINI = "gemini"


#: $5 per 1,000 tool calls for xAI's `x_search` / `web_search`, billed on top of
#: tokens. The Sentiment Analyst is the only employee that uses them, and it
#: batches the whole watchlist into one call precisely because of this.
SEARCH_TOOL_COST_USD = 0.005

# After a socket timeout, do not immediately retry that same model — the hang
# already cost 3–5 minutes, and a second wait freezes paper + research. Cool
# the model for ten minutes so Quant/Desk Head skip while Flash-Lite (Ops)
# can still run. Walk-forward does not wait on Gemini.
PROVIDER_TIMEOUT_COOLDOWN_SEC = 600.0
_model_open_until: dict[str, float] = {}


def _model_key(provider: Provider | str, model: str) -> str:
    name = provider.value if isinstance(provider, Provider) else str(provider)
    return f"{name}:{model}"


def reset_model_cooldowns() -> None:
    """Tests only: forget live timeout trips."""
    _model_open_until.clear()


def trip_model_timeout(
    provider: Provider | str,
    model: str,
    *,
    seconds: float | None = None,
) -> None:
    """Stop calling this model until the cooldown elapses."""
    wait = PROVIDER_TIMEOUT_COOLDOWN_SEC if seconds is None else float(seconds)
    _model_open_until[_model_key(provider, model)] = time.monotonic() + wait


def model_cooldown_remaining(provider: Provider | str, model: str) -> float:
    until = _model_open_until.get(_model_key(provider, model), 0.0)
    return max(0.0, until - time.monotonic())


def clear_model_timeout(provider: Provider | str, model: str) -> None:
    _model_open_until.pop(_model_key(provider, model), None)


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
#: overridable through `.env` (e.g. `LLM_MODEL_STRONG=gemini-3.6-flash`) so a
#: model retirement never requires a code change. Paid Gemini quota (not the
#: 20 RPD free-tier metric) is what employees use.
DEFAULT_CATALOGUE: dict[ModelTier, ModelSpec] = {
    ModelTier.CHEAP: ModelSpec(
        tier=ModelTier.CHEAP,
        provider=Provider.GEMINI,
        # Highest RPD on the paid Flash-Lite row (150K/day in AI Studio).
        model="gemini-3.5-flash-lite",
        input_per_mtok=0.30,
        output_per_mtok=2.50,
    ),
    ModelTier.STANDARD: ModelSpec(
        tier=ModelTier.STANDARD,
        provider=Provider.GEMINI,
        model="gemini-3.5-flash",
        input_per_mtok=1.50,
        output_per_mtok=9.00,
    ),
    ModelTier.STRONG: ModelSpec(
        tier=ModelTier.STRONG,
        provider=Provider.GEMINI,
        # 3.6 Flash is listed on the paid dashboard but returns empty content
        # on the OpenAI-compat JSON path. 3.7 Flash JSON-works, then 503s.
        # Stay on 3.5 Flash until those are stable; override via env.
        model="gemini-3.5-flash",
        input_per_mtok=1.50,
        output_per_mtok=9.00,
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
    Provider.OPENAI: "https://api.openai.com/v1/chat/completions",
    Provider.DEEPSEEK: "https://api.deepseek.com/chat/completions",
    # OpenAI-compatible Gemini surface. Same JSON contract as the others, so
    # employees do not need a second request path.
    Provider.GEMINI: "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
}

#: Employees exempt from the budget pause. Both exist to detect problems; muting
#: them when spend runs high is exactly when it would hurt most.
ESSENTIAL_AGENTS = frozenset({"risk_officer", "ops_engineer"})

#: Fraction of budget at which non-essential agents are downgraded.
DEGRADE_AT = 0.80


def _key_status(key: str) -> dict[str, Any]:
    """Whether a secret is present. Returns a prefix only — never the key."""
    token = (key or "").strip()
    if not token:
        return {"configured": False}
    if token.startswith("sk-proj"):
        prefix = "sk-proj"
    elif token.startswith("AQ."):
        prefix = "AQ."
    elif token.startswith("AIza"):
        prefix = "AIza"
    else:
        prefix = "set"
    return {"configured": True, "prefix": prefix}


def _key_for(settings: Any, provider: Provider) -> str:
    if provider is Provider.XAI:
        return settings.xai_api_key
    if provider is Provider.OPENAI:
        return settings.openai_api_key
    if provider is Provider.GEMINI:
        return settings.gemini_api_key
    return settings.deepseek_api_key


def provider_status(
    settings: Any | None = None,
    catalogue: dict[ModelTier, ModelSpec] | None = None,
) -> dict[str, Any]:
    """Desk-safe snapshot of which LLM seats can actually run."""
    settings = settings or get_settings()
    catalogue = catalogue or dict(DEFAULT_CATALOGUE)
    return {
        "providers": {
            "openai": _key_status(settings.openai_api_key),
            "gemini": _key_status(settings.gemini_api_key),
            "xai": _key_status(settings.xai_api_key),
            "deepseek": _key_status(settings.deepseek_api_key),
        },
        "tiers": [
            {
                "tier": spec.tier.value,
                "provider": spec.provider.value,
                "model": spec.model,
                "configured": bool(_key_for(settings, spec.provider)),
                "supports_search": spec.supports_search,
            }
            for spec in catalogue.values()
        ],
    }


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
        timeout: float = 180.0,
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
        # Search stays on xAI. Every other employee seat rides Gemini so a
        # leftover OpenAI/DeepSeek override cannot skip the floor after a
        # provider swap.
        remapped: dict[ModelTier, ModelSpec] = {}
        for tier, spec in catalogue.items():
            if spec.supports_search:
                remapped[tier] = spec
                continue
            if spec.provider in (Provider.OPENAI, Provider.DEEPSEEK):
                remapped[tier] = DEFAULT_CATALOGUE[tier]
                logger.info(
                    "Remapped %s tier %s onto Gemini %s",
                    spec.provider.value,
                    tier.value,
                    remapped[tier].model,
                )
            else:
                remapped[tier] = spec
        return remapped

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
        return _key_for(self.settings, provider)

    def is_configured(self, tier: ModelTier) -> bool:
        """Whether a tier has credentials, so callers can degrade gracefully."""
        spec = self.catalogue.get(tier)
        return bool(spec and self.api_key_for(spec.provider))

    def credential_snapshot(self) -> dict[str, Any]:
        """Provider/tier status for the desk. Never includes the key itself."""
        return provider_status(self.settings, self.catalogue)

    def ping(self, provider: Provider) -> dict[str, Any]:
        """Prove employees can actually call this provider.

        `/v1/models` can succeed on an account with a valid key and $0 credit.
        Employees use chat completions, so that is what we probe — one token.
        """
        api_key = self.api_key_for(provider)
        if not api_key:
            return {"ok": False, "provider": provider.value, "detail": "no API key in .env"}
        spec = next((s for s in self.catalogue.values() if s.provider is provider), None)
        model = spec.model if spec else (
            "gemini-3.5-flash-lite" if provider is Provider.GEMINI else "gpt-4o-mini"
        )
        payload: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 8,
        }
        if provider is Provider.GEMINI and "lite" not in model:
            payload["reasoning_effort"] = "none"
        try:
            response = self._client.post(
                PROVIDER_ENDPOINTS[provider],
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        except Exception as exc:
            return {"ok": False, "provider": provider.value, "detail": str(exc)[:240]}
        if response.status_code == 200:
            return {
                "ok": True,
                "provider": provider.value,
                "detail": f"chat completions ok ({model})",
            }
        body = response.text[:240]
        try:
            parsed = response.json()
            body = str((parsed.get("error") or {}).get("message") or body)
        except Exception:
            pass
        return {
            "ok": False,
            "provider": provider.value,
            "detail": f"HTTP {response.status_code}: {body}",
        }

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

        # 3.5 Flash (not Lite) needs this so thinking does not leak into JSON.
        # 3.6 Flash rejects the field (400). Lite rejects it too.
        if spec.provider is Provider.GEMINI and spec.model.startswith("gemini-3.5-flash") and "lite" not in spec.model:
            payload["reasoning_effort"] = "none"

        if enable_search:
            payload["search_parameters"] = {
                "mode": "on",
                "sources": search_sources or [{"type": "x"}],
                "return_citations": True,
            }

        cooling = model_cooldown_remaining(spec.provider, spec.model)
        if cooling > 0:
            raise LlmError(
                f"{spec.provider.value} skipped: {spec.model} cooling down "
                f"{int(cooling)}s after timeout. Research walk-forward does not wait."
            )

        started = time.perf_counter()
        body: dict[str, Any] | None = None
        # Retry once on 429/503. Do not retry a socket timeout: that doubles a
        # 3–5 minute hang and is what froze the duty board on Gemini outages.
        for attempt in range(2):
            try:
                response = self._client.post(
                    PROVIDER_ENDPOINTS[spec.provider],
                    headers={
                        "Authorization": f"Bearer {self.api_key_for(spec.provider)}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    # Quant / Desk Head send large prompts; Gemini often needs
                    # more than the default 180s socket or both retry attempts fail.
                    timeout=300.0 if spec.tier is ModelTier.STRONG else 180.0,
                )
                response.raise_for_status()
                body = response.json()
                break
            except httpx.HTTPStatusError as exc:
                retryable = exc.response.status_code in {429, 503} and attempt == 0
                if retryable:
                    logger.warning(
                        "%s %s returned 429 for %s; retrying once",
                        spec.provider.value,
                        spec.model,
                        agent,
                    )
                    time.sleep(2.0)
                    continue
                raise LlmError(
                    f"{spec.provider.value} returned {exc.response.status_code}: "
                    f"{exc.response.text[:400]}"
                ) from exc
            except httpx.TimeoutException as exc:
                trip_model_timeout(spec.provider, spec.model)
                logger.warning(
                    "%s %s timed out for %s; cooling %ss (no immediate retry)",
                    spec.provider.value,
                    spec.model,
                    agent,
                    int(PROVIDER_TIMEOUT_COOLDOWN_SEC),
                )
                raise LlmError(f"{spec.provider.value} call failed: {exc}") from exc
            except Exception as exc:
                raise LlmError(f"{spec.provider.value} call failed: {exc}") from exc
        if body is None:
            raise LlmError(f"{spec.provider.value} call failed: empty response")
        clear_model_timeout(spec.provider, spec.model)

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
    "PROVIDER_TIMEOUT_COOLDOWN_SEC",
    "Provider",
    "clear_model_timeout",
    "model_cooldown_remaining",
    "provider_status",
    "reset_model_cooldowns",
    "trip_model_timeout",
]
