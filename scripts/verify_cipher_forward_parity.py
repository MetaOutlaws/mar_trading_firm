#!/usr/bin/env python3
"""Compare the port with retained 2022-25 private fixtures; no network calls.

Fixtures remain outside Git. This verifies candidate features, target, old-2R
eligibility, fixed filter and prefix causality, NOT a running portfolio engine.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from research.cipher_forward.config import assert_no_promotion_clause
from research.cipher_forward.features import compute
from research.cipher_forward.strategy import (
    COSTS, HOUR, MIN_TURNOVER, MAX_STRUCTURAL_STOP_PERCENT,
    decision, fill_gate, from_feature, validate_history,
)

START = 1640995200000
END = 1767225600000


def sha(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def verify(features, signals_path, paths_path, late_path):
    saved = pd.read_parquet(signals_path)
    paths = pd.read_parquet(paths_path)
    late = pd.read_parquet(late_path)
    protocol = json.loads((ROOT / 'docs/cipher-forward/protocol.json').read_text())
    assert_no_promotion_clause(protocol)
    universe = protocol['universe']
    assert set(saved.symbol) <= set(universe)
    assert set(paths.symbol) <= set(universe)
    assert set(late.symbol) <= set(universe)
    max_hour = (END-START)//HOUR
    for df in [saved, paths, late]:
        assert df.hour.ge(0).all() and df.hour.le(max_hour).all()
    checked = dict(symbols=0, raw_signals=0, short_confluence_signals=0,
                   original_2R_fill_decisions=0, retained_3R_paths=0,
                   prefix_checks=0, failures=0)
    hashes = {}
    boolcols = ['side', 'ready', 'flow', 'trend', 'price', 'context_hour']
    floats = ['w1', 'w2', 'cmf', 'pressure', 'close', 'stop', 'target', 'atr',
              'efficiency', 'volatility', 'turnover']
    for n, symbol in enumerate(universe):
        path = features / f'{symbol}.npz'
        hashes[symbol] = sha(path)
        with np.load(path) as z:
            a = z['bars']
        assert len(a) == max_hour+1, 'Unexpected history bounds; refuse new dates'
        validate_history(a, START, END)
        f = compute(a)
        actual = f[f.side.ne(0)].reset_index(drop=True)
        expected = saved[saved.symbol.eq(symbol)].sort_values('hour').reset_index(drop=True)
        np.testing.assert_array_equal(actual.hour, expected.hour)
        np.testing.assert_array_equal(actual[boolcols], expected[boolcols])
        # Same arithmetic port: retained candidate features must match exactly.
        np.testing.assert_allclose(actual[floats], expected[floats], rtol=0, atol=0, equal_nan=True)
        short = f[f.side.eq(-1) & f.flow & f.trend]
        checked['raw_signals'] += len(actual)
        checked['short_confluence_signals'] += len(short)
        # All UTC four-hour boundary phases, for every retained token.
        for hour in [800, 801, 802, 803]:
            prefix = compute(a[:hour+1]).iloc[-1]
            np.testing.assert_allclose(prefix[floats].astype(float),
                                       f.iloc[hour][floats].astype(float), rtol=0, atol=0,
                                       equal_nan=True)
            np.testing.assert_array_equal(prefix[boolcols], f.iloc[hour][boolcols])
            checked['prefix_checks'] += 1
        if len(short):
            # Also exercise the public forward wrapper at real signal prefixes.
            hour = int(short.iloc[0].hour)
            got = decision(symbol, a[:hour+1], START, START+hour*HOUR)
            assert got == from_feature(symbol, f.iloc[hour], START)
            assert got['context_ms'] < got['signal_ms']
            checked['prefix_checks'] += 1
        rows = paths[paths.symbol.eq(symbol) & paths.side.eq(-1)]
        candidates = {int(h): from_feature(symbol, f.iloc[int(h)], START) for h in rows.hour.unique()}
        for row in rows.itertuples():
            signal = candidates[int(row.hour)]
            slip, stop_slip = COSTS[row.cost]
            v = fill_gate(signal, float(row.entry_price), market_slip=slip,
                          total_stop_slip=stop_slip)
            assert v['eligible'] == bool(row.eligible and row.flow and row.trend)
            for key, old in [('price_risk_unit', row.price_risk_unit),
                             ('planned_loss_unit', row.planned_loss_unit),
                             ('planned_gain_unit', row.planned_gain_unit),
                             ('original_planned_rr', row.planned_rr)]:
                # JSON-safe null is the port's equivalent of research NaN
                # when nonpositive planned loss makes a ratio undefined.
                actual_value = np.nan if v[key] is None else v[key]
                np.testing.assert_allclose(actual_value, old, rtol=1e-12, atol=1e-15)
            checked['original_2R_fill_decisions'] += 1
        for row in late[late.symbol.eq(symbol) & late.target_rule.eq('T30')].itertuples():
            signal = from_feature(symbol, f.iloc[int(row.hour)], START)
            assert signal['eligible_signal']
            np.testing.assert_allclose([signal['target'], signal['stop'], signal['original_target'],
                                       signal['structural_stop_pct']],
                                      [row.target, row.stop, row.original_target, row.structural_stop_pct],
                                      rtol=1e-12, atol=1e-15)
            assert signal['filter_pass'] == bool(row.turnover >= MIN_TURNOVER and
                                                 row.structural_stop_pct <= MAX_STRUCTURAL_STOP_PERCENT)
            checked['retained_3R_paths'] += 1
        checked['symbols'] += 1
        if (n+1) % 8 == 0:
            print(f"Verified {n+1}/{len(universe)} symbols", flush=True)
    assert checked['raw_signals'] == len(saved)
    assert checked['retained_3R_paths'] == int(late.target_rule.eq('T30').sum())
    return dict(passed=True, scope='candidate port and allocation contract, not deployed execution',
                counts=checked, historical_2026_opened=False, paper_trial_started=False,
                inputs={'signals_sha256': sha(signals_path), 'paths_sha256': sha(paths_path),
                        'late_paths_sha256': sha(late_path), 'feature_hashes': hashes},
                protocol_sha256=sha(ROOT / 'docs/cipher-forward/protocol.json'),
                source_sha256={p: sha(ROOT/p) for p in [
                    'research/cipher_forward/features.py', 'research/cipher_forward/strategy.py',
                    'research/cipher_forward/allocation.py', 'scripts/verify_cipher_forward_parity.py']})


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--features', type=Path, required=True)
    p.add_argument('--signals', type=Path, required=True)
    p.add_argument('--paths', type=Path, required=True)
    p.add_argument('--late-paths', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    result = verify(a.features, a.signals, a.paths, a.late_paths)
    with a.output.open('x') as f:
        json.dump(result, f, indent=2, allow_nan=False); f.write('\n')
    print(json.dumps(result['counts'], indent=2))


if __name__ == '__main__':
    main()
