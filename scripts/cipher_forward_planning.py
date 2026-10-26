#!/usr/bin/env python3
"""Print the SEEN desk031 IC and I planning report.

An unset CIPHER_FORWARD_TAPE_DIR prints NOT_STAGED. This command does not
fetch, and it does not treat the report as evidence or as a promotion input.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.cipher_forward.planning import run_default


def main() -> int:
    json.dump(run_default(), sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write('\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
