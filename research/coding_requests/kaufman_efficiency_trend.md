# Proposal: `kaufman_efficiency_trend`

Trade in the direction of a high-ER move.

ER is path-efficiency, not DI smoothing.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs Kaufman Efficiency Ratio: abs(close-close[n]) / sum(|close diffs|). Not ADX and not Aroon time-since-extreme.

## What to write

1. `core/strategy/kaufman_efficiency_trend.py` — `Strategy` subclass, `name = "kaufman_efficiency_trend"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("kaufman_efficiency_trend")`.
