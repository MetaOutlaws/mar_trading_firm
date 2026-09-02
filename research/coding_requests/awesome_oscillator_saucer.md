# Proposal: `awesome_oscillator_saucer`

Enter on an Awesome Oscillator saucer.

AO uses midpoint SMAs, not close MACD.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs Awesome Oscillator: SMA(HL2,5) - SMA(HL2,34). Saucer is three histogram bars, not MACD.

## What to write

1. `core/strategy/awesome_oscillator_saucer.py` — `Strategy` subclass, `name = "awesome_oscillator_saucer"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("awesome_oscillator_saucer")`.
