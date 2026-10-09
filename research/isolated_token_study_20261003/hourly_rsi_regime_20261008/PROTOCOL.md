# H-RSI-REGIME-01: incremental RSI exhaustion gate by prior market state

Pre-scoring protocol, 8 October 2026 Dubai. Brian authorized the four-arm test
at09:03 Dubai after reviewing the plan. Current owner-approved PAPER benchmark is
hourly_compression_btc_connors_loweff_v1: compression + own-token Connors + BTC
confirmation + a one-prior-ATR extension cap ONLY when prior ER24<0.30.
This study changes no runtime or deployment approval.

## Hypothesis and competing explanation

A conventional RSI14 exhaustion gate may avoid exhausted compression entries
in one prior path state while discarding valuable continuation trades in another.
The older standalone RSI test improved pooled2022–24 but worsened2025. That result
motivates this conditional follow-up; it does not establish a state or calendar
rule. Connors and the extension cap may already remove the same losing trades,
leaving no incremental benefit for RSI14. Both explanations are tested.

Four prespecified policies on the CURRENT approved benchmark:
- approved_none: no added RSI restriction.
- approved_always: add RSI restriction in every state.
- approved_directional: add it only when pre-signal ER24>=0.30.
- approved_loweff: add it only when pre-signal ER24<0.30.

RSI restriction: own-token completed-hour Wilder RSI14<=70 for LONG and >=30
for SHORT. Equality passes. No lower long bound, upper short bound, crossover,
slope or new setup-memory rule. Thresholds are unchanged from the earlier study.
The existing extension cap continues to apply in low-efficiency conditions in
ALL FOUR arms. No original/no-cap benchmark is substituted for current approval.
No new diagnostic arm, threshold sweep, token selection or post-result rescue.

## Causality and fixed state

Let completed hourly closes be labelled by close time and T be entry time.
RSI uses the signal hour [T-1h,T), ending at minute T-1min. Seed Wilder gain/loss
with the first14 changes, then recurse (13*prior+change)/14. Flat path gives50,
all gains100, all losses0; missing warmup stays missing. Reuse the frozen,
independently tested RSI module and independently reconstruct scalar RSI from
raw-minute endpoints at every original signal. Confirm prior saved RSI equality.

ER24=abs(C[T-1h]-C[T-25h])/sum(abs(24 hourly changes between those endpoints)).
It excludes the signal hour. Flat path gives0; cutoff0.30 with equality assigned
to directional. Use the exact state definition from H-EXT-REGIME-01, verify
independently from minute closes. Missing/duplicate/gapped context is an error,
never forward/backfilled. These are measured states, not labels for whole years.

## Fixed sample and execution

BTC/ETH/SOL; both sides;1h; SL2%,TP2.5%,no timeout. Begin with ALL143 original
membership-eligible raw opportunities, apply the unchanged approved conjunction,
then each RSI policy and independently replay occupancy. Do not simply filter
previously admitted trades. New opportunities freed by skipped trades count.

Same monthly membership/rank; one position/token across sides; basket6 and
same-direction3 limits; exit minute remains occupied. Historical2022–24 and
flat-reset2025 are scored separately.2025 is repeatedly examined/exploratory,
not untouched validation. No2026 feature or trade outcome is scored.

Use hash-verified previously validated minute paths: quote barriers, stop-first
ties, adverse stop gaps, target quote, actual funding and the same conservative
funding boundary convention. Fees0.055% per side. Base slippage0.05% BTC/ETH and
0.10% SOL per side; stress doubles only slippage. For retained raw opportunities,
paths/costs remain identical. Net R=net return/0.02. Production fills/shared account
risk differ from this research simulator; this is not an account PnL forecast.

## Selection and required reports

For EACH added-RSI policy, both periods must be nonempty with positive full-basket
means; neither period's mean may decrease versus approved_none at either cost;
at least one period must strictly improve at each cost. Floating tolerance1e-12.
Ties in one period are allowed. Fully identical policies have no demonstrated
incremental value. This is a practical point screen, not statistical proof,
automatic approval or a profitability guarantee. Thin cells are insufficient
for strong state conclusions; do not change thresholds to enlarge them.

Report trade/stop/target counts and rates, wins, base/stress mean, profit factor,
mean/sum R, additive net sums, holding times, token/side/year, leave-one-token-out
and within-state descriptive results. Additive sums are not funded account
returns. Report shared executions, directly excluded stops AND target winners,
new admissions, eligible baseline trades displaced by occupancy; reconcile totals.

Use the unchanged paired calendar block bootstrap (1week/4week,10,000 draws,
fixed seeds, empty weeks included), absolute and incremental intervals with valid
sample counts. No state may be called validated simply because it ranks highest.
Preserve original opportunities/context, each arm's ledger and ordinary CSVs.

## Verification, provenance and next step

Publish this protocol, implementation, tests and novelty audit before freeze/run.
Freeze source, feature, six raw-input and prior-result hashes. Verify RSI and ER
against independent minute-array/scalar methods for all143 original contexts;
reconcile286 cached cost rows with the prior RSI experiment, reproduce the
approved opportunity set and112 admitted cost rows (41+15 trades, two costs),
independently replay16 admission cells, verify shared costs and12 attributions.
Check final report values against ledgers. Preserve every attempt in a new
output folder and fresh-restore-check a durable checkpoint.

After this bounded follow-up, prioritize independent evidence: a preregistered
broader-token study when data arrive and prospective observation of the fixed
paper rule after verified deployment. Reserve2026 outcomes until a separate
validation protocol and data-coverage check are frozen. No automatic RSI activation.
