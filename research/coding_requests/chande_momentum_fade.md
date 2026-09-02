# Proposal: `chande_momentum_fade`

Fade CMO extremes.

CMO is a sum-of-change oscillator, not RSI.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs Chande Momentum Oscillator: (sum up - sum down)/(sum up + sum down) over N closes, scaled to -100..100. Not RSI Wilder smoothing.

## What to write

1. `core/strategy/chande_momentum_fade.py` — `Strategy` subclass, `name = "chande_momentum_fade"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("chande_momentum_fade")`.
