# H-ENTRY-LATENCY-01 findings

## Latest completed: entry-latency audit, 8 October 2026

H-ENTRY-LATENCY-01 is complete. Immediate,1-,5- and15-minute entries all have
positive pooled means in every period under base and doubled-slippage costs.
The prespecified primary5-minute point screen passes. Recent-period results
weaken materially; this does not establish that deliberate delay improves entry.
No strategy, scanner cadence, approval or production setting changed.

Average NET trade return and stop counts below include fees,funding and doubled
slippage. SL2%,TP2.5% are anchored to each actual fill. All65 original admitted
signals remain admitted in every arm/cost; targets equal trades minus stops.

| Delay | 2022–24: mean / stops (41 trades) | 2025: mean / stops (15 trades) | 2026: mean / stops (9 trades) |
|---|---:|---:|---:|
| 0 minutes | +0.0702% / 20 | +1.0412% / 4 | +1.7240% / 1 |
| 1 minutes | +0.1819% / 19 | +0.4416% / 6 | +1.2216% / 2 |
| 5 minutes | +0.2947% / 18 | +0.4414% / 6 | +1.2216% / 2 |
| 15 minutes | +0.4024% / 17 | +0.7408% / 5 | +1.2216% / 2 |

For the primary5-minute comparison: historical3 stops become targets and1 target
becomes a stop;2025 has2 target-to-stop conversions;2026 has1. Across65 trades,
25 baseline stops become26 delayed stops (40 targets become39). There are no new
or displaced admissions, endpoint exclusions, boundary marks or ambiguous bars.
No admitted baseline trade exited within the waiting window. Improvements and
losses arise from later entry prices moving the fill-based brackets and changing
subsequent paths, not from cancelling failed signals while waiting.

All delayed-arm95% four-week mean intervals include zero. Five-minute intervals:
2022–24 −0.4321% to+0.9420%;2025 −0.9603% to+1.6303%;2026 −0.3559% to+2.2293%.
The same small, already examined dataset is being reused. This is execution
sensitivity, not independent confirmation, future certainty or leverage evidence.
Do not select15 minutes because its pooled mean looks better than5 minutes.

Runtime inspection: signals expire more than15 minutes after hourly close;
exactly15 minutes has no evaluation-to-order processing margin. The runner's
default900-second wait follows scan/worker execution, so elapsed cycle time can
exceed15 minutes. The15-second exit polling constant applies within its waiting
loop, not a proven continuous background service. Actual deployed cadence and
latency distribution require timestamped logs. These fixed delays are scenarios,
not observed production fills; missed windows/retries are not simulated.

Protocol and code published BEFORE treatment outcomes in commit
4d1792891682b7570ee1c3a799defb988b1df72a.40 tests passed. Zero-delay preflight
exactly reproduces138 opportunity and130 admitted cost rows from the fill audit.
Full run verifies552 minute paths and cost rows,24 independent admissions and18
attribution identities. Independent reporting rebuilt576 table rows and156
bootstrap intervals.520 ledger rows represent65 trades x4 delays x2 costs,
not520 independent trades. Failed preflight_v1 stopped before scoring on an
incomplete local BTC extraction; the verified original archive restored exact
bytes. preflight_v2 passed. results_v1 is the only treatment run.

APPROVED PAPER rule remains hourly_compression_btc_connors_loweff_v1 for
BTC/ETH/SOL,LONG+SHORT,1h,SL2%/TP2.5%,no timeout. No deliberate-delay rule has been
approved or installed. Immediate fill-origin results remain the benchmark;
the delayed arms are execution sensitivity references. Historical ETH remains
negative at5 minutes;2025 BTC also becomes negative. These are descriptive
small cells, not new exclusion rules. See subgroups.csv for all cells.

NEXT: isolate sampled exit supervision against the immediate fill-origin benchmark,
keeping entries and initial SL/TP fixed. Available1-minute OHLC can support labelled
minute-resolution proxies; it cannot reconstruct15-second polling fills. Audit
observed scanner/worker timing separately when logs are available. Keep the
runtime OHLC stop-exit slippage convention as a separate comparison, not bundled
into polling. Then inspect winners/losers under the realistic execution model
before selecting new entry or risk changes. The H-HOURLY-EXPANSION-01 protocol
remains frozen; no new-token data or outcomes were opened in this experiment.

Read hourly_entry_latency_20261008/FINDINGS.md and PROTOCOL.md in research PR99.
Restore original MAR_hourly_compression_checkpoint_20261007.zip followed by
MAR_entry_latency_checkpoint_20261008.zip. The latest increment includes all
earlier increments, code, ledgers, attempted runs and runtime snapshot. Raw data
remain in their separately saved original archive. No background monitor started.
Earlier status sections below are historical and do not override this update.

## Complete cost comparison

| Period | Delay minutes | Costs | Trades | Stops | Targets | Mean net | Four-week95% interval |
|---|---:|---|---:|---:|---:|---:|---|
| 2022–24 | 0 | Base | 41 | 18 | 23 | +0.3529% | -0.3315% to +0.9607% |
| 2022–24 | 0 | Doubled slippage | 41 | 20 | 21 | +0.0702% | -0.6258% to +0.6902% |
| 2025 | 0 | Base | 15 | 3 | 12 | +1.4097% | +0.3875% to +2.3048% |
| 2025 | 0 | Doubled slippage | 15 | 4 | 11 | +1.0412% | +0.1309% to +1.8958% |
| 2026 Jan–2 Oct | 0 | Base | 9 | 1 | 8 | +1.8015% | +0.0484% to +2.3103% |
| 2026 Jan–2 Oct | 0 | Doubled slippage | 9 | 1 | 8 | +1.7240% | -0.0125% to +2.2352% |
| 2022–24 | 1 | Base | 41 | 19 | 22 | +0.2444% | -0.5022% to +0.9040% |
| 2022–24 | 1 | Doubled slippage | 41 | 19 | 22 | +0.1819% | -0.5647% to +0.8421% |
| 2025 | 1 | Base | 15 | 6 | 9 | +0.5128% | -0.5046% to +1.4610% |
| 2025 | 1 | Doubled slippage | 15 | 6 | 9 | +0.4416% | -0.5772% to +1.3902% |
| 2026 Jan–2 Oct | 1 | Base | 9 | 2 | 7 | +1.2989% | -0.2848% to +2.3088% |
| 2026 Jan–2 Oct | 1 | Doubled slippage | 9 | 2 | 7 | +1.2216% | -0.3560% to +2.2293% |
| 2022–24 | 5 | Base | 41 | 17 | 24 | +0.4647% | -0.2861% to +1.1490% |
| 2022–24 | 5 | Doubled slippage | 41 | 18 | 23 | +0.2947% | -0.4321% to +0.9420% |
| 2025 | 5 | Base | 15 | 5 | 10 | +0.8118% | -0.3376% to +1.8104% |
| 2025 | 5 | Doubled slippage | 15 | 6 | 9 | +0.4414% | -0.9603% to +1.6303% |
| 2026 Jan–2 Oct | 5 | Base | 9 | 2 | 7 | +1.2989% | -0.2848% to +2.3088% |
| 2026 Jan–2 Oct | 5 | Doubled slippage | 9 | 2 | 7 | +1.2216% | -0.3559% to +2.2293% |
| 2022–24 | 15 | Base | 41 | 17 | 24 | +0.4631% | -0.2884% to +1.1470% |
| 2022–24 | 15 | Doubled slippage | 41 | 17 | 24 | +0.4024% | -0.3494% to +1.0880% |
| 2025 | 15 | Base | 15 | 5 | 10 | +0.8120% | -0.2850% to +1.8733% |
| 2025 | 15 | Doubled slippage | 15 | 5 | 10 | +0.7408% | -0.3550% to +1.8016% |
| 2026 Jan–2 Oct | 15 | Base | 9 | 2 | 7 | +1.2989% | -0.2847% to +2.3088% |
| 2026 Jan–2 Oct | 15 | Doubled slippage | 9 | 2 | 7 | +1.2216% | -0.3559% to +2.2293% |

## Primary5-minute paired differences

| Period | Change in mean (percentage points) | Four-week95% interval (percentage points) |
|---|---:|---|
| 2025 | -0.5998 | -1.5003 to +0.0008 |
| 2022–24 | +0.2245 | -0.2054 to +0.6743 |
| 2026 Jan–2 Oct | -0.5024 | -1.5071 to +0.0000 |

## Changed primary stressed exit categories

| Signal UTC | Token | Side | Immediate | Five minutes |
|---|---|---|---|---|
| 2023-11-24 08:00:00+00:00 | ETHUSDT | LONG | stop | target |
| 2024-03-08 15:00:00+00:00 | BTCUSDT | LONG | target | stop |
| 2024-05-23 11:00:00+00:00 | SOLUSDT | SHORT | stop | target |
| 2024-12-08 09:00:00+00:00 | ETHUSDT | SHORT | stop | target |
| 2025-01-22 14:00:00+00:00 | BTCUSDT | SHORT | target | stop |
| 2025-10-05 03:00:00+00:00 | SOLUSDT | LONG | target | stop |
| 2026-09-05 17:00:00+00:00 | ETHUSDT | LONG | target | stop |

The sole2026 ETH trade changes from target to stop, illustrating how one trade
can move a nine-trade period mean. Five-minute historical token means:BTC+0.4983%
(15 trades),ETH−0.0886%(17),SOL+0.6796%(9).2025 BTC−0.2852%(7),ETH+2.2659%(2),
SOL+0.6809%(6).2026 BTC+0.7700%(3),ETH−2.2513%(1),SOL+2.1871%(5).
Neither calendar year nor this outcome table supplies an entry-time regime label.

Data definitions:returns are fractions (0.01=1%);side1 LONG/-1 SHORT;stress1 base,
2 doubled slippage. signal_i/signal_time identify the original completed-hour
signal; entry_i/entry identify actual execution. Pair by original signal plus
token,side,period,cost. Do not count scenarios as independent observations.
entry_quote_move is side*(delayed open/original open−1),positive means a worse
entry. Its mean need not predict outcome: small price changes can switch barrier
order. No path information enters an admission feature or cancellation rule.

Fees .055% each side;slippage .05% BTC/ETH,.10% SOL each side at base,doubled in
stress. Research exit slippage remains charged on stops as well as targets,
unlike the separate runtime OHLC-resolved stop convention. Funding remains the
same conservative minute-boundary calculation. Targets/stops resolve intraminute;
sampled quote exits,spread evolution,actual order delay,other strategies' occupancy,
missed scan windows and leverage are outside this experiment.

Counterfactual original-admission and executable replay views happen to agree
because identities do not change here. Code retains both views and reports
their differences when occupancy changes. Additive PnL sums are attribution
diagnostics, not compounded portfolio returns. Bootstrap intervals use paired
calendar weeks at original signal time and retain zero-trade weeks; they are
descriptive after repeated research, not multiple-testing-corrected validation.
