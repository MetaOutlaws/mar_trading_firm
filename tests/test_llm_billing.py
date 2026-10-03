"""Provider billing pause: 402 stops the retry storm and does not stop paper.

A Gemini payment-required response must mark the seat degraded, alarm that
the fault is billing, and refuse to swap models. The pause is not permanent:
one later successful call on that same provider clears that seat. Paper
fills and exit polling do not consult the pause.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx

from config.settings import get_settings
from core.execution.paper import PaperBroker
from firm.llm import (
    LlmError,
    LlmRouter,
    ModelTier,
    Provider,
    billing_degraded_seats,
    is_billing_failure_text,
    mark_seat_billing_degraded,
    open_billing_probe_window,
    reset_billing_pauses,
    seat_shows_billing_degraded,
    trip_provider_billing,
)
from firm.memory_models import RunStatus
from firm.runtime import Agent, AgentResult
from scripts.run_paper_trading import execute_paper_cycle, wait_for_next_cycle

APPROVALS = Path("config/approved_strategies.json")


def _approvals_digest() -> str:
    return hashlib.sha256(APPROVALS.read_bytes()).hexdigest()


def _http_402(url: str) -> httpx.Response:
    return httpx.Response(
        402,
        text='{"error":{"message":"Your prepaid credits are depleted. Payment required."}}',
        request=httpx.Request("POST", url),
    )


def _http_200(url: str, content: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "choices": [{"message": {"content": content}}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 2},
        },
        request=httpx.Request("POST", url),
    )


class _Seat(Agent):
    name = "quant_researcher"
    role = "Quant Researcher"
    tier = ModelTier.STRONG

    def system_prompt(self) -> str:
        return "sys"

    def task_prompt(self, inputs: dict) -> str:  # noqa: ANN001
        del inputs
        return "task"


def test_billing_phrases_are_not_the_monthly_budget() -> None:
    assert is_billing_failure_text("anything", status_code=402)
    assert is_billing_failure_text("Payment required")
    assert is_billing_failure_text("Your prepaid credits are depleted")
    assert not is_billing_failure_text(
        "monthly LLM budget is exhausted; paused until the next billing month"
    )
    from firm.health_filters import is_resolved_noise, is_transient_llm_error

    sample = "gemini billing failure (payment required): HTTP 402: prepaid credits depleted"
    assert is_billing_failure_text(sample)
    assert not is_transient_llm_error(sample)
    assert not is_resolved_noise(sample)


def test_402_pauses_without_retry_or_model_swap(monkeypatch, firm_db) -> None:
    """One 402, no second model, no sleep, and a later success clears that seat."""
    del firm_db
    reset_billing_pauses()
    mode = get_settings().trading_mode
    digest = _approvals_digest()
    router = LlmRouter()
    calls = {"n": 0, "models": [], "urls": []}

    def post(url, headers=None, json=None, timeout=None):  # noqa: ANN001
        del headers, timeout
        calls["n"] += 1
        calls["models"].append(json["model"])
        calls["urls"].append(url)
        if calls["n"] == 1:
            return _http_402(url)
        return _http_200(url, "{}")

    monkeypatch.setattr(router._client, "post", post)
    monkeypatch.setattr(router, "api_key_for", lambda provider: "test-key")
    monkeypatch.setattr("firm.llm.time.sleep", lambda _s: (_ for _ in ()).throw(AssertionError("slept")))

    strong = router.catalogue[ModelTier.STRONG]
    cheap = router.catalogue[ModelTier.CHEAP]
    search = router.catalogue[ModelTier.SEARCH]
    try:
        try:
            router._call("quant_researcher", strong, [], 0.2, 100, False, None)
            raise AssertionError("expected billing error")
        except LlmError as exc:
            assert "payment required" in str(exc).lower()
            assert "not a strategy fault" in str(exc).lower()
        assert calls["n"] == 1
        assert calls["models"] == [strong.model]
        assert "generativelanguage.googleapis.com" in calls["urls"][0]
        assert seat_shows_billing_degraded("quant_researcher", Provider.GEMINI)
        assert "quant_researcher" in billing_degraded_seats()

        # Same pause blocks the cheap Gemini model. That would be a silent swap.
        try:
            router._call("ops_engineer", cheap, [], 0.2, 100, False, None)
            raise AssertionError("cheap model should be paused too")
        except LlmError as exc:
            assert "billing pause" in str(exc)
        assert calls["n"] == 1
        assert cheap.model not in calls["models"]

        mark_seat_billing_degraded("desk_head")

        # xAI is a different provider. Do not pause it because Gemini is unpaid.
        router._call("sentiment_analyst", search, [], 0.2, 100, False, None)
        assert calls["models"][-1] == search.model
        assert "quant_researcher" in billing_degraded_seats()
        assert "desk_head" in billing_degraded_seats()

        open_billing_probe_window(Provider.GEMINI)
        router._call("quant_researcher", strong, [], 0.2, 100, False, None)
        assert calls["models"][-1] == strong.model
        assert "quant_researcher" not in billing_degraded_seats()
        assert "desk_head" in billing_degraded_seats()
        assert not seat_shows_billing_degraded("quant_researcher", Provider.GEMINI)

        router._call("desk_head", strong, [], 0.2, 100, False, None)
        assert "desk_head" not in billing_degraded_seats()
        assert billing_degraded_seats() == frozenset()
        assert get_settings().trading_mode is mode
        assert _approvals_digest() == digest
    finally:
        reset_billing_pauses()
        router.close()


def test_seat_run_alarms_then_clears_on_success(monkeypatch, firm_db, tmp_path) -> None:
    del firm_db
    reset_billing_pauses()
    monkeypatch.setattr("firm.pipeline_state.STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(
        "firm.continuity.fill_walk_forward_slots",
        lambda source="": {"started": []},
    )
    router = LlmRouter()
    calls = {"n": 0, "models": []}

    def post(url, headers=None, json=None, timeout=None):  # noqa: ANN001
        del headers, timeout
        calls["n"] += 1
        calls["models"].append(json["model"])
        if calls["n"] == 1:
            return _http_402(url)
        return _http_200(url, '{"reasoning":"credits restored","confidence":0.4}')

    monkeypatch.setattr(router._client, "post", post)
    monkeypatch.setattr(router, "api_key_for", lambda provider: "test-key")
    seat = _Seat(router)
    strong = router.catalogue[ModelTier.STRONG]
    try:
        first = seat.run()
        assert first.status is RunStatus.SKIPPED
        assert calls["n"] == 1
        assert calls["models"] == [strong.model]
        from firm import memory

        titles = [row["title"] for row in memory.open_escalations()]
        assert "LLM billing: provider payment required" in titles
        detail = next(
            row["detail"]
            for row in memory.open_escalations()
            if row["title"] == "LLM billing: provider payment required"
        )
        assert "not a strategy fault" in detail.lower()
        card = seat.status_card()
        assert card["status"] == "degraded"
        assert card["billing_degraded"] is True
        assert "not a strategy fault" in card["last_error"].lower()
        from firm.llm import billing_heartbeat

        beat = billing_heartbeat()
        assert beat["degraded"] is True
        assert beat["kind"] == "llm_billing"
        assert "quant_researcher" in beat["seats"]

        # Pause is still armed: another run must not HTTP.
        second = seat.run()
        assert second.status is RunStatus.SKIPPED
        assert calls["n"] == 1
        assert sum(1 for row in memory.open_escalations() if "LLM billing" in row["title"]) == 1

        open_billing_probe_window(Provider.GEMINI)
        third = seat.run()
        assert third.status is RunStatus.SUCCESS
        assert calls["n"] == 2
        assert calls["models"] == [strong.model, strong.model]
        assert "quant_researcher" not in billing_degraded_seats()
        assert not any("LLM billing" in row["title"] for row in memory.open_escalations())
    finally:
        reset_billing_pauses()
        seat.close()


def test_quant_does_not_retry_storm_on_billing(firm_db, monkeypatch) -> None:
    from datetime import datetime, timedelta, timezone

    from core.db import session_scope
    from firm.accountability import quant_should_run_now
    from firm.memory_models import AgentRun
    from firm import memory

    reset_billing_pauses()
    monkeypatch.setattr("firm.accountability.catalog_needs_replenish", lambda: True)
    run_id = memory.start_run("quant_researcher", "Quant Researcher", "agenda")
    memory.finish_run(
        run_id,
        RunStatus.SKIPPED,
        error="gemini billing failure (payment required): HTTP 402: prepaid credits depleted",
    )
    old = datetime.now(timezone.utc) - timedelta(minutes=20)
    with session_scope() as session:
        row = session.get(AgentRun, run_id)
        row.started_at = old
        row.finished_at = old
    assert quant_should_run_now() is False
    reset_billing_pauses()


def test_orchestrator_skips_paused_gemini_seats(firm_db, monkeypatch) -> None:
    from firm.orchestrator import Orchestrator

    del firm_db
    reset_billing_pauses()
    monkeypatch.setattr("firm.research_jobs.quant_should_run_now", lambda: False)
    monkeypatch.setattr("firm.accountability.gm_should_run_now", lambda last: False)
    monkeypatch.setattr("firm.accountability.advisor_should_run_now", lambda last: False)
    monkeypatch.setattr("firm.accountability.ops_should_run_now", lambda last: False)
    monkeypatch.setattr("firm.accountability.sleeve_engineer_should_run_now", lambda last: False)
    trip_provider_billing(
        Provider.GEMINI,
        "quant_researcher",
        "HTTP 402 payment required: prepaid credits depleted",
    )
    orch = Orchestrator()
    try:
        due_names = {e.name for e in orch.due()}
        assert "quant_researcher" not in due_names
        assert "desk_head" not in due_names
        assert "ops_engineer" not in due_names
        assert "sentiment_analyst" in due_names
        assert "desk_head" in billing_degraded_seats()
    finally:
        orch.close()
        reset_billing_pauses()


def test_run_due_stops_after_the_probing_seat_402s(firm_db, monkeypatch) -> None:
    from firm.orchestrator import Orchestrator

    del firm_db
    reset_billing_pauses()
    monkeypatch.setattr(
        "firm.continuity.fill_walk_forward_slots",
        lambda source="": {"started": []},
    )
    orch = Orchestrator()
    try:
        by_name = {e.name: e for e in orch.employees}
        order = [by_name["quant_researcher"], by_name["desk_head"]]
        monkeypatch.setattr(orch, "due", lambda now=None: order)
        seen: list[str] = []

        def quant_run():
            trip_provider_billing(
                Provider.GEMINI,
                "quant_researcher",
                "HTTP 402 payment required",
            )
            seen.append("quant")
            return AgentResult(agent="quant_researcher", status=RunStatus.SKIPPED)

        def desk_run():
            seen.append("desk")
            return AgentResult(agent="desk_head", status=RunStatus.SUCCESS)

        order[0].run = quant_run  # type: ignore[method-assign]
        order[1].run = desk_run  # type: ignore[method-assign]
        orch.run_due()
        assert seen == ["quant"]
        assert "desk_head" in billing_degraded_seats()
    finally:
        orch.close()
        reset_billing_pauses()


def test_paper_cycle_scans_when_llm_raises_billing(monkeypatch) -> None:
    order: list[str] = []
    engine = MagicMock()
    report = SimpleNamespace(halted=False, halt_reason="")
    engine.run_cycle.side_effect = lambda: order.append("cycle") or report
    orchestrator = MagicMock()

    def boom():
        order.append("llm")
        raise RuntimeError("gemini billing failure (payment required): HTTP 402")

    orchestrator.run_due.side_effect = boom
    monkeypatch.setattr("firm.research_jobs.advance_pipeline", lambda: order.append("advance"))
    monkeypatch.setattr(
        "firm.continuity.fill_walk_forward_slots",
        lambda source="": order.append(f"wf:{source}") or {"started": []},
    )
    out = execute_paper_cycle(engine, orchestrator)
    assert out is report
    assert order == ["advance", "cycle", "llm", "wf:paper_cycle"]
    engine.run_cycle.assert_called_once()


def test_exit_poll_runs_while_billing_degraded() -> None:
    reset_billing_pauses()
    trip_provider_billing(
        Provider.GEMINI,
        "ops_engineer",
        "HTTP 402 payment required: prepaid credits depleted",
    )
    try:
        engine = MagicMock()
        engine.broker = PaperBroker.__new__(PaperBroker)
        wait_for_next_cycle(
            engine,
            1,
            shutdown=lambda: False,
            sleep=lambda _s: None,
            poll_seconds=1,
        )
        engine.supervise_exits.assert_called_once()
    finally:
        reset_billing_pauses()
