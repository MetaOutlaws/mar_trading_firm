# Proposal: `funding_rate_divergence_fade`

Fades extreme perp positioning by identifying structural divergences between price action and funding rates. When price makes a higher high but the 8-hour funding rate makes a lower high (indicating spot-driven exhaustion or aggressive shor

Exploits the structural lead-lag relationship between spot and perpetual swap markets during retail-driven FOMO phases.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `SHORT`
- Why this is novel: Fades extreme perp positioning by identifying structural divergences between price action and funding rates. When price makes a higher high but the 8-hour funding rate makes a lower high (indicating spot-driven exhaustion or aggressive short hedging), the strategy enters a short position on a 4h clock, targeting a reversion to the 20-period EMA.

## What to write

1. `core/strategy/funding_rate_divergence_fade.py` — `Strategy` subclass, `name = "funding_rate_divergence_fade"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("funding_rate_divergence_fade")`.
