"""Monday rebalances, the v2 exclusion, and the window caps.

A dropped Monday opens no position, is not an ISO week, and contributes
no output row. The book that was opened the Monday before still exits at
its normal 7-day open, so exposure does not cross the gap.
"""

from __future__ import annotations

import pandas as pd

from research.xs_crowd_lsr_contrarian.pins import DROPPED_MONDAYS, HOLD_DAYS, YEAR_2026

# Inclusive calendar bounds. The first rebalance is the Monday on or after
# the start; the last is the Monday on or before the end.
WINDOWS: dict[str, tuple[str, str]] = {
    "main": ("2023-10-15", "2025-06-30"),
    "holdout": ("2025-07-01", "2025-12-31"),
}

# Feature window touches 2025-05-01..2025-06-01 inclusive when both hold.
RESTATEMENT_START = pd.Timestamp("2025-05-01", tz="UTC")
RESTATEMENT_END = pd.Timestamp("2025-06-01", tz="UTC")
YEAR_2026_TS = pd.Timestamp(YEAR_2026)


class WindowError(RuntimeError):
    """The requested window is not runnable."""


def as_utc(value: object) -> pd.Timestamp:
    stamp = pd.Timestamp(value)
    if stamp.tzinfo is None:
        return stamp.tz_localize("UTC")
    return stamp.tz_convert("UTC")


def feature_window_touches_restatement(t: pd.Timestamp) -> bool:
    """Prereg predicate: drop t iff t-7d <= 2025-06-01 and t-1d >= 2025-05-01."""
    stamp = as_utc(t)
    start = stamp - pd.Timedelta(days=7)
    end = stamp - pd.Timedelta(days=1)
    return bool(start <= RESTATEMENT_END and end >= RESTATEMENT_START)


def is_dropped_monday(t: pd.Timestamp) -> bool:
    """V2 exclusion. The predicate is the rule; the five dates are the check."""
    return feature_window_touches_restatement(t)


def rebalance_mondays(window: str) -> list[pd.Timestamp]:
    """Monday 00:00 UTC dates inside the frozen window, inclusive.

    2026 is not a window. A Monday at or after 2026-01-01 is refused even
    if a caller extends the bounds.
    """
    try:
        start_s, end_s = WINDOWS[window]
    except KeyError as exc:
        raise WindowError(
            f"refusing window {window!r}. Runnable windows are main and holdout. "
            "2026 is not touched."
        ) from exc
    start = as_utc(start_s)
    end = as_utc(end_s)
    if start >= YEAR_2026_TS or end >= YEAR_2026_TS:
        raise WindowError("refusing a window that reaches 2026")
    day = start
    while day.weekday() != 0:
        day += pd.Timedelta(days=1)
    times: list[pd.Timestamp] = []
    while day <= end:
        if day >= YEAR_2026_TS:
            raise WindowError(f"rebalance {day} is in 2026")
        times.append(day)
        day += pd.Timedelta(days=7)
    if not times:
        raise WindowError(f"{window} contains no Monday")
    return times


def exit_cap(window: str) -> pd.Timestamp:
    """Open time of the bar that closes the last in-window hold.

    Main's last Monday is 2025-06-30, so the cap is 2025-07-07 and no 2026
    bar is read. Holdout's last Monday is 2025-12-29, so the cap is
    2026-01-05 00:00 UTC. That single exit, and the hours of that hold, are
    the only timestamps at or after 2026-01-01 the loader may return, and
    only when the holdout has been unlocked.
    """
    last = rebalance_mondays(window)[-1]
    return last + pd.Timedelta(days=HOLD_DAYS)


def assert_dropped_monday_list(window: str = "main") -> list[str]:
    """The predicate on this window's Mondays must equal the frozen list.

    Main must drop exactly the five named Mondays. Holdout must drop none.
    A divergence refuses the run before any price is read.
    """
    found = [t.strftime("%Y-%m-%d") for t in rebalance_mondays(window) if is_dropped_monday(t)]
    if window == "main":
        expected = list(DROPPED_MONDAYS)
    elif window == "holdout":
        expected = []
    else:
        raise WindowError(f"refusing window {window!r}")
    if found != expected:
        raise RuntimeError(
            f"{window} dropped Mondays {found} != frozen {expected}. "
            "The v2 exclusion predicate and the named dates disagree."
        )
    return found


def calendar_years(window: str) -> float:
    """Annualisation denominator. The dropped weeks stay in the span.

    ``(end - start).days / 365.25``. The end date is not an extra day.
    The v2 rules say this denominator does not change when Mondays are dropped.
    """
    start_s, end_s = WINDOWS[window]
    days = (pd.Timestamp(end_s) - pd.Timestamp(start_s)).days
    return float(days) / 365.25


def continuous(prev: pd.Timestamp | None, t: pd.Timestamp) -> bool:
    """True when ``t`` is the 7-day exit of a book opened at ``prev``.

    A dropped or thin Monday in between breaks the chain. The next kept
    Monday is a fresh entry.
    """
    if prev is None:
        return False
    return bool(as_utc(t) - as_utc(prev) == pd.Timedelta(days=HOLD_DAYS))
