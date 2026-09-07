# Proposal: `prior_close_magnet_fade`

Fade / mean-reversion stretch away from the prior bar's close (the magnet).

Define distance from the current close to the **prior bar close** in ATR units (`atr_n`). When that stretch exceeds threshold `k` ATR, fade back toward the magnet: LONG if stretched below, SHORT if stretched above. Clock: `4h/4h`. Side: BOTH. No volume gate. Not VWAP, not session mid, not week-open reclaim, not CLV persistence, not Wyckoff spring.

## Coding brief (Brian Inbox-approved for coding)

- Clock: `4h/4h`
- Side: `BOTH`
- Status: Brian Inbox-approved for coding (do not start walk-forward)
- Quant lock: `atr_n = 20` LOCKED / not searched; `k` search `[1.2, 1.4]`; max 2 free params (only `k` is free); no volume gate
- Why this is novel: Fade / mean-reversion stretch away from the prior bar close (magnet). Distance is (close_t - close_{t-1}) / ATR(atr_n). LONG when stretched k ATR below the magnet; SHORT when stretched k ATR above. Quant-locked: atr_n=20 (not searched), k search [1.2, 1.4], max 2 free params (only k is free), no volume. Not VWAP / session-VWAP band. Not session mid. Not week-open reclaim. Not CLV persistence. Not Wyckoff spring. Not prior_day_extreme_reject / failed_range_break_reversion / asia_range_london_reject / orb_fail_reversion / nr7_fail_reversion / ib_fail_reversion / converging_wedge_break / engulfing_fail_reversion / wyckoff_spring_reclaim (118–127). Not H&S / asia_close_inventory_fade.

## What to write

1. `core/strategy/prior_close_magnet_fade.py` — `Strategy` subclass, `name = "prior_close_magnet_fade"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one LONG fade and one SHORT fade, kit lock asserts `atr_n` fixed at 20 and `k` searched `[1.2, 1.4]`.
4. Do not copy a rejected family and rename it. Do not recode 118–127. Do not code H&S / `asia_close_inventory_fade`.
5. Do not call `firm.cursor_coding.mark_done` (that starts walk-forward). Coding only.
