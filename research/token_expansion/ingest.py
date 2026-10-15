"""Build token_expansion_c1_results.json from the sealed C1 phase directories.

Fails closed: a SHA256SUMS mismatch exits before any results file is written.
Win rate is computed only after those manifest checks, from the sealed
per-token trade lists. This script does not replay candles and does not
import the research engine.

The phase directories are ``main``, ``holdout``, and ``exploratory``. The
exploratory phase is the 2026 window. Every written verdict is PENDING.
Profit factor is not a verdict.

Trade-list contract (one CSV per phase, name contains ``trade`` and is not
the summary). Columns ingest reads:

- ``net_return`` — net return of one trade. A win is ``net_return > 0``.
- ``segment`` — ``main``, ``holdout``, or ``exploratory`` (``2026`` is also
  accepted for the exploratory directory).
- ``cost_bar`` — only ``official_0.31`` rows count.
- ``token`` — symbol.
- ``row`` — ``rule:<ignored>:side:clock``, same identity as the summary.

Win rate is wins / N. It is null when N is 0. N must match the summary
``trades`` count for that rule, side, clock, and token.

Expected layout::

    /workspace/research/token_expansion_c1/outputs/{main,holdout,exploratory}/SHA256SUMS
"""

from __future__ import annotations

import csv
import hashlib
import json
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

# Column names on the per-token trade list. Reported so a box regenerate
# reads the same cells this script reads.
TRADE_NET_RETURN_COLUMN = "net_return"
TRADE_SEGMENT_COLUMN = "segment"
TRADE_COST_COLUMN = "cost_bar"
TRADE_TOKEN_COLUMN = "token"
TRADE_ROW_COLUMN = "row"
TRADE_LIST_COLUMNS = (
    TRADE_NET_RETURN_COLUMN,
    TRADE_SEGMENT_COLUMN,
    TRADE_COST_COLUMN,
    TRADE_TOKEN_COLUMN,
    TRADE_ROW_COLUMN,
)
WINRATE_FIELD = {
    "main": "winrate_main",
    "holdout": "winrate_holdout",
    "exploratory": "winrate_2026",
}
# segment values that belong in each phase directory.
SEGMENT_VALUES = {
    "main": {"main"},
    "holdout": {"holdout"},
    "exploratory": {"exploratory", "2026"},
}


def _sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        digest.update(handle.read())
    return digest.hexdigest()


def _fail(message: str) -> None:
    """Stop before a partial results file can be returned."""
    sys.exit(f"FAIL CLOSED: {message}")


def compute_win_rate(net_returns: list[float]) -> float | None:
    """Wins / N, where a win is net return strictly greater than zero.

    Null when N is 0. Does not look at profit factor.
    """
    count = len(net_returns)
    if count == 0:
        return None
    wins = sum(1 for value in net_returns if value > 0)
    return wins / count


def _trade_lists(directory: str, manifest_names: list[str]) -> list[str]:
    """Manifest members that are per-token trade lists, not the summary."""
    found: list[str] = []
    for name in manifest_names:
        base = os.path.basename(name).lower()
        if not base.endswith(".csv"):
            continue
        if base.startswith("summary"):
            continue
        if "trade" not in base:
            continue
        found.append(name)
    if not found:
        _fail(f"no per-token trade list in {directory}")
    return found


def _load_trade_returns(directory: str, names: list[str], phase: str) -> dict[tuple, list[float]]:
    """Official-cost net returns keyed by (rule, side, clock, token)."""
    grouped: dict[tuple, list[float]] = {}
    allowed_segments = SEGMENT_VALUES[phase]
    for name in names:
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
                if record[TRADE_COST_COLUMN] != OFFICIAL_COST:
                    continue
                segment = (record[TRADE_SEGMENT_COLUMN] or "").strip().lower()
                if segment not in allowed_segments:
                    _fail(f"{phase}/{name} segment {record[TRADE_SEGMENT_COLUMN]!r} is not {phase}")
                raw_return = (record[TRADE_NET_RETURN_COLUMN] or "").strip()
                try:
                    net_return = float(raw_return)
                except ValueError:
                    _fail(f"{phase}/{name} has a non-numeric {TRADE_NET_RETURN_COLUMN}")
                try:
                    rule, _unused, side, clock = record[TRADE_ROW_COLUMN].split(":")
                except ValueError:
                    _fail(f"{phase}/{name} has a bad {TRADE_ROW_COLUMN}")
                token = (record[TRADE_TOKEN_COLUMN] or "").strip()
                if not (rule and side and clock and token):
                    _fail(f"{phase}/{name} has an empty trade identity")
                key = (rule, side, clock, token)
                grouped.setdefault(key, []).append(net_return)
    return grouped


def _attach_win_rates(rows: dict[tuple, dict], directory: str, manifest_names: list[str], phase: str) -> None:
    """Fill this phase's win rate from the trade list. Mismatched N fails closed."""
    lists = _trade_lists(directory, manifest_names)
    grouped = _load_trade_returns(directory, lists, phase)
    field = WINRATE_FIELD[phase]
    seen: set[tuple] = set()
    for key, row in rows.items():
        count = row.get(f"trades_{phase}")
        if count is None:
            continue
        returns = grouped.get(key, [])
        if len(returns) != int(count):
            _fail(
                f"{phase} trade-list N {len(returns)} != summary trades {count} "
                f"for {key[0]} {key[3]}"
            )
        row[field] = compute_win_rate(returns)
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
        # Manifest is already verified. Win rate reads the sealed lists only.
        _attach_win_rates(rows, directory, manifest_names, phase)
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
