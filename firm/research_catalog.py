"""
The firm's research plan: what we test, in what order, and why.

This is the operator-visible catalog. The Quant Researcher is shown the same
list so it cannot pretend the only idea in the world is RSI. Approvals still
come only from `research.validate` — this file is the agenda, not a green light.

We do not dump hundreds of clock clones of a family that already lost after
costs. New math is allowed: Quant names a snake_case family, Cursor codes it,
walk-forward measures it. Rank first, code one, test one, keep a novel buffer.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

from config.settings import PROJECT_ROOT

logger = logging.getLogger(__name__)

CATALOG_RANKING_PATH = PROJECT_ROOT / "data" / "catalog_ranking.json"
# Append-only memory of finished family@clock[@side] grids. Survives a jobs
# ledger rewrite so Desk Head cannot treat CLOCK_BY_FAMILY as a fresh backlog.
WALK_FORWARD_HISTORY_PATH = PROJECT_ROOT / "data" / "walk_forward_history.json"

# Cannot be the next coding or walk-forward mandate until the feed exists.
FAMILIES_NEEDING_FEED = frozenset({"funding_fade"})
# Legacy baseline. Walk-forward already measured it; replenish must not clone it.
NEVER_REPLENISH_FAMILIES = frozenset({"rsi_trend", "rsi_golden_cross"})
# A family is done with auto clock clones once both of these have 0 approvals.
RESEARCH_METHOD = (
    "Desk Head (GM) owns walk-forward slots. Sleeve Engineer owns coding and "
    "standby. Quant owns catalog depth. Strategy Advisor watches the GM. "
    "Walk-forward is the only writer of approved_strategies.json. Tier A "
    "research advances without Inbox; paper-to-live is still a hard human "
    "gate. Paper may scan unapproved candidates. Live cannot."
)

RESEARCH_LESSONS: list[str] = [
    (
        "15m trend-following overtrades after costs. Donchian LONGs printed "
        "1173–1271 OOS trades with PF 0.68–0.79 and 29–36% drawdown. RSI on "
        "the same clock failed the same way."
    ),
    (
        "Slowing Donchian LONG to 1h was not enough: still ~500 OOS trades, "
        "PF 0.81–0.88, negative expectancy."
    ),
    (
        "4h Donchian shorts were the only sleeve close to the gates (PF "
        "1.17–1.24, positive expectancy) but still failed fold stability and "
        "the confidence interval. Next tests should start slow (4h), not 15m."
    ),
    (
        "Chop is the common BTC regime in sample. Another raw breakout on a "
        "fast clock is repeating a bet the data already rejected."
    ),
]

RESEARCH_FAMILIES: list[dict[str, Any]] = [
    {
        "id": "rsi_trend",
        "name": "RSI pullback + golden cross",
        "status": "rejected",
        "coded": True,
        "rank": 0,
        "summary": (
            "The legacy sleeve. Walk-forward expectancy is negative after costs. "
            "It stays in the book as the honest baseline, not as a live idea."
        ),
        "next_step": "Do not retest unless you can name why the previous test was invalid.",
    },
    {
        "id": "donchian_breakout",
        "name": "Donchian channel breakout",
        "status": "rejected",
        "coded": True,
        "rank": 0,
        "summary": (
            "Classic CTA: enter when close breaks the prior N-bar high (long) or "
            "low (short). Walk-forward on majors failed at both 15m/4h and 1h/4h "
            "after costs."
        ),
        "next_step": "Family rejected. Clock/side follow-ups live in the Next tests queue, not a re-run of this card.",
    },
    {
        "id": "ema_adx_trend",
        "name": "EMA trend + ADX pullback",
        "status": "rejected",
        "coded": True,
        "rank": 1,
        "summary": (
            "Ride the EMA trend only when ADX confirms strength; enter on a "
            "pullback to the fast EMA rather than a raw breakout. 4h clock. "
            "Walk-forward on majors rejected after costs (0 of 6). Integrity "
            "certified the setup (4h/4h, costs charged, verdicts written)."
        ),
        "next_step": "Family rejected. Next tests are ranked clock/side variants on this tab, not a new indicator.",
    },
    {
        "id": "bollinger_mean_reversion",
        "name": "Bollinger fade in chop",
        "status": "rejected",
        "coded": True,
        "rank": 2,
        "summary": (
            "Fade a 4h stretch only when ADX is weak. Chop was the common regime; "
            "this is the opposite bet from Donchian. Walk-forward on majors "
            "rejected after costs (0 of 6). Integrity certified the 4h/4h setup."
        ),
        "next_step": "Family rejected. Next tests are ranked clock/side variants on this tab, not a new indicator.",
    },
    {
        "id": "trend_pullback_htf",
        "name": "4h trend, 1h pullback",
        "status": "rejected",
        "coded": True,
        "rank": 3,
        "clock": "1h/1h",
        "summary": (
            "4h EMA/ADX trend with a 1h pullback entry. Walk-forward on majors "
            "at 1h/1h rejected after costs (0 of 6). Integrity certified the setup."
        ),
        "next_step": "Family rejected. Next tests are ranked clock/side variants on this tab.",
    },
    {
        "id": "atr_channel_breakout",
        "name": "ATR channel breakout (4h)",
        "status": "rejected",
        "coded": True,
        "rank": 5,
        "clock": "4h/4h",
        "summary": (
            "Keltner-style: enter when close breaks the prior bar's EMA ± k·ATR. "
            "Walk-forward on majors at 4h/4h rejected after costs (0 of 6). "
            "Same breakout family as Donchian; shorts were closer (PF 1.20–1.27) "
            "but failed stability / CI gates."
        ),
        "next_step": (
            "This 4h/4h card is done. Follow-ups (other clocks, SHORT-only) "
            "are in the Next tests queue — that is the live catalog."
        ),
    },
    {
        "id": "funding_fade",
        "name": "Funding-rate fade",
        "status": "queued",
        "coded": False,
        "rank": 4,
        "summary": (
            "Fade crowded perp positioning when funding is extreme and price is "
            "stretched. Crypto-native edge; needs a funding feed."
        ),
        "next_step": "Tier C: needs a funding feed. Not the next walk-forward. Do not jump the coded queue.",
    },
]

RESEARCH_BACKLOG: list[dict[str, Any]] = [
    {
        "id": "bb_squeeze_breakout",
        "name": "Bollinger squeeze then ATR break",
        "status": "queued",
        "coded": True,
        "rank": 10,
        "clock": "4h/4h",
        "summary": (
            "Break an ATR channel only after Bollinger width printed an N-bar low. "
            "Not a clock clone of Donchian or raw ATR breakout."
        ),
        "next_step": "Walk-forward 4h/4h both sides (auto-coded spec).",
    },
    {
        "id": "rsi_fade_chop",
        "name": "RSI fade in chop",
        "status": "queued",
        "coded": True,
        "rank": 11,
        "clock": "4h/4h",
        "summary": "Fade RSI extremes only when ADX is weak. Opposite bet from rsi_trend.",
        "next_step": "Walk-forward 4h/4h both sides (auto-coded spec).",
    },
    {
        "id": "macd_trend_pullback",
        "name": "MACD trend, RSI pullback",
        "status": "queued",
        "coded": True,
        "rank": 12,
        "clock": "4h/4h",
        "summary": "MACD regime plus RSI pullback. Not an EMA-tag rename of ema_adx_trend.",
        "next_step": "Walk-forward 4h/4h both sides (auto-coded spec).",
    },
    {
        "id": "atr_fade_chop",
        "name": "ATR channel fade in chop",
        "status": "queued",
        "coded": True,
        "rank": 13,
        "clock": "4h/4h",
        "summary": "Fade ATR-channel extremes when ADX is weak. Opposite of atr_channel_breakout.",
        "next_step": "Walk-forward 4h/4h both sides (auto-coded spec).",
    },
    {
        "id": "volume_climax_fade",
        "name": "Volume climax RSI fade",
        "status": "queued",
        "coded": True,
        "rank": 14,
        "clock": "4h/4h",
        "summary": "Fade an RSI extreme only on a volume spike.",
        "next_step": "Walk-forward 4h/4h both sides (auto-coded spec).",
    },
    {
        "id": "opening_range_breakout",
        "name": "UTC opening-range breakout",
        "status": "queued",
        "coded": True,
        "rank": 15,
        "clock": "1h/1h",
        "summary": (
            "Break the first N-hour range of the UTC day. Session math lives in "
            "core/strategy/opening_range_breakout.py — not a Donchian rename."
        ),
        "next_step": "Walk-forward 1h/1h both sides. Sleeve Engineer owns standby; Desk Head owns the slot.",
    },
    {
        "id": "utc_session_vwap_reversion",
        "name": "UTC-day VWAP fade",
        "status": "queued",
        "coded": True,
        "rank": 16,
        "clock": "1h/1h",
        "summary": "Fade stretch away from VWAP that resets at UTC midnight.",
        "next_step": "Walk-forward 1h/1h both sides. Sleeve is in core/strategy/utc_session_vwap_reversion.py.",
    },
    {
        "id": "asian_range_breakout",
        "name": "Asian session range break",
        "status": "queued",
        "coded": True,
        "rank": 17,
        "clock": "1h/1h",
        "summary": "Break the 00:00–08:00 UTC range after that window has closed.",
        "next_step": "Walk-forward 1h/1h both sides. Sleeve is in core/strategy/asian_range_breakout.py.",
    },
    {
        "id": "inside_bar_breakout",
        "name": "Inside-bar mother-bar break",
        "status": "queued",
        "coded": True,
        "rank": 18,
        "clock": "4h/4h",
        "summary": "Break the mother bar after a full inside bar.",
        "next_step": "Walk-forward 4h/4h both sides. Sleeve is in core/strategy/inside_bar_breakout.py.",
    },
    {
        "id": "swing_failure_reversal",
        "name": "Swing-failure fade",
        "status": "queued",
        "coded": True,
        "rank": 19,
        "clock": "4h/4h",
        "summary": "Fade a failed break of the last swing high or low.",
        "next_step": "Walk-forward 4h/4h both sides. Sleeve is in core/strategy/swing_failure_reversal.py.",
    },
    {
        "id": "consecutive_bar_exhaustion",
        "name": "Consecutive-close exhaustion",
        "status": "queued",
        "coded": True,
        "rank": 20,
        "clock": "4h/4h",
        "summary": "Fade after a run of closes in one direction.",
        "next_step": "Walk-forward 4h/4h both sides. Sleeve is in core/strategy/consecutive_bar_exhaustion.py.",
    },
    {
        "id": "wick_rejection_reversal",
        "name": "Wick-rejection reversal",
        "status": "queued",
        "coded": True,
        "rank": 21,
        "clock": "1h/1h",
        "summary": "Enter when a long wick rejects and the close comes back inside.",
        "next_step": "Walk-forward 1h/1h both sides. Sleeve is in core/strategy/wick_rejection_reversal.py.",
    },
    {
        "id": "prior_day_pivot_breakout",
        "name": "Prior-day floor pivots",
        "status": "queued",
        "coded": True,
        "rank": 22,
        "clock": "1h/1h",
        "summary": "Break prior UTC-day pivot / R1 / S1 after that day has closed.",
        "next_step": "Walk-forward 1h/1h both sides. Sleeve is in core/strategy/prior_day_pivot_breakout.py.",
    },
    {
        "id": "weekend_gap_fill",
        "name": "Weekend gap fill",
        "status": "queued",
        "coded": True,
        "rank": 23,
        "clock": "4h/4h",
        "summary": "Fade or fill the weekend gap versus Friday's UTC close.",
        "next_step": "Walk-forward 4h/4h both sides. Sleeve is in core/strategy/weekend_gap_fill.py.",
    },
    {
        "id": "engulfing_reversal",
        "name": "Engulfing reversal",
        "status": "queued",
        "coded": True,
        "rank": 24,
        "clock": "4h/4h",
        "summary": "Reverse when a bar's body fully engulfs the prior body.",
        "next_step": "Walk-forward 4h/4h both sides. Sleeve is in core/strategy/engulfing_reversal.py.",
    },
    {
        "id": "utc_midnight_gap_fill",
        "name": "UTC midnight gap fade",
        "status": "queued",
        "coded": True,
        "rank": 25,
        "clock": "1h/1h",
        "summary": "Fade the UTC-midnight gap back toward the prior day's close.",
        "next_step": "Walk-forward 1h/1h both sides. Sleeve is in core/strategy/utc_midnight_gap_fill.py.",
    },
    {
        "id": "london_session_breakout",
        "name": "London session range break",
        "status": "queued",
        "coded": False,
        "rank": 26,
        "clock": "1h/1h",
        "summary": "Break the 08:00–16:00 UTC range after that window has closed.",
        "next_step": "Inbox: approve the brief, then Cursor implements london_session_breakout.",
    },
    {
        "id": "ny_cash_open_drive",
        "name": "US cash-open drive",
        "status": "queued",
        "coded": False,
        "rank": 27,
        "clock": "1h/1h",
        "summary": "Trade in the direction of the 13:00–14:00 UTC cash-open hour.",
        "next_step": "Inbox: approve the brief, then Cursor implements ny_cash_open_drive.",
    },
    {
        "id": "three_bar_play",
        "name": "Three-bar play",
        "status": "queued",
        "coded": False,
        "rank": 28,
        "clock": "4h/4h",
        "summary": "Break the rest bar of a 3-bar play.",
        "next_step": "Inbox: approve the brief, then Cursor implements three_bar_play.",
    },
    {
        "id": "outside_bar_reversal",
        "name": "Outside-bar reversal",
        "status": "queued",
        "coded": False,
        "rank": 29,
        "clock": "4h/4h",
        "summary": "Reverse in the close direction of an outside bar.",
        "next_step": "Inbox: approve the brief, then Cursor implements outside_bar_reversal.",
    },
    {
        "id": "doji_star_reversal",
        "name": "Doji-star reversal",
        "status": "queued",
        "coded": False,
        "rank": 30,
        "clock": "4h/4h",
        "summary": "Fade after a doji that prints following a directional run.",
        "next_step": "Inbox: approve the brief, then Cursor implements doji_star_reversal.",
    },
    {
        "id": "round_number_fade",
        "name": "Round-number fade",
        "status": "queued",
        "coded": False,
        "rank": 31,
        "clock": "1h/1h",
        "summary": "Fade a rejection of a round psychological price.",
        "next_step": "Inbox: approve the brief, then Cursor implements round_number_fade.",
    },
    {
        "id": "prior_week_high_break",
        "name": "Prior-week high/low break",
        "status": "queued",
        "coded": False,
        "rank": 32,
        "clock": "4h/4h",
        "summary": "Break the prior UTC week's high or low after that week has closed.",
        "next_step": "Inbox: approve the brief, then Cursor implements prior_week_high_break.",
    },
    {
        "id": "utc_session_twap_reversion",
        "name": "UTC-day TWAP fade",
        "status": "queued",
        "coded": False,
        "rank": 33,
        "clock": "1h/1h",
        "summary": "Fade stretch away from TWAP that resets at UTC midnight.",
        "next_step": "Inbox: approve the brief, then Cursor implements utc_session_twap_reversion.",
    },
    {
        "id": "failed_higher_high",
        "name": "Failed higher-high",
        "status": "queued",
        "coded": False,
        "rank": 34,
        "clock": "4h/4h",
        "summary": "Fade a failed higher-high against the prior swing high.",
        "next_step": "Inbox: approve the brief, then Cursor implements failed_higher_high.",
    },
    {
        "id": "nr7_breakout",
        "name": "NR7 breakout",
        "status": "queued",
        "coded": False,
        "rank": 35,
        "clock": "4h/4h",
        "summary": "Break the NR7 bar after the narrowest of 7 prints.",
        "next_step": "Inbox: approve the brief, then Cursor implements nr7_breakout.",
    },
]

# Ranked hypotheses: new coded families first, then near-miss param grids.
# Unique key is family@clock@side. Do not re-queue an unchanged test.
RESEARCH_HYPOTHESES: list[dict[str, Any]] = [
    {
        "id": "opening_range_breakout@1h/1h",
        "family": "opening_range_breakout",
        "name": "UTC opening-range 1h both sides",
        "clock": "1h/1h",
        "side": "BOTH",
        "rank": 0,
        "coded": True,
        "free_params": 3,
        "disposition": "retest_under_different_regime",
        "justification": (
            "First coded session-range sleeve. Clock is 1h/1h BOTH. Not a silent "
            "re-run of Donchian or ATR channel — the range is the UTC opening window."
        ),
        "param_change": {"clock": "1h/1h", "range_hours": [1, 2]},
        "needs_feed": False,
    },
    {
        "id": "utc_session_vwap_reversion@1h/1h",
        "family": "utc_session_vwap_reversion",
        "name": "UTC VWAP fade 1h both sides",
        "clock": "1h/1h",
        "side": "BOTH",
        "rank": 16,
        "coded": True,
        "free_params": 3,
        "disposition": "new_family",
        "justification": "Operator-approved novel sleeve. First walk-forward at 1h/1h BOTH.",
        "param_change": {"clock": "1h/1h"},
        "needs_feed": False,
    },
    {
        "id": "asian_range_breakout@1h/1h",
        "family": "asian_range_breakout",
        "name": "Asian range 1h both sides",
        "clock": "1h/1h",
        "side": "BOTH",
        "rank": 17,
        "coded": True,
        "free_params": 3,
        "disposition": "new_family",
        "justification": "Operator-approved novel sleeve. First walk-forward at 1h/1h BOTH.",
        "param_change": {"clock": "1h/1h"},
        "needs_feed": False,
    },
    {
        "id": "inside_bar_breakout@4h/4h",
        "family": "inside_bar_breakout",
        "name": "Inside-bar 4h both sides",
        "clock": "4h/4h",
        "side": "BOTH",
        "rank": 18,
        "coded": True,
        "free_params": 2,
        "disposition": "new_family",
        "justification": "Operator-approved novel sleeve. First walk-forward at 4h/4h BOTH.",
        "param_change": {"clock": "4h/4h"},
        "needs_feed": False,
    },
    {
        "id": "swing_failure_reversal@4h/4h",
        "family": "swing_failure_reversal",
        "name": "Swing-failure 4h both sides",
        "clock": "4h/4h",
        "side": "BOTH",
        "rank": 19,
        "coded": True,
        "free_params": 3,
        "disposition": "new_family",
        "justification": "Operator-approved novel sleeve. First walk-forward at 4h/4h BOTH.",
        "param_change": {"clock": "4h/4h"},
        "needs_feed": False,
    },
    {
        "id": "consecutive_bar_exhaustion@4h/4h",
        "family": "consecutive_bar_exhaustion",
        "name": "Consecutive-close fade 4h both sides",
        "clock": "4h/4h",
        "side": "BOTH",
        "rank": 20,
        "coded": True,
        "free_params": 3,
        "disposition": "new_family",
        "justification": "Operator-approved novel sleeve. First walk-forward at 4h/4h BOTH.",
        "param_change": {"clock": "4h/4h"},
        "needs_feed": False,
    },
    {
        "id": "wick_rejection_reversal@1h/1h",
        "family": "wick_rejection_reversal",
        "name": "Wick rejection 1h both sides",
        "clock": "1h/1h",
        "side": "BOTH",
        "rank": 21,
        "coded": True,
        "free_params": 3,
        "disposition": "new_family",
        "justification": "Operator-approved novel sleeve. First walk-forward at 1h/1h BOTH.",
        "param_change": {"clock": "1h/1h"},
        "needs_feed": False,
    },
    {
        "id": "prior_day_pivot_breakout@1h/1h",
        "family": "prior_day_pivot_breakout",
        "name": "Prior-day pivots 1h both sides",
        "clock": "1h/1h",
        "side": "BOTH",
        "rank": 22,
        "coded": True,
        "free_params": 2,
        "disposition": "new_family",
        "justification": "Operator-approved novel sleeve. First walk-forward at 1h/1h BOTH.",
        "param_change": {"clock": "1h/1h"},
        "needs_feed": False,
    },
    {
        "id": "weekend_gap_fill@4h/4h",
        "family": "weekend_gap_fill",
        "name": "Weekend gap 4h both sides",
        "clock": "4h/4h",
        "side": "BOTH",
        "rank": 23,
        "coded": True,
        "free_params": 2,
        "disposition": "new_family",
        "justification": "Operator-approved novel sleeve. First walk-forward at 4h/4h BOTH.",
        "param_change": {"clock": "4h/4h"},
        "needs_feed": False,
    },
    {
        "id": "engulfing_reversal@4h/4h",
        "family": "engulfing_reversal",
        "name": "Engulfing 4h both sides",
        "clock": "4h/4h",
        "side": "BOTH",
        "rank": 24,
        "coded": True,
        "free_params": 2,
        "disposition": "new_family",
        "justification": "Operator-approved novel sleeve. First walk-forward at 4h/4h BOTH.",
        "param_change": {"clock": "4h/4h"},
        "needs_feed": False,
    },
    {
        "id": "utc_midnight_gap_fill@1h/1h",
        "family": "utc_midnight_gap_fill",
        "name": "UTC midnight gap 1h both sides",
        "clock": "1h/1h",
        "side": "BOTH",
        "rank": 25,
        "coded": True,
        "free_params": 2,
        "disposition": "new_family",
        "justification": "Operator-approved novel sleeve. First walk-forward at 1h/1h BOTH.",
        "param_change": {"clock": "1h/1h"},
        "needs_feed": False,
    },
    {
        "id": "atr_channel_breakout@1h/1h",
        "family": "atr_channel_breakout",
        "name": "ATR channel 1h, frozen ADX",
        "clock": "1h/1h",
        "side": "BOTH",
        "rank": 1,
        "coded": True,
        "free_params": 3,
        "disposition": "re-parameterise",
        "justification": (
            "4h/4h shorts were closest (PF 1.20-1.27) but min_adx flipped across "
            "folds. 1h/1h adds bars; atr_k stays [2.0, 2.5]; min_adx frozen at 20."
        ),
        "param_change": {"min_adx": [20.0], "atr_k": [2.0, 2.5]},
        "needs_feed": False,
    },
    {
        "id": "ema_adx_trend@1h/1h",
        "family": "ema_adx_trend",
        "name": "EMA + ADX on 1h",
        "clock": "1h/1h",
        "side": "BOTH",
        "rank": 2,
        "coded": True,
        "free_params": 4,
        "disposition": "retest_under_different_regime",
        "justification": (
            "4h/4h rejected after costs. A 1h clock is a different sample, not "
            "a silent re-run of the failed 4h grid."
        ),
        "param_change": {"clock": "1h/1h"},
        "needs_feed": False,
    },
    {
        "id": "bollinger_mean_reversion@1h/1h",
        "family": "bollinger_mean_reversion",
        "name": "Bollinger fade on 1h",
        "clock": "1h/1h",
        "side": "BOTH",
        "rank": 3,
        "coded": True,
        "free_params": 4,
        "disposition": "retest_under_different_regime",
        "justification": (
            "4h fade failed fold stability. 1h is a different holding period "
            "on the same coded sleeve."
        ),
        "param_change": {"clock": "1h/1h"},
        "needs_feed": False,
    },
    {
        "id": "donchian_breakout@4h/4h",
        "family": "donchian_breakout",
        "name": "Donchian 4h both sides",
        "clock": "4h/4h",
        "side": "BOTH",
        "rank": 4,
        "coded": True,
        "free_params": 4,
        "disposition": "retest_under_different_regime",
        "justification": (
            "15m and 1h/4h overtraded. 4h shorts were the only near-miss on "
            "that family; test the slow clock on both sides."
        ),
        "param_change": {"clock": "4h/4h"},
        "needs_feed": False,
    },
    {
        "id": "atr_channel_breakout@1h/4h",
        "family": "atr_channel_breakout",
        "name": "ATR channel 1h long / 4h short",
        "clock": "1h/4h",
        "side": "BOTH",
        "rank": 5,
        "coded": True,
        "free_params": 3,
        "disposition": "retest_under_different_regime",
        "justification": (
            "Asymmetric clock: longs on 1h, shorts on the 4h near-miss. "
            "min_adx stays frozen."
        ),
        "param_change": {"clock": "1h/4h", "min_adx": [20.0]},
        "needs_feed": False,
    },
    {
        "id": "trend_pullback_htf@4h/4h",
        "family": "trend_pullback_htf",
        "name": "HTF pullback on 4h",
        "clock": "4h/4h",
        "side": "BOTH",
        "rank": 6,
        "coded": True,
        "free_params": 4,
        "disposition": "retest_under_different_regime",
        "justification": "1h/1h rejected. Slow the entry clock to 4h.",
        "param_change": {"clock": "4h/4h"},
        "needs_feed": False,
    },
    {
        "id": "ema_adx_trend@1h/4h",
        "family": "ema_adx_trend",
        "name": "EMA + ADX 1h/4h",
        "clock": "1h/4h",
        "side": "BOTH",
        "rank": 7,
        "coded": True,
        "free_params": 4,
        "disposition": "retest_under_different_regime",
        "justification": "Asymmetric clock after a failed 4h/4h square test.",
        "param_change": {"clock": "1h/4h"},
        "needs_feed": False,
    },
    {
        "id": "bollinger_mean_reversion@1h/4h",
        "family": "bollinger_mean_reversion",
        "name": "Bollinger 1h/4h",
        "clock": "1h/4h",
        "side": "BOTH",
        "rank": 8,
        "coded": True,
        "free_params": 4,
        "disposition": "retest_under_different_regime",
        "justification": "Chop fade on mixed clocks after 4h/4h reject.",
        "param_change": {"clock": "1h/4h"},
        "needs_feed": False,
    },
    {
        "id": "rsi_trend@4h/4h",
        "family": "rsi_trend",
        "name": "RSI trend on 4h",
        "clock": "4h/4h",
        "side": "BOTH",
        "rank": 9,
        "coded": True,
        "free_params": 5,
        "disposition": "retest_under_different_regime",
        "justification": (
            "15m RSI overtraded after costs. 4h is the clock the other "
            "families needed; this is not a re-run of the 15m test."
        ),
        "param_change": {"clock": "4h/4h"},
        "needs_feed": False,
    },
    {
        "id": "donchian_breakout@4h/4h@SHORT",
        "family": "donchian_breakout",
        "name": "Donchian 4h shorts only",
        "clock": "4h/4h",
        "side": "SHORT",
        "rank": 10,
        "coded": True,
        "free_params": 4,
        "disposition": "re-parameterise",
        "justification": (
            "4h Donchian shorts were the original near-miss (PF 1.17-1.24). "
            "Drop the long side that overtraded."
        ),
        "param_change": {"side": "SHORT", "clock": "4h/4h"},
        "needs_feed": False,
    },
    {
        "id": "atr_channel_breakout@4h/4h@SHORT",
        "family": "atr_channel_breakout",
        "name": "ATR 4h shorts, frozen ADX",
        "clock": "4h/4h",
        "side": "SHORT",
        "rank": 11,
        "coded": True,
        "free_params": 2,
        "disposition": "re-parameterise",
        "justification": (
            "4h BOTH failed. Shorts were closest. Retest SHORT only with "
            "min_adx frozen so folds cannot flip the filter."
        ),
        "param_change": {"side": "SHORT", "min_adx": [20.0]},
        "needs_feed": False,
    },
    {
        "id": "ema_adx_trend@4h/4h@frozen_adx",
        "family": "ema_adx_trend",
        "name": "EMA + ADX 4h frozen ADX",
        "clock": "4h/4h",
        "side": "BOTH",
        "rank": 12,
        "coded": True,
        "free_params": 3,
        "disposition": "re-parameterise",
        "justification": (
            "Same 4h clock as the reject, but min_adx frozen at 20 so the "
            "fold-unstable filter is not a free parameter."
        ),
        "param_change": {"min_adx": [20.0]},
        "needs_feed": False,
    },
    {
        "id": "trend_pullback_htf@1h/4h",
        "family": "trend_pullback_htf",
        "name": "HTF pullback 1h/4h",
        "clock": "1h/4h",
        "side": "BOTH",
        "rank": 13,
        "coded": True,
        "free_params": 4,
        "disposition": "retest_under_different_regime",
        "justification": "1h/1h rejected. Mix the entry clock with a slower short.",
        "param_change": {"clock": "1h/4h"},
        "needs_feed": False,
    },
    {
        "id": "rsi_trend@1h/1h",
        "family": "rsi_trend",
        "name": "RSI trend on 1h",
        "clock": "1h/1h",
        "side": "BOTH",
        "rank": 14,
        "coded": True,
        "free_params": 5,
        "disposition": "retest_under_different_regime",
        "justification": "15m overtraded. 1h is slower without jumping to 4h.",
        "param_change": {"clock": "1h/1h"},
        "needs_feed": False,
    },
    {
        "id": "bollinger_mean_reversion@4h/4h@tight",
        "family": "bollinger_mean_reversion",
        "name": "Bollinger 4h tighter bands",
        "clock": "4h/4h",
        "side": "BOTH",
        "rank": 15,
        "coded": True,
        "free_params": 3,
        "disposition": "re-parameterise",
        "justification": (
            "Same 4h clock, band_k frozen at 2.5 so the fold cannot pick "
            "the noisier 2.0 setting."
        ),
        "param_change": {"band_k": [2.5]},
        "needs_feed": False,
    },
]


def hypothesis_key(family: str, clock: str, side: str = "BOTH") -> str:
    side_u = (side or "BOTH").upper()
    if side_u == "BOTH":
        return f"{family}@{clock}"
    return f"{family}@{clock}@{side_u}"


def coverage_keys(family: str, clock: str, side: str = "BOTH") -> set[str]:
    """Keys this job occupies so we do not launch a silent sibling.

    BOTH consumes SHORT and LONG on the same clock. A one-sided run consumes
    BOTH as well so we never re-test those shorts/longs as a 6-pair BOTH.
    """
    side_u = (side or "BOTH").upper()
    keys = {hypothesis_key(family, clock, side_u)}
    if not family or not clock:
        return keys
    if side_u == "BOTH":
        keys.add(hypothesis_key(family, clock, "SHORT"))
        keys.add(hypothesis_key(family, clock, "LONG"))
    else:
        keys.add(hypothesis_key(family, clock, "BOTH"))
    return keys


def _retired_families(overlay: dict[str, Any] | None = None) -> set[str]:
    data = overlay if overlay is not None else _ranking_overlay()
    extra = {str(x) for x in (data.get("retired_families") or []) if x}
    return set(NEVER_REPLENISH_FAMILIES) | extra


def family_has_approval(jobs: list[dict[str, Any]], family: str) -> bool:
    return any(
        str(job.get("family") or "") == family and int(job.get("pairs_approved") or 0) > 0
        for job in jobs
    )


def family_primary_clock(family: str) -> str:
    """The first clock this sleeve is supposed to walk. Extra clocks wait on a verdict."""
    from firm.sleeve_factory import spec_for_family
    from firm.research_jobs import CLOCK_BY_FAMILY

    spec = spec_for_family(family)
    if spec is not None and spec.clock:
        return spec.clock
    return CLOCK_BY_FAMILY.get(family, "4h/4h")


def primary_clocks_failed(jobs: list[dict[str, Any]], family: str) -> bool:
    """True when the family's first intended clock finished with zero approvals.

    Requiring both 4h/4h and 1h/1h used to force a 1h clone after a 4h 0-for-6.
    Extra clocks are a near-miss retest, not an automatic consolation prize.
    """
    clock = family_primary_clock(family)
    tested = hypothesis_tested_keys(jobs)
    if hypothesis_key(family, clock, "BOTH") not in tested:
        return False
    relevant = [
        job
        for job in jobs
        if str(job.get("family") or "") == family
        and str(job.get("clock") or "") == clock
        and job.get("status") in {"done", "failed"}
    ]
    if not relevant:
        return False
    return all(int(job.get("pairs_approved") or 0) == 0 for job in relevant)


def family_blocked_from_replenish(
    family: str, jobs: list[dict[str, Any]] | None = None
) -> bool:
    """Stop cloning clocks of a family that already failed the primary grid."""
    if not family or family in FAMILIES_NEEDING_FEED:
        return True
    if family in NEVER_REPLENISH_FAMILIES:
        return True
    if family in _retired_families():
        return True
    if jobs is None:
        return False
    if family_has_approval(jobs, family):
        return False
    # Peak PF 0 on a tested sleeve is a clear loss even if 1h/1h never ran.
    # Do not keep offering utc_midnight / London clock clones as "next".
    if is_clear_loss_family(family, jobs):
        return True
    return primary_clocks_failed(jobs, family)


def _ranking_overlay() -> dict[str, Any]:
    """Post-mortems write ranks here so a reject mutates order without a git edit."""
    path = CATALOG_RANKING_PATH
    if not path.exists():
        return {}
    import json

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return raw if isinstance(raw, dict) else {}


def ranked_hypotheses() -> list[dict[str, Any]]:
    """Catalog hypotheses with post-mortem rank overlays applied."""
    overlay = _ranking_overlay()
    ranks = overlay.get("ranks") if isinstance(overlay.get("ranks"), dict) else {}
    retired = set(overlay.get("retired") or [])
    rows: list[dict[str, Any]] = []
    for row in RESEARCH_HYPOTHESES:
        hid = str(row.get("id") or "")
        if hid in retired:
            continue
        item = dict(row)
        if hid in ranks:
            try:
                item["rank"] = int(ranks[hid])
            except (TypeError, ValueError):
                pass
        if hid in (overlay.get("justifications") or {}):
            item["justification"] = overlay["justifications"][hid]
        if hid in (overlay.get("dispositions") or {}):
            item["disposition"] = overlay["dispositions"][hid]
        rows.append(item)
    added = overlay.get("added") if isinstance(overlay.get("added"), list) else []
    seen = {str(r.get("id") or "") for r in rows}
    for row in added:
        if not isinstance(row, dict):
            continue
        hid = str(row.get("id") or "")
        if not hid or hid in seen or hid in retired:
            continue
        item = dict(row)
        if hid in ranks:
            try:
                item["rank"] = int(ranks[hid])
            except (TypeError, ValueError):
                pass
        if hid in (overlay.get("justifications") or {}):
            item["justification"] = overlay["justifications"][hid]
        if hid in (overlay.get("dispositions") or {}):
            item["disposition"] = overlay["dispositions"][hid]
        rows.append(item)
        seen.add(hid)
    rows.sort(
        key=lambda r: (
            int(r["rank"]) if r.get("rank") is not None and r.get("rank") != "" else 99,
            str(r.get("id") or ""),
        )
    )
    return rows


def hypothesis_tested_keys(jobs: list[dict[str, Any]]) -> set[str]:
    """family@clock[@side] keys that already finished a walk-forward."""
    out: set[str] = set()
    for job in jobs:
        if job.get("status") not in {"done", "failed"}:
            continue
        family = str(job.get("family") or "")
        clock = str(job.get("clock") or "")
        side = str(job.get("side") or "BOTH")
        if family and clock:
            out.update(coverage_keys(family, clock, side))
    return out


def _atomic_write_json(path: Any, payload: dict[str, Any]) -> None:
    """Write-then-rename so a crash cannot leave a truncated catalog file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _empty_walk_forward_history() -> dict[str, Any]:
    return {
        "updated_at": "",
        "max_job_id": 0,
        "grids": [],
        "hypothesis_ids": [],
    }


def load_walk_forward_history() -> dict[str, Any]:
    """Durable finished-grid index. Empty file or missing file is a cold start."""
    path = WALK_FORWARD_HISTORY_PATH
    base = _empty_walk_forward_history()
    if not path.exists():
        bak = path.with_suffix(path.suffix + ".bak")
        path = bak if bak.exists() else path
    if not path.exists():
        return base
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        logger.exception("Walk-forward history unreadable at %s", path)
        return {**base, "_corrupt": True}
    if not isinstance(raw, dict):
        return {**base, "_corrupt": True}
    base.update(raw)
    base["grids"] = [str(x) for x in (base.get("grids") or []) if x]
    base["hypothesis_ids"] = [str(x) for x in (base.get("hypothesis_ids") or []) if x]
    try:
        base["max_job_id"] = int(base.get("max_job_id") or 0)
    except (TypeError, ValueError):
        base["max_job_id"] = 0
    return base


def history_grid_keys() -> set[str]:
    return set(load_walk_forward_history().get("grids") or [])


def history_hypothesis_ids() -> set[str]:
    return set(load_walk_forward_history().get("hypothesis_ids") or [])


def history_max_job_id() -> int:
    return int(load_walk_forward_history().get("max_job_id") or 0)


def paper_book_finished_keys() -> set[str]:
    """family@clock[@side] keys already measured on the paper/approvals book.

    Presence in approved_strategies.json means a walk-forward wrote a verdict
    (approved or rejected). Auto-advance must not re-run that grid to fill a slot.
    """
    from config.universe import APPROVALS_PATH

    out: set[str] = set()
    if not APPROVALS_PATH.exists():
        return out
    try:
        raw = json.loads(APPROVALS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return out
    if not isinstance(raw, dict):
        return out
    for key, row in raw.items():
        if not key or str(key).startswith("_"):
            continue
        parts = str(key).split(":")
        family = ""
        side = "BOTH"
        tf = ""
        if len(parts) >= 4:
            family, _symbol, side, tf = parts[0], parts[1], parts[2], parts[3]
        elif len(parts) == 3:
            family, _symbol, side = parts[0], parts[1], parts[2]
            if isinstance(row, dict):
                tf = str(row.get("timeframe") or "")
        if not family or not tf:
            continue
        clock = f"{tf}/{tf}"
        out.update(coverage_keys(family, clock, str(side or "BOTH").upper()))
    return out


def durable_tested_keys(jobs: list[dict[str, Any]] | None = None) -> set[str]:
    """Jobs + append-only history + paper book. Used after a ledger id reset."""
    rows = jobs if jobs is not None else []
    return hypothesis_tested_keys(rows) | history_grid_keys() | paper_book_finished_keys()


def record_finished_walk_forward(job: dict[str, Any]) -> None:
    """Remember this family@clock@side even if research_jobs.json is later rewritten."""
    family = str(job.get("family") or "")
    clock = str(job.get("clock") or "")
    side = str(job.get("side") or "BOTH")
    hid = str(job.get("hypothesis_id") or job.get("id") or "")
    try:
        job_id = int(job.get("id") or 0)
    except (TypeError, ValueError):
        job_id = 0
    if not family or not clock:
        return
    data = load_walk_forward_history()
    if data.get("_corrupt"):
        logger.error("Refusing to overwrite corrupt walk-forward history")
        return
    grids = set(data.get("grids") or [])
    grids.update(coverage_keys(family, clock, side))
    ids = set(data.get("hypothesis_ids") or [])
    if hid:
        ids.add(str(hid))
    data["grids"] = sorted(grids)
    data["hypothesis_ids"] = sorted(ids)
    data["max_job_id"] = max(int(data.get("max_job_id") or 0), job_id)
    data["updated_at"] = _utcnow_iso()
    data.pop("_corrupt", None)
    path = WALK_FORWARD_HISTORY_PATH
    bak = path.with_suffix(path.suffix + ".bak")
    if path.exists():
        try:
            os.replace(path, bak)
        except OSError:
            logger.exception("Could not rotate walk-forward history bak")
    _atomic_write_json(path, data)


def note_job_id(job_id: int) -> None:
    """Keep the id sequencer above any ledger rewrite that restarted at 1."""
    try:
        n = int(job_id or 0)
    except (TypeError, ValueError):
        return
    if n <= 0:
        return
    data = load_walk_forward_history()
    if data.get("_corrupt"):
        logger.error("Refusing to overwrite corrupt walk-forward history")
        return
    if n <= int(data.get("max_job_id") or 0):
        return
    data["max_job_id"] = n
    data["updated_at"] = _utcnow_iso()
    data.pop("_corrupt", None)
    _atomic_write_json(WALK_FORWARD_HISTORY_PATH, data)


def is_explicit_retest(row: dict[str, Any]) -> bool:
    """Operator-queued frozen near-miss / tagged param grid, not a CLOCK leftover.

    Auto-advance may start these when they are already in remaining/standby.
    It must not invent them to keep walk-forward slots busy.
    """
    hid = str(row.get("id") or row.get("hypothesis_id") or "")
    family = str(row.get("family") or "")
    clock = str(row.get("clock") or "")
    side = str(row.get("side") or "BOTH")
    if not hid or not is_param_variant(
        {"id": hid, "family": family, "clock": clock, "side": side}
    ):
        return False
    if row.get("force_retest") or row.get("operator_queued"):
        return True
    near_miss_ids = {str(r.get("id") or "") for r in NEAR_MISS_RETESTS}
    near_miss_ids.update(str(r.get("id") or "") for r in TODAY_CLOSE_RETESTS)
    if hid in near_miss_ids:
        return True
    if str(row.get("added_by") or "") in {"operator", "test"}:
        return True
    if str(row.get("disposition") or "") == "re-parameterise" and str(
        row.get("added_by") or ""
    ):
        return True
    return False


def auto_advance_grid_spent(
    row: dict[str, Any], *, jobs: list[dict[str, Any]] | None = None
) -> bool:
    """True when Desk Head must not spawn this family/clock/side again.

    Explicit tagged near-miss retests are spent only after that hypothesis_id
    itself has finished. Base CLOCK_BY_FAMILY leftovers are spent when any
    finished job, history row, or paper-book verdict covers the grid.
    """
    family = str(row.get("family") or "")
    clock = str(row.get("clock") or "")
    side = str(row.get("side") or "BOTH")
    hid = str(row.get("id") or row.get("hypothesis_id") or "")
    if jobs is None:
        from firm.research_jobs import list_jobs

        jobs = list_jobs()
    finished_ids = _job_ids_by_status(jobs, {"done", "failed"}) | history_hypothesis_ids()
    if is_explicit_retest(row):
        return bool(hid) and hid in finished_ids
    if not family or not clock:
        return False
    tested = durable_tested_keys(jobs)
    return bool(coverage_keys(family, clock, side) & tested)


def _job_ids_by_status(jobs: list[dict[str, Any]], statuses: set[str]) -> set[str]:
    """hypothesis_id values currently in those statuses."""
    out: set[str] = set()
    for job in jobs:
        if job.get("status") not in statuses:
            continue
        hid = str(job.get("hypothesis_id") or "")
        if hid:
            out.add(hid)
    return out


def is_param_variant(row: dict[str, Any]) -> bool:
    """True when the catalog id has a tag beyond family@clock[@side].

    `bb_squeeze_breakout@4h/4h@LONG@no_adx` must remain after the base
    `family@clock@side` walk-forward already finished. Seed rows whose id
    equals `hypothesis_key` are not variants even if they list param_change.
    """
    hid = str(row.get("id") or "")
    family = str(row.get("family") or "")
    clock = str(row.get("clock") or "")
    side = str(row.get("side") or "BOTH")
    return bool(hid) and hid != hypothesis_key(family, clock, side)


_PEAK_PF_CACHE: tuple[float, dict[str, float]] | None = None


def _family_peak_pf() -> dict[str, float]:
    """Best OOS profit factor per family from the approvals ledger."""
    global _PEAK_PF_CACHE
    from config.universe import APPROVALS_PATH

    mtime = APPROVALS_PATH.stat().st_mtime if APPROVALS_PATH.exists() else 0.0
    if _PEAK_PF_CACHE is not None and _PEAK_PF_CACHE[0] == mtime:
        return _PEAK_PF_CACHE[1]
    peaks: dict[str, float] = {}
    if APPROVALS_PATH.exists():
        try:
            raw = json.loads(APPROVALS_PATH.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            raw = {}
        if isinstance(raw, dict):
            for key, row in raw.items():
                if not isinstance(row, dict):
                    continue
                family = str(row.get("strategy") or "").split(":")[0]
                if not family:
                    parts = str(key).split(":")
                    family = parts[0] if parts else ""
                pf = row.get("oos_profit_factor")
                if not family or not isinstance(pf, (int, float)):
                    continue
                peaks[family] = max(float(pf), peaks.get(family, float("-inf")))
    _PEAK_PF_CACHE = (mtime, peaks)
    return peaks


def is_clear_loss_family(family: str, jobs: list[dict[str, Any]] | None = None) -> bool:
    """True when this sleeve was tested and never came close (no PF >= 1.05, 0 approvals).

    Untested families are not clear losses — they are still eligible if the
    near-miss queue drains overnight.
    """
    if not family:
        return False
    if jobs is None:
        from firm.research_jobs import list_jobs

        jobs = list_jobs()
    tested = any(
        str(job.get("family") or "") == family and job.get("status") in {"done", "failed"}
        for job in jobs
    )
    if not tested:
        return False
    if family_has_approval(jobs, family):
        return False
    peak = _family_peak_pf().get(family)
    if peak is None:
        return True
    return peak < 1.05


def remaining_hypotheses(jobs: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Ranked hypotheses that are not running, standby, or already tested."""
    from core.strategy.registry import list_strategies

    if jobs is None:
        from firm.research_jobs import list_jobs

        jobs = list_jobs()
    # History survives a jobs-ledger id reset. Paper-book skip happens at
    # auto-advance (stage/fill) so catalog tests can isolate jobs + overlay.
    tested = hypothesis_tested_keys(jobs) | history_grid_keys()
    tested_ids = _job_ids_by_status(jobs, {"done", "failed"}) | history_hypothesis_ids()
    busy: set[str] = set()
    for job in jobs:
        if job.get("status") not in {"running", "queued", "standby", "gated"}:
            continue
        family = str(job.get("family") or "")
        clock = str(job.get("clock") or "")
        side = str(job.get("side") or "BOTH")
        if family and clock:
            busy.update(coverage_keys(family, clock, side))
    busy_ids = _job_ids_by_status(jobs, {"running", "queued", "standby", "gated"})
    coded = set(list_strategies())
    blocked = _retired_families()
    near_miss_ids = {str(r.get("id") or "") for r in NEAR_MISS_RETESTS}
    tested_families = {
        str(job.get("family") or "")
        for job in jobs
        if job.get("status") in {"done", "failed"} and job.get("family")
    }
    out: list[dict[str, Any]] = []
    for row in ranked_hypotheses():
        hid = str(row.get("id") or "")
        family = str(row.get("family") or "")
        clock = str(row.get("clock") or "")
        side = str(row.get("side") or "BOTH")
        key = hypothesis_key(family, clock, side)
        variant = is_param_variant(row)
        if variant:
            if hid in tested_ids or hid in busy_ids:
                continue
            change = row.get("param_change") or {}
            frozen = any(k not in {"clock", "side"} for k in change)
            if not frozen:
                continue
            if hid not in near_miss_ids:
                # Seed @tags (frozen_adx / tight) are redundant 0/6 clones.
                # Overlay-added re-parameterise rows are new justified grids.
                if not str(row.get("added_by") or ""):
                    continue
                if str(row.get("disposition") or "") != "re-parameterise":
                    continue
                if is_clear_loss_family(family, jobs):
                    continue
        elif hid in tested or key in tested or key in busy:
            continue
        if family in FAMILIES_NEEDING_FEED or row.get("needs_feed"):
            continue
        if not variant and (family in blocked or family_blocked_from_replenish(family, jobs)):
            continue
        if not variant and is_clear_loss_family(family, jobs):
            continue
        if family not in coded and not row.get("coded"):
            continue
        if not variant and family not in tested_families:
            # First walk-forward only. Extra clocks wait for a verdict so we
            # do not burn three slots on one untested sleeve.
            from firm.sleeve_factory import spec_for_family

            spec = spec_for_family(family)
            primary = spec.clock if spec is not None else "4h/4h"
            if clock != primary:
                continue
        out.append(row)
    return out


def unqueued_hypotheses(jobs: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Ranked items not currently in the walk-forward or standby queues."""
    return remaining_hypotheses(jobs)


def catalog_pipeline_items() -> list[dict[str, Any]]:
    """Rank-ordered families then backlog, unique by id, skipping feed-blocked."""
    seen: set[str] = set()
    items: list[dict[str, Any]] = []
    for row in list(RESEARCH_FAMILIES) + list(RESEARCH_BACKLOG):
        fid = str(row.get("id") or "")
        if not fid or fid in seen or fid in FAMILIES_NEEDING_FEED:
            continue
        seen.add(fid)
        items.append(row)
    return items


def next_catalog_step(*, tested: set[str], coded: set[str]) -> dict[str, Any] | None:
    """Next research move from ranked hypotheses, then uncoded families.

    `tested` is family ids that already have some finished job — kept so
    callers that only know families still work. Clock follow-ups live in
    RESEARCH_HYPOTHESES and are not skipped just because another clock ran.
    """
    del tested  # family-level skip used to hide clock follow-ups; hypotheses own that.
    remaining = remaining_hypotheses()
    if remaining:
        row = remaining[0]
        fid = str(row["family"])
        name = str(row.get("name") or fid)
        clock = str(row.get("clock") or "4h/4h")
        side = str(row.get("side") or "BOTH")
        if fid in coded or row.get("coded"):
            return {
                "kind": "strategy",
                "title": f"Next: walk-forward {name}",
                "family": fid,
                "action": "walk_forward",
                "clock": clock,
                "side": side,
                "hypothesis_id": row.get("id"),
                "rationale": str(row.get("justification") or ""),
                "owner": "desk_head",
                "owner_label": "Desk Head (walk-forward slot)",
            }
        return {
            "kind": "operational",
            "title": f"Next: code {name}",
            "family": fid,
            "action": "code_family",
            "clock": clock,
            "side": side,
            "hypothesis_id": row.get("id"),
            "rationale": (
                f"{name} is not in the registry. Sleeve Engineer owns templates; "
                "Cursor owns novel math. Walk-forward starts once the sleeve is registered."
            ),
            "owner": "sleeve_engineer",
            "owner_label": "Sleeve Engineer (templates) / Cursor (novel math)",
        }
    for row in catalog_pipeline_items():
        fid = str(row["id"])
        if fid == "rsi_trend" or fid in coded:
            continue
        name = str(row.get("name") or fid)
        clock = str(row.get("clock") or "4h/4h")
        return {
            "kind": "operational",
            "title": f"Next: code {name}",
            "family": fid,
            "action": "code_family",
            "clock": clock,
            "rationale": (
                f"Next catalog family is {name}. Sleeve Engineer materializes "
                "templates; Cursor writes novel math. Walk-forward starts when "
                "the sleeve is in the registry."
            ),
            "owner": "sleeve_engineer",
            "owner_label": "Sleeve Engineer (templates) / Cursor (novel math)",
        }
    from firm.sleeve_factory import ready_novel_specs

    novels = ready_novel_specs()
    if novels:
        spec = novels[0]
        return {
            "kind": "operational",
            "title": f"Next: code {spec.name}",
            "family": spec.name,
            "action": "code_family",
            "clock": spec.clock,
            "side": spec.side,
            "rationale": (
                f"{spec.name} is the next uncoded novel family. Cursor writes "
                f"core/strategy/{spec.name}.py. {spec.novel_reason or spec.justification}"
            ),
            "owner": "cursor",
            "owner_label": "Cursor (novel math)",
        }
    return None


def _coding_owner(family: str) -> tuple[str, str, str]:
    """Who writes this family, and where the brief/spec lives."""
    from firm.sleeve_factory import spec_for_family

    spec = spec_for_family(family)
    if spec is not None and spec.auto_code:
        return (
            "sleeve_engineer",
            "Sleeve Engineer",
            f"config/sleeves/{family}.json",
        )
    return (
        "cursor",
        "Cursor (novel math — Sleeve Engineer will not LLM-write Python)",
        f"research/coding_requests/{family}.md",
    )


def coding_queue() -> list[dict[str, Any]]:
    """Uncoded catalog families the Research tab should show above Next tests.

    Next tests are leftover walk-forwards of sleeves that already have a file.
    This list is the actual coding queue.
    """
    from core.strategy.registry import list_strategies
    from firm.sleeve_factory import spec_for_family

    coded = set(list_strategies())
    pending_by_family: dict[str, int] = {}
    try:
        from firm import memory
        from firm.research_jobs import infer_family

        for proposal in memory.pending_proposals(limit=100):
            payload = proposal.get("payload") if isinstance(proposal.get("payload"), dict) else {}
            if payload.get("action") != "code_family":
                continue
            fam = str(
                payload.get("family")
                or infer_family(payload, str(proposal.get("title") or ""))
            )
            if fam and fam not in pending_by_family:
                pending_by_family[fam] = int(proposal.get("id") or 0)
    except Exception:
        pending_by_family = {}

    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in catalog_pipeline_items():
        fid = str(row.get("id") or "")
        if not fid or fid in seen or fid in coded:
            continue
        seen.add(fid)
        spec = spec_for_family(fid)
        owner, owner_label, brief = _coding_owner(fid)
        plan = str(row.get("next_step") or row.get("summary") or "")
        if spec is not None and spec.novel_reason:
            plan = (
                f"Write core/strategy/{fid}.py. {spec.novel_reason} "
                f"Brief: {brief}."
            )
        elif spec is not None and spec.auto_code:
            plan = (
                f"Sleeve Engineer materializes config/sleeves/{fid}.json from "
                f"the {spec.template} template, then Desk Head starts walk-forward."
            )
        items.append(
            {
                "id": fid,
                "family": fid,
                "name": row.get("name") or fid,
                "clock": row.get("clock") or "",
                "side": row.get("side") or "BOTH",
                "summary": row.get("summary") or "",
                "next_step": row.get("next_step") or "",
                "owner": owner,
                "owner_label": owner_label,
                "brief": brief,
                "coding_plan": plan,
                "proposal_id": pending_by_family.get(fid) or None,
                "novel": bool(spec is not None and not spec.auto_code),
            }
        )
    from firm.sleeve_factory import ready_novel_specs

    for spec in ready_novel_specs():
        fid = spec.name
        if fid in seen:
            continue
        seen.add(fid)
        owner, owner_label, brief = _coding_owner(fid)
        items.append(
            {
                "id": fid,
                "family": fid,
                "name": spec.summary or fid,
                "clock": spec.clock,
                "side": spec.side,
                "summary": spec.summary,
                "next_step": f"Cursor implements core/strategy/{fid}.py",
                "owner": owner,
                "owner_label": owner_label,
                "brief": brief,
                "coding_plan": (
                    f"Write core/strategy/{fid}.py. {spec.novel_reason} "
                    f"Brief: {brief}."
                ),
                "proposal_id": pending_by_family.get(fid) or None,
                "novel": True,
            }
        )
    return items


def research_plan() -> dict[str, Any]:
    """Payload for the Research tab and the Quant Researcher gather."""
    from firm.envelope import classify_hypothesis
    from firm.research_jobs import list_jobs
    from firm.sleeve_factory import ready_novel_specs

    to_code = coding_queue()
    next_to_code = to_code[0] if to_code else None
    jobs = list_jobs()
    hyps = ranked_hypotheses()
    remaining = remaining_hypotheses(jobs)
    next_tests: list[dict[str, Any]] = []
    for row in remaining:
        env = classify_hypothesis(row, jobs=jobs)
        reasons = list(env.get("reasons") or [])
        if any("integrity" in str(r).lower() for r in reasons):
            test_owner = "performance_auditor"
            test_owner_label = "Performance Auditor (integrity flag)"
        elif env.get("auto"):
            test_owner = "desk_head"
            test_owner_label = "Desk Head (Tier A auto-start)"
        else:
            test_owner = "operator"
            test_owner_label = "Inbox (Tier B/C — approve to start)"
        next_tests.append(
            {
                "id": row.get("id"),
                "family": row.get("family"),
                "name": row.get("name"),
                "clock": row.get("clock"),
                "side": row.get("side") or "BOTH",
                "rank": row.get("rank"),
                "disposition": row.get("disposition"),
                "justification": row.get("justification"),
                "tier": env.get("tier"),
                "auto": bool(env.get("auto")),
                "reasons": reasons,
                "owner": test_owner,
                "owner_label": test_owner_label,
            }
        )
    in_flight = [
        {
            "id": j.get("id"),
            "family": j.get("family"),
            "clock": j.get("clock"),
            "side": j.get("side") or "BOTH",
            "status": j.get("status"),
            "blocked_by": j.get("blocked_by") or "",
        }
        for j in jobs
        if j.get("status") in {"running", "queued", "standby", "gated"}
    ]
    return {
        "method": RESEARCH_METHOD,
        "lessons": RESEARCH_LESSONS,
        "families": RESEARCH_FAMILIES,
        "backlog": RESEARCH_BACKLOG,
        "hypotheses": hyps,
        "next_tests": next_tests,
        "in_flight": in_flight,
        "to_code": to_code,
        "next_to_code": next_to_code,
        "novel_ready": [
            {
                "family": spec.name,
                "name": spec.summary,
                "clock": spec.clock,
                "side": spec.side,
                "brief": f"research/coding_requests/{spec.name}.md",
                "owner": "cursor",
                "owner_label": "Cursor — approve the Inbox brief to start coding",
                "novel_reason": spec.novel_reason,
                "justification": spec.justification,
            }
            for spec in ready_novel_specs()
        ],
        "catalog_owner": "quant_researcher",
        "catalog_replenish": (
            "Quant owns catalog depth and new-family intake. Newly coded "
            "sleeves land first. Clear-loss families are not cloned onto new "
            "clocks. Novel math still needs Cursor — one ticket stays queued."
        ),
        "note": (
            "Coding tickets go to Cursor (NOW.md) while walk-forward runs. "
            "Inbox remains the paper-to-live gate. Next tests are leftover "
            "walk-forwards of sleeves that already have a file. Keep at least "
            "10 uncoded novel briefs ready. funding_fade still needs a feed."
        ),
    }


# Clocks we will auto-replenish. 4h first: 15m already overtraded after costs.
REPLENISH_CLOCKS = ("4h/4h", "1h/1h", "1h/4h")
REPLENISH_SIDES = ("BOTH", "SHORT")


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _save_overlay(overlay: dict[str, Any]) -> None:
    path = CATALOG_RANKING_PATH
    overlay.setdefault("ranks", {})
    overlay.setdefault("retired", [])
    overlay.setdefault("retired_families", [])
    overlay.setdefault("justifications", {})
    overlay.setdefault("dispositions", {})
    overlay.setdefault("added", [])
    overlay["updated_at"] = _utcnow_iso()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(overlay, indent=2), encoding="utf-8")


def land_coded_family(family: str, *, added_by: str = "cursor") -> dict[str, Any] | None:
    """Put a registry family on the catalog so walk-forward can start.

    Cursor used to mark a sleeve done and then nothing launched, because
    replenish only auto-landed JSON templates (`auto_code`), not novel Python.
    """
    from core.strategy.registry import list_strategies
    from firm.research_jobs import CLOCK_BY_FAMILY
    from firm.sleeve_factory import spec_for_family

    slug = (family or "").strip().lower()
    if not slug or slug not in set(list_strategies()):
        return None
    spec = spec_for_family(slug)
    if spec is not None:
        if spec.needs_feed:
            return None
        row = spec.hypothesis_row(coded=True)
    else:
        clock = CLOCK_BY_FAMILY.get(slug, "4h/4h")
        row = {
            "id": f"{slug}@{clock}",
            "family": slug,
            "name": f"{slug} {clock} BOTH",
            "clock": clock,
            "side": "BOTH",
            "coded": True,
            "free_params": 4,
            "justification": (
                f"{slug} is in the registry. First walk-forward at {clock} BOTH."
            ),
            "needs_feed": False,
        }
    row["coded"] = True
    row["rank"] = 1
    row["disposition"] = "new_family"
    if not row.get("param_change"):
        row["param_change"] = {"clock": row.get("clock") or "4h/4h"}
    return append_hypothesis(row, added_by=added_by)


def land_coded_candidate_specs(
    *, jobs: list[dict[str, Any]] | None = None
) -> list[dict[str, Any]]:
    """Every coded CANDIDATE_SPECS family gets a catalog row, including novels."""
    from core.strategy.registry import list_strategies
    from firm.sleeve_factory import CANDIDATE_SPECS

    if jobs is None:
        from firm.research_jobs import list_jobs

        jobs = list_jobs()
    coded = set(list_strategies())
    existing = {str(r.get("family") or "") for r in ranked_hypotheses()}
    tested_families = {
        str(job.get("family") or "")
        for job in jobs
        if job.get("status") in {"done", "failed"} and job.get("family")
    }
    for key in durable_tested_keys(jobs):
        family = str(key).split("@")[0]
        if family:
            tested_families.add(family)
    added: list[dict[str, Any]] = []
    for spec in CANDIDATE_SPECS:
        if spec.name in existing or spec.name not in coded or spec.needs_feed:
            continue
        if spec.name in tested_families:
            continue
        if family_blocked_from_replenish(spec.name, jobs) or is_clear_loss_family(
            spec.name, jobs
        ):
            continue
        row = spec.hypothesis_row(coded=True)
        row["rank"] = 1
        row["disposition"] = "new_family"
        if not row.get("param_change"):
            row["param_change"] = {"clock": spec.clock}
        landed = append_hypothesis(row, added_by="quant_researcher")
        if landed:
            added.append(landed)
    return added


def append_hypothesis(row: dict[str, Any], *, added_by: str) -> dict[str, Any] | None:
    """Add one ranked hypothesis. No-op if that id already exists. Does not start a test."""
    hid = str(row.get("id") or "")
    family = str(row.get("family") or "")
    if not hid or not family or family in FAMILIES_NEEDING_FEED:
        return None
    existing_rows = ranked_hypotheses()
    existing = {str(r.get("id") or "") for r in existing_rows}
    if hid in existing:
        return None
    taken = {int(r.get("rank") or 0) for r in existing_rows}
    rank = int(row.get("rank") or 0)
    if rank <= 0:
        rank = 1
        while rank in taken:
            rank += 1
    item = dict(row)
    item["id"] = hid
    item["rank"] = rank
    item["added_by"] = added_by
    item["added_at"] = _utcnow_iso()
    overlay = _ranking_overlay()
    added = list(overlay.get("added") or [])
    added.append(item)
    overlay["added"] = added
    if item.get("justification"):
        just = dict(overlay.get("justifications") or {})
        just[hid] = str(item["justification"])
        overlay["justifications"] = just
    if item.get("disposition"):
        disp = dict(overlay.get("dispositions") or {})
        disp[hid] = str(item["disposition"])
        overlay["dispositions"] = disp
    _save_overlay(overlay)
    return item


def replenish_catalog(*, jobs: list[dict[str, Any]] | None = None, target: int | None = None) -> list[dict[str, Any]]:
    """Keep un-queued depth at the floor. Coded families (including novels) first.

    Does not invent indicators here — Quant/Cursor do that. This function only
    lands coded families that have never been walked. It does not refill from
    CLOCK_BY_FAMILY leftovers, SHORT clones, or extra clocks of a finished
    family. Empty remaining is idle. Uncoded novels become coding requests.
    """
    from config.pipeline import pipeline_config
    from core.strategy.registry import list_strategies
    from firm.sleeve_factory import (
        materialize_pending_specs,
        next_novel_candidate,
        next_template_candidate,
        write_coding_request,
    )

    if jobs is None:
        from firm.research_jobs import list_jobs

        jobs = list_jobs()
    materialize_pending_specs()
    cfg = pipeline_config()
    want = int(target if target is not None else cfg.catalog_min_unqueued)
    added: list[dict[str, Any]] = []
    tested_families = {
        str(job.get("family") or "")
        for job in jobs
        if job.get("status") in {"done", "failed"} and job.get("family")
    }
    for key in durable_tested_keys(jobs):
        family = str(key).split("@")[0]
        if family:
            tested_families.add(family)
    coded = [
        name
        for name in list_strategies()
        if not family_blocked_from_replenish(name, jobs)
        and not is_clear_loss_family(name, jobs)
    ]
    # Families that already finished a grid are not a replenish backlog.
    fresh = [name for name in coded if name not in tested_families]
    last_why: dict[str, str] = {}
    for job in jobs:
        family = str(job.get("family") or "")
        if family and job.get("detail"):
            last_why[family] = str(job.get("detail"))[:240]

    def _try_append(candidate: dict[str, Any]) -> dict[str, Any] | None:
        row = append_hypothesis(candidate, added_by="quant_researcher")
        if row is None:
            return None
        added.append(row)
        return row

    # Always land coded families (JSON templates and novel Python) even if
    # leftover clock clones already fill the depth floor.
    for row in land_coded_candidate_specs(jobs=jobs):
        added.append(row)

    while len(remaining_hypotheses(jobs)) < want:
        existing = {str(r.get("id") or "") for r in ranked_hypotheses()}
        existing_families = {str(r.get("family") or "") for r in ranked_hypotheses()}
        tested = hypothesis_tested_keys(jobs)
        candidate = None
        spec = next_template_candidate(existing=existing_families | set(list_strategies()))
        if spec is not None:
            hid = spec.hypothesis_row(coded=True)["id"]
            if hid not in existing and hid not in tested:
                candidate = spec.hypothesis_row(coded=True)
                candidate["rank"] = 1
        if candidate is None:
            # First clock of a coded family that has never been walked. Do not
            # invent CLOCK_BY_FAMILY leftovers, SHORT clones, or extra clocks
            # of a family that already has a finished grid — idle is correct.
            tested_durable = durable_tested_keys(jobs)
            for family in fresh:
                if family_blocked_from_replenish(family, jobs):
                    continue
                if is_clear_loss_family(family, jobs):
                    continue
                clock = family_primary_clock(family)
                side = "BOTH"
                hid = hypothesis_key(family, clock, side)
                if hid in existing or hid in tested or hid in tested_durable:
                    continue
                if auto_advance_grid_spent(
                    {"family": family, "clock": clock, "side": side, "id": hid},
                    jobs=jobs,
                ):
                    continue
                why = last_why.get(family) or (
                    f"{family} is coded and has not been walked at {clock} {side}."
                )
                candidate = {
                    "id": hid,
                    "family": family,
                    "name": f"{family} {clock} {side}",
                    "clock": clock,
                    "side": side,
                    "coded": True,
                    "rank": 1,
                    "free_params": 4,
                    "disposition": "new_family",
                    "justification": (
                        f"Catalog replenishment (quant_researcher). {why} "
                        "First clock of an untested coded family, not a leftover "
                        "CLOCK_BY_FAMILY clone."
                    ),
                    "param_change": {"clock": clock, "side": side},
                    "needs_feed": False,
                }
                break
        if candidate is None:
            novel = next_novel_candidate(existing=existing_families)
            if novel is not None:
                write_coding_request(novel)
            break
        if _try_append(candidate) is None:
            break
        if len(added) >= 8:
            break
    promote_remaining_into_top5(jobs)
    return added


def promote_remaining_into_top5(jobs: list[dict[str, Any]] | None = None) -> list[str]:
    """Keep the next untested hypotheses in ranks 1–5 so they stay Tier A.

    Post-mortems shove finished ids to rank 16+. If we only promote while
    replenishing, a full catalog sits at seed ranks 6+ and nothing auto-starts.
    Always compact remaining[:5] into that window.
    """
    leftover = remaining_hypotheses(jobs)
    overlay = _ranking_overlay()
    ranks = dict(overlay.get("ranks") or {})
    changed = False
    promoted: list[str] = []
    for slot, row in enumerate(leftover[:5], start=1):
        hid = str(row.get("id") or "")
        if not hid:
            continue
        current = int(ranks.get(hid) or row.get("rank") or 99)
        if current != slot:
            ranks[hid] = slot
            changed = True
            promoted.append(hid)
    if changed:
        overlay["ranks"] = ranks
        _save_overlay(overlay)
    return promoted


# Near-miss retests from 2026-08-31 OOS (PF >= 1.15, other gates failed).
# Same coded family; frozen grid so this is not a silent re-run of the reject.
NEAR_MISS_RETESTS: list[dict[str, Any]] = [
    {
        "id": "bb_squeeze_breakout@4h/4h@LONG@no_adx",
        "family": "bb_squeeze_breakout",
        "name": "BB squeeze 4h longs, ADX off",
        "clock": "4h/4h",
        "side": "LONG",
        "rank": 1,
        "coded": True,
        "free_params": 3,
        "disposition": "re-parameterise",
        "justification": (
            "SOLUSDT LONG 4h PF 1.67 but only 16 OOS trades; CI/random failed. "
            "Freeze min_adx at 0 so sample size is measurable."
        ),
        "param_change": {"min_adx": [0.0]},
    },
    {
        "id": "doji_star_reversal@4h/4h@LONG@run4",
        "family": "doji_star_reversal",
        "name": "Doji star 4h longs, 4-bar run",
        "clock": "4h/4h",
        "side": "LONG",
        "rank": 2,
        "coded": True,
        "free_params": 3,
        "disposition": "re-parameterise",
        "justification": (
            "ETHUSDT LONG 4h PF 1.66; CI includes zero (p=0.126). "
            "Freeze run_bars at 4 so folds cannot hunt pattern length."
        ),
        "param_change": {"run_bars": [4]},
    },
    {
        "id": "macd_trend_pullback@4h/4h@LONG@frozen_adx",
        "family": "macd_trend_pullback",
        "name": "MACD pullback 4h longs, frozen ADX",
        "clock": "4h/4h",
        "side": "LONG",
        "rank": 3,
        "coded": True,
        "free_params": 3,
        "disposition": "re-parameterise",
        "justification": (
            "ETHUSDT LONG 4h PF 1.33; min_adx cv=1.25 and chop loss. "
            "Freeze min_adx at 20."
        ),
        "param_change": {"min_adx": [20.0]},
    },
    {
        "id": "bb_squeeze_breakout@1h/1h@SHORT@frozen_adx",
        "family": "bb_squeeze_breakout",
        "name": "BB squeeze 1h shorts, frozen ADX",
        "clock": "1h/1h",
        "side": "SHORT",
        "rank": 4,
        "coded": True,
        "free_params": 3,
        "disposition": "re-parameterise",
        "justification": (
            "BTC/ETH SHORT 1h PF 1.26-1.27; CI/random and min_adx cv>1. "
            "Freeze min_adx at 20."
        ),
        "param_change": {"min_adx": [20.0]},
    },
    {
        "id": "prior_week_high_break@1h/1h@SHORT@wide_stop",
        "family": "prior_week_high_break",
        "name": "Prior-week 1h shorts, frozen stops",
        "clock": "1h/1h",
        "side": "SHORT",
        "rank": 5,
        "coded": True,
        "free_params": 2,
        "disposition": "re-parameterise",
        "justification": (
            "ETHUSDT SHORT 1h PF 1.25; CI/random fail. Freeze TP 5% / SL 3% "
            "so folds cannot hunt exits."
        ),
        "param_change": {"take_profit_pct": [0.05], "stop_loss_pct": [0.03]},
    },
    {
        "id": "donchian_breakout@4h/4h@SHORT@frozen_lookback_adx",
        "family": "donchian_breakout",
        "name": "Donchian 4h shorts, lookback 55 frozen ADX",
        "clock": "4h/4h",
        "side": "SHORT",
        "rank": 6,
        "coded": True,
        "free_params": 2,
        "disposition": "re-parameterise",
        "justification": (
            "ETH/BTC SHORT 4h PF 1.17-1.25; lookback and min_adx unstable, "
            "bear/bull regime loss. Freeze lookback 55 and min_adx 20."
        ),
        "param_change": {"lookback": [55], "min_adx": [20.0]},
    },
    {
        "id": "rsi_trend@4h/4h@LONG@tight_band",
        "family": "rsi_trend",
        "name": "RSI trend 4h longs, frozen band",
        "clock": "4h/4h",
        "side": "LONG",
        "rank": 7,
        "coded": True,
        "free_params": 3,
        "disposition": "re-parameterise",
        "justification": (
            "ETHUSDT LONG 4h PF 1.21; 48% folds, CI includes zero. "
            "Freeze rsi_min 30 / rsi_max 45 / volume 1.2."
        ),
        "param_change": {
            "rsi_min": [30.0],
            "rsi_max": [45.0],
            "volume_threshold": [1.2],
        },
    },
    {
        "id": "bb_squeeze_breakout@1h/1h@LONG@frozen_adx",
        "family": "bb_squeeze_breakout",
        "name": "BB squeeze 1h longs, frozen ADX",
        "clock": "1h/1h",
        "side": "LONG",
        "rank": 8,
        "coded": True,
        "free_params": 3,
        "disposition": "re-parameterise",
        "justification": (
            "SOLUSDT LONG 1h PF 1.19; 48% folds and min_adx cv=1.53. "
            "Freeze min_adx at 20."
        ),
        "param_change": {"min_adx": [20.0]},
    },
    {
        "id": "macd_trend_pullback@4h/4h@SHORT@frozen_adx",
        "family": "macd_trend_pullback",
        "name": "MACD pullback 4h shorts, frozen ADX",
        "clock": "4h/4h",
        "side": "SHORT",
        "rank": 9,
        "coded": True,
        "free_params": 3,
        "disposition": "re-parameterise",
        "justification": (
            "ETHUSDT SHORT 4h PF 1.19; min_adx cv=1.44 and bull loss. "
            "Freeze min_adx at 20."
        ),
        "param_change": {"min_adx": [20.0]},
    },
    {
        "id": "prior_week_high_break@4h/4h@SHORT@wide_stop",
        "family": "prior_week_high_break",
        "name": "Prior-week 4h shorts, frozen stops",
        "clock": "4h/4h",
        "side": "SHORT",
        "rank": 10,
        "coded": True,
        "free_params": 2,
        "disposition": "re-parameterise",
        "justification": (
            "ETHUSDT SHORT 4h PF 1.18; CI/random fail. Freeze TP 5% / SL 3%."
        ),
        "param_change": {"take_profit_pct": [0.05], "stop_loss_pct": [0.03]},
    },
    {
        "id": "bollinger_mean_reversion@4h/4h@SHORT@frozen_chop",
        "family": "bollinger_mean_reversion",
        "name": "Bollinger 4h shorts, frozen max ADX",
        "clock": "4h/4h",
        "side": "SHORT",
        "rank": 11,
        "coded": True,
        "free_params": 3,
        "disposition": "re-parameterise",
        "justification": (
            "BTCUSDT SHORT 4h PF 1.18; max_adx cv=0.65, 48% folds, bull loss. "
            "Freeze max_adx at 20."
        ),
        "param_change": {"max_adx": [20.0]},
    },
    {
        "id": "doji_star_reversal@4h/4h@SHORT@run4",
        "family": "doji_star_reversal",
        "name": "Doji star 4h shorts, 4-bar run",
        "clock": "4h/4h",
        "side": "SHORT",
        "rank": 12,
        "coded": True,
        "free_params": 3,
        "disposition": "re-parameterise",
        "justification": (
            "SOLUSDT SHORT 4h PF 1.17; CI/random fail. Freeze run_bars at 4 "
            "(SOL short 1h already approved with the looser 3-bar run)."
        ),
        "param_change": {"run_bars": [4]},
    },
    {
        "id": "atr_channel_breakout@4h/4h@LONG@wide_k",
        "family": "atr_channel_breakout",
        "name": "ATR channel 4h longs, k=2.5",
        "clock": "4h/4h",
        "side": "LONG",
        "rank": 13,
        "coded": True,
        "free_params": 2,
        "disposition": "re-parameterise",
        "justification": (
            "BTCUSDT LONG 4h PF 1.16; 45% folds, bear/chop loss. "
            "Freeze atr_k at 2.5 (shorts already approved). Wider channel, fewer trades."
        ),
        "param_change": {"atr_k": [2.5]},
    },
    {
        "id": "doji_star_reversal@1h/1h@LONG@run4",
        "family": "doji_star_reversal",
        "name": "Doji star 1h longs, 4-bar run",
        "clock": "1h/1h",
        "side": "LONG",
        "rank": 14,
        "coded": True,
        "free_params": 3,
        "disposition": "re-parameterise",
        "justification": (
            "SOL short 1h approved. Test the long side at the same clock with "
            "run_bars frozen at 4 so it is not a silent clone of the 4h long miss."
        ),
        "param_change": {"run_bars": [4]},
    },
    {
        "id": "bb_squeeze_breakout@4h/4h@SHORT@frozen_adx",
        "family": "bb_squeeze_breakout",
        "name": "BB squeeze 4h shorts, frozen ADX",
        "clock": "4h/4h",
        "side": "SHORT",
        "rank": 15,
        "coded": True,
        "free_params": 3,
        "disposition": "re-parameterise",
        "justification": (
            "ATR 4h shorts approved; squeeze 1h shorts were PF 1.26 near-misses. "
            "Retest squeeze shorts at 4h with min_adx frozen at 20."
        ),
        "param_change": {"min_adx": [20.0]},
    },
]


# 2026-09-01 close calls: PF/WR/expectancy cleared, one extra gate left.
# Frozen SMA trend filter so this is not a silent re-run of the 0-for-6 grid.
TODAY_CLOSE_RETESTS: list[dict[str, Any]] = [
    {
        "id": "mass_index_reversal@4h/4h@LONG@trend_sma50",
        "family": "mass_index_reversal",
        "name": "Mass Index 4h longs, SMA50 trend gate",
        "clock": "4h/4h",
        "side": "LONG",
        "rank": 1,
        "coded": True,
        "free_params": 2,
        "disposition": "re-parameterise",
        "justification": (
            "ETHUSDT LONG 4h WR 62.5 PF 2.30 E +1.33 n=48; only failed bear. "
            "SOLUSDT LONG 4h WR 62.1 PF 1.89 n=29. Freeze trend_sma at 50 so "
            "longs only fire above SMA. Freeze exits at the ETH last-fold pair."
        ),
        "param_change": {
            "trend_sma": [50],
            "take_profit_pct": [0.03],
            "stop_loss_pct": [0.03],
        },
    },
    {
        "id": "mama_fama_cross@4h/4h@SHORT@trend_sma50",
        "family": "mama_fama_cross",
        "name": "MAMA/FAMA 4h shorts, SMA50 trend gate",
        "clock": "4h/4h",
        "side": "SHORT",
        "rank": 2,
        "coded": True,
        "free_params": 2,
        "disposition": "re-parameterise",
        "justification": (
            "BTCUSDT SHORT 4h WR 51 PF 1.56 E +0.71 n=100; only failed bull. "
            "ETHUSDT SHORT 4h WR 50 PF 1.48 n=92; CI includes 0. Freeze "
            "trend_sma at 50 so shorts only fire below SMA."
        ),
        "param_change": {
            "trend_sma": [50],
            "take_profit_pct": [0.05],
            "stop_loss_pct": [0.03],
        },
    },
]


def queue_near_miss_retests(*, added_by: str = "operator") -> list[dict[str, Any]]:
    """Land the 15 near-miss frozen-grid hypotheses. Does not start validators."""
    landed: list[dict[str, Any]] = []
    for row in NEAR_MISS_RETESTS:
        payload = dict(row)
        payload["operator_queued"] = True
        item = append_hypothesis(payload, added_by=added_by)
        if item is not None:
            landed.append(item)
    promote_remaining_into_top5()
    return landed


def queue_today_close_retests(*, added_by: str = "operator") -> list[dict[str, Any]]:
    """Land today's PF/WR/expectancy close-calls as frozen trend-filter retests."""
    landed: list[dict[str, Any]] = []
    for row in TODAY_CLOSE_RETESTS:
        payload = dict(row)
        payload["operator_queued"] = True
        item = append_hypothesis(payload, added_by=added_by)
        if item is not None:
            landed.append(item)
    promote_remaining_into_top5()
    return landed


