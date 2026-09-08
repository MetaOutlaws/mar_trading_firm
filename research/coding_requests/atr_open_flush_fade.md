# Proposal: `atr_open_flush_fade`

Same-bar open flush then fade back through the open. SHORT: bar opens, flushes up (high extends) by ~k*ATR from open, then closes back below the open. LONG: bar opens, flushes down (low extends) by ~k*ATR from open, then closes back above the open. Clock: `4h/4h`. Side: BOTH.

## Coding brief (Brian Inbox-approved for coding)

- Clock: `4h/4h`
- Side: `BOTH`
- Status: Brian Inbox-approved for coding (do not start walk-forward)
- Quant lock: ATR period = 20 LOCKED / not searched; same-bar flush extreme then close back through open LOCKED; SHORT = up-flush fade, LONG = down-flush fade LOCKED. Free search (1 only): `k` (flush distance in ATR units from open) `[1.0, 1.5]`.
- Why this is novel: Same-bar open flush then fade through the open as one 4h BOTH family. Flush distance is k*ATR(20) from the signal-bar open (ATR known before the bar so the flush cannot lift its own threshold). Not a London IB fail, not a prior-close magnet stretch, not a next-bar expansion fail, not a UTC-day ORB fail. Quant-locked: ATR20, same-bar geometry, SHORT=up-flush / LONG=down-flush. Free search (1 only): k [1.0, 1.5]. Not ib_fail_reversion (124). Not prior_close_magnet_fade (128). Not expansion_fail_fade (131). Not orb_fail_reversion. Not prior_week_extreme_reject (CEO superseded — do not implement). Not NR7 / rectangle / three_black / bb_medium. Do not recode spent families 118–137.

## What to write

1. `core/strategy/atr_open_flush_fade.py` — `Strategy` subclass, `name = "atr_open_flush_fade"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), SHORT up-flush fade, LONG down-flush fade, kit lock asserts search only `k` `[1.0, 1.5]`, ATR20 locked, distinction vs ib_fail / magnet / expansion_fail / orb_fail.
4. Do not copy a rejected family and rename it. Do not recode 118–137. Do not clone `ib_fail_reversion`, `prior_close_magnet_fade`, `expansion_fail_fade`, or `orb_fail_reversion`. Do not code `prior_week_extreme_reject`.
5. Do not call `firm.cursor_coding.mark_done` (that starts walk-forward). Coding only.
