# BTC, ETH and SOL: isolated opportunity study

Protocol v2, amended 2026-10-03 before any historical returns were computed.

**Status: DATA BLOCKED.** No historical strategy result, net return, preferred token, or leverage conclusion has been established. Do not run `study.py` for returns while this status stands.

## Frozen v1

Protocol v1 stays frozen. Its text is reproduced byte-for-byte in "Frozen protocol v1 text" below, from the `# BTC, ETH and SOL` heading through the final source URL. SHA256 of that v1 file, taken before this amendment:

`5c5e6b29c27418ffbcfc5b3063dd2d16018c96dbca82530f9799d4983ffcfe66`

v1 was frozen before any candle results were viewed. v2 records the measured cache export and the rule for when a run is allowed. It leaves the v1 question list, chronology, 48-configuration matrix, cost assumptions, and execution rules unchanged.

## v2 delta

v1 already said to amend the protocol before results when coverage is insufficient, and that other cached intervals cannot substitute for 1-minute execution. The desktop export has now been measured. v2 writes that measurement down so the files in hand cannot be scored.

Ops export, desktop cache `C:\Users\PC\mar_trading_firm\data\cache`, window 2022-01-01 00:00:00 UTC through 2026-10-02 23:59:59 UTC inclusive. One-minute timestamps are bar opens. A complete tape is 2,499,840 opens per symbol, last open 2026-10-02 23:59:00 UTC. SGP1 `/data/state/data/cache` was empty. The desktop cache has no `*_1m.parquet` and no `*_5m.parquet` for BTCUSDT, ETHUSDT, or SOLUSDT. Daily parquet files are on the desktop and were not in the export zip. Coarse-file internal gaps were not computed; only first, last, and row counts were.

1-minute OHLCV is 0 rows for BTCUSDT, ETHUSDT, and SOLUSDT. Each symbol is missing the whole window (one hole, 2,499,840 opens). That hole covers discovery (2022-01-01 to 2025-01-01 exclusive), validation (2025-01-01 to 2026-01-01 exclusive), and reserved evaluation (2026-01-01 to 2026-10-03 exclusive).

In-window funding rows: BTCUSDT 5,108, ETHUSDT 5,108, SOLUSDT 5,468. All three start at 2022-01-01 00:00:00 UTC. The last observed stamp for all three is 2026-08-30 08:00:00 UTC. The shared hole is 2026-08-30 16:00:00 UTC through 2026-10-02 16:00:00 UTC, 100 steps of 8 hours, with no later cached funding stamp. BTC and ETH intervals inside the observed span are all 28,800 seconds. SOL includes 480 extra 2-hour prints from 2022-11-10 08:00:00 UTC through 2022-12-20 08:00:00 UTC (hours 0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22). The SOL 8-hour grid from 2022-01-01 00:00:00 UTC through the last observed stamp has no missing 8-hour step.

The zip also contains 15-minute, 1-hour, and 4-hour bars. Last in-file timestamps are short of the protocol end: BTC 15-minute 2026-09-03 08:15 UTC, ETH and SOL 15-minute 2026-08-31 11:45 UTC, BTC and ETH 1-hour 2026-09-08 05:00 UTC, SOL 1-hour 2026-09-29 06:00 UTC, and all three 4-hour series 2026-10-02 20:00 UTC. Those files are coverage evidence only.

### Block

The study stays DATA BLOCKED until both conditions below are true.

1. Complete 1-minute OHLCV for BTCUSDT, ETHUSDT, and SOLUSDT covers discovery, validation, and the reserved window: 2,499,840 bar opens each, 2022-01-01 00:00:00 UTC through 2026-10-02 23:59:00 UTC inclusive, and the v1 audit passes (explicit UTC timezone, unique timestamps, finite positive OHLC, no filled gaps, no cross-exchange splice).
2. Funding for all three symbols is filled through the reserved end, including the 100 missing 8-hour stamps from 2026-08-30 16:00:00 UTC through 2026-10-02 16:00:00 UTC. A later protocol revision may instead gate that hole explicitly, and that revision has to be frozen before any returns are viewed. v2 does not gate the hole.

### Coarse intervals

Scoring returns on 15-minute, 1-hour, or 4-hour bars under this package is forbidden. A study on those intervals needs its own protocol revision, written and frozen before any of its returns are viewed. v2 is not that revision. Five-minute files were not in the desktop cache and are not a substitute either.

### Unblock path

1. Backfill historical Bybit 1-minute OHLCV and funding into the cache for BTCUSDT, ETHUSDT, and SOLUSDT.
2. Re-export that cache.
3. Re-audit file hashes and gaps against the block conditions above.
4. Only after that audit passes, run `python study.py --cache <audited cache> --out <new results directory>`. The results directory must be new. Any later change to rules or windows is a new protocol version. v1 and v2 stay as written.

No candles are invented from the coarse files. No historical returns are computed from this export.

## Frozen protocol v1 text

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
