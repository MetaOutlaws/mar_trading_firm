# Proposal: `aroon_crossover`

Trade Aroon up crossing Aroon down.

Time-since-extreme is different from a channel break.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs Aroon up/down: bars since N-bar high vs low. Not Donchian break and not ADX.

## What to write

1. `core/strategy/aroon_crossover.py` — `Strategy` subclass, `name = "aroon_crossover"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("aroon_crossover")`.
