# Independent next experiments — draft before new market runs

Purpose: test a different source of predictability, not repeatedly adjust losing thresholds until a winner appears. No experiment below has run on candles in this environment. This is a concrete proposal, not evidence of profitability or a new approved strategy.

## 0. Resolve data transport and reproduce
The Windows path and /workspace/uploads path belong to the operator/Grokbot environment, not this review environment. Upload the 218 MB ZIP here or provide an accessible download URL. Verify SHA256 344ac29b5b2ee2fe9ba5966026914489dc22dfaed75374fbe86316052da863dc before extraction; then verify six input file hashes against FINDINGS. Include the small v2 results folder so exact floats can be compared. Never commit market Parquets or credentials to git.

Run the independent tests, reproduce the original 96 cells, and run diagnose_baselines.py. Inspect exact quoted-path movement, slippage, fees, funding, exit reasons and quarterly stability for every cell. Quote-path returns are accounting decompositions at original exit times, not claims about a tradable zero-cost strategy. Different execution costs require full resimulation because stop levels and reentry opportunities can change.

## 1. Opportunity-conditioned sampling, before another pattern catalog
The relevant question is whether information available NOW identifies a higher chance of a profitable next move. Daily range seen after the event is not such information.

Build 15m decision observations using only completed bars. Labels: first +/−1%, 2%, 3%, 5% excursion within 1h/4h/8h/24h, with opposite barriers and unresolved-minute ties explicit. Treat this as descriptive/path research, not a grid of promoted trading systems. Purge 24h around temporal boundaries. Cluster observations by day/week; overlapping labels are not independent samples. Use disjoint events for reported capture counts.

Partition predictive features into: trailing realized volatility percentile; trend strength; distance from prior session VWAP; volume shock; BTC market move; ETH/SOL residual return relative to lagged BTC beta. Features, bin boundaries and models must be fitted exclusively on training dates. Compare calibration and net outcomes to base-rate and volatility-only controls. Good direction classification without sufficient net payoff does not qualify.

First use 2022–2024 to discover feature relevance. Use 2025 as a reused diagnostic period, not a fresh confirmation sample: its results are already known. 2026 is partly exposed through opportunity summaries and possibly other Grokbot studies. Reserve confirmation through locked chronological folds plus prospective paper observations after registration; document organisation-wide reuse.

## 2. Two genuinely different questions, with limited candidate budgets

### A. Volatility-normalized continuation (BTC first)
Hypothesis: fixed 3/5% barriers mix very different volatility environments; conditional continuation may be worth testing even though unconditional opening-range breakouts failed.

Hourly signal: close crosses the prior 24 completed hourly highs/lows; long requires price above its trailing 168-hour EMA, short below. Prior completed hourly ATR(24)/price must exceed its lagged rolling 30-day median. Enter next minute. Stop = 1.5 ATR; target = 3 ATR; time cap 24h. Freeze ATR at entry. Baseline A0 omits the volatility filter; A1 includes it. Same execution costs and one position per token. Exactly 2 variants × 2 directions × 3 tokens = 12 candidates; no EMA/ATR/lookback optimization. These are draft thresholds to preregister, not selections inferred from observed returns. Check catalog duplication before any implementation handoff. This may neighbor existing breakout work; do not run it against Grokbot's task queue without ownership coordination.

### B. Cross-asset residual reversion (ETH and SOL vs BTC)
Hypothesis: some ETH/SOL movement is common BTC exposure, and a temporary relative dislocation may be more predictable than outright direction.

Estimate beta from trailing 30 days of hourly returns, ending BEFORE the current signal hour. Residual = current token hourly log return minus lagged beta × BTC hourly log return. Standardize using lagged trailing residual volatility. Trigger after a residual z-score crosses ±2.5 from inside. Fade via dollar-notional token leg and beta-sized opposing BTC leg. Require finite positive beta; skip bad estimates. Hold fixed 4h in B0, exit on residual normalization or at 4h in B1. No naked single-leg fill assumption: entry/exit slippage, fees and funding on BOTH legs; stress asynchronous execution. Predefine package loss stop at 1% of gross entry notional, priced jointly on synchronized 1m observations; high/low of separate legs cannot reveal a simultaneous spread high/low. Exactly 2 variants × 2 directions × 2 tokens = 8 candidates. Hedge sizing and turnover must be recorded explicitly. This is not riskless arbitrage.

## 3. Economic hurdles and controls
All 20 new candidate evaluations count toward a recorded search budget, even failures. Retain every previous 48 configuration result. Before selecting finalists, require positive net mean and PF >=1.15 in chronological out-of-sample evidence, plus existing sample-size/CI/random controls. No loosening gates and no best-of-2026 retuning. Multiple-testing adjustment, correlated trades and nonstationarity remain relevant.

For control entries, match month, UTC hour, direction, trailing volatility bucket and trend regime; use identical exits, holding caps, costs and non-overlap rules. Report executed-trade counts and time in market, since matched signal counts do not guarantee equal exposure. Report bootstrap intervals clustered by week, performance by calendar period, effective independent observations, and robustness with the most profitable week removed. Such exclusions are robustness diagnostics, not opportunities to delete losses from reported returns.

Measure actual fill quality before assuming maker costs. Passive-fill backtests require order-book queue, fill probability and adverse-selection modeling; changing taker fees to maker fees on guaranteed fills is invalid. Test spread/impact sensitivity rather than using the most flattering assumed friction.

## 4. Leverage and capital
Do not use 5x/10x to rescue negative per-notional expectancy. If a candidate survives, simulate account risk at fixed loss budgets, correlated BTC/ETH/SOL exposure, both-leg collateral where relevant, funding and mark-price liquidation. Distinguish return on notional, return on posted margin and return on total account equity. Candle stop orders are not guaranteed fills.

## Decision after diagnostics
- Quoted-path movement approximately zero across periods: discard the signal, rather than polish its stops.
- Positive quoted-path movement smaller than costs: investigate turnover and real execution; do not pretend fills are cheaper.
- Positive net results concentrated in one period: treat as regime-specific hypothesis requiring fresh validation.
- No stable predictive feature or net-positive candidate: retain cash/idle and record the negative result. More activity is not the success metric.
