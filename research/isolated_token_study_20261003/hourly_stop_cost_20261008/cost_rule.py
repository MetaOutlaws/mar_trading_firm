"""Cost-only reconciliation; never resimulate or modify an exit path."""
import numpy as np

FEE = .00055
MODELS = ('research_all_exit_slip', 'runtime_stop_fill')
CHANGED = ('exit_price', 'gross_return', 'fees', 'net_return', 'slippage_drag', 'net_R')

def reconcile_cost(frame):
    out = frame.copy(deep=True)
    if not out.reason.isin(['stop', 'target', 'boundary_mtm']).all():
        raise ValueError('unknown exit reason')
    if not out.side.isin([-1, 1]).all():
        raise ValueError('invalid side')
    if not ((out.entry_price > 0) & (out.quote > 0) & (out.stop > 0)
            & out.slippage_per_side.between(0, .02, inclusive='left')).all():
        raise ValueError('invalid cost geometry')
    stop = out.reason == 'stop'
    out.loc[stop, 'exit_price'] = out.loc[stop, 'quote']
    ratio = out.loc[stop, 'exit_price'] / out.loc[stop, 'entry_price']
    out.loc[stop, 'gross_return'] = out.loc[stop, 'side'] * (ratio - 1)
    out.loc[stop, 'fees'] = FEE * (1 + ratio)
    out.loc[stop, 'net_return'] = (out.loc[stop, 'gross_return']
                                 - out.loc[stop, 'fees'] - out.loc[stop, 'funding'])
    out.loc[stop, 'slippage_drag'] = out.loc[stop, 'quoted_return'] - out.loc[stop, 'gross_return']
    out.loc[stop, 'net_R'] = out.loc[stop, 'net_return'] / out.loc[stop, 'stop']
    assert np.allclose(out.net_return, out.gross_return-out.fees-out.funding, atol=1e-12, rtol=0)
    return out
