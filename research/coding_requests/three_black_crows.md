# Proposal: `three_black_crows`

Classic three black crows — three consecutive bearish candles with descending closes; each opens within the prior candle's range; substantial bodies; limited upper wicks. SHORT entry after the third crow confirms. Clock: `4h/4h`. Side: SHORT (SHORT-bias — not BOTH).

## Coding brief (Brian Inbox-approved for coding)

- Clock: `4h/4h`
- Side: `SHORT`
- Status: Brian Inbox-approved for coding (do not start walk-forward)
- Quant lock: exactly 3 consecutive bearish descending closes LOCKED / not searched (`close[t] < close[t-1] < close[t-2]`, each bearish); each crow opens in the prior candle's range (open inside prior high-low) LOCKED; SHORT side only LOCKED. Free search (2 only): `min_body_frac` `[0.40, 0.50]`, `max_upper_wick_frac` `[0.15, 0.25]`.
- Why this is novel: Classic three black crows as a SHORT-only family. Three consecutive bearish candles with descending closes; each opens within the prior candle's high-low; substantial bodies; limited upper wicks. SHORT entry after the third crow confirms. Quant-locked: n_crows=3 (not searched), open-in-prior-range locked, SHORT only (not BOTH / not three white soldiers). Free search (2 only): min_body_frac [0.40, 0.50], max_upper_wick_frac [0.15, 0.25]. Not three_bar_play (trend + narrow rest + break of rest leftover). Not engulfing_fail_reversion (job 126 — two-bar body engulf then fail through engulf open). Not candle_reject / consecutive_bar_exhaustion / open_in_prior_range_fail / rectangle. Do not recode spent families 118–133. Do not code three white soldiers / BOTH.

## What to write

1. `core/strategy/three_black_crows.py` — `Strategy` subclass, `name = "three_black_crows"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), SHORT three-crow entry, kit lock asserts search only `min_body_frac` `[0.40, 0.50]` plus `max_upper_wick_frac` `[0.15, 0.25]`, `n_crows` locked at 3, open-in-prior-range locked, descending-closes lock, distinction vs `three_bar_play` and `engulfing_fail_reversion`.
4. Do not copy a rejected family and rename it. Do not recode 118–133. Do not code LONG three white soldiers / BOTH. Do not clone `three_bar_play` leftover or `engulfing_fail_reversion`.
5. Do not call `firm.cursor_coding.mark_done` (that starts walk-forward). Coding only.
