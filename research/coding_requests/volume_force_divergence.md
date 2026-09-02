# Proposal: `volume_force_divergence`

Calculates the cumulative Volume Force (signed volume based on close-to-close price change normalized by ATR). It triggers a mean-reversion trade when price makes a new 20-period high/low but the Volume Force fails to confirm (divergence), 

Exposes institutional distribution or accumulation that is hidden behind small price candles with massive volume.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Calculates the cumulative Volume Force (signed volume based on close-to-close price change normalized by ATR). It triggers a mean-reversion trade when price makes a new 20-period high/low but the Volume Force fails to confirm (divergence), filtered by a low ADX to ensure a range-bound regime.

## What to write

1. `core/strategy/volume_force_divergence.py` — `Strategy` subclass, `name = "volume_force_divergence"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("volume_force_divergence")`.
