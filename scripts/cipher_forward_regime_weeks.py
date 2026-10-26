#!/usr/bin/env python3
"""Count SEEN BTC 4h BULL/BEAR/CHOP weeks on the staged tape.

Reads BTCUSDT 4h from CIPHER_FORWARD_TAPE_DIR. Does not fetch. Does not
read a 2026 bar. Loss is not evaluated. The count is not evidence.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.cipher_forward.regime_weeks import count_regimes  # noqa: E402
from research.cipher_forward.tape import TapeNotStaged, load_tape, tape_dir  # noqa: E402


def main() -> int:
    root = tape_dir()
    if root is None or not root.is_dir():
        json.dump({
            'label': 'SEEN',
            'status': 'NOT_STAGED',
            'no_2026_bars_read': True,
            'loss_evaluated': False,
        }, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write('\n')
        return 0
    try:
        tape = load_tape(root)
    except TapeNotStaged as exc:
        json.dump({
            'label': 'SEEN',
            'status': 'NOT_STAGED',
            'reason': str(exc),
            'no_2026_bars_read': True,
            'loss_evaluated': False,
        }, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write('\n')
        return 0
    report = count_regimes(tape['BTCUSDT']['4h'])
    report['status'] = 'COUNTED'
    json.dump(report, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write('\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
