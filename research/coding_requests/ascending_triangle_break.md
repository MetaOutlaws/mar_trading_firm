# Proposal: `ascending_triangle_break`

Break an ascending triangle on volume (descending-triangle inverse for shorts).

LONG needs at least two rising swing lows into a flat swing-high cap, then a close through the cap with volume above the prior-20 mean. SHORT is the descending-triangle inverse. Volume threshold is locked; free params are lookback and atr_tol only.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Status: Inbox-approved
- Why this is novel: LONG: at least two rising swing lows (each low > prior swing low) into a flat swing-high cap (highs within 0.15*ATR(20)), then close_t through the cap AND volume_t > mean(volume_{t-20..t-1}). SHORT: descending-triangle inverse, at least two falling swing highs into a flat swing-low floor, then close through the floor on volume above prior-20 mean. Free params: lookback (default 40), atr_tol. Volume threshold is fixed as prior-20 mean, not a third param. Not NR7. Not range_compression_volume_thrust (102, compression then thrust, no triangle geometry). Not inside_bar_breakout. Not squeeze_momentum_break (dead, do not recode).

## What to write

1. `core/strategy/ascending_triangle_break.py` — `Strategy` subclass, `name = "ascending_triangle_break"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one LONG and one SHORT entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("ascending_triangle_break")`.
