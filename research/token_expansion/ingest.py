"""Build token_expansion_c1_results.json from the sealed C1 phase directories.

Fails closed: a SHA256SUMS mismatch exits before any results file is written.
The phase directories are ``main``, ``holdout``, and ``exploratory``. The
exploratory phase is the 2026 window. Every written verdict is PENDING.
This script does not infer a verdict from profit factor, and it does not
touch the approval book or the trading engine.

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


def _sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        digest.update(handle.read())
    return digest.hexdigest()


def build_results(outputs_root: str = OUTPUTS_ROOT) -> dict:
    """Read the three sealed phases and return the C1 results document.

    Raises SystemExit on any manifest or member mismatch. No partial document
    is returned in that case.
    """
    rows: dict[tuple, dict] = {}
    for phase, expected in PHASE_SEALS.items():
        directory = os.path.join(outputs_root, phase)
        manifest = os.path.join(directory, "SHA256SUMS")
        if _sha256(manifest) != expected:
            sys.exit(f"FAIL CLOSED: {phase} manifest mismatch")
        with open(manifest, encoding="utf-8") as handle:
            for line in handle:
                digest, name = line.split(None, 1)
                name = name.strip().lstrip("*")
                member = os.path.join(directory, name)
                if _sha256(member) != digest:
                    sys.exit(f"FAIL CLOSED: {phase}/{name} mismatch")
        summaries = [name for name in os.listdir(directory) if name.startswith("summary")]
        with open(os.path.join(directory, summaries[0]), encoding="utf-8", newline="") as handle:
            for record in csv.DictReader(handle):
                if record["cost_bar"] != "official_0.31":
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
                        "seal_sha": {phase_name: PHASE_SEALS[phase_name] for phase_name in PHASE_SEALS},
                    },
                )
                raw_pf = record["pf"]
                if raw_pf not in ("", "inf", "nan"):
                    row[f"pf_{phase}"] = float(raw_pf)
                else:
                    row[f"pf_{phase}"] = raw_pf
                row[f"trades_{phase}"] = int(record["trades"])
    ordered = sorted(rows.values(), key=lambda row: (row["rule"], row["side"], row["token"]))
    return {
        "batch": "C1",
        "cost_view": "official_0.31",
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
