"""Tape C loader.

The harness takes the tape directory as a path. It checks SHA256SUMS
before it reads a bar. A pinned cell also requires the SUMS file itself,
``perp_1h.parquet`` and ``membership_pit.parquet`` to match the Tape C
digests in ``cells``.

Point-in-time membership comes from ``membership_pit``. A delisted name
stays eligible while ``launchTime <= t < delistTime`` and drops out at
the delist. Price history starts at ``first_bar``.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from research.xs_spread.cells import (
    MEMBERSHIP_PIT_PARQUET_SHA256,
    PERP_1H_SHA256,
    TAPE_C_SUMS_SHA256,
)
from research.xs_spread.hashing import sha256_file

# Tape C perp_1h names the bar open ``bar_open_ts_ms`` (int64 milliseconds).
# membership_pit (csv and parquet) already uses launchTime, delistTime,
# first_bar and last_bar, which normalize_membership accepts.
OPEN_TIME_ALIASES = (
    "bar_open_ts_ms",
    "open_time_ms",
    "open_time",
    "start",
    "start_ms",
    "timestamp",
    "ts",
    "time",
)
# The column name is the unit. Do not infer it from the magnitude.
MS_OPEN_TIME_COLUMNS = frozenset({"bar_open_ts_ms"})
OHLC = ("open", "high", "low", "close")


class TapeIntegrityError(RuntimeError):
    """SHA256SUMS is missing, incomplete, or does not match the bytes."""


def parse_sha256sums(path: Path) -> dict[str, str]:
    """Parse a ``sha256sum`` file. Later duplicate names replace earlier ones."""
    entries: dict[str, str] = {}
    text = path.read_text(encoding="utf-8")
    for line_no, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            raise TapeIntegrityError(f"{path.name}:{line_no} is not 'hash  filename'")
        digest, name = parts
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest.lower()):
            raise TapeIntegrityError(f"{path.name}:{line_no} has a bad digest")
        entries[name] = digest.lower()
    if not entries:
        raise TapeIntegrityError(f"{path} is empty")
    return entries


def verify_sums(tape_dir: Path, *, check_pins: bool) -> dict[str, object]:
    """Verify every SHA256SUMS entry. Optionally require the Tape C pins.

    ``check_pins`` is on for ``xs_realized_skew_weekly``. Synthetic tests
    pass false so a tiny fixture can still prove the checker works.
    """
    tape_dir = Path(tape_dir)
    sums_path = tape_dir / "SHA256SUMS"
    if not sums_path.is_file():
        raise TapeIntegrityError(f"SHA256SUMS is missing under {tape_dir}")
    sums_hash = sha256_file(sums_path)
    if check_pins and sums_hash != TAPE_C_SUMS_SHA256:
        raise TapeIntegrityError(
            f"SHA256SUMS hash {sums_hash} != Tape C pin {TAPE_C_SUMS_SHA256}"
        )
    entries = parse_sha256sums(sums_path)
    if check_pins:
        if entries.get("perp_1h.parquet") != PERP_1H_SHA256:
            raise TapeIntegrityError("perp_1h.parquet line does not match the Tape C pin")
        if entries.get("membership_pit.parquet") != MEMBERSHIP_PIT_PARQUET_SHA256:
            raise TapeIntegrityError(
                "membership_pit.parquet line does not match the Tape C pin"
            )
    for name, expected in entries.items():
        file_path = tape_dir / name
        if not file_path.is_file():
            raise TapeIntegrityError(f"SHA256SUMS lists {name}, which is missing")
        got = sha256_file(file_path)
        if got != expected:
            raise TapeIntegrityError(f"{name} sha256 {got} != SUMS {expected}")
    return {
        "sums_sha256": sums_hash,
        "n_files": len(entries),
        "perp_1h_sha256": entries.get("perp_1h.parquet"),
        "membership_pit_parquet_sha256": entries.get("membership_pit.parquet"),
        "pins_checked": check_pins,
    }


def _pick_column(columns: list[str], aliases: tuple[str, ...], what: str) -> str:
    lookup = {c.lower(): c for c in columns}
    for alias in aliases:
        if alias.lower() in lookup:
            return lookup[alias.lower()]
    raise TapeIntegrityError(
        f"cannot find {what}; looked for {aliases} in columns {columns}"
    )


def _to_utc(values: pd.Series, *, unit: str | None = None) -> pd.DatetimeIndex:
    """Bybit kline times are int milliseconds. ISO strings are accepted too.

    ``unit`` is set for ``bar_open_ts_ms``, which Tape C defines as
    milliseconds even when a short fixture would not trip the median check.
    """
    if unit is not None:
        numeric = pd.to_numeric(values, errors="coerce")
        finite = numeric.to_numpy(dtype="float64")
        if not np.isfinite(finite).any():
            raise TapeIntegrityError("open-time column is all null")
        return pd.DatetimeIndex(pd.to_datetime(numeric, unit=unit, utc=True))
    if np.issubdtype(values.dtype, np.number):
        numeric = values.to_numpy(dtype="float64")
        finite = numeric[np.isfinite(numeric)]
        if finite.size == 0:
            raise TapeIntegrityError("open-time column is all null")
        median = float(np.median(finite))
        if median > 1e17:
            unit = "ns"
        elif median > 1e14:
            unit = "us"
        elif median > 1e11:
            unit = "ms"
        else:
            unit = "s"
        return pd.DatetimeIndex(pd.to_datetime(values, unit=unit, utc=True))
    return pd.DatetimeIndex(pd.to_datetime(values, utc=True))


def _read_table(path: Path) -> pd.DataFrame:
    if path.suffix == ".parquet":
        try:
            return pd.read_parquet(path)
        except ImportError as exc:
            raise TapeIntegrityError(
                "reading parquet needs pyarrow; it is not installed"
            ) from exc
    if path.name.endswith(".csv.gz") or path.suffix == ".csv":
        return pd.read_csv(path)
    raise TapeIntegrityError(f"unsupported table {path.name}")


def load_perp_panel(tape_dir: Path) -> dict[str, pd.DataFrame]:
    """Long perp_1h table to a UTC panel keyed by symbol.

    Required columns: symbol, an open-time, and open/high/low/close.
    The open-time is the bar open. Duplicate opens are an error.
    """
    path = Path(tape_dir) / "perp_1h.parquet"
    if not path.is_file():
        raise TapeIntegrityError(f"perp_1h.parquet is missing under {tape_dir}")
    frame = _read_table(path)
    symbol_col = _pick_column(list(frame.columns), ("symbol",), "symbol")
    time_col = _pick_column(list(frame.columns), OPEN_TIME_ALIASES, "bar open time")
    time_unit = "ms" if time_col.lower() in MS_OPEN_TIME_COLUMNS else None
    ohlc_cols = [_pick_column(list(frame.columns), (name,), name) for name in OHLC]
    out: dict[str, pd.DataFrame] = {}
    grouped = frame.groupby(symbol_col, sort=False)
    for symbol, part in grouped:
        index = _to_utc(part[time_col], unit=time_unit)
        bars = pd.DataFrame(
            {name: pd.to_numeric(part[col], errors="coerce").to_numpy() for name, col in zip(OHLC, ohlc_cols)},
            index=index,
        )
        bars.index.name = "open_time"
        if bars.index.has_duplicates:
            raise TapeIntegrityError(f"{symbol} has duplicate open times")
        out[str(symbol)] = bars.sort_index()
    if not out:
        raise TapeIntegrityError("perp_1h.parquet has no symbols")
    return out


def normalize_membership(frame: pd.DataFrame) -> pd.DataFrame:
    """Canonical membership columns used by the point-in-time filter."""
    symbol_col = _pick_column(list(frame.columns), ("symbol",), "symbol")
    launch_col = _pick_column(list(frame.columns), ("launch_time", "launchTime"), "launchTime")
    delist_col = _pick_column(list(frame.columns), ("delist_time", "delistTime"), "delistTime")
    first_col = _pick_column(list(frame.columns), ("first_bar",), "first_bar")
    last_col = _pick_column(list(frame.columns), ("last_bar",), "last_bar")

    def _times(series: pd.Series) -> pd.Series:
        cleaned = series.replace({"": pd.NA, "NaT": pd.NA})
        return pd.to_datetime(cleaned, utc=True, errors="coerce")

    out = pd.DataFrame(
        {
            "symbol": frame[symbol_col].astype(str),
            "launch_time": _times(frame[launch_col]),
            "delist_time": _times(frame[delist_col]),
            "first_bar": _times(frame[first_col]),
            "last_bar": _times(frame[last_col]),
        }
    )
    if out["symbol"].duplicated().any():
        raise TapeIntegrityError("membership has duplicate symbols")
    return out.set_index("symbol", drop=True)


def load_membership(tape_dir: Path) -> pd.DataFrame:
    """Prefer the parquet membership table. The csv is still hash-checked."""
    parquet = Path(tape_dir) / "membership_pit.parquet"
    csv_path = Path(tape_dir) / "membership_pit.csv"
    if parquet.is_file():
        return normalize_membership(_read_table(parquet))
    if csv_path.is_file():
        return normalize_membership(_read_table(csv_path))
    raise TapeIntegrityError("membership_pit.parquet and membership_pit.csv are both missing")


def load_tape(tape_dir: Path, *, check_pins: bool) -> tuple[dict[str, pd.DataFrame], pd.DataFrame, dict[str, object]]:
    """Verify SUMS, then load the perp panel and the membership table."""
    report = verify_sums(tape_dir, check_pins=check_pins)
    panel = load_perp_panel(tape_dir)
    membership = load_membership(tape_dir)
    return panel, membership, report
