# Proposal: `chaikin_oscillator_momentum`

Applies a MACD-style formula to the Accumulation Distribution Line (ADL) rather than price. It enters trend-following positions when the Chaikin Oscillator crosses zero, indicating that volume-weighted accumulation is accelerating in the di

It ensures that trend entries are only triggered when volume flow actively supports the directional expansion.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Applies a MACD-style formula to the Accumulation Distribution Line (ADL) rather than price. It enters trend-following positions when the Chaikin Oscillator crosses zero, indicating that volume-weighted accumulation is accelerating in the direction of the price move.

## What to write

1. `core/strategy/chaikin_oscillator_momentum.py` — `Strategy` subclass, `name = "chaikin_oscillator_momentum"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("chaikin_oscillator_momentum")`.
