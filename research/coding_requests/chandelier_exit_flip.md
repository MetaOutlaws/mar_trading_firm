# Proposal: `chandelier_exit_flip`

Trade a Chandelier Exit flip.

Chandelier trails ATR from HH/LL, not SAR AF steps.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs Chandelier Exit: ATR trail from the extreme high/low since entry side, flip on a close through the trail. Not Parabolic SAR acceleration.

## What to write

1. `core/strategy/chandelier_exit_flip.py` — `Strategy` subclass, `name = "chandelier_exit_flip"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("chandelier_exit_flip")`.
