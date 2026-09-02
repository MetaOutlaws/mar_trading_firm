# Proposal: `engulfing_reversal`

Reverse when a bar's body fully engulfs the prior body.

Two-bar engulfing is pattern math, not a stretch template.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs a two-bar engulfing rule (current body fully covers prior body) plus close direction. Not RSI fade and not inside-bar.

## What to write

1. `core/strategy/engulfing_reversal.py` — `Strategy` subclass, `name = "engulfing_reversal"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("engulfing_reversal")`.
