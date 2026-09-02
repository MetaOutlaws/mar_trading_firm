# Proposal: `trix_cross`

Trade TRIX crossing zero.

Triple-smoothed ROC is not ema_adx_trend.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs TRIX: rate of change of a triple EMA of close. Not a single EMA+ADX trend.

## What to write

1. `core/strategy/trix_cross.py` — `Strategy` subclass, `name = "trix_cross"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("trix_cross")`.
