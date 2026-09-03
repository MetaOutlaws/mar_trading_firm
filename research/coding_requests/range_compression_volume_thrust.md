# Proposal: `range_compression_volume_thrust`

Follow a volume-thrust bar that exits ATR compression.

ATR-percentile compression plus a volume-confirmed range expansion is not a BB-width squeeze and not NR7.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Status: Inbox-approved
- Why this is novel: Needs 20-bar ATR in the bottom 30% of its 100-bar range, then a bar with true range > 1.5× ATR, close in the bar's direction, and volume above the prior-20 mean. Compression is ATR percentile only. Not squeeze_momentum_break. Not nr7_breakout. Not bb_squeeze_breakout.

## What to write

1. `core/strategy/range_compression_volume_thrust.py` — `Strategy` subclass, `name = "range_compression_volume_thrust"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one LONG and one SHORT entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("range_compression_volume_thrust")`.
