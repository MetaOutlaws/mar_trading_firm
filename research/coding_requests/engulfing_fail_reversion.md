# Proposal: `engulfing_fail_reversion`

Fade a failed engulfing continuation: after a bullish/bearish engulfing bar, price breaks the engulf extreme then fails to hold and reverts back inside the engulf range.

SHORT when a bullish engulf is followed by a trade through that engulf high, then `close_t` is back below that high (within `max_bars_since_engulf`), still inside the engulf box. LONG when a bearish engulf is followed by a trade through that engulf low, then `close_t` is back above it. The box is the engulfing bar's high/low (not the body, not a rolling N-bar). Clock starts at the engulf, not at the break. Quant-locked: `require_close_inside=True`, `max_bars_since_engulf` search `[1, 2]`. No volume gate. Failed continuation of a two-bar body engulf, then a later (or same-bar wick) fail — not a held breakout, and not a trade on the engulf bar itself.

## Coding brief (Brian Inbox-approved for coding)

- Clock: `4h/4h`
- Side: `BOTH`
- Status: Brian Inbox-approved for coding (do not start walk-forward)
- Quant lock: `require_close_inside=True` (fixed); `max_bars_since_engulf` search `[1, 2]`; no volume gate
- Why this is novel: Fade a failed engulfing continuation: after a bullish/bearish engulfing bar, price breaks the engulf extreme then fails to hold and reverts back inside the engulf range. SHORT: after a bullish engulf, break above the engulf high then close back below within max_bars_since_engulf. LONG: after a bearish engulf, break below the engulf low then close back above. Quant-locked: require_close_inside=True, max_bars_since_engulf [1, 2], no volume. Not book engulfing_reversal (fires on the engulf bar). Not failed_range_break_reversion (119 — rolling N-bar). Not orb_fail_reversion (121 — UTC day ORB). Not nr7 / ib_fail / asia_range / prior_day / converging_wedge (125 spent n-starve). Not H&S / asia_close / wyckoff.

## What to write

1. `core/strategy/engulfing_fail_reversion.py` — `Strategy` subclass, `name = "engulfing_fail_reversion"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one LONG and one SHORT entry, held breakout does not fire.
4. Do not copy a rejected family and rename it.
5. Do not call `firm.cursor_coding.mark_done` (that starts walk-forward). Coding only.
