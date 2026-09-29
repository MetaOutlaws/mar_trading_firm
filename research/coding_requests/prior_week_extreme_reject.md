# Proposal: `prior_week_extreme_reject`

UNAPPROVED — Option B exploratory. SCORE/RETIRE only. Not Inbox.
Not `prior_day_extreme_reject`. Not `week_open_reclaim`. Not `classic_floor_pivot_reject`.

## Mechanism (preregistered)
The prior ISO week (Monday 00:00 through Sunday, UTC) publishes a raw high and low after Sunday closes. A 4h bar that tags that extreme and closes back inside the week range is a fade. Hold is the desk's standard percent TP/SL plus fees. Invalidation is a close that stays through the extreme or leaves the week range.

## One-liner
4h BOTH (SHORT priority): fade a tag of the prior ISO week's high or low that closes back inside that week's range.

## Geometry
- Level: raw prior ISO-week H/L (UTC weeks). Not a rolling 7-day window.
- SHORT: `high` tags `prior_week_high` within `touch_tol_atr * ATR(20)` AND `close < prior_week_high` AND close inside `[prior_week_low, prior_week_high]`
- LONG: inverse on `prior_week_low`
- Two-sided bar is SHORT, not LONG
- One entry per ISO week per side
- Fill t+1 open
- Free: `touch_tol_atr ∈ {0.0, 0.10}` only
- Locked: `require_close_inside=True`, ATR(20) known before the signal bar, raw week H/L only

## Do-not-recode
`prior_day_extreme_reject`, `week_open_reclaim`, `classic_floor_pivot_reject`, `prior_week_high_break`.

## Option B
SCORE/RETIRE only. No `approved=true`. Live stays off. Do not call `mark_done`. Do not start walk-forward from this coding PR. Do not edit `config/approved_strategies.json`. Protect Research 12 + Overrides 56. Hold H&S alone.
