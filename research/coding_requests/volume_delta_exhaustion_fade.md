# Proposal: `volume_delta_exhaustion_fade`

Calculates a rolling Cumulative Volume Delta (CVD) over a 20-bar window. When price prints a new high but CVD prints a lower high (or price prints a new low but CVD prints a higher low), it triggers a mean-reversion trade targeting the 20-p

Directly targets institutional limit order absorption at key liquidity pools, which is highly effective in choppy, non-trending regimes.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Calculates a rolling Cumulative Volume Delta (CVD) over a 20-bar window. When price prints a new high but CVD prints a lower high (or price prints a new low but CVD prints a higher low), it triggers a mean-reversion trade targeting the 20-period EMA, filtered by a low ADX to ensure a range-bound regime.

## What to write

1. `core/strategy/volume_delta_exhaustion_fade.py` — `Strategy` subclass, `name = "volume_delta_exhaustion_fade"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("volume_delta_exhaustion_fade")`.
