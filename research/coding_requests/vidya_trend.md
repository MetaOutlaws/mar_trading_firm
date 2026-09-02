# Proposal: `vidya_trend`

Trade a VIDYA turn.

VIDYA uses CMO for alpha; KAMA uses efficiency ratio.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs VIDYA: CMO-scaled EMA of close. Adaptive alpha from Chande momentum, not Kaufman ER and not MAMA Hilbert period.

## What to write

1. `core/strategy/vidya_trend.py` — `Strategy` subclass, `name = "vidya_trend"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("vidya_trend")`.
