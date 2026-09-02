"""
FastAPI backend for the Employee Floor.

Read endpoints are open on localhost. Halt, reset, wake, and promotions
require `X-API-Token`. Inbox decide/ack from this machine do not — they are
desk actions, not remote kill-switch operations.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request
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

logger = logging.getLogger(__name__)


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


def _is_loopback(request: Request) -> bool:
    """True when the operator is on this machine.

    Inbox approve/reject is a desk action, not a remote halt. Binding the API
    to localhost already keeps strangers out; requiring the kill-switch token
    for every inbox click was a false coupling.
    """
    host = (request.client.host if request.client else "") or ""
    if host in {"127.0.0.1", "::1", "localhost", "0:0:0:0:0:0:0:1"}:
        return True
    if host.startswith("127.") or host.startswith("::ffff:127."):
        return True
    return False


def require_token_or_loopback(
    request: Request,
    x_api_token: str | None = Header(default=None, alias="X-API-Token"),
) -> None:
    """Inbox writes from the local desk skip the halt token."""
    if _is_loopback(request):
        return
    require_token(x_api_token)


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
    # Close leftover DeepSeek / is_tripped inbox items so Desk Head cannot
    # re-diagnose retired providers as a live outage.
    memory.clear_resolved_health_noise()
    try:
        from firm.research_jobs import advance_pipeline

        progressed = advance_pipeline()
        if progressed.get("started_jobs"):
            logger.info("Pipeline started walk-forward jobs: %s", progressed["started_jobs"])
        if progressed.get("posted_inbox"):
            logger.info("Posted research verdicts to Inbox for jobs %s", progressed["posted_inbox"])
    except Exception:
        logger.exception("Research catch-up failed; desk will still load.")


STATIC_DIR = Path(__file__).resolve().parent / "static"


@app.get("/")
def floor_page() -> FileResponse:
    # Operators refresh this constantly; never serve a stale desk after a restart.
    return FileResponse(
        STATIC_DIR / "index.html",
        headers={"Cache-Control": "no-store, max-age=0"},
    )


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


@app.get("/api/research-plan")
def research_plan_endpoint() -> dict[str, Any]:
    """The written catalog of what we test and why — not RSI-only."""
    from firm.research_catalog import research_plan

    return research_plan()


@app.get("/api/local-session")
def local_session(request: Request) -> dict[str, Any]:
    """Hand the desk the API token when the browser is on this machine.

    So halt/wake still work without pasting the token into Controls. Refuses
    anything that is not loopback.
    """
    if not _is_loopback(request):
        raise HTTPException(status_code=403, detail="loopback only")
    return {"ok": True, "loopback": True, "token": get_settings().api_token}


@app.get("/api/sentiment")
def sentiment() -> list[dict[str, Any]]:
    return memory.latest_sentiment()


@app.get("/api/regime")
def regime() -> dict[str, Any] | None:
    return memory.latest_regime()


@app.get("/api/positioning")
def positioning() -> dict[str, Any]:
    """Last Bybit open-interest / funding / account-ratio snapshot.

    Written by the paper clock and the regime analyst. This endpoint does not
    hit Bybit, so a dashboard refresh cannot rate-limit the feed.
    """
    from core.data.positioning import load_last_positioning

    return load_last_positioning() or {}


@app.get("/api/llm")
def llm_status() -> dict[str, Any]:
    """Which LLM seats have keys. Never returns the keys themselves."""
    from firm.llm import LlmRouter, provider_status

    snapshot = provider_status(catalogue=LlmRouter._catalogue_from_env())
    snapshot["budget"] = BudgetGuard().snapshot()
    snapshot["catalogue_note"] = (
        "Cheap, standard, and strong seats use Gemini. "
        "Search (Sentiment Analyst) still requires XAI_API_KEY."
    )
    return snapshot


class PingBody(BaseModel):
    provider: str = "gemini"


@app.post("/api/llm/ping")
def llm_ping(body: PingBody, _: None = Depends(require_token)) -> dict[str, Any]:
    """Ask the provider whether employees can complete. Uses one token."""
    from firm.llm import LlmRouter, Provider

    try:
        provider = Provider(body.provider.lower())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="unknown provider") from exc
    with LlmRouter(timeout=20.0) as router:
        return router.ping(provider)


@app.get("/api/cycle")
def last_cycle() -> dict[str, Any]:
    """Last paper/live engine cycle, plus a plain-language 'why quiet' read."""
    from core.execution.engine import load_last_cycle
    from firm.llm import provider_status

    cycle = load_last_cycle()
    snapshot = provider_status()
    employee_ok = any(
        bool(t.get("configured"))
        for t in (snapshot.get("tiers") or [])
        if t.get("tier") in ("cheap", "standard", "strong")
    )
    xai_ok = bool((snapshot.get("providers") or {}).get("xai", {}).get("configured"))
    return {
        "cycle": cycle,
        "quiet_reasons": _quiet_reasons(cycle, employee_ok, xai_ok),
    }


def _strategy_name_from_record(record: dict[str, Any]) -> str:
    """Name the sleeve that produced this verdict. Old files omitted the field."""
    named = str(record.get("strategy") or "").strip()
    if named:
        return named
    params = record.get("params") if isinstance(record.get("params"), dict) else {}
    if "lookback" in params:
        return "donchian_breakout"
    if any(key in params for key in ("rsi_min", "rsi_max", "rsi_threshold", "rsi_period")):
        return "rsi_trend"
    if "htf_minutes" in params or "pullback_ema" in params:
        return "trend_pullback_htf"
    if "atr_k" in params:
        return "atr_channel_breakout"
    if "ema_fast" in params or "ema_slow" in params:
        return "ema_adx_trend"
    if "bb_period" in params or "band_k" in params:
        return "bollinger_mean_reversion"
    return "unknown"


@app.get("/api/strategies")
def strategies() -> dict[str, Any]:
    """Research verdicts for every tested pair, plus registered strategy names."""
    from config.universe import APPROVALS_PATH, get_universe, parse_approval_key
    from core.strategy.registry import list_strategies

    get_universe.cache_clear()
    universe = get_universe()
    pairs: list[dict[str, Any]] = []
    for key, record in sorted(universe.approvals.items()):
        parsed = parse_approval_key(key)
        if parsed is None:
            continue
        strategy_id, symbol, side = parsed
        named = _strategy_name_from_record(record)
        pairs.append(
            {
                "key": key,
                "symbol": symbol,
                "side": side,
                "strategy": named if named != "unknown" else strategy_id,
                "approved": bool(record.get("approved") is True),
                "paper_override": bool(record.get("paper_override") is True),
                "paper_override_reason": record.get("paper_override_reason") or "",
                "paper_override_at": record.get("paper_override_at") or "",
                "timeframe": record.get("timeframe"),
                "params": record.get("params") or {},
                "oos_trades": record.get("oos_trades"),
                "oos_win_rate": record.get("oos_win_rate"),
                "oos_profit_factor": record.get("oos_profit_factor"),
                "oos_expectancy_pct": record.get("oos_expectancy_pct"),
                "oos_max_drawdown_pct": record.get("oos_max_drawdown_pct"),
                "failures": record.get("failures") or [],
                "validated_at": record.get("validated_at"),
            }
        )
    verdict = ""
    generated_at = ""
    if APPROVALS_PATH.exists():
        try:
            raw = json.loads(APPROVALS_PATH.read_text(encoding="utf-8"))
            verdict = str(raw.get("_verdict") or "")
            generated_at = str(raw.get("_generated_at") or "")
        except (json.JSONDecodeError, OSError, TypeError):
            verdict = ""
            generated_at = ""
    paper_overrides = [p for p in pairs if p.get("paper_override") and not p.get("approved")]
    return {
        "verdict": verdict,
        "generated_at": generated_at,
        "registered": list_strategies(),
        "approved_count": len(universe.approved_pairs),
        "paper_override_count": len(paper_overrides),
        "paper_overrides": [
            {
                "key": p["key"],
                "strategy": p["strategy"],
                "symbol": p["symbol"],
                "side": p["side"],
                "timeframe": p["timeframe"],
                "oos_trades": p["oos_trades"],
                "oos_profit_factor": p["oos_profit_factor"],
                "reason": p.get("paper_override_reason") or "",
            }
            for p in paper_overrides
        ],
        "pairs": pairs,
        "note": (
            "Approved is the live gate (every walk-forward check passed). "
            "Paper override is an operator veto: the row still fails research, "
            "but paper scans that exact sleeve for fills. Live stays locked. "
            "A later clock cannot overwrite an earlier one."
        ),
        "legend": {
            "oos_trades": "Closed round-trips on unseen (out-of-sample) folds, not paper fills.",
            "win": "Share of those OOS trades that made money after costs.",
            "pf": "Gross wins / gross losses. Below 1.00 loses money; we require 1.15.",
            "expectancy": "Average net return per trade. Must be positive after costs.",
            "dd": "Worst peak-to-trough equity drop during the OOS period.",
            "verdict": (
                "Approved = every research gate passed (live still needs go-live). "
                "Paper = operator veto for the paper book only. Rejected = not scanned "
                "as a named sleeve. PF >= 1.15 and positive expectancy are necessary, "
                "not sufficient."
            ),
        },
    }


def _quiet_reasons(cycle: dict[str, Any] | None, employee_llm_ok: bool, xai_ok: bool) -> list[str]:
    """Operator-facing explanation of an empty blotter. Not a trading signal."""
    reasons: list[str] = []
    if not employee_llm_ok:
        reasons.append(
            "No key for cheap/standard/strong seats (Gemini). Employees will skip LLM calls."
        )
    if not xai_ok:
        reasons.append(
            "XAI_API_KEY is missing, so the Sentiment Analyst (live X search) stays dark."
        )
    if cycle is None:
        reasons.append(
            "The paper clock has not completed a cycle yet, so there is no scan to explain."
        )
        reasons.append(
            "No strategy is research-approved. That locks live trading; paper may still scan."
        )
        return reasons
    if cycle.get("halted"):
        reasons.append(f"Last cycle halted: {cycle.get('halt_reason') or 'unknown reason'}.")
    scanned = int(cycle.get("symbols_scanned") or 0)
    signals = int(cycle.get("signals_found") or 0)
    orders = int(cycle.get("orders_placed") or 0)
    rejections = int(cycle.get("rejections") or 0)
    if scanned and signals == 0:
        reasons.append(
            f"Last cycle scanned {scanned} pairs and found 0 signals — RSI + golden-cross "
            "did not fire, which is expected for a rejected sleeve."
        )
    elif signals and orders == 0:
        reasons.append(
            f"Last cycle found {signals} signal(s) but placed 0 orders "
            f"({rejections} rejected by risk)."
        )
    elif orders:
        reasons.append(f"Last cycle placed {orders} order(s). If the blotter is empty, they are still open.")
    crowding_skips = int(cycle.get("crowding_skips") or 0)
    crowding_cuts = int(cycle.get("crowding_size_cuts") or 0)
    if not crowding_skips:
        crowding_skips = sum(
            1
            for d in (cycle.get("rejection_details") or [])
            if isinstance(d, dict) and "crowding:" in str(d.get("reason") or "").lower()
        )
    if crowding_skips:
        reasons.append(
            f"Crowding overlay skipped {crowding_skips} crowded-with-the-crowd signal(s)."
        )
    if crowding_cuts:
        reasons.append(
            f"Crowding overlay sized down {crowding_cuts} entry(ies) where accounts already leaned with the trade."
        )
    errors = cycle.get("errors") or []
    if errors:
        reasons.append("Last cycle had evaluation errors: " + "; ".join(str(e) for e in errors[:3]))
    plan = [e for e in (cycle.get("plan") or []) if isinstance(e, dict)]
    approved_n = sum(1 for e in plan if e.get("approved") is True)
    paper_n = sum(1 for e in plan if e.get("paper_override") is True)
    if approved_n:
        reasons.append(
            f"{approved_n} research-approved pair(s) are on the paper book. "
            "Live still needs the go-live gates."
        )
    else:
        reasons.append(
            "No pair is research-approved. Paper is gathering evidence; live stays locked."
        )
    if paper_n:
        reasons.append(
            f"{paper_n} operator paper veto(es) are also being scanned. "
            "They are not live-approved."
        )
    return reasons


def _unrealised_fields(
    side: str,
    quantity: float,
    entry_price: float,
    notional: float,
    mark_price: float | None,
) -> dict[str, Any]:
    """Live mark and open P&L. The ledger row itself never stores these."""
    if mark_price is None:
        return {
            "mark_price": None,
            "unrealised_pnl": None,
            "return_pct": None,
            "in_the_money": None,
        }
    direction = 1.0 if str(side).upper() == "LONG" else -1.0
    upnl = (float(mark_price) - float(entry_price)) * float(quantity) * direction
    denom = float(notional) or abs(float(quantity) * float(entry_price))
    ret = (upnl / denom * 100.0) if denom else 0.0
    return {
        "mark_price": float(mark_price),
        "unrealised_pnl": round(upnl, 4),
        "return_pct": round(ret, 4),
        "in_the_money": upnl > 0,
    }


def _ticker_marks(symbols: list[str]) -> dict[str, float | None]:
    """Last traded price per symbol from the public ticker. One request each."""
    unique = sorted({symbol for symbol in symbols if symbol})
    if not unique:
        return {}
    from core.data.ohlcv import BybitOHLCV

    source = BybitOHLCV()
    try:
        return {symbol: source.latest_price(symbol) for symbol in unique}
    finally:
        source.close()


@app.get("/api/risk")
def risk() -> dict[str, Any]:
    state = KillSwitch().read()
    settings = get_settings()
    ledger = Ledger(mode=settings.trading_mode.value)
    rows = list(ledger.open_positions())
    marks = _ticker_marks([p.symbol for p in rows])
    open_positions = []
    for p in rows:
        payload = {
            "id": p.id,
            "symbol": p.symbol,
            "side": p.side,
            "quantity": p.quantity,
            "entry_price": p.entry_price,
            "notional": p.notional,
            "take_profit": p.take_profit_price,
            "stop_loss": p.stop_loss_price,
            "strategy": p.strategy,
            "opened_at": p.opened_at.isoformat() if p.opened_at else None,
            "agents": p.contributing_agents,
        }
        payload.update(
            _unrealised_fields(
                p.side, p.quantity, p.entry_price, p.notional, marks.get(p.symbol)
            )
        )
        open_positions.append(payload)
    return {
        "kill_switch": state.to_dict(),
        "mode": settings.trading_mode.value,
        "performance": ledger.performance(),
        "equity": _latest_equity(settings.trading_mode.value),
        "open_positions": open_positions,
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
                "quantity": t.quantity,
                "notional": t.notional,
                "entry_price": t.entry_price,
                "exit_price": t.exit_price,
                "gross_pnl": t.gross_pnl,
                "net_pnl": t.net_pnl,
                "return_pct": t.return_pct,
                "fees": t.fees,
                "funding": t.funding,
                "exit_reason": t.exit_reason,
                "strategy": t.strategy,
                "agents": t.contributing_agents,
                "entry_slippage_bps": t.entry_slippage_bps,
                "exit_slippage_bps": t.exit_slippage_bps,
                "mode": t.mode,
                "entry_time": t.entry_time.isoformat(),
                "exit_time": t.exit_time.isoformat(),
            }
            for t in rows
        ]


def _latest_equity(mode: str) -> dict[str, Any] | None:
    from sqlalchemy import select

    from core.db import session_scope
    from core.ledger.models import EquitySnapshot

    with session_scope() as session:
        row = session.scalars(
            select(EquitySnapshot)
            .where(EquitySnapshot.mode == mode)
            .order_by(EquitySnapshot.recorded_at.desc())
            .limit(1)
        ).first()
        if row is None:
            return None
        return {
            "recorded_at": row.recorded_at.isoformat(),
            "equity": row.equity,
            "realised_pnl": row.realised_pnl,
            "unrealised_pnl": row.unrealised_pnl,
            "exposure": row.exposure,
            "open_positions": row.open_positions,
            "peak_equity": row.peak_equity,
            "drawdown_pct": row.drawdown_pct,
        }


@app.get("/api/equity")
def equity_curve(limit: int = 240) -> list[dict[str, Any]]:
    """Equity snapshots for the sparkline and drawdown read, newest last."""
    from sqlalchemy import select

    from core.db import session_scope
    from core.ledger.models import EquitySnapshot

    settings = get_settings()
    cap = max(1, min(int(limit), 2000))
    with session_scope() as session:
        rows = list(
            session.scalars(
                select(EquitySnapshot)
                .where(EquitySnapshot.mode == settings.trading_mode.value)
                .order_by(EquitySnapshot.recorded_at.desc())
                .limit(cap)
            )
        )
        rows.reverse()
        return [
            {
                "recorded_at": r.recorded_at.isoformat(),
                "equity": r.equity,
                "realised_pnl": r.realised_pnl,
                "unrealised_pnl": r.unrealised_pnl,
                "exposure": r.exposure,
                "open_positions": r.open_positions,
                "peak_equity": r.peak_equity,
                "drawdown_pct": r.drawdown_pct,
            }
            for r in rows
        ]


@app.get("/api/rejections")
def rejections(limit: int = 40) -> list[dict[str, Any]]:
    """Signals that fired but never became orders — explains a quiet blotter."""
    from sqlalchemy import select

    from core.db import session_scope
    from core.ledger.models import RejectedSignal

    cap = max(1, min(int(limit), 200))
    with session_scope() as session:
        rows = session.scalars(
            select(RejectedSignal).order_by(RejectedSignal.occurred_at.desc()).limit(cap)
        )
        return [
            {
                "id": r.id,
                "occurred_at": r.occurred_at.isoformat(),
                "symbol": r.symbol,
                "side": r.side,
                "strategy": r.strategy,
                "signal_score": r.signal_score,
                "verdict": r.verdict,
                "reasons": r.reasons,
            }
            for r in rows
        ]


class DecisionBody(BaseModel):
    """Inbox approve/reject payload from the dashboard."""

    approved: bool
    decided_by: str = "operator"
    reason: str = ""


class CodeFamilyBody(BaseModel):
    family: str
    reason: str = "research_tab"


@app.post("/api/research/code-family")
def start_coding(
    body: CodeFamilyBody, _: None = Depends(require_token_or_loopback)
) -> dict[str, Any]:
    """Approve-and-code from the Research tab, same path as Inbox approve.

    Templates materialize immediately and walk-forward starts. Novel families
    already in the registry start walk-forward. Novel still uncoded get a
    Cursor brief and escalate; catch-up starts the test when the file lands.
    """
    family = (body.family or "").strip().lower()
    if not family:
        raise HTTPException(status_code=400, detail="family is required")
    from firm.research_jobs import infer_family, on_operator_approved

    matching = None
    for proposal in memory.pending_proposals(limit=100):
        payload = proposal.get("payload") if isinstance(proposal.get("payload"), dict) else {}
        if str(payload.get("action") or "") != "code_family":
            continue
        if infer_family(payload, str(proposal.get("title") or "")) == family:
            matching = proposal
            break
    if matching and memory.decide_proposal(
        int(matching["id"]),
        approved=True,
        decided_by="operator",
        reason=body.reason,
    ):
        result = on_operator_approved(memory.get_proposal(int(matching["id"])) or matching)
    else:
        result = on_operator_approved(
            {
                "kind": "operational",
                "title": f"Code {family}",
                "payload": {"action": "code_family", "family": family, "novel": True},
                "status": "approved",
            }
        )
    return {
        "ok": True,
        "family": str(result.get("family") or family),
        "queued": bool(result.get("queued")),
        "handed_to_cursor": bool(result.get("handed_to_cursor")),
        "next_step": str(result.get("next_step") or "Approved."),
        "coding": result.get("coding") or {},
    }


@app.post("/api/inbox/{proposal_id}/decide")
def decide(
    proposal_id: int, body: DecisionBody, _: None = Depends(require_token_or_loopback)
) -> dict[str, Any]:
    ok = memory.decide_proposal(
        proposal_id, approved=body.approved, decided_by=body.decided_by, reason=body.reason
    )
    if not ok:
        raise HTTPException(status_code=409, detail="proposal is not pending")
    next_step = "Rejected. Nothing is queued."
    queued = False
    family = ""
    handed_to_cursor = False
    if body.approved:
        proposal = memory.get_proposal(proposal_id)
        from firm.research_jobs import on_operator_approved

        result = on_operator_approved(proposal or {})
        next_step = str(result.get("next_step") or "Approved.")
        queued = bool(result.get("queued"))
        family = str(result.get("family") or "")
        handed_to_cursor = bool(result.get("handed_to_cursor"))
    return {
        "ok": True,
        "next_step": next_step,
        "queued": queued,
        "family": family,
        "handed_to_cursor": handed_to_cursor,
    }


@app.post("/api/escalations/{escalation_id}/ack")
def ack(escalation_id: int, _: None = Depends(require_token_or_loopback)) -> dict[str, Any]:
    if not memory.acknowledge_escalation(escalation_id):
        raise HTTPException(status_code=404, detail="not found or already acknowledged")
    return {"ok": True}


@app.post("/api/escalations/{escalation_id}/resolve")
def resolve_escalation(
    escalation_id: int, _: None = Depends(require_token_or_loopback)
) -> dict[str, Any]:
    if not memory.resolve_escalation(escalation_id):
        raise HTTPException(status_code=404, detail="not found or already resolved")
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


@app.post("/api/employees/wake")
def wake_floor(_: None = Depends(require_token)) -> dict[str, Any]:
    """Run every employee whose seat has a key. Sentiment stays dark without xAI."""
    orch = get_orchestrator()
    runnable = [
        employee.name
        for employee in orch.employees
        if employee.tier is None or orch.router.is_configured(employee.tier)
    ]
    parked = [
        employee.name
        for employee in orch.employees
        if employee.name not in runnable
    ]
    results = orch.run_named(runnable)
    return {
        "ran": [result.summary() for result in results],
        "skipped": parked,
    }


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
