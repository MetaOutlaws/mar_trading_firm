# Proposal: `opening_range_breakout`

Break the first N-hour range of the UTC day.

Crypto session structure is untested here; requires new bar math.

## Coding brief (implement this after Inbox approve)

- Clock: `1h/1h`
- Side: `BOTH`
- Why this is novel: Needs a session opening-range high/low (UTC or US cash hours) that the indicator library does not compute. Do not fake it with a rolling Donchian.

## What to write

1. `core/strategy/opening_range_breakout.py` — `Strategy` subclass, `name = "opening_range_breakout"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("opening_range_breakout")`.
