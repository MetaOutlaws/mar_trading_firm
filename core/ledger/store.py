"""
Ledger: the firm's book of record for positions, trades and equity.

The ledger is the *only* source of portfolio state the risk engine reads. That
matters because it means an agent cannot influence a risk decision by
misreporting state -- risk sees the book, not an agent's summary of it.

It also reconciles against the broker. A position the broker knows about and the
ledger does not (or vice versa) is a serious condition: it means the system's
model of reality is wrong, so it trips the kill switch rather than continuing to
size new trades against a fiction.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Sequence

from sqlalchemy import func, select

from core.db import session_scope
from core.execution.broker import PositionSnapshot
from core.ledger.models import (
    EquitySnapshot,
    Position,
    PositionStatus,
    RejectedSignal,
    RiskEvent,
    TradeRecord,
)
from core.risk.engine import OpenPosition, PortfolioState

logger = logging.getLogger(__name__)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def today_utc() -> str:
    return utcnow().strftime("%Y-%m-%d")


class Ledger:
    """Reads and writes the trading book for one mode (paper/testnet/live)."""

    def __init__(self, mode: str = "paper", starting_equity: float = 10_000.0) -> None:
        self.mode = mode
        self.starting_equity = starting_equity

    # -----------------------------------------------------------------
    # Positions
    # -----------------------------------------------------------------
    def open_position(
        self,
        symbol: str,
        side: str,
        quantity: float,
        entry_price: float,
        expected_entry_price: float,
        take_profit: float | None,
        stop_loss: float | None,
        strategy: str,
        sector: str,
        signal_score: float,
        signal_reason: str,
        broker_order_id: str,
        contributing_agents: Sequence[str] = (),
        entry_indicators: dict | None = None,
    ) -> int:
        """Record a newly opened position and return its id."""
        with session_scope() as session:
            position = Position(
                symbol=symbol,
                side=side.upper(),
                status=PositionStatus.OPEN.value,
                mode=self.mode,
                quantity=quantity,
                entry_price=entry_price,
                notional=quantity * entry_price,
                expected_entry_price=expected_entry_price,
                take_profit_price=take_profit,
                stop_loss_price=stop_loss,
                strategy=strategy,
                sector=sector,
                signal_score=signal_score,
                signal_reason=signal_reason,
                broker_order_id=broker_order_id,
                contributing_agents=list(contributing_agents),
                entry_indicators=entry_indicators or {},
            )
            session.add(position)
            session.flush()
            logger.info(
                "Ledger: opened position %d - %s %s qty=%.6f @ %.6f (slippage %.1f bps)",
                position.id, side, symbol, quantity, entry_price,
                position.entry_slippage_bps,
            )
            return position.id

    def close_position(
        self,
        position_id: int,
        exit_price: float,
        expected_exit_price: float,
        exit_reason: str,
        fees: float = 0.0,
        funding: float = 0.0,
    ) -> TradeRecord | None:
        """Close a position and write the resulting trade record."""
        with session_scope() as session:
            position = session.get(Position, position_id)
            if position is None:
                logger.error("Ledger: cannot close unknown position %d", position_id)
                return None
            if position.status != PositionStatus.OPEN.value:
                logger.warning("Ledger: position %d is already %s", position_id, position.status)
                return None

            direction = 1.0 if position.side == "LONG" else -1.0
            gross_pnl = (exit_price - position.entry_price) * position.quantity * direction
            net_pnl = gross_pnl - fees - funding

            exit_slippage_bps = 0.0
            if expected_exit_price:
                difference = (exit_price - expected_exit_price) / expected_exit_price
                # A long exiting below expectation is unfavourable, hence -1.
                exit_slippage_bps = difference * -direction * 10_000

            trade = TradeRecord(
                position_id=position.id,
                symbol=position.symbol,
                side=position.side,
                mode=self.mode,
                strategy=position.strategy,
                quantity=position.quantity,
                notional=position.notional,
                entry_price=position.entry_price,
                exit_price=exit_price,
                entry_time=position.opened_at,
                exit_time=utcnow(),
                gross_pnl=gross_pnl,
                fees=fees,
                funding=funding,
                net_pnl=net_pnl,
                return_pct=(net_pnl / position.notional * 100.0) if position.notional else 0.0,
                exit_reason=exit_reason,
                entry_slippage_bps=position.entry_slippage_bps,
                exit_slippage_bps=exit_slippage_bps,
                contributing_agents=list(position.contributing_agents or []),
                entry_indicators=dict(position.entry_indicators or {}),
            )
            session.add(trade)

            position.status = PositionStatus.CLOSED.value
            position.closed_at = utcnow()

            session.flush()
            logger.info(
                "Ledger: closed position %d - %s net P&L %.4f (%.3f%%), reason=%s",
                position_id, position.symbol, net_pnl, trade.return_pct, exit_reason,
            )
            return trade

    def open_positions(self) -> list[Position]:
        """All currently open positions in this mode."""
        with session_scope() as session:
            return list(
                session.scalars(
                    select(Position).where(
                        Position.status == PositionStatus.OPEN.value,
                        Position.mode == self.mode,
                    )
                )
            )

    def find_open_position(self, symbol: str) -> Position | None:
        with session_scope() as session:
            return session.scalars(
                select(Position).where(
                    Position.symbol == symbol,
                    Position.status == PositionStatus.OPEN.value,
                    Position.mode == self.mode,
                )
            ).first()

    # -----------------------------------------------------------------
    # Portfolio state for the risk engine
    # -----------------------------------------------------------------
    def portfolio_state(self, equity: float, marks: dict[str, float] | None = None) -> PortfolioState:
        """Assemble the state the risk engine evaluates against.

        Args:
            equity: Current account equity, from the broker.
            marks: Latest prices, for unrealised P&L on open positions.
        """
        marks = marks or {}
        positions = self.open_positions()

        open_positions = []
        for position in positions:
            mark = marks.get(position.symbol, position.entry_price)
            direction = 1.0 if position.side == "LONG" else -1.0
            open_positions.append(
                OpenPosition(
                    symbol=position.symbol,
                    side=position.side,
                    quantity=position.quantity,
                    entry_price=position.entry_price,
                    notional=position.quantity * mark,
                    sector=position.sector,
                    unrealised_pnl=(mark - position.entry_price) * position.quantity * direction,
                )
            )

        return PortfolioState(
            equity=equity,
            peak_equity=max(self.peak_equity(), equity),
            open_positions=open_positions,
            trades_today=self.trades_today(),
            realised_pnl_today=self.realised_pnl_today(),
            consecutive_losses=self.consecutive_losses(),
            day=today_utc(),
        )

    def trades_today(self) -> int:
        """Count of trades opened today (UTC).

        Counts *opens*, not closes: the daily trade limit exists to cap activity
        and exposure to execution error, both of which are driven by entries.
        """
        start = datetime.combine(utcnow().date(), datetime.min.time(), tzinfo=timezone.utc)
        with session_scope() as session:
            return int(
                session.scalar(
                    select(func.count(Position.id)).where(
                        Position.mode == self.mode, Position.opened_at >= start
                    )
                )
                or 0
            )

    def realised_pnl_today(self) -> float:
        start = datetime.combine(utcnow().date(), datetime.min.time(), tzinfo=timezone.utc)
        with session_scope() as session:
            return float(
                session.scalar(
                    select(func.coalesce(func.sum(TradeRecord.net_pnl), 0.0)).where(
                        TradeRecord.mode == self.mode, TradeRecord.exit_time >= start
                    )
                )
                or 0.0
            )

    def consecutive_losses(self) -> int:
        """Length of the current losing streak."""
        with session_scope() as session:
            recent = list(
                session.scalars(
                    select(TradeRecord)
                    .where(TradeRecord.mode == self.mode)
                    .order_by(TradeRecord.exit_time.desc())
                    .limit(50)
                )
            )
        streak = 0
        for trade in recent:
            if trade.net_pnl > 0:
                break
            streak += 1
        return streak

    def peak_equity(self) -> float:
        """Highest equity ever recorded, for drawdown measurement."""
        with session_scope() as session:
            recorded = session.scalar(
                select(func.max(EquitySnapshot.equity)).where(EquitySnapshot.mode == self.mode)
            )
        return max(float(recorded or 0.0), self.starting_equity)

    # -----------------------------------------------------------------
    # Equity and events
    # -----------------------------------------------------------------
    def record_equity(
        self,
        equity: float,
        unrealised_pnl: float = 0.0,
        exposure: float = 0.0,
        open_position_count: int = 0,
    ) -> None:
        """Append an equity snapshot."""
        peak = max(self.peak_equity(), equity)
        drawdown = ((peak - equity) / peak * 100.0) if peak > 0 else 0.0

        with session_scope() as session:
            session.add(
                EquitySnapshot(
                    mode=self.mode,
                    equity=equity,
                    realised_pnl=equity - self.starting_equity,
                    unrealised_pnl=unrealised_pnl,
                    exposure=exposure,
                    open_positions=open_position_count,
                    peak_equity=peak,
                    drawdown_pct=drawdown,
                )
            )

    def record_risk_event(
        self,
        event_type: str,
        severity: str = "info",
        symbol: str = "",
        detail: str = "",
        action_taken: str = "",
        context: dict | None = None,
    ) -> None:
        with session_scope() as session:
            session.add(
                RiskEvent(
                    event_type=event_type,
                    severity=severity,
                    symbol=symbol,
                    detail=detail,
                    action_taken=action_taken,
                    context=context or {},
                )
            )

    def record_rejected_signal(
        self,
        symbol: str,
        side: str,
        strategy: str,
        signal_score: float,
        verdict: str,
        reasons: Sequence[str],
    ) -> None:
        """Record a signal that fired but was not traded.

        Without this, "the strategy did nothing this week" is ambiguous between
        no signals and every signal being blocked.
        """
        with session_scope() as session:
            session.add(
                RejectedSignal(
                    symbol=symbol,
                    side=side,
                    strategy=strategy,
                    signal_score=signal_score,
                    verdict=verdict,
                    reasons=list(reasons),
                )
            )

    # -----------------------------------------------------------------
    # Reconciliation
    # -----------------------------------------------------------------
    def reconcile(self, broker_positions: list[PositionSnapshot]) -> list[str]:
        """Compare the ledger against the broker and report discrepancies.

        Any mismatch means the system's model of reality is wrong. The caller
        trips the kill switch on a non-empty result rather than sizing new
        trades against a book it cannot trust.
        """
        discrepancies: list[str] = []

        broker_by_symbol = {p.symbol: p for p in broker_positions}
        ledger_by_symbol = {p.symbol: p for p in self.open_positions()}

        for symbol in ledger_by_symbol.keys() - broker_by_symbol.keys():
            discrepancies.append(
                f"{symbol}: open in ledger but not at broker (closed externally, "
                "or a stop filled without the ledger being updated)"
            )

        for symbol in broker_by_symbol.keys() - ledger_by_symbol.keys():
            discrepancies.append(
                f"{symbol}: open at broker but not in ledger (untracked position)"
            )

        for symbol in broker_by_symbol.keys() & ledger_by_symbol.keys():
            broker_position = broker_by_symbol[symbol]
            ledger_position = ledger_by_symbol[symbol]

            if broker_position.side != ledger_position.side:
                discrepancies.append(
                    f"{symbol}: side mismatch (broker {broker_position.side}, "
                    f"ledger {ledger_position.side})"
                )

            # Allow 1% for fee-driven quantity drift and rounding.
            if ledger_position.quantity > 0:
                drift = abs(broker_position.quantity - ledger_position.quantity)
                if drift / ledger_position.quantity > 0.01:
                    discrepancies.append(
                        f"{symbol}: quantity mismatch (broker {broker_position.quantity}, "
                        f"ledger {ledger_position.quantity})"
                    )

        if discrepancies:
            logger.error("Reconciliation found %d discrepancies:", len(discrepancies))
            for issue in discrepancies:
                logger.error("  - %s", issue)
        else:
            logger.debug("Reconciliation clean: %d positions match.", len(ledger_by_symbol))

        return discrepancies

    def mark_orphaned(self, symbol: str) -> None:
        """Flag a ledger position the broker does not have."""
        with session_scope() as session:
            position = session.scalars(
                select(Position).where(
                    Position.symbol == symbol,
                    Position.status == PositionStatus.OPEN.value,
                    Position.mode == self.mode,
                )
            ).first()
            if position:
                position.status = PositionStatus.ORPHANED.value
                position.closed_at = utcnow()
                logger.warning("Ledger: marked %s position %d as orphaned", symbol, position.id)

    # -----------------------------------------------------------------
    # Reporting
    # -----------------------------------------------------------------
    def performance(self, days: int | None = None) -> dict[str, object]:
        """Aggregate performance metrics, for the dashboard and the auditor."""
        with session_scope() as session:
            query = select(TradeRecord).where(TradeRecord.mode == self.mode)
            if days:
                query = query.where(TradeRecord.exit_time >= utcnow() - timedelta(days=days))
            trades = list(session.scalars(query.order_by(TradeRecord.exit_time)))

        if not trades:
            return {
                "mode": self.mode,
                "trades": 0,
                "win_rate": 0.0,
                "profit_factor": None,
                "net_pnl": 0.0,
                "measured_slippage_bps": None,
            }

        wins = [t for t in trades if t.net_pnl > 0]
        losses = [t for t in trades if t.net_pnl <= 0]
        gross_profit = sum(t.net_pnl for t in wins)
        gross_loss = abs(sum(t.net_pnl for t in losses))

        slippages = [
            t.entry_slippage_bps for t in trades if t.entry_slippage_bps
        ] + [t.exit_slippage_bps for t in trades if t.exit_slippage_bps]

        return {
            "mode": self.mode,
            "trades": len(trades),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round(len(wins) / len(trades) * 100.0, 2),
            "profit_factor": round(gross_profit / gross_loss, 3) if gross_loss else None,
            "net_pnl": round(sum(t.net_pnl for t in trades), 2),
            "total_fees": round(sum(t.fees for t in trades), 2),
            "total_funding": round(sum(t.funding for t in trades), 2),
            "avg_return_pct": round(sum(t.return_pct for t in trades) / len(trades), 4),
            # The go-live gate compares this against the modelled 10 bps.
            "measured_slippage_bps": (
                round(sum(slippages) / len(slippages), 2) if slippages else None
            ),
            "first_trade": trades[0].exit_time.isoformat(),
            "last_trade": trades[-1].exit_time.isoformat(),
        }

    def attribution_by_agent(self) -> dict[str, dict[str, float]]:
        """Net P&L grouped by contributing employee.

        This is what the trust ladder promotes on. An agent with no attributed
        P&L cannot be promoted, regardless of how confident its outputs read.
        """
        with session_scope() as session:
            trades = list(
                session.scalars(select(TradeRecord).where(TradeRecord.mode == self.mode))
            )

        attribution: dict[str, dict[str, float]] = {}
        for trade in trades:
            for agent in trade.contributing_agents or []:
                record = attribution.setdefault(
                    agent, {"trades": 0.0, "net_pnl": 0.0, "wins": 0.0}
                )
                record["trades"] += 1
                record["net_pnl"] += trade.net_pnl
                if trade.net_pnl > 0:
                    record["wins"] += 1

        for record in attribution.values():
            record["win_rate"] = (
                round(record["wins"] / record["trades"] * 100.0, 2) if record["trades"] else 0.0
            )
            record["net_pnl"] = round(record["net_pnl"], 2)

        return attribution
