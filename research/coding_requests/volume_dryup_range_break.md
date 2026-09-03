# Proposal: `volume_dryup_range_break`

Break a 3-bar dry-up box on the first volume-confirmed thrust.

Three quiet-volume bars then a volume-confirmed range break is not ATR-percentile compression and not NR7.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Status: Inbox-approved
- Why this is novel: Needs 3 consecutive bars with volume below the prior-20 mean (current bar excluded), then a thrust bar with volume above that mean that closes beyond the 3-bar high (LONG) or 3-bar low (SHORT). Not range_compression_volume_thrust. Not nr7_breakout. Not squeeze_momentum_break.

## What to write

1. `core/strategy/volume_dryup_range_break.py` — `Strategy` subclass, `name = "volume_dryup_range_break"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one LONG and one SHORT entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("volume_dryup_range_break")`.
