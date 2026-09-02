# Proposal: `nr7_breakout`

Break the NR7 bar after the narrowest of 7 prints.

NR7 is a range-rank, not a squeeze of Bollinger width.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs the narrowest range of the last 7 bars (NR7), then a close beyond that bar. Not BB squeeze and not Donchian.

## What to write

1. `core/strategy/nr7_breakout.py` — `Strategy` subclass, `name = "nr7_breakout"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("nr7_breakout")`.
