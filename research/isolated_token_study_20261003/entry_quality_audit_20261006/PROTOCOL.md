# Entry-quality audit: frozen design, pending source recovery

6 October 2026. Authorized by Brian: “ok proceed with the plan”.

Status: design and input-readiness audit only. No matched-control returns have
been calculated. No entry, exit, cloud configuration or trading approval changes.

## Question and source boundary

Do the latest standalone zone-rejection entries predict favourable movement
beyond that available at comparable times in the same market conditions?
This is distinct from the earlier EMA-reclaim signal followed by optional zone
timing/deadline fallback. Do not substitute that earlier entry family.

The latest user-supplied screenshot reports 38,469 zone-entry records and two
2025 SL/TP comparisons: 2%/2.5% and 3%/3%. It is evidence of the previous report,
not a replacement for the executable entry definition or individual records.
Recover the latest runner, protocol and ledger, verify their identities, and
reconcile counts, exit reasons and net returns before scoring new outcomes.
If reconstruction is necessary, record an explicit source amendment before
scoring; never call a reconstructed variant an exact replication without proof.

## Fixed scope

- BTCUSDT, ETHUSDT, SOLUSDT; long and short separately; 5m, 15m, 1h.
- 2022–2024 development; 2025 reused historical evaluation. Neither is a fresh
  confirmatory sample. Do not score 2026 or the 15 expansion tokens.
- Include all eligible original signals and retain an executed-trades view.
  Keep configuration records separate; overlapping trades are not independent.
- Keep baseline fees, slippage, funding and regime exits; no maximum holding
  period. Verify minute input hashes against the earlier complete manifests.
- Freeze rules and record all attempts. Do not optimize RSI, ADX or volume
  thresholds during this audit.

## Comparable entry times

Construct the potential-control pool from completed entry-clock candles. Every
feature must be available at that candle close; fill at the next minute open.
Match within token, side, timeframe, historical partition, calendar week,
six-hour UTC time-of-day block, higher-timeframe regime direction and volatility
tertile. Define volatility as completed entry-clock Wilder ATR(14)/close; learn
tertile boundaries from 2022–2024 eligible-clock observations only, separately
for each token/timeframe, then freeze them for 2025.

Exclude exact original signal times from the control pool. Require at least five
eligible control times in a stratum; otherwise mark the signal unmatched. Draw
up to twenty distinct controls per signal using seed 20261006. Permit reuse
across different signals, record it, and disclose the effective unique-control
count. Never relax matching criteria after inspecting outcomes. Report coverage
by cell, quarter and volatility bin; matched-subset evidence does not describe
unmatched signals.

Do not match on future holding time, eventual exit, winner status, favourable
excursion, adverse excursion or exit RSI. Matching controls measured context,
not unobserved confounding; estimates are not causal proof.

## Outcomes and uncertainty

Primary entry-prediction diagnostic: signed close return after four hours minus
the mean return at that signal's matched control times. Secondary descriptive
horizons: one and 24 hours, with favourable/adverse excursions. These horizons
measure prediction and are NOT trading exits or holding limits. Use identical
partition-boundary exclusions for real and control observations and report them.

Also simulate independent opportunity outcomes for each existing SL/TP policy
(2%/2.5%, 3%/3%), with identical regime exit, funding and modeled execution for
real and control entries. These overlapping opportunity returns are diagnostic,
not an executable portfolio. Conservatively resolve minute-bar stop/target
ambiguity using the archived execution policy. Report ambiguity counts.

Report effect sizes and calendar-block bootstrap intervals (one-week and
four-week blocks, 10,000 draws), preserving paired differences and shared-time
dependence. Report the 18 token/direction/timeframe cells in each historical
period. Use Bonferroni simultaneous 95% intervals over the 36 primary contrasts;
secondary horizons and exit diagnostics cannot rescue a failed primary claim.
These adjustments do not undo the earlier reuse of historical data.

## Progression rule

An entry hypothesis warrants a separate executable experiment only when primary
uplift is positive in both periods, has at least 100 matched signals across
20 distinct weeks in each period, and has positive simultaneous lower bounds
under both block lengths in both periods. This is a conservative research triage
rule, not a certification of profitability. Report all cells regardless of pass.

If no cell qualifies, report that outcome and reframe the entry hypothesis;
do not relax the rule until a survivor appears. If a cell qualifies, freeze one
entry-time change in a new protocol, then replay ALL eligible signals with
position occupancy and pending-order handling. Do not filter the old trade list.

Profit protection and adaptive stops remain subsequent isolated experiments.
Do not combine entry selection, stop widening and a new exit in one comparison.
Equal-risk sizing is required for stop-width comparisons. Fresh confirmation
must use documented unused data and/or a future frozen paper cohort.

## Required tables and reproducibility

Export input hashes, source hashes, all original signals, all control draws,
unmatched reasons, feature timestamps, chronological trade ledgers, and tables
by token/direction/timeframe/period. Include count, stop count/rate, net mean,
profit factor, average win/loss, costs, holding duration, boundary marks,
uncertainty and chronological drawdown where an executable replay is available.
Do not label overlapping opportunity drawdown as portfolio drawdown.

Execution blockers and recovered-file checks are recorded by `audit_inputs.py`.
Run it with `--cache PATH` after restoring the six original parquet inputs.
