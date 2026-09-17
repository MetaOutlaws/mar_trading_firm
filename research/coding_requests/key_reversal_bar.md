# Proposal: `key_reversal_bar`

Classic key reversal bar — break of the prior bar's extreme, then the same bar closes reverse vs the prior close **and** vs open. SHORT: `high > prior_high` AND sized break AND `close < prior_close` AND `close < open`. LONG: `low < prior_low` AND sized break AND `close > prior_close` AND `close > open`. Clock: `4h/4h`. Side: BOTH with SHORT priority. Family id: `key_reversal_bar` only.

## Coding brief (Munha AUTHORITATIVE stamp — Brian YES geometry lock)

- Clock: `4h/4h`
- Side: `BOTH` with SHORT priority
- Status: Munha AUTHORITATIVE stamp for coding (do not start walk-forward). Brian YES live. Live trading stays off. Register for ONE walk-forward after merge (Job ~152). Desk walks that one after merge.
- Quant lock (implement exactly): ATR period = 20 LOCKED / not searched; ATR known before the signal bar (`atr.shift(1)`). Reverse body LOCKED. SHORT = `high[t] > high[t-1]` AND `(high[t] - high[t-1]) >= min_break_atr * ATR20` AND `close[t] < close[t-1]` AND `close[t] < open[t]`. LONG = `low[t] < low[t-1]` AND `(low[t-1] - low[t]) >= min_break_atr * ATR20` AND `close[t] > close[t-1]` AND `close[t] > open[t]`. Free search (1 only): `min_break_atr` `[0.2, 0.5]` (endpoints only — do not invent interiors). Fill at `t+1` open. Family id `key_reversal_bar` only. Do not rename free params. Do not clone `inside_bar_break_fail`. Do not recode `outside_bar_*`. Do not implement `bullish_rectangle_fail_reclaim` (Job 133 DEAD).
- Why this is novel: Classic key reversal bar as one 4h BOTH family with SHORT priority. The extreme is the prior bar's high/low. The fail is a same-bar close reverse vs prior close **and** vs open after a sized break.

## What to write

1. `core/strategy/key_reversal_bar.py` — `Strategy` subclass, `name = "key_reversal_bar"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead, LONG, SHORT, kit lock search only `min_break_atr` `[0.2, 0.5]`, ATR20 + reverse-body locked, wrong-body does not fire, sibling-distinction on the one-sided fixture vs `inside_bar_break_fail`, `outside_bar_reversal`, `outside_bar_fail_reversion`. Size grid matters (0.2 fires, 0.5 does not). SHORT is the priority side; LONG stays honest.
4. Distinct from: `inside_bar_break_fail` (family F), `outside_bar_*`, thrust-bar fail-reversion, dead VP, Job 133 `bullish_rectangle_fail_reclaim` (DEAD 0/12 — no-recode / no-spawn). Hold H&S / asia / wyckoff alone. No Jobs 148–151 respawn.
5. Do not call `firm.cursor_coding.mark_done`. Coding only. Do not edit `config/approved_strategies.json`. Do not loosen research gates / touch `PIPELINE_AUTO_ADVANCE`. Do not touch Floor UI.
