"""Constants and params for two_bar_run_mid_fail (Option B)."""

from __future__ import annotations

from dataclasses import dataclass

from core.strategy.base import SignalSide, StrategyParams

ATR_N_LOCKED = 20
# TWO same-color consecutive closes + monotonic run; fade through TWO-BAR
# envelope mid. FORBID extreme_frac (Job 165 territory). FORBID single-bar mid.
REQUIRE_TWO_SAME_COLOR_LOCKED = True
REQUIRE_MONOTONIC_RUN_LOCKED = True
REQUIRE_TWO_BAR_ENVELOPE_MID_LOCKED = True
FORBID_EXTREME_FRAC_LOCKED = True
FORBID_SINGLE_BAR_MID_LOCKED = True
OPTION_B_LOCKED = True

# Free ≤2 (only one free). Endpoints only.
MIN_RANGE_ATR_MIN = 1.0
MIN_RANGE_ATR_MAX = 1.5
MIN_RANGE_ATR_GRID = [1.0, 1.5]


@dataclass(frozen=True)
class TwoBarRunMidFailParams(StrategyParams):
    side: SignalSide = SignalSide.SHORT
    atr_n: int = ATR_N_LOCKED
    min_range_atr: float = MIN_RANGE_ATR_MIN
    require_two_same_color: bool = REQUIRE_TWO_SAME_COLOR_LOCKED
    require_monotonic_run: bool = REQUIRE_MONOTONIC_RUN_LOCKED
    require_two_bar_envelope_mid: bool = REQUIRE_TWO_BAR_ENVELOPE_MID_LOCKED
    forbid_extreme_frac: bool = FORBID_EXTREME_FRAC_LOCKED
    forbid_single_bar_mid: bool = FORBID_SINGLE_BAR_MID_LOCKED
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


__all__ = [
    "ATR_N_LOCKED",
    "FORBID_EXTREME_FRAC_LOCKED",
    "FORBID_SINGLE_BAR_MID_LOCKED",
    "MIN_RANGE_ATR_GRID",
    "MIN_RANGE_ATR_MAX",
    "MIN_RANGE_ATR_MIN",
    "OPTION_B_LOCKED",
    "REQUIRE_MONOTONIC_RUN_LOCKED",
    "REQUIRE_TWO_BAR_ENVELOPE_MID_LOCKED",
    "REQUIRE_TWO_SAME_COLOR_LOCKED",
    "TwoBarRunMidFailParams",
]


def _register_option_b_wire() -> None:
    try:
        from firm.two_bar_run_mid_fail_wire import apply

        apply()
    except Exception:
        # Registry import can precede firm package init in some harnesses.
        pass


_register_option_b_wire()
