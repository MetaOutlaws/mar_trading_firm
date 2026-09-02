# Approved for Cursor: `squeeze_momentum_break`

The operator approved this brief in Inbox. Implement it now.

# Proposal: `squeeze_momentum_break`

Break after a BB-inside-Keltner squeeze.

Squeeze requires BB inside KC, then momentum, not width only.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs TTM-style squeeze: Bollinger inside Keltner, then a linreg momentum release. Not BB-width squeeze alone.

## What to write

1. `core/strategy/squeeze_momentum_break.py` — `Strategy` subclass, `name = "squeeze_momentum_break"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("squeeze_momentum_break")`.


Source: `C:\Users\PC\mar_trading_firm\research\coding_requests\squeeze_momentum_break.json`
