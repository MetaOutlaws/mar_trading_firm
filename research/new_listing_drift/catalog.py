"""Frozen catalog v2: the event list, not a return.

The file is the attached events table (C union D union N). A pinned load
checks its sha256. HMSTRUSDT is the one missing main name against the
15 Oct snapshot and must not be added. Pre-cut rows (entry before
2023-10-15) stay in the file and are not part of main, holdout, or 2026.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from research.new_listing_drift import PACKAGE_DIR
from research.new_listing_drift.cells import (
    DAYS_PER_YEAR,
    EVENTS_V2_SHA256,
    EXCLUSIONS,
    SNAPSHOT_COVERAGE,
    WINDOW_ENDPOINT_DAYS,
    WINDOWS,
)
from research.new_listing_drift.hashing import sha256_file

DEFAULT_EVENTS_PATH = PACKAGE_DIR / "data" / "events_v2.csv"

REQUIRED_COLUMNS = ("symbol", "src", "typ", "launch", "entry", "exit", "lag_h")


class CatalogError(RuntimeError):
    """The event list is missing, altered, or imputes an excluded name."""


def window_bounds(window: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Half-open UTC interval ``[start, end of the stated end date)``.

    An entry at 2025-06-30 23:00 is main. An entry at 2025-07-01 00:00
    is holdout. The stated dates are inclusive.
    """
    try:
        start_s, end_s = WINDOWS[window]
    except KeyError as exc:
        known = ", ".join(sorted(WINDOWS))
        raise KeyError(f"unknown window {window!r}; known: {known}") from exc
    start = pd.Timestamp(start_s, tz="UTC")
    # The day after the stated end date, exclusive.
    stop = pd.Timestamp(end_s, tz="UTC") + pd.Timedelta(days=1)
    return start, stop


def in_window(timestamps: pd.Series, window: str) -> pd.Series:
    start, stop = window_bounds(window)
    stamps = pd.to_datetime(timestamps, utc=True)
    return (stamps >= start) & (stamps < stop)


def window_years(window: str) -> float:
    """Endpoint-day span divided by 365.25.

    Main is 624/365.25 years. That is the span behind the prereg's
    213.1 trades a year on 364 events (364 / (624/365.25) = 213.06).
    """
    days = WINDOW_ENDPOINT_DAYS[window]
    return days / DAYS_PER_YEAR


def iso_week_id(timestamps: pd.Series) -> pd.Series:
    """ISO year-week of an entry. One week is one cluster."""
    stamps = pd.to_datetime(timestamps, utc=True)
    iso = stamps.dt.isocalendar()
    return iso.year.astype(str) + "-W" + iso.week.astype(int).astype(str).str.zfill(2)


def load_events(path: Path | None = None, *, check_pin: bool = True) -> pd.DataFrame:
    """Load the catalog. ``check_pin`` is on for any run that is not a fixture.

    Raises if an excluded name has been written back in. The missing
    snapshot name is a disclosure, not a row to invent.
    """
    events_path = Path(path) if path is not None else DEFAULT_EVENTS_PATH
    if not events_path.is_file():
        raise CatalogError(f"events catalog is missing: {events_path}")
    digest = sha256_file(events_path)
    if check_pin and digest != EVENTS_V2_SHA256:
        raise CatalogError(
            f"events catalog hash {digest} != pinned {EVENTS_V2_SHA256}"
        )
    frame = pd.read_csv(events_path)
    missing = [name for name in REQUIRED_COLUMNS if name not in frame.columns]
    if missing:
        raise CatalogError(f"events catalog is missing columns {missing}")
    out = frame.loc[:, list(REQUIRED_COLUMNS)].copy()
    out["symbol"] = out["symbol"].astype(str)
    out["src"] = out["src"].astype(str)
    out["typ"] = out["typ"].fillna("").astype(str)
    for column in ("launch", "entry", "exit"):
        out[column] = pd.to_datetime(out[column], utc=True)
    out["lag_h"] = pd.to_numeric(out["lag_h"], errors="coerce")
    if out["symbol"].duplicated().any():
        raise CatalogError("events catalog has duplicate symbols")
    bad_src = sorted(set(out["src"]) - {"C", "D", "N"})
    if bad_src:
        raise CatalogError(f"events catalog has unknown tape sources {bad_src}")
    present = set(out["symbol"])
    imputed = [name for name in EXCLUSIONS if name in present]
    if imputed:
        raise CatalogError(
            "excluded names are in the catalog and would be imputed "
            f"back into the cell: {imputed}"
        )
    out["iso_week"] = iso_week_id(out["entry"])
    return out.reset_index(drop=True)


def events_for_window(events: pd.DataFrame, window: str) -> pd.DataFrame:
    """Rows whose catalog entry time falls in ``window``.

    The catalog entry is the frozen schedule (launch+24h, no stop).
    The engine recomputes the fill from the tape and flags a mismatch.
    """
    picked = events.loc[in_window(events["entry"], window)].copy()
    return picked.reset_index(drop=True)


def coverage_disclosure() -> dict[str, object]:
    """15 Oct snapshot coverage. Missing names are listed, not filled in."""
    return {
        "catalog": "v2",
        "sources": "C union D union N",
        "main_events_are_not_the_snapshot_count": True,
        "snapshot": SNAPSHOT_COVERAGE,
        "note": (
            "Main 191/192 and holdout 106/106 are coverage against the "
            "15 Oct USDT snapshot. HMSTRUSDT is missing and is not imputed. "
            "The scored event counts are the catalog rows in each window."
        ),
    }
