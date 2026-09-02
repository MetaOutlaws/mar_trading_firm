# Proposal: `outside_bar_reversal`

Reverse in the close direction of an outside bar.

Outside-bar geometry is not an existing template.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs an outside bar (range fully contains the prior bar) plus close direction. Opposite of inside-bar breakout.

## What to write

1. `core/strategy/outside_bar_reversal.py` — `Strategy` subclass, `name = "outside_bar_reversal"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("outside_bar_reversal")`.
