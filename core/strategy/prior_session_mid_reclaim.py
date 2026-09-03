"""Reclaim the prior completed UTC 8h session midpoint.

UTC is split 00–08 / 08–16 / 16–24. After a session closes through one side
of its own (high+low)/2 midpoint, a later bar that closes back through that
frozen mid on volume above the prior-20 mean trades the reclaim.

Not `session_boundary_volume_fade` (prior UTC day H/L weak-volume fade).
Not `utc_session_vwap_reversion` (session VWAP stretch). Not
`utc_open_fail_reversion` (first-4h box fail on the second 4h).
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams


@dataclass(frozen=True)
class PriorSessionMidReclaimParams(StrategyParams):
    side: SignalSide = SignalSide.LONG
    # 8h slots are locked. Walk-forward may search the volume lookback.
    vol_lookback: int = 20
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class PriorSessionMidReclaimStrategy(Strategy):
    name = "prior_session_mid_reclaim"

    def __init__(self, params: PriorSessionMidReclaimParams | None = None) -> None:
        super().__init__(params or PriorSessionMidReclaimParams())
        self.params: PriorSessionMidReclaimParams = self.params
        self.min_bars = int(self.params.vol_lookback) + 10

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        close = candles["close"]
        volume = candles["volume"]
        # Causal: blank until the 8h session ends, then ffill that session's box.
        prev_h, prev_l, prev_c, mid, ready = ind.prior_utc_8h_session(
            candles["high"], candles["low"], close
        )
        sess = ind.utc_8h_session_key(candles.index)
        vol_mean = ind.prior_rolling_mean(volume, int(params.vol_lookback))
        heavy = vol_mean.notna() & (volume > vol_mean)
        prev_close = close.shift(1)

        # Session close through one side of its own mid, then a later close
        # back through that frozen mid. Not a first-4h box fail.
        through_low = ready & (prev_c < mid)
        through_high = ready & (prev_c > mid)
        long_raw = through_low & (close > mid) & (prev_close <= mid) & heavy
        short_raw = through_high & (close < mid) & (prev_close >= mid) & heavy

        signals["session_high"] = prev_h
        signals["session_low"] = prev_l
        signals["session_close"] = prev_c
        signals["session_mid"] = mid
        signals["vol_mean"] = vol_mean

        if params.side is SignalSide.LONG:
            raw = long_raw
            signal_value, side_value = 1, SignalSide.LONG.value
        else:
            raw = short_raw
            signal_value, side_value = -1, SignalSide.SHORT.value

        # One reclaim per current 8h session against the just-finished mid.
        entry = raw.fillna(False) & raw.groupby(sess).cumsum().eq(1)
        entry.iloc[: self.min_bars] = False
        signals.loc[entry, "signal"] = signal_value
        signals.loc[entry, "side"] = side_value
        width = (prev_h - prev_l).replace(0, pd.NA)
        if params.side is SignalSide.LONG:
            score = ((close - mid) / width).clip(0.0, 1.0)
        else:
            score = ((mid - close) / width).clip(0.0, 1.0)
        signals.loc[entry, "score"] = score.fillna(0.0)[entry]
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any():
            reasons.loc[entry] = [
                (
                    f"{side_value}: 8h mid reclaim close {close.loc[i]:.4f} "
                    f"mid {mid.loc[i]:.4f} sess {prev_h.loc[i]:.4f}/{prev_l.loc[i]:.4f} "
                    f"vol {volume.loc[i]:.1f}>{vol_mean.loc[i]:.1f}"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = ["PriorSessionMidReclaimParams", "PriorSessionMidReclaimStrategy"]
