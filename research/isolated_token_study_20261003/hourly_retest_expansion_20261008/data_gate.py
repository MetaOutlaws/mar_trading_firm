"""Outcome-blind acquisition audit for H-RETEST-EXPANSION-01.

This module validates the collector contract and prepares a read-only 2022-2025
cache.  It never calculates signals, trades, or returns, and it refuses any
minute candle at or beyond the reserved 2026 boundary.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path, PurePosixPath

import numpy as np
import pandas as pd


BEGIN = pd.Timestamp("2022-01-01", tz="UTC")
END = pd.Timestamp("2026-01-01", tz="UTC")
REFERENCE = {"BTCUSDT", "ETHUSDT", "SOLUSDT"}
REQUIRED_CONTROL = {
    "STATUS.json",
    "FILES_SHA256.json",
    "catalog.json",
    "membership.json",
    "universe_freeze.json",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True, default=str))


def safe_relative(name: str) -> Path:
    pure = PurePosixPath(name)
    if pure.is_absolute() or not pure.parts or ".." in pure.parts:
        raise ValueError(f"unsafe manifest path: {name!r}")
    return Path(*pure.parts)


def read_json(path: Path) -> object:
    return json.loads(path.read_text())


def verify_collector_manifest(source: Path) -> tuple[dict[str, str], dict]:
    missing = sorted(name for name in REQUIRED_CONTROL if not (source / name).is_file())
    if missing:
        raise ValueError(f"collector layout missing: {missing}")
    status = read_json(source / "STATUS.json")
    if not isinstance(status, dict) or status.get("status") not in {
        "acquired_needs_audit",
        "partial_needs_audit",
    }:
        raise ValueError(f"collector status is not auditable: {status!r}")
    if status.get("scores_2026") is not False:
        raise ValueError("collector status does not preserve the closed 2026 outcome flag")
    expected = read_json(source / "FILES_SHA256.json")
    if not isinstance(expected, dict) or not expected:
        raise ValueError("FILES_SHA256.json must be a non-empty object")
    verified: dict[str, str] = {}
    for name, wanted in sorted(expected.items()):
        if not isinstance(name, str) or not isinstance(wanted, str) or len(wanted) != 64:
            raise ValueError("invalid FILES_SHA256.json entry")
        relative = safe_relative(name)
        path = source / relative
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"missing or unsafe collector file: {name}")
        actual = sha256(path)
        if actual != wanted:
            raise ValueError(f"collector hash mismatch: {name}")
        verified[relative.as_posix()] = actual
    freeze = read_json(source / "universe_freeze.json")
    if not isinstance(freeze, dict):
        raise ValueError("universe_freeze.json must be an object")
    for name, key in [("membership.json", "membership_sha256"), ("catalog.json", "catalog_sha256")]:
        if freeze.get(key) != sha256(source / name):
            raise ValueError(f"universe freeze mismatch: {name}")
    if freeze.get("historical_universe_complete") is not False:
        raise ValueError("historical-universe provenance may not be upgraded by this audit")
    if freeze.get("classification_history_verified") is not False:
        raise ValueError("classification provenance may not be upgraded by this audit")
    return verified, freeze


def validate_membership(source: Path, freeze: dict) -> tuple[list[dict], list[str]]:
    rows = read_json(source / "membership.json")
    if not isinstance(rows, list) or not rows:
        raise ValueError("membership.json must contain selected new-token rows")
    seen_pairs: set[tuple[str, str]] = set()
    seen_ranks: set[tuple[str, int]] = set()
    symbols: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("membership row must be an object")
        month = str(row.get("month", ""))
        symbol = str(row.get("symbol", ""))
        rank = row.get("rank")
        if len(month) != 7 or month >= "2026-01":
            raise ValueError(f"invalid or outcome-reserved membership month: {month!r}")
        if not symbol.isascii() or not symbol.endswith("USDT") or not symbol.replace("_", "").isalnum():
            raise ValueError(f"invalid membership symbol: {symbol!r}")
        if symbol in REFERENCE:
            raise ValueError("reference assets must not appear in primary new-token membership")
        if isinstance(rank, bool) or not isinstance(rank, int) or not 1 <= rank <= 15:
            raise ValueError(f"invalid selected rank for {symbol} {month}")
        pair = (month, symbol)
        ranked = (month, rank)
        if pair in seen_pairs or ranked in seen_ranks:
            raise ValueError("duplicate membership symbol or rank within month")
        seen_pairs.add(pair)
        seen_ranks.add(ranked)
        symbols.add(symbol)
    frozen_union = sorted(freeze.get("selected_union", []))
    if frozen_union != sorted(symbols):
        raise ValueError("membership union differs from universe_freeze.json")
    return rows, sorted(symbols)


def read_csv_frame(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    if "timestamp_ms" not in frame:
        raise ValueError(f"timestamp_ms missing: {path}")
    frame.index = pd.DatetimeIndex(
        pd.to_datetime(frame.pop("timestamp_ms"), unit="ms", utc=True), name="timestamp"
    )
    return frame.sort_index()


def expected_bounds(item: dict) -> tuple[pd.Timestamp, pd.Timestamp]:
    launch_ms = int(item.get("launchTime") or 0)
    launch = pd.Timestamp(launch_ms, unit="ms", tz="UTC").ceil("min")
    begin = max(BEGIN, launch)
    delivery_ms = int(item.get("deliveryTime") or 0)
    delivery = pd.Timestamp(delivery_ms, unit="ms", tz="UTC") if delivery_ms else END
    return begin, min(END, delivery)


def audit_symbol(source: Path, out: Path, symbol: str, item: dict, observed_hours: bool = False) -> tuple[dict, dict[str, str]]:
    pages = sorted((source / "minutes" / symbol).glob("*.csv.gz"))
    if not pages:
        raise ValueError(f"missing minute history: {symbol}")
    candles = pd.concat([read_csv_frame(path) for path in pages]).sort_index()
    required_columns = ["open", "high", "low", "close", "volume", "turnover"]
    if list(candles.columns) != required_columns:
        raise ValueError(f"unexpected candle schema: {symbol}")
    if not candles.index.is_unique or candles.index.tz is None or str(candles.index.tz) != "UTC":
        raise ValueError(f"invalid minute index: {symbol}")
    if not np.isfinite(candles[required_columns].to_numpy()).all():
        raise ValueError(f"non-finite candle value: {symbol}")
    if (candles[["open", "high", "low", "close"]] <= 0).any().any():
        raise ValueError(f"non-positive candle price: {symbol}")
    if (candles[["volume", "turnover"]] < 0).any().any():
        raise ValueError(f"negative volume/turnover: {symbol}")
    if (
        (candles.high < candles[["open", "low", "close"]].max(axis=1))
        | (candles.low > candles[["open", "high", "close"]].min(axis=1))
    ).any():
        raise ValueError(f"inconsistent OHLC: {symbol}")
    begin, end = expected_bounds(item)
    wanted = pd.date_range(begin, end, freq="min", inclusive="left")
    missing = wanted.difference(candles.index)
    extra = candles.index.difference(wanted)
    original_missing = len(missing)
    trimmed_leading = trimmed_trailing = 0
    if observed_hours:
        if candles.empty or len(extra):
            raise ValueError(f"empty or out-of-catalog observed history: {symbol}")
        inside = pd.date_range(candles.index.min(), candles.index.max(), freq="min")
        if len(inside.difference(candles.index)):
            raise ValueError(f"interior minute gap may not be trimmed: {symbol}")
        begin = candles.index.min().ceil("h")
        end = (candles.index.max() + pd.Timedelta(minutes=1)).floor("h")
        trimmed_leading = int((candles.index < begin).sum())
        trimmed_trailing = int((candles.index >= end).sum())
        candles = candles[(candles.index >= begin) & (candles.index < end)].copy()
        wanted = pd.date_range(begin, end, freq="min", inclusive="left")
        missing = wanted.difference(candles.index)
        extra = candles.index.difference(wanted)
        if candles.empty:
            raise ValueError(f"no complete observed hours: {symbol}")
    if len(missing) or len(extra):
        raise ValueError(
            f"minute coverage mismatch {symbol}: missing={len(missing)} extra={len(extra)}"
        )
    if len(candles) and candles.index.max() >= END:
        raise ValueError(f"reserved 2026 candle found in scoring cache: {symbol}")

    funding_path = source / "funding" / f"{symbol}.csv.gz"
    if not funding_path.is_file():
        raise ValueError(f"missing funding history: {symbol}")
    funding = read_csv_frame(funding_path)
    if list(funding.columns) != ["funding_rate"]:
        raise ValueError(f"unexpected funding schema: {symbol}")
    if not funding.index.is_unique or not np.isfinite(funding.funding_rate).all():
        raise ValueError(f"invalid funding history: {symbol}")
    terminal_funding_minutes_trimmed = 0
    if observed_hours and len(funding):
        # Stop before the next unverified settlement; never invent a zero rate.
        funded_end = (funding.index.max() + pd.Timedelta(hours=8)).floor("h")
        if funded_end < end:
            terminal_funding_minutes_trimmed = int((candles.index >= funded_end).sum())
            candles = candles[candles.index < funded_end].copy()
            end = funded_end
            if candles.empty:
                raise ValueError(f"no observed hours within funding coverage: {symbol}")
    if len(funding) < 2 or funding.index.min() > begin + pd.Timedelta(hours=8):
        raise ValueError(f"funding starts too late: {symbol}")
    if funding.index.max() < end - pd.Timedelta(hours=8) or funding.index.max() > END:
        raise ValueError(f"funding does not end at the allowed boundary: {symbol}")
    max_gap = funding.index.to_series().diff().max()
    if max_gap > pd.Timedelta(hours=8):
        raise ValueError(f"funding gap over 8 hours: {symbol} {max_gap}")

    candle_out = out / f"{symbol}_1m.parquet"
    funding_out = out / "funding" / f"{symbol}_funding.parquet"
    candles.to_parquet(candle_out, compression="zstd")
    funding.to_parquet(funding_out, compression="zstd")
    hashes = {
        candle_out.relative_to(out).as_posix(): sha256(candle_out),
        funding_out.relative_to(out).as_posix(): sha256(funding_out),
    }
    coverage = {
        "symbol": symbol,
        "candles": len(candles),
        "first_minute": str(candles.index.min()),
        "last_minute": str(candles.index.max()),
        "missing_minutes": 0,
        "catalog_boundary_missing_minutes": original_missing,
        "leading_partial_minutes_trimmed": trimmed_leading,
        "trailing_partial_minutes_trimmed": trimmed_trailing,
        "terminal_funding_minutes_trimmed": terminal_funding_minutes_trimmed,
        "boundary_policy": "complete_observed_hours_amendment_20261009" if observed_hours else "strict_catalog",
        "funding_events": len(funding),
        "max_funding_gap_hours": max_gap.total_seconds() / 3600,
        "scores_2026": False,
    }
    return coverage, hashes


def run(source: Path, out: Path, observed_hours: bool = False) -> None:
    source = source.resolve()
    if not source.is_dir():
        raise ValueError(f"collector directory is not accessible: {source}")
    out.mkdir(parents=True, exist_ok=False)
    (out / "funding").mkdir()
    try:
        collector_hashes, freeze = verify_collector_manifest(source)
        membership, new_symbols = validate_membership(source, freeze)
        catalog = read_json(source / "catalog.json")
        if not isinstance(catalog, dict) or not isinstance(catalog.get("instruments"), list):
            raise ValueError("invalid catalog.json")
        records = {str(row.get("symbol")): row for row in catalog["instruments"]}
        symbols = sorted(set(new_symbols) | REFERENCE)
        absent = sorted(symbol for symbol in symbols if symbol not in records)
        if absent:
            raise ValueError(f"selected/reference symbols absent from catalog: {absent}")
        coverage: list[dict] = []
        output_hashes: dict[str, str] = {}
        for symbol in symbols:
            row, hashes = audit_symbol(source, out, symbol, records[symbol], observed_hours)
            coverage.append(row)
            output_hashes.update(hashes)
            print("AUDITED", symbol, flush=True)
        shutil.copy2(source / "membership.json", out / "membership.json")
        shutil.copy2(source / "catalog.json", out / "catalog.json")
        output_hashes["membership.json"] = sha256(out / "membership.json")
        output_hashes["catalog.json"] = sha256(out / "catalog.json")
        result = {
            "status": "usable_provisional",
            "experiment_id": "H-RETEST-EXPANSION-01",
            "coverage": coverage,
            "selected_new_tokens": len(new_symbols),
            "new_token_symbols": new_symbols,
            "collector_file_hashes": collector_hashes,
            "output_hashes": output_hashes,
            "membership_rows": len(membership),
            "historical_universe_complete": False,
            "historical_funding_schedule_verified": False,
            "classification_history_verified": False,
            "scores_2026": False,
            "outcomes_scored": False,
            "boundary_policy": "complete_observed_hours_amendment_20261009" if observed_hours else "strict_catalog",
            "note": "Execution coverage passed; independent universe/funding/classification provenance remains provisional.",
        }
        write_json(out / "audit.json", result)
    except Exception as exc:
        write_json(
            out / "audit.json",
            {
                "status": "blocked",
                "experiment_id": "H-RETEST-EXPANSION-01",
                "error": repr(exc),
                "scores_2026": False,
                "outcomes_scored": False,
            },
        )
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--observed-hours", action="store_true", help="Apply published data-only observed-hour boundary amendment; reject every interior gap.")
    args = parser.parse_args()
    run(args.input, args.out, args.observed_hours)
