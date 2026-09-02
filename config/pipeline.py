"""
Configurable research-pipeline thresholds.

Cadences are backstops. Walk-forward start is event-driven: a free slot
launches from standby in the same tick. No duration constant is used to
decide *when* the next test starts. The hung-job detector is the only
duration threshold, and it is a rolling median of completed runs.

Conflicts vs the implementation brief (not silently reinterpreted):

1. Sleeve Engineer materializes allowed JSON templates (`config/sleeves/`)
   into the registry. Novel families (new math, new feed) escalate to
   Cursor via `research/coding_requests/`. Lookahead bugs in freeform
   generated Python are how the last bot lied to itself.

   2. Coding-queue floor of 2 uncoded families fights "code immediately".
   `pipeline_coding_queue_floor` defaults to 0. When the coded catalog is
   empty, one novel family is auto-queued to Cursor (NOW.md). Inbox remains
   the paper-to-live gate. Cap of 5 still applies.

3. Catalog depth of 10 clock/param variants still applies. Separately,
   at least 10 **novel** families must sit ready as Inbox briefs for Cursor.
   `funding_fade` stays feed-blocked (Tier C).

4. Walk-forward parallelism defaults to 3 as specified. Lower it with
   PIPELINE_WF_PARALLELISM if Bybit rate-limits. The 24h auto-advance
   budget is a same-grid loop cap; a new family@clock@side still starts.

5. Tier A auto-advance relocates the human gate to paper-to-live. A global
   PIPELINE_AUTO_ADVANCE=false switch reverts to default-block.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from config.settings import get_settings

#: BTC/ETH/SOL plus BNB/XRP/AVAX — 6 symbols, 12 long/short pairs.
#: New names still need asset_params rows before paper will scan them.
APPROVED_RESEARCH_SYMBOLS = (
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "BNBUSDT",
    "XRPUSDT",
    "AVAXUSDT",
)

#: Paper-only extra scans. Not live and not a walk-forward verdict.
#: 1h ATR failed gates on BTC/ETH/SOL; BNB/XRP/AVAX were never tested there.
#: The catalog clock for this family stays 4h/4h.
PAPER_SCAN_SLEEVES: tuple[tuple[str, str, str, str], ...] = (
    ("atr_channel_breakout", "BNBUSDT", "LONG", "1h"),
    ("atr_channel_breakout", "BNBUSDT", "SHORT", "1h"),
    ("atr_channel_breakout", "XRPUSDT", "LONG", "1h"),
    ("atr_channel_breakout", "XRPUSDT", "SHORT", "1h"),
    ("atr_channel_breakout", "AVAXUSDT", "LONG", "1h"),
    ("atr_channel_breakout", "AVAXUSDT", "SHORT", "1h"),
)


def is_paper_scan_sleeve(family: str, symbol: str, side: str, timeframe: str) -> bool:
    """True when this exact sleeve is on the operator paper-candidate list."""
    return (family, symbol, str(side).upper(), timeframe) in PAPER_SCAN_SLEEVES


SUPPORTED_TIMEFRAMES = frozenset({"15m", "1h", "4h"})
STANDARD_TRAIN_DAYS = 180
STANDARD_TEST_DAYS = 60

STAGE_OWNERS: dict[str, str] = {
    "catalog": "quant_researcher",
    "coding": "sleeve_engineer",
    "standby": "sleeve_engineer",
    "walk_forward": "desk_head",
    "postmortem": "performance_auditor",
    "paper_to_live": "operator",
}

# Event -> (owner seat, max seconds before the response is overdue).
# Zero means same-tick: the handler must run in the emitting process.
EVENT_OWNERS: dict[str, tuple[str, int]] = {
    "on_test_finished": ("desk_head", 0),
    "on_test_rejected": ("performance_auditor", 15 * 60),
    "on_walk_forward_slot_free": ("desk_head", 0),
    "on_inbox_empty": ("desk_head", 5 * 60),
    "on_coding_request_queued": ("sleeve_engineer", 15 * 60),
    "on_sleeve_registered": ("desk_head", 0),
    "on_standby_depth_low": ("sleeve_engineer", 15 * 60),
    "on_catalog_depth_low": ("quant_researcher", 15 * 60),
    "on_llm_timeout": ("ops_engineer", 15 * 60),
}


@dataclass(frozen=True)
class PipelineConfig:
    auto_advance: bool
    auto_advance_budget_24h: int
    circuit_breaker_rejects: int
    wf_parallelism: int
    catalog_min_unqueued: int
    coding_queue_floor: int
    coding_queue_cap: int
    standby_floor: int
    standby_target: int
    tier_b_hours: float
    max_free_params: int
    reject_cooldown_days: int
    hung_median_n: int
    hung_median_mult: float

    def snapshot(self) -> dict[str, Any]:
        return {
            "auto_advance": self.auto_advance,
            "auto_advance_budget_24h": self.auto_advance_budget_24h,
            "circuit_breaker_rejects": self.circuit_breaker_rejects,
            "wf_parallelism": self.wf_parallelism,
            "catalog_min_unqueued": self.catalog_min_unqueued,
            "coding_queue_floor": self.coding_queue_floor,
            "coding_queue_cap": self.coding_queue_cap,
            "standby_floor": self.standby_floor,
            "standby_target": self.standby_target,
            "tier_b_hours": self.tier_b_hours,
            "max_free_params": self.max_free_params,
            "reject_cooldown_days": self.reject_cooldown_days,
            "hung_median_n": self.hung_median_n,
            "hung_median_mult": self.hung_median_mult,
            "coding_queue_floor_note": (
                "Brief asked for >=2 uncoded. Default 0: uncoded work is the "
                "stall. Standby depth is the reserve."
            ),
        }


def pipeline_config() -> PipelineConfig:
    s = get_settings()
    return PipelineConfig(
        auto_advance=bool(s.pipeline_auto_advance),
        auto_advance_budget_24h=int(s.pipeline_auto_advance_budget_24h),
        circuit_breaker_rejects=int(s.pipeline_circuit_breaker_rejects),
        wf_parallelism=int(s.pipeline_wf_parallelism),
        catalog_min_unqueued=int(s.pipeline_catalog_min_unqueued),
        coding_queue_floor=int(s.pipeline_coding_queue_floor),
        coding_queue_cap=int(s.pipeline_coding_queue_cap),
        standby_floor=int(s.pipeline_standby_floor),
        standby_target=int(s.pipeline_standby_target),
        tier_b_hours=float(s.pipeline_tier_b_hours),
        max_free_params=int(s.pipeline_max_free_params),
        reject_cooldown_days=int(s.pipeline_reject_cooldown_days),
        hung_median_n=int(s.pipeline_hung_median_n),
        hung_median_mult=float(s.pipeline_hung_median_mult),
    )
