# Proposal: `atr_channel_breakout_4h_short_near_miss`

An ATR channel breakout strategy on a 4h clock restricted to the SHORT side to capture major structural breakdowns while adjusting channel width dynamically to market volatility, with a frozen ADX filter.

4h shorts were the closest to passing our validation gates in previous runs. Freezing the ADX parameter stabilizes the optimization folds.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `SHORT`
- Why this is novel: An ATR channel breakout strategy on a 4h clock restricted to the SHORT side to capture major structural breakdowns while adjusting channel width dynamically to market volatility, with a frozen ADX filter.

## What to write

1. `core/strategy/atr_channel_breakout_4h_short_near_miss.py` — `Strategy` subclass, `name = "atr_channel_breakout_4h_short_near_miss"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("atr_channel_breakout_4h_short_near_miss")`.
