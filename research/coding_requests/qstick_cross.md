# Proposal: `qstick_cross`

Trade Qstick crossing zero.

Qstick averages raw candle bodies, not reconstructed HA bars.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs Qstick: SMA of (close-open). Candle-body oscillator, not close MACD and not Heikin-Ashi.

## What to write

1. `core/strategy/qstick_cross.py` — `Strategy` subclass, `name = "qstick_cross"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("qstick_cross")`.
