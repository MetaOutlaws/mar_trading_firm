# Proposal: `ultimate_oscillator_fade`

Fade Ultimate Oscillator extremes.

UO mixes three BP/TR windows; it is not a single RSI period.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs Ultimate Oscillator: weighted average of 7/14/28 buying-pressure over true-range sums. Not RSI and not MFI.

## What to write

1. `core/strategy/ultimate_oscillator_fade.py` — `Strategy` subclass, `name = "ultimate_oscillator_fade"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("ultimate_oscillator_fade")`.
