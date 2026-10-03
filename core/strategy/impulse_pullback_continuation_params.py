"""Constants and params for impulse_pullback_continuation (Option B)."""

from __future__ import annotations

from dataclasses import dataclass

from core.strategy.base import SignalSide, StrategyParams

# Free ≤2. Endpoints only (Garwe Eng free set).
PULLBACK_MAX_RETRACE_FRAC_MIN = 0.38
PULLBACK_MAX_RETRACE_FRAC_MAX = 0.50
PULLBACK_MAX_RETRACE_FRAC_GRID = [0.38, 0.50]
IMPULSE_MIN_CLOSE_PCT_MIN = 1.5
IMPULSE_MIN_CLOSE_PCT_MAX = 2.0
IMPULSE_MIN_CLOSE_PCT_GRID = [1.5, 2.0]

# Locked geometry / Option B guards (≠ Job 165 mid-fail fade).
IMPULSE_WINDOW_BARS_LOCKED = 2
PULLBACK_MAX_BARS_LOCKED = 4
SMA_PERIOD_LOCKED = 200
REGIME_GATE_ALIGNED_200SMA_LOCKED = True
MID_ANCHOR_LOCKED = False
FAIL_OF_IMPULSE_LOCKED = False
FORBID_SIGNAL_CLOSE_FILL_LOCKED = True
FORBID_SMA20_STRETCH_FADE_LOCKED = True
FORBID_THREE_BLACK_CROWS_ENTRY_LOCKED = True
FORBID_MIDPOINT_FAIL_FADE_LOCKED = True
OPTION_B_LOCKED = True
# BOTH book side; LONG priority on same-bar conflict (JSON priority + Brian BOTH).
PRIORITY_LONG_ON_CONFLICT_LOCKED = True
# Shell defaults (Munha stamp cell M3/S1.5/H18 next_open).
TAKE_PROFIT_PCT_LOCKED_DEFAULT = 0.03
STOP_LOSS_PCT_LOCKED_DEFAULT = 0.015
MAX_HOLDING_BARS_LOCKED = 18
STOP_LOSS_PCT_GRID = [0.015, 0.02]
TAKE_PROFIT_PCT_GRID = [0.03]


@dataclass(frozen=True)
class ImpulsePullbackContinuationParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    impulse_window_bars: int = IMPULSE_WINDOW_BARS_LOCKED
    impulse_min_close_pct: float = IMPULSE_MIN_CLOSE_PCT_MIN
    pullback_max_retrace_frac: float = PULLBACK_MAX_RETRACE_FRAC_MAX
    pullback_max_bars: int = PULLBACK_MAX_BARS_LOCKED
    mid_anchor: bool = MID_ANCHOR_LOCKED
    fail_of_impulse: bool = FAIL_OF_IMPULSE_LOCKED
    forbid_signal_close_fill: bool = FORBID_SIGNAL_CLOSE_FILL_LOCKED
    regime_gate_aligned_200sma: bool = REGIME_GATE_ALIGNED_200SMA_LOCKED
    priority_long_on_conflict: bool = PRIORITY_LONG_ON_CONFLICT_LOCKED
    take_profit_pct: float = TAKE_PROFIT_PCT_LOCKED_DEFAULT
    stop_loss_pct: float = STOP_LOSS_PCT_LOCKED_DEFAULT
    max_holding_bars: int = MAX_HOLDING_BARS_LOCKED


__all__ = [
    "ImpulsePullbackContinuationParams",
    "FAIL_OF_IMPULSE_LOCKED",
    "FORBID_MIDPOINT_FAIL_FADE_LOCKED",
    "FORBID_SIGNAL_CLOSE_FILL_LOCKED",
    "FORBID_SMA20_STRETCH_FADE_LOCKED",
    "FORBID_THREE_BLACK_CROWS_ENTRY_LOCKED",
    "IMPULSE_MIN_CLOSE_PCT_GRID",
    "IMPULSE_MIN_CLOSE_PCT_MAX",
    "IMPULSE_MIN_CLOSE_PCT_MIN",
    "IMPULSE_WINDOW_BARS_LOCKED",
    "MAX_HOLDING_BARS_LOCKED",
    "MID_ANCHOR_LOCKED",
    "OPTION_B_LOCKED",
    "PRIORITY_LONG_ON_CONFLICT_LOCKED",
    "PULLBACK_MAX_BARS_LOCKED",
    "PULLBACK_MAX_RETRACE_FRAC_GRID",
    "PULLBACK_MAX_RETRACE_FRAC_MAX",
    "PULLBACK_MAX_RETRACE_FRAC_MIN",
    "REGIME_GATE_ALIGNED_200SMA_LOCKED",
    "SMA_PERIOD_LOCKED",
    "STOP_LOSS_PCT_GRID",
    "STOP_LOSS_PCT_LOCKED_DEFAULT",
    "TAKE_PROFIT_PCT_GRID",
    "TAKE_PROFIT_PCT_LOCKED_DEFAULT",
]


def _register_option_b_wire() -> None:
    try:
        from firm.impulse_pullback_continuation_wire import apply

        apply()
    except Exception:
        # Registry import can precede firm package init in some harnesses.
        pass


_register_option_b_wire()
