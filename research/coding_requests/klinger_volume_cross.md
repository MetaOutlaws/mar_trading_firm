# Proposal: `klinger_volume_cross`

Trade Klinger Volume Oscillator crossing its signal.

KVO signs volume from HLC trend, not close-to-close force.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs Klinger Volume Oscillator: EMA of signed volume based on high-low-close trend, fast minus slow, plus a signal EMA. Not Force Index and not Chaikin.

## What to write

1. `core/strategy/klinger_volume_cross.py` — `Strategy` subclass, `name = "klinger_volume_cross"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("klinger_volume_cross")`.
