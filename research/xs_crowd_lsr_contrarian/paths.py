"""Next-open fill, 12% stop on 1h closes, and realized funding.

Stop: 12% adverse from the entry fill (long at or below -12%, short at or
above +12%), checked on 1h closes only. A wick through the stop whose
close is still on the safe side does not exit. The exit fill is the next
1h open, not the stop price and not an intrabar print.

Delist: if the tape ends before the scheduled Monday open, the exit is the
last available 1h close and the cost is still charged.

Funding: every observed print with timestamp in (entry, exit] is summed.
That window is the hours held. A print at the entry open belongs to the
previous interval and is excluded. A print at the exit is included. Names
with no funding rows book 0. Missing 8h boundaries are counted and are not
replaced with another name's rate. There is no leg-mean fill.

A selected name with no Monday 00:00 open, or with no finite price over
the hold, returns None. The book turns that into BLOCKED. It does not
drop the name.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from research.xs_crowd_lsr_contrarian.calendar import as_utc
from research.xs_crowd_lsr_contrarian.pins import STOP_PCT

FUNDING_STEP = pd.Timedelta(hours=8)


class BlockedRun(RuntimeError):
    """A held name has no 1h price. The run stops. Nothing is dropped."""

    def __init__(self, symbol: str, rebalance: pd.Timestamp, reason: str) -> None:
        self.symbol = symbol
        self.rebalance = rebalance
        self.reason = reason
        super().__init__(
            f"BLOCKED {symbol} at {rebalance}: {reason}. "
            "A held name with no 1h price is not dropped."
        )


@dataclass(frozen=True)
class SidePath:
    """One side's path from the Monday 00:00 open to its exit fill."""

    reason: str  # hold, stop, delist
    exit_time: pd.Timestamp
    exit_price: float
    underlying_return: float
    price_ratio: float
    funding_sum: float
    funding_gaps: int
    funding_missing_name: bool
    off_grid_prints: int

    @property
    def stopped(self) -> bool:
        """True when the name is cash at the next rebalance."""
        return self.reason in {"stop", "delist"}


def settlement_times(entry: pd.Timestamp, exit_time: pd.Timestamp) -> pd.DatetimeIndex:
    """8h UTC boundaries strictly after entry and at or before exit."""
    entry = as_utc(entry)
    exit_time = as_utc(exit_time)
    if exit_time <= entry:
        return pd.DatetimeIndex([], tz="UTC")
    step = int(FUNDING_STEP.value)
    first = (int(entry.value) // step + 1) * step
    last = int(exit_time.value)
    if first > last:
        return pd.DatetimeIndex([], tz="UTC")
    stamps = np.arange(first, last + 1, step, dtype="int64")
    return pd.to_datetime(stamps, utc=True)


def _rates_utc(rates: pd.Series) -> pd.Series:
    index = rates.index
    if getattr(index, "tz", None) is None:
        index = index.tz_localize("UTC")
    else:
        index = index.tz_convert("UTC")
    out = pd.Series(np.asarray(rates.to_numpy(dtype="float64")), index=index)
    return out[~out.index.duplicated(keep="last")].sort_index()


def funding_over_hold(
    rates: pd.Series | None,
    entry: pd.Timestamp,
    exit_time: pd.Timestamp,
) -> tuple[float, int, bool, int]:
    """Realized funding sum, 8h gap count, no-data flag, off-grid print count.

    Every finite print in ``(entry, exit]`` is summed, including a 4h print
    that does not sit on the 8h grid. The gap count is how many 8h UTC
    boundaries in that window have no finite print. A symbol with no rows
    books 0, is flagged, and every expected 8h boundary counts as a gap.
    An observed rate of zero is a real print.
    """
    expected = settlement_times(entry, exit_time)
    entry = as_utc(entry)
    exit_time = as_utc(exit_time)
    if rates is None or len(rates) == 0:
        return 0.0, int(len(expected)), True, 0
    aligned = _rates_utc(rates)
    window = aligned[(aligned.index > entry) & (aligned.index <= exit_time)]
    finite = window.to_numpy(dtype="float64")
    finite = finite[np.isfinite(finite)]
    total = float(finite.sum()) if finite.size else 0.0
    if len(expected) == 0:
        gaps = 0
    else:
        on_grid = aligned.reindex(expected)
        present = np.isfinite(on_grid.to_numpy(dtype="float64"))
        gaps = int(len(expected) - int(present.sum()))
    if window.empty:
        off_grid = 0
    else:
        grid = set(expected)
        off_grid = int(sum(1 for stamp in window.index if stamp not in grid))
    return total, gaps, False, off_grid


def _finish(
    reason: str,
    exit_time: pd.Timestamp,
    exit_price: float,
    entry_price: float,
    rates: pd.Series | None,
    entry: pd.Timestamp,
) -> SidePath | None:
    if not np.isfinite(exit_price) or exit_price <= 0 or entry_price <= 0:
        return None
    ratio = float(exit_price) / float(entry_price)
    funding_sum, gaps, missing, off_grid = funding_over_hold(rates, entry, exit_time)
    return SidePath(
        reason=reason,
        exit_time=as_utc(exit_time),
        exit_price=float(exit_price),
        underlying_return=ratio - 1.0,
        price_ratio=ratio,
        funding_sum=funding_sum,
        funding_gaps=gaps,
        funding_missing_name=missing,
        off_grid_prints=off_grid,
    )


def path_for_side(
    bars: pd.DataFrame | None,
    t: pd.Timestamp,
    t_next: pd.Timestamp,
    side: str,
    rates: pd.Series | None,
    stop_pct: float = STOP_PCT,
) -> SidePath | None:
    """Path for one side. None means the mandated fill does not exist.

    The entry is the open of the 1h bar that starts at ``t``. The hold
    scans closes of bars whose open is in ``[t, t_next)``. The scheduled
    exit, if no stop fired, is the open of the bar at ``t_next``.
    """
    if side not in {"long", "short"}:
        raise ValueError(f"side must be long or short, got {side!r}")
    if bars is None or bars.empty:
        return None
    t = as_utc(t)
    t_next = as_utc(t_next)
    index = bars.index
    if t not in index:
        return None
    entry_price = float(bars.at[t, "open"])
    if not np.isfinite(entry_price) or entry_price <= 0:
        return None
    start = int(index.get_loc(t))
    if isinstance(start, slice):
        return None
    end_loc = int(index.searchsorted(t_next, side="left"))
    stop_level = entry_price * (1.0 - stop_pct) if side == "long" else entry_price * (1.0 + stop_pct)
    closes = bars["close"].to_numpy(dtype="float64")
    opens = bars["open"].to_numpy(dtype="float64")
    for i in range(start, end_loc):
        close = closes[i]
        if not np.isfinite(close):
            continue
        breached = close <= stop_level if side == "long" else close >= stop_level
        if not breached:
            continue
        # Next 1h open. The bar at t_next is a valid fill. A later bar is not.
        if i + 1 < len(index) and index[i + 1] <= t_next:
            nxt = i + 1
            # If the immediate next hour is missing, use the next bar that
            # is still at or before the scheduled exit. The fill is that open.
            return _finish("stop", index[nxt], float(opens[nxt]), entry_price, rates, t)
        return _finish("delist", index[i], close, entry_price, rates, t)
    if end_loc < len(index) and index[end_loc] == t_next:
        return _finish("hold", t_next, float(opens[end_loc]), entry_price, rates, t)
    if end_loc <= start:
        return None
    last = end_loc - 1
    last_close = float(closes[last])
    return _finish("delist", index[last], last_close, entry_price, rates, t)


def require_paths(
    symbol: str,
    t: pd.Timestamp,
    bars: pd.DataFrame | None,
    t_next: pd.Timestamp,
    rates: pd.Series | None,
) -> tuple[SidePath, SidePath]:
    """Both sides, or BLOCKED. A silent drop is not allowed."""
    long = path_for_side(bars, t, t_next, "long", rates)
    short = path_for_side(bars, t, t_next, "short", rates)
    if long is None or short is None:
        raise BlockedRun(
            symbol,
            t,
            "no 1h price over the hold (missing Monday 00:00 open or no finite exit)",
        )
    return long, short
