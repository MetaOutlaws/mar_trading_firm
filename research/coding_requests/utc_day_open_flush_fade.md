# Proposal: `utc_day_open_flush_fade`

Fade a flush of the UTC day-open then reclaim through that open. SHORT: high extends by ~k*ATR above the UTC day-open, then closes back below the day-open. LONG: low extends by ~k*ATR below the UTC day-open, then closes back above the day-open. UTC day-open is the open of the first 4h bar whose open time falls in 00:00–03:59 UTC on that calendar day (same UTC day only). Clock: `4h/4h`. Side: BOTH.

## Coding brief (Brian Inbox-approved for coding)

- Clock: `4h/4h`
- Side: `BOTH`
- Status: Brian Inbox-approved for coding (do not start walk-forward)
- Quant lock: ATR period = 20 LOCKED / not searched; UTC day-open = first 4h open in 00:00–03:59 UTC, same calendar day only LOCKED; SHORT = up-flush of day-open then close below, LONG = down-flush then close above LOCKED. Free search (1 only): `k` (flush distance in ATR units from day-open) `[1.0, 1.5]`.
- Why this is novel: Fade a flush of the frozen UTC day-open (not the signal bar's own open) as one 4h BOTH family. Same UTC day only. Not atr_open_flush_fade (138 — RETIRED same-bar bar-open flush). Not a prior-day / prior-week extreme reject, not a prior-close magnet stretch, not a London IB fail, not a UTC-day ORB fail, not a next-bar expansion fail, not an inventory-close / NY-close fade. Quant-locked: ATR20, UTC day-open anchor, SHORT=up-flush / LONG=down-flush. Free search (1 only): k [1.0, 1.5]. Do not recode spent family 138. Do not modify atr_open_flush_fade geometry.

## What to write

1. `core/strategy/utc_day_open_flush_fade.py` — `Strategy` subclass, `name = "utc_day_open_flush_fade"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), SHORT up-flush fade of day-open, LONG down-flush fade of day-open, same-day constraint, kit lock asserts search only `k` `[1.0, 1.5]`, ATR20 locked, day-open anchor locked, distinction vs atr_open_flush_fade / prior_day / magnet / IB fail / orb_fail / expansion_fail / inventory-close.
4. Do not copy a rejected family and rename it. Do not recode 138. Do not clone `atr_open_flush_fade`, `prior_day_extreme_reject`, `prior_close_magnet_fade`, `ib_fail_reversion`, `orb_fail_reversion`, `expansion_fail_fade`, or `london_close_inventory_fade`.
5. Do not call `firm.cursor_coding.mark_done` (that starts walk-forward). Coding only.
