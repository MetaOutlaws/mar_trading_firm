# Proposal: `choppiness_index_break`

Break after Choppiness Index compresses.

CI is a range-efficiency log ratio, not ATR-channel breakout.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs Choppiness Index: 100*log10(sum(ATR)/range)/log10(n). Break when CI falls from a high reading. Not BB width squeeze and not ADX.

## What to write

1. `core/strategy/choppiness_index_break.py` — `Strategy` subclass, `name = "choppiness_index_break"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("choppiness_index_break")`.
