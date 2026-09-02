# Proposal: `chaikin_money_flow_fade`

Fade Chaikin Money Flow extremes.

CMF is a windowed CLV volume ratio, not an EMA of ADL.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs Chaikin Money Flow: sum(CLV*volume)/sum(volume) over N. Not Twiggs TR-buffer and not Chaikin Oscillator of ADL.

## What to write

1. `core/strategy/chaikin_money_flow_fade.py` — `Strategy` subclass, `name = "chaikin_money_flow_fade"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("chaikin_money_flow_fade")`.
