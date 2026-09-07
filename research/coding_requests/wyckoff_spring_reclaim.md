# Proposal: `wyckoff_spring_reclaim`

Wyckoff spring / failed-breakdown reclaim of a recent lookback range low, with the upthrust mirror for shorts.

Identify a recent range low over `lookback` prior bars. SPRING: price briefly trades below that low (liquidity grab) then CLOSES back above it within `hold_bars`. LONG on the reclaim close. SHORT when price trades above a range high then closes back below (upthrust). `hold_bars=1` is a same-bar wick spring; `hold_bars=2` also allows a next-bar reclaim after a grab that did not close back through. Clock: `4h/4h`. Side: BOTH. No volume gate. Not a close-through failed-range fade (119).

## Coding brief (Brian Inbox-approved for coding)

- Clock: `4h/4h`
- Side: `BOTH`
- Status: Brian Inbox-approved for coding (do not start walk-forward)
- Quant lock: `lookback` search `[16, 20]`; `hold_bars` search `[1, 2]`; max 2 free params; no volume gate
- Why this is novel: Wyckoff spring / failed-breakdown reclaim: identify a recent range low over lookback prior bars, then a liquidity grab that trades below that low and CLOSES back above it within hold_bars. LONG on the reclaim close. SHORT is the upthrust (trade above a range high, close back below). Quant-locked: lookback [16, 20], hold_bars [1, 2], no volume. Not failed_range_break_reversion (119 — close-through then later fail). Not prior_day_extreme_reject (118). Not asia_range_london_reject (120). Not orb / nr7 / ib fail (121–124). Not converging_wedge / engulfing_fail (125–126). Not equal_high_low_restest_fade. Not swing_failure_reversal. Not H&S / asia_close / prior_close_magnet_fade. Do not recode the 118–126 spent families.

## What to write

1. `core/strategy/wyckoff_spring_reclaim.py` — `Strategy` subclass, `name = "wyckoff_spring_reclaim"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one LONG spring and one SHORT upthrust, kit lock asserts `lookback` `[16, 20]` and `hold_bars` `[1, 2]`.
4. Do not copy a rejected family and rename it. Do not recode 118–126. Do not code `prior_close_magnet_fade`.
5. Do not call `firm.cursor_coding.mark_done` (that starts walk-forward). Coding only.
