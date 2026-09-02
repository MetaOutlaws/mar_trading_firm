"""
Regime Analyst: classifies the current market so the rest of the firm can react.

Hourly, cheap model. The classification is a *gate*, not a trade: it decides
which strategy families are appropriate (trend-following longs in a bull,
mean-reversion in chop, shorts in a bear) and writes a snapshot the Portfolio
Manager and Desk Head read later.

The metrics themselves are computed deterministically from BTC daily candles.
The LLM's job is the judgement call -- "is this a late-stage bull or a new
chop?" -- which the numbers alone cannot make. If the LLM is unavailable the
deterministic metrics still get recorded, so the firm is never blind.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import numpy as np
from pydantic import Field

from core.data.ohlcv import BybitOHLCV
from config.pipeline import APPROVED_RESEARCH_SYMBOLS
from firm import memory
from firm.llm import ModelTier
from firm.runtime import Agent, AgentOutput, Cadence


class RegimeOutput(AgentOutput):
    """Structured regime classification."""

    regime: str = Field(description="One of: bull, bear, chop.")
    volatility_bucket: str = Field(description="One of: low, normal, high.")
    btc_trend: str = Field(description="One of: up, down, sideways.")
    permitted_strategies: list[str] = Field(
        description="Strategy families appropriate for this regime."
    )
    caution: str = Field(
        default="",
        description="Anything the rest of the firm should treat carefully.",
    )


class RegimeAnalyst(Agent):
    name = "regime_analyst"
    role = "Regime Analyst"
    cadence = Cadence.HOURLY
    tier = ModelTier.CHEAP
    prompt_version = "v2"
    output_model = RegimeOutput
    max_tokens = 1_200

    def system_prompt(self) -> str:
        return (
            "You are the Regime Analyst of a systematic crypto trading firm. "
            "You classify the current Bitcoin-led market into bull / bear / chop "
            "and a volatility bucket. Be conservative: when the evidence is mixed, "
            "choose chop. Do not recommend trades. Do not invent numbers -- use "
            "only the metrics provided. permitted_strategies must be drawn from: "
            "trend_long, pullback_long, mean_reversion, fade_rally_short, "
            "trend_short. In a bull prefer trend_long and pullback_long; in a "
            "bear prefer trend_short; in chop prefer mean_reversion and be "
            "sceptical of both trend families."
        )

    def describe_task(self, inputs: dict[str, Any]) -> str:
        metrics = inputs.get("metrics") or {}
        return (
            f"Classify regime: 30d {metrics.get('return_30d_pct', '?')}%, "
            f"vol {metrics.get('vol_30d_ann_pct', '?')}%"
        )

    def gather(self) -> dict[str, Any]:
        with BybitOHLCV() as source:
            daily = source.fetch_latest("BTCUSDT", "1d", bars=120)
            hourly = source.fetch_latest("BTCUSDT", "1h", bars=48)

        if daily.empty or len(daily) < 30:
            raise RuntimeError("not enough BTC daily candles to classify the regime")

        close = daily["close"]
        ret_7 = float(close.iloc[-1] / close.iloc[-8] - 1.0) if len(close) >= 8 else 0.0
        ret_30 = float(close.iloc[-1] / close.iloc[-31] - 1.0) if len(close) >= 31 else 0.0
        ret_90 = float(close.iloc[-1] / close.iloc[-91] - 1.0) if len(close) >= 91 else 0.0

        daily_rets = close.pct_change().dropna()
        vol_30 = float(daily_rets.tail(30).std() * np.sqrt(365)) if len(daily_rets) >= 10 else 0.0

        ema50 = float(close.ewm(span=50, adjust=False).mean().iloc[-1])
        ema200 = float(close.ewm(span=200, adjust=False).mean().iloc[-1]) if len(close) >= 200 else ema50
        last = float(close.iloc[-1])

        hourly_range = 0.0
        if not hourly.empty:
            hourly_range = float(
                (hourly["high"].tail(24).max() - hourly["low"].tail(24).min()) / last
            )

        metrics = {
            "btc_price": last,
            "return_7d_pct": round(ret_7 * 100, 2),
            "return_30d_pct": round(ret_30 * 100, 2),
            "return_90d_pct": round(ret_90 * 100, 2),
            "vol_30d_ann_pct": round(vol_30 * 100, 1),
            "price_vs_ema50_pct": round((last / ema50 - 1.0) * 100, 2) if ema50 else 0.0,
            "price_vs_ema200_pct": round((last / ema200 - 1.0) * 100, 2) if ema200 else 0.0,
            "ema50_above_ema200": ema50 > ema200,
            "range_24h_pct": round(hourly_range * 100, 2),
            "as_of": datetime.now(timezone.utc).isoformat(),
        }

        # Positioning is a *context* for the classification, not a trade. Fail
        # open if Bybit is unreachable so a dead OI feed cannot blind the desk.
        try:
            from core.data.positioning import snapshot_symbols

            blob = snapshot_symbols(
                list(APPROVED_RESEARCH_SYMBOLS), include_cross=True
            )
            symbols = blob.get("symbols") if isinstance(blob, dict) else {}
            btc_pos = (symbols or {}).get("BTCUSDT") or {}
            metrics["btc_oi_change_24h_pct"] = btc_pos.get("oi_change_24h_pct")
            metrics["btc_funding_rate_8h_pct"] = btc_pos.get("funding_rate_8h_pct")
            metrics["btc_buy_ratio"] = btc_pos.get("buy_ratio")
            metrics["btc_positioning"] = btc_pos.get("label")
            cross = blob.get("cross") if isinstance(blob, dict) else {}
            if isinstance(cross, dict):
                metrics["eth_btc"] = cross.get("eth_btc")
                metrics["eth_btc_7d_pct"] = cross.get("eth_btc_7d_pct")
        except Exception:
            metrics["positioning_error"] = "unavailable"

        return {"metrics": metrics}

    def task_prompt(self, inputs: dict[str, Any]) -> str:
        return (
            "Classify the current crypto market regime from these BTC metrics. "
            "Open interest, funding, account long/short, and ETH/BTC are crowding "
            "context only — do not invent a trade from them. High positive funding "
            "plus rising OI is a crowded long; the mirror is a crowded short. "
            f"{inputs['metrics']}"
        )

    def on_output(self, output: AgentOutput, inputs: dict[str, Any], run_id: int) -> list[int]:
        del run_id
        parsed = output if isinstance(output, RegimeOutput) else RegimeOutput.model_validate(
            output.model_dump()
        )
        metrics = inputs.get("metrics") or {}
        memory.record_regime(
            regime=parsed.regime,
            volatility_bucket=parsed.volatility_bucket,
            btc_trend=parsed.btc_trend,
            permitted_strategies=parsed.permitted_strategies,
            reasoning=parsed.reasoning,
            confidence=parsed.confidence,
            metrics=metrics,
        )
        return []
