"""Build token_expansion_c1_results.json from the sealed C1 phase directories.

Fails closed: a SHA256SUMS mismatch exits before any results file is written.
Win rate is computed only after those manifest checks, from the sealed
per-token trade lists. This script does not replay candles and does not
import the research engine.

The phase directories are ``main``, ``holdout``, and ``exploratory``. The
exploratory phase is the 2026 window. The phase is the directory, not a
column in the trade file. Every written verdict is PENDING. Profit factor
is not a verdict.

Official-cost trade lists live at::

    {phase}/trades/{rule}_{side}_{clock}_{token}_official_0.31.csv

The cost bar is the filename suffix, not a column. Columns ingest reads:

- ``net_pnl`` — a win is ``net_pnl > 0``.
- ``return_pct`` — present on the real file. Not used to decide a win.
- ``symbol`` — must match the token in the filename.
- ``segment`` — ``fold`` or ``tail``. Both count. This is not the phase.

Win rate is wins / N. It is null when N is 0. N must match the summary
``trades`` count. When the summary has a ``win_rate`` cell, the computed
rate must match it.

Expected layout::

    /workspace/research/token_expansion_c1/outputs/{main,holdout,exploratory}/SHA256SUMS
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import sys

# Sealed manifest for each phase directory. exploratory is the 2026 window.
PHASE_SEALS = {
    "main": "16ead71273c6a6c5608887564c7631b37685869a3f06416e6cc454f305296729",
    "holdout": "04bbc365edaaf8f1c3532b21dc8b7782ca6dafdaa118bf4f18665b6bc33773d6",
    "exploratory": "c232e61481f273c544e583eadc267fabc0319d59146b11d331e91dbd923250f8",
}
OUTPUTS_ROOT = "/workspace/research/token_expansion_c1/outputs"
RESULTS_NAME = "token_expansion_c1_results.json"
OFFICIAL_COST = "official_0.31"

# Real sealed trade-list columns. The cost bar is in the filename.
TRADE_NET_PNL_COLUMN = "net_pnl"
TRADE_RETURN_PCT_COLUMN = "return_pct"
TRADE_SYMBOL_COLUMN = "symbol"
TRADE_SEGMENT_COLUMN = "segment"
TRADE_LIST_COLUMNS = (
    TRADE_NET_PNL_COLUMN,
    TRADE_RETURN_PCT_COLUMN,
    TRADE_SYMBOL_COLUMN,
    TRADE_SEGMENT_COLUMN,
)
TRADE_SEGMENTS = frozenset({"fold", "tail"})
TRADE_SIDES = frozenset({"LONG", "SHORT"})
SUMMARY_WIN_RATE_COLUMN = "win_rate"
# Summary win_rate is a fraction. A 1e-6 gap is still the same rate.
WIN_RATE_ABS_TOL = 1e-6
WINRATE_FIELD = {
    "main": "winrate_main",
    "holdout": "winrate_holdout",
    "exploratory": "winrate_2026",
}


def _sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        digest.update(handle.read())
    return digest.hexdigest()


def _fail(message: str) -> None:
    """Stop before a partial results file can be returned."""
    sys.exit(f"FAIL CLOSED: {message}")


def compute_win_rate(net_pnls: list[float]) -> float | None:
    """Wins / N, where a win is net_pnl strictly greater than zero.

    Null when N is 0. Does not look at profit factor or return_pct.
    """
    count = len(net_pnls)
    if count == 0:
        return None
    wins = sum(1 for value in net_pnls if value > 0)
    return wins / count


def _official_trade_names(manifest_names: list[str]) -> list[str]:
    """Manifest members under trades/ whose filename carries the official cost."""
    suffix = f"_{OFFICIAL_COST}.csv"
    found: list[str] = []
    for name in manifest_names:
        rel = name.replace("\\", "/").strip()
        if os.path.dirname(rel) != "trades":
            continue
        if os.path.basename(rel).endswith(suffix):
            found.append(rel)
    return found


def _identity_from_trade_name(name: str) -> tuple[str, str, str, str]:
    """Parse rule, side, clock, token from ``..._{cost}.csv``.

    The rule may contain underscores, so the last three fields are side,
    clock, and token.
    """
    base = os.path.basename(name)
    suffix = f"_{OFFICIAL_COST}.csv"
    if not base.endswith(suffix):
        _fail(f"{name} is not an {OFFICIAL_COST} trade list")
    parts = base[: -len(suffix)].rsplit("_", 3)
    if len(parts) != 4:
        _fail(f"{name} is not rule_side_clock_token_{OFFICIAL_COST}.csv")
    rule, side, clock, token = parts
    if side not in TRADE_SIDES or not rule or not clock or not token:
        _fail(f"{name} is not rule_side_clock_token_{OFFICIAL_COST}.csv")
    return rule, side, clock, token


def _load_trade_pnls(directory: str, names: list[str], phase: str) -> dict[tuple, list[float]]:
    """Official-cost net_pnl values keyed by (rule, side, clock, token)."""
    grouped: dict[tuple, list[float]] = {}
    owners: dict[tuple, str] = {}
    for name in names:
        rule, side, clock, token = _identity_from_trade_name(name)
        key = (rule, side, clock, token)
        if key in owners:
            _fail(f"{phase} has two official trade files for {rule} {token}")
        owners[key] = name
        grouped[key] = []
        path = os.path.join(directory, name)
        with open(path, encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            header = reader.fieldnames or []
            missing = [column for column in TRADE_LIST_COLUMNS if column not in header]
            if missing:
                _fail(
                    f"{phase}/{name} missing columns {', '.join(missing)}; "
                    f"header is {', '.join(header)}"
                )
            for record in reader:
                segment = (record[TRADE_SEGMENT_COLUMN] or "").strip().lower()
                if segment not in TRADE_SEGMENTS:
                    _fail(f"{phase}/{name} segment {record[TRADE_SEGMENT_COLUMN]!r} is not fold or tail")
                symbol = (record[TRADE_SYMBOL_COLUMN] or "").strip()
                if symbol != token:
                    _fail(f"{phase}/{name} symbol {symbol!r} != {token}")
                raw_pnl = (record[TRADE_NET_PNL_COLUMN] or "").strip()
                try:
                    net_pnl = float(raw_pnl)
                except ValueError:
                    _fail(f"{phase}/{name} has a non-numeric {TRADE_NET_PNL_COLUMN}")
                if not math.isfinite(net_pnl):
                    _fail(f"{phase}/{name} has a non-numeric {TRADE_NET_PNL_COLUMN}")
                grouped[key].append(net_pnl)
    return grouped


def _summary_win_rate(record: dict[str, str], phase: str, token: str) -> float | None:
    """Fraction from the summary, or None when that cell is absent."""
    if SUMMARY_WIN_RATE_COLUMN not in record:
        return None
    raw = (record.get(SUMMARY_WIN_RATE_COLUMN) or "").strip()
    if raw == "" or raw.lower() in {"nan", "none", "null"}:
        return None
    try:
        value = float(raw)
    except ValueError:
        _fail(f"{phase} summary win_rate for {token} is not a fraction")
    if not math.isfinite(value) or value < 0 or value > 1:
        _fail(f"{phase} summary win_rate for {token} is not a fraction")
    return value


def _rates_match(computed: float | None, expected: float) -> bool:
    if computed is None:
        return False
    return math.isclose(computed, expected, rel_tol=0.0, abs_tol=WIN_RATE_ABS_TOL)


def _attach_win_rates(
    rows: dict[tuple, dict],
    directory: str,
    manifest_names: list[str],
    phase: str,
    expected_rates: dict[tuple, float],
) -> None:
    """Fill this phase's win rate from the trade lists. Mismatches fail closed."""
    names = _official_trade_names(manifest_names)
    grouped = _load_trade_pnls(directory, names, phase)
    field = WINRATE_FIELD[phase]
    seen: set[tuple] = set()
    for key, row in rows.items():
        count = row.get(f"trades_{phase}")
        if count is None:
            continue
        pnls = grouped.get(key, [])
        if len(pnls) != int(count):
            _fail(
                f"{phase} trade-list N {len(pnls)} != summary trades {count} "
                f"for {key[0]} {key[3]}"
            )
        rate = compute_win_rate(pnls)
        expected = expected_rates.get(key)
        if expected is not None and not _rates_match(rate, expected):
            _fail(
                f"{phase} win rate {rate} != summary win_rate {expected} "
                f"for {key[0]} {key[3]}"
            )
        row[field] = rate
        seen.add(key)
    extra = [key for key in grouped if key not in seen]
    if extra:
        rule, _side, _clock, token = extra[0]
        _fail(f"{phase} trade list has {rule} {token} which is not in the summary")


def build_results(
    outputs_root: str = OUTPUTS_ROOT,
    seals: dict[str, str] | None = None,
) -> dict:
    """Read the three sealed phases and return the C1 results document.

    Raises SystemExit on any manifest, member, or trade-list mismatch.
    No partial document is returned in that case. ``seals`` overrides the
    committed phase hashes for tests only.
    """
    expected_seals = seals if seals is not None else PHASE_SEALS
    rows: dict[tuple, dict] = {}
    for phase in PHASE_SEALS:
        expected = expected_seals[phase]
        directory = os.path.join(outputs_root, phase)
        manifest_path = os.path.join(directory, "SHA256SUMS")
        if _sha256(manifest_path) != expected:
            _fail(f"{phase} manifest mismatch")
        manifest_names: list[str] = []
        with open(manifest_path, encoding="utf-8") as handle:
            for line in handle:
                digest, name = line.split(None, 1)
                name = name.strip().lstrip("*")
                manifest_names.append(name)
                member = os.path.join(directory, name)
                if _sha256(member) != digest:
                    _fail(f"{phase}/{name} mismatch")
        summaries = [name for name in os.listdir(directory) if name.startswith("summary")]
        expected_rates: dict[tuple, float] = {}
        with open(os.path.join(directory, summaries[0]), encoding="utf-8", newline="") as handle:
            for record in csv.DictReader(handle):
                if record["cost_bar"] != OFFICIAL_COST:
                    continue
                rule, _unused, side, clock = record["row"].split(":")
                key = (rule, side, clock, record["token"])
                row = rows.setdefault(
                    key,
                    {
                        "batch": "C1",
                        "rule": rule,
                        "side": side,
                        "clock": clock,
                        "token": record["token"],
                        # Verdicts are not scored here. A later file may overlay them.
                        "verdict": "PENDING",
                        "seal_sha": {
                            phase_name: PHASE_SEALS[phase_name] for phase_name in PHASE_SEALS
                        },
                    },
                )
                raw_pf = record["pf"]
                if raw_pf not in ("", "inf", "nan"):
                    row[f"pf_{phase}"] = float(raw_pf)
                else:
                    row[f"pf_{phase}"] = raw_pf
                row[f"trades_{phase}"] = int(record["trades"])
                summary_rate = _summary_win_rate(record, phase, record["token"])
                if summary_rate is not None:
                    expected_rates[key] = summary_rate
        # Manifest is already verified. Win rate reads the sealed lists only.
        _attach_win_rates(rows, directory, manifest_names, phase, expected_rates)
    ordered = sorted(rows.values(), key=lambda row: (row["rule"], row["side"], row["token"]))
    return {
        "batch": "C1",
        "cost_view": OFFICIAL_COST,
        "verdict_source": None,
        "rows": ordered,
    }


def main() -> None:
    document = build_results()
    with open(RESULTS_NAME, "w", encoding="utf-8") as handle:
        json.dump(document, handle, indent=1)
    print(len(document["rows"]))


if __name__ == "__main__":
    main()
