"""Constants and params for body_gap_fail_reversion (Option B)."""

from __future__ import annotations

from dataclasses import dataclass

from core.strategy.base import SignalSide, StrategyParams

ATR_N_LOCKED = 20
REQUIRE_CLOSE_RECLAIM_INSIDE_LOCKED = True
FORBID_FOLLOW_CONTINUATION_LOCKED = True
OPTION_B_LOCKED = True
MIN_GAP_ATR_MIN = 0.10
MIN_GAP_ATR_MAX = 0.25
MIN_GAP_ATR_GRID = [0.10, 0.25]
MIN_PRIOR_RANGE_ATR_MIN = 0.5
MIN_PRIOR_RANGE_ATR_MAX = 1.0
MIN_PRIOR_RANGE_ATR_GRID = [0.5, 1.0]


@dataclass(frozen=True)
class BodyGapFailReversionParams(StrategyParams):
    side: SignalSide = SignalSide.SHORT
    atr_n: int = ATR_N_LOCKED
    min_gap_atr: float = MIN_GAP_ATR_MIN
    min_prior_range_atr: float = MIN_PRIOR_RANGE_ATR_MIN
    require_close_reclaim_inside: bool = REQUIRE_CLOSE_RECLAIM_INSIDE_LOCKED
    forbid_follow_continuation: bool = FORBID_FOLLOW_CONTINUATION_LOCKED
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


__all__ = [
    "ATR_N_LOCKED",
    "FORBID_FOLLOW_CONTINUATION_LOCKED",
    "MIN_GAP_ATR_GRID",
    "MIN_GAP_ATR_MAX",
    "MIN_GAP_ATR_MIN",
    "MIN_PRIOR_RANGE_ATR_GRID",
    "MIN_PRIOR_RANGE_ATR_MAX",
    "MIN_PRIOR_RANGE_ATR_MIN",
    "OPTION_B_LOCKED",
    "REQUIRE_CLOSE_RECLAIM_INSIDE_LOCKED",
    "BodyGapFailReversionParams",
]


def _register_option_b_wire() -> None:
    try:
        from firm.body_gap_fail_reversion_wire import apply
        apply()
    except Exception:
        # Registry import can precede firm package init in some harnesses.
        pass


_register_option_b_wire()
