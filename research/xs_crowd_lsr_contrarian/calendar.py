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

# Addendum d0cc64c8. Holdout evidence is the 25 Mondays 2025-07-07 through
# 2025-12-22. The 2025-12-29 rebalance would be marked with bars after that
# Monday, so it is veto-only and is not a week of evidence. The data bound
# is the 2025-12-29 00:00 open, which closes the 2025-12-22 hold.
HOLDOUT_EVIDENCE_FIRST = pd.Timestamp("2025-07-07", tz="UTC")
HOLDOUT_EVIDENCE_LAST = pd.Timestamp("2025-12-22", tz="UTC")
HOLDOUT_VETO_ONLY = pd.Timestamp("2025-12-29", tz="UTC")
HOLDOUT_EVIDENCE_WEEKS = 25
MAIN_LAST_REBALANCE = pd.Timestamp("2025-06-30", tz="UTC")
MAIN_DATA_CAP = pd.Timestamp("2025-07-07", tz="UTC")


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


def _mondays_in_bounds(window: str) -> list[pd.Timestamp]:
    """Every Monday 00:00 UTC inside the frozen calendar bounds.

    This includes the holdout Monday that the addendum then takes out of
    the evidence book. ``rebalance_mondays`` is what the book trades.
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


def rebalance_mondays(window: str) -> list[pd.Timestamp]:
    """Monday 00:00 UTC rebalances that are evidence.

    2026 is not a window. Holdout evidence is 2025-07-07 through 2025-12-22
    (25 weeks). 2025-12-29 is not in this list.
    """
    times = _mondays_in_bounds(window)
    if window == "main":
        if times[-1] != MAIN_LAST_REBALANCE:
            raise WindowError(f"main last rebalance {times[-1]} is not {MAIN_LAST_REBALANCE}")
        return times
    if window != "holdout":
        raise WindowError(f"refusing window {window!r}")
    evidence = [stamp for stamp in times if stamp <= HOLDOUT_EVIDENCE_LAST]
    veto = [stamp for stamp in times if stamp > HOLDOUT_EVIDENCE_LAST]
    if (
        not evidence
        or evidence[0] != HOLDOUT_EVIDENCE_FIRST
        or evidence[-1] != HOLDOUT_EVIDENCE_LAST
        or len(evidence) != HOLDOUT_EVIDENCE_WEEKS
        or veto != [HOLDOUT_VETO_ONLY]
    ):
        raise WindowError(
            "holdout evidence is not the 25 Mondays 2025-07-07..2025-12-22 "
            f"(got {len(evidence)} weeks, veto {veto})"
        )
    return evidence


def veto_only_mondays(window: str) -> list[pd.Timestamp]:
    """Rebalances that may be reported and must not be scored.

    Holdout has one: 2025-12-29. Its hold would need bars after that open,
    and 2026 data is veto-only. The line cannot turn a FAIL into a PASS.
    Main has none. The 2025-06-30 hold still closes on 2025-07-07.
    """
    if window == "main":
        rebalance_mondays("main")
        return []
    if window != "holdout":
        raise WindowError(f"refusing window {window!r}")
    rebalance_mondays("holdout")
    return [HOLDOUT_VETO_ONLY]


def exit_cap(window: str) -> pd.Timestamp:
    """Last price or funding timestamp this window may load. Inclusive.

    Main's last evidence Monday is 2025-06-30, so the cap is the 2025-07-07
    00:00 open. Holdout's last evidence Monday is 2025-12-22, so the cap is
    the 2025-12-29 00:00 open. A bar opened after that instant is not read.
    """
    cap = rebalance_mondays(window)[-1] + pd.Timedelta(days=HOLD_DAYS)
    if window == "main" and cap != MAIN_DATA_CAP:
        raise WindowError(f"main data bound {cap} is not {MAIN_DATA_CAP}")
    if window == "holdout" and cap != HOLDOUT_VETO_ONLY:
        raise WindowError(f"holdout data bound {cap} is not {HOLDOUT_VETO_ONLY}")
    return cap


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
