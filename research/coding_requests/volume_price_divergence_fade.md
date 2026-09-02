# Proposal: `volume_price_divergence_fade`

Fades price extremes on a 4h clock when price makes a new 20-bar high or low but volume-weighted accumulation-distribution (or volume force) fails to confirm, printing a clear divergence. This signals that aggressive market orders are being

It directly exploits institutional limit order absorption at key liquidity pools, which is highly effective in choppy, non-trending regimes.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Fades price extremes on a 4h clock when price makes a new 20-bar high or low but volume-weighted accumulation-distribution (or volume force) fails to confirm, printing a clear divergence. This signals that aggressive market orders are being absorbed by passive limit orders, indicating an impending reversal.

## What to write

1. `core/strategy/volume_price_divergence_fade.py` — `Strategy` subclass, `name = "volume_price_divergence_fade"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("volume_price_divergence_fade")`.
