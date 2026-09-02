# Proposal: `coppock_curve_cross`

Trade Coppock Curve crossing zero.

Coppock is a WMA of two ROCs, not a triple EMA.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs Coppock Curve: WMA of ROC(14)+ROC(11). Long-horizon ROC sum, not MACD and not TRIX.

## What to write

1. `core/strategy/coppock_curve_cross.py` — `Strategy` subclass, `name = "coppock_curve_cross"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("coppock_curve_cross")`.
