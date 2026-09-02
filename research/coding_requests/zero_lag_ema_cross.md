# Proposal: `zero_lag_ema_cross`

Trade zero-lag EMA crossing a slow EMA.

ZLEMA error-corrects lag; a plain EMA cross does not.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs Ehlers zero-lag EMA: 2*EMA - EMA(EMA). Not MACD of raw EMAs and not T3.

## What to write

1. `core/strategy/zero_lag_ema_cross.py` — `Strategy` subclass, `name = "zero_lag_ema_cross"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("zero_lag_ema_cross")`.
