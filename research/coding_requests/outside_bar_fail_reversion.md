# Proposal: `outside_bar_fail_reversion`

Outside-bar fail reversion — outside range vs the prior bar, then the next bar closes back inside the outside bar. LONG when that fail close sits above the outside-bar mid; SHORT when it sits below. Clock: `4h/4h`. Side: BOTH.

## Coding brief (Brian Inbox-approved for coding)

- Clock: `4h/4h`
- Side: `BOTH`
- Status: Brian Inbox-approved for coding (do not start walk-forward)
- Quant lock: ATR period = 20 LOCKED / not searched; outside definition LOCKED (`high[t-1] > high[t-2]` AND `low[t-1] < low[t-2]`); `require_close_inside_outside=True` LOCKED (close[t] strictly inside `(low[t-1], high[t-1])`); mid-side split LOCKED (LONG = close[t] > mid, SHORT = close[t] < mid). Free search (1 only): `min_outside_atr` `[0.8, 1.2]`. Size: `(high[t-1]-low[t-1]) >= min_outside_atr * ATR20` (ATR known before the signal bar). Fill at `t+1` open.
- Why this is novel: Outside-bar fail reversion as one 4h BOTH family. Outside bar is t-1 vs t-2 (range containment). Fail/reversion is bar t closing strictly inside that outside high-low. Side is the fail close vs the outside mid — not the outside bar's own close, not a body-engulf open fail, not a Donchian / IB / NR7 rail. Quant-locked: ATR20, outside definition, require_close_inside_outside, mid-side split (not searched). Free search (1 only): min_outside_atr [0.8, 1.2]. Not engulfing_fail_reversion (126 — two-bar body engulf then fail through engulf open). Not failed_range_break_reversion (119 — rolling N-bar Donchian). Not failed_break_reclaim (130 — multi-bar wick probe). Not expansion_fail_fade (131 — ATR true-range expansion + weak-vol; side from expansion close vs mid). Not candle_reject_reversal. Not ib_fail_reversion (124). Not nr7_fail_reversion (123). Not atr_open_flush_fade (138). Not utc_day_open_flush_fade (139). Not three_white_soldiers (140) / three_black_crows (134). Not sma20_stretch_fade (141). Not london_close_inventory_fade (100) / ny_close_inventory_fade (banned/parked). Not outside_bar_reversal (fires ON the outside bar). Do not recode spent families 118–141. Do not modify sibling geometry.

## What to write

1. `core/strategy/outside_bar_fail_reversion.py` — `Strategy` subclass, `name = "outside_bar_fail_reversion"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), LONG close-above-mid, SHORT close-below-mid, kit lock asserts search only `min_outside_atr` `[0.8, 1.2]`, ATR20 + require_close_inside_outside + mid-side locked, distinction vs `engulfing_fail_reversion`, `failed_range_break_reversion`, `failed_break_reclaim`, `expansion_fail_fade`, `candle_reject_reversal`, `ib_fail_reversion`, `nr7_fail_reversion`, `atr_open_flush_fade`, `utc_day_open_flush_fade`, `three_white_soldiers`, `three_black_crows`, `sma20_stretch_fade`, `london_close_inventory_fade`, and `outside_bar_reversal`.
4. Do not copy a rejected family and rename it. Do not recode 118–141. Do not clone `engulfing_fail_reversion`, `failed_range_break_reversion`, `failed_break_reclaim`, `expansion_fail_fade`, `candle_reject_reversal`, `ib_fail_reversion`, `nr7_fail_reversion`, `atr_open_flush_fade`, `utc_day_open_flush_fade`, `three_white_soldiers`, `sma20_stretch_fade`, or `outside_bar_reversal`. Do not code `ny_close_inventory_fade`. Do not modify sibling geometry.
5. Do not call `firm.cursor_coding.mark_done` (that starts walk-forward). Coding only.
