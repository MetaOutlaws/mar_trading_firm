"""SEEN BTC 4h week counts. Synthetic bars only. No 2026 close is used."""
from datetime import datetime, timezone

import pandas as pd
import pytest

from research.cipher_forward.regime_weeks import count_regimes, monday_opens
from research.cipher_forward.tape import FOUR_HOUR_MS, HARD_END_MS, BarsOnOrAfter2026


def _ms(year, month, day, hour=0):
    return int(datetime(year, month, day, hour, tzinfo=timezone.utc).timestamp() * 1000)


def _frame(start, count, prices):
    rows = []
    for index in range(count):
        price = prices[index]
        rows.append(dict(
            open_time_ms=start + index * FOUR_HOUR_MS,
            open=price, high=price + 1, low=max(price - 1, 0.1),
            close=price, volume=1.0, turnover=price,
        ))
    return pd.DataFrame(rows)


def test_constant_prices_are_chop_after_the_ema200_warmup():
    start = _ms(2024, 1, 1)
    report = count_regimes(_frame(start, 260, [100.0] * 260))
    assert report['label'] == 'SEEN'
    assert report['loss_evaluated'] is False
    assert report['not_for_promotion'] is True
    assert report['counts']['BULL'] == 0
    assert report['counts']['BEAR'] == 0
    assert report['counts']['CHOP'] >= 1
    assert report['counts']['UNLABELLED'] >= 1
    assert sum(report['counts'].values()) == len(monday_opens())


def test_a_close_after_the_cap_is_not_a_monday_input():
    # The 20:00 UTC bar closes at 2026-01-01 00:00, which is past the cap.
    open_ms = HARD_END_MS - 3 * 60 * 60 * 1000
    assert open_ms + FOUR_HOUR_MS > HARD_END_MS
    report = count_regimes(_frame(open_ms, 1, [100.0]))
    assert report['counts']['UNLABELLED'] == len(monday_opens())
    assert report['counts']['BULL'] == report['counts']['BEAR'] == report['counts']['CHOP'] == 0


def test_a_2026_open_raises_before_a_label():
    with pytest.raises(BarsOnOrAfter2026):
        count_regimes(_frame(_ms(2026, 1, 1), 1, [100.0]))
