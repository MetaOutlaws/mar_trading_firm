"""Loaders for tapes C, D, and N.

The harness takes the three directories as paths. It checks each
SHA256SUMS file before it reads a bar. A pinned run also requires the
SUMS file itself to match the digest in ``cells``.

BTCUSDT is always read from tape C. A listing is read from the catalog
source (C, D, or N). Tape D is the delisted history and is required even
when the caller only wants a survivor: the cell is C union D union N.

Column names differ across the three pulls. The loader accepts the names
each README records and does not guess a unit from the magnitude when the
column is already called ``bar_open_ts_ms`` or ``fundingRateTimestamp``.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from research.new_listing_drift.cells import REAL_TAPE_DIR_NAMES, TAPE_SUMS_SHA256
from research.new_listing_drift.hashing import sha256_file

# Tape C and tape N name the bar open ``bar_open_ts_ms`` (int64 milliseconds).
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
MS_OPEN_TIME_COLUMNS = frozenset({"bar_open_ts_ms"})

FUNDING_TIME_ALIASES = (
    "fundingratetimestamp",
    "funding_ts_ms",
    "funding_time_ms",
    "funding_time",
    "timestamp",
    "ts",
    "time",
)
MS_FUNDING_TIME_COLUMNS = frozenset({"fundingratetimestamp", "funding_ts_ms", "funding_time_ms"})
FUNDING_RATE_ALIASES = ("fundingrate", "funding_rate", "rate")

LAUNCH_ALIASES = ("launchtime", "launch_time", "launchtime_ms", "launch_time_ms")
DELIST_ALIASES = ("delisttime", "delist_time", "delisttime_ms")
DELIVERY_ALIASES = ("deliverytime", "delivery_time", "deliverytime_ms")
OHLC = ("open", "high", "low", "close")

MEMBERSHIP_NAMES = (
    "membership_pit.parquet",
    "membership_pit.csv",
    "membership.parquet",
    "membership.csv",
)


class TapeIntegrityError(RuntimeError):
    """SHA256SUMS is missing, incomplete, or does not match the bytes."""


class CountersignRequired(RuntimeError):
    """A real tape was asked to run before Garwe's countersign."""


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


def verify_sums(tape_dir: Path, source: str) -> dict[str, object]:
    """Verify every SHA256SUMS entry for one tape source (C, D, or N)."""
    if source not in TAPE_SUMS_SHA256:
        raise TapeIntegrityError(f"unknown tape source {source!r}")
    tape_dir = Path(tape_dir)
    sums_path = tape_dir / "SHA256SUMS"
    if not sums_path.is_file():
        raise TapeIntegrityError(f"SHA256SUMS is missing under {tape_dir}")
    sums_hash = sha256_file(sums_path)
    pinned = TAPE_SUMS_SHA256[source]
    pins_matched = sums_hash == pinned
    entries = parse_sha256sums(sums_path)
    mismatches: list[str] = []
    missing: list[str] = []
    for name, digest in entries.items():
        # Per-symbol trees are part of the SUMS file. A pinned run checks
        # every line. A fixture that lists only the files it created still
        # checks those files.
        file_path = tape_dir / name
        if not file_path.is_file():
            missing.append(name)
            continue
        actual = sha256_file(file_path)
        if actual != digest:
            mismatches.append(name)
    if missing or mismatches:
        raise TapeIntegrityError(
            f"tape {source} SUMS failed: missing={missing[:5]} mismatches={mismatches[:5]}"
        )
    return {
        "source": source,
        "tape_dir": str(tape_dir),
        "sums_sha256": sums_hash,
        "pinned_sums_sha256": pinned,
        "pins_matched": pins_matched,
        "n_files": len(entries),
    }


def assert_real_tapes_closed(paths: dict[str, Path], *, pins_matched: bool) -> None:
    """Refuse the research-box tapes until COUNTERSIGN.md exists.

    The path-name check runs before any file is opened. The pin check
    catches a copy of the real SUMS living under another directory name.
    """
    from research.new_listing_drift.hashing import countersign_present

    if countersign_present():
        return
    named = [
        source
        for source, path in paths.items()
        if Path(path).name == REAL_TAPE_DIR_NAMES.get(source)
    ]
    if named or pins_matched:
        raise CountersignRequired(
            "Real tapes stay closed. The harness and scorer hashes are "
            "provisional until Garwe countersigns. No bar and no metric "
            "is read before that ACK."
        )


def _pick_column(columns: list[str], aliases: tuple[str, ...], what: str) -> str:
    lookup = {c.lower(): c for c in columns}
    for alias in aliases:
        if alias.lower() in lookup:
            return lookup[alias.lower()]
    raise TapeIntegrityError(
        f"cannot find {what}; looked for {aliases} in columns {columns}"
    )


def _to_utc(values: pd.Series, *, unit: str | None = None) -> pd.DatetimeIndex:
    """Bybit times are int milliseconds. ISO strings are accepted too."""
    if unit is not None:
        numeric = pd.to_numeric(values, errors="coerce")
        finite = numeric.to_numpy(dtype="float64")
        if not np.isfinite(finite).any():
            raise TapeIntegrityError("time column is all null")
        return pd.DatetimeIndex(pd.to_datetime(numeric, unit=unit, utc=True))
    if pd.api.types.is_numeric_dtype(values):
        numeric = values.to_numpy(dtype="float64")
        finite = numeric[np.isfinite(numeric)]
        if finite.size == 0:
            raise TapeIntegrityError("time column is all null")
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


def _read_table(path: Path, symbol: str | None = None) -> pd.DataFrame:
    """Read a csv or parquet table, optionally one symbol from parquet."""
    if path.suffix == ".parquet":
        try:
            import pyarrow.parquet as pq
        except ImportError as exc:
            raise TapeIntegrityError(
                "reading parquet needs pyarrow; it is not installed"
            ) from exc
        filters = [("symbol", "==", symbol)] if symbol is not None else None
        table = pq.read_table(path, filters=filters)
        return table.to_pandas()
    if path.name.endswith(".csv.gz") or path.suffix == ".csv":
        frame = pd.read_csv(path)
        if symbol is not None and "symbol" in frame.columns:
            frame = frame.loc[frame["symbol"].astype(str) == symbol]
        return frame
    raise TapeIntegrityError(f"unsupported table {path.name}")


def _bars_from_frame(frame: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if frame.empty:
        raise TapeIntegrityError(f"{symbol} has no perp bars")
    time_col = _pick_column(list(frame.columns), OPEN_TIME_ALIASES, "bar open time")
    time_unit = "ms" if time_col.lower() in MS_OPEN_TIME_COLUMNS else None
    ohlc_cols = [_pick_column(list(frame.columns), (name,), name) for name in OHLC]
    index = _to_utc(frame[time_col], unit=time_unit)
    data = {
        name: pd.to_numeric(frame[col], errors="coerce").to_numpy()
        for name, col in zip(OHLC, ohlc_cols)
    }
    if "volume" in {c.lower() for c in frame.columns}:
        volume_col = _pick_column(list(frame.columns), ("volume",), "volume")
        data["volume"] = pd.to_numeric(frame[volume_col], errors="coerce").to_numpy()
    bars = pd.DataFrame(data, index=index)
    bars.index.name = "open_time"
    if bars.index.has_duplicates:
        raise TapeIntegrityError(f"{symbol} has duplicate open times")
    bars = bars.sort_index()
    if bars.index.tz is None:
        raise TapeIntegrityError(f"{symbol} bar index is not timezone-aware")
    return bars


def load_symbol_bars(tape_dir: Path, symbol: str) -> pd.DataFrame:
    """Hourly perp bars for one symbol. Index is the bar open, UTC."""
    tape_dir = Path(tape_dir)
    parquet = tape_dir / "perp_1h.parquet"
    csv_path = tape_dir / "perp_1h.csv"
    if parquet.is_file():
        frame = _read_table(parquet, symbol)
    elif csv_path.is_file():
        frame = _read_table(csv_path, symbol)
    else:
        raise TapeIntegrityError(f"perp_1h is missing under {tape_dir}")
    return _bars_from_frame(frame, symbol)


def load_symbol_funding(tape_dir: Path, symbol: str) -> pd.Series:
    """Funding rates indexed by settlement time. Empty if the symbol has none.

    An empty series is not a zero fill. The engine flags a hold that
    should have contained a settlement and finds none.
    """
    tape_dir = Path(tape_dir)
    parquet = tape_dir / "funding.parquet"
    csv_path = tape_dir / "funding.csv"
    if parquet.is_file():
        frame = _read_table(parquet, symbol)
    elif csv_path.is_file():
        frame = _read_table(csv_path, symbol)
    else:
        raise TapeIntegrityError(f"funding table is missing under {tape_dir}")
    if frame.empty:
        return pd.Series(dtype="float64", name="funding_rate")
    time_col = _pick_column(list(frame.columns), FUNDING_TIME_ALIASES, "funding time")
    rate_col = _pick_column(list(frame.columns), FUNDING_RATE_ALIASES, "funding rate")
    time_unit = "ms" if time_col.lower() in MS_FUNDING_TIME_COLUMNS else None
    index = _to_utc(frame[time_col], unit=time_unit)
    rates = pd.Series(
        pd.to_numeric(frame[rate_col], errors="coerce").to_numpy(),
        index=index,
        name="funding_rate",
    )
    rates = rates[np.isfinite(rates.to_numpy(dtype="float64"))]
    if rates.index.has_duplicates:
        # A duplicated print is a tape error, not something to average away.
        raise TapeIntegrityError(f"{symbol} has duplicate funding timestamps")
    return rates.sort_index()


def _parse_membership_time(series: pd.Series) -> pd.Series:
    """Launch and delist columns arrive as milliseconds or as ISO text."""
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_datetime(series, unit="ms", utc=True, errors="coerce")
    # A csv may store milliseconds as text. Numbers longer than 12 digits are ms.
    as_text = series.astype(str).str.strip()
    numeric = pd.to_numeric(as_text, errors="coerce")
    if numeric.notna().any() and float(np.nanmedian(numeric.to_numpy(dtype="float64"))) > 1e11:
        return pd.to_datetime(numeric, unit="ms", utc=True, errors="coerce")
    cleaned = series.replace({"": pd.NA, "NaT": pd.NA, "nan": pd.NA})
    return pd.to_datetime(cleaned, utc=True, errors="coerce")


def load_membership(tape_dir: Path) -> pd.DataFrame:
    """Membership table indexed by symbol.

    Tape C uses ``membership_pit``. Tape N uses ``membership``. Delist and
    delivery columns are optional: survivors do not have one. The index
    keeps the first row if a symbol is repeated.
    """
    tape_dir = Path(tape_dir)
    path = next((tape_dir / name for name in MEMBERSHIP_NAMES if (tape_dir / name).is_file()), None)
    if path is None:
        raise TapeIntegrityError(f"membership table is missing under {tape_dir}")
    frame = _read_table(path)
    symbol_col = _pick_column(list(frame.columns), ("symbol",), "symbol")
    launch_col = _pick_column(list(frame.columns), LAUNCH_ALIASES, "launchTime")
    columns = {c.lower(): c for c in frame.columns}
    delist_col = next((columns[alias] for alias in DELIST_ALIASES if alias in columns), None)
    delivery_col = next((columns[alias] for alias in DELIVERY_ALIASES if alias in columns), None)
    interval_col = columns.get("fundinginterval_min")
    out = pd.DataFrame(
        {
            "symbol": frame[symbol_col].astype(str),
            "launch_time": _parse_membership_time(frame[launch_col]),
        }
    )
    # Kept separate so the engine can exit at the earlier of delivery and delist
    # and label the reason with the one that bound.
    empty_deadline = pd.Series(pd.NaT, index=out.index, dtype="datetime64[ns, UTC]")
    out["delist_time"] = (
        empty_deadline.copy() if delist_col is None else _parse_membership_time(frame[delist_col]).to_numpy()
    )
    out["delivery_time"] = (
        empty_deadline.copy() if delivery_col is None else _parse_membership_time(frame[delivery_col]).to_numpy()
    )
    if interval_col is None:
        out["funding_interval_min"] = np.nan
    else:
        out["funding_interval_min"] = pd.to_numeric(frame[interval_col], errors="coerce")
    out = out.drop_duplicates("symbol", keep="first")
    return out.set_index("symbol", drop=True)


def listing_deadline(membership: pd.DataFrame, symbol: str) -> tuple[pd.Timestamp | None, str | None]:
    """Earlier of delivery and delist, and which one it was.

    The exit is the last tradable bar before that clock time. When only
    one of the two columns is present, that one is the deadline.
    """
    if symbol not in membership.index:
        return None, None
    row = membership.loc[symbol]
    candidates: list[tuple[pd.Timestamp, str]] = []
    for column, kind in (("delivery_time", "delivery"), ("delist_time", "delist")):
        if column not in membership.columns:
            continue
        value = row[column] if not isinstance(row, pd.DataFrame) else row.iloc[0][column]
        if pd.notna(value):
            candidates.append((pd.Timestamp(value), kind))
    if not candidates:
        return None, None
    when, kind = min(candidates, key=lambda item: item[0])
    return when, kind


def funding_interval(membership: pd.DataFrame, symbol: str) -> pd.Timedelta:
    """Settlement spacing. Bybit's default is 8h when the column is absent."""
    if symbol in membership.index:
        minutes = membership.at[symbol, "funding_interval_min"]
        if pd.notna(minutes) and float(minutes) > 0:
            return pd.Timedelta(minutes=float(minutes))
    return pd.Timedelta(hours=8)
