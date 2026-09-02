# Proposal: `volume_force_divergence_fade`

Calculates a cumulative Volume Force index (signed volume based on close-to-close price change normalized by ATR). It triggers a mean-reversion trade when price makes a new 20-period high or low but the Volume Force fails to confirm (printi

It directly targets the lack of institutional participation on marginal new highs/lows in a range-bound market, preventing buying the top of weak breakouts.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Calculates a cumulative Volume Force index (signed volume based on close-to-close price change normalized by ATR). It triggers a mean-reversion trade when price makes a new 20-period high or low but the Volume Force fails to confirm (printing a clear divergence), filtered by a low ADX to ensure a range-bound regime.

## What to write

1. `core/strategy/volume_force_divergence_fade.py` — `Strategy` subclass, `name = "volume_force_divergence_fade"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("volume_force_divergence_fade")`.
