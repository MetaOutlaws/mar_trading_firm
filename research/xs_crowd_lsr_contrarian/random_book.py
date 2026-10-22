"""Turnover-matched random book. 1,000 draws, seed 20261016.

At each kept rebalance the null draws a long set and a disjoint short set
of size k from the PIT-eligible names that have a valid L, in the pinned
(L, symbol) order. The previous random book is carried, and exactly the
number of names the strategy replaced on that leg is redrawn. A gap
(dropped Monday or thin skip) clears the carried book, so the next kept
Monday is a fresh draw, matching the strategy's fresh entry.

Stops are the random book's own paths, not the strategy's stop set. The
same simulator, the same 12% stop, the same funding and the same 0.31%
cost produce the weekly net. The result stored for the seal is the mean
weekly net of each draw. The p-value is not computed here.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from research.xs_crowd_lsr_contrarian.book import Schedule, Simulation, TradeWeek, simulate_weeks
from research.xs_crowd_lsr_contrarian.calendar import continuous
from research.xs_crowd_lsr_contrarian.hashing import assert_pythonhashseed
from research.xs_crowd_lsr_contrarian.pins import LEG, N_RANDOM_DRAWS, OFFICIAL_LEG_COST, RANDOM_SEED
from research.xs_crowd_lsr_contrarian.signal import leg_weights


def draw_leg(
    prev: set[str],
    eligible: list[str],
    k: int,
    n_new: int,
    banned: set[str],
    rng: np.random.Generator,
) -> set[str]:
    """Carry ``prev`` and replace ``n_new`` names.

    ``eligible`` is already in the pinned order. A name that left that
    pool cannot be carried. A dropped name is not drawn straight back, so
    the realized turnover is a match and not a ceiling.
    """
    pool = [symbol for symbol in eligible if symbol not in banned]
    pool_set = set(pool)
    carried = [symbol for symbol in sorted(prev) if symbol in pool_set]
    target_keep = min(len(carried), max(0, k - int(n_new)))
    if len(carried) > target_keep:
        n_drop = len(carried) - target_keep
        drop_at = rng.choice(len(carried), size=n_drop, replace=False)
        dropped = {carried[int(i)] for i in np.atleast_1d(drop_at)}
        keep = [symbol for symbol in carried if symbol not in dropped]
    else:
        keep = list(carried)
    need = k - len(keep)
    keep_set = set(keep)
    fresh = [symbol for symbol in pool if symbol not in keep_set and symbol not in prev]
    if need > len(fresh):
        raise RuntimeError(
            f"eligible set cannot fill the leg: need {need} new names, have {len(fresh)}"
        )
    if need:
        pick = rng.choice(len(fresh), size=need, replace=False)
        chosen = [fresh[int(i)] for i in np.atleast_1d(pick)]
    else:
        chosen = []
    return set(keep) | set(chosen)


def draw_weights(schedule: Schedule, rng: np.random.Generator) -> dict[pd.Timestamp, dict[str, float]]:
    """One turnover-matched book, keyed by rebalance time."""
    prev_long: set[str] = set()
    prev_short: set[str] = set()
    random_long: set[str] = set()
    random_short: set[str] = set()
    prev_t: pd.Timestamp | None = None
    drawn: dict[pd.Timestamp, dict[str, float]] = {}
    for week in schedule.trades:
        if not continuous(prev_t, week.t):
            prev_long = set()
            prev_short = set()
            random_long = set()
            random_short = set()
        realized_long = set(week.long)
        realized_short = set(week.short)
        n_new_long = len(realized_long - prev_long)
        n_new_short = len(realized_short - prev_short)
        random_long = draw_leg(
            random_long, week.eligible_order, week.k, n_new_long, set(), rng
        )
        random_short = draw_leg(
            random_short, week.eligible_order, week.k, n_new_short, random_long, rng
        )
        drawn[week.t] = leg_weights(sorted(random_long), sorted(random_short), LEG)
        prev_long, prev_short = realized_long, realized_short
        prev_t = week.t
    return drawn


def _weight_fn(drawn: dict[pd.Timestamp, dict[str, float]]):
    def weights(week: TradeWeek, _fresh: bool) -> dict[str, float]:
        try:
            return drawn[week.t]
        except KeyError as exc:
            raise RuntimeError(f"random book has no weights at {week.t}") from exc

    return weights


def simulate_draw(schedule: Schedule, rng: np.random.Generator) -> Simulation:
    """Weekly net of one draw at the binding 0.31% rate. No trade log."""
    drawn = draw_weights(schedule, rng)
    return simulate_weeks(
        schedule.trades,
        _weight_fn(drawn),
        rate=OFFICIAL_LEG_COST,
        collect=False,
    )


def random_book_means(
    schedule: Schedule,
    *,
    n_perm: int = N_RANDOM_DRAWS,
    seed: int = RANDOM_SEED,
    progress=None,
) -> np.ndarray:
    """Mean weekly net of each draw.

    The binding call uses the defaults: 1,000 draws, seed 20261016.
    ``SeedSequence.spawn`` makes draw i independent of how many draws are
    requested only within a single spawn of that same count, so two calls
    with the same arguments match. A test may pass a smaller ``n_perm``.
    The command line does not.
    """
    # The shell has to have started this process with PYTHONHASHSEED=0.
    # Setting the variable here would not disable hash randomization.
    assert_pythonhashseed()
    if n_perm < 1:
        raise ValueError("n_perm must be positive")
    if not schedule.trades:
        return np.empty(0, dtype="float64")
    children = np.random.SeedSequence(seed).spawn(n_perm)
    means = np.empty(n_perm, dtype="float64")
    for i, child in enumerate(children):
        rng = np.random.default_rng(child)
        sim = simulate_draw(schedule, rng)
        net = [float(row["net_return"]) for row in sim.weekly]
        means[i] = float(np.mean(net)) if net else float("nan")
        if progress is not None and (i + 1 == n_perm or (i + 1) % 100 == 0):
            progress(i + 1, n_perm)
    return means
