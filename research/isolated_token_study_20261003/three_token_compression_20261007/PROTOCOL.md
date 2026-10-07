# Three-token compression diagnostic — frozen scope amendment

7 October 2026 UTC. User instruction: run the planned experiment here using the available BTC, ETH and SOL data while additional-token access is unavailable.

This is a diagnostic on previously studied assets and years. It cannot satisfy the broader replication requirement of eight previously untested tokens. No independent holdout claim, strategy approval or leverage approval follows from this run. The original broader-token protocol remains unchanged.

## Fixed design

- Symbols: BTCUSDT, ETHUSDT, SOLUSDT, USDT linear perpetuals from the saved original minute/funding cache. No token selected by its profitability.
- Compression entry and feature warm-up: unchanged `entry_discovery_20261006/features.py`. Long: prior six-bar mean true range / prior sixty-bar median true range <=0.7; current true range >=1.5 times prior ATR14; volume >=1.5 times prior twenty-bar median; bullish close above prior twenty-bar high in the top quarter of the candle; nonnegative preceding 24-hour return. Short is the mirror. Completed 5m, 15m and 60m candles; entry at the next available minute open, the close timestamp of the completed signal candle. Cached causal features are reused only after checking their frozen hashes and entry alignment.
- Primary arm: 2% stop / 2.5% target. Descriptive arm: 3% stop / 3% target. All clocks and both directions pooled in each arm. No threshold fitting, RSI filter, target-distance gate, regime exit or holding-time limit is added.
- Existing execution: fixed quote-based barriers; adverse gap stop fills; same-minute stop/target ambiguity goes to stop; conservative funding timing. Fee 0.055% per side. Base per-side slippage BTC/ETH 0.05%, SOL 0.10%; stress doubles slippage. Actual cached settled funding included. Targets/stops do not move between cost scenarios.
- Existing admission: one open trade per token across clocks and sides; maximum six overall and three per direction. At conflicting simultaneous same-token directions skip both; otherwise prefer 60m >15m >5m. Cross-token ties use prior liquidity rank, then symbol. Exit minute remains occupied until the following minute. With only three symbols, the six-position limit cannot bind; a larger basket is not stress-tested.
- Generate every eligible raw signal opportunity before pooled admission. Do not build this test from previously thinned per-configuration trade ledgers.

## Monthly membership and chronology

Adapt the original liquidity rule to the three specified symbols: at least 90 observed calendar days from the first cached minute; all previous 30 completed daily turnover observations; median daily USDT turnover >=10 million. Rank qualifying symbols by this median, then alphabetically. No new assets or replacements. Derive daily turnover from complete minute grids. Freeze monthly eligibility before calculating trade outcomes. Membership affects new entries only.

The cache begins in January 2022, so this observed-history rule can delay eligibility until April 2022. No pre-cache listing history is invented. Eligibility exclusions and all monthly ranks are saved, including months with no eligible symbols.

Historical context: 2022-01-01 through 2024-12-31 as one continuous run. Reused evaluation: calendar 2025, reset flat at the boundary, with explicit terminal marks in both partitions. Annual summaries are by entry year; the historical partition carries positions across 2022/23 and 2023/24. The old reference checks retain the original development/selection boundaries. Consequently historical descriptive counts need not equal the old discovery counts.

No price bars from 2026 are scored. The single funding settlement exactly at 2026-01-01 00:00 UTC is retained for terminal cost accounting; no later funding is used.

## Reporting and validation

Report pooled base/stress mean net return and mean nominal-stop R, all trades versus closed trades versus terminal marks, closed net win rate, target hits, stops and stop fraction, holding times, cost decomposition and admission rejections. Include every token, clock and direction subgroup as descriptive evidence, not an invitation to select historical winners. The wider arm changes both stop and target, so its difference cannot be attributed solely to the stop.

Frozen uncertainty method: calendar-week moving-block bootstrap, 1- and 4-week blocks, 10,000 draws with seed 20261006 + block length; all three tokens sampled together, including empty weeks. Report intervals and leave-one-token-out stressed means. These intervals are conditional descriptive uncertainty and do not correct for prior hypothesis selection or all prior experiments.

Keep the original broader-token qualification false/not assessed as replication: zero new tokens, requirement eight. Also report each applicable numeric support and expectancy check explicitly. A positive cell or interval is insufficient to establish a known edge on these reused data.

Use original trade-level cost conventions. Cumulative trade-return units and entry-order drawdown are not account returns or portfolio drawdown. No new capital, margin, liquidation or leverage simulation. No production modifications or orders.

Validate all six data hashes, nine feature hashes, complete pre-2026 minute grids, finite price/funding fields, causal membership and entry alignment, reference reconciliation, cost identity, partition bounds, shared occupancy and ledger/summary counts. Preserve source, inputs manifest, signals, all opportunities, accepted/rejected ledgers, plain CSV exports and a reproducible private checkpoint; publish protocol/findings/aggregates only.
