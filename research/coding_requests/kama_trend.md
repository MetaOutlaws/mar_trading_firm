# Proposal: `kama_trend`

Trade a KAMA turn.

KAMA adapts with efficiency ratio; VIDYA adapts with CMO.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs Kaufman Adaptive Moving Average: ER-scaled smoothing constant between fast and slow SC. Not the ER-only kaufman_efficiency_trend sleeve and not VIDYA.

## What to write

1. `core/strategy/kama_trend.py` — `Strategy` subclass, `name = "kama_trend"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("kama_trend")`.
