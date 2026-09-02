# Proposal: `stochastic_rsi_volatility_squeeze`

Applies a 14-period Stochastic formula to the RSI indicator itself, but only triggers entries when the Bollinger Band Width is in the bottom 20% of its 100-bar range (indicating extreme volatility compression). It enters a mean-reversion tr

Filters out false signals by ensuring mean-reversion is only traded when volatility is compressed and a explosive expansion is statistically overdue.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Applies a 14-period Stochastic formula to the RSI indicator itself, but only triggers entries when the Bollinger Band Width is in the bottom 20% of its 100-bar range (indicating extreme volatility compression). It enters a mean-reversion trade when the Stochastic of RSI crosses back from overbought (>80) or oversold (<20) thresholds on a 4h clock.

## What to write

1. `core/strategy/stochastic_rsi_volatility_squeeze.py` — `Strategy` subclass, `name = "stochastic_rsi_volatility_squeeze"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("stochastic_rsi_volatility_squeeze")`.
