# Proposal: `relative_vigor_cross`

Trade RVI crossing its signal line.

RVI normalizes body by range; Qstick does not.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs Relative Vigor Index: SMA of (close-open)/(high-low) vs its signal SMA. Not RSI and not Qstick of close-open alone.

## What to write

1. `core/strategy/relative_vigor_cross.py` — `Strategy` subclass, `name = "relative_vigor_cross"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("relative_vigor_cross")`.
