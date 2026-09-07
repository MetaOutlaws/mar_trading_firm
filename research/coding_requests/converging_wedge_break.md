# Proposal: `converging_wedge_break`

Break a converging wedge where both rails slope and converge: SHORT a rising wedge (HH+HL) on a close below the lower rail; LONG a falling wedge (LH+LL) on a close above the upper rail.

## Coding brief (Brian Inbox-approved for coding)

- Clock: `4h/4h`
- Side: `BOTH`
- Status: Brian Inbox-approved for coding (do not start walk-forward)
- Quant lock: `min_touches=3` (fixed / not searched); `lookback` search `[30, 40]`; no volume gate
- Why this is novel: Converging wedge break (both rails slope and converge). Rising wedge (HH+HL both slope up, converge): SHORT on close below the lower rail. Falling wedge (LH+LL both slope down, converge): LONG on close above the upper rail. Quant-locked: min_touches=3 (not searched), lookback [30, 40], no volume. Not ascending_triangle_break (one rail flat). Not ib_fail_reversion (124 — inside-bar fail). Not nr7 / orb_fail / asia_range / prior_day / failed_range (118–123). Not engulfing_fail / prior_week_extreme. Not H&S / asia_close / wyckoff.

## What to write

1. `core/strategy/converging_wedge_break.py` — `Strategy` subclass, `name = "converging_wedge_break"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one LONG and one SHORT entry, held breakout does not fire, both-rails-slope asserted.
4. Do not copy a rejected family and rename it.
5. Do not call `firm.cursor_coding.mark_done` (that starts walk-forward). Coding only.
