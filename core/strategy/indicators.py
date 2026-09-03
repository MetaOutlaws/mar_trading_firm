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


def bollinger_bands(
    close: pd.Series, period: int = 20, k: float = 2.0
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Mid (SMA), upper, and lower Bollinger bands. Uses population std (ddof=0)."""
    if period <= 0:
        raise ValueError(f"period must be positive, got {period}")
    if k <= 0:
        raise ValueError(f"band width k must be positive, got {k}")
    mid = sma(close, period)
    std = close.astype("float64").rolling(window=period, min_periods=period).std(ddof=0)
    width = std * k
    return mid, mid + width, mid - width


def utc_opening_range(
    high: pd.Series,
    low: pd.Series,
    *,
    range_hours: float = 1.0,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """High/low of the first `range_hours` of each UTC day.

    The range for day D is the max high / min low of bars whose UTC open is
    strictly inside `[00:00, range_hours)`. It is published only on later bars
    of that same day — never during the window, and never using a later day's
    bars. That is the no-lookahead contract: every post-window bar only sees
    window bars that already closed.

    Returns `(range_high, range_low, window_complete)`. Incomplete rows are NaN
    / False. This is not a rolling Donchian; the window is calendar-session.
    """
    if range_hours <= 0:
        raise ValueError(f"range_hours must be positive, got {range_hours}")
    if not high.index.equals(low.index):
        raise ValueError("high and low must share an index")
    index = high.index
    if not isinstance(index, pd.DatetimeIndex):
        raise ValueError("utc_opening_range needs a DatetimeIndex")
    if index.tz is None:
        utc_index = index.tz_localize("UTC")
    else:
        utc_index = index.tz_convert("UTC")

    day = utc_index.normalize()
    hours_into = (utc_index - day) / pd.Timedelta(hours=1)
    in_window = hours_into < float(range_hours)

    # Window extremes are computed from in-window bars only, then mapped onto
    # the whole day. During the window we blank them so a bar cannot trade
    # against a range that still includes future opening-range bars.
    day_key = pd.Series(day, index=high.index)
    day_high = high.where(in_window).groupby(day_key).max()
    day_low = low.where(in_window).groupby(day_key).min()
    range_high = pd.Series(day_key.map(day_high), index=high.index, dtype="float64")
    range_low = pd.Series(day_key.map(day_low), index=high.index, dtype="float64")
    complete = (~in_window) & range_high.notna() & range_low.notna()
    range_high = range_high.where(complete)
    range_low = range_low.where(complete)
    return range_high, range_low, complete.astype(bool)


def _as_utc_index(index: pd.Index) -> pd.DatetimeIndex:
    """Normalize a candle index to UTC. Strategies that use calendar math share this."""
    if not isinstance(index, pd.DatetimeIndex):
        raise ValueError("calendar indicators need a DatetimeIndex")
    if index.tz is None:
        return index.tz_localize("UTC")
    return index.tz_convert("UTC")


def utc_day_key(index: pd.Index) -> pd.Series:
    """UTC calendar date per bar."""
    utc_index = _as_utc_index(index)
    return pd.Series(utc_index.normalize(), index=index)


def utc_session_vwap(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    volume: pd.Series,
) -> pd.Series:
    """VWAP that resets at each UTC midnight. Typical price * volume, cumulative in-day.

    Bar t includes bar t's own volume. That is the usual session VWAP definition
    and uses only bars `<= t`.
    """
    if not high.index.equals(low.index) or not high.index.equals(close.index):
        raise ValueError("high, low, close must share an index")
    if not high.index.equals(volume.index):
        raise ValueError("volume must share the candle index")
    day = utc_day_key(close.index)
    typical = (high.astype("float64") + low.astype("float64") + close.astype("float64")) / 3.0
    pv = typical * volume.astype("float64")
    cum_pv = pv.groupby(day).cumsum()
    cum_vol = volume.astype("float64").groupby(day).cumsum()
    return cum_pv / cum_vol.replace(0, np.nan)


def utc_session_range(
    high: pd.Series,
    low: pd.Series,
    *,
    start_hour: float,
    end_hour: float,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """High/low of `[start_hour, end_hour)` UTC, published only after `end_hour`.

    Same no-lookahead contract as `utc_opening_range`: the box is blank while
    the session is still forming.
    """
    if end_hour <= start_hour:
        raise ValueError(f"end_hour must be > start_hour, got {start_hour}-{end_hour}")
    if not high.index.equals(low.index):
        raise ValueError("high and low must share an index")
    utc_index = _as_utc_index(high.index)
    day = utc_index.normalize()
    hours_into = (utc_index - day) / pd.Timedelta(hours=1)
    in_window = (hours_into >= float(start_hour)) & (hours_into < float(end_hour))
    day_key = pd.Series(day, index=high.index)
    day_high = high.where(in_window).groupby(day_key).max()
    day_low = low.where(in_window).groupby(day_key).min()
    range_high = pd.Series(day_key.map(day_high), index=high.index, dtype="float64")
    range_low = pd.Series(day_key.map(day_low), index=high.index, dtype="float64")
    complete = (hours_into >= float(end_hour)) & range_high.notna() & range_low.notna()
    return range_high.where(complete), range_low.where(complete), complete.astype(bool)


def prior_day_close(close: pd.Series) -> pd.Series:
    """Close of the previous UTC day. Known from the first bar of the new day."""
    day = utc_day_key(close.index)
    new_day = day.ne(day.shift(1))
    return close.shift(1).where(new_day).ffill()


def prior_day_floor_pivots(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Classic floor pivots from the prior completed UTC day: P, R1, S1.

    Published only after that day has closed. Intraday bars never see the same
    day's still-forming high/low.
    """
    if not high.index.equals(low.index) or not high.index.equals(close.index):
        raise ValueError("high, low, close must share an index")
    day = utc_day_key(close.index)
    new_day = day.ne(day.shift(1))
    # Last bar of the previous day is close/high/low.shift(1) at the first bar of today.
    prev_c = close.shift(1).where(new_day).ffill()
    # Day high/low of the previous day: take expanding max within day, then
    # snapshot it at the last bar (shift onto the next day). Using transform
    # max would leak later bars of the same day, so snapshot on new_day only.
    day_high = high.groupby(day).cummax()
    day_low = low.groupby(day).cummin()
    prev_h = day_high.shift(1).where(new_day).ffill()
    prev_l = day_low.shift(1).where(new_day).ffill()
    pivot = (prev_h + prev_l + prev_c) / 3.0
    r1 = (2.0 * pivot) - prev_l
    s1 = (2.0 * pivot) - prev_h
    return pivot, r1, s1


def prior_utc_day_range(high: pd.Series, low: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Prior completed UTC calendar day's high/low. Published after midnight.

    Calendar day box, not floor pivots (P/R1/S1) and not an Asian session
    window. Intraday bars never see the still-forming day's extrema: the
    snapshot is taken on the first bar of the new UTC day, then ffilled.
    """
    if not high.index.equals(low.index):
        raise ValueError("high and low must share an index")
    day = utc_day_key(high.index)
    new_day = day.ne(day.shift(1))
    # Same causal snapshot as prior_day_floor_pivots, without the pivot math.
    day_high = high.groupby(day).cummax()
    day_low = low.groupby(day).cummin()
    prev_h = day_high.shift(1).where(new_day).ffill()
    prev_l = day_low.shift(1).where(new_day).ffill()
    return prev_h, prev_l


def rolling_vwap(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    volume: pd.Series,
    period: int = 20,
) -> pd.Series:
    """Rolling typical-price VWAP. Does not reset at UTC midnight.

    Distinct from `utc_session_vwap` (session reset) and from `vwma`
    (close × volume, no typical price). Bar t uses bars ``t-period+1..t``
    only.
    """
    if period <= 0:
        raise ValueError(f"period must be positive, got {period}")
    if not high.index.equals(low.index) or not high.index.equals(close.index):
        raise ValueError("high, low, close must share an index")
    if not high.index.equals(volume.index):
        raise ValueError("volume must share the candle index")
    typical = (
        high.astype("float64") + low.astype("float64") + close.astype("float64")
    ) / 3.0
    pv = typical * volume.astype("float64")
    num = pv.rolling(window=period, min_periods=period).sum()
    den = volume.astype("float64").rolling(window=period, min_periods=period).sum()
    return num / den.replace(0, np.nan)


def bollinger_width(close: pd.Series, period: int = 20, k: float = 2.0) -> pd.Series:
    """Relative Bollinger Band Width: (upper - lower) / mid.

    Mid is the SMA. Zero/NaN mid is blanked. Bars ``<= t`` only.
    """
    mid, upper, lower = bollinger_bands(close, period, k)
    return (upper - lower) / mid.replace(0, np.nan)


def confirmed_swings(
    high: pd.Series,
    low: pd.Series,
    *,
    left: int = 3,
) -> tuple[pd.Series, pd.Series]:
    """Last confirmed swing high/low using a centered window that has already closed.

    At bar t the candidate pivot is bar t-left. It is confirmed when it is the
    max/min of `[t-2*left, t]`. No future bars after t are used. The series is
    shifted so bar t trades against a swing confirmed on an earlier bar.
    """
    if left <= 0:
        raise ValueError(f"left must be positive, got {left}")
    window = 2 * left + 1
    roll_high = high.rolling(window=window, min_periods=window).max()
    roll_low = low.rolling(window=window, min_periods=window).min()
    pivot_high = high.shift(left).where(high.shift(left) >= roll_high)
    pivot_low = low.shift(left).where(low.shift(left) <= roll_low)
    return pivot_high.ffill().shift(1), pivot_low.ffill().shift(1)


def friday_utc_close(close: pd.Series) -> pd.Series:
    """Last completed Friday UTC close, published Sat/Sun/Mon only."""
    utc_index = _as_utc_index(close.index)
    weekday = pd.Series(utc_index.dayofweek, index=close.index)
    friday_close = close.where(weekday.eq(4)).ffill()
    after_friday = weekday.isin([5, 6, 0])
    return friday_close.where(after_friday)


def engulfing_direction(open_: pd.Series, close: pd.Series) -> pd.Series:
    """+1 bullish engulfing, -1 bearish, 0 otherwise. Current body covers prior body."""
    body_high = pd.concat([open_, close], axis=1).max(axis=1)
    body_low = pd.concat([open_, close], axis=1).min(axis=1)
    prev_high = body_high.shift(1)
    prev_low = body_low.shift(1)
    bullish = (close > open_) & (close.shift(1) < open_.shift(1))
    bearish = (close < open_) & (close.shift(1) > open_.shift(1))
    covers = (body_high >= prev_high) & (body_low <= prev_low)
    out = pd.Series(0, index=close.index, dtype="int64")
    out = out.mask(bullish & covers, 1)
    out = out.mask(bearish & covers, -1)
    return out


def inside_bar_mother(
    high: pd.Series,
    low: pd.Series,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Mother-bar high/low when the prior bar was inside it. Ready on the break bar.

    Bar t-1 is inside bar t-2 when its range sits strictly inside t-2.
    The mother range is published on bar t (the first bar that may break it).
    """
    mother_high = high.shift(2)
    mother_low = low.shift(2)
    inside = (high.shift(1) < mother_high) & (low.shift(1) > mother_low)
    return mother_high.where(inside), mother_low.where(inside), inside.fillna(False)


def nr7_setup(high: pd.Series, low: pd.Series, *, lookback: int = 7) -> tuple[pd.Series, pd.Series, pd.Series]:
    """NR7 bar high/low published on the following bar, ready to break.

    Bar t-1 is NR7 when its range is the narrowest of the last `lookback` bars
    ending at t-1. Bar t may close through that range. Rolling min uses only
    bars `<= t-1` on the identification, then shift(1) so bar t never sees a
    later bar's range.
    """
    if lookback < 2:
        raise ValueError(f"lookback must be >= 2, got {lookback}")
    rng = (high.astype("float64") - low.astype("float64")).clip(lower=0.0)
    window_min = rng.rolling(window=lookback, min_periods=lookback).min()
    is_nr7 = rng.eq(window_min) & window_min.notna()
    setup = is_nr7.shift(1).eq(True)
    return high.shift(1).where(setup), low.shift(1).where(setup), setup.astype(bool)


def utc_session_twap(close: pd.Series) -> pd.Series:
    """Equal-weight TWAP that resets at UTC midnight. Not volume-weighted."""
    day = utc_day_key(close.index)
    count = close.groupby(day).cumcount() + 1
    return close.astype("float64").groupby(day).cumsum() / count


def prior_utc_week_range(high: pd.Series, low: pd.Series) -> tuple[pd.Series, pd.Series]:
    """High/low of the last completed UTC week (Mon–Sun). Blank until Sunday closes.

    In-week cummax/cummin is snapshotted onto the first bar of the next week.
    Mid-week bars never see the still-forming week's extreme.
    """
    if not high.index.equals(low.index):
        raise ValueError("high and low must share an index")
    utc_index = _as_utc_index(high.index)
    naive = utc_index.tz_localize(None) if utc_index.tz is not None else utc_index
    week = pd.Series(naive.to_period("W-SUN").astype(str), index=high.index)
    new_week = week.ne(week.shift(1))
    week_high = high.groupby(week).cummax()
    week_low = low.groupby(week).cummin()
    prev_h = week_high.shift(1).where(new_week).ffill()
    prev_l = week_low.shift(1).where(new_week).ffill()
    return prev_h, prev_l


def weekend_utc_range(
    high: pd.Series, low: pd.Series
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Sat 00:00–Sun 23:59 UTC high/low, published on the following Monday only.

    Calendar weekend box, not the Asian 00:00–08:00 session and not the
    Mon–Sun prior-week range. Saturday bars see Saturday extrema only
    (groupby cummax). Monday reads Sunday's last print via ffill, and only
    when that Sunday is yesterday and a Sunday bar actually printed.
    """
    if not high.index.equals(low.index):
        raise ValueError("high and low must share an index")
    utc_index = _as_utc_index(high.index)
    weekday = pd.Series(utc_index.dayofweek, index=high.index)
    in_weekend = weekday.isin([5, 6])
    dates = pd.Series(utc_index.normalize(), index=high.index)
    # Saturday belongs to the next calendar Sunday; Sunday keeps its own date.
    sunday = dates + pd.to_timedelta(weekday.eq(5).astype("int64"), unit="D")
    weekend_id = sunday.where(in_weekend)
    expanding_high = high.where(in_weekend).groupby(weekend_id).cummax()
    expanding_low = low.where(in_weekend).groupby(weekend_id).cummin()
    # Sunday-seen flag so a Saturday-only sample cannot publish as "complete".
    saw_sunday = (
        weekday.eq(6).astype("float64").where(in_weekend).groupby(weekend_id).cummax()
    )
    carried_high = expanding_high.ffill()
    carried_low = expanding_low.ffill()
    carried_sunday = weekend_id.ffill()
    expected_sunday = dates - pd.Timedelta(days=1)
    ready = (
        weekday.eq(0)
        & carried_sunday.eq(expected_sunday)
        & saw_sunday.ffill().eq(1.0)
        & carried_high.notna()
        & carried_low.notna()
    )
    return carried_high.where(ready), carried_low.where(ready), ready


def bar_buy_share(
    high: pd.Series, low: pd.Series, close: pd.Series
) -> pd.Series:
    """This bar's buying-volume share: (close - low) / (high - low).

    1.0 = close at the high (all buying), 0.0 = close at the low (all selling).
    Zero-range bars are 0.5. One bar only — do not cumsum. Not Elder Force,
    not OBV/VPT, and not the A/D running CLV ledger.
    """
    if not high.index.equals(low.index) or not high.index.equals(close.index):
        raise ValueError("high, low, close must share an index")
    span = high.astype("float64") - low.astype("float64")
    buy = (close.astype("float64") - low.astype("float64")) / span.replace(0, np.nan)
    return buy.where(span > 0, 0.5)


def psychological_round(price: pd.Series) -> pd.Series:
    """Nearest 1/10/100/1000 step from price magnitude. Not a floor pivot."""
    p = price.astype("float64")
    step = np.where(p >= 10_000, 1000.0, np.where(p >= 1_000, 100.0, np.where(p >= 100, 10.0, 1.0)))
    stepped = pd.Series(step, index=price.index, dtype="float64")
    return (p / stepped).round() * stepped


def doji_bar(open_: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series, *, max_body_frac: float = 0.1) -> pd.Series:
    """True when |close-open| / range is a small doji. Range 0 is not a doji."""
    body = (close.astype("float64") - open_.astype("float64")).abs()
    rng = (high.astype("float64") - low.astype("float64")).replace(0, np.nan)
    return (body / rng) <= float(max_body_frac)


def outside_bar(high: pd.Series, low: pd.Series) -> pd.Series:
    """True when this bar's range fully contains the prior bar's range."""
    return (high > high.shift(1)) & (low < low.shift(1))


def three_bar_play_setup(
    open_: pd.Series,
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Rest-bar high/low after a directional mother, ready to break on this bar.

    Bar t-2 is the trend bar (close vs open). Bar t-1 is a narrower inside rest.
    Direction is +1 (up mother) or -1 (down mother) on the break bar t.
    """
    mother_up = close.shift(2) > open_.shift(2)
    mother_down = close.shift(2) < open_.shift(2)
    rest_inside = (high.shift(1) < high.shift(2)) & (low.shift(1) > low.shift(2))
    rest_high = high.shift(1).where(rest_inside)
    rest_low = low.shift(1).where(rest_inside)
    direction = pd.Series(0, index=close.index, dtype="int64")
    direction = direction.mask(rest_inside & mother_up, 1)
    direction = direction.mask(rest_inside & mother_down, -1)
    return rest_high, rest_low, direction


def ny_cash_open_drive(
    open_: pd.Series,
    close: pd.Series,
) -> tuple[pd.Series, pd.Series]:
    """Direction of the 13:00 UTC (08:00 ET) hour, published only after 14:00.

    Returns `(direction, ready)` where direction is +1 bullish drive, -1 bearish.
    """
    utc_index = _as_utc_index(close.index)
    hour = pd.Series(utc_index.hour + utc_index.minute / 60.0, index=close.index)
    day = utc_day_key(close.index)
    is_drive = (hour >= 13.0) & (hour < 14.0)
    drive_open = open_.where(is_drive).groupby(day).ffill()
    drive_close = close.where(is_drive).groupby(day).ffill()
    ready = (hour >= 14.0) & drive_open.notna() & drive_close.notna()
    direction = pd.Series(0, index=close.index, dtype="int64")
    direction = direction.mask(ready & (drive_close > drive_open), 1)
    direction = direction.mask(ready & (drive_close < drive_open), -1)
    return direction, ready.astype(bool)


def prior_distinct_level(level: pd.Series) -> pd.Series:
    """Previous distinct value of a step-ffilled series (prior swing, not this one)."""
    changed = level.notna() & level.ne(level.shift(1))
    return level.shift(1).where(changed).ffill()


def stochastic_k(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Slow %K. Uses only bars <= t (rolling window ending at t)."""
    lowest = low.rolling(period, min_periods=period).min()
    highest = high.rolling(period, min_periods=period).max()
    span = (highest - lowest).replace(0, pd.NA)
    return 100.0 * (close - lowest) / span


def williams_r(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Williams %R in [-100, 0]. (HH-C)/(HH-LL)*-100. Causal rolling window."""
    lowest = low.rolling(period, min_periods=period).min()
    highest = high.rolling(period, min_periods=period).max()
    span = (highest - lowest).replace(0, pd.NA)
    return -100.0 * (highest - close) / span


def on_balance_volume(close: pd.Series, volume: pd.Series) -> pd.Series:
    """Causal OBV: signed volume accumulated using close vs prior close only."""
    close = close.astype("float64")
    volume = volume.astype("float64")
    direction = close.diff()
    signed = volume.where(direction > 0, 0.0)
    signed = signed.where(direction >= 0, -volume)
    signed.iloc[0] = 0.0
    return signed.cumsum()


def tenkan_kijun(
    high: pd.Series,
    low: pd.Series,
    *,
    tenkan_period: int = 9,
    kijun_period: int = 26,
) -> tuple[pd.Series, pd.Series]:
    """Ichimoku midpoints of past highs/lows. No displaced cloud (that would leak)."""
    tenkan = (high.rolling(tenkan_period, min_periods=tenkan_period).max() + low.rolling(tenkan_period, min_periods=tenkan_period).min()) / 2.0
    kijun = (high.rolling(kijun_period, min_periods=kijun_period).max() + low.rolling(kijun_period, min_periods=kijun_period).min()) / 2.0
    return tenkan, kijun


def money_flow_index(
    high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series, period: int = 14
) -> pd.Series:
    """MFI: RSI of typical-price * volume. Causal rolling sums."""
    typical = (high + low + close) / 3.0
    money = typical * volume.astype("float64")
    delta = typical.diff()
    pos = money.where(delta > 0, 0.0)
    neg = money.where(delta < 0, 0.0)
    pos_sum = pos.rolling(period, min_periods=period).sum()
    neg_sum = neg.rolling(period, min_periods=period).sum()
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = pos_sum / neg_sum.replace(0, np.nan)
    mfi = 100.0 - (100.0 / (1.0 + ratio))
    mfi = mfi.where(neg_sum != 0, 100.0)
    mfi = mfi.where(pos_sum != 0, 0.0)
    both_zero = (pos_sum == 0) & (neg_sum == 0)
    return mfi.where(~both_zero, 50.0)


def chaikin_oscillator(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    volume: pd.Series,
    *,
    fast: int = 3,
    slow: int = 10,
) -> pd.Series:
    """EMA(ADL, fast) - EMA(ADL, slow). CLV uses this bar's H/L/C only."""
    span = (high - low).replace(0, pd.NA)
    clv = ((close - low) - (high - close)) / span
    adl = (clv.fillna(0.0) * volume.astype("float64")).cumsum()
    return ema(adl, fast) - ema(adl, slow)


def chande_momentum(close: pd.Series, period: int = 14) -> pd.Series:
    """CMO in [-100, 100]. Sum of up vs down closes, not Wilder RSI."""
    delta = close.astype("float64").diff()
    up = delta.clip(lower=0.0).rolling(period, min_periods=period).sum()
    down = (-delta).clip(lower=0.0).rolling(period, min_periods=period).sum()
    denom = (up + down).replace(0, pd.NA)
    return 100.0 * (up - down) / denom


def vortex(
    high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
) -> tuple[pd.Series, pd.Series]:
    """+VI and -VI. VM uses prior bar only."""
    tr = true_range(high, low, close)
    vm_plus = (high - low.shift(1)).abs()
    vm_minus = (low - high.shift(1)).abs()
    tr_sum = tr.rolling(period, min_periods=period).sum().replace(0, pd.NA)
    plus_vi = vm_plus.rolling(period, min_periods=period).sum() / tr_sum
    minus_vi = vm_minus.rolling(period, min_periods=period).sum() / tr_sum
    return plus_vi, minus_vi


def causal_dpo(close: pd.Series, period: int = 20) -> pd.Series:
    """DPO with SMA lagged by N/2+1 past bars only (no centered future SMA)."""
    lag = period // 2 + 1
    mid = sma(close, period)
    return close.astype("float64") - mid.shift(lag)


def trix(close: pd.Series, period: int = 15) -> pd.Series:
    """Rate of change of a triple EMA."""
    e1 = ema(close, period)
    e2 = ema(e1, period)
    e3 = ema(e2, period)
    prev = e3.shift(1).replace(0, pd.NA)
    return 100.0 * (e3 - e3.shift(1)) / prev.abs()


def force_index(close: pd.Series, volume: pd.Series, period: int = 13) -> pd.Series:
    """EMA of (close-prior close)*volume."""
    raw = close.astype("float64").diff() * volume.astype("float64")
    return ema(raw.fillna(0.0), period)


def atr_normalized_volume_force(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    volume: pd.Series,
    atr_period: int = 14,
) -> pd.Series:
    """Signed volume scaled by close-to-close change / ATR.

    Not Elder Force Index (no EMA of raw ΔC*V) and not OBV (no ATR scale).
    """
    rng = atr(high, low, close, atr_period).replace(0, np.nan)
    delta = close.astype("float64").diff()
    raw = (delta / rng) * volume.astype("float64")
    return raw.fillna(0.0)


def cumulative_volume_force(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    volume: pd.Series,
    atr_period: int = 14,
) -> pd.Series:
    """Running sum of ATR-normalized volume force. Bars ``<= t`` only."""
    return atr_normalized_volume_force(high, low, close, volume, atr_period).cumsum()


def awesome_oscillator(high: pd.Series, low: pd.Series) -> pd.Series:
    """SMA(HL2,5) - SMA(HL2,34)."""
    hl2 = (high + low) / 2.0
    return sma(hl2, 5) - sma(hl2, 34)


def aroon(high: pd.Series, low: pd.Series, period: int = 25) -> tuple[pd.Series, pd.Series]:
    """Aroon up/down: 100 * (period - bars-since-extreme) / period. Loop is causal."""
    values_h = high.astype("float64").to_numpy()
    values_l = low.astype("float64").to_numpy()
    n = len(values_h)
    up = np.full(n, np.nan)
    down = np.full(n, np.nan)
    for i in range(period - 1, n):
        window_h = values_h[i - period + 1 : i + 1]
        window_l = values_l[i - period + 1 : i + 1]
        bars_since_high = period - 1 - int(np.argmax(window_h))
        bars_since_low = period - 1 - int(np.argmin(window_l))
        up[i] = 100.0 * (period - bars_since_high) / period
        down[i] = 100.0 * (period - bars_since_low) / period
    return pd.Series(up, index=high.index), pd.Series(down, index=low.index)


def ppo(
    close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple[pd.Series, pd.Series]:
    """Percentage Price Oscillator and its signal EMA. Percent MACD, not price units."""
    if fast >= slow:
        raise ValueError(f"fast ({fast}) must be less than slow ({slow})")
    slow_ema = ema(close, slow).replace(0, np.nan)
    line = 100.0 * (ema(close, fast) - slow_ema) / slow_ema
    return line, ema(line, signal)


def ultimate_oscillator(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    *,
    short: int = 7,
    mid: int = 14,
    long: int = 28,
) -> pd.Series:
    """Williams Ultimate Oscillator: 4/2/1 weighted BP/TR averages over 7/14/28."""
    prev = close.shift(1)
    floor = pd.concat([low.astype("float64"), prev], axis=1).min(axis=1)
    buying = close.astype("float64") - floor
    tr = true_range(high, low, close)

    def _avg(window: int) -> pd.Series:
        denom = tr.rolling(window, min_periods=window).sum().replace(0, np.nan)
        return buying.rolling(window, min_periods=window).sum() / denom

    return 100.0 * (4.0 * _avg(short) + 2.0 * _avg(mid) + _avg(long)) / 7.0


def kst(
    close: pd.Series,
    *,
    roc: tuple[int, int, int, int] = (10, 15, 20, 30),
    sma_len: tuple[int, int, int, int] = (10, 10, 10, 15),
    signal: int = 9,
) -> tuple[pd.Series, pd.Series]:
    """Know Sure Thing: weighted SMAs of four ROCs, plus a signal SMA. Not MACD."""
    close = close.astype("float64")
    line = None
    for weight, roc_n, win in zip((1.0, 2.0, 3.0, 4.0), roc, sma_len):
        prev = close.shift(roc_n).replace(0, np.nan)
        rate = 100.0 * (close - close.shift(roc_n)) / prev.abs()
        term = weight * sma(rate, win)
        line = term if line is None else line + term
    return line, sma(line, signal)


def tsi(close: pd.Series, long: int = 25, short: int = 13) -> pd.Series:
    """True Strength Index: double-smoothed momentum over double-smoothed |momentum|."""
    mom = close.astype("float64").diff()
    num = ema(ema(mom.fillna(0.0), long), short)
    den = ema(ema(mom.abs().fillna(0.0), long), short).replace(0, np.nan)
    return 100.0 * num / den


def fisher_transform(
    high: pd.Series, low: pd.Series, period: int = 10
) -> tuple[pd.Series, pd.Series]:
    """Ehlers Fisher Transform of median price, plus the prior-bar trigger.

    Maps a normalized high-low median onto a Gaussian. Recursive 0.5 blend uses
    only bars ``<= t``. Trigger is the previous Fisher value, not a z-score of close.
    """
    median = (high.astype("float64") + low.astype("float64")) / 2.0
    highest = median.rolling(period, min_periods=period).max()
    lowest = median.rolling(period, min_periods=period).min()
    span = (highest - lowest).replace(0, np.nan)
    raw = (2.0 * ((median - lowest) / span - 0.5)).clip(-0.999, 0.999)
    values = np.full(len(raw), np.nan)
    prev = 0.0
    started = False
    for i, x in enumerate(raw.to_numpy()):
        if np.isnan(x):
            continue
        fish = 0.5 * np.log((1.0 + x) / (1.0 - x)) + (0.5 * prev if started else 0.0)
        values[i] = fish
        prev = fish
        started = True
    line = pd.Series(values, index=raw.index)
    return line, line.shift(1)


def wma(series: pd.Series, period: int) -> pd.Series:
    """Linear weighted moving average. Newest bar has the largest weight."""
    weights = np.arange(1, period + 1, dtype="float64")

    def _dot(window: np.ndarray) -> float:
        return float(np.dot(window, weights) / weights.sum())

    return series.astype("float64").rolling(period, min_periods=period).apply(_dot, raw=True)


def hull_ma(close: pd.Series, period: int = 16) -> pd.Series:
    """Hull Moving Average: WMA(2*WMA(n/2) - WMA(n), sqrt(n)). Not EMA/SMA."""
    n = max(int(period), 2)
    half = max(n // 2, 1)
    hull_len = max(int(round(n ** 0.5)), 1)
    return wma(2.0 * wma(close, half) - wma(close, n), hull_len)


def elder_ray(
    high: pd.Series, low: pd.Series, close: pd.Series, period: int = 13
) -> tuple[pd.Series, pd.Series]:
    """Elder Ray Bull/Bear Power: high-EMA and low-EMA. Not ATR channel, not Force Index."""
    mid = ema(close, period)
    return high.astype("float64") - mid, low.astype("float64") - mid


def _range_stoch(series: pd.Series, period: int) -> pd.Series:
    """Stochastic %K of an arbitrary series. Bars ``<= t`` only."""
    lo = series.rolling(period, min_periods=period).min()
    hi = series.rolling(period, min_periods=period).max()
    return 100.0 * (series - lo) / (hi - lo).replace(0, np.nan)


def schaff_trend(
    close: pd.Series,
    *,
    fast: int = 23,
    slow: int = 50,
    cycle: int = 10,
    smooth: int = 3,
) -> pd.Series:
    """Schaff Trend Cycle: stochastic of MACD, then a second stochastic. Not %K of price."""
    macd_line = ema(close, fast) - ema(close, slow)
    first = ema(_range_stoch(macd_line, cycle), smooth)
    return ema(_range_stoch(first, cycle), smooth)


def mass_index(high: pd.Series, low: pd.Series, ema_len: int = 9, sum_len: int = 25) -> pd.Series:
    """Mass Index: 25-bar sum of EMA(high-low)/EMA of that EMA. Range-ratio bulge, not BB width."""
    span = (high.astype("float64") - low.astype("float64")).clip(lower=0.0)
    single = ema(span, ema_len)
    double = ema(single, ema_len).replace(0, np.nan)
    return (single / double).rolling(sum_len, min_periods=sum_len).sum()


def ease_of_movement(
    high: pd.Series, low: pd.Series, volume: pd.Series, period: int = 14
) -> pd.Series:
    """Ease of Movement: midpoint change scaled by volume/range, then SMA. Not Force Index."""
    mid = (high.astype("float64") + low.astype("float64")) / 2.0
    box = volume.astype("float64") / (high - low).replace(0, np.nan)
    return sma(mid.diff() / box.replace(0, np.nan), period)


def coppock_curve(
    close: pd.Series, *, roc_long: int = 14, roc_short: int = 11, wma_len: int = 10
) -> pd.Series:
    """Coppock Curve: WMA of ROC(14)+ROC(11). Not MACD and not TRIX."""
    close = close.astype("float64")
    roc = 100.0 * (
        (close - close.shift(roc_long)) / close.shift(roc_long).abs().replace(0, np.nan)
        + (close - close.shift(roc_short)) / close.shift(roc_short).abs().replace(0, np.nan)
    )
    return wma(roc, wma_len)


def qstick(open_: pd.Series, close: pd.Series, period: int = 8) -> pd.Series:
    """Qstick: SMA of (close-open). Candle-body oscillator, not Heikin-Ashi."""
    return sma(close.astype("float64") - open_.astype("float64"), period)


def relative_vigor(
    open_: pd.Series,
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 10,
    signal: int = 4,
) -> tuple[pd.Series, pd.Series]:
    """RVI: SMA(close-open)/SMA(high-low) vs a signal SMA. Not Qstick."""
    body = close.astype("float64") - open_.astype("float64")
    span = (high.astype("float64") - low.astype("float64")).replace(0, np.nan)
    line = sma(body, period) / sma(span, period)
    return line, sma(line, signal)


def klinger_volume(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    volume: pd.Series,
    *,
    fast: int = 34,
    slow: int = 55,
    signal: int = 13,
) -> tuple[pd.Series, pd.Series]:
    """Klinger Volume Oscillator: signed volume from HLC trend. Not Force Index."""
    h = high.astype("float64").to_numpy()
    l = low.astype("float64").to_numpy()
    c = close.astype("float64").to_numpy()
    v = volume.astype("float64").to_numpy()
    n = len(c)
    vf = np.zeros(n)
    trend = 1.0
    cm = 0.0
    prev_dm = 0.0
    prev_hlc = h[0] + l[0] + c[0] if n else 0.0
    for i in range(n):
        dm = h[i] - l[i]
        hlc = h[i] + l[i] + c[i]
        next_trend = 1.0 if hlc >= prev_hlc else -1.0
        if i == 0 or next_trend == trend:
            cm = cm + dm
        else:
            cm = prev_dm + dm
        trend = next_trend
        if cm != 0:
            vf[i] = v[i] * abs(2.0 * dm / cm - 1.0) * trend * 100.0
        prev_dm, prev_hlc = dm, hlc
    osc = ema(pd.Series(vf, index=close.index), fast) - ema(
        pd.Series(vf, index=close.index), slow
    )
    return osc, ema(osc, signal)


def kaufman_efficiency(close: pd.Series, period: int = 10) -> pd.Series:
    """Kaufman Efficiency Ratio: net move over path length. Not ADX."""
    close = close.astype("float64")
    change = (close - close.shift(period)).abs()
    path = close.diff().abs().rolling(period, min_periods=period).sum().replace(0, np.nan)
    return change / path


def demarker(high: pd.Series, low: pd.Series, period: int = 14) -> pd.Series:
    """DeMarker: SMA(DeMax)/(SMA(DeMax)+SMA(DeMin)) from high-to-high and low-to-low steps."""
    high = high.astype("float64")
    low = low.astype("float64")
    up = (high - high.shift(1)).clip(lower=0.0)
    down = (low.shift(1) - low).clip(lower=0.0)
    de_max = sma(up, period)
    de_min = sma(down, period)
    return de_max / (de_max + de_min).replace(0, np.nan)


def choppiness_index(
    high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
) -> pd.Series:
    """Choppiness Index: 100*log10(sum(ATR)/range)/log10(n). Not BB width, not ADX."""
    atr_sum = true_range(high, low, close).rolling(period, min_periods=period).sum()
    span = (
        high.rolling(period, min_periods=period).max()
        - low.rolling(period, min_periods=period).min()
    ).replace(0, np.nan)
    return 100.0 * np.log10(atr_sum / span) / np.log10(float(period))


def psychological_line(close: pd.Series, period: int = 12) -> pd.Series:
    """PSY: 100 * share of up-closes over N. Count of up days, not RSI."""
    up = (close.astype("float64") > close.astype("float64").shift(1)).astype("float64")
    return 100.0 * sma(up, period)


def kairi_relative(close: pd.Series, period: int = 20) -> pd.Series:
    """Kairi Relative Index: 100*(close-SMA)/SMA. Percent from mean, not Bollinger z."""
    mid = sma(close, period).replace(0, np.nan)
    return 100.0 * (close.astype("float64") - mid) / mid


def linreg_slope(close: pd.Series, period: int = 20) -> pd.Series:
    """OLS slope of close over N bars. A fit, not an EMA difference."""
    x = np.arange(period, dtype="float64")
    x = x - x.mean()
    denom = float((x * x).sum()) or np.nan

    def _slope(window: np.ndarray) -> float:
        y = window - window.mean()
        return float((x * y).sum() / denom)

    return close.astype("float64").rolling(period, min_periods=period).apply(_slope, raw=True)


def ehlers_highpass(close: pd.Series, period: int = 20) -> pd.Series:
    """One-pole Ehlers high-pass of close. Causal recursion, bars ``<= t`` only."""
    c = close.astype("float64").to_numpy()
    n = len(c)
    hp = np.full(n, np.nan)
    a = float(np.exp(-2.0 * np.pi / max(period, 2)))
    gain = 0.5 * (1.0 + a)
    for i in range(n):
        if i == 0:
            hp[i] = 0.0
            continue
        hp[i] = gain * (c[i] - c[i - 1]) + a * hp[i - 1]
    return pd.Series(hp, index=close.index)


def ehlers_decycler(close: pd.Series, fast: int = 20, slow: int = 40) -> pd.Series:
    """Decycler oscillator: fast high-pass minus slow high-pass. Not DPO."""
    return ehlers_highpass(close, fast) - ehlers_highpass(close, slow)


def volume_price_trend(close: pd.Series, volume: pd.Series) -> pd.Series:
    """VPT: cumulative percent-change * volume. Not sign-only OBV."""
    ret = close.astype("float64").pct_change().fillna(0.0)
    return (ret * volume.astype("float64")).cumsum()


def balance_of_power(
    open_: pd.Series, high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
) -> pd.Series:
    """BOP: SMA of (close-open)/(high-low). Single-bar body/range, not RVI."""
    span = (high.astype("float64") - low.astype("float64")).replace(0, np.nan)
    raw = (close.astype("float64") - open_.astype("float64")) / span
    return sma(raw, period)


def twiggs_money_flow(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    volume: pd.Series,
    period: int = 21,
) -> pd.Series:
    """Twiggs Money Flow: TR-buffered AD volume over EMA(volume). Not MFI."""
    tr = true_range(high, low, close).replace(0, np.nan)
    ad = volume.astype("float64") * (2.0 * close.astype("float64") - high - low) / tr
    return ema(ad, period) / ema(volume.astype("float64"), period).replace(0, np.nan)


def parabolic_sar_direction(
    high: pd.Series,
    low: pd.Series,
    *,
    af_start: float = 0.02,
    af_step: float = 0.02,
    af_max: float = 0.20,
) -> tuple[pd.Series, pd.Series]:
    """Wilder Parabolic SAR and trend (+1 below price, -1 above). Not SuperTrend ATR bands."""
    h = high.astype("float64").to_numpy()
    l = low.astype("float64").to_numpy()
    n = len(h)
    sar = np.full(n, np.nan)
    direction = np.zeros(n, dtype="int64")
    if n == 0:
        return pd.Series(sar, index=high.index), pd.Series(direction, index=high.index)
    trend = 1
    af = af_start
    ep = h[0]
    sar[0] = l[0]
    direction[0] = 1
    for i in range(1, n):
        prev = sar[i - 1]
        nxt = prev + af * (ep - prev)
        if trend == 1:
            nxt = min(nxt, l[i - 1], l[i - 2] if i >= 2 else l[i - 1])
            if l[i] < nxt:
                trend = -1
                sar[i] = ep
                ep = l[i]
                af = af_start
            else:
                sar[i] = nxt
                if h[i] > ep:
                    ep = h[i]
                    af = min(af_max, af + af_step)
        else:
            nxt = max(nxt, h[i - 1], h[i - 2] if i >= 2 else h[i - 1])
            if h[i] > nxt:
                trend = 1
                sar[i] = ep
                ep = h[i]
                af = af_start
            else:
                sar[i] = nxt
                if l[i] < ep:
                    ep = l[i]
                    af = min(af_max, af + af_step)
        direction[i] = trend
    return pd.Series(sar, index=high.index), pd.Series(direction, index=high.index)


def center_of_gravity(close: pd.Series, period: int = 10) -> tuple[pd.Series, pd.Series]:
    """Ehlers Center of Gravity of the last N closes, plus prior-bar trigger."""
    weights = np.arange(period, 0, -1, dtype="float64")

    def _cg(window: np.ndarray) -> float:
        den = float(window.sum())
        if den == 0:
            return float("nan")
        return float(-np.dot(weights, window) / den)

    line = close.astype("float64").rolling(period, min_periods=period).apply(_cg, raw=True)
    return line, line.shift(1)


def mama_fama(
    close: pd.Series, *, fastlimit: float = 0.5, slowlimit: float = 0.05
) -> tuple[pd.Series, pd.Series]:
    """Ehlers MAMA/FAMA from a causal Hilbert period. Not a fixed EMA cross."""
    c = close.astype("float64").to_numpy()
    n = len(c)
    mama = np.full(n, np.nan)
    fama = np.full(n, np.nan)
    smooth = np.zeros(n)
    detrender = np.zeros(n)
    i1 = np.zeros(n)
    q1 = np.zeros(n)
    i2 = np.zeros(n)
    q2 = np.zeros(n)
    re = np.zeros(n)
    im = np.zeros(n)
    period = 20.0
    for t in range(n):
        if t == 0:
            mama[t] = fama[t] = c[t]
            continue
        if t < 6:
            mama[t] = c[t]
            fama[t] = c[t]
            continue
        smooth[t] = (4.0 * c[t] + 3.0 * c[t - 1] + 2.0 * c[t - 2] + c[t - 3]) / 10.0
        sp = 0.075 * period + 0.54
        detrender[t] = (
            0.0962 * smooth[t]
            + 0.5769 * smooth[t - 2]
            - 0.5769 * smooth[t - 4]
            - 0.0962 * smooth[t - 6]
        ) * sp
        q1[t] = (
            0.0962 * detrender[t]
            + 0.5769 * detrender[t - 2]
            - 0.5769 * detrender[t - 4]
            - 0.0962 * detrender[t - 6]
        ) * sp
        i1[t] = detrender[t - 3]
        j_i = (
            0.0962 * i1[t]
            + 0.5769 * i1[t - 2]
            - 0.5769 * i1[t - 4]
            - 0.0962 * i1[t - 6]
        ) * sp
        j_q = (
            0.0962 * q1[t]
            + 0.5769 * q1[t - 2]
            - 0.5769 * q1[t - 4]
            - 0.0962 * q1[t - 6]
        ) * sp
        i2[t] = 0.2 * (i1[t] - j_q) + 0.8 * i2[t - 1]
        q2[t] = 0.2 * (q1[t] + j_i) + 0.8 * q2[t - 1]
        re[t] = 0.2 * (i2[t] * i2[t - 1] + q2[t] * q2[t - 1]) + 0.8 * re[t - 1]
        im[t] = 0.2 * (i2[t] * q2[t - 1] - q2[t] * i2[t - 1]) + 0.8 * im[t - 1]
        if re[t] != 0.0:
            period = 2.0 * np.pi / max(abs(np.arctan(im[t] / re[t])), 1e-6)
        period = min(50.0, max(6.0, period))
        alpha = min(fastlimit, max(slowlimit, fastlimit / period))
        mama[t] = alpha * c[t] + (1.0 - alpha) * mama[t - 1]
        fama[t] = 0.5 * alpha * mama[t] + (1.0 - 0.5 * alpha) * fama[t - 1]
    return pd.Series(mama, index=close.index), pd.Series(fama, index=close.index)


def connors_rsi(
    close: pd.Series, *, rsi_len: int = 3, streak_len: int = 2, rank_len: int = 100
) -> pd.Series:
    """Connors RSI: average of RSI(3), streak RSI, and ROC percent-rank. Not Wilder RSI alone."""
    close = close.astype("float64")
    chg = np.sign(close.diff().fillna(0.0).to_numpy())
    streak = np.zeros(len(close))
    for i in range(1, len(close)):
        if chg[i] > 0:
            streak[i] = streak[i - 1] + 1.0 if streak[i - 1] > 0 else 1.0
        elif chg[i] < 0:
            streak[i] = streak[i - 1] - 1.0 if streak[i - 1] < 0 else -1.0
        else:
            streak[i] = 0.0
    streak_s = pd.Series(streak, index=close.index)
    roc = close.diff()
    rank = roc.rolling(rank_len, min_periods=rank_len).apply(
        lambda w: 100.0 * float(np.mean(w <= w[-1])), raw=True
    )
    return (rsi(close, rsi_len) + rsi(streak_s, streak_len) + rank) / 3.0


def rsi_laguerre(close: pd.Series, gamma: float = 0.5) -> pd.Series:
    """Ehlers Laguerre RSI: 4-pole Laguerre filter of close mapped to 0..1.

    Not Wilder RSI and not Connors RSI. Each bar uses only ``close[<= t]``.
    """
    c = close.astype("float64").to_numpy()
    n = len(c)
    out = np.full(n, np.nan)
    g = float(np.clip(gamma, 0.01, 0.99))
    l0 = l1 = l2 = l3 = 0.0
    for i in range(n):
        prev0, prev1, prev2, prev3 = l0, l1, l2, l3
        if i == 0:
            l0 = l1 = l2 = l3 = c[i]
        else:
            l0 = (1.0 - g) * c[i] + g * prev0
            l1 = -g * l0 + prev0 + g * prev1
            l2 = -g * l1 + prev1 + g * prev2
            l3 = -g * l2 + prev2 + g * prev3
        cu = cd = 0.0
        if l0 >= l1:
            cu += l0 - l1
        else:
            cd += l1 - l0
        if l1 >= l2:
            cu += l1 - l2
        else:
            cd += l2 - l1
        if l2 >= l3:
            cu += l2 - l3
        else:
            cd += l3 - l2
        denom = cu + cd
        out[i] = 0.0 if denom == 0.0 else cu / denom
    return pd.Series(out, index=close.index)


def cci(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 20) -> pd.Series:
    """Commodity Channel Index. Typical price vs its SMA, scaled by mean deviation."""
    typical = (high + low + close) / 3.0
    mid = typical.rolling(period, min_periods=period).mean()
    mad = (typical - mid).abs().rolling(period, min_periods=period).mean()
    return (typical - mid) / (0.015 * mad.replace(0, pd.NA))


def supertrend_direction(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    *,
    period: int = 10,
    multiplier: float = 3.0,
) -> pd.Series:
    """Causal SuperTrend: +1 in uptrend, -1 in downtrend. No future bars."""
    atr_ = atr(high, low, close, period)
    hl2 = (high + low) / 2.0
    basic_upper = hl2 + multiplier * atr_
    basic_lower = hl2 - multiplier * atr_
    n = len(close)
    direction = pd.Series(0, index=close.index, dtype="int64")
    final_upper = pd.Series(index=close.index, dtype="float64")
    final_lower = pd.Series(index=close.index, dtype="float64")
    prev_u = float("nan")
    prev_l = float("nan")
    prev_dir = 0
    prev_close = float("nan")
    for i in range(n):
        bu = float(basic_upper.iloc[i]) if pd.notna(basic_upper.iloc[i]) else float("nan")
        bl = float(basic_lower.iloc[i]) if pd.notna(basic_lower.iloc[i]) else float("nan")
        c = float(close.iloc[i])
        if bu != bu or bl != bl:
            continue
        if prev_u != prev_u:
            fu, fl = bu, bl
        else:
            fu = bu if (bu < prev_u or prev_close > prev_u) else prev_u
            fl = bl if (bl > prev_l or prev_close < prev_l) else prev_l
        if prev_dir >= 0:
            d = -1 if c < fu else 1
        else:
            d = 1 if c > fl else -1
        final_upper.iloc[i] = fu
        final_lower.iloc[i] = fl
        direction.iloc[i] = d
        prev_u, prev_l, prev_dir, prev_close = fu, fl, d, c
    return direction


def heikin_ashi(
    open_: pd.Series,
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
) -> pd.DataFrame:
    """Causal Heikin-Ashi OHLC. HA open at t uses only HA values at t-1."""
    n = len(close)
    ha_close = (open_ + high + low + close) / 4.0
    ha_open = np.empty(n, dtype="float64")
    ha_high = np.empty(n, dtype="float64")
    ha_low = np.empty(n, dtype="float64")
    o0 = float(open_.iloc[0])
    c0 = float(close.iloc[0])
    ha_open[0] = (o0 + c0) / 2.0
    for i in range(n):
        hc = float(ha_close.iloc[i])
        if i > 0:
            ha_open[i] = (ha_open[i - 1] + float(ha_close.iloc[i - 1])) / 2.0
        ho = ha_open[i]
        ha_high[i] = max(float(high.iloc[i]), ho, hc)
        ha_low[i] = min(float(low.iloc[i]), ho, hc)
    return pd.DataFrame(
        {
            "ha_open": ha_open,
            "ha_high": ha_high,
            "ha_low": ha_low,
            "ha_close": ha_close.to_numpy(),
        },
        index=close.index,
    )


def vidya(close: pd.Series, period: int = 9) -> pd.Series:
    """Chande VIDYA: CMO-scaled EMA of close. Not Kaufman ER and not MAMA."""
    momentum = chande_momentum(close, period)
    sc = 2.0 / (float(period) + 1.0)
    alpha = (momentum.abs() / 100.0) * sc
    values = close.astype("float64").to_numpy()
    gains = alpha.to_numpy()
    out = np.full(len(values), np.nan)
    prev = np.nan
    for i, (price, a) in enumerate(zip(values, gains)):
        if a != a:
            continue
        prev = price if prev != prev else a * price + (1.0 - a) * prev
        out[i] = prev
    return pd.Series(out, index=close.index)


def tillson_t3(close: pd.Series, period: int = 5, vfactor: float = 0.7) -> pd.Series:
    """Tillson T3: six cascaded EMAs with a volume factor. Not Hull MA."""
    e1 = ema(close, period)
    e2 = ema(e1, period)
    e3 = ema(e2, period)
    e4 = ema(e3, period)
    e5 = ema(e4, period)
    e6 = ema(e5, period)
    v = float(vfactor)
    c1 = -(v ** 3)
    c2 = 3.0 * (v ** 2) + 3.0 * (v ** 3)
    c3 = -6.0 * (v ** 2) - 3.0 * v - 3.0 * (v ** 3)
    c4 = 1.0 + 3.0 * v + 3.0 * (v ** 2) + (v ** 3)
    return c1 * e6 + c2 * e5 + c3 * e4 + c4 * e3


def zero_lag_ema(close: pd.Series, period: int = 10) -> pd.Series:
    """Ehlers zero-lag EMA: 2*EMA - EMA(EMA). Not a raw EMA MACD."""
    first = ema(close, period)
    return 2.0 * first - ema(first, period)


def laguerre_filter(close: pd.Series, gamma: float = 0.5) -> pd.Series:
    """Ehlers 4-pole Laguerre filter of close. FIR of the poles, not Laguerre RSI."""
    c = close.astype("float64").to_numpy()
    n = len(c)
    out = np.full(n, np.nan)
    g = float(np.clip(gamma, 0.01, 0.99))
    l0 = l1 = l2 = l3 = 0.0
    for i in range(n):
        prev0, prev1, prev2, prev3 = l0, l1, l2, l3
        if i == 0:
            l0 = l1 = l2 = l3 = c[i]
        else:
            l0 = (1.0 - g) * c[i] + g * prev0
            l1 = -g * l0 + prev0 + g * prev1
            l2 = -g * l1 + prev1 + g * prev2
            l3 = -g * l2 + prev2 + g * prev3
        out[i] = (l0 + 2.0 * l1 + 2.0 * l2 + l3) / 6.0
    return pd.Series(out, index=close.index)


def accumulation_distribution(
    high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series
) -> pd.Series:
    """A/D line: cumulative CLV * volume. Not sign-only OBV."""
    span = (high.astype("float64") - low.astype("float64")).replace(0, np.nan)
    clv = ((close.astype("float64") - low) - (high - close)) / span
    return (clv.fillna(0.0) * volume.astype("float64")).cumsum()


def chaikin_money_flow(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    volume: pd.Series,
    period: int = 20,
) -> pd.Series:
    """Windowed CLV volume ratio. Not Twiggs TR-buffer and not Chaikin Oscillator."""
    span = (high.astype("float64") - low.astype("float64")).replace(0, np.nan)
    clv = ((close.astype("float64") - low) - (high - close)) / span
    flow = clv.fillna(0.0) * volume.astype("float64")
    denom = volume.astype("float64").rolling(period, min_periods=period).sum().replace(0, np.nan)
    return flow.rolling(period, min_periods=period).sum() / denom


def stochastic_momentum_index(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    q: int = 25,
    r: int = 13,
    s: int = 2,
) -> pd.Series:
    """SMI: double-smoothed close vs HH/LL midpoint. Not Stochastic %K."""
    hh = high.astype("float64").rolling(q, min_periods=q).max()
    ll = low.astype("float64").rolling(q, min_periods=q).min()
    mid = (hh + ll) / 2.0
    ds = ema(ema(close.astype("float64") - mid, r), s)
    dhl = ema(ema(hh - ll, r), s)
    return 100.0 * ds / (dhl / 2.0).replace(0, np.nan)


def rainbow_oscillator(close: pd.Series, steps: int = 10, step: int = 2) -> pd.Series:
    """Rainbow Oscillator: close vs the SMA ribbon, scaled by ribbon width."""
    smas = [sma(close, int(step) * (i + 1)) for i in range(int(steps))]
    stacked = pd.concat(smas, axis=1)
    hi = stacked.max(axis=1)
    lo = stacked.min(axis=1)
    mid = stacked.mean(axis=1)
    width = (hi - lo).replace(0, np.nan)
    return 100.0 * (close.astype("float64") - mid) / width


def elder_impulse(
    close: pd.Series,
    ema_len: int = 13,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> pd.Series:
    """Elder Impulse color: +1 green, -1 red, 0 blue. EMA slope AND MACD hist."""
    mid = ema(close, ema_len)
    _line, _sig, hist = macd(close, fast=fast, slow=slow, signal=signal)
    ema_up = mid > mid.shift(1)
    hist_up = hist > hist.shift(1)
    color = pd.Series(0, index=close.index, dtype="int64")
    color = color.mask(ema_up & hist_up, 1)
    color = color.mask((~ema_up) & (~hist_up), -1)
    return color.fillna(0).astype("int64")


def gator_lines(
    high: pd.Series,
    low: pd.Series,
    *,
    jaw: int = 13,
    teeth: int = 8,
    lips: int = 5,
    jaw_off: int = 8,
    teeth_off: int = 5,
    lips_off: int = 3,
) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series, pd.Series]:
    """Bill Williams Gator: lagged SMMA of median price. Offsets are past bars only."""
    median = (high.astype("float64") + low.astype("float64")) / 2.0
    jaw_line = _wilder(median, jaw).shift(jaw_off)
    teeth_line = _wilder(median, teeth).shift(teeth_off)
    lips_line = _wilder(median, lips).shift(lips_off)
    upper = (jaw_line - teeth_line).abs()
    lower = (teeth_line - lips_line).abs()
    return upper, lower, jaw_line, teeth_line, lips_line


def williams_fractals(high: pd.Series, low: pd.Series) -> tuple[pd.Series, pd.Series]:
    """Last confirmed 5-bar Williams fractal high/low. Confirm at t using bars t-4..t."""
    hv = high.astype("float64").to_numpy()
    lv = low.astype("float64").to_numpy()
    n = len(hv)
    last_up = np.full(n, np.nan)
    last_down = np.full(n, np.nan)
    up = np.nan
    down = np.nan
    for i in range(n):
        if i >= 4:
            pivot = i - 2
            peak = hv[pivot]
            if peak > hv[i - 4] and peak > hv[i - 3] and peak > hv[i - 1] and peak > hv[i]:
                up = peak
            trough = lv[pivot]
            if trough < lv[i - 4] and trough < lv[i - 3] and trough < lv[i - 1] and trough < lv[i]:
                down = trough
        last_up[i] = up
        last_down[i] = down
    return pd.Series(last_up, index=high.index), pd.Series(last_down, index=low.index)


def kaufman_adaptive_ma(
    close: pd.Series, period: int = 10, fast: int = 2, slow: int = 30
) -> pd.Series:
    """Kaufman AMA: ER scales the smoothing constant between fast and slow SC.

    Not the ER-only gate and not VIDYA (CMO alpha). Bars ``<= t`` only.
    """
    er = kaufman_efficiency(close, period)
    fast_sc = 2.0 / (float(fast) + 1.0)
    slow_sc = 2.0 / (float(slow) + 1.0)
    sc = (er * (fast_sc - slow_sc) + slow_sc) ** 2
    prices = close.astype("float64").to_numpy()
    gains = sc.to_numpy()
    out = np.full(len(prices), np.nan)
    prev = np.nan
    for i, (price, alpha) in enumerate(zip(prices, gains)):
        if alpha != alpha:
            continue
        prev = price if prev != prev else prev + alpha * (price - prev)
        out[i] = prev
    return pd.Series(out, index=close.index)


def dema(close: pd.Series, period: int = 10) -> pd.Series:
    """Double EMA: 2*EMA - EMA(EMA). Paired as DEMA vs DEMA, not ZLEMA vs EMA."""
    first = ema(close, period)
    return 2.0 * first - ema(first, period)


def tema(close: pd.Series, period: int = 10) -> pd.Series:
    """Triple EMA: 3*EMA - 3*EMA(EMA) + EMA^3. Not Tillson T3."""
    e1 = ema(close, period)
    e2 = ema(e1, period)
    e3 = ema(e2, period)
    return 3.0 * e1 - 3.0 * e2 + e3


def alma(
    close: pd.Series, period: int = 9, offset: float = 0.85, sigma: float = 6.0
) -> pd.Series:
    """Arnaud Legoux MA: Gaussian window with offset. Not SMA, EMA, Hull, or T3."""
    if period <= 0:
        raise ValueError(f"period must be positive, got {period}")
    if sigma <= 0:
        raise ValueError(f"sigma must be positive, got {sigma}")
    m = float(offset) * (period - 1)
    s = float(period) / float(sigma)
    idx = np.arange(period, dtype="float64")
    weights = np.exp(-((idx - m) ** 2) / (2.0 * s * s))
    weights = weights / weights.sum()

    def _dot(window: np.ndarray) -> float:
        return float(np.dot(window, weights))

    return close.astype("float64").rolling(period, min_periods=period).apply(_dot, raw=True)


def keltner_channel(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    ema_period: int = 20,
    atr_period: int = 10,
    atr_k: float = 1.5,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Keltner: EMA of typical price ± k*ATR. Not Bollinger stdev, not SuperTrend."""
    typical = (high.astype("float64") + low.astype("float64") + close.astype("float64")) / 3.0
    mid = ema(typical, ema_period)
    width = float(atr_k) * atr(high, low, close, atr_period)
    return mid, mid + width, mid - width


def stochastic_rsi(
    close: pd.Series, rsi_period: int = 14, stoch_period: int = 14
) -> pd.Series:
    """%K of Wilder RSI over N. Ranks RSI, not close."""
    ranked = rsi(close, rsi_period)
    lowest = ranked.rolling(stoch_period, min_periods=stoch_period).min()
    highest = ranked.rolling(stoch_period, min_periods=stoch_period).max()
    span = (highest - lowest).replace(0, np.nan)
    return 100.0 * (ranked - lowest) / span


def chandelier_direction(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    *,
    period: int = 22,
    atr_k: float = 3.0,
) -> tuple[pd.Series, pd.Series]:
    """Chandelier trail and side: ATR from HH/LL since the current side.

    Flip when close crosses the trail. Not SAR acceleration and not SuperTrend
    HL2 bands. Recursion uses bars ``<= t`` only.
    """
    atr_ = atr(high, low, close, period)
    hv = high.astype("float64").to_numpy()
    lv = low.astype("float64").to_numpy()
    cv = close.astype("float64").to_numpy()
    av = atr_.to_numpy()
    n = len(cv)
    trail = np.full(n, np.nan)
    direction = np.zeros(n, dtype=np.int64)
    side = 0
    extreme = np.nan
    for i in range(n):
        if av[i] != av[i]:
            continue
        if side == 0:
            if i < period:
                continue
            side = 1 if cv[i] >= cv[i - 1] else -1
            extreme = hv[i] if side > 0 else lv[i]
        if side > 0:
            extreme = hv[i] if extreme != extreme else max(extreme, hv[i])
            stop = extreme - float(atr_k) * av[i]
            if cv[i] < stop:
                side = -1
                extreme = lv[i]
                stop = extreme + float(atr_k) * av[i]
        else:
            extreme = lv[i] if extreme != extreme else min(extreme, lv[i])
            stop = extreme + float(atr_k) * av[i]
            if cv[i] > stop:
                side = 1
                extreme = hv[i]
                stop = extreme - float(atr_k) * av[i]
        trail[i] = stop
        direction[i] = side
    return pd.Series(trail, index=close.index), pd.Series(direction, index=close.index)


def mcginley_dynamic(close: pd.Series, period: int = 12) -> pd.Series:
    """McGinley Dynamic: MD += (C-MD) / (N * (C/MD)^4). Not EMA, not VIDYA."""
    if period <= 0:
        raise ValueError(f"period must be positive, got {period}")
    prices = close.astype("float64").to_numpy()
    out = np.full(len(prices), np.nan)
    prev = np.nan
    n = float(period)
    for i, price in enumerate(prices):
        if price != price:
            continue
        if prev != prev or prev == 0.0 or price == 0.0:
            prev = price
            out[i] = prev
            continue
        denom = n * ((price / prev) ** 4)
        if denom == 0.0:
            out[i] = prev
            continue
        prev = prev + (price - prev) / denom
        out[i] = prev
    return pd.Series(out, index=close.index)


def ehlers_super_smoother(close: pd.Series, period: int = 10) -> pd.Series:
    """Ehlers 2-pole Butterworth SuperSmoother of close. Not Laguerre FIR."""
    c = close.astype("float64").to_numpy()
    n = len(c)
    out = np.full(n, np.nan)
    length = max(int(period), 2)
    a1 = float(np.exp(-1.414 * np.pi / length))
    c2 = 2.0 * a1 * float(np.cos(1.414 * np.pi / length))
    c3 = -a1 * a1
    c1 = 1.0 - c2 - c3
    for i in range(n):
        if i == 0:
            out[i] = c[i]
        elif i == 1:
            out[i] = c1 * (c[i] + c[i - 1]) / 2.0 + c2 * out[i - 1]
        else:
            out[i] = c1 * (c[i] + c[i - 1]) / 2.0 + c2 * out[i - 1] + c3 * out[i - 2]
    return pd.Series(out, index=close.index)


def ehlers_roofing_filter(
    close: pd.Series, hp_period: int = 48, lp_period: int = 10
) -> pd.Series:
    """Roofing filter: 2-pole high-pass then SuperSmoother. Not a decycler."""
    c = close.astype("float64").to_numpy()
    n = len(c)
    hp = np.zeros(n)
    hp_len = max(int(hp_period), 2)
    angle = 0.707 * 2.0 * np.pi / hp_len
    alpha1 = (np.cos(angle) + np.sin(angle) - 1.0) / np.cos(angle)
    gain = (1.0 - alpha1 / 2.0) ** 2
    b = 2.0 * (1.0 - alpha1)
    d = (1.0 - alpha1) ** 2
    for i in range(n):
        if i < 2:
            hp[i] = 0.0
            continue
        hp[i] = gain * (c[i] - 2.0 * c[i - 1] + c[i - 2]) + b * hp[i - 1] - d * hp[i - 2]
    return ehlers_super_smoother(pd.Series(hp, index=close.index), lp_period)


def vwma(close: pd.Series, volume: pd.Series, period: int) -> pd.Series:
    """Volume-weighted moving average of close. Not an EMA of close."""
    if period <= 0:
        raise ValueError(f"period must be positive, got {period}")
    weighted = close.astype("float64") * volume.astype("float64")
    num = weighted.rolling(period, min_periods=period).sum()
    den = volume.astype("float64").rolling(period, min_periods=period).sum().replace(0, np.nan)
    return num / den


def volume_weighted_macd(
    close: pd.Series,
    volume: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> tuple[pd.Series, pd.Series]:
    """MACD of VWMA(close, volume), not EMA of close."""
    line = vwma(close, volume, fast) - vwma(close, volume, slow)
    return line, ema(line, signal)


def squeeze_on(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    *,
    bb_period: int = 20,
    bb_k: float = 2.0,
    kc_ema: int = 20,
    kc_atr: int = 10,
    kc_k: float = 1.5,
) -> pd.Series:
    """True when Bollinger is inside Keltner. Not BB-width alone."""
    _, bb_up, bb_dn = bollinger_bands(close, bb_period, bb_k)
    _, kc_up, kc_dn = keltner_channel(high, low, close, kc_ema, kc_atr, kc_k)
    return (bb_up < kc_up) & (bb_dn > kc_dn)


def squeeze_linreg_momentum(
    high: pd.Series, low: pd.Series, close: pd.Series, period: int = 20
) -> pd.Series:
    """TTM-style linreg of close minus typical-price mean. Bars ``<= t`` only."""
    typical = (high.astype("float64") + low.astype("float64") + close.astype("float64")) / 3.0
    basis = typical.rolling(period, min_periods=period).mean()
    src = close.astype("float64") - basis
    x = np.arange(period, dtype="float64")
    x_mean = float(x.mean())
    x_c = x - x_mean
    denom = float((x_c * x_c).sum()) or np.nan

    def _fit_end(window: np.ndarray) -> float:
        y_c = window - window.mean()
        slope = float((x_c * y_c).sum() / denom)
        intercept = float(window.mean() - slope * x_mean)
        return intercept + slope * (period - 1)

    return src.rolling(period, min_periods=period).apply(_fit_end, raw=True)

