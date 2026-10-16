"""Frozen cell configs. The signal is selected by name and plugged in.

``size_factor_weekly_cap`` is a stub. It records the draft rules so the
same engine can run it later. ``runnable`` is false and the signal raises.
Do not point it at a tape.
"""

from __future__ import annotations

from dataclasses import dataclass

# Document digests the harness was built against. SPEC.md / PREREG.md /
# COUNTERSIGN.md in this directory are the verbatim bytes.
LOCK_SHA256 = "974a05adf510dfca0e0c6562ff089282ae85e274edfaa479138915efe079efce"
PREREG_SHA256 = "41a91e19da12ee6dd7875ab970738cc729e46caeb6a0e993cff9aae1234fa965"
COUNTERSIGN_SHA256 = "112c52122ee72447ac9e4e3d6ae86a5c7757f8d7caf2fb19a14f4a04a65c4b6a"
PROPOSAL_SHA256 = "7512025efe7ba96b5b66c1560df4402db6a44b8537a2581d676da0455f331f4e"

# Tape C identity. Verified against SHA256SUMS before a pinned run.
TAPE_C_SUMS_SHA256 = "ab4472210b9f4ef357fabaa746d7fa20f0eec9b781fafe52461df378be44acd9"
PERP_1H_SHA256 = "e974ef5abc25843f4fdaf72a09f2e2b5ab7dbfa05aedc13b0039b74e16ca6247"
MEMBERSHIP_PIT_PARQUET_SHA256 = "3f85621345dcef92b459dac6d2390dd15636a5870015a85f5caace8fdb6349f0"

# Monday-inclusive windows. The first Monday on or after the start, through
# the last Monday on or before the end: main 90, holdout 26, veto 41.
WINDOWS: dict[str, tuple[str, str]] = {
    "main": ("2023-10-15", "2025-06-30"),
    "holdout": ("2025-07-01", "2025-12-31"),
    "veto": ("2026-01-01", "2026-10-16"),
}


@dataclass(frozen=True)
class CellConfig:
    """One frozen cross-sectional cell. No retune fields."""

    name: str
    signal_name: str
    long_side: str  # "bottom" (lowest score) or "top"
    stop_pct: float
    leg_cost_rate: float
    min_history_days: int
    lookback_bars: int
    min_bars: int
    hold_days: int
    runnable: bool
    check_tape_pins: bool
    note: str


XS_REALIZED_SKEW_WEEKLY = CellConfig(
    name="xs_realized_skew_weekly",
    signal_name="realized_skew",
    long_side="bottom",
    stop_pct=0.12,
    leg_cost_rate=0.0031,
    min_history_days=31,
    lookback_bars=168,
    min_bars=150,
    hold_days=7,
    runnable=True,
    check_tape_pins=True,
    note=(
        "RSK = sqrt(N)*sum(r^3)/(sum(r^2))^1.5 over the 168 hourly log "
        "returns ending at the bar that closes at or before Monday 00:00 UTC. "
        "Long the bottom tercile, short the top, equal-weight, dollar-neutral."
    ),
)

# Stub only. Cap tape is not wired. Invoking the signal raises.
SIZE_FACTOR_WEEKLY_CAP = CellConfig(
    name="size_factor_weekly_cap",
    signal_name="market_cap",
    long_side="bottom",
    stop_pct=0.12,
    leg_cost_rate=0.0031,
    min_history_days=31,
    lookback_bars=1,
    min_bars=1,
    hold_days=7,
    runnable=False,
    check_tape_pins=True,
    note=(
        "STUB. Do not run. Point-in-time market cap, lagged one UTC day, "
        "long the small tercile and short the large tercile on the same "
        "engine. No cap tape is attached and no metric is computed."
    ),
)

CELLS: dict[str, CellConfig] = {
    XS_REALIZED_SKEW_WEEKLY.name: XS_REALIZED_SKEW_WEEKLY,
    SIZE_FACTOR_WEEKLY_CAP.name: SIZE_FACTOR_WEEKLY_CAP,
}


def get_cell(name: str) -> CellConfig:
    try:
        return CELLS[name]
    except KeyError as exc:
        known = ", ".join(sorted(CELLS))
        raise KeyError(f"unknown cell {name!r}; known: {known}") from exc
