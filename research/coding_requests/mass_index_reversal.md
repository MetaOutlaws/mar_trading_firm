# Proposal: `mass_index_reversal`

Reverse after a Mass Index bulge.

Mass Index is a range-ratio bulge, not a squeeze of Bollinger width.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs Mass Index: EMA(high-low,9) / EMA of that EMA, then a 25-bar sum and a bulge-then-reversal. Not ATR and not BB width.

## What to write

1. `core/strategy/mass_index_reversal.py` — `Strategy` subclass, `name = "mass_index_reversal"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("mass_index_reversal")`.
