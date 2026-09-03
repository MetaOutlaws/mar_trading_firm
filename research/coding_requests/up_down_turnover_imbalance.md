# Proposal: `up_down_turnover_imbalance`

Follow the money via up-bar vs down-bar turnover.

Turnover on up-closes versus down-closes is a participation split the close-only oscillators never see. A rolling imbalance of unused quote volume is not an OBV ledger and not a per-bar VWAP pulse.

## Coding brief (implement this after Inbox approve)

- Clock: `4h/4h`
- Side: `BOTH`
- Why this is novel: Needs up-bar vs down-bar turnover (close>prior close vs close<prior close). imb=(sum_N up_to - sum_N down_to)/(sum_N up_to + sum_N down_to). LONG imb>k, SHORT imb<-k. Follow-the-money, not a fade. Not a close-only oscillator. Not OBV/VPT/Force/bar_vwap_inflow_surge/ADL/CMF. Do not cumsum. Do not invent taker/CVD/netflow/on-chain/funding columns.

## What to write

1. `core/strategy/up_down_turnover_imbalance.py` — `Strategy` subclass, `name = "up_down_turnover_imbalance"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one long and one short. Assert tests read turnover. Same price path, flipped turnover allocation, must flip the side (not a close-only oscillator).
4. Do not copy a rejected family and rename it.
5. After `list_strategies()` contains this name, call `firm.cursor_coding.mark_done("up_down_turnover_imbalance")`.
