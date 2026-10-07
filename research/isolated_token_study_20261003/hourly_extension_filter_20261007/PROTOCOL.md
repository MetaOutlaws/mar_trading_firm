# Hourly compression: fixed breakout extension cap

Pre-scoring protocol, 7 October 2026. Brian authorized the entry-selectivity plan.
This batch executes its FIRST comparison. BTC market confirmation and oscillator/
trend-strength filters remain subsequent independent comparisons, not stacked
changes in this run. Read NOVELTY_AUDIT.md.

## Hypothesis and single cutoff
A qualifying hourly compression breakout whose completed signal close is already
far beyond its prior range boundary may leave poorer entry economics. Test one
volatility-normalized cap. The earlier sweep confirmation study motivates asking
about entry location, but does not establish this relationship for compression.

Use all 143 original membership-eligible hourly signal opportunities, not only
the 133 previously admitted trades. For each LONG signal, boundary B is the
maximum high of the 20 COMPLETED hours immediately before the signal hour.
For SHORT, B is the corresponding minimum low. Exclude the signal hour from B.
A is Wilder ATR14 in absolute price units at the close of the preceding hour,
also excluding the signal hour. Seed with the first 14 true ranges' arithmetic
mean, then A[t]=(13*A[t-1]+TR[t])/14, as in the frozen baseline features.

Extension E = side*(signal_close-B)/A. The baseline already requires E>0.
Treatment keeps E<=1.0, with equality included; reject E>1.0. Require finite,
positive A; an invalid reference is a verification failure, not a silent data
drop. One prior ATR is a simple fixed unit of recent movement, selected before
inspecting extension distributions or treatment outcomes. It is not an optimized
or claimed optimal threshold. Do not scan 0.5/1.5/2.0 or token-specific cutoffs.

The calculation uses the completed signal close, not the following entry open.
Preserve each retained signal's exact next-minute entry and its original raw
SL/TP path. This is an admission filter, not a delayed-entry or pullback order.
No retry, new signal trigger, indicator filter, new timeframe or stop/target arm.

## Fixed research baseline
BTCUSDT/ETHUSDT/SOLUSDT, both directions, 1h compression entry. SL2%, TP2.5%, no
holding timeout, quote-based brackets. Fees0.055% per side, base slippage0.05%
BTC/ETH and0.10% SOL per side, doubled-slippage stress, actual historical funding
with the existing conservative exit-minute rule. Stop-first ties, adverse stop
gaps, target at quote. Initial risk R=net return/0.02. Additive return sums are
not account equity. No production, approval, live or leverage change.

Same monthly membership/rank and one position per token across sides, six basket
and three per direction slots; no reentry in an exit minute. Replay each arm
from ALL its eligible raw signals: a skipped trade can free a slot for a later
signal which can then block another baseline entry. Keep that effect separate
from exclusion by the extension predicate.

## Data, periods and causality
Historical2022–24 and flat-reset reused2025. No2026 candle in features, entries or
exits; boundary funding is retained only as required by the existing accounting
contract. Terminal marks are separate and excluded from closed win/stop rates.
Verify six input hashes, nine frozen features, four baseline reference files.
Independently reconstruct B, the signal close and prior ATR from raw minute data.
Do not fit or select a threshold using these prices/outcomes before freezing.
2025 has repeatedly been examined; it is exploratory, not an independent holdout.

## Required comparisons
Two arms: original baseline and extension_cap_1atr. Two cost scenarios and two
partitions. Report closed trades, stop hits/rates, targets/marks, win rate, net
mean/PF, mean and sum initial-risk R, holding time, annual/token/side detail.
Use existing1-week and4-week shared-calendar block bootstraps with10000 draws
and fixed seeds, including empty weeks. Show uncertainty in the difference.

For all raw opportunities and separately original baseline admissions, report
retained/excluded counts, stops avoided, target winners excluded and their
counterfactual net contribution. Then compare actual chronological ledgers:
shared identical trades, baseline-only entries rejected directly by the filter,
baseline-only entries lost through changed occupancy, and newly admitted trades.
Reconcile total additive change exactly to added returns minus dropped returns;
retained trades must have identical prices, exits and costs. Do not attribute
all lost baseline trades directly to the extension rule.

Primary exploratory continuation criterion: treatment has positive stressed
chronological mean in BOTH periods AND a positive stressed difference in mean
versus baseline in BOTH. Also report win/stop-rate changes, total return change,
sample retention, confidence intervals and token/year concentration. A point
pass is not independent qualification. Empty arms are insufficient evidence.
No automatic deployment, leverage, cutoff rescue or broader-token gate changes.
Fewer trades may improve selectivity; losing fewer total units only by taking
fewer trades is not proof of better per-trade expectancy.

## Verification and publication
Commit this protocol and duplicate audit before scoring. Freeze source/input/
feature/reference hashes; preserve each attempt. Test long/short symmetry,
exact cutoff, strict breakout requirement, invalid ATR, excluded signal-hour
boundary/ATR, future perturbation and unchanged retained execution. Verify all
143 raw barriers and reproduce the complete baseline, including its286 raw cost
rows and266 admitted cost rows. Independently replay all eight admissions.
Publish findings and aggregate contrasts in draftPR99; retain full ordinary CSV
ledgers, excluded/new-trade evidence and a freshly verified private checkpoint.
Update the roadmap with this result and next queued BTC-confirmation comparison.
