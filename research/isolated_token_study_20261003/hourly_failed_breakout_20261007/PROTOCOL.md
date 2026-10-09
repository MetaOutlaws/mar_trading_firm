# Hourly compression: fixed failed-breakout exit

Frozen before scoring, 7 October 2026. Follow-up to the completed price-break-even
protection experiment, which reduced returns. The owner authorized this next
isolated test. The approved paper pilot keeps its existing exits.

## Hypothesis and one fixed treatment

A breakout that closes back through the range boundary may have failed before
it reaches the original 2% stop. Exiting on that evidence may reduce losses by
more than it sacrifices in trades that would recover to the 2.5% target.

Retain the exact hourly entries, initial 2% stop, 2.5% target and no timeout.
At entry, fix the breakout boundary to the signal's high20 for LONG or low20
for SHORT: the high/low of the 20 completed hourly candles preceding the signal
candle. Exclude the breakout signal candle itself. Never move this boundary.

Review every full UTC hourly candle completed AFTER entry. Earliest review is
the first hour after the entry open, not the signal candle. For LONG, a close
at or below the fixed boundary triggers failure; for SHORT, a close at or above
it triggers failure. Execute at the following minute's open. No waiting for
two closes, buffer, volume filter, profit condition, partial exit or re-entry.
One treatment only; no lookback/threshold/timeframe sweep or token-specific rule.

Standing SL/TP orders take priority before a review close. If either has
already executed in that minute, its later close cannot schedule another exit.
At the scheduled exit open, an opening stop/target breach has priority; otherwise
exit at the open before that minute's later extrema. Preserve the baseline
stop-first convention for intrabar SL/TP ties. Stops fill at the worse of stop
and open, targets at the target quote. Apply the unchanged cost model. Scheduled
open exits use funding known through the open; intrabar exits keep the original
conservative funding convention. A last-partition-hour failure with no following
minute is not executable; preserve the terminal mark convention.

## Data and invariants

Use the same 143 membership-eligible hourly opportunities from the stop-width
study: BTC, ETH, SOL; both directions; 2022–24 and flat-reset reused 2025.
Verify six original price/funding files, nine frozen feature files, and all
reference results. Independently reconstruct every entry boundary directly from
the prior 1,200 one-minute bars ending before the signal candle begins.

Fees remain 0.055% per side. Base slippage is 0.05% per side BTC/ETH and 0.10%
SOL; stress doubles slippage. Funding, initial quote-based barriers, signal IDs,
membership, ranking, one-position-per-token and basket/direction limits remain
fixed. Recompute admissions independently for each exit arm. No 2026 outcome,
new-token result, real-money change or leverage simulation.

## Comparisons

Report chronological trades, actual 2% stop exits, failed-breakout exits, target
hits, terminal marks, net win rate, mean net return, mean/sum initial-risk R,
holding time, token/direction/year results and 1/4-week calendar-block intervals.
R is net return divided by the unchanged INITIAL 2% risk. Return sums are
additive units, not compounded account returns.

Pair all raw opportunities and separately the baseline-admitted set. Count
original stops intercepted, whether they actually improve net return, original
target winners cut short, their cost, and changed funding. Report matched
uncertainty. Separately decompose chronological change into retained-pair
effects, newly admitted trades and dropped baseline trades. An early exit can
admit a later losing trade or block another later entry; include the full replay.
Report each affected trade with its fixed boundary and trigger/exit times.

## Decision and verification

The exploratory improvement screen is unchanged from the previous exit test:
positive stressed chronological mean in both periods AND positive stressed
differences versus baseline in both mean net return and total additive net R
in both periods. All confidence intervals remain descriptive; 2025 has already
been reused and is not an independent holdout. No automatic deployment.

Require exact baseline raw/admitted reconciliation, independent scalar checks
of every arm path, hand-worked long/short timing/gap/order-priority cases,
causality and fixed-boundary checks, independent admissions, cost identities,
effect decomposition and complete frozen input/source/output hashes. Save all
attempts and a restorable checkpoint. If the rule fails, keep the baseline and
report the failure without searching additional settings in this run.
