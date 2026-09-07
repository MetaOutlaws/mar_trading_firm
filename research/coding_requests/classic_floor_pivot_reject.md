# Proposal: `classic_floor_pivot_reject`

Classic daily floor-trader pivot reject from the prior UTC day's H, L, C.

Define P = (H+L+C)/3, R1 = 2P-L, S1 = 2P-H after that UTC day has closed. SHORT when a 4h bar tags R1 (within `touch_tol_atr`) and closes back below P. LONG when a 4h bar tags S1 (within `touch_tol_atr`) and closes back above P. Clock: `4h/4h`. Side: BOTH. No volume gate. Not prior-session mid, not week-open reclaim, not prior-close magnet, not raw prior-day H/L.

## Coding brief (Brian Inbox-approved for coding)

- Clock: `4h/4h`
- Side: `BOTH`
- Status: Brian Inbox-approved for coding (do not start walk-forward)
- Quant lock: P/R1/S1 formula FIXED / not searched; `touch_tol_atr` search `[0.0, 0.10]`; max 2 free params (only `touch_tol_atr` is free); no volume gate
- Why this is novel: Classic daily floor-trader pivot reject from the prior UTC day H,L,C: P=(H+L+C)/3, R1=2P-L, S1=2P-H. SHORT when a 4h bar tags R1 (within touch_tol_atr) and closes back below P. LONG when a 4h bar tags S1 (within touch_tol_atr) and closes back above P. Quant-locked: P/R1/S1 formula FIXED (not searched), touch_tol_atr search [0.0, 0.10], max 2 free params (only touch_tol_atr is free), no volume. Not prior_session_mid_reclaim (107). Not week_open_reclaim. Not prior_close_magnet_fade (128). Not prior_day_extreme_reject raw H/L (118). Not prior_day_pivot_breakout (close-through R1/S1). Not H&S / asia_close / displacement_gap_follow. Do not recode spent families 118–128.

## What to write

1. `core/strategy/classic_floor_pivot_reject.py` — `Strategy` subclass, `name = "classic_floor_pivot_reject"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one LONG reject and one SHORT reject, kit lock asserts P/R1/S1 formula fixed and `touch_tol_atr` searched `[0.0, 0.10]`.
4. Do not copy a rejected family and rename it. Do not recode 118–128. Do not code H&S / `asia_close_inventory_fade` / `displacement_gap_follow`.
5. Do not call `firm.cursor_coding.mark_done` (that starts walk-forward). Coding only.
