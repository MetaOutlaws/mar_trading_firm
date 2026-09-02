# Proposal: `volume_weighted_force_breakout`

Calculates a Volume-Weighted Force Index (VWFI) by multiplying the directional close-to-close change by volume, normalized by a rolling 20-period ATR. It enters a breakout trade on a 4h clock when the VWFI crosses above a positive threshold

Ensures that breakout entries are only triggered when there is significant institutional volume backing the directional expansion, avoiding low-liquidity traps.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Calculates a Volume-Weighted Force Index (VWFI) by multiplying the directional close-to-close change by volume, normalized by a rolling 20-period ATR. It enters a breakout trade on a 4h clock when the VWFI crosses above a positive threshold (for longs) or below a negative threshold (for shorts).

## What to write

1. `core/strategy/volume_weighted_force_breakout.py` — `Strategy` subclass, `name = "volume_weighted_force_breakout"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("volume_weighted_force_breakout")`.
