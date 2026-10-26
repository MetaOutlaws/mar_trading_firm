"""Desk cost labels for the paper settings.

``desk031`` is 0.31% of price on entry, on a non-stop exit, and on a stop
exit. baseline, moderate, and severe keep their previous numbers. Only the
PRIMARY arm at desk031 is labelled BINDING. Every other cell is REPORT-ONLY.
"""
from __future__ import annotations

from decimal import Decimal

from .config import require_primary
from .strategy import COSTS, FEE

# Exact written literals. They are checked against the runtime floats so a
# silent edit of FEE or COSTS cannot keep a stale label.
BINDING_PER_LEG = Decimal('0.0031')
_FEE = Decimal('0.00055')
_SLIP = {
    'desk031': (Decimal('0.00255'), Decimal('0.00255')),
    'baseline': (Decimal('0.002'), Decimal('0')),
    'moderate': (Decimal('0.003'), Decimal('0.002')),
    'severe': (Decimal('0.01'), Decimal('0.01')),
}
COST_ORDER = ('desk031', 'baseline', 'moderate', 'severe')
ARMS = ('I', 'IC', 'IM', 'IF')


def _percent(rate: Decimal) -> str:
    text = format(rate * Decimal('100'), 'f')
    if '.' in text:
        text = text.rstrip('0').rstrip('.')
    return text + '%'


def _leg(fee: Decimal, slip: Decimal) -> dict:
    total = fee + slip
    cheaper = total < BINDING_PER_LEG
    equal = total == BINDING_PER_LEG
    return dict(
        fee=format(fee, 'f'),
        slip=format(slip, 'f'),
        total=format(total, 'f'),
        percent=_percent(total),
        equals_binding=equal,
        cheaper_than_binding=cheaper,
    )


def assert_cost_literals_unchanged() -> None:
    """Refuse to label costs if the frozen numbers have drifted."""
    if Decimal(str(FEE)) != _FEE:
        raise RuntimeError('fee literal drifted; refusing to relabel costs')
    if tuple(COSTS) != COST_ORDER:
        raise RuntimeError('cost setting names drifted')
    for name, pair in _SLIP.items():
        slip, stop = COSTS[name]
        if (Decimal(str(slip)), Decimal(str(stop))) != pair:
            raise RuntimeError(f'{name} cost literal drifted; refusing to relabel costs')


def cell_role(arm: str, cost: str, primary: str) -> str:
    """BINDING only for the one PRIMARY x desk031 cell."""
    if arm == primary and cost == 'desk031':
        return 'BINDING'
    return 'REPORT-ONLY'


def desk_cost_read() -> dict:
    """Per-leg rates plus the one binding cell.

    Severe stays a secondary display. The column itself is not the label:
    I, IM, and IF at desk031 are REPORT-ONLY, as are baseline, moderate,
    and severe on every arm.
    """
    from .config import ROOT
    import json

    assert_cost_literals_unchanged()
    protocol = json.loads((ROOT / 'docs/cipher-forward/protocol.json').read_text())
    primary = require_primary(protocol)
    settings = {}
    for name, (entry_slip, stop_slip) in _SLIP.items():
        entry = _leg(_FEE, entry_slip)
        nonstop_exit = _leg(_FEE, entry_slip)
        stop_exit = _leg(_FEE, stop_slip)
        legs = (entry, nonstop_exit, stop_exit)
        equals = all(leg['equals_binding'] for leg in legs)
        cheaper = all(leg['cheaper_than_binding'] for leg in legs)
        settings[name] = dict(
            display='secondary' if name == 'severe' else 'prominent',
            equals_0_31pct_per_leg=equals,
            every_leg_cheaper_than_0_31pct=cheaper,
            fee_each_leg=format(_FEE, 'f'),
            entry_and_nonstop_slip=format(entry_slip, 'f'),
            stop_slip=format(stop_slip, 'f'),
            entry=entry,
            nonstop_exit=nonstop_exit,
            stop_exit=stop_exit,
        )
    cells = {
        f'{cost}:{arm}': cell_role(arm, cost, primary)
        for cost in COST_ORDER for arm in ARMS
    }
    binding = [name for name, role in cells.items() if role == 'BINDING']
    if binding != [f'desk031:{primary}']:
        raise RuntimeError('binding cell drifted')
    return dict(
        binding_per_leg=format(BINDING_PER_LEG, 'f'),
        binding_per_leg_percent='0.31%',
        binding_applies_to='entry and exit',
        primary=primary,
        binding_cell=f'desk031:{primary}',
        binding_cells=binding,
        prior_three_cost_settings_unchanged=True,
        added_setting='desk031',
        statement=(
            f'Only {primary} at desk031 is labelled BINDING. '
            'Every other cell is REPORT-ONLY. Severe stays secondary display only.'
        ),
        settings=settings,
        cells=cells,
    )
