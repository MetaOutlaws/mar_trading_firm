# Proposal: `close_location_persistence`

Auction location persistence across bars. Mean CLV stays high (low) without a new 20-bar close extreme.

A doji at the high has CLV near 1 and body efficiency near 0. This is not body occupancy, not a wick rejection, not turnover, not session/VWAP, and not week-open.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Status: Inbox-approved
- Why this is novel: Needs CLV=(close-low)/(high-low) averaged over lookback (default 8). LONG when mean CLV>=0.75 and current close is not a 20-bar high. SHORT when mean CLV<=0.25 and current close is not a 20-bar low. Free params: lookback, clv_threshold. Not body_efficiency_follow. Not wick_rejection_reversal. Not turnover, session/VWAP, or week-open.

## What to write

1. `core/strategy/close_location_persistence.py` — `Strategy` subclass, `name = "close_location_persistence"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one LONG and one SHORT entry.
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("close_location_persistence")`.
