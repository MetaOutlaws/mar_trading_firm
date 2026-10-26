import json
from pathlib import Path

import numpy as np
import pytest

from research.cipher_forward.allocation import membership, ordered_candidates, planned_notional
from research.cipher_forward.config import assert_no_promotion_clause, frozen_config
from research.cipher_forward.strategy import (
    HOUR, MINUTE, MIN_TURNOVER, MAX_STRUCTURAL_STOP_PERCENT,
    decision, fill_gate, from_feature, validate_history,
)


def feature(**changes):
    return dict(hour=805, ready=True, side=-1, flow=True, trend=True,
                stop=105., close=100., turnover=3e6, context_hour=804,
                w1=61., w2=62., cmf=.1) | changes


def test_target_extension_keeps_old_eligibility():
    s = from_feature('TEST', feature(), 0)
    assert s['target'] == 85 and s['original_target'] == 90
    assert fill_gate(s, 99.8)['eligible']
    # Extended 3R looks attractive, but the frozen 2R entry gate rejects it.
    assert (96. - 85.) / (105. - 96.) > 1.
    assert not fill_gate(s, 96.)['eligible']


def test_short_only_and_confluence():
    for change in [dict(side=1), dict(ready=False), dict(flow=False), dict(trend=False)]:
        assert not from_feature('TEST', feature(**change), 0)['eligible_signal']


def test_fixed_filter_inclusive_boundaries():
    stop = 100 * (1 + MAX_STRUCTURAL_STOP_PERCENT / 100)
    # Avoid manufacturing an exact decimal through a different float algebra.
    s = from_feature('TEST', feature(stop=stop, turnover=MIN_TURNOVER), 0)
    assert s['filter_pass'] == (s['structural_stop_pct'] <= MAX_STRUCTURAL_STOP_PERCENT)
    assert from_feature('TEST', feature(stop=104., turnover=MIN_TURNOVER), 0)['filter_pass']
    assert not from_feature('TEST', feature(stop=104., turnover=np.nextafter(MIN_TURNOVER, 0)), 0)['filter_pass']
    assert not from_feature('TEST', feature(stop=105.), 0)['filter_pass']


def test_signal_and_action_clock():
    s = from_feature('TEST', feature(), 0)
    assert s['signal_ms'] == 805 * HOUR
    assert s['context_ms'] < s['signal_ms']
    assert s['action_ms'] == s['signal_ms'] + MINUTE
    assert s['action_deadline_ms'] == s['action_ms'] + MINUTE


def test_history_rejects_future_missing_or_shifted_clock():
    a = np.array([[np.nan]*6, [100, 101, 99, 100, 1, 100]])
    validate_history(a, 0, HOUR)
    for seed, now in [(HOUR, 2*HOUR), (0, HOUR+1), (0, 2*HOUR), (0, 0)]:
        with pytest.raises(ValueError): validate_history(a, seed, now)


def test_history_requires_real_turnover_and_empty_seed():
    a = np.array([[np.nan]*6, [100, 101, 99, 100, 1, 100]])
    b = a.copy(); b[1, 5] = np.nan
    with pytest.raises(ValueError): validate_history(b, 0, HOUR)
    b = a.copy(); b[0] = b[1]
    with pytest.raises(ValueError): validate_history(b, 0, HOUR)
    b = a.copy(); b[1, 1] = 90
    with pytest.raises(ValueError): validate_history(b, 0, HOUR)


def test_missing_bar_does_not_create_a_signal():
    a = np.tile([100., 101., 99., 100., 1., 100.], (810, 1)); a[0] = np.nan
    a[-1] = np.nan
    s = decision('TEST', a, 0, 809*HOUR)
    assert not s['eligible_signal']
    json.dumps(s, allow_nan=False)


def test_warmup_and_future_prefix():
    a = np.tile([100., 101., 99., 100., 1., 100.], (810, 1)); a[0] = np.nan
    assert decision('TEST', a[:800], 0, 799*HOUR)['reason'] == 'warmup'
    before = decision('TEST', a, 0, 809*HOUR)
    assert not before['eligible_signal']
    with pytest.raises(ValueError): decision('TEST', a, 0, 808*HOUR)


@pytest.mark.parametrize('bad', [float('nan'), float('inf'), -1., True])
def test_bad_fill_fails(bad):
    with pytest.raises(ValueError): fill_gate(from_feature('TEST', feature(), 0), bad)


def test_half_size_scales_challenger_only():
    assert planned_notional('IM', 'C3', 20000, 0, .05) == 1000
    assert planned_notional('IM', 'H', 20000, 0, .05) == 2000
    assert planned_notional('IC', 'C3', 20000, 0, .05) == 2000
    assert planned_notional('IM', 'C3', 20000, 0, .2) == 500


def test_residual_headroom_not_scaled_twice():
    assert planned_notional('IM', 'C3', 20000, 9500, .05) == 500
    assert planned_notional('IM', 'C3', 20000, 11000, .05) == 0


def test_membership_and_restricted_opportunities_are_distinct():
    assert not membership('I', 'C3')
    assert not membership('IF', 'C3')
    assert membership('IF', 'C3', filter_pass=True)
    assert membership('IM', 'C3')
    assert planned_notional('IF', 'C3', 20000, 0, .05) == 0


def test_common_priority():
    rows = [dict(action_ms=1, source=s, symbol='X', uid=s) for s in ['C3', 'B', 'H']]
    assert [r['source'] for r in ordered_candidates(rows)] == ['H', 'B', 'C3']


def test_no_production_override_and_no_fake_start():
    p = json.loads((Path(__file__).resolve().parents[1] / 'docs/cipher-forward/protocol.json').read_text())
    assert p['status'] == 'prepared_not_activated'
    assert p['start_time_utc'] is None
    assert p['accounts']['gross_admission'] == .5
    assert p['accounts']['drawdown_entry_latch'] == .15
    assert p['accounts']['daily_closed_loss_fraction'] == .03
    assert p['accounts']['nonpositive_close_streak'] == 6
    assert p['accounts']['risk_incumbent'] == .01
    assert p['accounts']['position_incumbent'] == .1
    assert p['books']['IM']['challenger_risk'] == .005
    assert p['books']['IM']['challenger_position'] == .05
    assert p['books']['IC']['challenger_risk'] == .01
    assert p['books']['IC']['challenger_position'] == .1
    assert not p['accounts']['historical_70_percent_guard_copied']
    assert not p['production_account_changes']
    assert len(p['books']) == 4 and len(p['universe']) == 96
    assert_no_promotion_clause(p)
    # Loading the runtime config checks the clause again and does not change
    # the frozen paper risk set.
    cfg = frozen_config()
    assert cfg['gross_fraction'] == .5 and cfg['drawdown_fraction'] == .15
    assert cfg['daily_realised_loss'] == .03 and cfg['risk_fraction'] == .01
    assert cfg['position_fraction'] == .1 and cfg['live_authorized'] is False


def test_missing_no_promotion_clause_is_refused():
    p = json.loads((Path(__file__).resolve().parents[1] / 'docs/cipher-forward/protocol.json').read_text())
    broken = dict(p)
    del broken['promotion']
    with pytest.raises(ValueError, match='no-promotion'):
        assert_no_promotion_clause(broken)
    weakened = json.loads(json.dumps(p))
    weakened['promotion']['required_gates']['profit_factor_min'] = 1.0
    with pytest.raises(ValueError, match='full desk gates'):
        assert_no_promotion_clause(weakened)
    weakened = json.loads(json.dumps(p))
    weakened['promotion']['statement'] = 'This is a non-promotional experiment.'
    with pytest.raises(ValueError, match='missing'):
        assert_no_promotion_clause(weakened)
