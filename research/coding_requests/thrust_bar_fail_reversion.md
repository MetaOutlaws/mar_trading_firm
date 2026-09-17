# Proposal: `thrust_bar_fail_reversion`

Thrust-bar fail reversion — a directional thrust bar (t-1) sized vs ATR, then the next bar fails and reverts through the thrust mid. SHORT (priority) when an UP thrust fails (close back below mid, still strictly inside the thrust H/L); LONG when a DOWN thrust fails (close back above mid). Clock: `4h/4h`. Side: BOTH with SHORT priority. Family id: `thrust_bar_fail_reversion` only. This is a FADE / failed-thrust edge — not a squeeze-then-volume follow, not a same-bar open flush, not an ATR true-range expansion-fail.

## Coding brief (Garwe/Munha stamp — Brian YES already live)

- Clock: `4h/4h`
- Side: `BOTH` (SHORT priority: implement BOTH; walk registration is BOTH, not a SHORT-only clone)
- Status: Garwe/Munha stamp for coding (do not start walk-forward). Brian YES already live. Live trading stays off.
- Quant lock: ATR period = 20 LOCKED / not searched; ATR known before the signal bar (`atr.shift(1)`). Thrust = bar t-1 LOCKED (H-L range, not true range; directional: close vs open AND close vs mid). `require_close_inside_thrust=True` LOCKED (`thrust_low < close[t] < thrust_high`). Fail close must cross back through the thrust mid. SHORT = UP thrust AND `close[t] < mid`. LONG = DOWN thrust AND `close[t] > mid`. Free search (1 only): `min_thrust_atr` `[1.0, 1.5]` (endpoints only — same sibling float-grid convention as `outside_bar_fail_reversion.min_outside_atr` / `inside_bar_break_fail.min_mother_atr`; do not invent interiors). Size: `(high[t-1] - low[t-1]) >= min_thrust_atr * ATR20`. Fill at `t+1` open. Family id `thrust_bar_fail_reversion` only. Do not rename free params. Do not clone `expansion_fail_fade`. Do not recode `lvn_fill_reject` or `inside_bar_break_fail`.
- Why this is novel: Thrust-bar fail reversion as one 4h BOTH family (SHORT priority). The thrust is a directional H-L bar at t-1 sized vs ATR20, not a true-range expansion with a weak-vol gate, not a squeeze-then-volume follow, and not a same-bar open flush. The fail is the next bar closing strictly inside and through the thrust mid.

## What to write

1. `core/strategy/thrust_bar_fail_reversion.py` — `Strategy` subclass, `name = "thrust_bar_fail_reversion"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), LONG down-thrust fail, SHORT up-thrust fail (priority edge), kit lock asserts search only `min_thrust_atr` `[1.0, 1.5]`, ATR20 + require_close_inside_thrust locked, sibling-distinction vs `expansion_fail_fade`, `range_compression_volume_thrust`, `atr_open_flush_fade`, `utc_day_open_flush_fade`, `outside_bar_fail_reversion`, `outside_bar_reversal`, `engulfing_fail_reversion`, `failed_range_break_reversion`, `failed_break_reclaim`, `ib_fail_reversion`, `inside_bar_break_fail`, `nr7_fail_reversion`, `candle_reject_reversal`, `body_efficiency_follow`, and `lvn_fill_reject`. Size grid matters (1.0 fires, 1.5 does not on a medium thrust).
4. Distinct from: `expansion_fail_fade` (131 — do not clone), `range_compression_volume_thrust` (102), `atr_open_flush_fade` (138), `outside_bar_fail_reversion`, `engulfing_fail_reversion` (126). Do not recode family E `lvn_fill_reject` or family F `inside_bar_break_fail`.
5. Do not call `firm.cursor_coding.mark_done` (that starts walk-forward). Coding only. Do not edit `config/approved_strategies.json`. Do not loosen research gates / touch `PIPELINE_AUTO_ADVANCE`. Do not empty or revert the `PAPER_SCAN_SLEEVES` blotter fix.
