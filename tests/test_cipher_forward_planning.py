"""Planning formulas and a synthetic desk031 book. No market tape."""
from datetime import datetime, timezone

import pandas as pd
import pytest

from research.cipher_forward.families import screen_inputs
from research.cipher_forward.planning import (
    N, Z_ALPHA, Z_BETA, lock_verdict, mde, norm_cdf, power_at, run_default,
    simulate, summarise,
)
from research.cipher_forward.tape import HOUR_MS, FOUR_HOUR_MS


def _ms(year, month, day, hour=0):
    return int(datetime(year, month, day, hour, tzinfo=timezone.utc).timestamp() * 1000)


def test_mde_power_and_the_two_times_breakeven_rule():
    assert norm_cdf(Z_ALPHA) == pytest.approx(0.95)
    assert norm_cdf(Z_BETA) == pytest.approx(0.80)
    sd = 10.0
    detectable = mde(sd)
    assert detectable == pytest.approx((Z_ALPHA + Z_BETA) * sd / N ** 0.5)
    assert mde(sd, scale=2.0) == pytest.approx(2 * detectable)
    assert power_at(detectable, sd) == pytest.approx(0.80)
    assert power_at(detectable, 2 * sd) < 0.80

    under = summarise(
        [1.0, 1.0], [1.0, 1.0], [1.0, 1.0],
        c3_stop_notional=0.0, c3_stop_exits=0, mean_equity=20_000.0)
    assert under['effect_multiple_of_breakeven'] == pytest.approx(1.0)
    assert under['verdict'] == 'REJECT'
    assert under['rules_tuned'] is False
    assert under['not_for_promotion'] is True
    assert under['label'] == 'SEEN'

    exact = summarise(
        [1.0, 3.0], [2.0, 2.0], [1.0, 1.0],
        c3_stop_notional=0.0, c3_stop_exits=0, mean_equity=20_000.0)
    assert exact['effect_multiple_of_breakeven'] == pytest.approx(2.0)
    assert exact['verdict'] == 'NOT_REJECT'
    assert lock_verdict(1.999999) == 'REJECT'


def test_unset_tape_is_not_a_reject(monkeypatch):
    monkeypatch.delenv('CIPHER_FORWARD_TAPE_DIR', raising=False)
    report = run_default()
    assert report['status'] == 'NOT_STAGED'
    assert report['verdict'] == 'NOT_STAGED'
    assert report['effect_multiple_of_breakeven'] is None
    assert report['ran_on_real_bars'] is False
    assert report['no_2026_bars_read'] is True


def _flat(start, step, count):
    rows = []
    for index in range(count):
        stamp = start + index * step
        rows.append(dict(
            open_time_ms=stamp, open=100.0, high=101.0, low=99.0, close=100.0,
            volume=1.0, turnover=1.0,
        ))
    return pd.DataFrame(rows)


def test_family_modules_accept_a_short_synthetic_tape_without_scoring_a_pass():
    start = _ms(2024, 1, 1)
    hours = _flat(start, HOUR_MS, 32)
    four = _flat(start, FOUR_HOUR_MS, 8)
    tape = {'BTCUSDT': {'1h': hours, '4h': four}}
    prepared = screen_inputs(tape)
    assert prepared['candidate_entries'] == []
    for block in prepared['comparators'].values():
        assert block['entries'] == []
        assert block['spec']['path'].endswith('.py')


def test_injected_c3_stop_is_counted_and_labelled_seen():
    start = _ms(2024, 1, 1)
    later = _ms(2024, 1, 9)
    frame = pd.DataFrame([
        dict(open_time_ms=start, open=100.0, high=110.0, low=90.0, close=100.0,
             volume=1.0, turnover=1.0),
        dict(open_time_ms=later, open=100.0, high=100.0, low=100.0, close=100.0,
             volume=1.0, turnover=1.0),
    ])
    tape = {'BTCUSDT': {'1h': frame}}
    intent = dict(
        symbol='BTCUSDT', source='C3', kind='pct', side=-1, entry_ms=start,
        stop_pct=0.02, target_pct=0.06, uid='C3|BTCUSDT|test',
    )
    report = simulate(tape, [intent], sector_of=lambda _symbol: 'other')
    assert report['status'] == 'SIMULATED'
    assert report['c3_stop_exits'] == 1
    assert report['stop_churn_turnover'] > 0
    assert report['cost_drag_per_week'] > 0
    assert report['breakeven_gross_per_week'] == pytest.approx(report['cost_drag_per_week'])
    assert report['verdict'] in ('REJECT', 'NOT_REJECT')
    assert report['scored_as_promotion'] is False
    assert report['funding'] == 'omitted_not_on_tape'
