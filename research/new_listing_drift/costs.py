"""Two cash cost levels, both expressed through CostModel.

The official level binds every hard gate. The measured level is a report
column and a sign-flip veto. Neither level moves a fill: slippage stays
off, and ``entry_price`` / ``exit_price`` are never called.

Funding is not charged here. The pinned CostModel would fall back to a
default rate when history is missing, and this cell forbids that fill.
Funding is summed from the tape in the engine, or the trade is flagged.

Official, from the LOCK and the prereg:
    0.31% of each leg's notional for that leg's entry+exit round trip.
    Two legs, so 0.62% of one-leg notional per spread trade.

Measured, report only, labelled "proxy, unmeasured for listings":
    BTC leg 0.135% (sampler conservative p90) plus listing leg 0.181%
    (SOL conservative, a floor proxy). That is 0.316% per spread.
    No measured figure exists for a new listing. A measured-level result
    cannot rescue a FAIL at 0.31%.
"""

from __future__ import annotations

from research.costs import COST_MODEL_VERSION, DEFAULT_COSTS, CostModel

#: 0.31% of one leg's notional, once for that leg's entry and exit together.
OFFICIAL_LEG_RATE = 0.0031

#: Sampler conservative round trips. Listing names were not in the sample.
MEASURED_BTC_LEG_RATE = 0.00135
MEASURED_LISTING_LEG_RATE = 0.00181

MEASURED_LABEL = "proxy, unmeasured for listings"


def _model(rate: float) -> CostModel:
    """A CostModel whose taker fee is ``rate`` and which does not move fills.

    ``include_funding`` is false so ``funding_cost`` cannot substitute the
    default rate. Callers still must not call ``funding_cost``.
    """
    return CostModel(
        taker_fee=rate,
        maker_fee=rate,
        slippage=0.0,
        include_funding=False,
        default_funding_rate=DEFAULT_COSTS.default_funding_rate,
    )


def official_leg_model() -> CostModel:
    return _model(OFFICIAL_LEG_RATE)


def measured_btc_model() -> CostModel:
    return _model(MEASURED_BTC_LEG_RATE)


def measured_listing_model() -> CostModel:
    return _model(MEASURED_LISTING_LEG_RATE)


def _fee(model: CostModel, notional: float = 1.0) -> float:
    """Cash cost as a fraction of one-leg notional. Does not move a fill."""
    return float(model.fee_for(notional, maker=False))


def official_spread_cost(notional: float = 1.0) -> float:
    """0.31% on the listing leg plus 0.31% on the BTC leg."""
    model = official_leg_model()
    return _fee(model, notional) + _fee(model, notional)


def measured_spread_cost(notional: float = 1.0) -> float:
    """BTC conservative round trip plus the SOL proxy on the listing leg."""
    return _fee(measured_btc_model(), notional) + _fee(measured_listing_model(), notional)


def cost_snapshot() -> dict[str, object]:
    """What a run charges, and the pinned schedule it does not apply to fills."""
    official = official_spread_cost()
    measured = measured_spread_cost()
    return {
        "pinned_cost_model_version": COST_MODEL_VERSION,
        "pinned_default_schedule": DEFAULT_COSTS.snapshot(),
        "charged_via": "CostModel.fee_for",
        "slippage_applied_to_fill": False,
        "funding_charged_by_cost_model": False,
        "for_symbol_used": False,
        "official": {
            "binds_gates": True,
            "per_leg_round_trip": OFFICIAL_LEG_RATE,
            "per_spread": official,
            "note": "0.31% per leg-trade (entry+exit) = 0.62% per spread",
        },
        "measured_proxy": {
            "binds_gates": False,
            "report_only": True,
            "sign_veto": True,
            "can_rescue_a_fail": False,
            "label": MEASURED_LABEL,
            "btc_leg_round_trip": MEASURED_BTC_LEG_RATE,
            "listing_leg_round_trip": MEASURED_LISTING_LEG_RATE,
            "per_spread": measured,
        },
        "wrap": (
            "CostModel has no flat per-leg field. Default round_trip_cost_pct "
            "is 0.31% per round trip (0.155% per side) and collects slippage "
            "by moving the fill. Each level builds a CostModel with taker_fee "
            "set to that level's per-leg rate, slippage 0, include_funding "
            "false, and calls fee_for once per leg. Fills stay at the open. "
            "Funding is applied from the tape and is never taken from "
            "CostModel.funding_cost."
        ),
    }
