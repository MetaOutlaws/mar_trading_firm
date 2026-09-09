"""Keltner channel fade — wick tags EMA±ATR, close rejects back inside. BOTH.

This is a same-bar FADE / reject-inside edge. It is not a Keltner breakout
(``keltner_break`` closes *through* a prior typical-price envelope).

    mid   = EMA(20) of close
    bands = mid ± k * ATR(20)

ATR is Wilder ATR(20) known *before* the signal bar (``atr.shift(1)``) so
bar ``t`` cannot widen its own hurdle. Mid updates with close[t] — causal
at signal time. Quant-locked strict tag (not ``>=`` / ``<=``):

    SHORT: high[t] > upper[t] AND close[t] < upper[t]
    LONG:  low[t]  < lower[t] AND close[t] > lower[t]

The engine fills at ``t+1`` open.

Quant-locked (not searched):

    - EMA period = 20 (of close, not typical price)
    - ATR period = 20
    - require close back inside the tagged band
    - SHORT = upper reject; LONG = lower reject

Free search (1 only):

    - ``k`` (ATR-width multiplier) grid ``[1.5, 2.0]``

OHLCV only. Causal: bars ``<= t``. No volume / bandwidth / session overlay.

Not ``keltner_break`` (close-through typical-price Keltner, ATR10 default).
Not ``sma20_stretch_fade`` (SMA wick stretch + halfway reclaim, not EMA±ATR).
Not ``bb_medium_bw_upper_reject`` (Bollinger + medium-BW gate).
Not ``outside_bar_fail_reversion`` (next-bar close inside an outside bar).
Not ``three_black_crows`` / ``three_white_soldiers``.
Not ``atr_open_flush_fade`` / ``utc_day_open_flush_fade``.
Not ``failed_break_reclaim`` / ``expansion_fail_fade`` / ``candle_reject_reversal``.
Not ``ib_fail`` / ``nr7_fail`` / ``engulfing_fail``.
Not ``asia_range_london_reject`` / ``prior_day_extreme_reject``.
Not ``displacement_gap_follow`` (PARKED — do not code / revive).
Not ``range_compression_volume_thrust`` / inventory fades.
Do not recode spent families 118–142. Do not modify sibling geometry.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams

# Locked EMA / ATR windows. Walk-forward searches k only.
EMA_N_LOCKED = 20
ATR_N_LOCKED = 20
# Quant-locked True: fade only if close rejects back inside the tagged band.
REQUIRE_CLOSE_INSIDE_LOCKED = True


@dataclass(frozen=True)
class KeltnerChannelFadeParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    # EMA of close. Quant-locked at 20 — not a free search param.
    ema_n: int = EMA_N_LOCKED
    # Wilder ATR period. Quant-locked at 20 — not a free search param.
    atr_n: int = ATR_N_LOCKED
    # Band width in ATR units. Quant grid: [1.5, 2.0].
    k: float = 1.5
    # Quant-locked True: require close back inside the tagged band.
    require_close_inside: bool = REQUIRE_CLOSE_INSIDE_LOCKED
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class KeltnerChannelFadeStrategy(Strategy):
    name = "keltner_channel_fade"

    def __init__(self, params: KeltnerChannelFadeParams | None = None) -> None:
        super().__init__(params or KeltnerChannelFadeParams())
        self.params: KeltnerChannelFadeParams = self.params
        # EMA/ATR seed plus one bar so the width is the *prior* ATR print.
        self.min_bars = max(EMA_N_LOCKED, ATR_N_LOCKED) + 2

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        high = candles["high"]
        low = candles["low"]
        close = candles["close"]
        # Searched k stays caller-set. Periods / close-inside stay locked
        # even if a caller tries to override them on the params object.
        k = float(params.k)
        ema_n = EMA_N_LOCKED
        atr_n = ATR_N_LOCKED

        # Mid is EMA of close — not typical (H+L+C)/3 used by keltner_break.
        mid = ind.ema(close, ema_n)
        atr20 = ind.atr(high, low, close, atr_n)
        # ATR known before the signal bar — the tag wick cannot lift the band.
        atr_known = atr20.shift(1)
        atr_ok = atr_known.gt(0)
        atr_safe = atr_known.replace(0, pd.NA)
        width = k * atr_safe
        upper = mid + width
        lower = mid - width

        # Strict tag (Quant lock). A print sitting exactly on the band is not a tag.
        tagged_upper = atr_ok & high.gt(upper)
        tagged_lower = atr_ok & low.lt(lower)
        # Reject-inside: close back across the tagged band. Locked even if
        # a caller passes require_close_inside=False.
        closed_inside_upper = close.lt(upper)
        closed_inside_lower = close.gt(lower)

        short_raw = tagged_upper & closed_inside_upper
        long_raw = tagged_lower & closed_inside_lower

        signals["keltner_mid"] = mid
        signals["keltner_upper"] = upper
        signals["keltner_lower"] = lower
        signals["atr"] = atr20
        signals["atr_known"] = atr_known
        signals["tagged_upper"] = tagged_upper.fillna(False)
        signals["tagged_lower"] = tagged_lower.fillna(False)
        signals["closed_inside_upper"] = closed_inside_upper.fillna(False)
        signals["closed_inside_lower"] = closed_inside_lower.fillna(False)

        if params.side is SignalSide.SHORT:
            entry = short_raw
            signal_value, side_value = -1, SignalSide.SHORT.value
        elif params.side is SignalSide.LONG:
            entry = long_raw
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            entry = pd.Series(False, index=candles.index)
            signal_value, side_value = 0, SignalSide.FLAT.value

        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        if signal_value != 0:
            signals.loc[entry, "signal"] = signal_value
            signals.loc[entry, "side"] = side_value
            # Stronger when the wick tags further through the band.
            if params.side is SignalSide.SHORT:
                depth = ((high - upper) / width).clip(0.0, 1.0)
            else:
                depth = ((lower - low) / width).clip(0.0, 1.0)
            signals.loc[entry, "score"] = depth.fillna(0.0)[entry]
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any() and signal_value != 0:
            band = upper if params.side is SignalSide.SHORT else lower
            reasons.loc[entry] = [
                (
                    f"{side_value}: Keltner fade-reject close {close.loc[i]:.4f} "
                    f"band {band.loc[i]:.4f} mid {mid.loc[i]:.4f} "
                    f"atr {atr_known.loc[i]:.4f} k={k:.2f}"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = [
    "ATR_N_LOCKED",
    "EMA_N_LOCKED",
    "REQUIRE_CLOSE_INSIDE_LOCKED",
    "KeltnerChannelFadeParams",
    "KeltnerChannelFadeStrategy",
]
