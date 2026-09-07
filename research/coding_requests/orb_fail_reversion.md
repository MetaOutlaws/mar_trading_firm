# Proposal: `orb_fail_reversion`

Fade a failed UTC-day opening-range break: price breaks the day ORB then fails to hold and reverts back inside.

SHORT when a prior same-day bar closed above ORB high, then `close_t` is back below that ORB high (within `max_bars_since_break`), still inside the ORB. LONG when a prior same-day bar closed below ORB low, then `close_t` is back above it. ORB is the high/low of the first `orb_bars` 4h bars of the UTC day. Quant-locked: `require_close_inside=True`, `orb_bars` search `[1, 2]`, `max_bars_since_break` search `[2, 4]`. No volume gate. Close-through of the published ORB, then a later fail (not a same-bar wick reject).

## Coding brief (Brian Inbox-approved for coding)

- Clock: `4h/4h`
- Side: `BOTH`
- Status: Brian Inbox-approved for coding (do not start walk-forward)
- Quant lock: `require_close_inside=True` (fixed); `orb_bars` search `[1, 2]`; `max_bars_since_break` search `[2, 4]`; no volume gate
- Why this is novel: Fade a failed UTC-day opening-range break: price breaks the day ORB then fails to hold and reverts back inside. SHORT: break above ORB high then close back below within max_bars_since_break. LONG: break below ORB low then close back above. Quant-locked: require_close_inside=True, orb_bars [1, 2], max_bars_since_break [2, 4], no volume. Not opening_range_breakout (finished leftover / breakout direction). Not failed_range_break_reversion (119 — rolling N-bar range). Not prior_day_extreme_reject (118 — prior UTC day H/L reject). Not asia_range_london_reject (120 — Asia box / London reject). Not nr7_fail_reversion (stays buffer). Not range_compression_volume_thrust (102). Not H&S / asia_close / wyckoff.

## What to write

1. `core/strategy/orb_fail_reversion.py` — `Strategy` subclass, `name = "orb_fail_reversion"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one LONG and one SHORT entry.
4. Do not copy a rejected family and rename it.
5. Do not call `firm.cursor_coding.mark_done` (that starts walk-forward). Coding only.
