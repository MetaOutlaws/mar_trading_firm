"""Impulse pullback continuation — CONTINUE after shallow PB break.

Option B. Garwe LOCK PASS. Live off. Do not set approved=true. No walk.
Protect 12+56. Soft-watch 165 + three_black_crows + sma20_stretch_fade EXPLICIT.

Geometry (OPPOSITE of Job 165 impulse_midpoint_fail_fade):

165 = impulse then next close through mid/extreme → FADE.
This = directional impulse (W close-to-close %) → shallow pullback that does
      NOT take the impulse start extreme → break of pullback extreme → CONTINUE.
      mid_anchor=false. fail_of_impulse=false. FORBID fade-through-mid / fail
      extreme paths. Soft-watch 165 / three_black_crows / sma20_stretch_fade
      EXPLICIT at SCORE (theme adjacency only — not soft-clone).

Impulse W=2 (locked):
  LONG:  (close[t_i]-close[t_i-W])/close[t_i-W] >= impulse_min_close_pct/100
  SHORT: drop >= same min pct
  ImpulseHigh = max(high of impulse bars [t_i-W+1 .. t_i])
  ImpulseLow  = min(low  of impulse bars [t_i-W+1 .. t_i])

Pullback within pullback_max_bars (4):
  LONG:  RetraceFrac=(ImpulseHigh-close[t_pb])/(ImpulseHigh-ImpulseLow) <= frac
         AND low[t_pb] >= ImpulseLow  (must NOT take ImpulseLow)
  SHORT: RetraceFrac=(close[t_pb]-ImpulseLow)/(ImpulseHigh-ImpulseLow) <= frac
         AND high[t_pb] <= ImpulseHigh

Trigger (signal bar t_tr; fill = next_open / engine t+1 — NEVER signal close):
  LONG:  close[t_tr] > max(high of pullback bars [t_i+1 .. t_pb])
  SHORT: close[t_tr] < min(low  of pullback bars [t_i+1 .. t_pb])

Regime gate REQUIRED aligned_200sma (shell §1.3 permission — NOT a stretch-fade):
  Resample completed 1D OHLCV from input 4h candles; SMA200 on daily close;
  shift(1) then ffill onto 4h index (no lookahead on in-progress day).
  LONG only if close_1d_completed >= SMA200; SHORT only if close_1d_completed < SMA200.
  Signal = geometry AND regime; else skip.
  Do NOT implement sma20 stretch fade.

BOTH sides; LONG priority on same-bar conflict (JSON priority LONG; Brian BOTH).
Free ≤2: pullback_max_retrace_frac {0.38, 0.50}, impulse_min_close_pct {1.5, 2.0}.
Locked shell defaults: TP=0.03, S=0.015, H=18. Kit space S {0.015, 0.02}, TP 0.03.
Do NOT fork impulse_midpoint_fail_fade, three_black_crows, sma20_stretch_fade,
trend_pullback_htf / macd_trend_pullback / swing_anchored_vwap_pullback /
elder_impulse_trend, range_compression_volume_thrust, body_efficiency_follow.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from core.strategy.base import SignalSide, Strategy
from core.strategy.impulse_pullback_continuation_params import (
    FAIL_OF_IMPULSE_LOCKED,
    FORBID_MIDPOINT_FAIL_FADE_LOCKED,
    FORBID_SIGNAL_CLOSE_FILL_LOCKED,
    FORBID_SMA20_STRETCH_FADE_LOCKED,
    FORBID_THREE_BLACK_CROWS_ENTRY_LOCKED,
    IMPULSE_MIN_CLOSE_PCT_GRID,
    IMPULSE_MIN_CLOSE_PCT_MAX,
    IMPULSE_MIN_CLOSE_PCT_MIN,
    IMPULSE_WINDOW_BARS_LOCKED,
    MAX_HOLDING_BARS_LOCKED,
    MID_ANCHOR_LOCKED,
    OPTION_B_LOCKED,
    PRIORITY_LONG_ON_CONFLICT_LOCKED,
    PULLBACK_MAX_BARS_LOCKED,
    PULLBACK_MAX_RETRACE_FRAC_GRID,
    PULLBACK_MAX_RETRACE_FRAC_MAX,
    PULLBACK_MAX_RETRACE_FRAC_MIN,
    REGIME_GATE_ALIGNED_200SMA_LOCKED,
    SMA_PERIOD_LOCKED,
    STOP_LOSS_PCT_GRID,
    STOP_LOSS_PCT_LOCKED_DEFAULT,
    TAKE_PROFIT_PCT_GRID,
    TAKE_PROFIT_PCT_LOCKED_DEFAULT,
    ImpulsePullbackContinuationParams,
)

_EPS = 1e-12


def _daily_ohlcv(candles: pd.DataFrame) -> pd.DataFrame:
    """Resample entry-clock (4h) bars to completed 1D OHLCV."""
    daily = candles.resample("1D").agg(
        {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }
    )
    return daily.dropna(how="any")


def _completed_daily(series: pd.Series, index: pd.Index) -> pd.Series:
    """Map daily values onto the entry clock using only finished daily bars.

    shift(1) drops the current (possibly incomplete) daily bar, then ffill
    carries the last completed value forward onto each 4h timestamp.
    """
    return series.shift(1).reindex(index, method="ffill")


def _aligned_200sma_regime(candles: pd.DataFrame) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    """Return (close_1d_completed, sma200_completed, long_ok, short_ok)."""
    daily = _daily_ohlcv(candles)
    sma = daily["close"].rolling(SMA_PERIOD_LOCKED, min_periods=SMA_PERIOD_LOCKED).mean()
    close_1d = _completed_daily(daily["close"], candles.index)
    sma_1d = _completed_daily(sma, candles.index)
    long_ok = close_1d.notna() & sma_1d.notna() & close_1d.ge(sma_1d)
    short_ok = close_1d.notna() & sma_1d.notna() & close_1d.lt(sma_1d)
    return close_1d, sma_1d, long_ok.fillna(False), short_ok.fillna(False)


def _scan_side(
    *,
    side_long: bool,
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    n: int,
    w: int,
    min_pct: float,
    frac: float,
    pb_max: int,
    regime_ok: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Scan impulse → shallow PB → break-of-PB-extreme continuation setups.

    Returns entry, impulse_end_idx, pb_end_idx, impulse_high, impulse_low, pb_extreme.
    mid_anchor / fail_of_impulse paths are intentionally absent.
    """
    entry = np.zeros(n, dtype=bool)
    impulse_end = np.full(n, -1, dtype=np.int64)
    pb_end = np.full(n, -1, dtype=np.int64)
    out_imp_hi = np.full(n, np.nan)
    out_imp_lo = np.full(n, np.nan)
    out_pb_ext = np.full(n, np.nan)

    # Trigger look-ahead after PB: same budget as PB window (tight geometry).
    trig_max = pb_max

    i = w
    while i < n - 1:
        base = close[i - w]
        if not (base > 0 and np.isfinite(base) and np.isfinite(close[i])):
            i += 1
            continue

        move = (close[i] - base) / base
        if side_long:
            impulse_ok = move >= min_pct
        else:
            impulse_ok = move <= -min_pct
        if not impulse_ok:
            i += 1
            continue

        # Impulse bars: [i-w+1 .. i] inclusive (W bars).
        a = i - w + 1
        b = i + 1
        imp_hi = float(np.max(high[a:b]))
        imp_lo = float(np.min(low[a:b]))
        rng = imp_hi - imp_lo
        if not (rng > _EPS and np.isfinite(imp_hi) and np.isfinite(imp_lo)):
            i += 1
            continue

        # Earliest valid pullback in (i, i+pb_max].
        t_pb = -1
        pb_hi = -np.inf
        pb_lo = np.inf
        last_j = min(i + pb_max, n - 1)
        for j in range(i + 1, last_j + 1):
            pb_hi = max(pb_hi, float(high[j]))
            pb_lo = min(pb_lo, float(low[j]))
            c_j = float(close[j])
            if side_long:
                retrace = (imp_hi - c_j) / rng
                valid = (
                    retrace <= frac
                    and retrace >= 0.0
                    and float(low[j]) >= imp_lo - _EPS
                )
            else:
                retrace = (c_j - imp_lo) / rng
                valid = (
                    retrace <= frac
                    and retrace >= 0.0
                    and float(high[j]) <= imp_hi + _EPS
                )
            if valid:
                t_pb = j
                break
            # Structure break during PB search → abandon this impulse.
            if side_long and float(low[j]) < imp_lo - _EPS:
                break
            if (not side_long) and float(high[j]) > imp_hi + _EPS:
                break

        if t_pb < 0:
            i += 1
            continue

        # Recompute PB extreme over pullback bars [i+1 .. t_pb].
        pb_slice_hi = float(np.max(high[i + 1 : t_pb + 1]))
        pb_slice_lo = float(np.min(low[i + 1 : t_pb + 1]))
        pb_extreme = pb_slice_hi if side_long else pb_slice_lo

        # First trigger after valid PB; abandon if structure extreme taken.
        t_tr = -1
        last_tr = min(t_pb + trig_max, n - 1)
        for t in range(t_pb + 1, last_tr + 1):
            if side_long and float(low[t]) < imp_lo - _EPS:
                break
            if (not side_long) and float(high[t]) > imp_hi + _EPS:
                break
            if side_long:
                fired = float(close[t]) > pb_extreme
            else:
                fired = float(close[t]) < pb_extreme
            if fired:
                t_tr = t
                break

        if t_tr >= 0 and bool(regime_ok[t_tr]):
            entry[t_tr] = True
            impulse_end[t_tr] = i
            pb_end[t_tr] = t_pb
            out_imp_hi[t_tr] = imp_hi
            out_imp_lo[t_tr] = imp_lo
            out_pb_ext[t_tr] = pb_extreme
            # Non-overlap soft advance: skip past this trigger for next impulse hunt.
            i = t_tr + 1
            continue

        i += 1

    return entry, impulse_end, pb_end, out_imp_hi, out_imp_lo, out_pb_ext


class ImpulsePullbackContinuationStrategy(Strategy):
    name = "impulse_pullback_continuation"

    def __init__(self, params: ImpulsePullbackContinuationParams | None = None) -> None:
        super().__init__(params or ImpulsePullbackContinuationParams())
        self.params: ImpulsePullbackContinuationParams = self.params
        # Daily SMA200 needs ~200 completed days from 4h (~6 bars/day) + impulse/PB/trig.
        self.min_bars = SMA_PERIOD_LOCKED * 6 + IMPULSE_WINDOW_BARS_LOCKED + PULLBACK_MAX_BARS_LOCKED + 8

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        p = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        if not (
            OPTION_B_LOCKED
            and REGIME_GATE_ALIGNED_200SMA_LOCKED
            and FORBID_SIGNAL_CLOSE_FILL_LOCKED
            and FORBID_SMA20_STRETCH_FADE_LOCKED
            and FORBID_THREE_BLACK_CROWS_ENTRY_LOCKED
            and FORBID_MIDPOINT_FAIL_FADE_LOCKED
            and PRIORITY_LONG_ON_CONFLICT_LOCKED
            and MID_ANCHOR_LOCKED is False
            and FAIL_OF_IMPULSE_LOCKED is False
            and p.mid_anchor is False
            and p.fail_of_impulse is False
            and p.forbid_signal_close_fill is True
            and p.regime_gate_aligned_200sma is True
            and int(p.impulse_window_bars) == IMPULSE_WINDOW_BARS_LOCKED
            and int(p.pullback_max_bars) == PULLBACK_MAX_BARS_LOCKED
            and int(p.max_holding_bars) == MAX_HOLDING_BARS_LOCKED
        ):
            raise RuntimeError("impulse_pullback_continuation locks were edited")

        o = candles["open"].astype("float64")
        h = candles["high"].astype("float64")
        l = candles["low"].astype("float64")
        c = candles["close"].astype("float64")

        w = IMPULSE_WINDOW_BARS_LOCKED
        pb_max = PULLBACK_MAX_BARS_LOCKED
        min_pct_raw = float(p.impulse_min_close_pct)
        min_pct_raw = min(IMPULSE_MIN_CLOSE_PCT_MAX, max(IMPULSE_MIN_CLOSE_PCT_MIN, min_pct_raw))
        min_pct = min_pct_raw / 100.0
        frac = float(p.pullback_max_retrace_frac)
        frac = min(PULLBACK_MAX_RETRACE_FRAC_MAX, max(PULLBACK_MAX_RETRACE_FRAC_MIN, frac))

        close_1d, sma_1d, long_regime, short_regime = _aligned_200sma_regime(candles)

        n = len(candles)
        o_a = o.to_numpy()
        h_a = h.to_numpy()
        l_a = l.to_numpy()
        c_a = c.to_numpy()
        long_ok = long_regime.to_numpy(dtype=bool)
        short_ok = short_regime.to_numpy(dtype=bool)

        long_raw, long_ie, long_pb, long_hi, long_lo, long_ext = _scan_side(
            side_long=True,
            open_=o_a,
            high=h_a,
            low=l_a,
            close=c_a,
            n=n,
            w=w,
            min_pct=min_pct,
            frac=frac,
            pb_max=pb_max,
            regime_ok=long_ok,
        )
        short_raw, short_ie, short_pb, short_hi, short_lo, short_ext = _scan_side(
            side_long=False,
            open_=o_a,
            high=h_a,
            low=l_a,
            close=c_a,
            n=n,
            w=w,
            min_pct=min_pct,
            frac=frac,
            pb_max=pb_max,
            regime_ok=short_ok,
        )

        # LONG priority on same-bar conflict (JSON priority; Brian BOTH).
        short_raw = short_raw & ~long_raw

        signals["close_1d_completed"] = close_1d
        signals["sma200_1d_completed"] = sma_1d
        signals["regime_long_ok"] = long_regime
        signals["regime_short_ok"] = short_regime
        signals["impulse_end_idx"] = np.where(long_raw, long_ie, np.where(short_raw, short_ie, -1))
        signals["pb_end_idx"] = np.where(long_raw, long_pb, np.where(short_raw, short_pb, -1))
        signals["impulse_high"] = np.where(long_raw, long_hi, np.where(short_raw, short_hi, np.nan))
        signals["impulse_low"] = np.where(long_raw, long_lo, np.where(short_raw, short_lo, np.nan))
        signals["pb_extreme"] = np.where(long_raw, long_ext, np.where(short_raw, short_ext, np.nan))
        signals["geometry_long"] = long_raw
        signals["geometry_short"] = short_raw
        # Diagnostics: mid / fail paths stay dark (locks forbid encoding them).
        signals["mid_anchor_path"] = False
        signals["fail_of_impulse_path"] = False

        if p.side is SignalSide.LONG:
            entry, sig, side = long_raw, 1, SignalSide.LONG.value
        elif p.side is SignalSide.SHORT:
            entry, sig, side = short_raw, -1, SignalSide.SHORT.value
        else:
            entry = np.zeros(n, dtype=bool)
            sig, side = 0, SignalSide.FLAT.value

        entry = pd.Series(entry, index=candles.index)
        entry.iloc[: self.min_bars] = False
        if sig != 0:
            signals.loc[entry, "signal"] = sig
            signals.loc[entry, "side"] = side
            # Score: how shallow the PB was (1 - retrace_frac proxy via room to extreme).
            imp_hi = pd.Series(np.where(long_raw, long_hi, short_hi), index=candles.index)
            imp_lo = pd.Series(np.where(long_raw, long_lo, short_lo), index=candles.index)
            rng = (imp_hi - imp_lo).where((imp_hi - imp_lo) > _EPS)
            if p.side is SignalSide.LONG:
                retrace = ((imp_hi - c) / rng).clip(0.0, 1.0)
            else:
                retrace = ((c - imp_lo) / rng).clip(0.0, 1.0)
            # Prefer shallower pullbacks (closer to continuation).
            score = (1.0 - retrace / max(frac, _EPS)).clip(0.0, 1.0)
            signals.loc[entry, "score"] = score.fillna(0.0)[entry]

        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any() and sig != 0:
            reasons.loc[entry] = [
                (
                    f"{side}: impulse+shallow-PB continuation "
                    f"imp_hi={float(signals['impulse_high'].loc[i]):.4f} "
                    f"imp_lo={float(signals['impulse_low'].loc[i]):.4f} "
                    f"pb_ext={float(signals['pb_extreme'].loc[i]):.4f} "
                    f"c={float(c.loc[i]):.4f} "
                    f"regime_1d={float(close_1d.loc[i]):.4f}/"
                    f"sma200={float(sma_1d.loc[i]):.4f} "
                    f"min_pct={min_pct_raw:.2f} frac={frac:.2f} "
                    f"fill=next_open(engine_t+1)"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = [
    "ImpulsePullbackContinuationParams",
    "ImpulsePullbackContinuationStrategy",
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
    "_aligned_200sma_regime",
    "_completed_daily",
    "_daily_ohlcv",
]
