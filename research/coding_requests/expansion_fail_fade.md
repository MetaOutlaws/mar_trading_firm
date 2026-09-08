# Proposal: `expansion_fail_fade`

Fade a failed 4h range-expansion bar when the next bar closes back inside that expansion bar's high-low on non-expanding volume.

An expansion bar is a single print whose true range exceeds `expansion_mult * ATR(20)`. Fade toward the expansion bar's midpoint: SHORT if the expansion closed on the high side (up expansion failed); LONG if the expansion closed on the low side. Clock: `4h/4h`. Side: BOTH. Weak-vol gate locked: `volume_t <= mean(volume of prior 20 bars)`. Not a successful squeeze thrust, not a rolling Donchian fail, not NR7/ORB/IB, not a multi-bar probe reclaim.

## Coding brief (Brian Inbox-approved for coding)

- Clock: `4h/4h`
- Side: `BOTH`
- Status: Brian Inbox-approved for coding (do not start walk-forward)
- Quant lock: `atr_n = 20` LOCKED / not searched; `expansion_mult` search `[1.5, 2.0]`; weak-vol gate LOCKED (`volume_t <= prior-20 mean`, not searched); max 2 free params (only `expansion_mult` is free)
- Why this is novel: Fade a failed 4h range-expansion bar when the next bar closes back inside that expansion bar's high-low on non-expanding volume. Expansion: true range > expansion_mult * ATR(20). Fail: next close inside that bar's H/L. Fade toward the expansion midpoint (SHORT if expansion was up / close near high side failed; LONG if expansion was down). Quant-locked: atr_n=20 (not searched), expansion_mult search [1.5, 2.0], weak-vol gate volume_t <= prior-20 mean (not searched), max 2 free params (only expansion_mult is free). Not range_compression_volume_thrust (102 — successful squeeze thrust). Not failed_range_break_reversion (119 — rolling N-bar close-through). Not nr7 / orb / ib fail. Not failed_break_reclaim (130 — multi-bar probe). Not displacement_gap_follow (PARKED). Do not recode spent families 118–130.

## What to write

1. `core/strategy/expansion_fail_fade.py` — `Strategy` subclass, `name = "expansion_fail_fade"`.
2. Signals may use bars `<= t` only; the engine fills at `t+1` open.
3. Tests: schema, no lookahead (truncation + future shock), at least one LONG fade and one SHORT fade, kit lock asserts `atr_n` / weak-vol locked and `expansion_mult` searched `[1.5, 2.0]`.
4. Do not copy a rejected family and rename it. Do not recode 118–130. Do not code `displacement_gap_follow` (PARKED). Do not recode `range_compression_volume_thrust`.
5. Do not call `firm.cursor_coding.mark_done` (that starts walk-forward). Coding only.
