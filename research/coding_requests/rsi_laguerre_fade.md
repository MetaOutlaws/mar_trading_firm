# Proposal: `rsi_laguerre_fade`

Fade Laguerre RSI extremes.

Laguerre RSI is a FIR gamma filter, not Wilder smoothing.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs Ehlers Laguerre RSI: a 4-pole Laguerre filter of close mapped to 0..1. Not Wilder RSI and not Connors RSI.

## What to write

1. `core/strategy/rsi_laguerre_fade.py` — `Strategy` subclass, `name = "rsi_laguerre_fade"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("rsi_laguerre_fade")`.
