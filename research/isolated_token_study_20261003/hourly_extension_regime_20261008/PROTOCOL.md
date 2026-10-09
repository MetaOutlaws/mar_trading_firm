# H-EXT-REGIME-01: fixed extension cap conditional on pre-breakout efficiency

Frozen before state-conditioned results, 8 October2026 Dubai. Brian authorized
the next planned test and approved BTC + Connors as the latest PAPER preference.

Hypothesis: a one-prior-ATR breakout extension cap has state-dependent value.
It may exclude exhausted trend continuations, but remove useful breakout starts
in low-efficiency conditions. No threshold search or outcome-selected states.

One causal state definition, reusable unchanged for the queued RSI follow-up:
Let hourly closes be labelled by their close time, and T be next-hour entry time.
ER24(T) = abs(C[T-1h]-C[T-25h]) / sum(abs(hourly close changes)) over those24
changes. Thus even the signal hour [T-1h,T) is excluded. ER>=0.30 is directional;
ER<0.30 is low-efficiency. Equality passes; a fully flat24h path has ER=0.
These are measured path states, not definitive economic regime labels. Missing
context is an error, never forward/backfilled. Causal timestamps verified against
independent minute-array endpoints and direct24-change sums for all143 signals.

Main benchmark: approved BTC+Connors entry conjunction, same original143 raw
opportunities, SL2%/TP2.5%, no timeout. Four arms: benchmark; extension cap always;
cap only when directional; cap only when low-efficiency. In the other state the
conditional arm uses the benchmark unchanged. Fixed side-adjusted extension
(signal close minus prior20-hour breakout boundary)/priorATR <=1, equality passes.
No RSI14/ADX/exit changes. Both conditional arms are preregistered; neither is
selected as a validated rule just because it looks best after scoring.

Diagnostic control: the same four policies on original hourly compression,
separate from the main benchmark, to explain the saved historical cap effect.
Do not optimize the obsolete baseline instead of the current approved benchmark.

Unchanged fees0.055% per side, funding, quote barriers, stop-first ambiguity,
adverse stop gaps, slippage0.05% per side BTC/ETH and0.10% SOL; stress doubles only
slippage. Same membership/ranking, one position/token, basket6/direction3, occupied
exit minute. Replay ALL eligible raw opportunities separately for8 arms*2 periods
*2 costs. Reuse hash-verified validated raw paths, not old admitted subsets.
Reconcile existing original/cap/current-combination ledgers exactly. Six raw input
hashes, feature/source/reference hashes frozen; no2026 price outcomes scored.

Selection reporting separates useful point evidence from independent validation.
For each main conditional policy: both periods' mean net must remain positive;
mean net must not decrease versus BTC+Connors in either period at either cost;
at least one period must strictly improve at each cost. Equality in one period
is acceptable, explicitly correcting the overly rigid prior selection approach.
Floating equality tolerance1e-12. This is a point-estimate non-degradation screen,
NOT statistical proof of non-inferiority. No automatic deployment. Report thin
samples and unchanged policies explicitly. Do not rescue thresholds after results.

Report trade/stop/target counts, base/stress mean, win rate, additive net sums
(not portfolio return), token/side/year, leave-one-token-out, paired10,000-draw
one/four-week bootstrap contrasts and valid draws. All2025 evidence is repeatedly
reviewed and exploratory. State summaries must include opportunity coverage,
removed stops AND target winners, retained/new/occupancy-lost trades. Report full
valid hourly state frequencies and signal frequencies by period; don't assume
2022–24=trend or2025=chop. Grouping admitted trades is diagnostic, not the same as
replaying a state-only portfolio. Preserve previous studies and frozen decisions.

Next after this experiment: same frozen state definition for H-RSI-REGIME-01,
separately, then broader-token/prospective confirmation when data are available.
