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
    # Dollar-neutral terciles are the skew book. Beta-neutral is BAB.
    # Defaults keep the skew cell on the original path.
    weighting: str = "dollar_neutral"
    funding_included: bool = False
    exclude_symbols: tuple[str, ...] = ()
    beta_lookback_days: int = 90
    beta_min_pairs: int = 60
    leverage_cap: float = 3.0
    # Report-only second cost. None means the cell has one level.
    proxy_leg_cost_rate: float | None = None
    proxy_cost_label: str = ""
    # Sampler figures disclosed by the prereg. Not a third charge.
    btc_sampler_rt: float | None = None
    mde_d: float | None = None
    mde_weeks: int | None = None


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

# xs_bab_btc_weekly. Documents live beside this package and are not part of
# the skew document pins. Prereg bf736a50 is countersigned in memo 97911533.
# Harness and scorer hashes stay provisional until Garwe ACKs them.
BAB_LOCK_SHA256 = "08ef0df60c012418cca646fe6339e7510af35231fbc4c900db382dbe101b57ba"
BAB_PREREG_SHA256 = "bf736a50def884170f515f1457b4864a94b19ba4dfb0fa05be58c63c77662a28"
BAB_COUNTERSIGN_MEMO = "97911533"
BAB_PROPOSAL_SHA256 = "1ca85938af74ab45811089325fcae03ce4b0032bab7ccdbdd0f12cc2e7075a10"
BAB_PRESTATED_SHA256 = "12dd3ae0709fdbfc2674e524fc313bebda490c566d1f12c5c8aa80def335b7d1"
# Official gate rate, and the report-only SOL p90 proxy from the frozen prereg.
# BTC 0.135% is the sampler's BTC figure. It is not added to the proxy.
BAB_PROXY_LEG_COST = 0.00181
BAB_BTC_SAMPLER_RT = 0.00135

XS_BAB_BTC_WEEKLY = CellConfig(
    name="xs_bab_btc_weekly",
    signal_name="btc_beta",
    long_side="bottom",
    stop_pct=0.12,
    leg_cost_rate=0.0031,
    min_history_days=31,
    lookback_bars=90,
    min_bars=60,
    hold_days=7,
    runnable=True,
    check_tape_pins=True,
    note=(
        "BAB: 90-day OLS beta of daily 00:00 UTC log returns on BTCUSDT, "
        "min 60 pairs. BTCUSDT is not ranked. Long the low-beta tercile, "
        "short the high-beta tercile, equal-weight within the leg, scaled "
        "1/mean_beta and normalised so the average gross per side is $1, "
        "with each side's leverage capped at 3 before that normalisation. "
        "Official cost is 0.31% per traded notional and binds the gates. "
        "0.181% is the report-only SOL proxy. Funding is included and never "
        "zero-filled. A name is dropped only when the 8h before its entry "
        "open has no funding print; an in-hold gap is kept and counted. "
        "Holdout and 2026 stay behind the lock."
    ),
    weighting="beta_neutral",
    funding_included=True,
    exclude_symbols=("BTCUSDT",),
    beta_lookback_days=90,
    beta_min_pairs=60,
    leverage_cap=3.0,
    proxy_leg_cost_rate=BAB_PROXY_LEG_COST,
    proxy_cost_label="proxy, alts unmeasured",
    btc_sampler_rt=BAB_BTC_SAMPLER_RT,
    mde_d=0.262,
    mde_weeks=90,
)

CELLS: dict[str, CellConfig] = {
    XS_REALIZED_SKEW_WEEKLY.name: XS_REALIZED_SKEW_WEEKLY,
    SIZE_FACTOR_WEEKLY_CAP.name: SIZE_FACTOR_WEEKLY_CAP,
    XS_BAB_BTC_WEEKLY.name: XS_BAB_BTC_WEEKLY,
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
