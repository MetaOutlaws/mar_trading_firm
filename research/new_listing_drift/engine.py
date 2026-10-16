"""One listing spread, from bars. No scoring.

Short the new USDT perp and long an equal notional of BTCUSDT.

Entry is the next bar open after the first full 1h bar whose own open is
at or after launch and whose close (open + 1h) is at or after launch+24h.
The signal bar is the previous row. Its close time is at or before the
entry open, and the entry bar's close is not an input to the decision.

Exit is the first of:
- the bar open 336h after entry (the 14-day hold),
- the last positive-volume bar open strictly before delivery or delist,
- the next open after a 1h close on which the spread is at or below -12%.

The spread at a price is the short-leg return plus the long-BTC return.
That sum is the P&L per one-leg notional, which is the P&L per unit of
gross/2. The stop uses closes. The fill uses the next open, not the close
and not the -12% price.

A tape that ends before the hold and before any deadline is a truncation.
The exit is the last bar open after entry. The last bar's close is not
used, because a stop fill would need a next open that the tape does not
have.

Funding is the sum of prints strictly after entry and at or before the
exit. The short receives the listing rate and the long pays the BTC rate,
so the funding contribution is listing_sum - btc_sum. A hold long enough
to contain a settlement, with a missing print, is flagged. The missing
sum is None. It is not replaced with zero and it is not replaced with
CostModel's default rate.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from research.new_listing_drift.cells import (
    HOLD_HOURS,
    LAUNCH_DELAY_HOURS,
    RANDOM_EXCLUSION_DAYS,
    STOP_SPREAD,
)
from research.new_listing_drift.costs import measured_spread_cost, official_spread_cost

HOUR = pd.Timedelta(hours=1)
HOLD = pd.Timedelta(hours=HOLD_HOURS)
DELAY = pd.Timedelta(hours=LAUNCH_DELAY_HOURS)
RANDOM_EXCLUSION = pd.Timedelta(days=RANDOM_EXCLUSION_DAYS)


def _as_utc(value: Any) -> pd.Timestamp:
    stamp = pd.Timestamp(value)
    if stamp.tzinfo is None:
        return stamp.tz_localize("UTC")
    return stamp.tz_convert("UTC")


def _require_bars(bars: pd.DataFrame, what: str) -> pd.DataFrame:
    frame = bars.sort_index()
    if not isinstance(frame.index, pd.DatetimeIndex):
        raise ValueError(f"{what} index must be a DatetimeIndex of bar opens")
    if frame.index.tz is None:
        raise ValueError(f"{what} index must be UTC")
    if frame.index.has_duplicates:
        raise ValueError(f"{what} has duplicate opens")
    for column in ("open", "close"):
        if column not in frame.columns:
            raise ValueError(f"{what} is missing {column}")
    return frame


def spread_return(
    listing_px: float,
    btc_px: float,
    listing_entry: float,
    btc_entry: float,
) -> float:
    """Short listing return plus long BTC return, per one-leg notional."""
    short_ret = (listing_entry - listing_px) / listing_entry
    long_ret = (btc_px - btc_entry) / btc_entry
    return float(short_ret + long_ret)


def find_entry(listing: pd.DataFrame, launch: pd.Timestamp) -> tuple[pd.Timestamp | None, pd.Timestamp | None]:
    """Signal bar open and the next open that is at or after the signal close.

    Returns ``(signal_open, entry_open)``. Either can be None when the
    tape has no qualifying bar or no open after that bar has closed.
    Prices are not read. A later bar cannot move this result unless it
    is itself the first qualifying bar, which only happens when no
    earlier bar qualified.
    """
    idx = listing.index
    close_time = idx + HOUR
    qualified = (idx >= launch) & (close_time >= launch + DELAY)
    if not bool(qualified.any()):
        return None, None
    signal_open = idx[int(np.flatnonzero(np.asarray(qualified))[0])]
    signal_close = signal_open + HOUR
    # The fill must not be before the signal bar has closed.
    after = idx[idx >= signal_close]
    if len(after) == 0:
        return signal_open, None
    return signal_open, after[0]


def _tradable_mask(listing: pd.DataFrame) -> np.ndarray:
    """Delivery and delist exits skip the zero-volume settlement bar.

    A tape with no volume column has no settlement flag. Those bars stay
    eligible. A NaN volume is not treated as tradable.
    """
    if "volume" not in listing.columns:
        return np.ones(len(listing), dtype=bool)
    volume = listing["volume"].to_numpy(dtype="float64")
    return np.isfinite(volume) & (volume > 0.0)


def _last_open(index: pd.DatetimeIndex, mask: np.ndarray) -> pd.Timestamp | None:
    hits = np.flatnonzero(mask)
    if hits.size == 0:
        return None
    return index[int(hits[-1])]


def forced_exit(
    listing: pd.DataFrame,
    entry_time: pd.Timestamp,
    deadline: pd.Timestamp | None,
    deadline_kind: str | None,
) -> tuple[pd.Timestamp, str] | None:
    """The non-stop exit: 14d hold, delivery, delist, or data truncation.

    The earliest of those times wins. Delivery and delist apply only when
    the tape actually reaches the deadline. A tape that ends first is a
    truncation, including the 2026 cutoff.
    """
    idx = listing.index
    after_entry = np.asarray(idx > entry_time)
    if not after_entry.any():
        return None
    target = entry_time + HOLD
    candidates: list[tuple[pd.Timestamp, str]] = []

    exact = idx == target
    if bool(exact.any()):
        candidates.append((target, "hold_14d"))
    else:
        up_to_target = after_entry & np.asarray(idx <= target)
        truncated_at = _last_open(idx, up_to_target)
        if truncated_at is not None:
            candidates.append((truncated_at, "truncated"))

    if deadline is not None:
        covers_deadline = bool((idx >= deadline).any())
        if covers_deadline:
            tradable = _tradable_mask(listing)
            before_deadline = after_entry & np.asarray(idx < deadline) & tradable
            deadline_open = _last_open(idx, before_deadline)
            # The contract ends at the deadline. Holding on to the 14-day
            # bar past that clock time would trade a delisted name. If no
            # positive-volume bar sits strictly between entry and the
            # deadline, there is no exit to take.
            if deadline_open is None:
                return None
            kind = deadline_kind if deadline_kind in {"delivery", "delist"} else "delist"
            candidates.append((deadline_open, kind))

    if not candidates:
        return None
    # Earliest clock time. A tie keeps the first reason we appended, which
    # is the hold or the truncation; a deadline at that same open overrides
    # it because the contract is already gone.
    earliest = min(candidates, key=lambda item: item[0])
    same_time = [item for item in candidates if item[0] == earliest[0]]
    for preferred in ("delivery", "delist", "hold_14d", "truncated"):
        for item in same_time:
            if item[1] == preferred:
                return item
    return earliest


def _stop_fill(
    listing: pd.DataFrame,
    btc: pd.DataFrame,
    entry_time: pd.Timestamp,
    forced_time: pd.Timestamp,
    listing_entry: float,
    btc_entry: float,
) -> tuple[pd.Timestamp, pd.Timestamp] | None:
    """First 1h close at or below the stop, filled at the next open.

    The fill has to be at or before the forced exit. A close with no
    following open is not a stop: that is how a terminal bar stays a
    truncation instead of an invented fill. High and low are not read.
    """
    idx = listing.index
    btc_idx = btc.index
    for i in range(len(idx) - 1):
        open_i = idx[i]
        if open_i < entry_time:
            continue
        fill_time = idx[i + 1]
        if fill_time > forced_time:
            break
        if open_i not in btc_idx or fill_time not in btc_idx:
            # No BTC mark, so there is no spread close and no spread fill.
            continue
        listing_close = float(listing.iloc[i]["close"])
        btc_close = float(btc.at[open_i, "close"])
        if not np.isfinite(listing_close) or not np.isfinite(btc_close):
            continue
        if listing_close <= 0.0 or btc_close <= 0.0:
            continue
        marked = spread_return(listing_close, btc_close, listing_entry, btc_entry)
        if marked <= STOP_SPREAD:
            return fill_time, open_i
    return None


def funding_sum(
    rates: pd.Series | None,
    entry_time: pd.Timestamp,
    exit_time: pd.Timestamp,
    interval: pd.Timedelta,
) -> tuple[float | None, bool]:
    """Sum of funding rates in ``(entry, exit]``.

    Returns ``(sum, missing)``. ``missing`` is true when the hold is at
    least one settlement long and a print that should have fallen inside
    it is absent. The sum is then None. A short hold with no print is a
    real zero, not a fill, because no settlement was due.
    """
    if exit_time <= entry_time:
        return 0.0, False
    # No prints at all. A short hold did not owe a settlement. A long hold
    # is missing data, and the sum stays None rather than becoming zero.
    if rates is None or len(rates) == 0 or not isinstance(rates.index, pd.DatetimeIndex):
        if exit_time - entry_time < interval:
            return 0.0, False
        return None, True
    series = rates.sort_index()
    window = series.loc[(series.index > entry_time) & (series.index <= exit_time)]
    if exit_time - entry_time < interval and window.empty:
        return 0.0, False
    if window.empty:
        return None, True
    times = list(window.index)
    if times[0] - entry_time > interval:
        return None, True
    for left, right in zip(times, times[1:]):
        if right - left > interval:
            return None, True
    if exit_time - times[-1] > interval:
        return None, True
    return float(window.sum()), False


def _blank_trade(symbol: str, launch: pd.Timestamp, reason: str) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "launch": launch,
        "signal_open": pd.NaT,
        "entry_time": pd.NaT,
        "exit_time": pd.NaT,
        "exit_reason": "no_trade",
        "no_trade_reason": reason,
        "listing_entry": np.nan,
        "listing_exit": np.nan,
        "btc_entry": np.nan,
        "btc_exit": np.nan,
        "gross_r": np.nan,
        "funding_listing": np.nan,
        "funding_btc": np.nan,
        "funding_r": np.nan,
        "funding_missing": False,
        "funding_zero_filled": False,
        "cost_official": official_spread_cost(),
        "cost_measured": measured_spread_cost(),
        "net_official": np.nan,
        "net_measured": np.nan,
        "truncated": False,
        "stop_trigger_open": pd.NaT,
    }


def simulate_spread(
    listing: pd.DataFrame,
    btc: pd.DataFrame,
    *,
    symbol: str,
    launch: Any,
    listing_funding: pd.Series | None = None,
    btc_funding: pd.Series | None = None,
    listing_interval: pd.Timedelta = pd.Timedelta(hours=8),
    btc_interval: pd.Timedelta = pd.Timedelta(hours=8),
    deadline: Any = None,
    deadline_kind: str | None = None,
    entry_time: Any = None,
) -> dict[str, Any]:
    """Simulate one spread.

    ``entry_time`` set means a random-baseline entry: the launch+24h rule
    is skipped and the given open is the fill. Exit, stop, cost, and
    funding rules are the same ones the real trade uses.
    """
    launch_ts = _as_utc(launch)
    listing_bars = _require_bars(listing, symbol)
    btc_bars = _require_bars(btc, "BTCUSDT")
    deadline_ts = None if deadline is None or pd.isna(deadline) else _as_utc(deadline)

    if entry_time is None:
        signal_open, entry = find_entry(listing_bars, launch_ts)
        if entry is None:
            trade = _blank_trade(symbol, launch_ts, "no bar closes at or after launch+24h")
            trade["signal_open"] = signal_open if signal_open is not None else pd.NaT
            return trade
    else:
        signal_open = pd.NaT
        entry = _as_utc(entry_time)
        if entry not in listing_bars.index:
            return _blank_trade(symbol, launch_ts, "entry open is not a listing bar")

    if entry not in btc_bars.index:
        trade = _blank_trade(symbol, launch_ts, "BTCUSDT has no bar at the entry open")
        trade["signal_open"] = signal_open if signal_open is not None else pd.NaT
        trade["entry_time"] = entry
        return trade

    listing_entry = float(listing_bars.at[entry, "open"])
    btc_entry = float(btc_bars.at[entry, "open"])
    if listing_entry <= 0.0 or btc_entry <= 0.0 or not np.isfinite(listing_entry) or not np.isfinite(btc_entry):
        return _blank_trade(symbol, launch_ts, "entry open is not a positive price")

    forced = forced_exit(listing_bars, entry, deadline_ts, deadline_kind)
    if forced is None:
        trade = _blank_trade(symbol, launch_ts, "no exit bar after entry")
        trade["signal_open"] = signal_open if signal_open is not None else pd.NaT
        trade["entry_time"] = entry
        return trade
    exit_time, reason = forced

    stop = _stop_fill(
        listing_bars, btc_bars, entry, exit_time, listing_entry, btc_entry
    )
    trigger_open: pd.Timestamp | None = None
    if stop is not None:
        exit_time, trigger_open = stop
        reason = "stop"

    if exit_time not in btc_bars.index:
        trade = _blank_trade(symbol, launch_ts, "BTCUSDT has no bar at the exit open")
        trade["entry_time"] = entry
        return trade

    listing_exit = float(listing_bars.at[exit_time, "open"])
    btc_exit = float(btc_bars.at[exit_time, "open"])
    gross = spread_return(listing_exit, btc_exit, listing_entry, btc_entry)

    listing_sum, listing_missing = funding_sum(
        listing_funding, entry, exit_time, listing_interval
    )
    btc_sum, btc_missing = funding_sum(btc_funding, entry, exit_time, btc_interval)
    missing = listing_missing or btc_missing
    # A flagged leg stays None. Adding zero would be the fill this cell forbids.
    if missing:
        funding_r = None
        net_official = None
        net_measured = None
    else:
        assert listing_sum is not None and btc_sum is not None
        funding_r = float(listing_sum - btc_sum)
        cost_official = official_spread_cost()
        cost_measured = measured_spread_cost()
        net_official = float(gross + funding_r - cost_official)
        net_measured = float(gross + funding_r - cost_measured)

    return {
        "symbol": symbol,
        "launch": launch_ts,
        "signal_open": signal_open if signal_open is not None else pd.NaT,
        "entry_time": entry,
        "exit_time": exit_time,
        "exit_reason": reason,
        "no_trade_reason": "",
        "listing_entry": listing_entry,
        "listing_exit": listing_exit,
        "btc_entry": btc_entry,
        "btc_exit": btc_exit,
        "gross_r": gross,
        "funding_listing": np.nan if listing_sum is None else listing_sum,
        "funding_btc": np.nan if btc_sum is None else btc_sum,
        "funding_r": np.nan if funding_r is None else funding_r,
        "funding_missing": missing,
        "funding_zero_filled": False,
        "cost_official": official_spread_cost(),
        "cost_measured": measured_spread_cost(),
        "net_official": np.nan if net_official is None else net_official,
        "net_measured": np.nan if net_measured is None else net_measured,
        "truncated": reason == "truncated",
        "stop_trigger_open": trigger_open if trigger_open is not None else pd.NaT,
    }


def eligible_random_opens(
    listing: pd.DataFrame,
    btc: pd.DataFrame,
    *,
    launch: Any,
    window_start: Any,
    window_stop: Any,
    deadline: Any = None,
) -> pd.DatetimeIndex:
    """Bar opens the null may draw for this name.

    The open is inside the same window, at least 15 days after launch,
    strictly before delivery or delist, and present on both legs. The
    first 15 days are the listing window itself, so they are not a null
    for listing timing. An empty result means the name keeps its real
    entry and is not replaced by another name.
    """
    launch_ts = _as_utc(launch)
    start = _as_utc(window_start)
    stop = _as_utc(window_stop)
    deadline_ts = None if deadline is None or (isinstance(deadline, float) and np.isnan(deadline)) else (
        None if deadline is None or pd.isna(deadline) else _as_utc(deadline)
    )
    idx = listing.sort_index().index
    first_ok = launch_ts + RANDOM_EXCLUSION
    mask = (idx >= first_ok) & (idx >= start) & (idx < stop)
    if deadline_ts is not None:
        mask = mask & (idx < deadline_ts)
    # Need a later listing bar so the position can exit, and a BTC bar
    # at the entry open. The exit rules then match the real trade.
    opens = idx[np.asarray(mask)]
    btc_index = btc.sort_index().index
    listing_has_later = np.array([(idx > open_).any() for open_ in opens], dtype=bool)
    on_btc = np.array([open_ in btc_index for open_ in opens], dtype=bool)
    keep = listing_has_later & on_btc
    return pd.DatetimeIndex(opens[keep])
