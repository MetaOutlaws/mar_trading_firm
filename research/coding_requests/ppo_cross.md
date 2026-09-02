# Proposal: `ppo_cross`

Trade PPO crossing its signal line.

PPO is a percent MACD, not ema_adx_trend.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs Percentage Price Oscillator: 100*(EMA12-EMA26)/EMA26, signal EMA9 of PPO. Not MACD histogram in price units.

## What to write

1. `core/strategy/ppo_cross.py` — `Strategy` subclass, `name = "ppo_cross"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("ppo_cross")`.
