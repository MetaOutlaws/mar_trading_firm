# Proposal: `failed_range_break_reversion`

Fade a 4h close back inside a prior N-bar range after a break that fails to hold.

SHORT when a prior bar closed above `range_high`, then `close_t` is back below that `range_high`, still inside the broken range. LONG when a prior bar closed below `range_low`, then `close_t` is back above it. Quant-locked: `require_close_inside=True`, `lookback` search `[16, 20]`, `max_bars_since_break` search `[2, 3]`. No volume gate. Rolling N-bar H/L excluding the current bar (not prior UTC day H/L).

## Coding brief (Brian Inbox-approved for coding)

- Clock: `4h/4h`
- Side: `BOTH`
- Status: Brian Inbox-approved for coding (do not start walk-forward)
- Quant lock: `require_close_inside=True` (fixed); `lookback` search `[16, 20]`; `max_bars_since_break` search `[2, 3]`; no volume gate
- Why this is novel: Fade a 4h close back inside a prior N-bar range after a close-through that fails to hold. SHORT: a prior bar closed above range_high, then close_t is back below range_high (within max_bars_since_break). LONG: a prior bar closed below range_low, then close_t is back above range_low. Quant-locked: require_close_inside=True, lookback [16, 20], max_bars_since_break [2, 3], no volume. Not range_compression_volume_thrust (successful thrust). Not expansion_fail_fade (single ATR expansion bar). Not nr7 / orb fail. Not ascending_triangle_break / H&S neckline confirmed breaks. Not prior_day_extreme_reject (prior UTC day H/L). Do not recode asia_close_inventory_fade, wyckoff_spring_reclaim, or the Garwe buffer three.

## What to write

1. `core/strategy/failed_range_break_reversion.py` — `Strategy` subclass, `name = "failed_range_break_reversion"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one LONG and one SHORT entry.
4. Do not copy a rejected family and rename it.
5. Do not call `firm.cursor_coding.mark_done` (that starts walk-forward). Coding only.
