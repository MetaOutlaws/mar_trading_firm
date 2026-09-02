# Proposal: `elder_ray_index_reversion`

Calculates the Elder-Ray Index (Bull Power and Bear Power) based on the distance between bar extremes and an exponential moving average. When Bull Power reaches an N-bar low while price makes a higher high (or Bear Power reaches an N-bar hi

It directly measures the ability of buyers/sellers to push prices to extremes relative to the consensus value, capturing exhaustion at key structural levels.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Calculates the Elder-Ray Index (Bull Power and Bear Power) based on the distance between bar extremes and an exponential moving average. When Bull Power reaches an N-bar low while price makes a higher high (or Bear Power reaches an N-bar high while price makes a lower low), it enters a mean-reversion trade targeting the EMA basis.

## What to write

1. `core/strategy/elder_ray_index_reversion.py` — `Strategy` subclass, `name = "elder_ray_index_reversion"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("elder_ray_index_reversion")`.
