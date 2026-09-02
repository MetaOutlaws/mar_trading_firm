# Proposal: `wick_rejection_reversal`

Enter when a long wick rejects and close re-enters the body zone.

Candle geometry is not an existing template input.

## Coding brief (implement this after Inbox approve)

- Clock: `1h/1h`
- Side: `BOTH`
- Why this is novel: Needs wick/body ratios vs the bar range, with close back inside. Not a Bollinger touch and not ATR stretch.

## What to write

1. `core/strategy/wick_rejection_reversal.py` — `Strategy` subclass, `name = "wick_rejection_reversal"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("wick_rejection_reversal")`.
