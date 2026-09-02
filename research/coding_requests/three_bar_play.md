# Proposal: `three_bar_play`

Break the rest bar of a 3-bar play.

Three-bar structure is not inside-bar and not Donchian.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs a 3-bar play: trend bar, narrow rest bar inside it, then a break of the rest bar in the trend direction.

## What to write

1. `core/strategy/three_bar_play.py` — `Strategy` subclass, `name = "three_bar_play"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("three_bar_play")`.
