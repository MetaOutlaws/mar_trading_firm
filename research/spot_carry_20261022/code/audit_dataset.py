#!/usr/bin/env python3
"""Independent audit of the unpacked 2022–2025 carry archive.

Reads monthly spot, perpetual, mark and funding files. Does not compute a
strategy return, a holding-period P&L, or any entry/exit result. Prints a
JSON object on stdout.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

MINUTE = 60_000
HOUR8 = 8 * 60 * 60 * 1000
BEGIN = 1640995200000  # 2022-01-01
END = 1767225600000  # 2026-01-01 exclusive
SYMBOLS = ("BTCUSDT", "ETHUSDT")
STREAMS = ("spot", "perpetual", "mark")


def month_labels():
    year, month = 2022, 1
    while (year, month) <= (2025, 12):
        yield f"{year:04d}-{month:02d}"
        month += 1
        if month == 13:
            year, month = year + 1, 1


def month_bounds(label: str):
    dt = datetime.strptime(label, "%Y-%m").replace(tzinfo=timezone.utc)
    if dt.month == 12:
        nxt = datetime(dt.year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        nxt = datetime(dt.year, dt.month + 1, 1, tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000), int(nxt.timestamp() * 1000)


def load_ohlc(path: Path, mark: bool):
    times = []
    ohlc = []
    vol_neg = 0
    bad_ohlc = 0
    nonfinite = 0
    with gzip.open(path, "rt", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        if tuple(header) != (
            "timestamp_ms",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "turnover",
        ):
            raise ValueError(f"header {header} in {path}")
        for row in reader:
            t = int(row[0])
            o, h, l, c = (float(row[1]), float(row[2]), float(row[3]), float(row[4]))
            if not all(math.isfinite(v) and v > 0 for v in (o, h, l, c)):
                nonfinite += 1
            elif l > min(o, c) or h < max(o, c) or h < l:
                bad_ohlc += 1
            if not mark:
                volume, turnover = float(row[5]), float(row[6])
                if not (math.isfinite(volume) and math.isfinite(turnover) and volume >= 0 and turnover >= 0):
                    vol_neg += 1
            else:
                if row[5] != "" or row[6] != "":
                    vol_neg += 1
            times.append(t)
            ohlc.append((o, h, l, c))
    return times, ohlc, {"nonfinite_or_nonpositive": nonfinite, "bad_ohlc": bad_ohlc, "bad_volume": vol_neg}


def load_funding(path: Path):
    times = []
    rates = []
    bad = 0
    with gzip.open(path, "rt", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        if header != ["timestamp_ms", "funding_rate"]:
            raise ValueError(f"funding header {header}")
        for row in reader:
            t = int(row[0])
            rate = float(row[1])
            if not math.isfinite(rate):
                bad += 1
            times.append(t)
            rates.append(rate)
    return times, rates, bad


def summarise_times(times, lo, hi):
    dup = 0
    backwards = 0
    unaligned = 0
    outside = 0
    seen = set()
    prev = None
    for t in times:
        if t in seen:
            dup += 1
        seen.add(t)
        if prev is not None and t < prev:
            backwards += 1
        prev = t
        if t % MINUTE:
            unaligned += 1
        if t < lo or t >= hi:
            outside += 1
    gaps = 0
    if times:
        # Missing minutes inside the month span, not filled.
        expected = (hi - lo) // MINUTE
        gaps = expected - len(seen)
    return {
        "rows": len(times),
        "unique": len(seen),
        "duplicates": dup,
        "backwards": backwards,
        "unaligned": unaligned,
        "outside_month_or_window": outside,
        "missing_minutes": gaps,
        "first": times[0] if times else None,
        "last": times[-1] if times else None,
    }


def basis_update(acc, spot_c, perp_c, mark_c):
    b_ps = (perp_c - spot_c) / spot_c
    b_ms = (mark_c - spot_c) / spot_c
    b_mp = (mark_c - perp_c) / perp_c
    acc["n"] += 1
    for key, value in (("perp_spot", b_ps), ("mark_spot", b_ms), ("mark_perp", b_mp)):
        a = acc[key]
        a["sum"] += value
        a["min"] = value if a["min"] is None else min(a["min"], value)
        a["max"] = value if a["max"] is None else max(a["max"], value)
        if abs(value) > 0.01:
            a["abs_gt_1pct"] += 1
        if abs(value) > 0.02:
            a["abs_gt_2pct"] += 1
        if a["prev"] is not None and abs(value - a["prev"]) > 0.005:
            a["jumps_gt_50bp"] += 1
            a["max_jump"] = max(a["max_jump"], abs(value - a["prev"]))
        a["prev"] = value
    if spot_c == perp_c:
        acc["spot_eq_perp"] += 1


def new_basis():
    def blank():
        return {"sum": 0.0, "min": None, "max": None, "abs_gt_1pct": 0, "abs_gt_2pct": 0, "jumps_gt_50bp": 0, "max_jump": 0.0, "prev": None}

    return {"n": 0, "spot_eq_perp": 0, "perp_spot": blank(), "mark_spot": blank(), "mark_perp": blank()}


def finish_basis(acc):
    out = {"minutes": acc["n"], "spot_close_equals_perp_close": acc["spot_eq_perp"]}
    for key in ("perp_spot", "mark_spot", "mark_perp"):
        a = acc[key]
        out[key] = {
            "mean": (a["sum"] / acc["n"]) if acc["n"] else None,
            "min": a["min"],
            "max": a["max"],
            "abs_gt_1pct": a["abs_gt_1pct"],
            "abs_gt_2pct": a["abs_gt_2pct"],
            "one_minute_jumps_gt_50bp": a["jumps_gt_50bp"],
            "max_one_minute_jump": a["max_jump"],
        }
    return out


def audit(root: Path):
    labels = list(month_labels())
    report = {
        "root": str(root),
        "window": ["2022-01-01T00:00:00+00:00", "2025-12-31T23:59:00+00:00"],
        "historical_2026_rows": 0,
        "streams": {},
        "funding": {},
        "basis": {},
        "sidecar_sha_mismatches": [],
        "issues": [],
    }
    for stream in STREAMS:
        for symbol in SYMBOLS:
            key = f"{stream}/{symbol}"
            total = summarise_times([], BEGIN, END)
            total.update({"bad_ohlc": 0, "nonfinite_or_nonpositive": 0, "bad_volume": 0, "months": 0, "incomplete_months": []})
            # reset counters that summarise_times computed on empty
            total["rows"] = 0
            total["unique"] = 0
            total["duplicates"] = 0
            total["backwards"] = 0
            total["unaligned"] = 0
            total["outside_month_or_window"] = 0
            total["missing_minutes"] = 0
            prev_last = None
            first = None
            last = None
            for label in labels:
                path = root / stream / symbol / f"{label}.csv.gz"
                meta = root / stream / symbol / f"{label}.json"
                if not path.is_file():
                    report["issues"].append(f"missing {path}")
                    continue
                lo, hi = month_bounds(label)
                times, ohlc, quality = load_ohlc(path, mark=(stream == "mark"))
                stats = summarise_times(times, lo, hi)
                total["months"] += 1
                total["rows"] += stats["rows"]
                total["duplicates"] += stats["duplicates"]
                total["backwards"] += stats["backwards"]
                total["unaligned"] += stats["unaligned"]
                total["outside_month_or_window"] += stats["outside_month_or_window"]
                total["missing_minutes"] += stats["missing_minutes"]
                total["bad_ohlc"] += quality["bad_ohlc"]
                total["nonfinite_or_nonpositive"] += quality["nonfinite_or_nonpositive"]
                total["bad_volume"] += quality["bad_volume"]
                for t in times:
                    if t >= END or t < BEGIN:
                        report["historical_2026_rows"] += 1
                if stats["missing_minutes"] or stats["duplicates"] or stats["backwards"]:
                    total["incomplete_months"].append(label)
                if times:
                    if first is None:
                        first = times[0]
                    last = times[-1]
                    if prev_last is not None and times[0] != prev_last + MINUTE:
                        report["issues"].append(f"boundary gap {key} {label}: {prev_last} -> {times[0]}")
                    prev_last = times[-1]
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                if meta.is_file():
                    side = json.loads(meta.read_text())
                    if side.get("sha256") != digest:
                        report["sidecar_sha_mismatches"].append(str(path))
                    if side.get("symbol") != symbol or side.get("stream") != stream or side.get("month") != label:
                        report["issues"].append(f"sidecar identity {path}")
            total["first"] = first
            total["last"] = last
            total["expected_minutes"] = (END - BEGIN) // MINUTE
            report["streams"][key] = total

    for symbol in SYMBOLS:
        all_t = []
        all_r = []
        bad_rates = 0
        months = 0
        grid_breaks = []
        per_month = {}
        for label in labels:
            path = root / "funding" / symbol / f"{label}.csv.gz"
            meta = root / "funding" / symbol / f"{label}.json"
            lo, hi = month_bounds(label)
            times, rates, bad = load_funding(path)
            bad_rates += bad
            months += 1
            per_month[label] = len(times)
            expected = list(range(lo, hi, HOUR8))
            if times != expected:
                grid_breaks.append(label)
            for t in times:
                if t >= END or t < BEGIN:
                    report["historical_2026_rows"] += 1
            all_t.extend(times)
            all_r.extend(rates)
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            side = json.loads(meta.read_text())
            if side.get("sha256") != digest:
                report["sidecar_sha_mismatches"].append(str(path))
        intervals = [b - a for a, b in zip(all_t, all_t[1:])]
        on_clock = sum(1 for t in all_t if t % HOUR8 == BEGIN % HOUR8)
        report["funding"][symbol] = {
            "months": months,
            "settlements": len(all_t),
            "duplicates": len(all_t) - len(set(all_t)),
            "bad_rates": bad_rates,
            "first": all_t[0] if all_t else None,
            "last": all_t[-1] if all_t else None,
            "min_interval_ms": min(intervals) if intervals else None,
            "max_interval_ms": max(intervals) if intervals else None,
            "months_not_exact_8h_grid": grid_breaks,
            "on_utc_8h_clock": on_clock,
            "per_month_min": min(per_month.values()) if per_month else None,
            "per_month_max": max(per_month.values()) if per_month else None,
            "rate_min": min(all_r) if all_r else None,
            "rate_max": max(all_r) if all_r else None,
            "rate_positive": sum(1 for r in all_r if r > 0),
            "rate_negative": sum(1 for r in all_r if r < 0),
            "rate_zero": sum(1 for r in all_r if r == 0),
        }

    # Basis on the common minute grid. Streams are already complete or the
    # issues list says they are not; still align on timestamp rather than
    # assuming equal length.
    for symbol in SYMBOLS:
        acc = new_basis()
        mark_join_missing = 0
        for label in labels:
            loaded = {}
            for stream in STREAMS:
                times, ohlc, _quality = load_ohlc(
                    root / stream / symbol / f"{label}.csv.gz", mark=(stream == "mark")
                )
                loaded[stream] = {t: ohlc[i][3] for i, t in enumerate(times)}
                if stream == "mark":
                    loaded["mark_open"] = {t: ohlc[i][0] for i, t in enumerate(times)}
            funding_times, _rates, _bad = load_funding(root / "funding" / symbol / f"{label}.csv.gz")
            for t in funding_times:
                if t not in loaded["mark_open"]:
                    mark_join_missing += 1
            common = set(loaded["spot"]) & set(loaded["perpetual"]) & set(loaded["mark"])
            for t in sorted(common):
                basis_update(acc, loaded["spot"][t], loaded["perpetual"][t], loaded["mark"][t])
        finished = finish_basis(acc)
        finished["funding_minutes_missing_mark_open"] = mark_join_missing
        report["basis"][symbol] = finished
    return report


def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "downloads")
    print(json.dumps(audit(root), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
