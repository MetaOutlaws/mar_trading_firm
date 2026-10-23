#!/usr/bin/env python3
"""Read selected non-secret runtime settings; never start, reset or resize a book.

Run INSIDE the existing paper container to capture its mounted source. The
receipt is a configuration observation, not cash/fill/activation verification.
"""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import sys


def audit(root: Path):
    root = root.resolve()
    relative = ['core/risk/limits.py', 'core/strategy/f111_semantics.py',
                'core/strategy/l01_context.py', 'core/strategy/bl8.py',
                'core/execution/recovery_paper.py', 'core/execution/recovery_feed.py',
                'config/sleeves/mar_l01_long_f111_short_v1.json',
                'config/sleeves/mar_recovery_paper_v1.json', 'config/approved_strategies.json']
    hashes = {p: hashlib.sha256((root / p).read_bytes()).hexdigest()
              if (root / p).is_file() else None for p in relative}
    spec = importlib.util.spec_from_file_location('observed_paper_limits', root / relative[0])
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    stamps = {}
    for p in ['GIT_SHA', 'data/DEPLOYED_SHA', 'RECOVERY_RELEASE_SHA']:
        path = root / p
        if path.is_file():
            value = path.read_text().strip()
            # Never emit arbitrary file contents from a mislabeled stamp file.
            if len(value) == 40 and all(x in '0123456789abcdefABCDEF' for x in value):
                stamps[p] = value
    mode = os.environ.get('TRADING_MODE', 'UNSET')
    mode = mode if mode in ('paper', 'live', 'UNSET') else 'OTHER'
    return dict(schema=1, observed_at=datetime.now(timezone.utc).isoformat(),
                hostname=socket.gethostname(), root=str(root), trading_mode_env=mode,
                go_live_confirmation_present=bool(os.environ.get('GO_LIVE_CONFIRMED')),
                release_stamps=stamps, source_sha256=hashes,
                paper_limits_declaration=asdict(module.PAPER_LIMITS),
                entry_disable_flags={p: (root / 'data' / p).exists()
                    for p in ['f111_paper_scan_disabled', 'l01_paper_scan_disabled']},
                overrides_and_active_workers_verified=False,
                cash_positions_funding_verified=False, activation_verified=False,
                interpretation='Declaration and source audit only. Verify runtime overrides, '
                               'active strategies and worker receipts separately.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path.cwd())
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    value = json.dumps(audit(args.root), indent=2, allow_nan=False) + '\n'
    if args.output:
        with args.output.open('x') as handle:
            handle.write(value)
    else:
        print(value, end='')


if __name__ == '__main__':
    main()
