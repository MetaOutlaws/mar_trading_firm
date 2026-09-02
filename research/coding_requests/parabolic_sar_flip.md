# Proposal: `parabolic_sar_flip`

Trade a Parabolic SAR flip.

SAR acceleration is a distinct stop geometry from SuperTrend.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs Wilder Parabolic SAR: accelerating stop that flips on a stop hit. Not SuperTrend ATR bands.

## What to write

1. `core/strategy/parabolic_sar_flip.py` — `Strategy` subclass, `name = "parabolic_sar_flip"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("parabolic_sar_flip")`.
