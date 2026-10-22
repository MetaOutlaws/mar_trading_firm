"""Load the verified monthly archive into arrays. Refuses a 2026 timestamp."""
from __future__ import annotations

import gzip
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from protocol_constants import (
    MIN_QTY,
    QTY_STEP,
    SERIES_BEGIN_MS,
    SERIES_END_EXCLUSIVE_MS,
    SYMBOLS,
)

MINUTE = 60_000


def _months():
    year, month = 2022, 1
    while (year, month) <= (2025, 12):
        yield f"{year:04d}-{month:02d}"
        month += 1
        if month == 13:
            year, month = year + 1, 1


def _read_prices(path: Path):
    stamps = []
    opens = []
    closes = []
    with gzip.open(path, "rt") as handle:
        header = handle.readline()
        if not header.startswith("timestamp_ms"):
            raise ValueError(f"unexpected header in {path}")
        for line in handle:
            parts = line.split(",")
            stamps.append(int(parts[0]))
            opens.append(float(parts[1]))
            closes.append(float(parts[4]))
    return stamps, opens, closes


def _read_funding(path: Path):
    stamps = []
    rates = []
    with gzip.open(path, "rt") as handle:
        header = handle.readline()
        if not header.startswith("timestamp_ms"):
            raise ValueError(f"unexpected funding header in {path}")
        for line in handle:
            stamp, rate = line.split(",")
            stamps.append(int(stamp))
            rates.append(float(rate))
    return stamps, rates


def load(root: Path):
    """Return books-ready arrays keyed by symbol, plus the shared clock."""
    root = Path(root)
    clock = None
    out = {}
    for symbol in SYMBOLS:
        spot_s, spot_o, spot_c = [], [], []
        perp_s, perp_o, perp_c = [], [], []
        mark_s, mark_o, mark_c = [], [], []
        for label in _months():
            s, o, c = _read_prices(root / "spot" / symbol / f"{label}.csv.gz")
            spot_s += s
            spot_o += o
            spot_c += c
            s, o, c = _read_prices(root / "perpetual" / symbol / f"{label}.csv.gz")
            perp_s += s
            perp_o += o
            perp_c += c
            s, o, c = _read_prices(root / "mark" / symbol / f"{label}.csv.gz")
            mark_s += s
            mark_o += o
            mark_c += c
        fund_s, fund_r = [], []
        for label in _months():
            s, r = _read_funding(root / "funding" / symbol / f"{label}.csv.gz")
            fund_s += s
            fund_r += r
        spot_s = np.asarray(spot_s, dtype=np.int64)
        if clock is None:
            clock = spot_s
        elif len(spot_s) != len(clock) or np.any(spot_s != clock):
            raise ValueError(f"{symbol} spot clock does not match BTC")
        for name, stamps in (("perpetual", perp_s), ("mark", mark_s)):
            stamps = np.asarray(stamps, dtype=np.int64)
            if len(stamps) != len(clock) or np.any(stamps != clock):
                raise ValueError(f"{symbol} {name} clock does not match spot")
        if int(clock[0]) != SERIES_BEGIN_MS or int(clock[-1]) >= SERIES_END_EXCLUSIVE_MS:
            raise ValueError("series is not the 2022–2025 window")
        if np.any(np.diff(clock) != MINUTE):
            raise ValueError(f"{symbol} minute grid is not continuous")
        flag = np.zeros(len(clock), dtype=bool)
        rate = np.zeros(len(clock), dtype=np.float64)
        for stamp, value in zip(fund_s, fund_r):
            if stamp < SERIES_BEGIN_MS or stamp >= SERIES_END_EXCLUSIVE_MS:
                raise ValueError("funding stamp is outside 2022–2025")
            i = int((stamp - SERIES_BEGIN_MS) // MINUTE)
            if int(clock[i]) != stamp:
                raise ValueError("funding stamp is not on the minute grid")
            if flag[i]:
                raise ValueError("duplicate funding stamp")
            flag[i] = True
            rate[i] = value
        out[symbol] = {
            "spot_o": np.asarray(spot_o, dtype=np.float64),
            "spot_c": np.asarray(spot_c, dtype=np.float64),
            "perp_o": np.asarray(perp_o, dtype=np.float64),
            "perp_c": np.asarray(perp_c, dtype=np.float64),
            "mark_o": np.asarray(mark_o, dtype=np.float64),
            "mark_c": np.asarray(mark_c, dtype=np.float64),
            "fund_flag": flag,
            "fund_rate": rate,
            "step": QTY_STEP[symbol],
            "min_qty": MIN_QTY[symbol],
        }
    year_ends = {}
    for year in (2022, 2023, 2024, 2025):
        boundary = int(datetime(year + 1, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
        year_ends[year] = int(np.searchsorted(clock, boundary, side="left") - 1)
    return out, clock, year_ends
