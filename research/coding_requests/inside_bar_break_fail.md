# Proposal: `inside_bar_break_fail`

Inside-bar break-fail — wick through one rail of the inside-bar mother, then the same bar closes strictly back inside the mother. SHORT when the high breaks the mother high and the close fails back inside; LONG when the low breaks the mother low and the close fails back inside. Clock: `4h/4h`. Side: BOTH. Family id: `inside_bar_break_fail` only. This is a FADE / failed-IB-break edge — not a London IB later-bar fail, not an IB breakout follow.

## Coding brief (Munhamutapa CHAIR stamp — Brian YES already live)

- Clock: `4h/4h`
- Side: `BOTH`
- Status: Munhamutapa CHAIR stamp for coding (do not start walk-forward). Brian YES already live. Live trading stays off.
- Quant lock: ATR period = 20 LOCKED / not searched; ATR known before the signal bar (`atr.shift(1)`). Mother = inside-bar mother context LOCKED (`inside_bar_mother`: bar t-1 strictly inside bar t-2; any bar, not a London 07:00–11:00 session lock). `require_close_inside_mother=True` LOCKED (`mother_low < close[t] < mother_high`). SHORT = `high[t] > mother_high` AND close strictly inside mother (and not also through the low). LONG = `low[t] < mother_low` AND close strictly inside mother (and not also through the high). Free search (1 only): `min_mother_atr` `[0.8, 1.2]` (endpoints only — same sibling float-grid convention as `outside_bar_fail_reversion.min_outside_atr`; do not invent interiors). Size: `(mother_high - mother_low) >= min_mother_atr * ATR20`. Fill at `t+1` open. Family id `inside_bar_break_fail` only. Do not rename free params. Do not clone `ib_fail_reversion`. Do not recode `lvn_fill_reject`.
- Why this is novel: Inside-bar break-fail as one 4h BOTH family. The mother is the classic two-bar inside-bar box, not a London first-4h-open-in-07:00–11:00 lock. The fail is a same-bar wick-through that closes back inside, not a close-through then a later bar, and not a successful IB follow.

## What to write

1. `core/strategy/inside_bar_break_fail.py` — `Strategy` subclass, `name = "inside_bar_break_fail"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), LONG downside-wick fail, SHORT upside-wick fail, kit lock asserts search only `min_mother_atr` `[0.8, 1.2]`, ATR20 + require_close_inside_mother locked, sibling-distinction vs `ib_fail_reversion`, `inside_bar_breakout`, `nr7_fail_reversion`, `outside_bar_fail_reversion`, `failed_range_break_reversion`, `failed_break_reclaim`, `engulfing_fail_reversion`, `expansion_fail_fade`, `candle_reject_reversal`, and `lvn_fill_reject`. Size grid matters (0.8 fires, 1.2 does not on a medium mother).
4. Distinct from: `ib_fail_reversion` (124 — do not clone), `inside_bar_breakout`, `nr7_fail_reversion` (123), `outside_bar_fail_reversion`, `failed_range_break_reversion` (119), `failed_break_reclaim` (130), `engulfing_fail_reversion` (126). Do not recode family E `lvn_fill_reject`.
5. Do not call `firm.cursor_coding.mark_done` (that starts walk-forward). Coding only. Do not edit `config/approved_strategies.json`. Do not loosen research gates / touch `PIPELINE_AUTO_ADVANCE`. Do not empty or revert the `PAPER_SCAN_SLEEVES` blotter fix.
