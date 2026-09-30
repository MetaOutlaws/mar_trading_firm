"""Alt vs BTC price-beta residual stretch fade. 4h BOTH, SHORT priority.

Garwe STAMP LOCK. Option B paper sleeve. SCORE/RETIRE only. Not an
approval. This module does not write ``approved=true``, does not start
a walk, and does not touch the protect 12+56 book. Live stays off.

On the locked alts, residual versus a BTC price beta stretches at least
``k_atr * ATR_alt``, then the close fades that residual back inside the
band (toward zero). The trade fades the stretch: rich alt is SHORT,
cheap alt is LONG.

    Fit:     close_alt = alpha + beta * close_btc
             alpha, beta from the prior ``lookback`` closes only
             (bar t is not in the fit)
    Fair_t:  alpha + beta * close_btc[t]
    ATR:     Wilder ATR(20) of the alt, known before the signal bar
             (``atr.shift(1)``). A caller-supplied ``atr_n`` is ignored.
    Stretch: high - fair >= k_atr * ATR   (rich)  or
             fair - low  >= k_atr * ATR   (cheap)
             An exact k_atr * ATR print counts (``>=``).
    Fade:    abs(close - fair) < k_atr * ATR
             (close residual is strictly back inside the band)
    SHORT:   rich stretch AND fade
    LONG:    cheap stretch AND fade, and the bar is not also a SHORT

BOTH sides are honest. SHORT priority: a bar that prints both fades is
SHORT, not LONG. The engine fills at ``t+1`` open. No volume gate, no
session gate, no univariate SMA or VWAP magnet.

The benchmark close arrives on column ``btc_close`` (same timestamps,
no forward fill). Missing benchmark, a flat BTC window (no price beta),
or the benchmark symbol itself produces no trade. Research pairs are
the locked alts only. BTC is the benchmark, not a traded leg.

Free search (2 only, endpoints, no interiors):

    - ``lookback`` grid ``[20, 40]``
    - ``k_atr`` grid ``[1.5, 2.0]``

A caller value outside those endpoints is ignored and the first
endpoint is used, so the sleeve cannot be walked on an interior.

Quant-locked (not searched):

    - Clock 4h/4h, side BOTH (SHORT priority on two-sided bars)
    - Family id ``alt_btc_residual_stretch_fade`` only
    - ``atr_n`` = 20
    - Fill ``t+1`` open
    - ``option_b`` = True
    - Pairs ETH / SOL / BNB / XRP / AVAX
    - Benchmark BTCUSDT
    - Price-level OLS residual, not a return z-score and not volume

Not ``cross_sectional_turnover_lead`` (volume lead; this sleeve does
not read volume).
Not ``sma20_stretch_fade`` (univariate SMA wick + halfway reclaim).
Not ``rolling_vwap_stretch_fade`` (VWAP magnet; not stamped, not this).
Not ``rsi_fade_chop``.
Not killed YES ×5, ORB, wyckoff, thrust_bar_fail_reversion, or the
reject pack. Do not revive them. Do not modify sibling geometry.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from core.strategy import indicators as ind
from core.strategy.base import SignalSide, Strategy, StrategyParams

# Locked ATR window. Walk-forward does not search it. Never ATR(14).
ATR_N_LOCKED = 20
# Free-grid beta window. Endpoints only — do not insert 30.
LOOKBACK_GRID = (20, 40)
LOOKBACK_MIN = LOOKBACK_GRID[0]
# Free-grid stretch in ATR(20) units of the alt. Endpoints only.
K_ATR_GRID = (1.5, 2.0)
K_ATR_MIN = K_ATR_GRID[0]
# Column the research loader stamps with the aligned BTC close.
BTC_CLOSE_COLUMN = "btc_close"
# Below this, BTC had no price variation and beta is undefined.
VAR_FLOOR = 1e-12
# Stamp lock. Option B only. The module does not write approvals.
OPTION_B_LOCKED = True
FILL_LOCKED = "t+1"
BENCHMARK_LOCKED = "BTCUSDT"
PAIRS_LOCKED = (
    "ETHUSDT",
    "SOLUSDT",
    "BNBUSDT",
    "XRPUSDT",
    "AVAXUSDT",
)
FAMILY_NAME = "alt_btc_residual_stretch_fade"


def coerce_lookback(value: int) -> int:
    """Return a stamped lookback endpoint. Interiors fall back to 20."""
    try:
        lookback = int(value)
    except (TypeError, ValueError):
        return LOOKBACK_MIN
    if lookback in LOOKBACK_GRID:
        return lookback
    return LOOKBACK_MIN


def coerce_k_atr(value: float) -> float:
    """Return a stamped k_atr endpoint. Interiors fall back to 1.5."""
    try:
        k_atr = float(value)
    except (TypeError, ValueError):
        return K_ATR_MIN
    for allowed in K_ATR_GRID:
        if abs(k_atr - allowed) <= 1e-9:
            return float(allowed)
    return K_ATR_MIN


def price_beta_fair(
    alt_close: pd.Series,
    btc_close: pd.Series,
    lookback: int,
) -> pd.DataFrame:
    """Causal OLS fair value of alt close on BTC close.

    Alpha and beta at bar ``t`` use closes ``[t-lookback, t-1]`` only.
    Fair at ``t`` is ``alpha + beta * btc_close[t]``, so the signal
    bar's own alt print cannot shrink its residual. Variance and
    covariance use the same ``/n`` divisor, which is ordinary
    least squares with an intercept. A flat BTC window leaves beta
    and fair as NaN.
    """
    # shift(1) drops bar t out of the fit. Rolling then looks backward.
    alt_hist = alt_close.astype("float64").shift(1)
    btc_hist = btc_close.astype("float64").shift(1)
    window = int(lookback)
    mean_alt = alt_hist.rolling(window, min_periods=window).mean()
    mean_btc = btc_hist.rolling(window, min_periods=window).mean()
    mean_alt_btc = (alt_hist * btc_hist).rolling(window, min_periods=window).mean()
    mean_btc2 = (btc_hist * btc_hist).rolling(window, min_periods=window).mean()
    var_btc = mean_btc2 - mean_btc * mean_btc
    cov = mean_alt_btc - mean_alt * mean_btc
    beta = cov / var_btc.where(var_btc > VAR_FLOOR)
    alpha = mean_alt - beta * mean_btc
    fair = alpha + beta * btc_close.astype("float64")
    return pd.DataFrame(
        {"alpha": alpha, "beta": beta, "fair": fair, "var_btc": var_btc},
        index=alt_close.index,
    )


def attach_btc_close(candles: pd.DataFrame, benchmark: pd.DataFrame) -> pd.DataFrame:
    """Copy ``benchmark`` close onto ``candles`` at matching timestamps.

    No forward fill. A bar with no benchmark print stays NaN and cannot
    fire. Future benchmark bars are not pulled backward.
    """
    out = candles.copy()
    aligned = benchmark["close"].reindex(candles.index)
    out[BTC_CLOSE_COLUMN] = aligned.astype("float64")
    return out


def maybe_attach_benchmark(
    strategy: str,
    symbol: str,
    candles: pd.DataFrame,
    benchmark: pd.DataFrame | None,
) -> pd.DataFrame | None:
    """Join BTC for this family. ``None`` means the symbol is not a locked pair.

    Other families are returned unchanged so a shared loader cannot
    alter their columns. The benchmark symbol itself is not a traded leg.
    """
    if strategy != FAMILY_NAME:
        return candles
    if str(symbol).upper() not in PAIRS_LOCKED:
        return None
    if benchmark is None or benchmark.empty or "close" not in benchmark.columns:
        return candles
    return attach_btc_close(candles, benchmark)


@dataclass(frozen=True)
class AltBtcResidualStretchFadeParams(StrategyParams):
    side: SignalSide = SignalSide.SHORT
    # Wilder ATR period. Quant-locked at 20. generate_signals ignores
    # any other value so the sleeve cannot become ATR(14).
    atr_n: int = ATR_N_LOCKED
    # Beta window in bars. Quant grid: [20, 40]. Interiors are coerced.
    lookback: int = LOOKBACK_MIN
    # Stretch distance in ATR(20) units of the alt. Quant grid: [1.5, 2.0].
    k_atr: float = K_ATR_MIN
    take_profit_pct: float = 0.04
    stop_loss_pct: float = 0.02


class AltBtcResidualStretchFadeStrategy(Strategy):
    name = FAMILY_NAME

    def __init__(self, params: AltBtcResidualStretchFadeParams | None = None) -> None:
        super().__init__(params or AltBtcResidualStretchFadeParams())
        self.params: AltBtcResidualStretchFadeParams = self.params
        lookback = coerce_lookback(self.params.lookback)
        # ATR seed plus the beta window that excludes the signal bar.
        self.min_bars = ATR_N_LOCKED + lookback

    def generate_signals(self, candles: pd.DataFrame) -> pd.DataFrame:
        self.validate_candles(candles)
        params = self.params
        signals = self.empty_signals(candles)
        if len(candles) < self.min_bars:
            signals["reason"] = "insufficient history"
            return signals

        # Benchmark is a joined close, not a second Strategy input.
        # Without it the residual is undefined — stay flat rather than
        # pretending a univariate stretch is this family.
        if BTC_CLOSE_COLUMN not in candles.columns:
            signals["reason"] = "benchmark close missing"
            return signals

        high = candles["high"]
        low = candles["low"]
        close = candles["close"]
        btc = candles[BTC_CLOSE_COLUMN].astype("float64")
        # BTC traded against itself is the benchmark, not an alt leg.
        if bool(btc.notna().all()) and np.allclose(
            close.to_numpy(dtype="float64"),
            btc.to_numpy(dtype="float64"),
            equal_nan=True,
        ):
            signals["reason"] = "benchmark is not a traded leg"
            return signals

        # Searched knobs stay on the stamped endpoints even if a caller
        # passes an interior. atr_n stays 20 even if the caller says 14.
        lookback = coerce_lookback(params.lookback)
        k_atr = coerce_k_atr(params.k_atr)
        atr_n = ATR_N_LOCKED

        fit = price_beta_fair(close, btc, lookback)
        fair = fit["fair"]
        atr20 = ind.atr(high, low, close, atr_n)
        # ATR known before the signal bar. The tag wick cannot lift the band.
        atr_known = atr20.shift(1)
        atr_ok = atr_known.gt(0) & fair.notna()
        band = k_atr * atr_known

        residual_close = close - fair
        # Positive rich-stretch: wick above fair. Positive cheap-stretch:
        # wick below fair. Compared with the alt's own ATR, in price units.
        rich = high - fair
        cheap = fair - low
        stretched_above = atr_ok & rich.ge(band)
        stretched_below = atr_ok & cheap.ge(band)
        # Fade toward zero: close residual strictly inside the band.
        # A close sitting on the band has not faded in yet.
        faded_inside = atr_ok & residual_close.abs().lt(band)

        short_raw = stretched_above & faded_inside
        long_raw = stretched_below & faded_inside
        # SHORT priority: a two-sided fade is SHORT, not LONG.
        long_raw = long_raw & (~short_raw)

        signals["alpha"] = fit["alpha"]
        signals["beta"] = fit["beta"]
        signals["fair"] = fair
        signals["var_btc"] = fit["var_btc"]
        signals["atr"] = atr20
        signals["atr_known"] = atr_known
        signals["band"] = band
        signals["residual_close"] = residual_close
        signals["stretched_above"] = stretched_above.fillna(False)
        signals["stretched_below"] = stretched_below.fillna(False)
        signals["faded_inside"] = faded_inside.fillna(False)

        if params.side is SignalSide.SHORT:
            entry = short_raw
            signal_value, side_value = -1, SignalSide.SHORT.value
            excess = (rich - band) / band.replace(0, pd.NA)
        elif params.side is SignalSide.LONG:
            entry = long_raw
            signal_value, side_value = 1, SignalSide.LONG.value
            excess = (cheap - band) / band.replace(0, pd.NA)
        else:
            entry = pd.Series(False, index=candles.index)
            signal_value, side_value = 0, SignalSide.FLAT.value
            excess = pd.Series(np.nan, index=candles.index)

        entry = entry.fillna(False)
        # Warm-up covers ATR(20) and the lookback that ends at t-1.
        entry.iloc[: self.min_bars] = False
        if signal_value != 0:
            signals.loc[entry, "signal"] = signal_value
            signals.loc[entry, "side"] = side_value
            signals.loc[entry, "score"] = excess.clip(0.0, 1.0).fillna(0.0)[entry]
        reasons = pd.Series("", index=candles.index, dtype="object")
        if entry.any() and signal_value != 0:
            reasons.loc[entry] = [
                (
                    f"{side_value}: BTC-beta residual fade fair {fair.loc[i]:.4f} "
                    f"close {close.loc[i]:.4f} beta {fit['beta'].loc[i]:.4f} "
                    f"residual {residual_close.loc[i]:.4f} "
                    f"atr {atr_known.loc[i]:.4f} k_atr={k_atr:.2f} "
                    f"lookback={lookback}"
                )
                for i in entry[entry].index
            ]
        signals["reason"] = reasons
        return signals


__all__ = [
    "ATR_N_LOCKED",
    "BENCHMARK_LOCKED",
    "BTC_CLOSE_COLUMN",
    "FAMILY_NAME",
    "FILL_LOCKED",
    "K_ATR_GRID",
    "K_ATR_MIN",
    "LOOKBACK_GRID",
    "LOOKBACK_MIN",
    "OPTION_B_LOCKED",
    "PAIRS_LOCKED",
    "AltBtcResidualStretchFadeParams",
    "AltBtcResidualStretchFadeStrategy",
    "attach_btc_close",
    "coerce_k_atr",
    "coerce_lookback",
    "maybe_attach_benchmark",
    "price_beta_fair",
]
