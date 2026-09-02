# Proposal: `balance_of_power_cross`

Trade BOP crossing zero.

BOP is a single-bar body/range ratio, not RVI's dual SMA.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs Balance of Power: (close-open)/(high-low), then SMA. Not Qstick of raw bodies and not RVI of those SMAs.

## What to write

1. `core/strategy/balance_of_power_cross.py` — `Strategy` subclass, `name = "balance_of_power_cross"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("balance_of_power_cross")`.
