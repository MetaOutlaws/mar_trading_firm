# Proposal: `volume_weighted_macd_cross`

Trade volume-weighted MACD crossing its signal.

VW-MACD weights by volume; standard MACD does not.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs MACD of VWMA(close, volume) rather than EMA of close. Not PPO and not a volume-less MACD.

## What to write

1. `core/strategy/volume_weighted_macd_cross.py` — `Strategy` subclass, `name = "volume_weighted_macd_cross"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("volume_weighted_macd_cross")`.
