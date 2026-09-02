# Proposal: `twiggs_money_flow_fade`

Fade Twiggs Money Flow extremes.

TMF uses a TR buffer, not typical-price MFI.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs Twiggs Money Flow: true-range AD buffer into volume, then EMA ratio. Not MFI and not Chaikin.

## What to write

1. `core/strategy/twiggs_money_flow_fade.py` — `Strategy` subclass, `name = "twiggs_money_flow_fade"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("twiggs_money_flow_fade")`.
