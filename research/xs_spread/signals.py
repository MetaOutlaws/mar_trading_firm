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
    "market_cap": market_cap_scores,
}


def get_signal(name: str):
    try:
        return SIGNALS[name]
    except KeyError as exc:
        known = ", ".join(sorted(SIGNALS))
        raise KeyError(f"unknown signal {name!r}; known: {known}") from exc
