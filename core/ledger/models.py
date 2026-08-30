"""
Trading tables: positions, trades, equity snapshots, risk events.

Two design points worth calling out:

**Slippage is recorded, not assumed.** Every fill stores both the price the
strategy expected and the price actually received. That turns the backtest's
0.1% slippage assumption from an article of faith into a measurable quantity,
which is one of the plan's go-live gates.

**Agent attribution is stored on the trade.** Each trade records which employees
influenced it, so per-agent P&L attribution -- the basis of the trust ladder --
is a query rather than a guess.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import JSON, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.db import Base, UtcDateTime


def utcnow() -> datetime:
    """Timezone-aware UTC now. Naive timestamps cause silent ordering bugs."""
    return datetime.now(timezone.utc)


class PositionStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"
    #: Broker reports a position the ledger does not know about, or vice versa.
    ORPHANED = "orphaned"


class TradingMode(str, Enum):
    PAPER = "paper"
    TESTNET = "testnet"
    LIVE = "live"


class Position(Base):
    """An open or historical position."""

    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    symbol: Mapped[str] = mapped_column(String(32), index=True)
    side: Mapped[str] = mapped_column(String(8))  # LONG / SHORT
    status: Mapped[str] = mapped_column(String(16), default=PositionStatus.OPEN.value, index=True)
    mode: Mapped[str] = mapped_column(String(16), default=TradingMode.PAPER.value, index=True)

    quantity: Mapped[float] = mapped_column(Float)
    entry_price: Mapped[float] = mapped_column(Float)
    notional: Mapped[float] = mapped_column(Float)

    #: What the strategy expected to pay, for slippage measurement.
    expected_entry_price: Mapped[float] = mapped_column(Float, default=0.0)

    take_profit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    stop_loss_price: Mapped[float | None] = mapped_column(Float, nullable=True)

    opened_at: Mapped[datetime] = mapped_column(UtcDateTime, default=utcnow, index=True)
    closed_at: Mapped[datetime | None] = mapped_column(UtcDateTime, nullable=True)

    strategy: Mapped[str] = mapped_column(String(64), default="")
    sector: Mapped[str] = mapped_column(String(32), default="other")
    signal_score: Mapped[float] = mapped_column(Float, default=0.0)
    signal_reason: Mapped[str] = mapped_column(Text, default="")

    broker_order_id: Mapped[str] = mapped_column(String(64), default="")

    #: Employees that influenced this position, e.g. ["regime_analyst", "risk_officer"].
    contributing_agents: Mapped[list] = mapped_column(JSON, default=list)
    #: Indicator readings at entry, for post-trade analysis.
    entry_indicators: Mapped[dict] = mapped_column(JSON, default=dict)

    trades: Mapped[list["TradeRecord"]] = relationship(back_populates="position")

    __table_args__ = (Index("ix_positions_status_mode", "status", "mode"),)

    @property
    def entry_slippage_bps(self) -> float:
        """Realised entry slippage in basis points, signed against the trader.

        Positive means the fill was worse than expected.
        """
        if not self.expected_entry_price:
            return 0.0
        difference = (self.entry_price - self.expected_entry_price) / self.expected_entry_price
        # A short filling below expectation is favourable, so flip the sign.
        direction = 1.0 if self.side.upper() == "LONG" else -1.0
        return difference * direction * 10_000


class TradeRecord(Base):
    """A completed round trip with full cost and attribution detail."""

    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    position_id: Mapped[int | None] = mapped_column(
        ForeignKey("positions.id"), nullable=True, index=True
    )

    symbol: Mapped[str] = mapped_column(String(32), index=True)
    side: Mapped[str] = mapped_column(String(8))
    mode: Mapped[str] = mapped_column(String(16), default=TradingMode.PAPER.value, index=True)
    strategy: Mapped[str] = mapped_column(String(64), default="")

    quantity: Mapped[float] = mapped_column(Float)
    notional: Mapped[float] = mapped_column(Float)

    entry_price: Mapped[float] = mapped_column(Float)
    exit_price: Mapped[float] = mapped_column(Float)
    entry_time: Mapped[datetime] = mapped_column(UtcDateTime, index=True)
    exit_time: Mapped[datetime] = mapped_column(UtcDateTime, index=True)

    gross_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    fees: Mapped[float] = mapped_column(Float, default=0.0)
    funding: Mapped[float] = mapped_column(Float, default=0.0)
    net_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    return_pct: Mapped[float] = mapped_column(Float, default=0.0)

    exit_reason: Mapped[str] = mapped_column(String(32), default="")

    #: Measured slippage, compared against the backtest assumption during the
    #: go-live gate check.
    entry_slippage_bps: Mapped[float] = mapped_column(Float, default=0.0)
    exit_slippage_bps: Mapped[float] = mapped_column(Float, default=0.0)

    contributing_agents: Mapped[list] = mapped_column(JSON, default=list)
    entry_indicators: Mapped[dict] = mapped_column(JSON, default=dict)

    position: Mapped["Position | None"] = relationship(back_populates="trades")

    @property
    def is_win(self) -> bool:
        """Profitable after every cost. Gross winners that lose money are losses."""
        return self.net_pnl > 0


class EquitySnapshot(Base):
    """Periodic account state, forming the equity curve."""

    __tablename__ = "equity_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recorded_at: Mapped[datetime] = mapped_column(
        UtcDateTime, default=utcnow, index=True
    )
    mode: Mapped[str] = mapped_column(String(16), default=TradingMode.PAPER.value, index=True)

    equity: Mapped[float] = mapped_column(Float)
    realised_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    unrealised_pnl: Mapped[float] = mapped_column(Float, default=0.0)
    exposure: Mapped[float] = mapped_column(Float, default=0.0)
    open_positions: Mapped[int] = mapped_column(Integer, default=0)
    peak_equity: Mapped[float] = mapped_column(Float, default=0.0)
    drawdown_pct: Mapped[float] = mapped_column(Float, default=0.0)


class RiskEvent(Base):
    """A risk decision, warning, halt or kill-switch trip.

    Persisted so the dashboard risk panel and any post-mortem have a full
    record, independent of log files.
    """

    __tablename__ = "risk_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(
        UtcDateTime, default=utcnow, index=True
    )

    event_type: Mapped[str] = mapped_column(String(48), index=True)
    severity: Mapped[str] = mapped_column(String(16), default="info")  # info/warning/critical
    symbol: Mapped[str] = mapped_column(String(32), default="")
    detail: Mapped[str] = mapped_column(Text, default="")
    action_taken: Mapped[str] = mapped_column(String(128), default="")
    #: Portfolio state at the moment of the event, for reconstruction.
    context: Mapped[dict] = mapped_column(JSON, default=dict)


class RejectedSignal(Base):
    """A signal that fired but was not traded, and why.

    Recording rejections matters: "the strategy did nothing for a week" has very
    different implications if the cause was no signals versus every signal being
    blocked by a risk limit.
    """

    __tablename__ = "rejected_signals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(
        UtcDateTime, default=utcnow, index=True
    )
    symbol: Mapped[str] = mapped_column(String(32), index=True)
    side: Mapped[str] = mapped_column(String(8))
    strategy: Mapped[str] = mapped_column(String(64), default="")
    signal_score: Mapped[float] = mapped_column(Float, default=0.0)
    verdict: Mapped[str] = mapped_column(String(24), default="")
    reasons: Mapped[list] = mapped_column(JSON, default=list)
