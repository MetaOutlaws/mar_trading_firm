# Proposal: `mfi_fade`

Fade Money Flow Index extremes.

MFI is volume-weighted RSI, not close-only RSI.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs Money Flow Index (typical price * volume, positive vs negative flow RSI). Not RSI(close) and not volume climax.

## What to write

1. `core/strategy/mfi_fade.py` — `Strategy` subclass, `name = "mfi_fade"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("mfi_fade")`.
