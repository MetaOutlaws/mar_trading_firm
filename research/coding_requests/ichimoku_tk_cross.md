# Proposal: `ichimoku_tk_cross`

Trade Tenkan crossing Kijun.

Ichimoku midpoints are high-low averages, not EMAs.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs Tenkan/Kijun midpoints of 9/26-bar high-low (no displaced cloud, which would leak future bars). Not EMA cross.

## What to write

1. `core/strategy/ichimoku_tk_cross.py` — `Strategy` subclass, `name = "ichimoku_tk_cross"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("ichimoku_tk_cross")`.
