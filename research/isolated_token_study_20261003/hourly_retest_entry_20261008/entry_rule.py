"""One preregistered retest/reclaim rule; no outcomes or parameter search."""
import numpy as np

WAIT_MINUTES = 60

def select_entry(high, low, close, signal_i, end, side, boundary):
    if side not in (-1, 1) or not np.isfinite(boundary) or boundary <= 0:
        raise ValueError('invalid direction or boundary')
    if not 0 <= signal_i < end <= min(len(high), len(low), len(close)):
        raise ValueError('invalid bounds')
    ix = np.arange(signal_i, min(signal_i + WAIT_MINUTES, end))
    touched = low[ix] <= boundary if side == 1 else high[ix] >= boundary
    reclaimed = close[ix] > boundary if side == 1 else close[ix] < boundary
    hits = np.flatnonzero(np.maximum.accumulate(touched) & reclaimed)
    touch = int(ix[np.flatnonzero(touched)[0]]) if touched.any() else -1
    confirm = int(ix[hits[0]]) if len(hits) else -1
    fill = confirm + 1 if confirm >= 0 and confirm + 1 < end else -1
    status = ('filled' if fill >= 0 else 'endpoint_censored' if end <= signal_i + WAIT_MINUTES
              else 'retest_no_reclaim' if touch >= 0 else 'no_retest')
    return dict(planned_entry_i=fill, touch_i=touch, confirm_i=confirm,
                entry_status=status, delay_minutes=fill-signal_i if fill >= 0 else -1)

def sequential_entry(high, low, close, signal_i, end, side, boundary):
    """Independent state-machine check; does not call the vector selector."""
    touch = confirm = fill = -1
    for k in range(signal_i, min(signal_i + 60, end)):
        hit = low[k] <= boundary if side == 1 else high[k] >= boundary
        if touch < 0 and hit:
            touch = k
        recover = close[k] > boundary if side == 1 else close[k] < boundary
        if touch >= 0 and recover:
            confirm = k
            if k + 1 < end:
                fill = k + 1
            break
    status = ('filled' if fill >= 0 else 'endpoint_censored' if end <= signal_i + 60
              else 'retest_no_reclaim' if touch >= 0 else 'no_retest')
    return dict(planned_entry_i=fill, touch_i=touch, confirm_i=confirm,
                entry_status=status, delay_minutes=fill-signal_i if fill >= 0 else -1)
