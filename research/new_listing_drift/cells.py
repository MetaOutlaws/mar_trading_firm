"""Frozen constants for new_listing_drift_short.

The cell is the LOCK (e693c870) and the rules it freezes (d4453d10).
Munha's prereg (08f8008b) sets the two cost levels, the MDE, and the
random-baseline draw. Nothing here is a retune knob.
"""

from __future__ import annotations

from dataclasses import dataclass

# Document digests. SPEC.md and PREREG.md in this directory are those bytes.
LOCK_SHA256 = "e693c8709f0fda22444fc1b51f9b58de83fa4a949b1b9d90751feedb7f9eac6e"
PREREG_SHA256 = "08f8008b29c5d36e9311cba0a1ffddabfa4925271b7fca0488532408daa62354"
PROPOSAL_SHA256 = "3ee54412e5a3114db69cd81a01d3b56656cd323a5db218435d868a0b8305a3ba"
RULES_SHA256 = "d4453d107c99f743f29c1af46729621c7de790e44f746fffd0c3e6c779b188f8"
KILL_SHA256 = "bc1ac0156e6e51be70c70558deff79fb4a5a4ea8a785d67e17dea6f85beaa57f"

# Catalog v2, the frozen event list. HMSTRUSDT is absent on purpose.
EVENTS_V2_SHA256 = "da1a2fb4b0ebbd006f000393e7face5cbbb07481e4d1cb8a13d15436c5242406"

# Tape identity. A pinned run requires each SHA256SUMS file to match.
TAPE_SUMS_SHA256 = {
    "C": "ab4472210b9f4ef357fabaa746d7fa20f0eec9b781fafe52461df378be44acd9",
    "D": "5d81bda354fae0740111e693ab5a42df9a9c56df20c01c014ff8f18e399b5039",
    "N": "9c9916e2ec3e58a22a7b45f88ec957c12ffae9943fde48feda78bc6eb8b40f3c",
}

# Directory names on the research box. The CLI refuses these until Garwe
# countersigns, so a pinned path cannot be opened by accident.
REAL_TAPE_DIR_NAMES = {
    "C": "universe96_full_history_20261016",
    "D": "delisted_perps_history_20261016",
    "N": "new_listings_perp_20261016",
}

CELL_NAME = "new_listing_drift_short"

# Entry, hold, stop. Hours, not parameters to search.
LAUNCH_DELAY_HOURS = 24
HOLD_HOURS = 336  # 14 days
STOP_SPREAD = -0.12
RANDOM_EXCLUSION_DAYS = 15

# MDE stated by the prereg for the 87 main week-clusters.
# d = (1.645 + 0.842) / sqrt(87) = 0.267 at one-sided 5% and 80% power.
# Reported, not used as a pass/fail gate.
MDE_D = 0.267
MDE_CLUSTERS = 87
MDE_Z_ALPHA = 1.645
MDE_Z_POWER = 0.842

# Beats-random. The rules said 1,000; the prereg strengthens that to 2,000.
RANDOM_SEED = 20261016
N_PERMUTATIONS = 2000
N_BOOTSTRAP = 10_000
BOOTSTRAP_SEED = 42

# 2026 veto uses the rules' own PF line, which is not the house 1.15.
VETO_PF = 1.0
VETO_MIN_CLUSTERS = 10

# Scorer sizing convention from the prereg. It does not change a trade.
LEG_NOTIONAL_FRACTION = 0.10

# Listing-specific floor from the rules. House criteria supply the rest.
MIN_TRADES_PER_YEAR = 100

# Names the frozen rules drop. They are disclosed, never imputed back.
EXCLUSIONS = (
    "HIGHUSDT",
    "HOOKUSDT",
    "ORBSUSDT",
    "DATAUSDT",
    "HMSTRUSDT",
    "DATAOLD01USDT",
    "LAYERUSDT",
    "LITENTRYUSDT",
    "MONPROUSDT",
    "BTCUSDT",
)

# 15 Oct snapshot coverage. The missing main name is not filled in.
# These are coverage counts, not the event counts (main has 364 events).
SNAPSHOT_COVERAGE = {
    "main": {"snapshot_usdt": 192, "with_event": 191, "missing": ["HMSTRUSDT"], "imputed": False},
    "holdout": {"snapshot_usdt": 106, "with_event": 106, "missing": [], "imputed": False},
}

# Inclusive UTC dates. Membership is by entry time.
WINDOWS: dict[str, tuple[str, str]] = {
    "main": ("2023-10-15", "2025-06-30"),
    "holdout": ("2025-07-01", "2025-12-31"),
    "veto": ("2026-01-01", "2026-10-16"),
}

# Days between the stated endpoints. Trades/year uses this over 365.25,
# which is the convention behind the prereg's 213.1 / 255.5 / 428.7.
WINDOW_ENDPOINT_DAYS = {
    "main": 624,
    "holdout": 183,
    "veto": 288,
}
DAYS_PER_YEAR = 365.25

HEDGE_SYMBOL = "BTCUSDT"
CLOSED_WINDOWS = ("holdout", "veto")


@dataclass(frozen=True)
class CellConfig:
    """The one runnable cell. There is no retune field."""

    name: str
    runnable: bool
    check_tape_pins: bool
    note: str


NEW_LISTING_DRIFT_SHORT = CellConfig(
    name=CELL_NAME,
    runnable=True,
    check_tape_pins=True,
    note=(
        "Short the new USDT perp and long equal-notional BTCUSDT at the "
        "next open after the first full 1h bar that closes at or after "
        "launch+24h. Hold 14 days, or exit at the last tradable bar before "
        "delivery or delist. Stop the spread at -12% on 1h closes and fill "
        "the next open. Official cost is 0.31% per leg. Funding is included "
        "on both legs and is never zero-filled."
    ),
)

CELLS = {NEW_LISTING_DRIFT_SHORT.name: NEW_LISTING_DRIFT_SHORT}


def get_cell(name: str) -> CellConfig:
    try:
        return CELLS[name]
    except KeyError as exc:
        known = ", ".join(sorted(CELLS))
        raise KeyError(f"unknown cell {name!r}; known: {known}") from exc
