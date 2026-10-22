"""Point-in-time L and the pinned tercile order.

L is the mean of usable daily buyRatio values. The raw tape is used as-is.
Nothing here applies the 0.35 + 0.30 restatement.

Tie-break, as Garwe clarified: a stable sort on the key (L ascending,
symbol ASCII ascending). The prereg builds that key by sorting symbols
first and then stable-sorting by L. Both steps are done. ``k = floor(n/3)``.
Long is the first k names (crowd most short). Short is the last k names
(crowd most long). Among names tied on L at the top boundary, the
alphabetically later symbol is the one that goes short.
"""

from __future__ import annotations

import pandas as pd

from research.xs_crowd_lsr_contrarian.calendar import as_utc
from research.xs_crowd_lsr_contrarian.pins import MIN_CLOSED_RATIOS, RATIO_WINDOW_DAYS


def usable_at(ts: pd.Timestamp, t: pd.Timestamp) -> bool:
    """A daily value is usable at t only if ts + 1d <= t and ts < t.

    Both halves are required. ``ts < t`` alone would admit a print whose
    period has not closed. ``ts + 1d <= t`` alone would admit a print
    stamped at t when the period length is zero.
    """
    stamp = as_utc(ts)
    as_of = as_utc(t)
    if not (stamp < as_of):
        return False
    return bool(stamp + pd.Timedelta(days=1) <= as_of)


def feature_bounds(t: pd.Timestamp) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Closed daily stamps that feed L: ts in [t-7d, t-1d]."""
    as_of = as_utc(t)
    return as_of - pd.Timedelta(days=RATIO_WINDOW_DAYS), as_of - pd.Timedelta(days=1)


def mean_buy_ratio(stamps: list[tuple[pd.Timestamp, float]], t: pd.Timestamp) -> float | None:
    """Mean of usable buyRatio in the 7-day window. None when fewer than 5.

    ``stamps`` is ``(ts, buy_ratio)`` for one symbol. Duplicate timestamps
    are a tape error, not an average. The value is not rescaled.
    """
    start, end = feature_bounds(t)
    seen: dict[pd.Timestamp, float] = {}
    for ts, value in stamps:
        stamp = as_utc(ts)
        if stamp < start or stamp > end:
            continue
        if not usable_at(stamp, t):
            continue
        if value is None or pd.isna(value):
            continue
        if stamp in seen:
            raise ValueError(f"duplicate buyRatio timestamp {stamp}")
        seen[stamp] = float(value)
    if len(seen) < MIN_CLOSED_RATIOS:
        return None
    total = 0.0
    for value in seen.values():
        total += value
    return total / len(seen)


def symbol_sort_key(symbol: str) -> bytes:
    """Byte-wise ASCII. A non-ASCII symbol is an error, not a locale sort."""
    try:
        return symbol.encode("ascii")
    except UnicodeEncodeError as exc:
        raise ValueError(f"symbol {symbol!r} is not ASCII") from exc


def assign_terciles(scored: list[tuple[str, float]]) -> tuple[list[str], list[str], int]:
    """Long the bottom tercile, short the top. Returns (long, short, k).

    Sort is stable. The key is (L ascending, symbol ASCII ascending).
    Input order does not change the legs. ``k = floor(n/3)``. The middle
    remainder is not traded, so the legs have equal count. ``k < 10`` is
    still returned; the book, not this function, skips that rebalance.
    """
    rows: list[tuple[bytes, str, float]] = []
    seen: set[str] = set()
    for symbol, level in scored:
        name = str(symbol)
        if name in seen:
            raise ValueError(f"duplicate symbol {name}")
        seen.add(name)
        rows.append((symbol_sort_key(name), name, float(level)))
    # Symbol order first, then a stable sort on the composite key. The
    # second key already includes the symbol bytes, which is what makes a
    # tie on L alphabetical. Stability keeps that order if two rows ever
    # share both L and the symbol bytes (they cannot: symbols are unique).
    rows.sort(key=lambda row: row[0])
    rows.sort(key=lambda row: (row[2], row[0]))
    n = len(rows)
    k = n // 3
    long = [row[1] for row in rows[:k]]
    short = [row[1] for row in rows[-k:]] if k else []
    return long, short, k


def leg_weights(long: list[str], short: list[str], leg: float) -> dict[str, float]:
    """Equal weight inside each leg. Long is positive, short is negative.

    ``leg`` is 0.59. A stopped name is not removed from this map: the cash
    rule is applied on the path, and the other names keep these weights.
    """
    if not long or not short:
        return {}
    if len(long) != len(short):
        raise ValueError(f"legs differ: {len(long)} long vs {len(short)} short")
    long_w = leg / len(long)
    short_w = -leg / len(short)
    weights: dict[str, float] = {}
    for symbol in long:
        weights[symbol] = long_w
    for symbol in short:
        if symbol in weights:
            raise ValueError(f"{symbol} is on both legs")
        weights[symbol] = short_w
    return weights
