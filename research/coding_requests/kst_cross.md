# Proposal: `kst_cross`

Trade KST crossing its signal line.

KST is a stacked ROC composite, not a dual-EMA MACD.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs Know Sure Thing: weighted sum of four ROC SMAs plus a signal SMA. Not MACD of close and not PPO.

## What to write

1. `core/strategy/kst_cross.py` — `Strategy` subclass, `name = "kst_cross"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("kst_cross")`.
