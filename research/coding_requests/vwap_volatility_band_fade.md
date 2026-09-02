# Proposal: `vwap_volatility_band_fade`

Constructs dynamic bands around a rolling 20-period VWAP using a multiplier of the rolling standard deviation of price. When price touches the outer band on a 1h clock and the Bollinger Band Width is in the bottom 30% of its 100-bar range (

Exploits the mean-reverting nature of crypto assets when they stretch to statistical extremes during periods of low macro volatility.

## Coding brief (implement this after Inbox approve)

- Clock: `1h/1h`
- Side: `BOTH`
- Why this is novel: Constructs dynamic bands around a rolling 20-period VWAP using a multiplier of the rolling standard deviation of price. When price touches the outer band on a 1h clock and the Bollinger Band Width is in the bottom 30% of its 100-bar range (indicating compression), it enters a reversion trade back to the VWAP.

## What to write

1. `core/strategy/vwap_volatility_band_fade.py` — `Strategy` subclass, `name = "vwap_volatility_band_fade"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("vwap_volatility_band_fade")`.
