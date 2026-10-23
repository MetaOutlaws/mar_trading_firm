"""Four independent paper-book routing and cost-aware sizing contracts.

No account mutation or default production risk import. A funded execution
adapter must enforce the other pinned gates before admitting these plans.
"""
from __future__ import annotations

import math

BOOKS = ('I', 'IC', 'IM', 'IF')
BASE_RISK = .01
BASE_POSITION = .10
GROSS = .50


def membership(book: str, source: str, *, filter_pass: bool = False) -> bool:
    if book not in BOOKS or source not in ('H', 'B', 'C3'):
        raise ValueError('unknown book/source')
    return source != 'C3' or book in ('IC', 'IM') or (book == 'IF' and filter_pass)


def planned_notional(book: str, source: str, equity: float, gross: float,
                     loss_fraction: float, *, filter_pass: bool = False) -> float:
    if any(not isinstance(x, (int, float)) or isinstance(x, bool)
           or not math.isfinite(x) for x in (equity, gross, loss_fraction)):
        raise ValueError('non-finite sizing input')
    if equity <= 0 or gross < 0 or loss_fraction <= 0:
        raise ValueError('invalid sizing input')
    if not membership(book, source, filter_pass=filter_pass):
        return 0.
    scale = .5 if book == 'IM' and source == 'C3' else 1.
    # Scale only challenger caps. Remaining account headroom is not scaled.
    return max(0., min(scale * BASE_RISK * equity / loss_fraction,
                       scale * BASE_POSITION * equity, GROSS * equity - gross))


def ordered_candidates(signals):
    """Stable common feed, before separate book admissions. No winner ranking."""
    rank = {'H': 0, 'B': 1, 'C3': 2}
    return sorted(signals, key=lambda s: (s['action_ms'], rank[s['source']],
                                          s['symbol'], s['uid']))
