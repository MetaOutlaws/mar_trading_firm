# Proposal: `asian_range_breakout`

Break the completed Asian (00:00–08:00 UTC) range.

An 8-hour session box is different bar math from a 1-hour ORB.

## Coding brief (implement this after Inbox approve)

- Clock: `1h/1h`
- Side: `BOTH`
- Why this is novel: Needs the high/low of 00:00–08:00 UTC, published only after 08:00. Not the 1-hour opening range and not a rolling Donchian.

## What to write

1. `core/strategy/asian_range_breakout.py` — `Strategy` subclass, `name = "asian_range_breakout"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("asian_range_breakout")`.
