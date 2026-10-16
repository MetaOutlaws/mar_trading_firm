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
    # Dollar-neutral terciles are the skew book and the TK book.
    # Defaults keep the skew cell on its original path.
    weighting: str = "dollar_neutral"
    funding_included: bool = False
    # Report-only second cost. None means the cell has one level.
    proxy_leg_cost_rate: float | None = None
    proxy_cost_label: str = ""
    btc_sampler_rt: float | None = None
    sol_sampler_rt: float | None = None
    mde_d: float | None = None
    mde_weeks: int | None = None
    # Daily feature window. The skew cell does not read these.
    lookback_days: int = 60
    min_daily_returns: int = 50
    # Cell document, relative to the package. Empty means this cell does
    # not hash a countersign at run time (the skew cell pins its own).
    countersign_relative: str = ""


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

# xs_prospect_value_weekly. Documents live beside this package and are not
# part of the skew document pins. Prereg 2afe8b36 is countersigned in
# xs_prospect_value_weekly/COUNTERSIGN.md (dfc6180d). The run hashes that
# file; it does not trust this constant alone.
TK_LOCK_SHA256 = "a712319ac9175e2e41befbbcae4c0dee7d18a3d077e14f3fa1e1bae38d702c15"
TK_PREREG_SHA256 = "2afe8b36b22a25ab4b46884795435520a24fb1bf621034dc2cfe63fd86d236d9"
TK_PROPOSAL_SHA256 = "b815ed4db98f8b72e17803742434d51cbb4437278f2d5ddfb42f060bda783d2e"
TK_PRESTATED_SHA256 = "62e906ffd6a2f359559c1b8dde525d4778419cd8fc0ce9f81409b3b9ce6f8f73"
TK_COUNTERSIGN_SHA256 = "dfc6180dc774e40f4d216bc1cde4157a97831171a46d975fd360402d51e6e95b"
TK_COUNTERSIGN_RELATIVE = "xs_prospect_value_weekly/COUNTERSIGN.md"
# Official gate rate is 0.31%. The report-only proxy is the mean of the
# BTC 0.135% and SOL 0.181% measured round trips. Alts are unmeasured.
TK_BTC_SAMPLER_RT = 0.00135
TK_SOL_SAMPLER_RT = 0.00181
TK_PROXY_LEG_COST = (TK_BTC_SAMPLER_RT + TK_SOL_SAMPLER_RT) / 2.0

XS_PROSPECT_VALUE_WEEKLY = CellConfig(
    name="xs_prospect_value_weekly",
    signal_name="prospect_value",
    long_side="bottom",
    stop_pct=0.12,
    leg_cost_rate=0.0031,
    min_history_days=31,
    lookback_bars=60,
    min_bars=50,
    hold_days=7,
    runnable=True,
    check_tape_pins=True,
    note=(
        "TK value of the past 60 daily 00:00 UTC log returns, minimum 50. "
        "Each observation has probability 1/n. Value alpha 0.88, lambda 2.25. "
        "Cumulative decision weights use gamma+ 0.61 and gamma- 0.69. "
        "BTCUSDT is included. Long the bottom tercile, short the top, "
        "equal-weight, dollar-neutral. Official cost is 0.31% per traded "
        "notional and binds the gates. 0.158% is the report-only measured "
        "proxy (mean of BTC 0.135% and SOL 0.181%) and a sign flip vetoes. "
        "Funding is included and never zero-filled. A name is dropped only "
        "when the 8h before its entry open has no funding print; an in-hold "
        "gap is kept and counted. Holdout and 2026 stay behind the lock."
    ),
    weighting="dollar_neutral",
    funding_included=True,
    proxy_leg_cost_rate=TK_PROXY_LEG_COST,
    proxy_cost_label="proxy, alts unmeasured",
    btc_sampler_rt=TK_BTC_SAMPLER_RT,
    sol_sampler_rt=TK_SOL_SAMPLER_RT,
    mde_d=0.262,
    mde_weeks=90,
    lookback_days=60,
    min_daily_returns=50,
    countersign_relative=TK_COUNTERSIGN_RELATIVE,
)

CELLS: dict[str, CellConfig] = {
    XS_REALIZED_SKEW_WEEKLY.name: XS_REALIZED_SKEW_WEEKLY,
    SIZE_FACTOR_WEEKLY_CAP.name: SIZE_FACTOR_WEEKLY_CAP,
    XS_PROSPECT_VALUE_WEEKLY.name: XS_PROSPECT_VALUE_WEEKLY,
}


def cost_rates(config: CellConfig) -> tuple[float, ...]:
    """Official rate first. Extra rates are report-only."""
    if config.proxy_leg_cost_rate is None:
        return (config.leg_cost_rate,)
    return (config.leg_cost_rate, float(config.proxy_leg_cost_rate))


def get_cell(name: str) -> CellConfig:
    try:
        return CELLS[name]
    except KeyError as exc:
        known = ", ".join(sorted(CELLS))
        raise KeyError(f"unknown cell {name!r}; known: {known}") from exc
