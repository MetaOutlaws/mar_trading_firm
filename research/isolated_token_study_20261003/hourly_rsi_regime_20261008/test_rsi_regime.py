import numpy as np
import pytest
from rsi_regime_rule import policy_pass


def test_conditional_equality_and_both_sides():
    rsi = [70., 70.0001, 29.9999, 30., 100.]
    side = [1, 1, -1, -1, 1]
    er = [.2999, .30, .2999, .30, .31]
    assert policy_pass(rsi, side, er, 'none').tolist() == [True]*5
    assert policy_pass(rsi, side, er, 'always').tolist() == [True, False, False, True, False]
    assert policy_pass(rsi, side, er, 'directional').tolist() == [True, False, True, True, False]
    assert policy_pass(rsi, side, er, 'loweff').tolist() == [True, True, False, True, True]


@pytest.mark.parametrize('er', [np.nan, np.inf, -.01, 1.01])
def test_missing_or_invalid_state_is_not_an_implicit_bypass(er):
    for policy in ['none', 'always', 'directional', 'loweff']:
        with pytest.raises(ValueError):
            policy_pass(50., 1, er, policy)


def test_policies_cannot_bypass_existing_benchmark():
    benchmark = np.array([False, True, True])
    assert (benchmark & policy_pass([80.,80.,80.], 1, [.2,.3,.2], 'loweff')).tolist() == [False,True,False]
    with pytest.raises(ValueError):
        policy_pass(50., 1, .2, 'unregistered')
