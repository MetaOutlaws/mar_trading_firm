# Proposal: `asia_range_london_reject`

Fade a London tag of the completed Asia session high/low that closes back inside that Asia range.

LONG when a London bar tags/pierces Asia low (within `touch_tol_atr * ATR`) and closes back above it, still inside the Asia box. SHORT when a London bar tags/pierces Asia high and closes back below it. Quant-locked: `require_close_inside=True`, `touch_tol_atr` search `[0.0, 0.10]`, fixed Asia 00:00–08:00 UTC and London 08:00–16:00 UTC (not searched). No volume gate.

## Coding brief (Brian Inbox-approved for coding)

- Clock: `4h/4h`
- Side: `BOTH`
- Status: Brian Inbox-approved for coding (do not start walk-forward)
- Quant lock: `require_close_inside=True` (fixed); `touch_tol_atr` search `[0.0, 0.10]`; no volume gate; session bounds fixed
- Why this is novel: London bar tags the completed Asia 00:00–08:00 UTC high/low then closes back inside that Asia range (failed hold of the Asia extreme). LONG: London low tags/pierces Asia low within touch_tol_atr*ATR, close back above Asia low / inside the box. SHORT: London high tags/pierces Asia high, close back below Asia high / inside the box. Quant-locked: require_close_inside=True, touch_tol_atr [0.0, 0.10], fixed Asia 00:00–08:00 and London 08:00–16:00, no volume. Not asia_close_inventory_fade (fade AT Asia close inventory). Not asian_range_breakout (close-through breakout). Not session_liquidity_sweep (1h London+NY, max_sweep_pct cap). Not prior_day_extreme_reject (prior UTC calendar day H/L). Not failed_range_break_reversion (rolling N-bar range). Not monday_range_sweep_reversal. Not range_compression_volume_thrust. Not orb / nr7 fail, H&S, or wyckoff.

## What to write

1. `core/strategy/asia_range_london_reject.py` — `Strategy` subclass, `name = "asia_range_london_reject"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one LONG and one SHORT entry.
4. Do not copy a rejected family and rename it.
5. Do not call `firm.cursor_coding.mark_done` (that starts walk-forward). Coding only.
