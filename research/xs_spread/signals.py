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

    The stamp is the bar's close time. A Monday 00:00 rebalance can see the
    Sunday 23:00 close and cannot see the Monday 00:00 bar, whose close is
    an hour later.
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
    """Log returns between 00:00 UTC samples exactly one day apart.

    A missing day stays missing. It is not filled and it does not bridge
    the gap with a multi-day return.
    """
    if prices.empty:
        return pd.Series(dtype="float64")
    full = pd.date_range(prices.index.min(), prices.index.max(), freq="D", tz="UTC")
    px = prices.reindex(full).astype("float64")
    prev = px.shift(1)
    with np.errstate(divide="ignore", invalid="ignore"):
        out = np.log(px / prev)
    invalid = (px <= 0) | (prev <= 0) | ~np.isfinite(px) | ~np.isfinite(prev)
    out = out.mask(invalid)
    out.name = "log_return"
    return out


# Tversky-Kahneman 1992 parameters, as frozen in the prestated file.
TK_ALPHA = 0.88
TK_LAMBDA = 2.25
TK_GAMMA_GAIN = 0.61
TK_GAMMA_LOSS = 0.69


def decision_weight(probability: float, gamma: float) -> float:
    """TK probability weight ``w(p) = p^γ / (p^γ + (1-p)^γ)^(1/γ)``.

    ``w(0)`` is 0 and ``w(1)`` is 1. Those two ends are the tails of the
    cumulative decision weights below.
    """
    p = float(probability)
    if p <= 0.0:
        return 0.0
    if p >= 1.0:
        return 1.0
    g = float(gamma)
    p_term = p ** g
    complement = (1.0 - p) ** g
    return float(p_term / (p_term + complement) ** (1.0 / g))


def tk_value(returns: np.ndarray) -> float:
    """Prospect value of a sample, one observation, probability ``1/n``.

    Barberis-Mukherjee-Wang / Tversky-Kahneman cumulative weights. Sort the
    finite returns from worst to best. Losses (``x < 0``) take ``w-`` with
    ``γ = 0.69``, accumulated from the worst outcome. Non-negative returns
    take ``w+`` with ``γ = 0.61``, accumulated from the best outcome. A zero
    sits with the gains and has value 0, so it only changes the ranks.

    Value is ``x^0.88`` for a gain and ``-2.25 * (-x)^0.88`` for a loss.
    The decision weight on the worst loss is ``w-(1/n)``. The decision
    weight on the best gain is ``w+(1/n)``. Interior outcomes take the
    difference of the cumulative weights. ``n`` is the number of finite
    returns in this call, not a padded 60.
    """
    sample = np.asarray(returns, dtype="float64")
    sample = sample[np.isfinite(sample)]
    n = int(sample.size)
    if n == 0:
        return float("nan")
    ordered = np.sort(sample)
    losses = ordered[ordered < 0.0]
    gains = ordered[ordered >= 0.0]
    total = 0.0
    n_losses = int(losses.size)
    for i in range(n_losses):
        # i = 0 is the worst loss. Its cumulative probability is 1/n.
        weight = decision_weight((i + 1) / n, TK_GAMMA_LOSS) - decision_weight(i / n, TK_GAMMA_LOSS)
        magnitude = float((-losses[i]) ** TK_ALPHA)
        total += -TK_LAMBDA * magnitude * weight
    n_gains = int(gains.size)
    for j in range(n_gains):
        # Rank 1 is the best gain. The smallest gain has rank n_gains.
        rank_from_best = n_gains - j
        weight = decision_weight(rank_from_best / n, TK_GAMMA_GAIN) - decision_weight(
            (rank_from_best - 1) / n, TK_GAMMA_GAIN
        )
        magnitude = float(gains[j] ** TK_ALPHA)
        total += magnitude * weight
    return float(total)


def prospect_at(
    bars: pd.DataFrame,
    as_of: pd.Timestamp,
    *,
    lookback_days: int,
    min_returns: int,
) -> tuple[float, float]:
    """TK value and the sum of the same daily log returns.

    The window is ``lookback_days`` calendar daily log returns ending at
    ``as_of``. The last return uses the bar that opened at 23:00 the day
    before, whose close is ``as_of`` when ``as_of`` is Monday 00:00 UTC.
    Fewer than ``min_returns`` finite days is ``(nan, nan)``. Bars whose
    close is after ``as_of`` are ignored.
    """
    as_of = pd.Timestamp(as_of)
    if as_of.tzinfo is None:
        as_of = as_of.tz_localize("UTC")
    else:
        as_of = as_of.tz_convert("UTC")
    usable = bars_closed_by(bars, as_of)
    prices = daily_sample_prices(usable)
    if as_of not in prices.index:
        return float("nan"), float("nan")
    returns = daily_log_returns(prices)
    window = pd.date_range(as_of - pd.Timedelta(days=lookback_days - 1), as_of, freq="D", tz="UTC")
    chosen = returns.reindex(window).to_numpy(dtype="float64")
    valid = chosen[np.isfinite(chosen)]
    if int(valid.size) < int(min_returns):
        return float("nan"), float("nan")
    return tk_value(valid), float(np.sum(valid))


def prospect_value_scores(
    bars_by_symbol: dict[str, pd.DataFrame],
    as_of: pd.Timestamp,
    config: CellConfig,
) -> pd.Series:
    """One TK value per symbol. NaN when the 60-day window has fewer than 50 returns.

    ``ret60`` is the sum of those same returns. The book stores it beside
    the score; this series is the rank key only.
    """
    scores: dict[str, float] = {}
    for symbol, bars in bars_by_symbol.items():
        tk, _ret60 = prospect_at(
            bars,
            as_of,
            lookback_days=config.lookback_days,
            min_returns=config.min_daily_returns,
        )
        scores[symbol] = tk
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
    "prospect_value": prospect_value_scores,
    "market_cap": market_cap_scores,
}


def get_signal(name: str):
    try:
        return SIGNALS[name]
    except KeyError as exc:
        known = ", ".join(sorted(SIGNALS))
        raise KeyError(f"unknown signal {name!r}; known: {known}") from exc
