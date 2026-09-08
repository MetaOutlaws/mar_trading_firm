"""Fade a failed 4h range-expansion bar on the next close-inside print.

An expansion bar is a single print whose true range exceeds
``expansion_mult * ATR(20)``. ATR is the Wilder average of the 20 bars
*before* that expansion print so the wide bar cannot lift its own
threshold. The fail is the *next* bar: it must close back inside that
expansion bar's high-low, on non-expanding volume.

Quant-locked weak-vol gate: ``volume_t <= mean(volume of the prior 20
bars)``. That lookback is not searched. ``atr_n = 20`` is also locked.
The only free param is ``expansion_mult`` (grid ``[1.5, 2.0]``).

Fade toward the expansion bar's midpoint, both sides:

- SHORT if the expansion closed on the high side of its midpoint
  (up expansion failed to hold).
- LONG if the expansion closed on the low side (down expansion failed).

OHLCV + volume only. Causal: bars ``<= t``. The engine fills at
``t+1`` open.

Not ``range_compression_volume_thrust`` (102 — successful squeeze thrust).
Not ``failed_range_break_reversion`` (119 — rolling N-bar close-through).
Not ``nr7_fail_reversion`` / ``orb_fail_reversion`` / ``ib_fail_reversion``.
Not ``failed_break_reclaim`` (130 — multi-bar probe then reclaim).
Not ``displacement_gap_follow`` (PARKED — do not code).
Do not recode spent families 118–130.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams

# Locked ATR window and weak-vol lookback. Walk-forward searches expansion_mult only.
ATR_N_LOCKED = 20
VOL_LOOKBACK_LOCKED = 20


@dataclass(frozen=True)
class ExpansionFailFadeParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    # Wilder ATR period. Quant-locked at 20 — not a free search param.
    atr_n: int = ATR_N_LOCKED
    # Expansion threshold vs prior ATR. Quant grid: [1.5, 2.0].
    expansion_mult: float = 1.5
    # Prior-bar volume mean window. Quant-locked at 20 — not searched.
    vol_lookback: int = VOL_LOOKBACK_LOCKED
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class ExpansionFailFadeStrategy(Strategy):
    name = "expansion_fail_fade"

    def __init__(self, params: ExpansionFailFadeParams | None = None) -> None:
        super().__init__(params or ExpansionFailFadeParams())
        self.params: ExpansionFailFadeParams = self.params
        # ATR seed + one bar so the expansion can be compared to *prior* ATR
        # + the fail bar itself. Volume mean uses the same locked 20.
        self.min_bars = ATR_N_LOCKED + 3

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
        volume = candles["volume"]
        # Locks stay locked even if a caller passes another value.
        atr_n = ATR_N_LOCKED
        vol_n = VOL_LOOKBACK_LOCKED
        mult = float(params.expansion_mult)

        tr = ind.true_range(high, low, close)
        atr20 = ind.atr(high, low, close, atr_n)
        # Expansion is the prior bar. Threshold uses ATR known *before* it.
        exp_tr = tr.shift(1)
        atr_prev = atr20.shift(2)
        is_expansion = atr_prev.gt(0) & exp_tr.gt(mult * atr_prev)

        exp_high = high.shift(1)
        exp_low = low.shift(1)
        exp_close = close.shift(1)
        exp_mid = (exp_high + exp_low) / 2.0
        # Close back inside the expansion bar's own high-low (not a Donchian).
        close_inside = exp_high.notna() & exp_low.notna() & close.ge(exp_low) & close.le(exp_high)
        # Up = close on/above the expansion midpoint; down = close below it.
        up_exp = exp_close.ge(exp_mid)
        down_exp = exp_close.lt(exp_mid)

        # Locked weak-vol: current volume vs the prior-20 mean (current excluded).
        vol_mean = ind.prior_rolling_mean(volume, vol_n)
        weak_vol = vol_mean.notna() & volume.le(vol_mean)

        short_raw = is_expansion & close_inside & weak_vol & up_exp
        long_raw = is_expansion & close_inside & weak_vol & down_exp

        signals["atr"] = atr20
        signals["atr_prev"] = atr_prev
        signals["expansion_tr"] = exp_tr
        signals["expansion_high"] = exp_high
        signals["expansion_low"] = exp_low
        signals["expansion_mid"] = exp_mid
        signals["vol_mean"] = vol_mean

        if params.side is SignalSide.LONG:
            entry = long_raw
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            entry = short_raw
            signal_value, side_value = -1, SignalSide.SHORT.value

        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        width = (exp_high - exp_low).replace(0, pd.NA)
        if params.side is SignalSide.LONG:
            # How far the fail close sits above the expansion low, toward mid.
            score = ((close - exp_low) / width).clip(0.0, 1.0)
        else:
            score = ((exp_high - close) / width).clip(0.0, 1.0)
        signals.loc[entry, "score"] = score.fillna(0.0)[entry]
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                (
                    f"{side_value}: expansion-fail fade close {close.loc[i]:.4f} "
                    f"inside [{exp_low.loc[i]:.4f}, {exp_high.loc[i]:.4f}] "
                    f"mid {exp_mid.loc[i]:.4f} "
                    f"TR {exp_tr.loc[i]:.4f}>{mult:.2f}×ATR {atr_prev.loc[i]:.4f} "
                    f"vol {volume.loc[i]:.1f}<={vol_mean.loc[i]:.1f}"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = [
    "ATR_N_LOCKED",
    "VOL_LOOKBACK_LOCKED",
    "ExpansionFailFadeParams",
    "ExpansionFailFadeStrategy",
]
