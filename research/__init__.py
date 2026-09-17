"""Validation harness: backtesting, walk-forward, cost modelling, significance.

The output of this package is the only acceptable evidence that a strategy has
an edge. Nothing reaches live trading without passing through here.

Walk-forward windowing/fill semantics are versioned by
`research.walkforward.RESEARCH_VERSION` so a later revalidation kit can key
off the F01 OOS-boundary repair.
"""

from research.walkforward import RESEARCH_VERSION

__all__ = ["RESEARCH_VERSION"]
