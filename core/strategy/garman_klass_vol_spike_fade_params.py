"""Constants and params for garman_klass_vol_spike_fade (Option B)."""

from __future__ import annotations

from dataclasses import dataclass

from core.strategy.base import SignalSide, StrategyParams

# Free ≤2. Endpoints only.
LOOKBACK_MIN = 20
LOOKBACK_MAX = 40
LOOKBACK_GRID = [20, 40]
Z_MIN_MIN = 2.0
Z_MIN_MAX = 2.5
Z_MIN_GRID = [2.0, 2.5]

# Locked geometry / Option B guards.
EPS_LOCKED = 1e-12
FADE_SPIKE_BAR_BODY_LOCKED = True
CAUSAL_Z_PRIOR_LOOKBACK_LOCKED = True
FORBID_EXTREME_FRAC_LOCKED = True
FORBID_NEXT_THRU_MID_LOCKED = True
FORBID_CLV_LOCKED = True
FORBID_VOLUME_IN_SIGNAL_LOCKED = True
FORBID_WICK_FRAC_LOCKED = True
FORBID_DONCHIAN_LOCKED = True
FORBID_COMPRESSION_LOCKED = True
OHLC_ONLY_GARMAN_KLASS_LOCKED = True
OPTION_B_LOCKED = True


@dataclass(frozen=True)
class GarmanKlassVolSpikeFadeParams(StrategyParams):
    side: SignalSide = SignalSide.SHORT
    lookback: int = LOOKBACK_MIN
    z_min: float = Z_MIN_MIN
    fade_spike_bar_body: bool = FADE_SPIKE_BAR_BODY_LOCKED
    causal_z_prior_lookback: bool = CAUSAL_Z_PRIOR_LOOKBACK_LOCKED
    forbid_extreme_frac: bool = FORBID_EXTREME_FRAC_LOCKED
    forbid_next_thru_mid: bool = FORBID_NEXT_THRU_MID_LOCKED
    forbid_clv: bool = FORBID_CLV_LOCKED
    forbid_volume_in_signal: bool = FORBID_VOLUME_IN_SIGNAL_LOCKED
    forbid_wick_frac: bool = FORBID_WICK_FRAC_LOCKED
    forbid_donchian: bool = FORBID_DONCHIAN_LOCKED
    forbid_compression: bool = FORBID_COMPRESSION_LOCKED
    ohlc_only_garman_klass: bool = OHLC_ONLY_GARMAN_KLASS_LOCKED
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


__all__ = [
    "GarmanKlassVolSpikeFadeParams",
    "CAUSAL_Z_PRIOR_LOOKBACK_LOCKED",
    "EPS_LOCKED",
    "FADE_SPIKE_BAR_BODY_LOCKED",
    "FORBID_CLV_LOCKED",
    "FORBID_COMPRESSION_LOCKED",
    "FORBID_DONCHIAN_LOCKED",
    "FORBID_EXTREME_FRAC_LOCKED",
    "FORBID_NEXT_THRU_MID_LOCKED",
    "FORBID_VOLUME_IN_SIGNAL_LOCKED",
    "FORBID_WICK_FRAC_LOCKED",
    "LOOKBACK_GRID",
    "LOOKBACK_MAX",
    "LOOKBACK_MIN",
    "OHLC_ONLY_GARMAN_KLASS_LOCKED",
    "OPTION_B_LOCKED",
    "Z_MIN_GRID",
    "Z_MIN_MAX",
    "Z_MIN_MIN",
]


def _register_option_b_wire() -> None:
    try:
        from firm.garman_klass_vol_spike_fade_wire import apply

        apply()
    except Exception:
        # Registry import can precede firm package init in some harnesses.
        pass


_register_option_b_wire()
