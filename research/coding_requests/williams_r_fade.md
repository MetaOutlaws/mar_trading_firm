# Proposal: `williams_r_fade`

Fade Williams %R extremes.

Williams %R is a distinct range oscillator.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs Williams %R = (HH-C)/(HH-LL). Related to Stochastic but inverted and typically −100..0. Not RSI fade.

## What to write

1. `core/strategy/williams_r_fade.py` — `Strategy` subclass, `name = "williams_r_fade"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("williams_r_fade")`.
