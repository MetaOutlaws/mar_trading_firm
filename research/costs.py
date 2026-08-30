"""
Transaction cost model for Bybit linear perpetuals.

Three cost components, all of which must be charged for a backtest to mean
anything:

1. **Fees.** Market orders pay the taker fee on both entry and exit.
2. **Slippage.** Market orders fill worse than the quoted price.
3. **Funding.** Perpetuals settle funding every 8 hours. The legacy backtester
   omitted this entirely while holding positions for up to 24 hours, which
   silently flattered every long in a bull market -- precisely the trades it was
   most confident about.

Ignoring any one of these turns a losing strategy into a winning-looking one.
On a 5% take-profit target, round-trip costs of ~0.35% consume about 7% of the
gross win, and considerably more of a marginal edge.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from core.data.funding import DEFAULT_FUNDING_RATE, FundingHistory

logger = logging.getLogger(__name__)

# Bybit linear perpetual fee schedule for a standard (non-VIP) account.
BYBIT_TAKER_FEE = 0.00055  # 0.055%
BYBIT_MAKER_FEE = 0.0002  # 0.02%


@dataclass(frozen=True)
class CostModel:
    """Round-trip cost assumptions for a simulated trade.

    Defaults are deliberately pessimistic. A strategy that only works under
    optimistic cost assumptions does not work.
    """

    taker_fee: float = BYBIT_TAKER_FEE
    maker_fee: float = BYBIT_MAKER_FEE

    #: One-way slippage as a fraction of price. 10 bps is realistic for a
    #: market order in a liquid perp; thin altcoins are worse, which is why
    #: `for_symbol` scales it.
    slippage: float = 0.001

    #: Charge funding. Disable only to isolate its impact in an experiment.
    include_funding: bool = True

    #: Fallback per-8h funding rate when a symbol has no history.
    default_funding_rate: float = DEFAULT_FUNDING_RATE

    # -- entry / exit prices ------------------------------------------------
    def entry_price(self, quoted: float, side: str) -> float:
        """Fill price after slippage. A buyer pays up; a seller sells down."""
        if side.upper() == "LONG":
            return quoted * (1.0 + self.slippage)
        return quoted * (1.0 - self.slippage)

    def exit_price(self, quoted: float, side: str) -> float:
        """Exit fill price after slippage, always in the unfavourable direction."""
        if side.upper() == "LONG":
            return quoted * (1.0 - self.slippage)
        return quoted * (1.0 + self.slippage)

    # -- fees ---------------------------------------------------------------
    def fee_for(self, notional: float, maker: bool = False) -> float:
        """Fee charged on one side of a trade."""
        return abs(notional) * (self.maker_fee if maker else self.taker_fee)

    def round_trip_fees(self, entry_notional: float, exit_notional: float) -> float:
        """Taker fees on both legs."""
        return self.fee_for(entry_notional) + self.fee_for(exit_notional)

    # -- funding ------------------------------------------------------------
    def funding_cost(
        self,
        side: str,
        entry_time: datetime,
        exit_time: datetime,
        notional: float,
        history: FundingHistory | None = None,
    ) -> float:
        """Funding paid over a holding period. Positive means it cost money."""
        if not self.include_funding:
            return 0.0

        if history is not None and not history.rates.empty:
            return history.cost_for_holding(side, entry_time, exit_time, notional)

        # No history: approximate with the baseline rate and elapsed settlements.
        hours = max((exit_time - entry_time).total_seconds() / 3600.0, 0.0)
        settlements = hours / 8.0
        direction = 1.0 if side.upper() == "LONG" else -1.0
        return settlements * self.default_funding_rate * direction * notional

    # -- summary ------------------------------------------------------------
    def round_trip_cost_pct(self) -> float:
        """Approximate round-trip cost as a fraction of notional, funding aside.

        Useful as a sanity check against a strategy's take-profit target: a 5%
        target against a 0.31% round trip keeps ~94% of the gross win.
        """
        return 2.0 * (self.taker_fee + self.slippage)

    def for_symbol(self, symbol: str) -> "CostModel":
        """Return a cost model adjusted for a symbol's expected liquidity.

        Majors fill close to the quote; small-cap and meme perps have wider
        spreads and thinner books, so assuming a single slippage figure across
        the universe systematically overstates altcoin performance.
        """
        from config.universe import get_universe

        sector = get_universe().sector_of(symbol)

        multiplier = {
            "majors": 1.0,
            "layer1": 1.5,
            "layer2": 2.0,
            "defi": 2.0,
            "infra": 2.0,
            "ai": 2.5,
            "gaming": 2.5,
            "memes": 3.0,
            "emerging": 3.0,
        }.get(sector, 2.5)

        return CostModel(
            taker_fee=self.taker_fee,
            maker_fee=self.maker_fee,
            slippage=self.slippage * multiplier,
            include_funding=self.include_funding,
            default_funding_rate=self.default_funding_rate,
        )


#: Baseline assumptions used unless a study overrides them.
DEFAULT_COSTS = CostModel()

#: Zero-cost model. For isolating cost impact in an experiment only -- never a
#: basis for a go-live decision.
FRICTIONLESS = CostModel(taker_fee=0.0, maker_fee=0.0, slippage=0.0, include_funding=False)
