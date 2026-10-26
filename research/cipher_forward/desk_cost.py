"""Desk cost labels for the paper settings.

``desk031`` is 0.31% of price on entry, on a non-stop exit, and on a stop
exit. baseline, moderate, and severe keep their previous numbers. Book cells
are REPORT-ONLY. The one BINDING statistic is the paired weekly IC-minus-I
P&L difference at desk031, not a book cell.
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


def binding_statistic_spec() -> dict:
    """The one statistic desk gates apply to.

    IC and I book metrics stay report-only. Profit factor for the gates is
    the challenger's own leg-trades (source C3 on desk031:IC). The IC book
    max drawdown is a veto at 25%, not a second binding statistic.
    """
    return dict(
        name='paired_weekly_ic_minus_i_pnl',
        count=1,
        scope='desk031',
        definition=(
            'The paired weekly IC-minus-I P&L difference at desk031 only, '
            'the 3R challenger marginal contribution.'
        ),
        gates='desk gates apply to this stream',
        profit_factor_source='challenger_leg_trades',
        challenger_source='C3',
        ic_book_metrics='REPORT-ONLY',
        i_book_metrics='REPORT-ONLY',
        ic_book_mdd_veto_lt=0.25,
        book_cells_are_not_binding=True,
    )


def cell_role(arm: str, cost: str, primary: str) -> str:
    """Every book cell is REPORT-ONLY. The binding statistic is not a cell."""
    if arm not in ARMS or cost not in COST_ORDER or primary not in ARMS:
        raise ValueError('unknown book cell')
    return 'REPORT-ONLY'


def desk_cost_read() -> dict:
    """Per-leg rates. No book cell is BINDING.

    Severe stays a secondary display. The one BINDING statistic is
    ``binding_statistic_spec``. IC and I at desk031 are REPORT-ONLY, as are
    IM, IF, baseline, moderate, and severe.
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
    if binding:
        raise RuntimeError('a book cell was labelled BINDING')
    if primary not in ARMS:
        raise RuntimeError('primary arm missing')
    statistic = binding_statistic_spec()
    if statistic['count'] != 1:
        raise RuntimeError('binding statistic count drifted')
    return dict(
        binding_per_leg=format(BINDING_PER_LEG, 'f'),
        binding_per_leg_percent='0.31%',
        binding_applies_to='entry and exit',
        primary=primary,
        binding_cells=binding,
        binding_statistic=statistic,
        prior_three_cost_settings_unchanged=True,
        added_setting='desk031',
        statement=(
            'The one BINDING statistic is the paired weekly IC-minus-I P&L '
            'difference at desk031. Desk gates apply to that stream. Profit '
            "factor is taken from the challenger's own leg-trades. IC and I "
            'book metrics are REPORT-ONLY. IC book max drawdown must stay '
            'under 25% as a veto. Every cell is REPORT-ONLY. Severe stays '
            'secondary display only.'
        ),
        settings=settings,
        cells=cells,
    )
