# BTC, ETH and SOL: isolated opportunity study
Protocol v1, frozen 2026-10-03 before any candle results were viewed.

Status: DATA BLOCKED. No historical strategy result or winning token has been established.

## Independence
This package has no trading, VM, API-key or production-repository dependency. It reads copied market data and writes a new results directory. It never launches the firm's validators, edits approvals, merges code, sends worker messages or places orders. Grokbot retains its active strategy tests. Earlier recovery edits remain uncommitted and undeployed in a separate checkout.

## Questions
1. How often do BTC, ETH and SOL offer 1%, 2%, 3% and 5% directional excursions within 1, 4, 8 and 24 hours?
2. How much adverse movement happens before a target? Does the target precede a 1% or 1.5% stop?
3. Are opportunities clustered by UTC hour, volatility and trend? Are multiple apparent moves merely overlapping observations of one move?
4. Can a rule known BEFORE entry capture a positive net expectancy, including losing trades, fees, slippage and funding?
5. Does performance survive chronological validation, reserved evaluation and matched random entry timing?

## Data contract and audit
Bybit USDT linear perpetuals: BTCUSDT, ETHUSDT, SOLUSDT. Prefer complete 1-minute OHLCV from 2022-01-01 through 2026-10-02 UTC inclusive. Use 1-minute execution; aggregate only complete 15-minute signal bars. Prior history is used only for indicator warm-up. No open candles, filled-in gaps, duplicate timestamps, invalid OHLC, or cross-exchange splicing. Missing history is a blocker, not zero returns. Audit and SHA256 hashes precede testing.

Copy the repository's data/cache/<SYMBOL>_1m.parquet plus data/cache/funding/<SYMBOL>_funding.parquet. Other cached intervals can inform a coarse study but cannot substitute for 1m execution. Funding timestamps must be timezone-aware UTC and rates decimal fractions. Funding valuation uses the 1-minute traded-price open as an explicitly labelled approximation to mark price. Missing funding or coverage gaps fail the runner. Historical order-book depth, spread, mark prices, maintenance tiers and liquidation rules remain necessary for leverage/execution validation.

## Chronology
Discovery: 2022-01-01 to 2025-01-01 exclusive.
Selection/validation: 2025-01-01 to 2026-01-01 exclusive.
Reserved evaluation: 2026-01-01 to 2026-10-03 exclusive.
This last period is reserved within THIS study only. Grokbot may have used it already; it is not claimed to be untouched across the organisation. All endpoints UTC. Trades must have their entire maximum holding window within their partition. No retuning after reserved results. If data coverage is insufficient, report it and amend the protocol BEFORE results, retaining both versions.

## Fixed exploratory rule matrix
48 configurations total: 3 tokens x 2 mechanisms x 2 directions x 2 targets x 2 stops. Targets 3% and 5%; stops 1% and 1.5%; maximum holding 24h. No parameter sweep beyond this matrix.

A. UTC opening-range breakout: first hour of each UTC day defines the range. A completed 15m candle from 01:00 through 08:00 UTC crosses outside that range from inside. Take the first directional signal per day.
B. Prior-range sweep/reclaim: a completed 15m candle sweeps the previous 16 completed bars' high/low and closes back inside. Fade the sweep, LONG below the low or SHORT above the high. No same-bar entry.

These are research baselines, not approved novel sleeves, and no claim of independence from the historical catalog is made. They do not implement Grokbot's active impulse_pullback_continuation task.

Enter at next 1m open after signal close. One position per token/configuration; no pyramiding. Market entry and exits. If stop and target touch within one minute, stop wins. Gap stops fill at the worse opening price, then adverse slippage. Target gaps receive no favourable improvement. Time exits at the final bar close. Funding events in (entry, exit] charged; if a settlement is in an ambiguous exit minute, choose the larger funding cost. This is a conservative uncertainty bound, not tick-accurate execution.

## Costs and scoring
Fee assumption: 5.5bp per side on actual entry/exit notional (standard non-VIP schedule, account-specific fees may differ). Base adverse slippage 5bp/side BTC and ETH; 10bp/side SOL. Stress doubles those values and re-simulates fills. These are assumptions, not measured liquidity estimates.

Discovery and validation results are reported for all 48 tests. Select at most one configuration per token using validation mean return, requiring discovery AND validation PF >=1.15, positive mean, and >=50 trades each. If none qualifies, select none; do not loosen the gates. At selection, freeze choices before reserved evaluation.

Reserved candidates: weekly block bootstrap mean confidence interval (2,000 replications, fixed seed); 99% interval to conservatively cover at most 3 finalists. Matched random baseline (200 seeds): same signal count within each UTC month/hour, same direction, barriers, execution, costs, funding and non-overlap engine. It is not conditioned on the signal's volatility or trend regime: add regime matching before any approval. Raw p-value uses (1 + null means >= observed)/(1 + valid simulations); apply Holm correction across finalists. Stress must remain positive. These are research screens only. None changes approval rights; existing CI/beats-random/F-kit gates still apply.

## Opportunity measurement
Use fixed, non-overlapping start grids for each horizon; long and short reported separately. Future high/low is descriptive only, never an entry feature. UTC daily high-low ranges do NOT prove that those ranges can be repeatedly captured. Counts from different horizons/directions must not be added as independent trades. Regime/session breakdowns are descriptive and cannot be turned into a new filter without a new, separately evaluated protocol.

## Leverage
First establish an unlevered edge. 5x and 10x multiply both P&L and costs relative to posted margin; they do not increase predictive accuracy. Account return additionally depends on notional/account-equity. Fixed-fractional risk, simultaneous correlated positions, mark-price liquidations and funding stress need a separate portfolio simulation. No approval for leveraged live trading is inferred from candle research.

## Sources checked 2026-10-03
- https://bybit-exchange.github.io/docs/v5/market/kline
- https://bybit-exchange.github.io/docs/v5/market/history-fund-rate
- https://bybit-exchange.github.io/docs/v5/guide
- https://www.bybit.com/en/help-center/article/FAQ-USDT-Perpetual-and-Expiry-Contracts
- https://public.bybit.com/kline_for_metatrader4/

Access evidence: api.bybit.com returned Site Unavailable; documented api.bytick.com explicitly reported country restriction. Public archive listings were readable via search, but CSV download returned HTML and the search tool could not retrieve binary CSV. No proxies or regional bypasses were used. No candles were obtained or results fabricated.
