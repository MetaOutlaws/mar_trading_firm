# Proposal: `elder_impulse_trend`

Trade when Elder Impulse turns green or red.

Impulse requires EMA slope AND MACD hist, not ADX.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs Elder Impulse: EMA slope and MACD histogram both green/red. Not ema_adx_trend and not MACD-only.

## What to write

1. `core/strategy/elder_impulse_trend.py` — `Strategy` subclass, `name = "elder_impulse_trend"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("elder_impulse_trend")`.
