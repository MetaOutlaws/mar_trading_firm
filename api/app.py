"""
FastAPI backend for the Employee Floor.

Read endpoints are open on localhost. Anything that can halt trading, approve
a proposal, or promote an employee requires `X-API-Token`.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from config.settings import PROJECT_ROOT, get_settings
from core.db import init_db
from core.ledger.store import Ledger
from core.risk.killswitch import KillSwitch, TripReason
from firm import memory, trust
from firm.llm import BudgetGuard
from firm.memory_models import TrustLevel
from firm.orchestrator import Orchestrator
from firm.trust import DEFAULT_CRITERIA


def _require_token(x_api_token: str | None = None) -> None:
    from fastapi import Header

    # Imported at call time so this module stays importable without FastAPI Header
    # binding during unit collection. The route wrappers below use the real
    # dependency.
    del x_api_token


from fastapi import Header  # noqa: E402


def require_token(x_api_token: str | None = Header(default=None, alias="X-API-Token")) -> None:
    settings = get_settings()
    if not x_api_token or x_api_token != settings.api_token:
        raise HTTPException(status_code=401, detail="missing or invalid X-API-Token")


@lru_cache(maxsize=1)
def get_orchestrator() -> Orchestrator:
    init_db()
    return Orchestrator()


app = FastAPI(title="MAR Trading Firm", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup() -> None:
    init_db()


STATIC_DIR = Path(__file__).resolve().parent / "static"


@app.get("/")
def floor_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/floor")
def floor() -> dict[str, Any]:
    return get_orchestrator().floor_snapshot()


@app.get("/api/employees")
def employees() -> list[dict[str, Any]]:
    return [e.status_card() for e in get_orchestrator().employees]


@app.get("/api/activity")
def activity(limit: int = 40) -> list[dict[str, Any]]:
    return memory.recent_runs(limit=limit)


@app.get("/api/inbox")
def inbox() -> list[dict[str, Any]]:
    return memory.pending_proposals()


@app.get("/api/escalations")
def escalations() -> list[dict[str, Any]]:
    return memory.open_escalations()


@app.get("/api/research")
def research() -> list[dict[str, Any]]:
    return memory.research_board()


@app.get("/api/sentiment")
def sentiment() -> list[dict[str, Any]]:
    return memory.latest_sentiment()


@app.get("/api/regime")
def regime() -> dict[str, Any] | None:
    return memory.latest_regime()


@app.get("/api/budget")
def budget() -> dict[str, Any]:
    return BudgetGuard().snapshot()


@app.get("/api/risk")
def risk() -> dict[str, Any]:
    state = KillSwitch().read()
    settings = get_settings()
    ledger = Ledger(mode=settings.trading_mode.value)
    return {
        "kill_switch": state.to_dict(),
        "mode": settings.trading_mode.value,
        "performance": ledger.performance(),
        "open_positions": [
            {
                "id": p.id,
                "symbol": p.symbol,
                "side": p.side,
                "quantity": p.quantity,
                "entry_price": p.entry_price,
                "strategy": p.strategy,
                "agents": p.contributing_agents,
            }
            for p in ledger.open_positions()
        ],
    }


@app.get("/api/trades")
def trades(limit: int = 50) -> list[dict[str, Any]]:
    from sqlalchemy import select

    from core.db import session_scope
    from core.ledger.models import TradeRecord

    with session_scope() as session:
        rows = session.scalars(
            select(TradeRecord).order_by(TradeRecord.exit_time.desc()).limit(limit)
        )
        return [
            {
                "id": t.id,
                "symbol": t.symbol,
                "side": t.side,
                "net_pnl": t.net_pnl,
                "return_pct": t.return_pct,
                "exit_reason": t.exit_reason,
                "strategy": t.strategy,
                "agents": t.contributing_agents,
                "entry_slippage_bps": t.entry_slippage_bps,
                "exit_slippage_bps": t.exit_slippage_bps,
                "entry_time": t.entry_time.isoformat(),
                "exit_time": t.exit_time.isoformat(),
            }
            for t in rows
        ]


class DecisionBody(BaseModel):
    approved: bool
    reason: str = ""
    decided_by: str = "operator"


@app.post("/api/inbox/{proposal_id}/decide")
def decide(proposal_id: int, body: DecisionBody, _: None = Depends(require_token)) -> dict[str, Any]:
    ok = memory.decide_proposal(
        proposal_id, approved=body.approved, decided_by=body.decided_by, reason=body.reason
    )
    if not ok:
        raise HTTPException(status_code=409, detail="proposal is not pending")
    return {"ok": True}


@app.post("/api/escalations/{escalation_id}/ack")
def ack(escalation_id: int, _: None = Depends(require_token)) -> dict[str, Any]:
    if not memory.acknowledge_escalation(escalation_id):
        raise HTTPException(status_code=404, detail="not found or already acknowledged")
    return {"ok": True}


class KillBody(BaseModel):
    detail: str = "manual halt from dashboard"
    operator: str = "operator"


@app.post("/api/risk/kill")
def kill(body: KillBody, _: None = Depends(require_token)) -> dict[str, Any]:
    state = KillSwitch().trip(TripReason.MANUAL, body.detail, tripped_by=body.operator)
    return state.to_dict()


class ResetBody(BaseModel):
    operator: str
    acknowledgement: str = Field(description="Must be exactly: I HAVE INVESTIGATED THE CAUSE")


@app.post("/api/risk/reset")
def reset_kill(body: ResetBody, _: None = Depends(require_token)) -> dict[str, Any]:
    try:
        state = KillSwitch().reset(body.operator, body.acknowledgement)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return state.to_dict()


class PromoteBody(BaseModel):
    to_level: int
    approved_by: str
    auditor_recommends: bool = False


@app.post("/api/employees/{agent}/promote")
def promote(agent: str, body: PromoteBody, _: None = Depends(require_token)) -> dict[str, Any]:
    try:
        level = TrustLevel(body.to_level)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid trust level") from exc
    ok, reason = trust.promote(
        agent,
        level,
        approved_by=body.approved_by,
        auditor_recommends=body.auditor_recommends,
        criteria=DEFAULT_CRITERIA,
    )
    if not ok:
        raise HTTPException(status_code=409, detail=reason)
    return {"ok": True, "detail": reason}


class RunBody(BaseModel):
    agents: list[str]


@app.post("/api/employees/run")
def run_employees(body: RunBody, _: None = Depends(require_token)) -> list[dict[str, Any]]:
    results = get_orchestrator().run_named(body.agents)
    return [r.summary() for r in results]


@app.get("/api/go-live")
def go_live_status() -> dict[str, Any]:
    # `scripts/` is a runner folder, not an installed package. Adding the repo
    # root lets uvicorn import the same module `python scripts/check_go_live.py` uses.
    import sys

    root = str(PROJECT_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
    from scripts.check_go_live import evaluate_gates

    return evaluate_gates()
