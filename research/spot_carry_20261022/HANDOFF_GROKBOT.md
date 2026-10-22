# Grokbot assignment: acquire, audit and test same-token funding carry

Owner-authorized research continuation, 22 October 2026 (Asia/Dubai).

## Objective and current state

Determine whether a long-spot/short-perpetual position in the SAME token can earn useful funding income after realistic execution, basis and capital costs, and add value compared with the approved historical strategies. Scope: BTCUSDT and ETHUSDT, 2022–2025. Do not claim success from the gross funding index alone.

The same-token strategy has not been implemented or backtested in this handoff. This branch contains only executable public-data collectors, synthetic tests and task instructions. It includes no private research records, account data or existing strategy results. Obtain the historical inputs directly from the exchange on your authorized host.

Work autonomously through the phases below when evidence permits. Do not stop for routine confirmations. If a required source is inaccessible, a verification fails or a defensible risk model cannot be specified, preserve the exact blocker and completed artifacts. Do not manufacture coverage or performance to complete the task.

## Phase A: acquisition and data audit

1. Use a separate research worktree at the supplied commit. Read README.md and DATA_REQUEST_spot_perpetual.txt. Check MANIFEST.json against file bytes. Run all offline collector tests.
2. Run both the candle collector and funding collector probes. Require six candle/mark responses with ten correctly identified historical rows each and both funding probes with nonempty, correctly bounded settlements. Review both summaries for failures and actual settlement intervals. If valid, run both full resumable downloads. Keep the process alive in the host's normal research-job/session facility and record PID/session, logs and output path. Do not report it finished merely because it was launched.
3. Audit all 288 stream/token/month units: SHA256, instrument identity, UTC timestamps, duplicates, out-of-window rows, finite valid OHLC, volume/turnover units, missing intervals and actual spot/perpetual/mark intersections. Inspect basis discontinuities. Do not substitute perpetual prices for spot or silently fill gaps. Report common usable coverage by token/month/year; any coverage exclusion must be fixed before strategy outcomes.
4. Download realized BTC/ETH funding for 2022–2025 with the provided public funding collector. Cross-check completeness, changing intervals and any independent accessible exchange source; preserve discrepancies. Join settlements to mark observations and document settlement timing/proxy limitations. Never use future realized funding to choose entry or exit.
5. Establish spot/perpetual fee assumptions, spread/slippage evidence, instrument size/tick rules and margin/collateral conventions. Current fee/risk-limit snapshots are not historical records. Use historical evidence where available; label and stress defensible assumptions where it is unavailable. No paid data purchase, account secrets or live account actions are needed.

Publish a data-audit summary with readiness and unresolved fields before moving to strategy evaluation. Price-download success alone does not establish readiness.

## Phase B: freeze a small, executable strategy protocol

After the audit and BEFORE inspecting strategy outcomes, commit a standalone protocol and implementation specification. Record commit SHA, dataset hashes, exact rules and the hypothesis count. This is reused 2022–2025 history, not a pristine holdout. Keep 2026 historical outcomes unopened.

Primary hypothesis: long paid-for spot and short the same token's linear perpetual, matching the actual net spot inventory after fees/rounding. No short-spot/reverse-carry leg without explicit historical borrow availability and costs. No claim that owning spot automatically prevents perpetual-leg liquidation.

Specify unambiguously:

- Entry uses only information already known, including lagged realized funding and lagged basis/liquidity context. Explain the economic cost hurdle and amortization assumption; do not fit a threshold grid to future profit.
- Fixed quantities versus rebalancing, both legs' fills, one-way delays, funding eligibility, spot-fee currency/inventory treatment and handling of partial/missing data.
- Dynamic exit when the economic premise fails, basis/risk controls and a mark-based margin/liquidation model. No arbitrary maximum holding period. Charge all exits and rebalances.
- Starting equity 20,000 USDT in simulation only; apply the owner's 1% simulated risk ceiling, 10% position cap and 15-position maximum consistently in the funded comparison. Define whether the cap counts total pair gross exposure and how the two legs consume capital BEFORE results. Do not use borrowed/free spot cash or unlimited collateral to make the return look larger. The previously authorized 70% drawdown entry-stop is for simulation only; no runtime risk setting changes.
- Baseline and moderate costs as the primary economic views. Severe costs as a secondary stress, not the sole veto. Calibrate plausible BTC/ETH execution using available evidence; distinguish measured costs from inherited 20/30-bps assumptions.
- A passive same-token carry control, cash and the frozen approved hourly/BL8 historical comparator where code/data can be reproduced. Compare on the same dates, costs and total capital tied up. If the incumbent cannot be reproduced, state that comparison is unavailable; never compare candidate percent ROI directly with incumbent research R.
- A small predeclared economic decision rule and uncertainty/concentration checks, rather than an open-ended parameter search. No historical winner-token whitelist or post-result rule rescue.

## Phase C: implement, validate, run and report

Implement the frozen protocol in the isolated research path. Verify cash/inventory conservation; funding sign and settlement boundaries; both-leg fees/slippage; quantity rounding; entry causality; gap handling; collateral/liquidation behavior; and no future timestamps. Preserve pre-outcome synthetic tests and protocol hashes. A genuine implementation bug fix must be logged; do not change the trading rule in response to losses.

Report 2022, 2023, 2024, 2025 and overall, with both BTC and ETH separately and the combined account. Clearly distinguish descriptive/development years and chronological reused-history evaluation.

Required results:

- Net funded-account return and ending equity on total committed capital, maximum drawdown percentage, exposure/utilization, trade count, win rate, profit factor, average win/loss and expectancy.
- R only if an explicit ex-ante risk denominator is meaningful; otherwise mark it not applicable and explain. Funding-rate sums are not R or ROI.
- Full P&L bridge: spot price, perpetual price/basis, funding, fees, slippage, rebalancing, financing/collateral costs and any forced exits. Include annual and token breakdowns; only these two tokens are in scope, so do not invent broad sector evidence.
- Baseline/moderate/severe, a causal execution-delay sensitivity, blocked/missed opportunities, open end marks and missing-data/censor counts.
- Direct incumbent comparison and incremental combined-account result where reproducible, plus uncertainty, time/token concentration and the exact predeclared advancement decision.

Lead with a plain-English answer: is this better than the approved comparator, complementary, worse, or still unresolved? Do not claim market-beating or consistent future profitability from these historical results.

Commit code, protocol, tests, small summaries and a self-contained HTML report to a research branch/PR. Store large raw data and detailed ledgers outside Git with persistent artifact locations, hashes and reproduction commands. Return the PR/branch, final commit, job status, protocol hash, data audit, result table and any blockers to Brian. Do not message other people or bots on his behalf.

## Operational boundary

Research only. Do not modify or restart the running paper/live containers, account balance, risk configuration or PR149 deployment. Do not merge this work into a running application checkout. No trading orders are authorized by this handoff. Existing operational activation verification remains a separate workstream.
