#!/usr/bin/env python3
"""Run the 3R clone screen and print JSON.

Entry timestamps are the feature comparison. Weekly P&L rho is computed only
for 2022-01-01..2025-12-31 and is printed as SEEN. Rho above 0.50 is FAIL and
is not evidence for the edge. Bars on or after 2026-01-01 UTC raise.

With no mounted archive the command prints UNAVAILABLE for every comparator
and does not invent a score. Pass a directory of JSON lists to score a fixture:

  candidate_entries.json, candidate_trades.json
  <comparator>_entries.json, <comparator>_trades.json
  optional bars.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.cipher_forward.clone_screen import run_default, score_archive


def main(argv: list[str]) -> int:
    if len(argv) > 1:
        report = score_archive(Path(argv[1]))
        report['status'] = 'SCORED'
    else:
        report = run_default()
    json.dump(report, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write('\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
