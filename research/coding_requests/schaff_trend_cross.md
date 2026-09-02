# Proposal: `schaff_trend_cross`

Trade STC crossing 25/75.

STC is a cycle transform of MACD, not ema_adx_trend.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs Schaff Trend Cycle: a stochastic of MACD, then a second stochastic. Not MACD histogram and not Stochastic %K of price.

## What to write

1. `core/strategy/schaff_trend_cross.py` — `Strategy` subclass, `name = "schaff_trend_cross"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("schaff_trend_cross")`.
