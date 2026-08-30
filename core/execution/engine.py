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

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from config.settings import TradingMode, get_settings
from config.universe import get_universe
from core.data.ohlcv import TIMEFRAME_DELTAS, BybitOHLCV, normalise_timeframe
from core.execution.broker import Broker
from core.execution.paper import PaperBroker
from core.ledger.store import Ledger
from core.risk.engine import RiskDecision, RiskEngine, RiskVerdict, TradeIntent
from core.risk.killswitch import TripReason
from core.strategy.base import Signal, SignalSide, Strategy
from core.strategy.rsi_golden_cross import long_strategy_for, short_strategy_for

logger = logging.getLogger(__name__)

#: Grace period on top of the timeframe before candles count as stale. Covers
#: exchange publication lag and cycle scheduling jitter.
MAX_CANDLE_LATENCY = timedelta(minutes=15)


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

    def summary(self) -> dict[str, object]:
        return {
            "started_at": self.started_at.isoformat(),
            "symbols_scanned": self.symbols_scanned,
            "signals_found": self.signals_found,
            "orders_placed": self.orders_placed,
            "positions_closed": self.positions_closed,
            "rejections": len(self.rejections),
            "errors": self.errors,
            "halted": self.halted,
            "halt_reason": self.halt_reason,
            "equity": round(self.equity, 2),
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


def _entry_for(symbol: str, side: SignalSide) -> PlanEntry | None:
    """Build a plan entry using the configured params for `symbol`/`side`."""
    universe = get_universe()
    params = universe.params_for(symbol, side.value)
    if params is None:
        return None

    strategy = (
        long_strategy_for(symbol) if side is SignalSide.LONG else short_strategy_for(symbol)
    )
    return PlanEntry(
        symbol=symbol,
        side=side,
        strategy=strategy,
        timeframe=normalise_timeframe(params.timeframe),
    )


def build_plan(require_approval: bool = True, candidates: list[str] | None = None) -> TradingPlan:
    """Assemble the trading plan from research approvals.

    Args:
        require_approval: When True (live and testnet), only research-approved
            pairs are included. Paper mode passes False so that *candidate*
            strategies can be forward-tested -- gathering that evidence is the
            entire purpose of paper trading, and requiring approval first would
            be circular.
        candidates: Explicit symbol list for paper mode. Defaults to the
            symbols that have configured parameters.
    """
    universe = get_universe()
    plan = TradingPlan()

    if require_approval:
        for symbol, side_value in universe.approved_pairs:
            entry = _entry_for(symbol, SignalSide(side_value))
            if entry is None:
                logger.error(
                    "%s:%s is approved but has no configured parameters; skipping.",
                    symbol, side_value,
                )
                continue
            plan.entries.append(entry)
        logger.info("Trading plan: %d research-approved pairs.", len(plan.entries))
        return plan

    # Default to the most liquid names: their cost assumptions are the most
    # reliable, so forward-test evidence from them is the most informative.
    default_pool = [
        symbol
        for symbol in ("BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "AVAXUSDT")
        if symbol in universe.long_params or symbol in universe.short_params
    ]
    pool = candidates or default_pool or universe.research_candidates("LONG")[:6]
    for symbol in pool:
        for side in (SignalSide.LONG, SignalSide.SHORT):
            entry = _entry_for(symbol, side)
            if entry is not None:
                plan.entries.append(entry)

    logger.warning(
        "Trading plan: %d UNAPPROVED candidate pairs (paper forward-test mode). "
        "These have NOT passed validation and must never run with real money.",
        len(plan.entries),
    )
    return plan


class TradingEngine:
    """Runs trading cycles against a broker."""

    def __init__(
        self,
        broker: Broker,
        risk_engine: RiskEngine,
        ledger: Ledger,
        plan: TradingPlan,
        data_source: BybitOHLCV | None = None,
    ) -> None:
        self.broker = broker
        self.risk = risk_engine
        self.ledger = ledger
        self.plan = plan
        self._data = data_source or BybitOHLCV()
        self._owns_data = data_source is None

        #: Agents whose advice applied to the current cycle, recorded on every
        #: position for later P&L attribution.
        self.active_agent_context: list[str] = []
        #: Per-symbol size multipliers contributed by agents. Clamped to <= 1.0
        #: by the risk engine, so this can only ever reduce risk.
        self.agent_size_multipliers: dict[str, float] = {}
        #: Symbols agents have vetoed this cycle.
        self.agent_vetoes: dict[str, str] = {}

    def close(self) -> None:
        if self._owns_data:
            self._data.close()

    # -----------------------------------------------------------------
    # Main cycle
    # -----------------------------------------------------------------
    def run_cycle(self) -> CycleReport:
        """Execute one full trading cycle."""
        report = CycleReport()

        # ---- 1. health ---------------------------------------------------
        healthy, message = self.broker.health_check()
        if not healthy:
            self.risk.kill_switch.trip(TripReason.BROKER_ERROR, message, tripped_by="engine")
            report.halted = True
            report.halt_reason = f"broker unhealthy: {message}"
            self.ledger.record_risk_event(
                "broker_unhealthy", "critical", detail=message, action_taken="kill switch tripped"
            )
            return report

        if self.risk.kill_switch.is_tripped:
            state = self.risk.kill_switch.read()
            report.halted = True
            report.halt_reason = f"kill switch tripped: {state.reason.value} - {state.detail}"
            logger.warning("Cycle skipped: %s", report.halt_reason)
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
            return report

        # ---- 3. manage open positions ------------------------------------
        report.positions_closed = self._manage_open_positions()

        # ---- 4/5. scan and execute ---------------------------------------
        marks: dict[str, float] = {}

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
                report.rejections.append((symbol, "; ".join(decision.reasons)))

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

        # Stale candles mean the feed is broken; acting on them is worse than
        # not trading. The tolerance scales with the timeframe: a 4h bar being
        # two hours old is normal, whereas a 15m bar being two hours old is not.
        age = datetime.now(timezone.utc) - candles.index[-1].to_pydatetime()
        max_age = TIMEFRAME_DELTAS[entry.timeframe] * 2 + MAX_CANDLE_LATENCY
        if age > max_age:
            raise RuntimeError(f"stale candles: newest {entry.timeframe} bar is {age} old")

        latest_price = float(candles["close"].iloc[-1])
        return strategy.latest_signal(entry.symbol, candles), latest_price

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
    and require research approval.
    """
    settings = get_settings()
    mode = settings.trading_mode

    from core.risk.limits import INITIAL_LIVE_LIMITS, PAPER_LIMITS

    if mode is TradingMode.PAPER:
        broker: Broker = PaperBroker(starting_equity=starting_equity)
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
        ledger=Ledger(mode=mode.value, starting_equity=starting_equity),
        plan=plan,
    )
