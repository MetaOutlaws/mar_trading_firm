# Proposal: `vwap_spread_exhaustion`

Calculates the absolute distance between the rolling 20-period VWAP and the 20-period SMA, normalized by the 20-period ATR. When this spread reaches an N-bar extreme and volume is expanding, it enters a mean-reversion trade targeting the VW

It exploits institutional execution limits where aggressive market orders push price away from the volume-weighted average, creating temporary liquidity vacuums that revert when the flow pauses.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Calculates the absolute distance between the rolling 20-period VWAP and the 20-period SMA, normalized by the 20-period ATR. When this spread reaches an N-bar extreme and volume is expanding, it enters a mean-reversion trade targeting the VWAP basis, filtered by a low ADX to ensure a range-bound environment.

## What to write

1. `core/strategy/vwap_spread_exhaustion.py` — `Strategy` subclass, `name = "vwap_spread_exhaustion"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("vwap_spread_exhaustion")`.
