# Proposal: `nr7_fail_reversion`

Fade a failed NR7 break: after an NR7 bar (narrowest range of last 7), price breaks the NR7 high/low then fails to hold and reverts back inside.

SHORT when the setup bar closed above the NR7 high, then `close_t` is back below that NR7 high (within `max_bars_since_break`), still inside the NR7 box. LONG when the setup bar closed below the NR7 low, then `close_t` is back above it. NR7 definition is locked (lookback 7, not a search param). Quant-locked: `require_close_inside=True`, `max_bars_since_break` search `[1, 3]`. No volume gate. Close-through of the published NR7 bar, then a later fail (not a held breakout).

## Coding brief (Brian Inbox-approved for coding)

- Clock: `4h/4h`
- Side: `BOTH`
- Status: Brian Inbox-approved for coding (do not start walk-forward)
- Quant lock: NR7 definition FIXED (lookback 7); `require_close_inside=True` (fixed); `max_bars_since_break` search `[1, 3]`; no volume gate
- Why this is novel: Fade a failed NR7 break: after an NR7 bar (narrowest range of last 7), price breaks the NR7 high/low then fails to hold and reverts back inside. SHORT: break above NR7 high then close back below within max_bars_since_break. LONG: break below NR7 low then close back above. Quant-locked: NR7 definition fixed, require_close_inside=True, max_bars_since_break [1, 3], no volume. Not nr7_breakout (breakout direction / leftover). Not expansion_fail_fade (single ATR expansion). Not range_compression_volume_thrust (102 — thrust). Not failed_range_break_reversion (119 — rolling N-bar). Not orb_fail_reversion (121/122 — UTC day ORB). Not prior_day_extreme_reject (118), asia_range_london_reject (120). Not H&S / asia_close / wyckoff.

## What to write

1. `core/strategy/nr7_fail_reversion.py` — `Strategy` subclass, `name = "nr7_fail_reversion"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one LONG and one SHORT entry, held breakout does not fire.
4. Do not copy a rejected family and rename it.
5. Do not call `firm.cursor_coding.mark_done` (that starts walk-forward). Coding only.
