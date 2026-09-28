# Proposal: `ny_cash_open_vwap_fade`

UNAPPROVED — Option B exploratory. SCORE/RETIRE only. Not Inbox.
Not a wick-fail sibling. Not `ny_cash_open_drive`. Not a UTC-midnight VWAP.

## Mechanism (preregistered)
US cash open (13:00 UTC) starts a new institutional fair-value clock. Price that stretches from the cash-open–anchored VWAP and closes back toward it tends to mean-revert. Hold is the desk's standard percent TP/SL plus fees. Invalidation is a close that stays beyond the halfway band.

## One-liner
4h BOTH (SHORT priority): fade a stretch from VWAP anchored at the first bar with hour_utc in [13, 16] that calendar day.

## Geometry
- Anchor: first 4h bar with hour_utc in [13, 16] that day → running VWAP from that bar forward through the rest of the UTC day (HLC3×vol). Resets at the next cash-open anchor. No signal before 13:00.
- SHORT: `(high - VWAP) >= k*ATR20` AND `close < VWAP + 0.5*k*ATR20`
- LONG: mirror (low stretch and close back above the halfway line)
- Fill t+1 open
- One entry per UTC day per side
- Free: `k [1.0, 1.5]` only (ATR20 multiples). Not 1.25. Not ATR14. Not a stretch percent.
- Exits: shared walk-forward TP/SL kit plus fees. TP is not frozen at 0.05. `stop_loss_pct` is not a family free axis.
- Locked: ATR20 known before the signal bar; NY cash-open anchor only (not UTC 00:00, not swing pivot, not prior-day freeze); reclaim toward VWAP; fill t+1
- Pairs: BTC/ETH/BNB/XRP/SOL/AVAX (desk research majors)

## Do-not-recode
`swing_anchored_vwap_pullback`, `up_down_turnover_imbalance`, `signed_range_turnover_trend`, `utc_session_vwap_reversion`, `prior_day_vwap_reject`, `bar_vwap_inflow_surge`, wick-fail cluster, `ny_cash_open_drive`.

## Option B
SCORE/RETIRE only. No `approved=true`. Live stays off. Do not call `mark_done`. Do not start walk-forward from this coding PR. Do not edit `config/approved_strategies.json`. Protect Research 12 + Overrides 56.

Job 154 `three_push_exhaustion_fail` is RETIRE 0/12. Do not revive it. This family is not that sleeve and not `ny_cash_open_drive`. `k` is an ATR20 multiple only (not σ, not a fraction of VWAP).
