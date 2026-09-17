# Proposal: `thrust_bar_fail_reversion`

Thrust-bar fail reversion — a sized close-through of the immediate prior bar, then the next bar fails and closes back inside that prior range. SHORT (priority) when an upside thrust-break fails (close back below prior high, still inside prior); LONG when a downside thrust-break fails (close back above prior low). Clock: `4h/4h`. Side: BOTH with SHORT priority. Family id: `thrust_bar_fail_reversion` only. This is a FADE / failed-thrust-break edge — sibling fail-reversion geometry, not a rolling Donchian, not an NR7 / London-IB / ORB box, not a close-inside of the thrust bar vs mid.

## Coding brief (Munha stamp — Brian YES already live)

- Clock: `4h/4h`
- Side: `BOTH` (SHORT priority: implement BOTH; walk registration is BOTH, not a SHORT-only clone)
- Status: Munha stamp for coding (do not start walk-forward). Brian YES already live. Live trading stays off.
- Quant lock: ATR period = 20 LOCKED / not searched; ATR known before the signal bar (`atr.shift(1)`). Prior = immediate previous bar (t-2) LOCKED (not a rolling N-bar Donchian). Thrust/break = bar t-1 LOCKED: close-through of prior (not a wick) AND `(high[t-1]-low[t-1]) >= min_thrust_atr * ATR20`. Fail = next bar only (`max_bars_since_break` not searched). `require_close_inside=True` LOCKED (close back inside the *prior* range). SHORT = `close[t-1] > prior_high` AND `prior_low < close[t] < prior_high`. LONG = `close[t-1] < prior_low` AND `prior_low < close[t] < prior_high`. Free search (1 only): `min_thrust_atr` `[1.0, 1.5]` (endpoints only — same sibling float-grid convention as `outside_bar_fail_reversion.min_outside_atr` / `inside_bar_break_fail.min_mother_atr`; do not invent interiors). Fill at `t+1` open. Family id `thrust_bar_fail_reversion` only. Do not rename free params. Do not clone `failed_range_break_reversion`. Do not recode `lvn_fill_reject` or `inside_bar_break_fail`.
- Why this is novel: Thrust-bar fail reversion as one 4h BOTH family (SHORT priority). The break is a sized close-through of the *immediate prior bar*, not a rolling Donchian, not NR7 / London IB / ORB, and not a same-bar wick. The fail is the next close back inside that prior range — not a close-inside of the thrust bar vs mid.

## What to write

1. `core/strategy/thrust_bar_fail_reversion.py` — `Strategy` subclass, `name = "thrust_bar_fail_reversion"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), LONG downside thrust-break fail, SHORT upside thrust-break fail (priority edge), kit lock asserts search only `min_thrust_atr` `[1.0, 1.5]`, ATR20 + require_close_inside locked, next-bar only, sibling-distinction vs `failed_range_break_reversion`, `nr7_fail_reversion`, `ib_fail_reversion`, `orb_fail_reversion`, `outside_bar_fail_reversion`, `inside_bar_break_fail`, `expansion_fail_fade`, `range_compression_volume_thrust`, `atr_open_flush_fade`, `engulfing_fail_reversion`, `failed_break_reclaim`, and `lvn_fill_reject`. Size grid matters (1.0 fires, 1.5 does not on a medium thrust). Wick-only break does not fire. Held close-through does not fire.
4. Distinct from: `failed_range_break_reversion` (119 — do not clone), `nr7_fail_reversion` (123), `ib_fail_reversion` (124), `orb_fail_reversion`, `outside_bar_fail_reversion`, `inside_bar_break_fail` (family F). Do not recode family E `lvn_fill_reject`.
5. Do not call `firm.cursor_coding.mark_done` (that starts walk-forward). Coding only. Do not edit `config/approved_strategies.json`. Do not loosen research gates / touch `PIPELINE_AUTO_ADVANCE`. Do not empty or revert the `PAPER_SCAN_SLEEVES` blotter fix.
