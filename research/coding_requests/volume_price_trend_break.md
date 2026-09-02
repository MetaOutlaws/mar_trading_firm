# Proposal: `volume_price_trend_break`

Break the VPT channel.

VPT scales volume by percent change; OBV is only sign(close).

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs Volume Price Trend: cumulative (close-change %)*volume, then a break of its own N-bar high. Not OBV which uses only close direction.

## What to write

1. `core/strategy/volume_price_trend_break.py` — `Strategy` subclass, `name = "volume_price_trend_break"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("volume_price_trend_break")`.
