# Proposal: `candle_reject_reversal`

Classic hammer / hanging-man reject candle as one family. LONG is a hammer (long lower wick, stub upper, non-doji body, close in the upper half). SHORT is a hanging-man (same geometry). Clock: `4h/4h`. Side: BOTH. No run_bars and no doji-star confirm. Not generic wick rejection.

## Coding brief (Brian Inbox-approved for coding)

- Clock: `4h/4h`
- Side: `BOTH`
- Status: Brian Inbox-approved for coding (do not start walk-forward)
- Quant lock: `max_upper_wick_frac = 0.15` LOCKED / not searched; `min_body_frac = 0.15` LOCKED / not searched (not a doji); close in upper half of bar LOCKED; no `run_bars`; no doji-star confirm. Free search (2 only): `min_lower_wick_frac` `[0.55, 0.65]`, `max_body_frac` `[0.20, 0.35]`.
- Why this is novel: Classic hammer/hanging reject candle as a single family. LONG = hammer shape (long lower wick, stub upper, non-doji body, close in upper half). SHORT = hanging-man shape (same geometry). Geometry: lower_wick_frac=(min(open,close)-low)/(high-low), upper_wick_frac=(high-max(open,close))/(high-low), body_frac=|close-open|/(high-low). Quant-locked: max_upper_wick_frac=0.15 (not searched), min_body_frac=0.15 (not a doji; doji_star uses max_body ~0.10), close in upper half locked, no run_bars / no doji-star confirm. Free search (2 only): min_lower_wick_frac [0.55, 0.65], max_body_frac [0.20, 0.35]. Not wick_rejection_reversal (generic long wick; no stub-upper / non-doji / close-upper-half kit). Not doji_star_reversal (doji body + run + confirm). Do not recode spent families 118–131. Displacement parked. Rectangle / three_black_crows buffer only.

## What to write

1. `core/strategy/candle_reject_reversal.py` — `Strategy` subclass, `name = "candle_reject_reversal"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one LONG hammer and one SHORT hanging-man, kit lock asserts `max_upper_wick_frac` / `min_body_frac` / close-upper-half locked and `min_lower_wick_frac` `[0.55, 0.65]` plus `max_body_frac` `[0.20, 0.35]` searched.
4. Do not copy a rejected family and rename it. Do not recode 118–131. Do not code `displacement_gap_follow` (PARKED). Do not code rectangle / three_black_crows. Do not recode `doji_star_reversal` or `wick_rejection_reversal`.
5. Do not call `firm.cursor_coding.mark_done` (that starts walk-forward). Coding only.
