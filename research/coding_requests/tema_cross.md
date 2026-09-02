# Proposal: `tema_cross`

Trade TEMA crossing a slow TEMA.

TEMA is a three-EMA identity, not Tillson T3.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs triple EMA: 3*EMA - 3*EMA(EMA) + EMA^3. Not T3's volume-factor cascade and not DEMA.

## What to write

1. `core/strategy/tema_cross.py` — `Strategy` subclass, `name = "tema_cross"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("tema_cross")`.
