# Proposal: `ib_fail_reversion`

Fade a failed London inside-bar break: after an inside bar whose mother is the first 4h bar with UTC open in 07:00–11:00, price breaks the mother high/low then fails to hold and reverts back inside.

SHORT when the setup bar closed above the mother high, then `close_t` is back below that mother high (within `max_bars_since_break`), still inside the mother. LONG when the setup bar closed below the mother low, then `close_t` is back above it. Mother is locked as the first 4h bar with UTC open in 07:00–11:00 (not searched; on 4h that is the 08:00 print). Quant-locked: `require_close_inside=True`, `max_bars_since_break` search `[2, 4]`. No volume gate. Mother+inside geometry only. Close-through of the published mother, then a later fail (not a held breakout).

## Coding brief (Brian Inbox-approved for coding)

- Clock: `4h/4h`
- Side: `BOTH`
- Status: Brian Inbox-approved for coding (do not start walk-forward)
- Quant lock: London IB = first 4h bar with open in UTC 07:00–11:00 (locked, not searched); `require_close_inside=True` (fixed); `max_bars_since_break` search `[2, 4]`; no volume gate
- Why this is novel: Fade a failed London inside-bar break: after an inside bar whose mother is the first 4h bar with UTC open in 07:00–11:00, price breaks the mother/IB high/low then fails to hold and reverts back inside. SHORT: break above mother high then close back below within max_bars_since_break. LONG: break below mother low then close back above. Quant-locked: London IB open 07:00–11:00 fixed, require_close_inside=True, max_bars_since_break [2, 4], no volume. Not nr7_fail_reversion (123 — narrowest-of-7). Not failed_range_break_reversion (119 — rolling N-bar). Not orb_fail_reversion (121 — UTC day ORB). Not asia_range_london_reject (120 — Asia H/L London tag). Not prior_day / prior_week extreme reject. Not inside_bar_breakout (breakout direction). Not engulfing_reversal. Not H&S / asia_close / wyckoff.

## What to write

1. `core/strategy/ib_fail_reversion.py` — `Strategy` subclass, `name = "ib_fail_reversion"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one LONG and one SHORT entry, held breakout does not fire.
4. Do not copy a rejected family and rename it.
5. Do not call `firm.cursor_coding.mark_done` (that starts walk-forward). Coding only.
