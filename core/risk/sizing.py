"""Position notional shared by the hourly risk engine and the BL8 paper observer.

The isolated BL8 release imports this module and ``limits.py`` only. It does not
import the kill switch, settings, or the hourly trading engine.
"""

from __future__ import annotations

from core.risk.limits import RiskLimits


def size_position(
    *,
    equity: float,
    stop_distance_pct: float,
    entry_price: float,
    total_exposure: float,
    limits: RiskLimits,
) -> tuple[float, float, float, list[str], bool]:
    """Notional is the minimum of the four PAPER_LIMITS caps.

    ``RiskEngine._size_position`` delegates here so a new cap can only shrink a
    position. The same call sizes BL8 paper entries.

    Caps, smallest wins:
      - risk budget: equity * max_risk_per_trade_pct / stop distance
      - single position: equity * max_position_pct
      - exposure room: equity * max_total_exposure_pct - open exposure
      - leverage: equity * max_leverage
    """
    notes: list[str] = []

    # Cap 1: equity lost if the stop fills. A tighter stop raises this notional.
    risk_budget = equity * limits.max_risk_per_trade_pct
    stop_distance = stop_distance_pct
    risk_based_notional = risk_budget / stop_distance if stop_distance > 0 else 0.0

    # Cap 2: single-position notional cap.
    position_cap = equity * limits.max_position_pct

    # Cap 3: remaining room under the total exposure cap.
    exposure_room = max(0.0, equity * limits.max_total_exposure_pct - total_exposure)

    # Cap 4: leverage ceiling. 1x means notional cannot exceed equity.
    leverage_cap = equity * limits.max_leverage

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

    quantity = notional / entry_price if entry_price > 0 else 0.0
    risk_amount = notional * stop_distance

    return quantity, notional, risk_amount, notes, reduced
