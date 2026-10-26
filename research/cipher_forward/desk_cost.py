"""Desk cost read for the three frozen paper settings.

The binding desk cost is 0.31% of price per leg, on entry and on exit.
This module only labels the settings that already exist. It does not edit
``FEE`` or ``COSTS``.
"""
from __future__ import annotations

from decimal import Decimal

from .strategy import COSTS, FEE

# Exact written literals. They are checked against the runtime floats so a
# silent edit of FEE or COSTS cannot keep a stale label.
BINDING_PER_LEG = Decimal('0.0031')
_FEE = Decimal('0.00055')
_SLIP = {
    'baseline': (Decimal('0.002'), Decimal('0')),
    'moderate': (Decimal('0.003'), Decimal('0.002')),
    'severe': (Decimal('0.01'), Decimal('0.01')),
}


def _percent(rate: Decimal) -> str:
    text = format(rate * Decimal('100'), 'f')
    if '.' in text:
        text = text.rstrip('0').rstrip('.')
    return text + '%'


def _leg(fee: Decimal, slip: Decimal) -> dict:
    total = fee + slip
    cheaper = total < BINDING_PER_LEG
    equal = total == BINDING_PER_LEG
    if equal:
        role = 'BINDING'
    elif cheaper:
        role = 'REPORT-ONLY'
    else:
        role = 'above_binding_not_equal'
    return dict(
        fee=format(fee, 'f'),
        slip=format(slip, 'f'),
        total=format(total, 'f'),
        percent=_percent(total),
        equals_binding=equal,
        cheaper_than_binding=cheaper,
        role=role,
    )


def assert_cost_literals_unchanged() -> None:
    """Refuse to label costs if the frozen numbers have drifted."""
    if Decimal(str(FEE)) != _FEE:
        raise RuntimeError('fee literal drifted; refusing to relabel costs')
    if tuple(COSTS) != ('baseline', 'moderate', 'severe'):
        raise RuntimeError('cost setting names drifted')
    for name, pair in _SLIP.items():
        slip, stop = COSTS[name]
        if (Decimal(str(slip)), Decimal(str(stop))) != pair:
            raise RuntimeError(f'{name} cost literal drifted; refusing to relabel costs')


def desk_cost_read() -> dict:
    """Exact per-leg cost of each setting, plus the desk label.

    A setting is BINDING only when entry, non-stop exit, and stop exit are
    each exactly 0.31%. Anything cheaper is REPORT-ONLY. Severe stays a
    secondary display regardless. No number in ``COSTS`` is modified.
    """
    assert_cost_literals_unchanged()
    settings = {}
    for name, (entry_slip, stop_slip) in _SLIP.items():
        entry = _leg(_FEE, entry_slip)
        nonstop_exit = _leg(_FEE, entry_slip)
        stop_exit = _leg(_FEE, stop_slip)
        legs = (entry, nonstop_exit, stop_exit)
        equals = all(leg['equals_binding'] for leg in legs)
        cheaper = all(leg['cheaper_than_binding'] for leg in legs)
        if name == 'severe':
            # Operator display rule: severe is secondary. It is not a desk read.
            role = 'secondary_display_only'
            display = 'secondary'
        elif equals:
            role = 'BINDING'
            display = 'prominent'
        elif cheaper:
            role = 'REPORT-ONLY'
            display = 'prominent'
        else:
            role = 'not_binding'
            display = 'prominent'
        settings[name] = dict(
            role=role,
            display=display,
            equals_0_31pct_per_leg=equals,
            every_leg_cheaper_than_0_31pct=cheaper,
            fee_each_leg=format(_FEE, 'f'),
            entry_and_nonstop_slip=format(entry_slip, 'f'),
            stop_slip=format(stop_slip, 'f'),
            entry=entry,
            nonstop_exit=nonstop_exit,
            stop_exit=stop_exit,
        )
    return dict(
        binding_per_leg=format(BINDING_PER_LEG, 'f'),
        binding_per_leg_percent='0.31%',
        binding_applies_to='entry and exit',
        any_setting_equals_0_31pct_per_leg=any(
            row['equals_0_31pct_per_leg'] for row in settings.values()),
        settings_changed=False,
        escalation=(
            'None of the three cost settings equals 0.31% per leg on entry and '
            'on exit. Cost settings were not changed. None is labelled BINDING.'
        ),
        settings=settings,
    )
