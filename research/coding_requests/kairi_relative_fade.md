# Proposal: `kairi_relative_fade`

Fade Kairi Relative Index extremes.

Kairi is percent from SMA, not a band of standard deviation.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs Kairi Relative Index: 100*(close-SMA)/SMA. Percent-from-mean, not Bollinger z-score and not RSI.

## What to write

1. `core/strategy/kairi_relative_fade.py` — `Strategy` subclass, `name = "kairi_relative_fade"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("kairi_relative_fade")`.
