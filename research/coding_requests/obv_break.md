# Proposal: `obv_break`

Break the OBV channel, not the price channel.

Volume ledger break is not a price-channel clone.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs On-Balance Volume cumulative signed volume, then a break of its own N-bar high/low. Not price Donchian.

## What to write

1. `core/strategy/obv_break.py` — `Strategy` subclass, `name = "obv_break"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("obv_break")`.
