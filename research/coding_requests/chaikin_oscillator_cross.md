# Proposal: `chaikin_oscillator_cross`

Trade Chaikin Oscillator crossing zero.

ADL uses close location in the bar, not close-to-close OBV.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs Chaikin Oscillator: EMA(ADL,3)-EMA(ADL,10) where ADL is cumulative CLV*volume. Not OBV and not MACD of close.

## What to write

1. `core/strategy/chaikin_oscillator_cross.py` — `Strategy` subclass, `name = "chaikin_oscillator_cross"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("chaikin_oscillator_cross")`.
