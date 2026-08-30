"""
Ops Engineer: data-feed health, stale candles, API errors, hung agent runs.

Hourly, cheap model, and exempt from the budget pause -- losing observability
when spend is high is exactly when it would hurt most. Most of the checks are
deterministic; the LLM writes the human-readable diagnosis and decides whether
to escalate.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from pydantic import Field
from sqlalchemy import select

from core.data.ohlcv import BybitOHLCV
from core.db import session_scope
from core.risk.killswitch import KillSwitch
from firm.llm import ModelTier
from firm.memory_models import AgentRun, RunStatus
from firm.runtime import Agent, AgentOutput, Cadence


class OpsReport(AgentOutput):
    """Health diagnosis for the current cycle."""

    overall: str = Field(description="One of: healthy, degraded, down.")
    issues: list[str] = Field(default_factory=list)
    escalate: bool = Field(default=False, description="True if a human must look.")
    escalate_title: str = Field(default="")


class OpsEngineer(Agent):
    name = "ops_engineer"
    role = "Ops Engineer"
    cadence = Cadence.HOURLY
    tier = ModelTier.CHEAP
    prompt_version = "v1"
    output_model = OpsReport
    max_tokens = 1_000

    def system_prompt(self) -> str:
        return (
            "You are the Ops Engineer of a systematic crypto trading firm. You "
            "read a list of deterministic health checks and produce a concise "
            "diagnosis. Escalate only when something needs a human: a tripped "
            "kill switch, a dead data feed, hung agent runs, or repeated "
            "failures. Do not escalate a single transient warning."
        )

    def gather(self) -> dict[str, Any]:
        checks: list[dict[str, Any]] = []
        now = datetime.now(timezone.utc)

        kill = KillSwitch().read()
        checks.append(
            {
                "name": "kill_switch",
                "ok": not kill.is_tripped,
                "detail": f"{kill.reason.value}: {kill.detail}" if kill.is_tripped else "clear",
            }
        )

        with BybitOHLCV() as source:
            healthy, message = _probe_feed(source)
        checks.append({"name": "bybit_public_feed", "ok": healthy, "detail": message})

        hung_cutoff = now - timedelta(minutes=20)
        with session_scope() as session:
            hung = session.scalars(
                select(AgentRun).where(
                    AgentRun.status == RunStatus.RUNNING.value,
                    AgentRun.started_at < hung_cutoff,
                )
            ).all()
            recent_failures = session.scalars(
                select(AgentRun)
                .where(AgentRun.status == RunStatus.FAILED.value)
                .order_by(AgentRun.started_at.desc())
                .limit(8)
            ).all()

        checks.append(
            {
                "name": "hung_agent_runs",
                "ok": not hung,
                "detail": (
                    f"{len(hung)} runs still 'running' after 20 minutes: "
                    + ", ".join(f"{r.agent}#{r.id}" for r in hung)
                    if hung
                    else "none"
                ),
            }
        )
        checks.append(
            {
                "name": "recent_failures",
                "ok": len(recent_failures) < 3,
                "detail": [
                    {"agent": r.agent, "error": r.error[:160], "when": r.started_at.isoformat()}
                    for r in recent_failures
                ],
            }
        )

        return {"checks": checks, "as_of": now.isoformat()}

    def task_prompt(self, inputs: dict[str, Any]) -> str:
        return f"Diagnose firm health from these checks.\n{inputs}"

    def on_output(self, output: AgentOutput, inputs: dict[str, Any], run_id: int) -> list[int]:
        del inputs, run_id
        report = OpsReport.model_validate(output.model_dump())
        if report.escalate:
            self.escalate(
                report.escalate_title or f"Ops: firm is {report.overall}",
                report.reasoning + "\n" + "\n".join(report.issues),
                severity="critical" if report.overall == "down" else "warning",
            )
        return []


def _probe_feed(source: BybitOHLCV) -> tuple[bool, str]:
    """Cheap liveness check against the public ticker."""
    price = source.latest_price("BTCUSDT")
    if price is None or price <= 0:
        return False, "BTCUSDT ticker returned no price"
    candles = source.fetch_latest("BTCUSDT", "15m", bars=3)
    if candles.empty:
        return False, "no 15m candles for BTCUSDT"
    age = datetime.now(timezone.utc) - candles.index[-1].to_pydatetime()
    if age > timedelta(minutes=45):
        return False, f"newest 15m candle is {age} old"
    return True, f"BTCUSDT {price:.2f}, newest bar {age} ago"
