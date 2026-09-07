# Proposal: `prior_day_extreme_reject`

Fade a 4h tag of the prior UTC day's high or low that closes back inside that day's range.

SHORT when this 4h high tags `prior_day_high` and the close comes back below it (preferably still inside the prior day range). LONG when this 4h low tags `prior_day_low` and the close comes back above it. Free params are `touch_tol_atr` (default 0) and `require_close_inside`.

## Coding brief (Brian Inbox-approved for coding)

- Clock: `4h/4h`
- Side: `BOTH`
- Status: Brian Inbox-approved for coding (do not start walk-forward)
- Why this is novel: Fade a 4h tag of the prior UTC day's high or low that closes back inside that day's range. SHORT when high_t >= prior_day_high and close_t < prior_day_high (preferably close inside prior day range). LONG when low_t <= prior_day_low and close_t > prior_day_low. Free params: touch_tol_atr (default 0) and require_close_inside. Not monday_range_sweep_reversal (weekend Sat-Sun box). Not week_open_reclaim. Not equal_high_low_restest_fade (rolling equal H/L). Not double_top/double_bottom neckline. Not classic_floor_pivot_reject (R1/S1 from P). Not session_boundary_volume_fade (weak-volume sweep, no close-inside). Do not recode asia_close_inventory_fade or wyckoff_spring_reclaim.

## What to write

1. `core/strategy/prior_day_extreme_reject.py` — `Strategy` subclass, `name = "prior_day_extreme_reject"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one LONG and one SHORT entry.
4. Do not copy a rejected family and rename it.
5. Do not call `firm.cursor_coding.mark_done` (that starts walk-forward). Coding only.
