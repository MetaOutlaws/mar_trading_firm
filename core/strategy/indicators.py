"""
Technical indicators: one implementation, used everywhere.

These are pure functions over pandas Series. No state, no I/O, no configuration
lookups -- which is what makes them testable against known-good values.

**Wilder smoothing.** RSI, ATR and ADX all use Wilder's moving average, which is
an exponential average with `alpha = 1/period` seeded by a simple average of the
first `period` observations. Seeding matters: an unseeded EWM converges to the
same values but disagrees for the first several hundred bars, which is exactly
the region a short backtest window lives in. `_wilder` below seeds explicitly.

**No lookahead.** Every function returns a value at bar `t` computed only from
bars `<= t`. Nothing shifts data backwards.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _wilder(series: pd.Series, period: int) -> pd.Series:
    """Wilder's smoothed moving average, seeded with an SMA.

    Equivalent to `ewm(alpha=1/period, adjust=False)` where the first value is
    the mean of the first `period` observations rather than the first
    observation alone.
    """
    if period <= 0:
        raise ValueError(f"period must be positive, got {period}")

    values = series.astype("float64")
    seeded = values.copy()

    # Blank everything before the seed point, then plant the SMA seed. pandas'
    # ewm skips leading NaNs and adopts the first valid value as its initial
    # state, which reproduces Wilder exactly.
    if len(seeded) >= period:
        seed = values.iloc[:period].mean()
        seeded.iloc[: period - 1] = np.nan
        seeded.iloc[period - 1] = seed

    return seeded.ewm(alpha=1.0 / period, adjust=False).mean()


def ema(series: pd.Series, period: int) -> pd.Series:
    """Standard exponential moving average (`alpha = 2/(period+1)`)."""
    if period <= 0:
        raise ValueError(f"period must be positive, got {period}")
    return series.astype("float64").ewm(span=period, adjust=False).mean()


def sma(series: pd.Series, period: int) -> pd.Series:
    """Simple moving average."""
    return series.astype("float64").rolling(window=period, min_periods=period).mean()


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index, Wilder-smoothed.

    Returns values in [0, 100]. Where average loss is zero (an unbroken run of
    gains) the result is 100 by definition rather than NaN from a zero divide.
    """
    close = close.astype("float64")
    delta = close.diff()

    gains = delta.clip(lower=0.0)
    losses = (-delta).clip(lower=0.0)

    avg_gain = _wilder(gains, period)
    avg_loss = _wilder(losses, period)

    # Guard the zero-divide: infinite RS maps to RSI 100.
    with np.errstate(divide="ignore", invalid="ignore"):
        rs = avg_gain / avg_loss
    result = 100.0 - (100.0 / (1.0 + rs))

    result = result.where(avg_loss != 0.0, 100.0)
    # An unbroken run of losses gives zero gain and zero RS -> RSI 0.
    result = result.where(~((avg_loss == 0.0) & (avg_gain == 0.0)), 50.0)

    return result.clip(0.0, 100.0)


def macd(
    close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """MACD line, signal line, and histogram."""
    if fast >= slow:
        raise ValueError(f"fast ({fast}) must be less than slow ({slow})")

    macd_line = ema(close, fast) - ema(close, slow)
    signal_line = ema(macd_line, signal)
    return macd_line, signal_line, macd_line - signal_line


def true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    """True range: the greatest of the three classic candle spans."""
    prev_close = close.shift(1)
    return pd.concat(
        [
            (high - low).abs(),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)


def atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Average True Range, Wilder-smoothed. Used for volatility-scaled sizing."""
    return _wilder(true_range(high, low, close), period)


def adx(
    high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Average Directional Index with the directional indicators.

    Returns:
        (adx, plus_di, minus_di), each in [0, 100].
    """
    high = high.astype("float64")
    low = low.astype("float64")

    up_move = high.diff()
    down_move = -low.diff()

    # A bar counts toward only one direction: whichever move was larger.
    plus_dm = pd.Series(
        np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=high.index
    )
    minus_dm = pd.Series(
        np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=high.index
    )

    smoothed_tr = _wilder(true_range(high, low, close), period)

    with np.errstate(divide="ignore", invalid="ignore"):
        plus_di = 100.0 * _wilder(plus_dm, period) / smoothed_tr
        minus_di = 100.0 * _wilder(minus_dm, period) / smoothed_tr

        di_sum = plus_di + minus_di
        dx = 100.0 * (plus_di - minus_di).abs() / di_sum

    # A flat market gives DI sum zero; there is no trend to measure, so DX is 0.
    dx = dx.where(di_sum != 0.0, 0.0)

    return _wilder(dx, period), plus_di, minus_di


def volume_ratio(volume: pd.Series, period: int = 20) -> pd.Series:
    """Current volume divided by its trailing average.

    The trailing window *excludes* the current bar. Including it would dampen
    exactly the spike the ratio is meant to detect, and makes a 1.2 threshold
    mean something different at different volatility levels.
    """
    volume = volume.astype("float64")
    trailing_mean = volume.shift(1).rolling(window=period, min_periods=period).mean()

    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = volume / trailing_mean

    return ratio.replace([np.inf, -np.inf], np.nan)


def slope(series: pd.Series, lookback: int = 1) -> pd.Series:
    """Change in a series over `lookback` bars.

    Used for momentum checks such as "RSI is rising", where the direction of an
    indicator matters as much as its level.
    """
    return series.astype("float64").diff(lookback)

