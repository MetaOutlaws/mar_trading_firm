# Proposal: `hull_ma_trend`

Trade in the direction of a Hull MA turn.

HMA weighting is distinct from EMA/SMA trend sleeves.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs Hull Moving Average: WMA(2*WMA(n/2) - WMA(n), sqrt(n)). Not EMA and not SMA.

## What to write

1. `core/strategy/hull_ma_trend.py` — `Strategy` subclass, `name = "hull_ma_trend"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("hull_ma_trend")`.
