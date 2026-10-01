"""Constants and params for broken_swing_retest_reject (Option B)."""

from __future__ import annotations

from dataclasses import dataclass

from core.strategy.base import SignalSide, StrategyParams

ATR_N_LOCKED = 20
# Pivot lock: confirmed swing = max/min of prior swing_lookback bars excluding
# signal bar t (causal shift(1).rolling). Not a hard 3/3 fractal helper — no
# shared pivot helper in repo; keep 3/3 noted as the stamp lock name.
PIVOT_33_LOCKED = True
REQUIRE_REJECT_CLOSE_LOCKED = True
CONTINUATION_ONLY_LOCKED = True
FORBID_CLOSE_THROUGH_SWING_LOCKED = True
REQUIRE_PRIOR_CLOSE_BREAK_LOCKED = True
OPTION_B_LOCKED = True

SWING_LOOKBACK_MIN = 5
SWING_LOOKBACK_MAX = 8
SWING_LOOKBACK_GRID = [5, 8]

RETEST_BARS_MIN = 3
RETEST_BARS_MAX = 6
RETEST_BARS_GRID = [3, 6]


@dataclass(frozen=True)
class BrokenSwingRetestRejectParams(StrategyParams):
    side: SignalSide = SignalSide.SHORT
    atr_n: int = ATR_N_LOCKED
    swing_lookback: int = SWING_LOOKBACK_MIN
    retest_bars: int = RETEST_BARS_MIN
    require_reject_close: bool = REQUIRE_REJECT_CLOSE_LOCKED
    continuation_only: bool = CONTINUATION_ONLY_LOCKED
    forbid_close_through_swing: bool = FORBID_CLOSE_THROUGH_SWING_LOCKED
    require_prior_close_break: bool = REQUIRE_PRIOR_CLOSE_BREAK_LOCKED
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


__all__ = [
    "ATR_N_LOCKED",
    "CONTINUATION_ONLY_LOCKED",
    "FORBID_CLOSE_THROUGH_SWING_LOCKED",
    "OPTION_B_LOCKED",
    "PIVOT_33_LOCKED",
    "REQUIRE_PRIOR_CLOSE_BREAK_LOCKED",
    "REQUIRE_REJECT_CLOSE_LOCKED",
    "RETEST_BARS_GRID",
    "RETEST_BARS_MAX",
    "RETEST_BARS_MIN",
    "SWING_LOOKBACK_GRID",
    "SWING_LOOKBACK_MAX",
    "SWING_LOOKBACK_MIN",
    "BrokenSwingRetestRejectParams",
]


def _register_option_b_wire() -> None:
    try:
        from firm.broken_swing_retest_reject_wire import apply

        apply()
    except Exception:
        # Registry import can precede firm package init in some harnesses.
        pass


_register_option_b_wire()
