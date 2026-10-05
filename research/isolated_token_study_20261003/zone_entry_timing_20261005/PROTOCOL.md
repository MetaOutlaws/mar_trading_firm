# Zone-aware entry timing: single fixed policy and delay control

5 October 2026. Frozen before outcomes. User authorizes zone-aware ENTRY timing next, with zone-aware EXIT timing reserved for later. No parameter sweep. The daily filter is omitted because the preceding test did not establish benefit.

## Common system and budget

Original completed4h EMA50/200 regime plus EMA20 reclaim at 5m/15m/1h, BTC/ETH/SOL, long and short separately: 18 cells. No additional4h pivot-structure filter, daily filter or range-position permission. Same fixed1% stop and2.5% target measured from actual quote entry, original4h EMA-regime exit, fees, slippage and historical funding. No holding cap. Stops/targets are installed only after entry. Same conservative minute-bar order and gap conventions. No passive/limit fills or assumed maker fees.

Three policies in every cell:
- A immediate: unchanged baseline.
- W fixed wait control: where a relevant support/resistance zone exists at signal, wait six entry-clock bars, then market enter if4h regime still valid. Missing-zone signals enter immediately.
- Z zone timing: where a relevant zone exists at signal, seek its rejection on one of the NEXT six completed entry-clock candles; enter at that candle's close / next minute open. If no valid rejection, enter at the six-bar deadline, provided4h regime still valid. Missing-zone signals enter immediately.

18 Z tests +18 W controls +18 baseline replications. Two reused periods(2022–2024,2025), two costs(base/doubled slippage), two views(paired opportunity/chronological single-position) =432 aggregate rows. No2026 features or returns. No exit-policy experiment. No additional settings after viewing results.

This intervention changes entry timing only as a policy; its rejection predicates and six-bar waiting convention are not claimed to have separately measured effects. W helps distinguish zone confirmation from simply delaying. Six bars is setup waiting time(30m/90m/6h by clock), NOT a trade holding cap.

## Frozen causal zone and timing definitions

Reuse the non-blocking map from incremental_context_20261005: nearest active hourly confirmed pivot support for long, resistance for short; strict two-bar confirmation, band±0.25 hourly ATR14 known at confirmation,30-day age and hourly-close invalidation. Freeze this zone at original signal time; never replace it with a subsequently favorable zone. Zone absence is not a rejection. Every original candidate is retained in the audit even if busy or canceled.

Z long rejection: subsequent entry-clock candle overlaps the frozen band and closes above its upper edge and above its open. Z short reverses geometry and closes below lower edge and its open. Trigger candles must finish after the original signal; no same-trigger-candle retrospective confirmation. Enter at the next available minute open, including any gap; do not fill at the favorable zone price. Next open need not remain beyond the band; ordinary market fill and costs apply.

A zone invalidated by a completed hourly close beyond its far edge during the wait, or older than30days, cannot supply a rejection trigger. This disables the zone trigger, NOT the opportunity: use the same six-bar fallback if regime remains valid. W uses the same zone-availability decision at original signal but ignores rejection/zone invalidation afterward.

For W/Z, original4h regime losing alignment at or before intended entry cancels the pending setup. Regime state uses the same completed lower-clock observations of4h state as the baseline; no new regime formula. Cancellation at the same timestamp has priority. A setup whose intended entry is at/beyond the partition end is censored and does not enter. Record cancellation, censoring, fallback and confirmed-entry reasons separately. No synthetic returns for unfilled orders.

## Opportunity and execution accounting

Paired view evaluates EVERY original signal independently; overlapping paths are diagnostics, not a realizable portfolio. Report filled mean return, fill fraction, and net return per ORIGINAL opportunity with zero for cancellations/censoring. Missing-zone immediate fallbacks have full ordinary trading outcomes.

Chronological view reserves the sleeve while a setup is pending, then while its position is open. Ignore subsequent signals during either state and report them as blocked_pending/blocked_position. A canceled pending setup releases capacity at its cancellation minute; permit only signals strictly afterward, matching the baseline's conservative no-same-minute reuse convention. No pyramiding. Long and short cells are separate research sleeves, not a shared portfolio.

All trade returns/costs/funding are recomputed from ACTUAL delayed entry to the unchanged exit rules. The target/stop quote levels move mechanically with actual entry; their percentages are unchanged. Each accepted record retains original signal and actual entry time, signed entry-price improvement, wait duration, frozen zone identity, timing reason and exit reason. All skipped/canceled signals remain in an audit. Zone mapping preserves candidate opportunities; entry timing need not preserve executed trade counts.

## Evaluation and limits

Report each cell separately by period and entry-year, including filled/completed/boundary counts, net/gross expectancy, PF, costs, holding time, MTM drawdown in fixed-notional additive units, waiting time, trigger/fallback/cancel/busy counts and base/stressed outcomes. Annual trade tables use actual entry-year; opportunity diagnostics use original signal-year.

Primary strategy comparison: chronological Z versus A; incremental zone-specific control: Z versus W. Also report paired net-per-original-opportunity differences, with common-signal weekly block bootstrap5000 draws, seed20261005, ordinary95% and Bonferroni36 intervals across18cells×2contrasts. These are descriptive exploratory intervals, not a correction for all historical research or long-trade dependence. Do not claim independent confirmation from reused years.

Full exploratory screen remains >=50 completed chronological trades in each period, positive base net mean and PF>=1.15 in both, plus positive means at doubled slippage in both. This is not production certification. Record all18 Z outcomes and all controls including failures; no retuning or opening2026. A reduced loss alone is not a profitable strategy.

## Verification and publication

Hash six original inputs and imported baseline/map sources; verify annotations against the preceding manifest and causal timestamps. Reconcile A counts/means against all36 prior configuration-period reference rows. Synthetic checks: mirrored long/short rejection, future independence, no same-bar confirmation, actual next-open gap entry, regime cancel priority, zone invalidation fallback, missing-zone immediate entry, pending-capacity blocking, cancellation release and partition censoring. Compare any altered scheduling/entry code with a simple scalar reference on synthetic cases where practical.

Save protocol, code, tests, every aggregate row, full opportunity audit and trade evidence locally. GitHub publication includes written protocol/findings and aggregate report tables only; detailed dataset export still awaits the specific approval requested earlier. No worker, VM, approvals or live settings changed. Exit timing remains a separate later study.
