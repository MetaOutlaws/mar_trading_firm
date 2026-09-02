# Proposal: `gator_oscillator_cross`

Trade Gator Oscillator turning from sleep to awake.

Gator is offset SMMA of median price, not an EMA histogram.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs Bill Williams Gator: SMMA of median price at 13/8/5 with 8/5/3 offsets, then jaw-teeth and teeth-lips as a two-sided oscillator. Not Alligator-only and not MACD of close.

## What to write

1. `core/strategy/gator_oscillator_cross.py` — `Strategy` subclass, `name = "gator_oscillator_cross"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("gator_oscillator_cross")`.
