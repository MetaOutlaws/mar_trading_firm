"""Fixed RSI gate and fixed causal state, with all four policies declared."""
import sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT/'hourly_rsi_filter_20261008'))
from rsi_rule import gate

POLICIES = ('none', 'always', 'directional', 'loweff')


def policy_pass(rsi, side, efficiency, policy):
    er = np.asarray(efficiency, float)
    if not np.isfinite(er).all() or not ((er >= 0) & (er <= 1 + 1e-12)).all():
        raise ValueError('Finite prior efficiency in [0,1] required')
    passes = gate(rsi, side)
    directional = er >= .30
    if policy == 'none':
        return np.ones(np.broadcast_shapes(er.shape, passes.shape), dtype=bool)
    if policy == 'always':
        return passes
    if policy == 'directional':
        return ~directional | passes
    if policy == 'loweff':
        return directional | passes
    raise ValueError(policy)
