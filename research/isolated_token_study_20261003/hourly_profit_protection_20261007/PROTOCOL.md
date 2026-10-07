# Hourly compression: one-step price break-even protection

Frozen before scoring on 7 October 2026. This is the next isolated research
comparison after the stop-width study. The owner-approved hourly paper pilot
has been verified scanning separately; this study does not change its exits.

## Hypothesis and fixed rule

Some breakouts travel one initial risk unit in our favor, then reverse into
the original stop. Moving the stop to the entry quote after that progress may
save more on those reversals than it loses by cutting eventual target winners.

Primary treatment: initial stop 2%, target 2.5%, no holding timeout. After a
completed one-minute candle CLOSE has moved at least +2% (+1R) from the entry
quote in the trade direction, move the stop once to that entry quote. The new
stop becomes active on the NEXT minute. Keep it there; no further trailing,
partial exit, re-entry, indicator, target or entry change. Comparator is the
unchanged 2%/2.5% baseline. One treatment only; no trigger/lock sweep.

The entry quote is the original next-minute open used for historical brackets,
not the slipped fill. Thus this is PRICE break-even, not guaranteed net break-even.
Slippage, both fees, funding and gaps are still charged. The trigger uses the
same quote anchor in both cost scenarios, so stress changes costs, not paths.

Orders already active in a minute take priority over its close. A minute that
hits the original stop or target cannot arm protection later at its close.
Same-minute stop/target ambiguity retains the baseline stop-first convention.
For a protective stop, use the worse of its stop quote and opening quote;
targets fill at the target quote, exactly as in the reference simulator.
At the partition boundary mark to the last available close as before.

## Data and controls

Use the identical 143 membership-eligible hourly compression raw opportunities
and input/feature hashes from hourly_stop_width_20261007. BTC, ETH, SOL, both
directions, pooled 2022-24 and a flat-reset 2025 partition. No 2026 outcomes.
Unchanged fees (0.055% per side), settled funding, base slippage (0.05% per side
BTC/ETH, 0.10% SOL), and doubled-slippage stress. Shared token occupancy and
original basket/direction capacities remain fixed and replayed for each arm.
No change to historical entry eligibility, rank, signal identities or parameters.

## Reports and accounting

Report chronological trades, original stop exits, protective stop exits, total
stop-order exits, targets, boundary marks, net wins, mean net return, mean/sum R,
holding time, calendar-year/token/side groups and 1/4-week block intervals.
R stays net return divided by the ORIGINAL 2% stop in both arms.
Return sums are additive units, not compounded account performance.

Pair every raw opportunity with its baseline. Separately report those pairs
restricted to the baseline-admitted set: original stops intercepted, original
target winners cut short, remaining stops/targets and paired return changes.
These counterfactuals can overlap; they are not the chronological portfolio.
Decompose matched net changes by original outcome, including any funding-only
changes. Reconcile matched changes with retained, newly admitted and dropped
chronological trades so freed capacity is not silently credited as exit skill.

Path diagnostics are descriptive only: favorable/adverse extrema and favorable
closes BEFORE the baseline exit minute, plus first close at +1%, +1.5%, +2%.
Exclude exit-minute extrema because their pre-exit ordering is unknown.
Report stop and target groups together, and token/year concentration. These
diagnostic thresholds cannot be used to pick a replacement rule in this run.

## Decision and validation

Exploratory continuation requires positive stressed chronological mean in both
partitions and improved stressed mean net return AND total additive net R
versus baseline in both partitions. Report paired and chronological uncertainty,
including 1/4-week calendar-block intervals, even if point criteria pass.
2025 has already been reused and is not an independent holdout. No automatic
paper/live deployment, token-specific fitting, leverage or profitability claim.

Require exact baseline raw and admitted-ledger reconciliation, an independent
scalar state-machine check of every raw path, hand-worked long/short timing,
gap and ambiguity fixtures, independent admissions, complete cost identities,
and saved protocol/source/input/output hashes. Preserve attempts on failure.
If it fails, retain the approved baseline; report what the paths teach before
proposing another separately frozen hypothesis. Additional-token and forward
confirmation remain separate pending work.
