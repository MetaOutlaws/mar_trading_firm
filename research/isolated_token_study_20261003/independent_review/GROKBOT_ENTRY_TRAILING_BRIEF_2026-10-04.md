# Grokbot brief: token-specific entries and trailing exits
Date: 2026-10-04
Status: proposed next research protocol; experiments below have NOT been run.
Owner: Grokbot to coordinate its existing team and return an isolated research PR.

## Objective
Determine whether observable entry conditions predict favourable price movement in BTCUSDT, ETHUSDT and SOLUSDT, and whether trailing exits improve net results on those entries. A profitable outcome is a hypothesis to test, not an assumed deliverable.

Read EMPIRICAL_FINDINGS_2026-10-04.md and results_20261004/ in this directory first. The original 48 configurations and 20 alternatives produced no qualifying survivor. Do not present these new instructions as completed tests.

## Coordination and scope
Before executing, record which worker owns entry research, execution simulation and independent verification, and check for overlap with the team's active impulse_pullback_continuation work. Reuse relevant work with attribution, avoid running conflicting deployments or duplicate parameter searches. Work on an isolated research branch/worktree. Do not alter running workers, VMs, live settings or the approval book. Return findings through a draft PR for Brian; no automatic promotion.

## Data and provenance
Use the supplied one-minute candles and historical funding:
isolated_token_study_1m_2022_20261002_v2.zip
SHA256: 344ac29b5b2ee2fe9ba5966026914489dc22dfaed75374fbe86316052da863dc
Archive locations previously supplied: Windows Downloads, or an available verified research copy.
Cache layout: BTCUSDT_1m.parquet, ETHUSDT_1m.parquet, SOLUSDT_1m.parquet, funding/*_funding.parquet.
Verify fingerprints against the empirical report manifests. Do not put raw candles in GitHub. Record code version, input hashes and every experiment.

## Stage 1: characterize moves without hindsight entries
Study upward/downward excursions of 1%, 2%, 3% and 5% per token over explicitly fixed horizons. Register horizons and sampling rules before reading new outcome summaries. Treat these thresholds as descriptive labels, not four optimized trading targets.

Measure maximum favourable/adverse excursion, time to each threshold and the order of adverse/favourable moves. Label all eligible observation times, including failures. Decluster overlapping events or use temporal blocks for uncertainty.

Examine only entry-available features: trailing realized volatility/ATR, relative volume, prior range compression, trend, distance from prior highs/lows and time of day. Use completed bars and lagged statistics. Future extrema may construct research labels but must never define an executable entry or a feature.

Compare each pattern with matched observations that did not produce the move. Measure incremental value against controls matched on token, side, hour and volatility. Report token-specific sample sizes, base rates and effect sizes.

## Stage 2: bounded entry discovery
Start with interpretable rules or a simple regularized model before complex models. Define the feature list, model/rule budget, hyperparameter budget and chronological splits in a committed execution addendum BEFORE fitting or scoring. Count all attempted configurations, including discarded ones.

Use expanding chronological folds with training-only fitting/scaling/feature selection. Purge labels that overlap evaluation boundaries; do not shuffle observations. Account for overlapping outcomes and long/short correlations. Test predictive value at fixed horizons before choosing exit settings.

Discovery 2022–2024 and validation 2025 have already been explored. Any further use is exploratory, not fresh confirmation. Do not score 2026 strategy returns during this stage. Earlier opportunity summaries partially exposed 2026. Freeze any eventual candidate before a separately documented reserved evaluation; genuine confirmation also requires new prospective observations.

## Stage 3: compare exits on the SAME entry opportunities
For each frozen entry candidate, compare:
1. Fixed initial stop and fixed target (baseline).
2. Initial stop plus trailing stop activated only after a specified favourable move.
3. Initial stop plus volatility-adjusted activated trailing stop.
4. Partial profit-taking plus trailing protection of the remainder.

Before scoring, commit exact initial risk, activation threshold, trailing distance, ATR convention, partial fraction, time limit, position sizing and a SMALL finite configuration budget. Set thresholds using training data only; no unrecorded search for a profitable combination.

First compare exits on paired identical entries to isolate exit effects. Those paired experiments may overlap and are NOT a deployable portfolio. Then evaluate each complete strategy chronologically under the same one-position/risk rules and disclose differences in eligible entries caused by holding duration.

For minute-candle execution, never credit a favourable high that tightens a trail and then assume an advantageous ordering versus the same bar's low. Define and test a conservative ordering or update trails from completed bars for the following bar. Gap fills can be worse than the stop. A stop price is not a guaranteed locked profit.

## Costs, validation and reporting
Use the prior modeled base fees/slippage for comparability, plus doubled-slippage stress and actual funding. Apply fees to every partial exit; avoid double counting entry fees or funding. No assumed maker fills without fill evidence. Clearly state that candles cannot establish order-book depth, queue position, tick ordering or actual mark prices.

Report per token/configuration: net expectancy, profit factor, trade count, win rate, payoff ratio, adverse excursion, profit giveback, holding time, exit reasons, losing streaks and drawdown with its sizing definition. Fixed-notional return sums are not account equity. No leveraged return claims without a separate margin/liquidation model.

Maintain the earlier minimum screening gates (at least 50 trades, positive net expectancy and PF >= 1.15 in both historical periods, positive expectancy under doubled slippage). These are screening criteria, not sufficient proof. Any survivors also require temporal-block confidence intervals, matched controls, accounting for multiple testing and prospective paper confirmation.

Add meaningful tests for trailing activation, monotonic stops, gap-through stops, same-bar ambiguity, short-side symmetry, partial-exit accounting, funding, future-feature leakage and partition boundaries. Reconcile representative trades against a simple independent reference calculation.

## Deliverables
- Committed execution addendum BEFORE new results; complete experiment ledger.
- Reproducible offline runner and tests.
- Token-level move/entry diagnostics including failures and matched controls.
- Paired exit comparison and separate chronological strategy results.
- Full result tables and per-trade export instructions.
- Plain-English conclusion: qualifying candidates or none, limitations and the next evidence needed.

Report negative findings in full. Stop at the declared experiment budget; do not enlarge the search merely because it failed to find profit.
