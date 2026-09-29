# Proposal: `broadening_formation_break`

UNAPPROVED — Option B exploratory. SCORE/RETIRE only. Not Inbox.
Brian CODE NOW, in parallel with head-and-shoulders. This file does not code H&S.
Garwe stamp: free `lookback` {32, 48} and `min_touches` {3, 4}; expanding rails (upper slope > 0, lower slope < 0); ATR(20) touch tolerance only; pivot 3/3 for swing detection; fill t+1; not `converging_wedge_break`.

## One-liner
4h BOTH: break an expanding megaphone (higher highs + lower lows). LONG close above the upper rail; SHORT close below the lower rail.

## Geometry
- Lookback window; at least `min_touches` swing highs on a rising upper rail; at least `min_touches` swing lows on a falling lower rail
- Rails must be expanding (upper slope > 0, lower slope < 0) and still open (upper above lower)
- LONG: `close_t > upper_rail_t`. SHORT: `close_t < lower_rail_t`. A wick without the close does not fire
- Fill t+1 open
- ATR(20), known before the signal bar, is the touch tolerance only (1.0 × ATR). It is not a break-size filter and it is not searched
- Free: `lookback` in `{32, 48}`, `min_touches` in `{3, 4}` (endpoints only)
- Locked: expanding rails; break on the close; pivot 3/3 (three bars left and three bars right; a 2/2 fractal is not a swing); no volume gate; no session gate; no volume profile

## Do-not-recode
`converging_wedge_break` (Job 125 — rails converge). `ascending_triangle_break` (flat cap). `failed_range_break_reversion`. `double_top_neckline_break`. `round_number_fade` / `consecutive_bar_exhaustion` / `mass_index_reversal`. Do not code head-and-shoulders in this change.

## Option B
SCORE/RETIRE only. No `approved=true`. Live stays off. Do not call `mark_done`. Do not start walk-forward from this coding PR. Do not edit `config/approved_strategies.json`.
