"""0.31% of notional on every one-way leg-trade, via CostModel.fee_for.

The pinned CostModel has no flat per-leg field. Its default round trip is
0.31% including slippage, and slippage moves the fill. This wrap sets
taker_fee to the cell rate, turns slippage and funding off, and calls
``fee_for``. Fills stay at the open the prereg names.

The 0.158% column uses the same wrap. It is report-only.
"""

from __future__ import annotations

from research.costs import COST_MODEL_VERSION, DEFAULT_COSTS, CostModel
from research.xs_crowd_lsr_contrarian.pins import (
    OFFICIAL_LEG_COST,
    PROXY_COST_LABEL,
    PROXY_LEG_COST,
)


def leg_cost_model(rate: float) -> CostModel:
    """CostModel that charges ``rate`` once per leg-trade and does not move a fill."""
    return CostModel(
        taker_fee=rate,
        maker_fee=rate,
        slippage=0.0,
        include_funding=False,
        default_funding_rate=DEFAULT_COSTS.default_funding_rate,
    )


def charge_leg(notional: float, rate: float = OFFICIAL_LEG_COST) -> float:
    """Cash cost of one leg-trade. Positive. Does not move a fill."""
    return float(leg_cost_model(rate).fee_for(notional, maker=False))


def cost_snapshot() -> dict[str, object]:
    """What a run charges, and the pinned schedule it does not apply to fills."""
    return {
        "pinned_cost_model_version": COST_MODEL_VERSION,
        "pinned_default_schedule": DEFAULT_COSTS.snapshot(),
        "official_rate_per_leg_trade": OFFICIAL_LEG_COST,
        "official_binds_gates": True,
        "proxy_rate_per_leg_trade": PROXY_LEG_COST,
        "proxy_label": PROXY_COST_LABEL,
        "proxy_binds_gates": False,
        "proxy_sign_flip_is_a_veto": True,
        "charged_via": "CostModel.fee_for",
        "slippage_applied_to_fill": False,
        "funding_from_cost_model": False,
        "for_symbol_used": False,
        "wrap": (
            "CostModel has no flat per-leg field. LegCost sets taker_fee to "
            "the cell rate, slippage to 0, include_funding to False, and calls "
            "fee_for. Fills stay at next_open. The proxy rate is the mean of "
            "BTC 0.135% and SOL 0.181% and is labelled as a proxy."
        ),
    }
