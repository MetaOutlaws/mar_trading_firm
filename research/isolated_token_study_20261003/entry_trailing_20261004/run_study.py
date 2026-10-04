"""Offline runner for the frozen entry and trailing protocol.

Refuses to open the cache until --acknowledge-garwe-lock is passed.
That flag records that a parent reply has already logged the Garwe lock.
It is not a strategy parameter. This module does not score 2026 returns.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

# study.py lives in the parent package directory and is imported by name.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import study  # noqa: E402

from entry_trailing_20261004.budget import (  # noqa: E402
    ARCHIVE_SHA256, FILE_SHA256, LEDGER_COLUMNS, TOKENS,
)
from entry_trailing_20261004.execution import FundingBook  # noqa: E402
from entry_trailing_20261004.stage1 import run_stage1  # noqa: E402
from entry_trailing_20261004.stage2 import choose_frozen, research_entries  # noqa: E402
from entry_trailing_20261004.stage3 import PARTITIONS, run_stage3  # noqa: E402

WAITING_FOR_GARWE_LOCK = (
    'WAITING_FOR_GARWE_LOCK: scoring is blocked until a parent reply records '
    'the Garwe lock. Re-run with --acknowledge-garwe-lock only after that reply. '
    'The cache was not opened.\n'
)
SCORE_CUT = pd.Timestamp('2026-01-01', tz='UTC')


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description='Frozen BTC/ETH/SOL entry and trailing study')
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--acknowledge-garwe-lock', action='store_true')
    return parser.parse_args(argv)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_inputs(cache: Path):
    """Audit the full tape, check the six fingerprints, then drop 2026 prices."""
    tapes = {}
    funding = {}
    audits = {}
    for token in TOKENS:
        candle_path = cache / f'{token}_1m.parquet'
        funding_path = cache / 'funding' / f'{token}_funding.parquet'
        candle_hash = _sha256(candle_path)
        funding_hash = _sha256(funding_path)
        expected_c = FILE_SHA256[candle_path.name]
        expected_f = FILE_SHA256[funding_path.name]
        if candle_hash != expected_c or funding_hash != expected_f:
            raise ValueError(f'{token} fingerprint mismatch')
        candles = study.load(candle_path)
        fund = study.load(funding_path, True)
        audits[token] = {
            'audit': study.audit(candles, fund),
            'sha256': {candle_path.name: candle_hash, funding_path.name: funding_hash},
        }
        # Prices from 2026 are not entries, exits, labels, or features.
        sliced = candles.loc[(candles.index >= study.START) & (candles.index < SCORE_CUT)].copy()
        fund = fund.loc[fund.index <= SCORE_CUT].copy()
        tapes[token] = sliced
        funding[token] = fund
    return tapes, funding, audits


def _write_trades(frame: pd.DataFrame, path: Path, experiment_id: str) -> None:
    if frame is None or frame.empty:
        return
    keep = frame.drop(columns=['exit_i'], errors='ignore').copy()
    keep.insert(0, 'experiment_id', experiment_id)
    keep.to_csv(path, index=False)


def _ledger_from_stage2(rows: list[dict]) -> pd.DataFrame:
    """Outcome ledger for the output directory. The repo template stays blank."""
    out_rows = []
    for row in rows:
        item = {col: '' for col in LEDGER_COLUMNS}
        item.update({
            'experiment_id': row['experiment_id'],
            'stage': '2',
            'token': row['token'],
            'side': row['side'],
            'family': row['family'],
            'spec': row['spec'],
            'status': 'scored' if not row['passes_screen'] else 'passed_screen',
            'trades_discovery': row['trades_discovery'],
            'mean_discovery': row['mean_discovery'],
            'pf_discovery': row['pf_discovery'],
            'trades_validation': row['trades_validation'],
            'mean_validation': row['mean_validation'],
            'pf_validation': row['pf_validation'],
            'stress_mean_discovery': row['stress_mean_discovery'],
            'stress_mean_validation': row['stress_mean_validation'],
            'desk_mean_discovery': row['desk_mean_discovery'],
            'desk_mean_validation': row['desk_mean_validation'],
            'notes': row['notes'],
        })
        out_rows.append(item)
    return pd.DataFrame(out_rows)


def run(cache: Path, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=False)
    here = Path(__file__).resolve().parent
    manifest = {
        'status': 'auditing',
        'archive_sha256': ARCHIVE_SHA256,
        'garwe_lock_acknowledged': True,
        'scores_2026': False,
        'source_sha256': {
            name: _sha256(here / name)
            for name in ('EXECUTION_ADDENDUM.md', 'run_study.py', 'execution.py', 'stage2.py', 'stage3.py')
        },
    }
    tapes, funding, audits = load_inputs(cache)
    manifest['data'] = audits
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2, default=str))
    run_stage1(tapes, PARTITIONS, out)
    rows = []
    signals = {}
    frames = {}
    for token in TOKENS:
        result = research_entries(tapes[token], funding[token], token)
        rows.extend(result['rows'])
        signals[token] = result['signals']
        frames[token] = result['frames']
        print(f'stage2 {token}', flush=True)
    frozen = choose_frozen(rows)
    # Freeze file is written before any exit path is scored.
    (out / 'frozen_selection.json').write_text(json.dumps(frozen, indent=2))
    for token, by_id in frames.items():
        for experiment_id, parts in by_id.items():
            for partition, modes in parts.items():
                for mode, frame in modes.items():
                    _write_trades(
                        frame, out / f'{experiment_id}_{partition}_{mode}_trades.csv.gz', experiment_id,
                    )
    public = [{k: v for k, v in row.items() if not k.startswith('_')} for row in rows]
    pd.DataFrame(public).to_csv(out / 'stage2_summary.csv', index=False)
    _ledger_from_stage2(rows).to_csv(out / 'experiment_ledger.csv', index=False)
    books = {token: FundingBook(tapes[token], funding[token]) for token in TOKENS}
    run_stage3(tapes, books, {'frozen': frozen, 'signals': signals}, out)
    manifest['status'] = 'discovery_validation_complete'
    manifest['frozen_selection'] = frozen
    manifest['reserved_evaluation'] = 'not run'
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2, default=str))
    print('FROZEN', json.dumps(frozen), flush=True)


def main(argv=None) -> int:
    args = parse_args(argv)
    if not args.acknowledge_garwe_lock:
        sys.stderr.write(WAITING_FOR_GARWE_LOCK)
        return 2
    run(args.cache, args.out)
    return 0


if __name__ == '__main__':
    sys.exit(main())
