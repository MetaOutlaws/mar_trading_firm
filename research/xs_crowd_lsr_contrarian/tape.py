"""Loaders for tape C, the N-tape, the LSR tape, and the OI pin.

The four SHA256SUMS file digests are checked before a bar is used as a
return. Files this loader reads are checked against their line in that
SUMS file. Raw payloads that are not read are not rehashed; the pin is
the SUMS file itself, which is what the prereg names.

Prices are tape C ``perp_1h`` union N-tape perp, tape C winning on a
symbol that is in both. Funding is the same union: a name with no row in
either books 0 later, and is disclosed. The LSR input is the raw daily
buyRatio. It is not rescaled.

2026 rows are dropped, except price and funding timestamps up to the
holdout's last exit (2026-01-05 00:00 UTC) when that window is the one
being loaded. No 2026 rebalance is formed by the calendar.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from research.xs_crowd_lsr_contrarian.calendar import YEAR_2026_TS, WindowError, exit_cap
from research.xs_crowd_lsr_contrarian.hashing import sha256_file
from research.xs_crowd_lsr_contrarian.pins import (
    DEFAULT_ROOT,
    LS_SUMS_SHA256,
    LS_TAPE_DIRNAME,
    N_TAPE_DIRNAME,
    N_TAPE_SUMS_SHA256,
    OI_SUMS_SHA256,
    OI_TAPE_DIRNAME,
    TAPE_C_DIRNAME,
    TAPE_C_SUMS_SHA256,
)

OHLC = ("open", "high", "low", "close")
OPEN_TIME_ALIASES = (
    "bar_open_ts_ms",
    "open_time_ms",
    "start",
    "timestamp",
    "ts",
    "ts_ms",
    "time",
    "open_time",
)
MS_OPEN_COLUMNS = frozenset({"bar_open_ts_ms", "open_time_ms", "ts_ms"})


class TapeIntegrityError(RuntimeError):
    """A pinned tape is missing or its bytes do not match."""


def parse_sha256sums(path: Path) -> dict[str, str]:
    """Parse a sha256sum file. Later duplicate names replace earlier ones."""
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


def assert_sums_pin(tape_dir: Path, expected: str, label: str) -> dict[str, str]:
    """The SHA256SUMS file's own digest must equal the prereg pin."""
    path = Path(tape_dir) / "SHA256SUMS"
    if not path.is_file():
        raise TapeIntegrityError(f"{label} SHA256SUMS is missing under {tape_dir}")
    digest = sha256_file(path)
    if digest != expected:
        raise TapeIntegrityError(f"{label} SHA256SUMS {digest} != pin {expected}")
    return parse_sha256sums(path)


def assert_listed(entries: dict[str, str], tape_dir: Path, name: str) -> None:
    """A file this run reads must match its SUMS line."""
    expected = entries.get(name)
    if expected is None:
        raise TapeIntegrityError(f"{name} is not listed in SHA256SUMS")
    path = Path(tape_dir) / name
    digest = sha256_file(path)
    if digest != expected:
        raise TapeIntegrityError(f"{name} sha256 {digest} != SUMS {expected}")


def _pick(columns: list[str], aliases: tuple[str, ...], what: str) -> str:
    lookup = {column.lower(): column for column in columns}
    for alias in aliases:
        if alias.lower() in lookup:
            return lookup[alias.lower()]
    raise TapeIntegrityError(f"cannot find {what}; looked for {aliases} in {columns}")


def _read_table(path: Path) -> pd.DataFrame:
    if path.suffix == ".parquet":
        try:
            return pd.read_parquet(path)
        except ImportError as exc:
            raise TapeIntegrityError("reading parquet needs pyarrow") from exc
    if path.name.endswith(".csv.gz") or path.suffix == ".csv":
        return pd.read_csv(path)
    raise TapeIntegrityError(f"unsupported table {path.name}")


def _to_utc(values: pd.Series, *, force_ms: bool) -> pd.DatetimeIndex:
    if force_ms or np.issubdtype(values.dtype, np.number):
        numeric = pd.to_numeric(values, errors="coerce")
        finite = numeric.to_numpy(dtype="float64")
        finite = finite[np.isfinite(finite)]
        if finite.size == 0:
            raise TapeIntegrityError("time column is all null")
        if force_ms:
            unit = "ms"
        else:
            median = float(np.median(finite))
            if median > 1e17:
                unit = "ns"
            elif median > 1e14:
                unit = "us"
            elif median > 1e11:
                unit = "ms"
            else:
                unit = "s"
        return pd.DatetimeIndex(pd.to_datetime(numeric, unit=unit, utc=True))
    return pd.DatetimeIndex(pd.to_datetime(values, utc=True))


def _bars_from_frame(frame: pd.DataFrame, *, default_symbol: str | None) -> dict[str, pd.DataFrame]:
    columns = list(frame.columns)
    if "symbol" in {column.lower() for column in columns}:
        symbol_col = _pick(columns, ("symbol",), "symbol")
    elif default_symbol is not None:
        symbol_col = None
    else:
        raise TapeIntegrityError(f"price table is missing symbol; columns {columns}")
    time_col = _pick(columns, OPEN_TIME_ALIASES, "bar open time")
    ohlc_cols = [_pick(columns, (name,), name) for name in OHLC]
    force_ms = time_col.lower() in MS_OPEN_COLUMNS
    out: dict[str, pd.DataFrame] = {}
    if symbol_col is None:
        groups = [(default_symbol, frame)]
    else:
        groups = frame.groupby(symbol_col, sort=False)
    for symbol, part in groups:
        index = _to_utc(part[time_col], force_ms=force_ms)
        bars = pd.DataFrame(
            {name: pd.to_numeric(part[col], errors="coerce").to_numpy() for name, col in zip(OHLC, ohlc_cols, strict=True)},
            index=index,
        )
        bars.index.name = "open_time"
        bars = bars[~bars.index.duplicated(keep="last")].sort_index()
        out[str(symbol)] = bars
    return out


def _clip_panel(panel: dict[str, pd.DataFrame], cap: pd.Timestamp) -> dict[str, pd.DataFrame]:
    """Drop bars opened after the window's exit cap. That is the 2026 wall."""
    clipped: dict[str, pd.DataFrame] = {}
    for symbol, bars in panel.items():
        kept = bars.loc[bars.index <= cap]
        if not kept.empty:
            clipped[symbol] = kept
    return clipped


def load_price_panel(tape_dir: Path, *, combined: str, per_symbol_glob: str) -> dict[str, pd.DataFrame]:
    """Combined parquet if it is there, otherwise one file per symbol."""
    root = Path(tape_dir)
    combined_path = root / combined
    if combined_path.is_file():
        return _bars_from_frame(_read_table(combined_path), default_symbol=None)
    paths = sorted(root.glob(per_symbol_glob))
    if not paths:
        raise TapeIntegrityError(f"no perp prices under {tape_dir} ({combined} or {per_symbol_glob})")
    panel: dict[str, pd.DataFrame] = {}
    for path in paths:
        symbol = path.name.split(".", 1)[0]
        part = _bars_from_frame(_read_table(path), default_symbol=symbol)
        panel.update(part)
    return panel


def load_funding_table(path: Path) -> dict[str, pd.Series]:
    """Funding prints. Tape C and the N-tape do not share column names."""
    if not path.is_file():
        raise TapeIntegrityError(f"funding file is missing: {path}")
    frame = _read_table(path)
    columns = list(frame.columns)
    symbol_col = _pick(columns, ("symbol",), "symbol")
    time_col = _pick(
        columns,
        ("funding_ts_ms", "fundingRateTimestamp", "funding_time_ms", "timestamp"),
        "funding time",
    )
    rate_col = _pick(columns, ("funding_rate", "fundingRate", "rate"), "funding rate")
    force_ms = time_col.lower() in {"funding_ts_ms", "fundingratetimestamp", "funding_time_ms", "timestamp"}
    out: dict[str, pd.Series] = {}
    for symbol, part in frame.groupby(symbol_col, sort=False):
        index = _to_utc(part[time_col], force_ms=force_ms)
        rates = pd.Series(
            pd.to_numeric(part[rate_col], errors="coerce").to_numpy(dtype="float64"),
            index=index,
            dtype="float64",
        )
        rates = rates[~rates.index.duplicated(keep="last")].sort_index()
        out[str(symbol)] = rates
    return out


def _clip_funding(funding: dict[str, pd.Series], cap: pd.Timestamp) -> dict[str, pd.Series]:
    clipped: dict[str, pd.Series] = {}
    for symbol, rates in funding.items():
        kept = rates.loc[rates.index <= cap]
        if len(kept):
            clipped[symbol] = kept
    return clipped


def merge_funding(
    tape_c: dict[str, pd.Series],
    n_tape: dict[str, pd.Series],
) -> tuple[dict[str, pd.Series], list[str]]:
    """Union. On a shared symbol, tape C rows win timestamp by timestamp.

    N-tape rows are added only where tape C has no print. Overlap is returned
    so the manifest can list it. No rate is invented for a hole.
    """
    merged = {symbol: rates.copy() for symbol, rates in tape_c.items()}
    overlap: list[str] = []
    for symbol, rates in n_tape.items():
        if symbol not in merged:
            merged[symbol] = rates.copy()
            continue
        overlap.append(symbol)
        existing = merged[symbol]
        extra = rates.loc[~rates.index.isin(existing.index)]
        if len(extra):
            merged[symbol] = pd.concat([existing, extra]).sort_index()
    overlap.sort()
    return merged, overlap


def merge_panels(
    tape_c: dict[str, pd.DataFrame],
    n_tape: dict[str, pd.DataFrame],
) -> tuple[dict[str, pd.DataFrame], list[str]]:
    """Tape C prices win for a symbol present in both panels."""
    merged = dict(tape_c)
    overlap = sorted(symbol for symbol in n_tape if symbol in tape_c)
    for symbol, bars in n_tape.items():
        if symbol not in merged:
            merged[symbol] = bars
    return merged, overlap


def _times(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.notna().mean() > 0.5:
        median = float(numeric.dropna().median()) if numeric.notna().any() else 0.0
        unit = "ms" if median > 1e11 else "s"
        return pd.to_datetime(numeric, unit=unit, utc=True, errors="coerce")
    cleaned = series.replace({"": pd.NA, "NaT": pd.NA})
    return pd.to_datetime(cleaned, utc=True, errors="coerce")


def load_tape_c_membership(tape_dir: Path) -> pd.DataFrame:
    root = Path(tape_dir)
    path = root / "membership_pit.parquet"
    if not path.is_file():
        path = root / "membership_pit.csv"
    if not path.is_file():
        raise TapeIntegrityError("membership_pit.parquet and membership_pit.csv are both missing")
    frame = _read_table(path)
    symbol_col = _pick(list(frame.columns), ("symbol",), "symbol")
    launch_col = _pick(list(frame.columns), ("launch_time", "launchTime"), "launch")
    delist_col = _pick(list(frame.columns), ("delist_time", "delistTime"), "delist")
    first_col = _pick(list(frame.columns), ("first_bar", "first_bar_utc"), "first_bar")
    last_col = _pick(list(frame.columns), ("last_bar", "last_bar_utc"), "last_bar")
    out = pd.DataFrame(
        {
            "symbol": frame[symbol_col].astype(str),
            "launch_time": _times(frame[launch_col]),
            "delist_time": _times(frame[delist_col]),
            "first_bar": _times(frame[first_col]),
            "last_bar": _times(frame[last_col]),
            "source": "tape_c",
        }
    )
    return out


def n_tape_mask(frame: pd.DataFrame) -> pd.Series:
    """USDT linear perps. Empty symbolType, quoteCoin USDT. USDC perps are out."""
    quote = frame["quoteCoin"].astype(str).str.upper()
    kind = frame["symbolType"] if "symbolType" in frame.columns else ""
    kind_text = kind.fillna("").astype(str).str.strip()
    return (quote == "USDT") & (kind_text == "")


def load_n_membership(tape_dir: Path) -> pd.DataFrame:
    path = Path(tape_dir) / "membership.csv"
    if not path.is_file():
        raise TapeIntegrityError(f"N-tape membership.csv is missing under {tape_dir}")
    frame = _read_table(path)
    if "quoteCoin" not in frame.columns:
        raise TapeIntegrityError("N-tape membership.csv has no quoteCoin")
    kept = frame.loc[n_tape_mask(frame)].copy()
    symbol_col = _pick(list(kept.columns), ("symbol",), "symbol")
    launch_col = _pick(list(kept.columns), ("launch_utc", "launchTime", "launch_time"), "launch")
    first_col = _pick(list(kept.columns), ("first_bar_utc", "first_bar"), "first_bar")
    last_col = _pick(list(kept.columns), ("last_bar_utc", "last_bar"), "last_bar")
    out = pd.DataFrame(
        {
            "symbol": kept[symbol_col].astype(str),
            "launch_time": _times(kept[launch_col]),
            "delist_time": pd.NaT,
            "first_bar": _times(kept[first_col]),
            "last_bar": _times(kept[last_col]),
            "source": "n_tape",
        }
    )
    return out


def union_membership(
    tape_c: pd.DataFrame,
    n_tape: pd.DataFrame,
) -> tuple[pd.DataFrame, list[str]]:
    """Tape C wins when a symbol is in both membership tables."""
    overlap = sorted(set(tape_c["symbol"]) & set(n_tape["symbol"]))
    extra = n_tape.loc[~n_tape["symbol"].isin(set(tape_c["symbol"]))]
    out = pd.concat([tape_c, extra], ignore_index=True)
    if out["symbol"].duplicated().any():
        raise TapeIntegrityError("universe membership has duplicate symbols after the union")
    return out.set_index("symbol", drop=True), overlap


def load_ratio_frame(ls_dir: Path) -> pd.DataFrame:
    """Raw daily buyRatio. Combined parquet, else one file per symbol.

    Rows at or after 2026-01-01 are dropped here. They are never a feature.
    """
    root = Path(ls_dir)
    combined = root / "bybit_lsratio_20261020_ls1d_combined.parquet"
    frames: list[pd.DataFrame] = []
    if combined.is_file():
        frames.append(_read_table(combined))
    else:
        for path in sorted((root / "per_symbol" / "ls1d").glob("*.parquet")):
            if path.name.endswith(".meta.json"):
                continue
            frames.append(_read_table(path))
    if not frames:
        raise TapeIntegrityError(f"no ls1d parquet under {ls_dir}")
    frame = pd.concat(frames, ignore_index=True)
    columns = list(frame.columns)
    symbol_col = _pick(columns, ("symbol",), "symbol")
    time_col = _pick(columns, ("ts_ms", "timestamp", "ts"), "ratio timestamp")
    value_col = _pick(columns, ("buyRatio", "buy_ratio"), "buyRatio")
    out = pd.DataFrame(
        {
            "symbol": frame[symbol_col].astype(str),
            "ts": _to_utc(frame[time_col], force_ms=time_col.lower() in {"ts_ms", "timestamp"}),
            "buy_ratio": pd.to_numeric(frame[value_col], errors="coerce"),
        }
    )
    # Raw values. Do not apply 0.35 + 0.30 * buy_ratio.
    out = out.loc[out["ts"] < YEAR_2026_TS]
    return out.reset_index(drop=True)


def load_status(ls_dir: Path) -> dict[str, str]:
    """``status`` from per_symbol/ls1d meta, with ls1h as a fallback."""
    root = Path(ls_dir)
    found: dict[str, str] = {}
    for series in ("ls1d", "ls1h"):
        folder = root / "per_symbol" / series
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.meta.json")):
            symbol = path.name[: -len(".meta.json")]
            if symbol in found and series != "ls1d":
                continue
            payload = json.loads(path.read_text(encoding="utf-8"))
            status = payload.get("status")
            if status in {"Trading", "Closed"}:
                found[symbol] = str(status)
    return found


def _verify_inputs(paths: dict[str, Path], sums: dict[str, dict[str, str]]) -> None:
    """Hash every price, funding, membership, and ratio file this run will parse.

    Unread raw captures stay covered by the SHA256SUMS file pin only.
    """
    _verify_prices(paths["tape_c"], sums["tape_c"])
    _verify_prices(paths["n_tape"], sums["n_tape"])
    for root_key, names in (
        ("tape_c", ("funding.parquet", "membership_pit.parquet", "membership_pit.csv")),
        ("n_tape", ("funding.parquet", "membership.csv")),
        ("ls_tape", ("bybit_lsratio_20261020_ls1d_combined.parquet",)),
    ):
        root = paths[root_key]
        for name in names:
            if (root / name).is_file():
                assert_listed(sums[root_key], root, name)
    combined = paths["ls_tape"] / "bybit_lsratio_20261020_ls1d_combined.parquet"
    if not combined.is_file():
        for path in sorted((paths["ls_tape"] / "per_symbol" / "ls1d").glob("*.parquet")):
            assert_listed(sums["ls_tape"], paths["ls_tape"], path.relative_to(paths["ls_tape"]).as_posix())


def _verify_prices(root: Path, entries: dict[str, str]) -> None:
    combined = root / "perp_1h.parquet"
    if combined.is_file():
        assert_listed(entries, root, "perp_1h.parquet")
        return
    found = False
    for path in sorted(root.glob("per_symbol/*.perp.parquet")):
        found = True
        assert_listed(entries, root, path.relative_to(root).as_posix())
    if not found:
        raise TapeIntegrityError(f"no perp prices to verify under {root}")


def resolve_roots(
    root: Path | None,
    tape_c: Path | None,
    n_tape: Path | None,
    ls_tape: Path | None,
    oi_tape: Path | None,
) -> dict[str, Path]:
    base = Path(root) if root is not None else DEFAULT_ROOT
    return {
        "tape_c": Path(tape_c) if tape_c is not None else base / TAPE_C_DIRNAME,
        "n_tape": Path(n_tape) if n_tape is not None else base / N_TAPE_DIRNAME,
        "ls_tape": Path(ls_tape) if ls_tape is not None else base / LS_TAPE_DIRNAME,
        "oi_tape": Path(oi_tape) if oi_tape is not None else base / OI_TAPE_DIRNAME,
    }


def load_research_tapes(
    *,
    window: str,
    root: Path | None = None,
    tape_c: Path | None = None,
    n_tape: Path | None = None,
    ls_tape: Path | None = None,
    oi_tape: Path | None = None,
    check_pins: bool = True,
) -> dict[str, object]:
    """Pins first, then the frames the book needs. OI payload is not read."""
    if window not in {"main", "holdout"}:
        raise WindowError("refusing to load a 2026 window")
    paths = resolve_roots(root, tape_c, n_tape, ls_tape, oi_tape)
    cap = exit_cap(window)
    report: dict[str, object] = {"window": window, "exit_cap": str(cap), "pins_checked": check_pins}
    sums: dict[str, dict[str, str]] = {}
    if check_pins:
        sums["tape_c"] = assert_sums_pin(paths["tape_c"], TAPE_C_SUMS_SHA256, "tape C")
        sums["n_tape"] = assert_sums_pin(paths["n_tape"], N_TAPE_SUMS_SHA256, "N-tape")
        sums["ls_tape"] = assert_sums_pin(paths["ls_tape"], LS_SUMS_SHA256, "LSR")
        sums["oi_tape"] = assert_sums_pin(paths["oi_tape"], OI_SUMS_SHA256, "OI")
        # The OI payload is not an input. The pin is the check.
        report["oi_payload_read"] = False
        _verify_inputs(paths, sums)
        report["loaded_files_checked_against_sums"] = True
    tape_c_panel = load_price_panel(
        paths["tape_c"],
        combined="perp_1h.parquet",
        per_symbol_glob="per_symbol/*.perp.parquet",
    )
    n_panel = load_price_panel(
        paths["n_tape"],
        combined="perp_1h.parquet",
        per_symbol_glob="per_symbol/*.perp.parquet",
    )
    panel, price_overlap = merge_panels(tape_c_panel, n_panel)
    panel = _clip_panel(panel, cap)
    tape_c_funding = load_funding_table(paths["tape_c"] / "funding.parquet")
    n_funding_path = paths["n_tape"] / "funding.parquet"
    n_funding = load_funding_table(n_funding_path) if n_funding_path.is_file() else {}
    funding, funding_overlap = merge_funding(tape_c_funding, n_funding)
    funding = _clip_funding(funding, cap)
    ratios = load_ratio_frame(paths["ls_tape"])
    membership, member_overlap = union_membership(
        load_tape_c_membership(paths["tape_c"]),
        load_n_membership(paths["n_tape"]),
    )
    status = load_status(paths["ls_tape"])
    btc = panel.get("BTCUSDT")
    if btc is None:
        raise TapeIntegrityError("BTCUSDT has no 1h bars inside the window cap")
    report["price_overlap"] = price_overlap
    report["funding_overlap"] = funding_overlap
    report["membership_overlap"] = member_overlap
    report["n_symbols_prices"] = len(panel)
    report["n_symbols_funding"] = len(funding)
    report["n_symbols_membership"] = int(len(membership))
    report["n_status_meta"] = len(status)
    report["n_ratio_rows"] = int(len(ratios))
    report["max_price_open"] = str(max(bars.index.max() for bars in panel.values()))
    report["max_ratio_ts"] = str(ratios["ts"].max()) if len(ratios) else None
    max_ratio = report["max_ratio_ts"]
    if max_ratio is not None and pd.Timestamp(max_ratio) >= YEAR_2026_TS:
        raise TapeIntegrityError("LSR rows at or after 2026-01-01 survived the filter")
    return {
        "panel": panel,
        "membership": membership,
        "ratios": ratios,
        "funding": funding,
        "status": status,
        "btc": btc,
        "report": report,
        "paths": {key: str(value) for key, value in paths.items()},
    }
