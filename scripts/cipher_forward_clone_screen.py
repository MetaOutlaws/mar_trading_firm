#!/usr/bin/env python3
"""Run the 3R clone screen and print JSON.

Weekly P&L rho is SEEN and is a disqualifier only. Rho above 0.50 is FAIL.
Any bar after 2025-12-31 23:00:00 UTC raises. The default reads
CIPHER_FORWARD_TAPE_DIR and does not fetch. An unset directory prints
NOT_STAGED. Pass a directory of JSON lists to score a fixture:

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
