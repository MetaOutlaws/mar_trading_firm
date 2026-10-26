"""SEEN week counts for BTC 4h, 2022 through 2025.

The label is research.cipher_forward.regime.label_week_cluster. EMA50 and
EMA200 are the standard recursive form, pandas ewm(span, adjust=False), on
the 4h close. A week uses the last 4h bar whose close is at or before that
Monday 00:00 UTC. A bar that closes exactly at the Monday counts. A close
after 2025-12-31 23:00:00 UTC is not used. EMA200 is unlabelled until 200
closed 4h bars exist. Loss is not evaluated. This is not evidence.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from .regime import label_week_cluster
from .tape import FOUR_HOUR_MS, HARD_END, HARD_END_MS, WINDOW_START, assert_bar_timestamp

WARMUP_BARS = 200


def monday_opens() -> list[datetime]:
    """Monday 00:00 UTC opens from the first Monday of 2022 through 2025."""
    moment = datetime(2022, 1, 3, tzinfo=timezone.utc)
    if moment < WINDOW_START:
        raise RuntimeError('first Monday is outside the window')
    last = datetime(2025, 12, 29, tzinfo=timezone.utc)
    opens = []
    while moment <= last and moment <= HARD_END:
        opens.append(moment)
        moment += timedelta(days=7)
    return opens


def _closes(frame) -> list[tuple[int, float]]:
    """(close_ms, close) for bars whose open is inside the window.

    The close is open + 4h. A close after the hard end is left out, which
    drops the 4h bar that opens 2025-12-31 20:00 UTC.
    """
    pairs = []
    for open_ms, price in zip(frame['open_time_ms'], frame['close']):
        stamp = int(open_ms)
        assert_bar_timestamp(stamp)
        if stamp % FOUR_HOUR_MS:
            raise ValueError(f'4h bar {stamp} is not aligned')
        close_ms = stamp + FOUR_HOUR_MS
        if close_ms > HARD_END_MS:
            continue
        pairs.append((close_ms, float(price)))
    pairs.sort()
    return pairs


def count_regimes(frame) -> dict:
    """Count BULL, BEAR, CHOP, and unlabelled Mondays. Does not score loss."""
    import pandas as pd
    closes = _closes(frame)
    mondays = monday_opens()
    if closes:
        series = pd.Series(
            [price for _stamp, price in closes],
            index=pd.Index([stamp for stamp, _price in closes]),
            dtype='float64',
        )
        ema50 = series.ewm(span=50, adjust=False).mean()
        ema200 = series.ewm(span=200, adjust=False).mean()
        index = list(series.index)
    else:
        ema50 = ema200 = None
        index = []
    counts = {'BULL': 0, 'BEAR': 0, 'CHOP': 0, 'UNLABELLED': 0}
    for monday in mondays:
        as_of = int(monday.timestamp() * 1000)
        pos = -1
        for cursor, stamp in enumerate(index):
            if stamp <= as_of:
                pos = cursor
            else:
                break
        if ema50 is None or pos < WARMUP_BARS - 1:
            counts['UNLABELLED'] += 1
            continue
        label = label_week_cluster(monday, float(ema50.iloc[pos]), float(ema200.iloc[pos]))
        counts[label] += 1
    return dict(
        label='SEEN',
        role='planning_context_only',
        not_evidence=True,
        not_for_promotion=True,
        loss_evaluated=False,
        symbol='BTCUSDT',
        timeframe='4h',
        ema='pandas ewm span 50 and span 200, adjust=False, on the 4h close',
        as_of=(
            'Monday 00:00 UTC. The last 4h close at or before that open is used. '
            'A close after 2025-12-31 23:00:00 UTC is excluded.'
        ),
        warmup_closed_4h_bars=WARMUP_BARS,
        window_start='2022-01-01T00:00:00Z',
        window_end='2025-12-31T23:00:00Z',
        monday_count=len(mondays),
        counts=counts,
        no_2026_bars_read=True,
        classifier='research.cipher_forward.regime.label_week_cluster',
    )
