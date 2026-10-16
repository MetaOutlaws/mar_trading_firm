"""Flat 0.31% charge on every leg-trade, expressed through CostModel.

The cell charges 0.31% of that coin's notional on every entry, every exit
and every stop. Fills stay at the next open. Funding is not added on top.

The pinned ``research.costs.CostModel`` (``COST_MODEL_VERSION``,
bybit-linear-v1) cannot say that:

* ``taker_fee`` defaults to 0.055% and ``slippage`` to 0.10%.
* ``round_trip_cost_pct()`` is ``2 * (taker_fee + slippage)`` = 0.31% for a
  *round trip*, which is 0.155% per side.
* Slippage is collected by moving the fill in ``entry_price`` / ``exit_price``,
  so using it would leave next_open.
* ``fee_for`` charges only the fee, not the slippage.
* There is no flat per-leg rate and no way to turn funding off on a single
  call without a second instance.

``core/execution/replay.py`` (the in-repo paper replay; there is no
``oi_funding_z`` replay in this checkout) applies ``entry_price``,
``exit_price`` and ``fee_for`` on the engine fill. That is the right shape
for a fee-plus-slippage round trip and the wrong shape for a flat 0.31%
cash charge that must not move the fill.

``LegCost`` is the explicit wrap. It keeps the pinned class, builds an
instance whose ``taker_fee`` is 0.0031 and whose slippage and funding are
off, and charges ``CostModel.fee_for``. It never calls ``entry_price`` or
``exit_price``. ``for_symbol`` is not used: sector slippage would make the
rate depend on the coin, and the cell's rate does not.
"""

from __future__ import annotations

from research.costs import COST_MODEL_VERSION, DEFAULT_COSTS, CostModel

#: 0.31% of notional, once per entry, exit or stop.
LEG_COST_RATE = 0.0031


def leg_cost_model() -> CostModel:
    """CostModel instance that expresses the cell's flat per-leg rate.

    The pinned default schedule is intentionally not this instance. The
    version stamp on the default model is still recorded in the run manifest.
    """
    return CostModel(
        taker_fee=LEG_COST_RATE,
        maker_fee=LEG_COST_RATE,
        slippage=0.0,
        include_funding=False,
        default_funding_rate=DEFAULT_COSTS.default_funding_rate,
    )


def charge_leg(notional: float, model: CostModel | None = None) -> float:
    """Cash cost of one leg-trade. Positive. Does not move a fill."""
    charging = model or leg_cost_model()
    return float(charging.fee_for(notional, maker=False))


def cost_snapshot() -> dict[str, object]:
    """What a run charged, and the pinned schedule it did not apply to fills."""
    return {
        "pinned_cost_model_version": COST_MODEL_VERSION,
        "pinned_default_schedule": DEFAULT_COSTS.snapshot(),
        "cell_rate_per_leg_trade": LEG_COST_RATE,
        "charged_via": "CostModel.fee_for",
        "slippage_applied_to_fill": False,
        "funding_included": False,
        "for_symbol_used": False,
        "wrap": (
            "CostModel has no flat 0.31% per-leg field. Default "
            "round_trip_cost_pct is 0.31% per round trip (0.155% per side) "
            "and collects slippage by moving the fill. LegCost sets "
            "taker_fee=0.0031, slippage=0, include_funding=False and calls "
            "fee_for. Fills stay at next_open."
        ),
    }
