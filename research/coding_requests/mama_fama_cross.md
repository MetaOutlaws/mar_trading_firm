# Proposal: `mama_fama_cross`

Trade MAMA crossing FAMA.

MAMA is a Hilbert-period adaptive MA, not a fixed-length EMA.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs Ehlers MAMA/FAMA: MESA adaptive moving averages from Hilbert period. Not EMA cross and not Hull MA.

## What to write

1. `core/strategy/mama_fama_cross.py` — `Strategy` subclass, `name = "mama_fama_cross"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("mama_fama_cross")`.
