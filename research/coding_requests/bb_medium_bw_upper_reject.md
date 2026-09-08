# Proposal: `bb_medium_bw_upper_reject`

Bollinger Band medium-bandwidth reject / fade. SHORT: price tags/touches the upper band then closes back below the upper band (reject). LONG: price tags/touches the lower band then closes back above the lower band (reject). Only fires when bandwidth is in the medium window (not squeeze, not blowoff expansion). Clock: `4h/4h`. Side: BOTH.

## Coding brief (Brian Inbox-approved for coding)

- Clock: `4h/4h`
- Side: `BOTH`
- Status: Brian Inbox-approved for coding (do not start walk-forward)
- Quant lock: BB period = 20 LOCKED / not searched; medium bandwidth window `[0.04, 0.10]` LOCKED (BW = `(upper-lower)/mid`, the repo `bollinger_width` helper); SHORT = upper reject, LONG = lower reject LOCKED. Free search (1 only): `k` (BB stdev multiplier) `[1.8, 2.0]`.
- Why this is novel: Bollinger medium-bandwidth band reject / fade as one 4h BOTH family. Same-bar tag-then-close-back inside the envelope, only when BW is in the locked medium window. Not a squeeze breakout, not NR7, not an ATR expansion-fail / blowoff fade. Quant-locked: BB20, medium BW [0.04, 0.10], SHORT=upper / LONG=lower. Free search (1 only): k [1.8, 2.0]. Not squeeze_momentum_break / bb_squeeze_breakout leftover. Not expansion_fail_fade (131 — single ATR expansion bar then next-bar fail). Not nr7_fail_reversion. Not bollinger_mean_reversion (close-through stretch, no medium-BW reject). Not displacement / H&S / cup / diamond / pennant / wedge. Do not recode spent families 118–135.

## What to write

1. `core/strategy/bb_medium_bw_upper_reject.py` — `Strategy` subclass, `name = "bb_medium_bw_upper_reject"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), SHORT upper-reject, LONG lower-reject, kit lock asserts search only `k` `[1.8, 2.0]`, BB20 locked, medium BW `[0.04, 0.10]` locked, distinction vs squeeze / NR7 / expansion blowoff.
4. Do not copy a rejected family and rename it. Do not recode 118–135. Do not clone `squeeze_momentum_break`, `bb_squeeze_breakout`, `nr7_fail_reversion`, or `expansion_fail_fade`.
5. Do not call `firm.cursor_coding.mark_done` (that starts walk-forward). Coding only.
