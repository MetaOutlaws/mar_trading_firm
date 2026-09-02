"""
The trading engine: one cycle of scan, risk-check, execute, reconcile.

Order of operations is deliberate and matters:

1. **Health check.** A broker that cannot be reached, or candles that have gone
   stale, means the engine is blind. It trips the kill switch instead of trading
   on stale information.
2. **Reconcile.** Compare the ledger against the broker *before* deciding
   anything. Sizing new trades against a book that disagrees with reality is how
   small errors compound into large ones.
3. **Manage open positions.** Exits come before entries. Freeing a position slot
   by taking profit should let a new signal through in the same cycle.
4. **Scan for entries.** Signals come from `core.strategy` -- the same code the
   backtester ran.
5. **Risk-check every candidate.** Nothing reaches the broker without a
   `RiskDecision`, and every rejection is recorded.
6. **Record equity.**

The engine never decides *whether* a trade is safe; that is the risk engine's
job. It also never decides what a good signal is; that is the strategy's job.
Keeping those responsibilities separate is what makes each of them testable.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, fields, replace
from datetime import datetime, timedelta, timezone

from config.settings import PROJECT_ROOT, TradingMode, get_settings
from config.pipeline import APPROVED_RESEARCH_SYMBOLS, PAPER_SCAN_SLEEVES, is_paper_scan_sleeve
from config.universe import get_universe, parse_approval_key
from core.data.ohlcv import TIMEFRAME_DELTAS, BybitOHLCV, closed_candles, normalise_timeframe
from core.execution.broker import Broker
from core.execution.paper import PaperBroker
from core.ledger.store import Ledger
from core.risk.engine import RiskDecision, RiskEngine, RiskVerdict, TradeIntent
from core.risk.killswitch import TripReason
from core.strategy.base import Signal, SignalSide, Strategy

logger = logging.getLogger(__name__)

#: Grace period on top of the timeframe before candles count as stale. Covers
#: exchange publication lag and cycle scheduling jitter.
MAX_CANDLE_LATENCY = timedelta(minutes=15)

#: Last completed cycle, written so the dashboard can explain a quiet blotter
#: even though paper trading and the API are separate processes.
LAST_CYCLE_PATH = PROJECT_ROOT / "data" / "last_cycle.json"


def _now() -> datetime:
    """Clock seam so tests can freeze the just-closed-bar window."""
    return datetime.now(timezone.utc)


@dataclass
class CycleReport:
    """What happened during one engine cycle."""

    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    symbols_scanned: int = 0
    signals_found: int = 0
    orders_placed: int = 0
    positions_closed: int = 0
    rejections: list[tuple[str, str]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    halted: bool = False
    halt_reason: str = ""
    equity: float = 0.0
    crowding_skips: int = 0
    crowding_size_cuts: int = 0

    def summary(self) -> dict[str, object]:
        return {
            "started_at": self.started_at.isoformat(),
            "symbols_scanned": self.symbols_scanned,
            "signals_found": self.signals_found,
            "orders_placed": self.orders_placed,
            "positions_closed": self.positions_closed,
            "rejections": len(self.rejections),
            "rejection_details": [
                {"symbol": symbol, "reason": reason} for symbol, reason in self.rejections
            ],
            "errors": self.errors,
            "halted": self.halted,
            "halt_reason": self.halt_reason,
            "equity": round(self.equity, 2),
            "crowding_skips": self.crowding_skips,
            "crowding_size_cuts": self.crowding_size_cuts,
        }

    def __str__(self) -> str:
        if self.halted:
            return f"cycle HALTED: {self.halt_reason}"
        return (
            f"cycle: {self.symbols_scanned} scanned, {self.signals_found} signals, "
            f"{self.orders_placed} orders, {self.positions_closed} closed, "
            f"{len(self.rejections)} rejected, equity {self.equity:.2f}"
        )


@dataclass(frozen=True)
class PlanEntry:
    """One symbol/side the engine may trade, with its strategy and timeframe.

    The timeframe belongs here rather than on the engine because the legacy
    strategies genuinely differ: longs were tuned on 15m candles, shorts on 4h.
    Scanning a 4h short strategy on 15m candles would evaluate entirely
    different indicator values from the ones the backtest validated.
    """

    symbol: str
    side: SignalSide
    strategy: Strategy
    timeframe: str

    @property
    def key(self) -> str:
        return f"{self.symbol}:{self.side.value}"


@dataclass
class TradingPlan:
    """Which symbol/side pairs the engine may trade, and with what strategy."""

    entries: list[PlanEntry] = field(default_factory=list)

    @property
    def symbols(self) -> list[str]:
        return sorted({entry.symbol for entry in self.entries})

    @property
    def timeframes(self) -> list[str]:
        return sorted({entry.timeframe for entry in self.entries})


def _named_strategy(name: str, symbol: str, side: SignalSide, params: dict | None = None) -> Strategy:
    """Build a registered sleeve, using approval params when we have them.

    New catalog families must not require an engine edit, and must never fall
    through to RSI just because this process has not seen them yet.
    """
    del symbol
    from core.strategy.registry import get_strategy

    blob = params or {}
    cls = get_strategy(name)
    instance = cls()
    current = instance.params
    updates: dict = {"side": side}
    for item in fields(current):
        if item.name == "side" or item.name not in blob:
            continue
        default = getattr(current, item.name)
        raw = blob[item.name]
        try:
            if isinstance(default, bool):
                updates[item.name] = bool(raw)
            elif isinstance(default, int) and not isinstance(default, bool):
                updates[item.name] = int(raw)
            elif isinstance(default, float):
                updates[item.name] = float(raw)
            else:
                updates[item.name] = raw
        except (TypeError, ValueError):
            continue
    return cls(replace(current, **updates))


def _approved_record(symbol: str, side: SignalSide) -> tuple[str, dict] | None:
    """Latest approved (strategy, record) for this pair, preferring non-RSI."""
    from config.universe import parse_approval_key

    universe = get_universe()
    found: tuple[str, dict] | None = None
    for key, record in universe.approvals.items():
        parsed = parse_approval_key(key)
        if parsed is None:
            continue
        name, rec_symbol, rec_side = parsed
        if rec_symbol != symbol or rec_side != side.value:
            continue
        if record.get("approved") is not True:
            continue
        found = (name, record)
        if name != "rsi_trend":
            return found
    return found


def _clock_timeframe(family: str, side: SignalSide) -> str:
    """Candle clock the catalog assigned this family, or empty if unknown.

    Empty means skip — never fall back to asset_params 15m. That fallback is
    how paper traded wick_rejection on 15m while research tested 1h.
    """
    from firm.research_jobs import CLOCK_BY_FAMILY

    blob = CLOCK_BY_FAMILY.get(family) or ""
    if "/" not in blob:
        try:
            from firm.sleeve_factory import spec_for_family

            spec = spec_for_family(family)
            if spec is not None and spec.clock and "/" in spec.clock:
                blob = spec.clock
        except Exception:
            blob = blob
    if "/" not in blob:
        return ""
    long_tf, short_tf = blob.split("/", 1)
    raw = long_tf if side is SignalSide.LONG else short_tf
    try:
        return normalise_timeframe(raw.strip())
    except (ValueError, TypeError, KeyError):
        return ""


def _as_utc(value: datetime | object) -> datetime:
    """Normalise a pandas Timestamp or datetime to aware UTC."""
    dt = value.to_pydatetime() if hasattr(value, "to_pydatetime") else value
    if not isinstance(dt, datetime):
        raise TypeError(f"expected datetime, got {type(value)!r}")
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _clock_already_rejected(family: str, symbol: str, side: SignalSide, timeframe: str) -> bool:
    """True when walk-forward already failed this family@symbol@side@clock."""
    from config.universe import parse_approval_key

    universe = get_universe()
    for key, record in universe.approvals.items():
        parsed = parse_approval_key(key)
        if parsed is None:
            continue
        name, rec_symbol, rec_side = parsed
        if name != family or rec_symbol != symbol or rec_side != side.value:
            continue
        parts = key.split(":")
        rec_tf = str(record.get("timeframe") or (parts[3] if len(parts) >= 4 else "") or "")
        if not rec_tf:
            continue
        try:
            rec_tf = normalise_timeframe(rec_tf)
        except (ValueError, TypeError):
            pass
        if rec_tf != timeframe:
            continue
        if record.get("paper_override") is True:
            return False
        if record.get("approved") is False:
            return True
    return False


def _entry_from_record(name: str, record: dict, symbol: str, side: SignalSide) -> PlanEntry | None:
    """Build a plan row from one approvals-file record."""
    universe = get_universe()
    params = universe.params_for(symbol, side.value)
    try:
        strategy = _named_strategy(
            name,
            symbol,
            side,
            record.get("params") if isinstance(record.get("params"), dict) else {},
        )
    except KeyError:
        logger.error("%s:%s listed as %s but that sleeve is not registered", symbol, side.value, name)
        return None
    rec_tf = str(record.get("timeframe") or "")
    try:
        rec_tf = normalise_timeframe(rec_tf) if rec_tf else ""
    except (ValueError, TypeError, KeyError):
        rec_tf = ""
    fallback = ""
    if params is not None:
        try:
            fallback = normalise_timeframe(params.timeframe)
        except (ValueError, TypeError, KeyError):
            fallback = ""
    clock_tf = rec_tf or _clock_timeframe(name, side) or fallback
    if not clock_tf:
        logger.error("%s:%s as %s has no timeframe", symbol, side.value, name)
        return None
    return PlanEntry(symbol=symbol, side=side, strategy=strategy, timeframe=clock_tf)


def _entry_for(symbol: str, side: SignalSide, *, require_approval: bool = False) -> PlanEntry | None:
    """Build a plan entry using the sleeve research is actually testing.

    Live/testnet (`require_approval=True`) only emit pairs that passed
    walk-forward, using that record's parameters. Paper (`False`) follows
    the latest coded research job for unapproved candidates; approved pairs
    are added separately in `build_plan`.
    """
    universe = get_universe()
    params = universe.params_for(symbol, side.value)

    if require_approval:
        # Approval records carry their own clock. Do not require asset_params
        # shorts — that file is leftover RSI long-only config, and ETH/SOL
        # shorts already passed walk-forward without a row there.
        approved = _approved_record(symbol, side)
        if approved is None:
            return None
        name, record = approved
        return _entry_from_record(name, record, symbol, side)

    if params is None:
        return None
    timeframe = normalise_timeframe(params.timeframe)

    from firm.research_jobs import _active_job_for, paper_scan_family

    family = paper_scan_family()
    try:
        strategy = _named_strategy(family, symbol, side)
    except KeyError:
        logger.error("Paper asked to scan %s but it is not in the registry yet", family)
        return None
    clock_tf = _clock_timeframe(family, side)
    if not clock_tf:
        logger.error(
            "Paper skip %s %s: %s has no catalog clock (refusing asset_params %s fallback)",
            symbol,
            side.value,
            family,
            timeframe,
        )
        return None
    if _clock_already_rejected(family, symbol, side, clock_tf) and _active_job_for(family) is None:
        logger.info(
            "Paper skip %s %s %s %s: this clock already failed walk-forward",
            family,
            symbol,
            side.value,
            clock_tf,
        )
        return None
    return PlanEntry(symbol=symbol, side=side, strategy=strategy, timeframe=clock_tf)


def build_plan(require_approval: bool = True, candidates: list[str] | None = None) -> TradingPlan:
    """Assemble the trading plan from research approvals.

    Args:
        require_approval: When True (live and testnet), only research-approved
            pairs are included. Paper mode passes False so unapproved candidates
            can be forward-tested, but approved pairs are still always scanned.
        candidates: Explicit symbol list for paper mode. Defaults to the
            symbols that have configured parameters.
    """
    universe = get_universe()
    plan = TradingPlan()

    if require_approval:
        for symbol, side_value in universe.approved_pairs:
            entry = _entry_for(symbol, SignalSide(side_value), require_approval=True)
            if entry is None:
                logger.error(
                    "%s:%s is approved but has no configured parameters; skipping.",
                    symbol, side_value,
                )
                continue
            plan.entries.append(entry)
        logger.info("Trading plan: %d research-approved pairs.", len(plan.entries))
        return plan

    # Paper always scans research-approved pairs first. Last night the clock
    # followed the latest rejected job and skipped BTC/ETH/SOL because those
    # clocks had already failed, so the three approved pairs never traded.
    approved_pairs = set(universe.approved_pairs)
    seen: set[tuple[str, str, str, str]] = set()
    for symbol, side_value in universe.approved_pairs:
        entry = _entry_for(symbol, SignalSide(side_value), require_approval=True)
        if entry is None:
            logger.error(
                "%s:%s is approved but has no configured parameters; skipping.",
                symbol,
                side_value,
            )
            continue
        plan.entries.append(entry)
        seen.add((entry.symbol, entry.side.value, entry.strategy.name, entry.timeframe))

    # Operator paper vetoes: scan this exact sleeve even though gates failed.
    # Live `require_approval=True` never reaches here.
    for key, record in universe.paper_override_records:
        parsed = parse_approval_key(key)
        if parsed is None:
            continue
        name, symbol, side_value = parsed
        entry = _entry_from_record(name, record, symbol, SignalSide(side_value))
        if entry is None:
            continue
        ident = (entry.symbol, entry.side.value, entry.strategy.name, entry.timeframe)
        if ident in seen:
            continue
        plan.entries.append(entry)
        seen.add(ident)

    # Default to the most liquid names: their cost assumptions are the most
    # reliable, so forward-test evidence from them is the most informative.
    default_pool = [
        symbol
        for symbol in APPROVED_RESEARCH_SYMBOLS
        if symbol in universe.long_params or symbol in universe.short_params
    ]
    pool = candidates or default_pool or universe.research_candidates("LONG")[:6]
    for symbol in pool:
        for side in (SignalSide.LONG, SignalSide.SHORT):
            if (symbol, side.value) in approved_pairs:
                continue
            entry = _entry_for(symbol, side)
            if entry is None:
                continue
            ident = (entry.symbol, entry.side.value, entry.strategy.name, entry.timeframe)
            if ident in seen:
                continue
            plan.entries.append(entry)
            seen.add(ident)

    # Named paper candidates (ATR 1h on BNB/XRP/AVAX). These do not follow
    # paper_scan_family() or the catalog 4h clock, and they never unlock live.
    for family, symbol, side_value, timeframe in PAPER_SCAN_SLEEVES:
        entry = _entry_from_record(
            family,
            {"timeframe": timeframe, "params": {}, "approved": False},
            symbol,
            SignalSide(side_value),
        )
        if entry is None:
            continue
        ident = (entry.symbol, entry.side.value, entry.strategy.name, entry.timeframe)
        if ident in seen:
            continue
        plan.entries.append(entry)
        seen.add(ident)

    override_n = sum(
        1
        for e in plan.entries
        if universe.has_paper_override(e.strategy.name, e.symbol, e.side.value, e.timeframe)
    )
    approved_n = sum(1 for e in plan.entries if (e.symbol, e.side.value) in approved_pairs)
    extra_n = len(plan.entries) - approved_n
    logger.warning(
        "Trading plan: %d research-approved pair(s) plus %d UNAPPROVED "
        "candidate pair(s) (%d operator paper override(s)). Candidates have NOT "
        "passed validation and must never run with real money.",
        approved_n,
        extra_n,
        override_n,
    )
    return plan


def persist_last_cycle(report: CycleReport, plan: TradingPlan | None = None) -> None:
    """Write the latest cycle so the API process can explain a quiet blotter."""
    payload: dict[str, object] = report.summary()
    if plan is not None:
        universe = get_universe()
        payload["plan"] = [
            {
                "symbol": entry.symbol,
                "side": entry.side.value,
                "timeframe": entry.timeframe,
                "strategy": entry.strategy.name,
                "approved": universe.is_approved(entry.symbol, entry.side.value),
                "paper_override": universe.has_paper_override(
                    entry.strategy.name, entry.symbol, entry.side.value, entry.timeframe
                ),
                "paper_candidate": is_paper_scan_sleeve(
                    entry.strategy.name, entry.symbol, entry.side.value, entry.timeframe
                ),
            }
            for entry in plan.entries
        ]
    try:
        LAST_CYCLE_PATH.parent.mkdir(parents=True, exist_ok=True)
        LAST_CYCLE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError as exc:
        logger.warning("Could not persist last cycle: %s", exc)


def load_last_cycle() -> dict[str, object] | None:
    """Read the last persisted cycle, or None if paper has not run yet."""
    if not LAST_CYCLE_PATH.exists():
        return None
    try:
        data = json.loads(LAST_CYCLE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    return data if isinstance(data, dict) else None


class TradingEngine:
    """Runs trading cycles against a broker."""

    def __init__(
        self,
        broker: Broker,
        risk_engine: RiskEngine,
        ledger: Ledger,
        plan: TradingPlan,
        data_source: BybitOHLCV | None = None,
        paper_candidates: list[str] | None = None,
    ) -> None:
        self.broker = broker
        self.risk = risk_engine
        self.ledger = ledger
        self.plan = plan
        self._data = data_source or BybitOHLCV()
        self._owns_data = data_source is None
        # Paper rebuilds this plan every cycle so a new family does not wait
        # for a process restart. Live/testnet leave it as the approved book.
        self._paper_candidates = paper_candidates

        #: Agents whose advice applied to the current cycle, recorded on every
        #: position for later P&L attribution.
        self.active_agent_context: list[str] = []
        #: Per-symbol size multipliers contributed by agents. Clamped to <= 1.0
        #: by the risk engine, so this can only ever reduce risk.
        self.agent_size_multipliers: dict[str, float] = {}
        #: Symbols agents have vetoed this cycle.
        self.agent_vetoes: dict[str, str] = {}
        #: Paper crowding overlay rows keyed by symbol. Empty means fail-open.
        self._crowding: dict[str, dict] = {}
        self._crowding_skips = 0
        self._crowding_cuts = 0

    def refresh_scan_plan(self) -> bool:
        """Rebuild the paper sleeve from the latest coded research job.

        Returns True when the scanned family changed. Live/testnet no-op.
        """
        if get_settings().trading_mode is not TradingMode.PAPER:
            return False
        get_universe.cache_clear()
        new_plan = build_plan(require_approval=False, candidates=self._paper_candidates)
        old_names = {entry.strategy.name for entry in self.plan.entries}
        new_names = {entry.strategy.name for entry in new_plan.entries}
        self.plan = new_plan
        if old_names != new_names:
            logger.warning(
                "Paper scan sleeve changed %s -> %s (no process restart)",
                sorted(old_names) or ["(empty)"],
                sorted(new_names) or ["(empty)"],
            )
            return True
        return False

    def close(self) -> None:
        if self._owns_data:
            self._data.close()

    # -----------------------------------------------------------------
    # Main cycle
    # -----------------------------------------------------------------
    def run_cycle(self) -> CycleReport:
        """Execute one full trading cycle."""
        report = CycleReport()
        try:
            self.refresh_scan_plan()
        except Exception:
            logger.exception("Could not refresh the paper scan plan this cycle")

        # ---- 1. health ---------------------------------------------------
        healthy, message = self.broker.health_check()
        if not healthy:
            self.risk.kill_switch.trip(TripReason.BROKER_ERROR, message, tripped_by="engine")
            report.halted = True
            report.halt_reason = f"broker unhealthy: {message}"
            self.ledger.record_risk_event(
                "broker_unhealthy", "critical", detail=message, action_taken="kill switch tripped"
            )
            persist_last_cycle(report, self.plan)
            return report

        if self.risk.kill_switch.is_tripped:
            state = self.risk.kill_switch.read()
            report.halted = True
            report.halt_reason = f"kill switch tripped: {state.reason.value} - {state.detail}"
            logger.warning("Cycle skipped: %s", report.halt_reason)
            persist_last_cycle(report, self.plan)
            return report

        equity = self.broker.get_balance()
        report.equity = equity

        # ---- 2. reconcile ------------------------------------------------
        try:
            discrepancies = self.ledger.reconcile(self.broker.get_positions())
        except Exception as exc:
            report.errors.append(f"reconciliation failed: {exc}")
            logger.exception("Reconciliation error")
            discrepancies = []

        if discrepancies:
            detail = "; ".join(discrepancies[:5])
            self.risk.kill_switch.trip(
                TripReason.RECONCILIATION_MISMATCH, detail, tripped_by="engine"
            )
            self.ledger.record_risk_event(
                "reconciliation_mismatch",
                "critical",
                detail=detail,
                action_taken="kill switch tripped",
                context={"discrepancies": discrepancies},
            )
            report.halted = True
            report.halt_reason = f"reconciliation mismatch: {detail}"
            persist_last_cycle(report, self.plan)
            return report

        # ---- 3. manage open positions ------------------------------------
        report.positions_closed = self._manage_open_positions()

        # ---- 4/5. scan and execute ---------------------------------------
        marks: dict[str, float] = {}
        self._refresh_crowding()
        report.crowding_skips = 0
        report.crowding_size_cuts = 0

        for entry in self.plan.entries:
            report.symbols_scanned += 1
            try:
                signal, price = self._evaluate(entry)
            except Exception as exc:
                report.errors.append(f"{entry.key}: {exc}")
                logger.warning("Signal evaluation failed for %s: %s", entry.key, exc)
                continue

            if price:
                marks[entry.symbol] = price
            if signal is None:
                continue

            report.signals_found += 1
            decision = self._attempt_entry(signal, equity, marks)

            if decision.is_approved:
                report.orders_placed += 1
            else:
                report.rejections.append((signal.symbol, "; ".join(decision.reasons)))

        report.crowding_skips = self._crowding_skips
        report.crowding_size_cuts = self._crowding_cuts

        # ---- 6. record equity --------------------------------------------
        positions = self.ledger.open_positions()
        exposure = sum(p.quantity * marks.get(p.symbol, p.entry_price) for p in positions)
        self.ledger.record_equity(
            equity=equity,
            exposure=exposure,
            open_position_count=len(positions),
        )

        for warning in self.risk.check_portfolio_health(
            self.ledger.portfolio_state(equity, marks)
        ):
            logger.warning("Risk warning: %s", warning)
            self.ledger.record_risk_event("risk_warning", "warning", detail=warning)

        logger.info("%s", report)
        persist_last_cycle(report, self.plan)
        return report

    # -----------------------------------------------------------------
    # Steps
    # -----------------------------------------------------------------
    def _evaluate(self, entry: PlanEntry) -> tuple[Signal | None, float | None]:
        """Fetch candles and evaluate the strategy's latest bar.

        Uses `strategy.latest_signal`, which internally calls the same
        `generate_signals` the backtester uses. That is the structural reason
        live behaviour matches simulated behaviour.
        """
        strategy = entry.strategy
        candles = self._data.fetch_latest(
            entry.symbol, entry.timeframe, bars=strategy.min_bars + 50
        )

        if candles.empty:
            raise RuntimeError("no candles returned")

        now = _now()
        closed = closed_candles(candles, entry.timeframe, now=now)
        if closed.empty:
            return None, float(candles["close"].iloc[-1])

        # Stale candles mean the feed is broken; acting on them is worse than
        # not trading. Age is measured on the last *closed* bar so a forming
        # candle cannot disguise a dead feed.
        bar_open = _as_utc(closed.index[-1])
        step = TIMEFRAME_DELTAS[entry.timeframe]
        age = now - bar_open
        max_age = step * 2 + MAX_CANDLE_LATENCY
        if age > max_age:
            raise RuntimeError(f"stale candles: newest {entry.timeframe} bar is {age} old")

        # Only the just-closed bar is actionable. Replaying a 1h signal every
        # 5-minute cycle for the rest of the hour is how one wick becomes spam.
        close_at = bar_open + step
        latest_price = float(candles["close"].iloc[-1])
        if now > close_at + MAX_CANDLE_LATENCY:
            return None, latest_price

        return strategy.latest_signal(entry.symbol, closed), latest_price

    def _refresh_crowding(self) -> None:
        """Pull Bybit OI / funding / long-short for the paper book. Fail open."""
        self._crowding = {}
        self._crowding_skips = 0
        self._crowding_cuts = 0
        if get_settings().trading_mode is not TradingMode.PAPER:
            return
        symbols = self.plan.symbols
        if not symbols:
            return
        try:
            from core.data.positioning import snapshot_symbols

            blob = snapshot_symbols(symbols)
            rows = blob.get("symbols") if isinstance(blob, dict) else None
            self._crowding = rows if isinstance(rows, dict) else {}
        except Exception:
            logger.exception("Positioning snapshot failed; crowding overlay off this cycle")
            self._crowding = {}

    def _apply_crowding(self, decision: RiskDecision, signal: Signal) -> RiskDecision:
        """Skip or shrink a paper fill that would add to a crowded book."""
        if get_settings().trading_mode is not TradingMode.PAPER:
            return decision
        if not decision.is_approved:
            return decision
        from core.data.positioning import crowding_decision

        overlay = crowding_decision(self._crowding.get(signal.symbol), signal.side.value)
        if overlay.action == "skip":
            self._crowding_skips += 1
            return RiskDecision(
                verdict=RiskVerdict.REJECTED,
                reasons=[overlay.reason],
                warnings=list(decision.warnings),
            )
        if overlay.action == "size" and overlay.size_mult < 1.0:
            self._crowding_cuts += 1
            decision = self.risk.apply_agent_adjustment(
                decision, overlay.size_mult, agent="crowding"
            )
            if overlay.reason:
                decision.warnings.append(overlay.reason)
        return decision

    def _attempt_entry(
        self, signal: Signal, equity: float, marks: dict[str, float]
    ) -> RiskDecision:
        """Risk-check a signal and, if approved, place the order."""
        universe = get_universe()
        sector = universe.sector_of(signal.symbol)

        # Levels are derived from the signal's own TP/SL percentages, so the
        # live stop matches what the backtest assumed.
        if signal.side is SignalSide.LONG:
            stop_price = signal.price * (1.0 - signal.stop_loss_pct)
            take_profit = signal.price * (1.0 + signal.take_profit_pct)
        else:
            stop_price = signal.price * (1.0 + signal.stop_loss_pct)
            take_profit = signal.price * (1.0 - signal.take_profit_pct)

        intent = TradeIntent(
            symbol=signal.symbol,
            side=signal.side.value,
            entry_price=signal.price,
            stop_price=stop_price,
            take_profit_price=take_profit,
            strategy=signal.strategy,
            score=signal.score,
            sector=sector,
            contributing_agents=list(self.active_agent_context),
        )

        state = self.ledger.portfolio_state(equity, marks)
        decision = self.risk.evaluate(intent, state)

        # Agents may veto or shrink, never enlarge. The risk engine enforces
        # the clamp; the engine only relays the request.
        if decision.is_approved and signal.symbol in self.agent_vetoes:
            decision = self.risk.apply_agent_adjustment(
                decision, 0.0, agent=self.agent_vetoes[signal.symbol]
            )
        elif decision.is_approved and signal.symbol in self.agent_size_multipliers:
            decision = self.risk.apply_agent_adjustment(
                decision, self.agent_size_multipliers[signal.symbol], agent="portfolio_manager"
            )

        # Paper-only: skip or shrink crowded-with-the-crowd entries. Live is
        # unchanged until this overlay has a measured paper record.
        decision = self._apply_crowding(decision, signal)

        if not decision.is_approved:
            logger.info(
                "%s %s signal rejected: %s",
                signal.symbol, signal.side.value, "; ".join(decision.reasons),
            )
            self.ledger.record_rejected_signal(
                symbol=signal.symbol,
                side=signal.side.value,
                strategy=signal.strategy,
                signal_score=signal.score,
                verdict=decision.verdict.value,
                reasons=decision.reasons,
            )
            if decision.verdict is RiskVerdict.HALTED:
                self.ledger.record_risk_event(
                    "trading_halted",
                    "critical",
                    symbol=signal.symbol,
                    detail="; ".join(decision.reasons),
                )
            return decision

        self._place_order(signal, decision, stop_price, take_profit, sector)
        return decision

    def _place_order(
        self,
        signal: Signal,
        decision: RiskDecision,
        stop_price: float,
        take_profit: float,
        sector: str,
    ) -> None:
        """Submit the order, attach stops, and record the position."""
        result = self.broker.place_market_order(
            symbol=signal.symbol,
            side=signal.side.value,
            quantity=decision.quantity,
            expected_price=signal.price,
        )

        if not result.success:
            logger.error("Order failed for %s: %s", signal.symbol, result.error)
            self.ledger.record_risk_event(
                "order_failed", "warning", symbol=signal.symbol, detail=result.error
            )
            return

        # Stops are attached immediately. A filled position without a stop is
        # unbounded risk, so a failure here closes the position rather than
        # leaving it naked.
        stops_ok = self.broker.set_stops(signal.symbol, take_profit, stop_price)
        if not stops_ok:
            logger.critical(
                "Stops could not be set on %s; closing the position immediately "
                "rather than holding it unprotected.",
                signal.symbol,
            )
            self.broker.close_position(signal.symbol)
            self.ledger.record_risk_event(
                "stops_failed",
                "critical",
                symbol=signal.symbol,
                detail="stop placement failed",
                action_taken="position closed immediately",
            )
            return

        self.ledger.open_position(
            symbol=signal.symbol,
            side=signal.side.value,
            quantity=result.filled_quantity or decision.quantity,
            entry_price=result.fill_price,
            expected_entry_price=signal.price,
            take_profit=take_profit,
            stop_loss=stop_price,
            strategy=signal.strategy,
            sector=sector,
            signal_score=signal.score,
            signal_reason=signal.reason,
            broker_order_id=result.order_id,
            contributing_agents=self.active_agent_context,
            entry_indicators=signal.indicators,
        )

    def _manage_open_positions(self) -> int:
        """Handle exits. Returns the number of positions closed.

        In paper mode the engine polls the stops itself, because there is no
        exchange to enforce them. On a real broker the exchange fills them
        server-side and reconciliation notices the change.
        """
        closed = 0

        if isinstance(self.broker, PaperBroker):
            for symbol, reason, result in self.broker.check_stops():
                position = self.ledger.find_open_position(symbol)
                if position is None:
                    continue
                self.ledger.close_position(
                    position_id=position.id,
                    exit_price=result.fill_price,
                    expected_exit_price=position.take_profit_price
                    if reason == "take_profit"
                    else position.stop_loss_price,
                    exit_reason=reason,
                    fees=result.fee,
                )
                closed += 1
            return closed

        # Real broker: a position missing from the exchange means a stop filled.
        broker_symbols = {p.symbol for p in self.broker.get_positions()}
        for position in self.ledger.open_positions():
            if position.symbol in broker_symbols:
                continue

            exit_price = self.broker.get_price(position.symbol) or position.entry_price
            self.ledger.close_position(
                position_id=position.id,
                exit_price=exit_price,
                expected_exit_price=exit_price,
                exit_reason="broker_closed",
            )
            logger.info(
                "%s closed at the exchange (stop or target filled); ledger updated.",
                position.symbol,
            )
            closed += 1

        return closed


def build_engine(
    starting_equity: float = 10_000.0,
    candidates: list[str] | None = None,
) -> TradingEngine:
    """Construct an engine wired for the configured trading mode.

    Paper mode uses the simulated broker and permits unapproved candidates so
    the forward test can gather evidence. Testnet and live use the real broker
    and require research approval. Paper hydrates the in-memory book from the
    ledger so a process restart does not trip reconciliation.
    """
    settings = get_settings()
    mode = settings.trading_mode
    ledger = Ledger(mode=mode.value, starting_equity=starting_equity)

    from core.risk.limits import INITIAL_LIVE_LIMITS, PAPER_LIMITS

    if mode is TradingMode.PAPER:
        broker: Broker = PaperBroker(starting_equity=starting_equity)
        broker.hydrate(ledger.open_positions())
        limits = PAPER_LIMITS
        plan = build_plan(require_approval=False, candidates=candidates)
    else:
        from core.execution.bybit import BybitBroker

        broker = BybitBroker(mode=mode)
        limits = INITIAL_LIVE_LIMITS if mode is TradingMode.LIVE else PAPER_LIMITS
        plan = build_plan(require_approval=True)

        if not plan.entries:
            logger.critical(
                "No research-approved strategies. %s mode has nothing to trade, "
                "which is the correct outcome until validation passes.",
                mode.value,
            )

    return TradingEngine(
        broker=broker,
        risk_engine=RiskEngine(limits=limits),
        ledger=ledger,
        plan=plan,
        paper_candidates=candidates if mode is TradingMode.PAPER else None,
    )
