# Proposal: `connors_rsi_fade`

Fade Connors RSI extremes.

Connors RSI mixes streak and rank; Wilder RSI does not.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs Connors RSI: average of RSI(3), streak RSI, and percentile rank of ROC. Not a single-period RSI fade.

## What to write

1. `core/strategy/connors_rsi_fade.py` — `Strategy` subclass, `name = "connors_rsi_fade"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("connors_rsi_fade")`.
