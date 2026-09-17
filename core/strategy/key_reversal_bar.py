"""Classic key reversal bar — break of the prior extreme, then reverse close.

Brian YES live. Munha AUTHORITATIVE geometry lock — implement exactly.

    SHORT: high[t] > high[t-1]
           AND (high[t] - high[t-1]) >= min_break_atr * ATR20
           AND close[t] < close[t-1]
           AND close[t] < open[t]
    LONG:  low[t]  < low[t-1]
           AND (low[t-1] - low[t])  >= min_break_atr * ATR20
           AND close[t] > close[t-1]
           AND close[t] > open[t]

ATR is Wilder ATR(20) known *before* the signal bar so bar t cannot lift
its own threshold (``atr.shift(1)``). Reverse body (close vs open) is
quant-locked, not searched.

Quant-locked (not searched):

    - Clock 4h/4h, side BOTH (SHORT priority; both sides honest)
    - Family id ``key_reversal_bar`` only
    - ATR period = 20, known before the signal bar (``atr.shift(1)``)
    - Reverse body: SHORT close < open / LONG close > open
    - Fill at t+1 open (engine convention)

Free search (1 only):

    - ``min_break_atr`` grid ``[0.2, 0.5]``
      (endpoints only — do not invent interiors)

OHLCV only. Causal: bars ``<= t``. No volume gate. No session lock.
No inside-bar mother. No Donchian lookback. No rectangle box.

Not ``inside_bar_break_fail`` (family F — inside-bar mother wick-fail).
Not ``outside_bar_reversal`` / ``outside_bar_fail_reversion`` (both-rail
containment is the sibling definition; this lock is prior-extreme +
close-vs-prior-close + reverse body). Not a thrust-bar fail-reversion.
Not dead VP families. Not Job 133 ``bullish_rectangle_fail_reclaim``
(DEAD — no-recode / no-spawn). Hold H&S / asia / wyckoff alone.
Do not recode spent families 118–151. Do not modify sibling geometry.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams

# Locked ATR window. Walk-forward searches min_break_atr only.
ATR_N_LOCKED = 20
# Quant-locked True: SHORT close < open / LONG close > open.
REQUIRE_REVERSE_BODY_LOCKED = True
# Free-grid break floor vs ATR20. Endpoints only — no invented interiors.
MIN_BREAK_ATR_MIN = 0.2
MIN_BREAK_ATR_MAX = 0.5
MIN_BREAK_ATR_GRID = [0.2, 0.5]


@dataclass(frozen=True)
class KeyReversalBarParams(StrategyParams):
    side: SignalSide = SignalSide.SHORT
    # Wilder ATR period. Quant-locked at 20 — not a free search param.
    atr_n: int = ATR_N_LOCKED
    # Prior-extreme break floor in ATR units. Quant grid: [0.2, 0.5].
    min_break_atr: float = MIN_BREAK_ATR_MIN
    # Quant-locked True: fade only if the body closes reverse vs open.
    require_reverse_body: bool = REQUIRE_REVERSE_BODY_LOCKED
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class KeyReversalBarStrategy(Strategy):
    name = "key_reversal_bar"

    def __init__(self, params: KeyReversalBarParams | None = None) -> None:
        super().__init__(params or KeyReversalBarParams())
        self.params: KeyReversalBarParams = self.params
        # ATR seed + the prior bar that publishes the extreme.
        self.min_bars = ATR_N_LOCKED + 2

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        open_ = candles["open"]
        high = candles["high"]
        low = candles["low"]
        close = candles["close"]
        # Searched break floor stays caller-set. Period / reverse-body stay locked.
        min_atr = float(params.min_break_atr)
        atr_n = ATR_N_LOCKED

        prior_high = high.shift(1)
        prior_low = low.shift(1)
        prior_close = close.shift(1)

        # Authoritative lock — these four conjuncts per side, nothing extra.
        broke_up = prior_high.notna() & high.gt(prior_high)
        broke_down = prior_low.notna() & low.lt(prior_low)
        break_up = high - prior_high
        break_down = prior_low - low

        atr20 = ind.atr(high, low, close, atr_n)
        # ATR known before the signal bar — bar t cannot lift the size gate.
        atr_known = atr20.shift(1)
        atr_ok = atr_known.gt(0)
        atr_safe = atr_known.replace(0, pd.NA)
        sized_up = atr_ok & break_up.ge(min_atr * atr_known)
        sized_down = atr_ok & break_down.ge(min_atr * atr_known)

        close_lt_prior = prior_close.notna() & close.lt(prior_close)
        close_gt_prior = prior_close.notna() & close.gt(prior_close)
        # Locked reverse body. A caller cannot pass require_reverse_body=False
        # to take a close that did not reverse vs open.
        close_lt_open = close.lt(open_)
        close_gt_open = close.gt(open_)

        short_raw = broke_up & sized_up & close_lt_prior & close_lt_open
        long_raw = broke_down & sized_down & close_gt_prior & close_gt_open

        signals["atr"] = atr20
        signals["atr_known"] = atr_known
        signals["prior_high"] = prior_high
        signals["prior_low"] = prior_low
        signals["prior_close"] = prior_close
        signals["broke_up"] = broke_up.fillna(False)
        signals["broke_down"] = broke_down.fillna(False)
        signals["break_up"] = break_up
        signals["break_down"] = break_down
        signals["break_up_atr"] = break_up / atr_safe
        signals["break_down_atr"] = break_down / atr_safe
        signals["sized_up"] = sized_up.fillna(False)
        signals["sized_down"] = sized_down.fillna(False)
        signals["close_lt_prior"] = close_lt_prior.fillna(False)
        signals["close_gt_prior"] = close_gt_prior.fillna(False)
        signals["close_lt_open"] = close_lt_open.fillna(False)
        signals["close_gt_open"] = close_gt_open.fillna(False)
        signals["close_reverse_short"] = close_lt_prior.fillna(False)
        signals["close_reverse_long"] = close_gt_prior.fillna(False)

        if params.side is SignalSide.LONG:
            entry = long_raw
            signal_value, side_value = 1, SignalSide.LONG.value
        elif params.side is SignalSide.SHORT:
            entry = short_raw
            signal_value, side_value = -1, SignalSide.SHORT.value
        else:
            entry = pd.Series(False, index=candles.index)
            signal_value, side_value = 0, SignalSide.FLAT.value

        entry = entry.fillna(False)
        entry.iloc[: self.min_bars] = False
        if signal_value != 0:
            signals.loc[entry, "signal"] = signal_value
            signals.loc[entry, "side"] = side_value
            # Stronger when the reverse close sits further through prior close.
            if params.side is SignalSide.LONG:
                depth = (close - prior_close) / atr_safe
            else:
                depth = (prior_close - close) / atr_safe
            signals.loc[entry, "score"] = depth.clip(0.0, 1.0).fillna(0.0)[entry]
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any() and signal_value != 0:
            reasons.loc[entry] = [
                (
                    f"{side_value}: key-reversal-bar close {close.loc[i]:.4f} "
                    f"{'<' if params.side is SignalSide.SHORT else '>'} "
                    f"open {open_.loc[i]:.4f} vs prior close {prior_close.loc[i]:.4f} "
                    f"broke "
                    f"{'high' if params.side is SignalSide.SHORT else 'low'} "
                    f"by "
                    f"{(break_up if params.side is SignalSide.SHORT else break_down).loc[i]:.4f}"
                    f">={min_atr:.2f}×ATR {atr_known.loc[i]:.4f}"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = [
    "ATR_N_LOCKED",
    "MIN_BREAK_ATR_GRID",
    "MIN_BREAK_ATR_MAX",
    "MIN_BREAK_ATR_MIN",
    "REQUIRE_REVERSE_BODY_LOCKED",
    "KeyReversalBarParams",
    "KeyReversalBarStrategy",
]
