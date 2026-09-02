# Proposal: `stochrsi_fade`

Fade Stochastic RSI extremes.

StochRSI ranks RSI, not close, inside its own window.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs Stochastic RSI: %K of Wilder RSI over N. Not Stochastic of price and not a single RSI fade.

## What to write

1. `core/strategy/stochrsi_fade.py` — `Strategy` subclass, `name = "stochrsi_fade"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("stochrsi_fade")`.
