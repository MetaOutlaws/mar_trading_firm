"""Persist one growing minute-aggregated indicator history per instrument.

Missing minutes invalidate their hour. They are never filled with later data.
The seed boundary is immutable; a restart appends to it, never rolls it.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import numpy as np

from .strategy import HOUR, MINUTE, validate_history


def atomic_json(path, value):
    path = Path(path)
    tmp = path.with_suffix('.tmp')
    with tmp.open('w') as f:
        json.dump(value, f, sort_keys=True, allow_nan=False, indent=2)
        f.write('\n'); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)
    sync_directory(path.parent)


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)


def aggregate(rows, start, end):
    """Exchange rows are open-labelled; return complete close-labelled hours."""
    if start % HOUR or end % HOUR or end <= start:
        raise ValueError('invalid aggregation boundary')
    values = {}
    for row in rows:
        t = int(row[0])
        if not start <= t < end or t % MINUTE or t in values:
            raise ValueError('duplicate, future or unaligned minute')
        v = np.asarray(row[1:7], dtype=float)
        if (len(v) != 6 or not np.isfinite(v).all() or (v[:4] <= 0).any()
                or (v[4:] < 0).any() or v[1] < max(v[0], v[2], v[3])
                or v[2] > min(v[0], v[1], v[3])):
            raise ValueError('invalid minute OHLCV/turnover')
        values[t] = v
    out = np.full(((end-start)//HOUR, 6), np.nan)
    for i, hour in enumerate(range(start, end, HOUR)):
        keys = range(hour, hour+HOUR, MINUTE)
        if not all(t in values for t in keys):
            continue
        a = np.asarray([values[t] for t in keys])
        out[i] = [a[0, 0], a[:, 1].max(), a[:, 2].min(), a[-1, 3],
                  a[:, 4].sum(), a[:, 5].sum()]
    return out


class SeedStore:
    def __init__(self, root, universe, *, initialize_asof=None):
        self.root = Path(root)
        self.manifest_path = self.root/'manifest.json'
        if initialize_asof is not None and not self.manifest_path.exists():
            self.root.mkdir(parents=True, exist_ok=True)
            if any(self.root.iterdir()):
                raise ValueError('unrecognized seed directory; do not reset')
            end = int(initialize_asof)//HOUR*HOUR
            start = end//(4*HOUR)*(4*HOUR)-804*HOUR
            atomic_json(self.manifest_path, dict(version=1, universe=list(universe),
                seed_start_ms=start, initial_asof_ms=end,
                basis='60 distinct completed public minute candles per hour; actual quote turnover'))
        self.manifest = json.loads(self.manifest_path.read_text())
        if self.manifest['version'] != 1 or self.manifest['universe'] != list(universe):
            raise ValueError('seed universe/schema changed')
        self.start = self.manifest['seed_start_ms']
        if type(self.start) is not int or self.start % (4*HOUR):
            raise ValueError('invalid fixed seed boundary')

    def path(self, symbol):
        if symbol not in self.manifest['universe']:
            raise ValueError('symbol outside frozen universe')
        return self.root/(symbol+'.npz')

    def read(self, symbol):
        path = self.path(symbol)
        if not path.exists():
            return np.full((1, 6), np.nan), self.start
        with np.load(path, allow_pickle=False) as f:
            a, start, end = f['bars'], int(f['start']), int(f['end'])
        if start != self.start:
            raise ValueError('seed start changed')
        return validate_history(a, start, end), end

    def advance(self, symbol, asof, get):
        a, end = self.read(symbol)
        if asof < end or asof % HOUR:
            raise ValueError('seed cannot move backwards or include partial hour')
        # 16 hours = 960 minutes < the exchange page maximum. Checkpoint each
        # page so an interrupted initial warmup resumes the identical seed.
        while end < asof:
            nxt = min(end+16*HOUR, asof)
            result = get('kline', symbol=symbol, interval='1', start=end,
                         end=nxt-1, limit=1000)['result']
            if result.get('symbol') != symbol or result.get('category') != 'linear':
                raise ValueError('wrong-symbol minute history')
            part = aggregate(result['list'], end, nxt)
            a = np.concatenate((a, part))
            validate_history(a, self.start, nxt)
            path = self.path(symbol); tmp = path.with_suffix('.tmp')
            with tmp.open('wb') as f:
                np.savez_compressed(f, bars=a, start=self.start, end=nxt)
                f.flush(); os.fsync(f.fileno())
            os.replace(tmp, path); sync_directory(self.root)
            end = nxt
        return a

    def receipt(self):
        files = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in sorted(self.root.glob('*.npz'))}
        return dict(manifest=self.manifest, files_sha256=files,
            manifest_sha256=hashlib.sha256(self.manifest_path.read_bytes()).hexdigest())
