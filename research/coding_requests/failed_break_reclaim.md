# Proposal: `failed_break_reclaim`

Fade a multi-bar range/swing probe that fails and closes back inside a prior-bar lookback range.

Define a rolling range over `lookback` prior bars (current bar does not set its own range). SHORT when highs print beyond `range_high` for `min_probe_bars` then `close_t` is back below `range_high` and still inside `[range_low, range_high]`. LONG when lows print beyond `range_low` then `close_t` is back above `range_low` and still inside. Clock: `4h/4h`. Side: BOTH. No volume gate. Not a single-bar close-through (119), not a same-bar Wyckoff spring (127), not prior-day H/L (118), not London IB (124), not floor P/R1/S1 (129).

## Coding brief (Brian Inbox-approved for coding)

- Clock: `4h/4h`
- Side: `BOTH`
- Status: Brian Inbox-approved for coding (do not start walk-forward)
- Quant lock: `require_close_inside=True` (fixed / not searched); `lookback` search `[16, 20]`; `min_probe_bars` search `[2, 3]`; ATR period locked 20 if used; max 2 free params; no volume gate
- Why this is novel: Multi-bar range/swing probe that closes back inside, then fade the failed break. Rolling range over lookback prior bars only. SHORT: highs beyond range_high for min_probe_bars then close_t back below range_high AND inside [range_low, range_high]. LONG: lows beyond range_low then close_t back above range_low AND inside. Quant-locked: require_close_inside=True, lookback [16, 20], min_probe_bars [2, 3], ATR period locked 20 if used, no volume. Not prior_day_extreme_reject (118 PDH). Not failed_range_break_reversion (119 single-bar closed-outside). Not ib_fail_reversion (124 IB). Not wyckoff_spring_reclaim (127). Not classic_floor_pivot_reject (129 P/R1/S1). Do not recode spent families 118–129. Do not code displacement_gap_follow.

## What to write

1. `core/strategy/failed_break_reclaim.py` — `Strategy` subclass, `name = "failed_break_reclaim"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one LONG and one SHORT reclaim, kit lock asserts `lookback` `[16, 20]`, `min_probe_bars` `[2, 3]`, and `require_close_inside=True` locked.
4. Do not copy a rejected family and rename it. Do not recode 118–129. Do not code `displacement_gap_follow`.
5. Do not call `firm.cursor_coding.mark_done` (that starts walk-forward). Coding only.
