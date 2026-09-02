# Proposal: `linreg_slope_cross`

Trade linear-regression slope crossing zero.

OLS slope is a fit, not a moving-average difference.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs least-squares slope of close over N bars, then a zero cross. Not EMA trend and not Coppock ROC.

## What to write

1. `core/strategy/linreg_slope_cross.py` — `Strategy` subclass, `name = "linreg_slope_cross"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("linreg_slope_cross")`.
