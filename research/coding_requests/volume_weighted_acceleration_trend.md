# Proposal: `volume_weighted_acceleration_trend`

Calculates the second derivative (acceleration) of a volume-weighted moving average (VWMA) of price. It enters trend-following positions on a 4h clock when the acceleration crosses zero, indicating that the trend is actively speeding up wit

Ensures trend entries are backed by both volume expansion and momentum acceleration, avoiding late entries into exhausted trends.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Calculates the second derivative (acceleration) of a volume-weighted moving average (VWMA) of price. It enters trend-following positions on a 4h clock when the acceleration crosses zero, indicating that the trend is actively speeding up with volume support.

## What to write

1. `core/strategy/volume_weighted_acceleration_trend.py` — `Strategy` subclass, `name = "volume_weighted_acceleration_trend"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("volume_weighted_acceleration_trend")`.
