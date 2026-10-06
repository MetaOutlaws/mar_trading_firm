# Standalone breakout/retest findings — 6 October 2026

**Decision: no configuration qualifies. Zero of 36 breakout/retest configurations passes the frozen two-period screen. Every retest configuration has negative mean net return in 2022–2024.** No parameter was retuned after scoring.

## What was tested

BTC, ETH and SOL; 5m, 15m and 1h entries; long and short. The completed 4h EMA regime supplies context. A breakout closes beyond the previous 20 entry-clock candles, then a later candle must retest and reject a frozen +/-0.25 ATR band within six candles. Entry is the next minute open. See PROTOCOL.md for cancellation, expiry and execution rules.

Two fixed arms: 2% stop / 2.5% target and 3% stop / 3% target. Fees, symbol-specific slippage, funding, regime exits, position occupancy, gaps and conservative stop-first intrabar ordering are retained. Doubled-slippage stress is also reported. There is no maximum holding period. Discovery is 2022–24; “validation” in the CSV means reused historical 2025 evaluation, not fresh confirmation. No 2026 observations were scored.

## Retest results, pooled descriptive view

| Period | SL / TP | Positions | Stop-outs | Mean net/trade | Win rate | PF |
| --- | --- | --- | --- | --- | --- | --- |
| discovery | 2% / 2.5% | 5,150 | 2,718 (52.8%) | -0.260% | 43.5% | 0.788 |
| validation | 2% / 2.5% | 1,857 | 960 (51.7%) | -0.224% | 43.8% | 0.814 |
| discovery | 3% / 3.0% | 4,112 | 1,822 (44.4%) | -0.280% | 47.5% | 0.822 |
| validation | 3% / 3.0% | 1,474 | 634 (43.0%) | -0.203% | 48.4% | 0.867 |

Means include retained end-of-partition marks; stop and win rates use completed trades. Discovery contains three boundary marks in the 2% arm and four in the 3% arm. No 2025 retest positions are boundary marks. These are trade-weighted summaries of overlapping independent research configurations, not a combined portfolio or independent samples. Returns are percentages; PF is gross positive net returns divided by the absolute sum of negative net returns.

The wider arm lowered the 2025 stop-out rate from 51.7% to 43.0% and raised win rate from 43.8% to 48.4%, but net return stayed negative. Both stop AND target changed, along with holding times and subsequent position occupancy. This does not prove that widening the stop rescued the same trades or identify an optimal stop.

## Like-for-like entry comparisons

| Entry | SL / TP | 2022–24 mean net | 2025 mean net |
| --- | --- | --- | --- |
| breakout_retest | 2% / 2.5% | -0.260% | -0.224% |
| breakout_retest | 3% / 3.0% | -0.280% | -0.203% |
| immediate_parent_breakout | 2% / 2.5% | -0.273% | -0.205% |
| immediate_parent_breakout | 3% / 3.0% | -0.264% | -0.219% |
| ema20 | 2% / 2.5% | -0.287% | -0.273% |
| ema20 | 3% / 3.0% | -0.319% | -0.269% |
| zone_rejection | 2% / 2.5% | -0.311% | -0.394% |
| zone_rejection | 3% / 3.0% | -0.298% | -0.387% |

Retest beats EMA and zone in these pooled means but does not consistently beat immediate breakout. In 2025 it trails immediate breakout by 0.0197 percentage points per trade with 2%/2.5%, and leads by 0.0161 points with 3%/3%; both policies remain negative. The same parent setups generate immediate-breakout and retest candidates, but confirmation and busy-position rejection lead to different executed trades. These are policy contrasts, not paired causal effects. `results_v1/contrasts.csv` gives all 432 cell/period/cost comparisons; use identical token, clock, side and SL/TP when comparing.

## Gate and positive exceptions

The frozen screen requires at least 50 completed trades in each period, positive base-cost mean and PF >=1.15 in both periods, and positive mean under doubled slippage in both periods. No retest cell even has a positive discovery mean. The three controls also have zero passing configurations under this same screen.

Five of 18 retest cells per arm have positive 2025 base-cost means. Examples include ETH 1h long (2%/2.5%: +0.559%, 34 trades) and BTC 1h long (3%/3%: +0.412%, 21 trades). Both have small 2025 samples and negative discovery results. ETH 15m long with 2%/2.5% has 82 trades and PF 1.167 in 2025 but negative discovery mean. These are disclosed exceptions, not selected strategies.

## Full 2025 retest breakdown

| Token | Clock | Direction | SL / TP | Trades | Stops | Net/trade | PF |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BTCUSDT | 5m | LONG | 2% / 2.5% | 66 | 23 (34.8%) | 0.118% | 1.125 |
| BTCUSDT | 5m | LONG | 3% / 3.0% | 46 | 13 (28.3%) | 0.138% | 1.117 |
| BTCUSDT | 5m | SHORT | 2% / 2.5% | 124 | 60 (48.4%) | -0.225% | 0.805 |
| BTCUSDT | 5m | SHORT | 3% / 3.0% | 96 | 35 (36.5%) | -0.346% | 0.767 |
| BTCUSDT | 15m | LONG | 2% / 2.5% | 43 | 17 (39.5%) | -0.086% | 0.921 |
| BTCUSDT | 15m | LONG | 3% / 3.0% | 34 | 11 (32.4%) | -0.031% | 0.976 |
| BTCUSDT | 15m | SHORT | 2% / 2.5% | 83 | 43 (51.8%) | -0.249% | 0.796 |
| BTCUSDT | 15m | SHORT | 3% / 3.0% | 62 | 22 (35.5%) | -0.209% | 0.859 |
| BTCUSDT | 60m | LONG | 2% / 2.5% | 24 | 10 (41.7%) | 0.102% | 1.099 |
| BTCUSDT | 60m | LONG | 3% / 3.0% | 21 | 5 (23.8%) | 0.411% | 1.353 |
| BTCUSDT | 60m | SHORT | 2% / 2.5% | 35 | 15 (42.9%) | 0.177% | 1.176 |
| BTCUSDT | 60m | SHORT | 3% / 3.0% | 31 | 11 (35.5%) | -0.015% | 0.989 |
| ETHUSDT | 5m | LONG | 2% / 2.5% | 157 | 84 (53.5%) | -0.266% | 0.781 |
| ETHUSDT | 5m | LONG | 3% / 3.0% | 110 | 44 (40.0%) | -0.106% | 0.927 |
| ETHUSDT | 5m | SHORT | 2% / 2.5% | 247 | 122 (49.4%) | -0.090% | 0.920 |
| ETHUSDT | 5m | SHORT | 3% / 3.0% | 179 | 79 (44.1%) | -0.147% | 0.902 |
| ETHUSDT | 15m | LONG | 2% / 2.5% | 82 | 37 (45.1%) | 0.170% | 1.167 |
| ETHUSDT | 15m | LONG | 3% / 3.0% | 68 | 29 (42.6%) | 0.009% | 1.006 |
| ETHUSDT | 15m | SHORT | 2% / 2.5% | 119 | 66 (55.5%) | -0.273% | 0.781 |
| ETHUSDT | 15m | SHORT | 3% / 3.0% | 102 | 47 (46.1%) | -0.153% | 0.900 |
| ETHUSDT | 60m | LONG | 2% / 2.5% | 34 | 13 (38.2%) | 0.559% | 1.661 |
| ETHUSDT | 60m | LONG | 3% / 3.0% | 33 | 13 (39.4%) | 0.412% | 1.324 |
| ETHUSDT | 60m | SHORT | 2% / 2.5% | 47 | 31 (66.0%) | -0.679% | 0.535 |
| ETHUSDT | 60m | SHORT | 3% / 3.0% | 46 | 28 (60.9%) | -0.860% | 0.560 |
| SOLUSDT | 5m | LONG | 2% / 2.5% | 188 | 94 (50.0%) | -0.214% | 0.820 |
| SOLUSDT | 5m | LONG | 3% / 3.0% | 142 | 56 (39.4%) | -0.049% | 0.965 |
| SOLUSDT | 5m | SHORT | 2% / 2.5% | 267 | 145 (54.3%) | -0.302% | 0.762 |
| SOLUSDT | 5m | SHORT | 3% / 3.0% | 208 | 97 (46.6%) | -0.342% | 0.790 |
| SOLUSDT | 15m | LONG | 2% / 2.5% | 100 | 56 (56.0%) | -0.411% | 0.690 |
| SOLUSDT | 15m | LONG | 3% / 3.0% | 81 | 44 (54.3%) | -0.735% | 0.604 |
| SOLUSDT | 15m | SHORT | 2% / 2.5% | 137 | 82 (59.9%) | -0.526% | 0.622 |
| SOLUSDT | 15m | SHORT | 3% / 3.0% | 117 | 57 (48.7%) | -0.350% | 0.790 |
| SOLUSDT | 60m | LONG | 2% / 2.5% | 50 | 27 (54.0%) | -0.246% | 0.803 |
| SOLUSDT | 60m | LONG | 3% / 3.0% | 46 | 17 (37.0%) | 0.239% | 1.180 |
| SOLUSDT | 60m | SHORT | 2% / 2.5% | 54 | 35 (64.8%) | -0.729% | 0.514 |
| SOLUSDT | 60m | SHORT | 3% / 3.0% | 52 | 26 (50.0%) | -0.391% | 0.768 |

## Evidence and interpretation

- 576 chronological result rows: 4 entry families x 18 token/clock/direction groups x 2 arms x 2 periods x 2 cost levels.
- 140,120 ledger rows include both cost scenarios; the second scenario reprices the same executions and is not another independent set of trades.
- 144 control reconciliation checks passed: all selected zone reference rows and EMA 2%/2.5% reference rows. Maximum mean-return discrepancy: 9.97e-17. The zone reference is reconstructed; original row identity remains unproven.
- Four focused setup-state tests passed, covering confirmation timing, frozen levels, symmetry, expiry, price/regime cancellation and future-prefix independence.
- Report generation verified 16 frozen output hashes and reconciled all 576 summary rows with individual trades, stops, boundary marks and non-overlapping execution within each configuration.
- Protocol freeze commit: `536abb5`; runner freeze commit: `81dce86`. Input and source hashes are in the run manifest. Source, setups, full ledgers and prior evidence are in the private research checkpoint. Public GitHub contains written findings, protocols and aggregates.

This fixed breakout/retest definition did not establish an edge. A lower stop-out rate or higher win rate alone is insufficient when average net return remains negative. Close this variant without another threshold grid. The outstanding matched costed-opportunity diagnostic can complete the zone audit; any subsequent entry hypothesis needs its own frozen rationale and a genuinely unused confirmation sample. Profit protection remains a separate queued experiment, not a result of this run.
