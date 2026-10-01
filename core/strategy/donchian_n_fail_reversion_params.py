"""Constants and params for donchian_n_fail_reversion (Option B)."""

from __future__ import annotations

from dataclasses import dataclass

from core.strategy.base import SignalSide, StrategyParams

ATR_N_LOCKED = 20
# Causal Donchian exclude-t: DHigh/DLow via shift(1).rolling(n).
DONCHIAN_EXCLUDE_T_LOCKED = True
# Same-bar wick pierce beyond DHigh/DLow then close back inside + body confirm.
REQUIRE_WICK_PIERCE_CLOSE_INSIDE_LOCKED = True
# FORBID multi-touch flat band (Job 167), next-thru-mid / extreme_frac / CLV.
FORBID_MULTI_TOUCH_FLAT_BAND_LOCKED = True
FORBID_NEXT_THRU_MID_LOCKED = True
FORBID_EXTREME_FRAC_LOCKED = True
FORBID_CLV_LOCKED = True
OPTION_B_LOCKED = True

# Free ≤2. Endpoints only.
N_MIN = 10
N_MAX = 20
N_GRID = [10, 20]
PIERCE_TOL_ATR_MIN = 0.0
PIERCE_TOL_ATR_MAX = 0.10
PIERCE_TOL_ATR_GRID = [0.0, 0.10]


@dataclass(frozen=True)
class DonchianNFailReversionParams(StrategyParams):
    side: SignalSide = SignalSide.SHORT
    atr_n: int = ATR_N_LOCKED
    n: int = N_MIN
    pierce_tol_atr: float = PIERCE_TOL_ATR_MIN
    donchian_exclude_t: bool = DONCHIAN_EXCLUDE_T_LOCKED
    require_wick_pierce_close_inside: bool = REQUIRE_WICK_PIERCE_CLOSE_INSIDE_LOCKED
    forbid_multi_touch_flat_band: bool = FORBID_MULTI_TOUCH_FLAT_BAND_LOCKED
    forbid_next_thru_mid: bool = FORBID_NEXT_THRU_MID_LOCKED
    forbid_extreme_frac: bool = FORBID_EXTREME_FRAC_LOCKED
    forbid_clv: bool = FORBID_CLV_LOCKED
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


__all__ = [
    "ATR_N_LOCKED",
    "DONCHIAN_EXCLUDE_T_LOCKED",
    "FORBID_CLV_LOCKED",
    "FORBID_EXTREME_FRAC_LOCKED",
    "FORBID_MULTI_TOUCH_FLAT_BAND_LOCKED",
    "FORBID_NEXT_THRU_MID_LOCKED",
    "N_GRID",
    "N_MAX",
    "N_MIN",
    "OPTION_B_LOCKED",
    "PIERCE_TOL_ATR_GRID",
    "PIERCE_TOL_ATR_MAX",
    "PIERCE_TOL_ATR_MIN",
    "REQUIRE_WICK_PIERCE_CLOSE_INSIDE_LOCKED",
    "DonchianNFailReversionParams",
]


def _register_option_b_wire() -> None:
    try:
        from firm.donchian_n_fail_reversion_wire import apply

        apply()
    except Exception:
        # Registry import can precede firm package init in some harnesses.
        pass


_register_option_b_wire()
