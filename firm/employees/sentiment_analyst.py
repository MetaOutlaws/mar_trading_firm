"""
Sentiment Analyst: Crypto Twitter narrative.

Primary feed is Luke's file snapshot (`data/last_sentiment.json`), which the
desk reads directly — no X API key and no XAI_API_KEY on the paper box.

This employee is the optional xAI Grok search fallback: it only spends search
budget when the Luke file is missing or older than 30 minutes *and* an xAI key
is configured. Until forward-return validation exists, trust stays at L1.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from pydantic import Field

from config.universe import get_universe
from core.data.ohlcv import BybitOHLCV
from core.data.sentiment import load_last_sentiment, snapshot_is_fresh
from firm import memory
from firm.llm import ModelTier
from firm.memory_models import ProposalKind, RunStatus
from firm.runtime import Agent, AgentOutput, AgentResult, Cadence

logger = logging.getLogger(__name__)


class AssetSentiment(AgentOutput):
    """One symbol's reading. Score is the only field later statistical tests use."""

    symbol: str
    score: float = Field(ge=-1.0, le=1.0, description="-1 bearish .. +1 bullish.")
    hype_stage: str = Field(
        description="One of: building, peaking, exhausted, fading, absent."
    )
    narrative: str = Field(default="")
    sources: list[str] = Field(default_factory=list)


class SentimentSweep(AgentOutput):
    """Batched reading across the watchlist."""

    market_narrative: str = Field(description="The dominant story on X right now.")
    readings: list[AssetSentiment]


class SentimentAnalyst(Agent):
    name = "sentiment_analyst"
    role = "Sentiment Analyst"
    cadence = Cadence.FOUR_HOURLY
    tier = ModelTier.SEARCH
    prompt_version = "v1"
    output_model = SentimentSweep
    uses_search = True
    max_tokens = 4_000

    #: Majors first: they have the most X coverage, so the reading is least
    #: likely to be a handful of shill accounts.
    WATCHLIST = [
        "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
        "DOGEUSDT", "AVAXUSDT", "LINKUSDT",
    ]

    def system_prompt(self) -> str:
        return (
            "You are the Sentiment Analyst of a systematic crypto trading firm. "
            "Search recent posts on X about the listed assets. Score each from "
            "-1 (maximally bearish) to +1 (maximally bullish). Distinguish hype "
            "from exhaustion: a crowded long that everyone is already in is "
            "'peaking' or 'exhausted', not 'building'. Cite the posts you used. "
            "Do not recommend trades. If there is no meaningful discussion of an "
            "asset, say so with hype_stage=absent and score near 0."
        )

    def gather(self) -> dict[str, Any]:
        universe = get_universe()
        symbols = [s for s in self.WATCHLIST if s in universe.monitored_symbols]
        prices: dict[str, float] = {}
        with BybitOHLCV() as source:
            for symbol in symbols:
                price = source.latest_price(symbol)
                if price:
                    prices[symbol] = price
        return {
            "symbols": symbols,
            "prices": prices,
            "prior": memory.latest_sentiment(limit=len(symbols)),
        }

    def task_prompt(self, inputs: dict[str, Any]) -> str:
        symbols = ", ".join(inputs.get("symbols") or self.WATCHLIST)
        return (
            f"Score current X sentiment for: {symbols}. "
            "One reading per symbol. Include source URLs."
        )

    def run(self) -> AgentResult:
        """Skip xAI when Luke's snapshot is fresh, or when no search key exists."""
        blob = load_last_sentiment()
        if snapshot_is_fresh(blob):
            error = (
                "Skipped: Luke CT snapshot is fresh. "
                "xAI search is a fallback only."
            )
            run_id = memory.start_run(
                self.name, self.role, self.describe_task({}), prompt_version=self.prompt_version
            )
            memory.finish_run(run_id, RunStatus.SKIPPED, error=error)
            logger.info("%s %s", self.name, error)
            return AgentResult(
                agent=self.name, status=RunStatus.SKIPPED, run_id=run_id, error=error
            )
        if self.tier and not self.router.is_configured(self.tier):
            error = (
                "Skipped: no fresh data/last_sentiment.json and no XAI_API_KEY. "
                "The Sentiment tab reads Luke's file; paper does not need xAI."
            )
            run_id = memory.start_run(
                self.name, self.role, self.describe_task({}), prompt_version=self.prompt_version
            )
            memory.finish_run(run_id, RunStatus.SKIPPED, error=error)
            logger.info("%s %s", self.name, error)
            return AgentResult(
                agent=self.name, status=RunStatus.SKIPPED, run_id=run_id, error=error
            )
        return super().run()

    def on_output(self, output: AgentOutput, inputs: dict[str, Any], run_id: int) -> list[int]:
        sweep = SentimentSweep.model_validate(output.model_dump())
        prices = inputs.get("prices") or {}
        ids: list[int] = []
        for reading in sweep.readings:
            memory.record_sentiment(
                symbol=reading.symbol,
                score=reading.score,
                narrative=reading.narrative,
                hype_stage=reading.hype_stage,
                confidence=reading.confidence,
                sources=reading.sources,
                model="grok-search",
                price_at_reading=float(prices.get(reading.symbol, 0.0)),
            )
            ids.append(
                self.propose(
                    kind=ProposalKind.TRADE,
                    title=f"{reading.symbol} sentiment {reading.score:+.2f} ({reading.hype_stage})",
                    payload=reading.model_dump(),
                    rationale=reading.narrative or sweep.market_narrative,
                    confidence=reading.confidence,
                    run_id=run_id,
                    symbol=reading.symbol,
                    ttl=timedelta(hours=6),
                )
            )
        return ids
