#!/usr/bin/env python3
"""Fetch the pre-2026 Bybit 1h/4h tape into CIPHER_FORWARD_TAPE_DIR.

Public /v5/market/kline only. category=linear, intervals 60 and 240,
limit 1000, no auth. Start is 2022-01-01 00:00:00 UTC. End is never after
2025-12-31 23:00:00 UTC. This does not call BybitOHLCV.fetch.

A 403, geo block, or CloudFront body stops the process. It does not use a
proxy or a mirror. The bars are written under the tape directory and are
not for commit. Pass --manifest to write the row-count manifest.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research.cipher_forward.fetch_tape import (  # noqa: E402
    BybitBlocked,
    FetchFailed,
    fetch_tape,
    manifest_document,
)
from research.cipher_forward.tape import TAPE_ENV  # noqa: E402


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--out',
        default=os.environ.get(TAPE_ENV, 'data/cipher_forward_tape'),
        help='Tape directory. Layout is {1h,4h}/<SYMBOL>.parquet.',
    )
    parser.add_argument(
        '--manifest',
        default='',
        help='Write the committed manifest JSON here after a complete pull.',
    )
    args = parser.parse_args(argv[1:])
    out = Path(args.out)
    try:
        manifest = fetch_tape(out)
    except BybitBlocked as exc:
        sys.stderr.write(f'BYBIT_BLOCKED {exc}\n')
        return 2
    except FetchFailed as exc:
        sys.stderr.write(f'FETCH_FAILED {exc}\n')
        return 1
    document = manifest_document(manifest)
    text = json.dumps(document, indent=2, sort_keys=True) + '\n'
    if args.manifest:
        target = Path(args.manifest)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
    sys.stdout.write(text)
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
