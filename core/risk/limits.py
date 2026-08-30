"""
Risk limits: the numbers that bound every trade.

The legacy project *declared* `MAX_POSITIONS = 5` and `MAX_DAILY_TRADES = 30`
and then never checked either one. Declaring a limit without enforcing it is
worse than having no limit, because it creates false confidence. Every field
here is enforced in `core/risk/engine.py` and covered by a test that proves the
enforcement happens.

Defaults are sized for the plan's initial live capital of $1-5k and are
deliberately tight. They can be loosened later on evidence, never on optimism.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class RiskLimits:
    """Hard bounds on portfolio and per-trade risk.

    Frozen so limits cannot be mutated at runtime. Loosening them requires a
    deliberate config change and a restart, not an in-flight decision by an
    agent or a stray assignment.
    """

    # -- position count ----------------------------------------------------
    max_concurrent_positions: int = 5
    max_daily_trades: int = 20

    #: Positions sharing a narrative sector. Crypto correlations spike toward 1
    #: in a selloff, so five "diversified" alt longs is really one leveraged bet.
    max_positions_per_sector: int = 2

    #: One position per symbol. No pyramiding, no hedged duplicates.
    max_positions_per_symbol: int = 1

    # -- sizing ------------------------------------------------------------
    #: Notional of a single position as a fraction of equity.
    max_position_pct: float = 0.10

    #: Combined notional across all open positions, as a fraction of equity.
    #: Below 1.0 means the account is never fully committed.
    max_total_exposure_pct: float = 0.50

    #: Equity fraction lost if a stop is hit. This, not notional, is the real
    #: risk measure: a 10% position with a 5% stop risks 0.5% of equity.
    max_risk_per_trade_pct: float = 0.01

    #: Exchange minimum order value; smaller orders are rejected outright.
    min_notional_usdt: float = 5.0

    #: Leverage cap. 1.0 = unlevered. Raising this multiplies both edge and ruin.
    max_leverage: float = 1.0

    # -- loss limits -------------------------------------------------------
    #: Realised loss in one UTC day that halts new entries until tomorrow.
    daily_loss_limit_pct: float = 0.03

    #: Peak-to-trough equity decline that trips the kill switch permanently
    #: until a human resets it.
    max_drawdown_pct: float = 0.15

    #: Consecutive losses that trigger a cool-down. Usually a sign the regime
    #: has changed rather than that the next trade is due to win.
    max_consecutive_losses: int = 6

    # -- stop discipline ---------------------------------------------------
    #: Every position must carry a stop. A trade without one has unbounded loss.
    require_stop_loss: bool = True

    #: Sanity bounds on stop distance. A 0.1% stop is noise; a 30% stop is not
    #: a stop.
    min_stop_distance_pct: float = 0.005
    max_stop_distance_pct: float = 0.15

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def describe(self) -> list[str]:
        """Human-readable limit list for the dashboard risk panel."""
        return [
            f"Max {self.max_concurrent_positions} concurrent positions",
            f"Max {self.max_daily_trades} trades per day",
            f"Max {self.max_positions_per_sector} positions per sector",
            f"Max {self.max_position_pct:.0%} of equity per position",
            f"Max {self.max_total_exposure_pct:.0%} total exposure",
            f"Max {self.max_risk_per_trade_pct:.1%} equity risk per trade",
            f"Halt new entries after {self.daily_loss_limit_pct:.1%} daily loss",
            f"Kill switch at {self.max_drawdown_pct:.0%} drawdown",
            f"Cool down after {self.max_consecutive_losses} consecutive losses",
            f"Max leverage {self.max_leverage:g}x",
        ]


#: Limits used in paper mode. Identical to live: paper trading is only useful as
#: a forward test if it operates under the same constraints.
PAPER_LIMITS = RiskLimits()

#: Starting limits for first live capital. Half the paper exposure, because the
#: first weeks of real trading are for discovering execution surprises, not for
#: maximising return.
INITIAL_LIVE_LIMITS = RiskLimits(
    max_concurrent_positions=3,
    max_daily_trades=10,
    max_position_pct=0.05,
    max_total_exposure_pct=0.20,
    max_risk_per_trade_pct=0.005,
    daily_loss_limit_pct=0.02,
    max_drawdown_pct=0.10,
)
