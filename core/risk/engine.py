"""
The deterministic risk engine.

Every order in the system passes through `RiskEngine.evaluate`. It is the final
authority: if it says no, no order is placed, regardless of which agent asked or
how confident that agent was.

Three invariants, each enforced by a test:

1. **No LLM calls.** This module imports nothing that can reach a network or a
   model. Risk decisions must be reproducible from inputs alone.
2. **Agents can only reduce risk.** An agent may shrink a position or veto a
   trade. `apply_agent_adjustment` clamps any requested size to the engine's
   own maximum, so an agent asking for more gets less.
3. **Every rejection is explained.** Decisions carry the full list of reasons,
   which is what makes the dashboard's risk panel meaningful and post-mortems
   possible.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from core.risk.killswitch import KillSwitch, TripReason
from core.risk.limits import RiskLimits

logger = logging.getLogger(__name__)


class RiskVerdict(str, Enum):
    """Outcome of a risk evaluation."""

    APPROVED = "approved"
    APPROVED_REDUCED = "approved_reduced"  # allowed, but at a smaller size
    REJECTED = "rejected"
    HALTED = "halted"  # kill switch or daily halt is active


@dataclass
class TradeIntent:
    """A proposed trade, before risk approval."""

    symbol: str
    side: str  # "LONG" or "SHORT"
    entry_price: float
    stop_price: float
    take_profit_price: float | None = None
    strategy: str = ""
    score: float = 0.0
    sector: str = "other"

    #: Which agents influenced this intent, for post-trade attribution.
    contributing_agents: list[str] = field(default_factory=list)

    @property
    def stop_distance_pct(self) -> float:
        """Stop distance as a fraction of entry price."""
        if self.entry_price <= 0:
            return 0.0
        return abs(self.entry_price - self.stop_price) / self.entry_price


@dataclass
class OpenPosition:
    """An open position, as the risk engine sees it."""

    symbol: str
    side: str
    quantity: float
    entry_price: float
    notional: float
    sector: str = "other"
    unrealised_pnl: float = 0.0


@dataclass
class PortfolioState:
    """Everything the risk engine needs to know about the account.

    Assembled by the ledger, never by an agent, so risk decisions cannot be
    influenced by an agent misreporting state.
    """

    equity: float
    peak_equity: float
    open_positions: list[OpenPosition] = field(default_factory=list)
    trades_today: int = 0
    realised_pnl_today: float = 0.0
    consecutive_losses: int = 0
    day: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d"))

    @property
    def total_exposure(self) -> float:
        return sum(p.notional for p in self.open_positions)

    @property
    def exposure_pct(self) -> float:
        if self.equity <= 0:
            return float("inf")
        return self.total_exposure / self.equity

    @property
    def drawdown_pct(self) -> float:
        """Current peak-to-trough decline as a fraction."""
        if self.peak_equity <= 0:
            return 0.0
        return max(0.0, (self.peak_equity - self.equity) / self.peak_equity)

    @property
    def daily_loss_pct(self) -> float:
        """Today's realised loss as a positive fraction of equity. 0 if up."""
        if self.equity <= 0:
            return 0.0
        return max(0.0, -self.realised_pnl_today / self.equity)

    def positions_in_sector(self, sector: str) -> int:
        return sum(1 for p in self.open_positions if p.sector == sector)

    def has_position(self, symbol: str) -> bool:
        return any(p.symbol == symbol for p in self.open_positions)


@dataclass
class RiskDecision:
    """The engine's ruling on a trade intent."""

    verdict: RiskVerdict
    quantity: float = 0.0
    notional: float = 0.0
    risk_amount: float = 0.0  # equity at risk if the stop is hit
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_approved(self) -> bool:
        return self.verdict in (RiskVerdict.APPROVED, RiskVerdict.APPROVED_REDUCED)

    def summary(self) -> dict[str, object]:
        return {
            "verdict": self.verdict.value,
            "approved": self.is_approved,
            "quantity": round(self.quantity, 8),
            "notional": round(self.notional, 2),
            "risk_amount": round(self.risk_amount, 2),
            "reasons": self.reasons,
            "warnings": self.warnings,
        }

    def __str__(self) -> str:
        if self.is_approved:
            return (
                f"{self.verdict.value}: qty {self.quantity:.6f} "
                f"(${self.notional:.2f} notional, ${self.risk_amount:.2f} at risk)"
            )
        return f"{self.verdict.value}: {'; '.join(self.reasons)}"


class RiskEngine:
    """Evaluates trade intents against hard limits. Contains no LLM calls."""

    def __init__(
        self,
        limits: RiskLimits | None = None,
        kill_switch: KillSwitch | None = None,
    ) -> None:
        self.limits = limits or RiskLimits()
        self.kill_switch = kill_switch or KillSwitch()

    # -----------------------------------------------------------------
    # Main entry point
    # -----------------------------------------------------------------
    def evaluate(self, intent: TradeIntent, state: PortfolioState) -> RiskDecision:
        """Decide whether `intent` may be executed, and at what size.

        Checks run in order of severity: halts first (nothing else matters),
        then validity of the intent itself, then portfolio-level limits, then
        sizing. All blocking reasons are collected rather than short-circuited,
        so the operator sees the whole picture.
        """
        reasons: list[str] = []
        warnings: list[str] = []

        # ---- 1. halts ---------------------------------------------------
        halt_reasons = self._check_halts(state)
        if halt_reasons:
            return RiskDecision(verdict=RiskVerdict.HALTED, reasons=halt_reasons)

        # ---- 2. intent validity ----------------------------------------
        reasons.extend(self._check_intent_validity(intent))

        # ---- 3. portfolio limits ---------------------------------------
        reasons.extend(self._check_portfolio_limits(intent, state))

        if reasons:
            return RiskDecision(verdict=RiskVerdict.REJECTED, reasons=reasons, warnings=warnings)

        # ---- 4. sizing --------------------------------------------------
        quantity, notional, risk_amount, sizing_notes, reduced = self._size_position(
            intent, state
        )
        warnings.extend(sizing_notes)

        if quantity <= 0 or notional < self.limits.min_notional_usdt:
            return RiskDecision(
                verdict=RiskVerdict.REJECTED,
                reasons=[
                    f"position size ${notional:.2f} below exchange minimum "
                    f"${self.limits.min_notional_usdt:.2f}"
                ],
                warnings=warnings,
            )

        return RiskDecision(
            verdict=RiskVerdict.APPROVED_REDUCED if reduced else RiskVerdict.APPROVED,
            quantity=quantity,
            notional=notional,
            risk_amount=risk_amount,
            warnings=warnings,
        )

    # -----------------------------------------------------------------
    # Checks
    # -----------------------------------------------------------------
    def _check_halts(self, state: PortfolioState) -> list[str]:
        """Conditions that stop all new entries outright."""
        reasons: list[str] = []

        switch = self.kill_switch.read()
        if switch.tripped:
            reasons.append(
                f"kill switch tripped ({switch.reason.value}: {switch.detail}) "
                f"at {switch.tripped_at} - manual reset required"
            )
            return reasons  # nothing else is relevant

        # Drawdown breach trips the switch rather than merely blocking, because
        # it means the strategy is behaving outside its validated envelope.
        if state.drawdown_pct >= self.limits.max_drawdown_pct:
            self.kill_switch.trip(
                TripReason.MAX_DRAWDOWN,
                f"drawdown {state.drawdown_pct:.2%} >= limit "
                f"{self.limits.max_drawdown_pct:.2%}",
                tripped_by="risk_engine",
            )
            reasons.append(f"drawdown {state.drawdown_pct:.2%} breached limit; kill switch tripped")
            return reasons

        # A daily loss halt is temporary: it clears at the next UTC day.
        if state.daily_loss_pct >= self.limits.daily_loss_limit_pct:
            reasons.append(
                f"daily loss {state.daily_loss_pct:.2%} >= limit "
                f"{self.limits.daily_loss_limit_pct:.2%}; halted until tomorrow (UTC)"
            )

        if state.consecutive_losses >= self.limits.max_consecutive_losses:
            reasons.append(
                f"{state.consecutive_losses} consecutive losses >= limit "
                f"{self.limits.max_consecutive_losses}; cooling down"
            )

        if state.equity <= 0:
            reasons.append("account equity is zero or negative")

        return reasons

    def _check_intent_validity(self, intent: TradeIntent) -> list[str]:
        """Structural problems with the proposed trade."""
        reasons: list[str] = []

        if intent.side.upper() not in ("LONG", "SHORT"):
            reasons.append(f"invalid side {intent.side!r}")

        if intent.entry_price <= 0:
            reasons.append(f"invalid entry price {intent.entry_price}")
            return reasons  # further price checks are meaningless

        if self.limits.require_stop_loss and intent.stop_price <= 0:
            reasons.append("no stop loss set (required)")
            return reasons

        # A stop on the wrong side of entry would be filled instantly.
        if intent.side.upper() == "LONG" and intent.stop_price >= intent.entry_price:
            reasons.append(
                f"long stop {intent.stop_price} is not below entry {intent.entry_price}"
            )
        if intent.side.upper() == "SHORT" and intent.stop_price <= intent.entry_price:
            reasons.append(
                f"short stop {intent.stop_price} is not above entry {intent.entry_price}"
            )

        distance = intent.stop_distance_pct
        if distance < self.limits.min_stop_distance_pct:
            reasons.append(
                f"stop distance {distance:.2%} below minimum "
                f"{self.limits.min_stop_distance_pct:.2%} (would be stopped by noise)"
            )
        if distance > self.limits.max_stop_distance_pct:
            reasons.append(
                f"stop distance {distance:.2%} above maximum "
                f"{self.limits.max_stop_distance_pct:.2%}"
            )

        return reasons

    def _check_portfolio_limits(self, intent: TradeIntent, state: PortfolioState) -> list[str]:
        """Position-count, concentration and frequency limits.

        These are the checks the legacy bot declared and never performed.
        """
        reasons: list[str] = []
        limits = self.limits

        if len(state.open_positions) >= limits.max_concurrent_positions:
            reasons.append(
                f"{len(state.open_positions)} open positions >= limit "
                f"{limits.max_concurrent_positions}"
            )

        if state.trades_today >= limits.max_daily_trades:
            reasons.append(
                f"{state.trades_today} trades today >= limit {limits.max_daily_trades}"
            )

        if state.has_position(intent.symbol) and limits.max_positions_per_symbol <= 1:
            reasons.append(f"already holding {intent.symbol} (no pyramiding)")

        in_sector = state.positions_in_sector(intent.sector)
        if in_sector >= limits.max_positions_per_sector:
            reasons.append(
                f"{in_sector} positions already in sector {intent.sector!r} >= limit "
                f"{limits.max_positions_per_sector} (correlation risk)"
            )

        if state.exposure_pct >= limits.max_total_exposure_pct:
            reasons.append(
                f"total exposure {state.exposure_pct:.1%} >= limit "
                f"{limits.max_total_exposure_pct:.1%}"
            )

        return reasons

    def _size_position(
        self, intent: TradeIntent, state: PortfolioState
    ) -> tuple[float, float, float, list[str], bool]:
        """Compute position size as the *minimum* of every applicable cap.

        Three independent caps, and the smallest wins:
          - risk-based: equity risked if the stop fills
          - notional: single-position size cap
          - headroom: what remains under the total exposure cap

        Taking the minimum rather than a preferred sizing rule means adding a
        new cap can only ever make positions smaller.
        """
        limits = self.limits
        notes: list[str] = []

        # Cap 1: risk-based sizing off stop distance.
        risk_budget = state.equity * limits.max_risk_per_trade_pct
        stop_distance = intent.stop_distance_pct
        risk_based_notional = risk_budget / stop_distance if stop_distance > 0 else 0.0

        # Cap 2: single-position notional cap.
        position_cap = state.equity * limits.max_position_pct

        # Cap 3: remaining room under the total exposure cap.
        exposure_room = max(
            0.0, state.equity * limits.max_total_exposure_pct - state.total_exposure
        )

        # Cap 4: leverage ceiling.
        leverage_cap = state.equity * limits.max_leverage

        notional = min(risk_based_notional, position_cap, exposure_room, leverage_cap)

        binding = min(
            ("risk-per-trade", risk_based_notional),
            ("position cap", position_cap),
            ("exposure headroom", exposure_room),
            ("leverage cap", leverage_cap),
            key=lambda pair: pair[1],
        )[0]
        reduced = notional < position_cap - 1e-9
        if reduced:
            notes.append(f"size limited by {binding} to ${notional:.2f}")

        quantity = notional / intent.entry_price if intent.entry_price > 0 else 0.0
        risk_amount = notional * stop_distance

        return quantity, notional, risk_amount, notes, reduced

    # -----------------------------------------------------------------
    # Agent interaction
    # -----------------------------------------------------------------
    def apply_agent_adjustment(
        self,
        decision: RiskDecision,
        requested_multiplier: float,
        agent: str,
    ) -> RiskDecision:
        """Apply an agent's sizing request, clamped so it can only reduce risk.

        This is the mechanism behind the trust ladder's L3 "sizing" authority.
        An agent asking for 2x gets 1x; an agent asking for 0.5x gets 0.5x.
        The asymmetry is the entire point.

        Args:
            decision: An approved decision from `evaluate`.
            requested_multiplier: The agent's requested size multiple.
            agent: Agent name, for the audit trail.
        """
        if not decision.is_approved:
            return decision

        clamped = max(0.0, min(requested_multiplier, 1.0))

        if clamped < requested_multiplier:
            logger.warning(
                "Agent %s requested %.2fx sizing; clamped to %.2fx. "
                "Agents cannot increase risk.",
                agent, requested_multiplier, clamped,
            )
            decision.warnings.append(
                f"{agent} requested {requested_multiplier:.2f}x; clamped to {clamped:.2f}x"
            )

        if clamped == 1.0:
            return decision

        if clamped == 0.0:
            return RiskDecision(
                verdict=RiskVerdict.REJECTED,
                reasons=[f"{agent} vetoed this trade (requested 0x sizing)"],
                warnings=decision.warnings,
            )

        decision.quantity *= clamped
        decision.notional *= clamped
        decision.risk_amount *= clamped
        decision.verdict = RiskVerdict.APPROVED_REDUCED
        decision.warnings.append(f"{agent} reduced size to {clamped:.2f}x")
        return decision

    # -----------------------------------------------------------------
    # Monitoring
    # -----------------------------------------------------------------
    def check_portfolio_health(self, state: PortfolioState) -> list[str]:
        """Warnings that do not block a trade but should reach the dashboard.

        Early warning at 80% of a limit gives the operator a chance to act
        before the limit stops trading.
        """
        warnings: list[str] = []
        limits = self.limits

        if state.drawdown_pct >= limits.max_drawdown_pct * 0.8:
            warnings.append(
                f"drawdown {state.drawdown_pct:.1%} is at 80% of the "
                f"{limits.max_drawdown_pct:.0%} kill-switch threshold"
            )
        if state.daily_loss_pct >= limits.daily_loss_limit_pct * 0.8:
            warnings.append(
                f"daily loss {state.daily_loss_pct:.1%} is approaching the "
                f"{limits.daily_loss_limit_pct:.1%} halt"
            )
        if state.exposure_pct >= limits.max_total_exposure_pct * 0.9:
            warnings.append(f"exposure {state.exposure_pct:.0%} is near the cap")
        if state.consecutive_losses >= limits.max_consecutive_losses - 2:
            warnings.append(f"{state.consecutive_losses} consecutive losses")

        return warnings
