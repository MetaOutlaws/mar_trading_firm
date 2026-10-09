# Hourly compression: isolated stop-width diagnostic

Frozen before scoring on 7 October 2026. Brian has separately approved the
existing hourly SL2%/TP2.5% baseline for BTC/ETH/SOL paper use, both directions.
That owner decision does not change prior findings or research qualification.

## Hypothesis and scope

Wider initial stops may recover compression breakouts that first retrace, but
the extra recoveries must offset larger losses, funding and foregone entries.
Test SL1%, 2%, 3%, 4%, 5%, with TP fixed at 2.5%. SL2% is the reference.
No entry thresholds, token filters, direction filters, target, trailing stop,
breakeven move, regime exit, sizing logic or holding limit are optimized.

Use exactly the frozen, membership-eligible raw `compression_hourly` signals
from family_followups_20261007. Re-score every raw hourly opportunity, then
independently replay token occupancy for each stop. A 2022–24 partition and a
flat-reset 2025 partition are retained. No 2026 price outcome is scored.
Same six original price/funding files and nine frozen feature hashes; same
quote-based brackets, minute stop-first convention, opening gaps, fees,
settled funding, base slippage and doubled-slippage stress as the baseline.

## Comparisons

1. Chronological strategy: trades, stops/count/rate, targets, marks, win rate,
   mean net return, mean and sum net R, holding time, annual/token/side tables,
   calendar-week 1/4-week block intervals. R uses each arm's initial stop and
   is not dollar account P&L. Return sums are not compounded portfolio returns.
2. Matched raw opportunities: pair every stop with SL2% on token, side,
   partition and entry minute; count baseline stops recovered to targets,
   targets lost to stops, remaining stops, marks and paired net difference.
   Also report that pairing restricted to baseline-admitted trades. These
   counterfactuals overlap and are not an executable portfolio.
3. Admission differences: retained, newly admitted and dropped signals and
   their outcomes; wider stops occupy positions longer and can block signals.

Exploratory continuation screen only: positive stressed chronological mean in
both partitions, and positive stressed differences versus SL2% in BOTH mean
net return and mean net R in both partitions. Count all four alternatives;
do not pick different stops per token/timeframe from sparse cells. Report
uncertainty even if point screen passes. No automatic change to the approved
2% baseline. Reused 2025 is not an independent holdout.

## Verification and next decision

Require exact SL2% baseline ledger reconciliation, independently checked minute
barriers, independent admissions, unchanged signal IDs and cost accounting.
Save all rows, attempts, protocol/source/input hashes and verification.
If no stop passes, retain 2% and move next to a separately frozen, narrow
profit-protection hypothesis; no new entry family sweep merely to find a winner.
Fresh additional-token/forward confirmation remains a separate pending stage.
