# Proposal: `demarker_fade`

Fade DeMarker extremes.

DeMarker uses bar-to-bar high/low steps, not a close oscillator.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs DeMarker: SMA of DeMax / (DeMax+DeMin) from high-to-high and low-to-low steps. Not Stochastic %K of close and not RSI.

## What to write

1. `core/strategy/demarker_fade.py` — `Strategy` subclass, `name = "demarker_fade"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("demarker_fade")`.
