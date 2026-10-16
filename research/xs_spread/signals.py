"""Pluggable cross-sectional signals.

A signal returns one score per symbol at ``as_of``. Higher means more of
the feature. NaN means "not scored" and the name drops out of the terciles.
The engine, not the signal, applies the point-in-time listing and the
31-day history floor, then cuts terciles.

Bars passed in may include the future. Every signal has to ignore a bar
whose close is after ``as_of``. Close time is open time plus one hour.
The harness also slices before the call; the slice here is the backstop
the no-lookahead test exercises.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from research.xs_spread.cells import CellConfig


def bars_closed_by(bars: pd.DataFrame, as_of: pd.Timestamp) -> pd.DataFrame:
    """Bars whose close is at or before ``as_of``.

    A bar timestamp is the open. The bar covers ``[open, open+1h)`` and is
    usable only once ``open+1h <= as_of``.
    """
    if bars.empty:
        return bars
    close_time = bars.index + pd.Timedelta(hours=1)
    return bars.loc[close_time <= as_of]


def realized_skew(returns: np.ndarray) -> float:
    """Amaya realized skewness: ``sqrt(N) * sum(r^3) / (sum(r^2))^1.5``.

    Raw third moment, not the mean-centered sample skewness. Equal non-zero
    returns give +1 when they are positive and -1 when they are negative.
    """
    r = np.asarray(returns, dtype="float64")
    r = r[np.isfinite(r)]
    n = int(r.size)
    if n == 0:
        return float("nan")
    sum_sq = float(np.sum(r * r))
    denom = sum_sq ** 1.5
    if not np.isfinite(denom) or denom == 0.0:
        return float("nan")
    return float(np.sqrt(n) * np.sum(r ** 3) / denom)


def _hourly_log_returns(close: np.ndarray, open_time: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Log returns on bars that are exactly one hour apart, aligned to the later bar."""
    if close.size < 2:
        return np.empty(0, dtype="int64"), np.empty(0, dtype="float64")
    step = open_time[1:] - open_time[:-1]
    one_hour = np.timedelta64(1, "h")
    consecutive = step == one_hour
    prev = close[:-1]
    cur = close[1:]
    good = consecutive & np.isfinite(prev) & np.isfinite(cur) & (prev > 0) & (cur > 0)
    indices = np.flatnonzero(good) + 1  # index of the later bar
    values = np.log(cur[good] / prev[good])
    return indices.astype("int64"), values


def realized_skew_at(
    bars: pd.DataFrame,
    as_of: pd.Timestamp,
    *,
    lookback_bars: int,
    min_bars: int,
) -> float:
    """RSK at ``as_of`` from hourly log returns ending at the last closed bar.

    The window is the ``lookback_bars`` hourly slots ending at the bar whose
    close is ``<= as_of``. A return counts only when both closes exist and
    the two opens are exactly one hour apart. Fewer than ``min_bars`` valid
    returns is NaN.
    """
    usable = bars_closed_by(bars, as_of)
    if len(usable) < 2:
        return float("nan")
    open_time = usable.index.to_numpy(dtype="datetime64[ns]")
    close = usable["close"].to_numpy(dtype="float64")
    later_idx, rets = _hourly_log_returns(close, open_time)
    if later_idx.size == 0:
        return float("nan")
    last_open = open_time[-1]
    window_start = last_open - np.timedelta64(lookback_bars - 1, "h")
    in_window = (open_time[later_idx] >= window_start) & (open_time[later_idx] <= last_open)
    chosen = rets[in_window]
    if int(chosen.size) < min_bars:
        return float("nan")
    return realized_skew(chosen)


def realized_skew_scores(
    bars_by_symbol: dict[str, pd.DataFrame],
    as_of: pd.Timestamp,
    config: CellConfig,
) -> pd.Series:
    """One RSK per symbol. NaN when the lookback is too thin."""
    scores: dict[str, float] = {}
    for symbol, bars in bars_by_symbol.items():
        scores[symbol] = realized_skew_at(
            bars,
            as_of,
            lookback_bars=config.lookback_bars,
            min_bars=config.min_bars,
        )
    return pd.Series(scores, dtype="float64", name="score")


def daily_sample_prices(bars: pd.DataFrame) -> pd.Series:
    """Price at each 00:00 UTC: the close of the bar that opened at 23:00.

    The stamp is the bar's close time, so a Monday 00:00 rebalance can see
    Sunday 23:00's close and cannot see the Monday 00:00 bar's own close.
    """
    if bars.empty:
        return pd.Series(dtype="float64")
    chosen = bars.loc[bars.index.hour == 23, "close"]
    if chosen.empty:
        return pd.Series(dtype="float64")
    stamped = pd.to_numeric(chosen, errors="coerce")
    stamped.index = chosen.index + pd.Timedelta(hours=1)
    stamped = stamped[~stamped.index.duplicated(keep="last")].sort_index()
    stamped.name = "price"
    return stamped


def daily_log_returns(prices: pd.Series) -> pd.Series:
    """Log returns on a calendar daily index. A missing day stays missing."""
    if prices.empty:
        return pd.Series(dtype="float64")
    full = pd.date_range(prices.index.min(), prices.index.max(), freq="D", tz="UTC")
    px = prices.reindex(full).astype("float64")
    prev = px.shift(1)
    out = np.log(px / prev)
    out[(px <= 0) | (prev <= 0) | ~np.isfinite(px) | ~np.isfinite(prev)] = np.nan
    out.name = "log_return"
    return out


def ols_slope(y: np.ndarray, x: np.ndarray) -> float:
    """OLS slope of ``y`` on ``x`` with an intercept. ``x`` is BTC."""
    y = np.asarray(y, dtype="float64")
    x = np.asarray(x, dtype="float64")
    if y.size < 2 or x.size != y.size:
        return float("nan")
    x_mean = float(np.mean(x))
    y_mean = float(np.mean(y))
    var = float(np.mean((x - x_mean) ** 2))
    if not np.isfinite(var) or var == 0.0:
        return float("nan")
    cov = float(np.mean((y - y_mean) * (x - x_mean)))
    return cov / var


def btc_beta_at(
    bars: pd.DataFrame,
    btc_bars: pd.DataFrame,
    as_of: pd.Timestamp,
    *,
    lookback_days: int,
    min_pairs: int,
) -> float:
    """Beta of one perp on BTC at ``as_of``.

    The window is ``lookback_days`` calendar daily log returns ending at
    ``as_of``. Both the coin and BTC need a 00:00 sample exactly at
    ``as_of``. Fewer than ``min_pairs`` finite pairs is NaN.
    """
    coin_px = daily_sample_prices(bars_closed_by(bars, as_of))
    btc_px = daily_sample_prices(bars_closed_by(btc_bars, as_of))
    if as_of not in coin_px.index or as_of not in btc_px.index:
        return float("nan")
    coin_r = daily_log_returns(coin_px)
    btc_r = daily_log_returns(btc_px)
    window = pd.date_range(as_of - pd.Timedelta(days=lookback_days - 1), as_of, freq="D", tz="UTC")
    y = coin_r.reindex(window)
    x = btc_r.reindex(window)
    mask = y.notna() & x.notna()
    if int(mask.sum()) < min_pairs:
        return float("nan")
    return ols_slope(y[mask].to_numpy(dtype="float64"), x[mask].to_numpy(dtype="float64"))


def btc_beta_scores(
    bars_by_symbol: dict[str, pd.DataFrame],
    as_of: pd.Timestamp,
    config: CellConfig,
) -> pd.Series:
    """One BTC beta per alt. BTCUSDT itself is not a score."""
    btc = bars_by_symbol.get("BTCUSDT")
    if btc is None:
        return pd.Series(dtype="float64", name="score")
    scores: dict[str, float] = {}
    for symbol, bars in bars_by_symbol.items():
        if symbol == "BTCUSDT" or symbol in config.exclude_symbols:
            continue
        scores[symbol] = btc_beta_at(
            bars,
            btc,
            as_of,
            lookback_days=config.beta_lookback_days,
            min_pairs=config.beta_min_pairs,
        )
    return pd.Series(scores, dtype="float64", name="score")


def market_cap_scores(
    bars_by_symbol: dict[str, pd.DataFrame],
    as_of: pd.Timestamp,
    config: CellConfig,
) -> pd.Series:
    """Stub for ``size_factor_weekly_cap``. There is no cap tape. Do not run."""
    raise NotImplementedError(
        "size_factor_weekly_cap is a stub. No point-in-time cap tape is "
        "wired, and this cell must not be run or scored."
    )


SIGNALS = {
    "realized_skew": realized_skew_scores,
    "btc_beta": btc_beta_scores,
    "market_cap": market_cap_scores,
}


def get_signal(name: str):
    try:
        return SIGNALS[name]
    except KeyError as exc:
        known = ", ".join(sorted(SIGNALS))
        raise KeyError(f"unknown signal {name!r}; known: {known}") from exc
