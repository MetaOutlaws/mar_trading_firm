# RSI by market state adds no improvement to the approved strategy

Completed8October2026 Dubai. Keep the approved BTC + Connors + low-efficiency-only extension cap unchanged. The added standard RSI14 gate fails every prespecified incremental-benefit screen. Applied only in low-efficiency states, it changes no opportunities or trades. Applied always or only in directional states, it slightly lowers pooled2022–24 average net return and leaves2025 unchanged. This study creates no runtime/deployment change.

## Scope and frozen definitions

Benchmark: original hourly compression, own-token CRSI(3,2,100), matching BTC direction for ETH/SOL, and extension<=1 priorATR only when pre-signal ER24<0.30. BTC/ETH/SOL, both sides,1h,SL2%,TP2.5%,no timeout. The added RSI14 rule retains LONG at<=70 and SHORT at>=30. Four policies were declared before scoring: none, always, directional only, low-efficiency only. ER24 excludes the signal hour, cutoff0.30, using exactly the preceding experiment’s definition. The preexisting extension cap remains in every arm.

Protocol/code committed before scoring:7088e063ff876fd7b0c3b9d1c142433be698120c. No threshold search,2026 outcome or new token.143 original raw signals,60 approved raw opportunities (45 historical,15 evaluation), fresh occupancy replay. Same fees, actual funding, quote barriers, stop-first ties and adverse gaps. Stress doubles only slippage. The earlier RSI standalone comparison against original compression is retained as historical evidence and was not relabelled as this test.

## Full-basket comparison

| Period | Added RSI policy | Trades | Stops / rate | Targets | Win rate | Base mean net | Stressed mean net |
|---|---|---:|---:|---:|---:|---:|---:|
| 2022–24 | Approved benchmark | 41 | 15 / 36.59% | 26 | 63.41% | +0.6229% | +0.5003% |
| 2022–24 | RSI always | 38 | 14 / 36.84% | 24 | 63.16% | +0.6133% | +0.4914% |
| 2022–24 | RSI only directional | 38 | 14 / 36.84% | 24 | 63.16% | +0.6133% | +0.4914% |
| 2022–24 | RSI only low-efficiency | 41 | 15 / 36.59% | 26 | 63.41% | +0.6229% | +0.5003% |
| 2025 | Approved benchmark | 15 | 3 / 20.00% | 12 | 80.00% | +1.3400% | +1.1993% |
| 2025 | RSI always | 15 | 3 / 20.00% | 12 | 80.00% | +1.3400% | +1.1993% |
| 2025 | RSI only directional | 15 | 3 / 20.00% | 12 | 80.00% | +1.3400% | +1.1993% |
| 2025 | RSI only low-efficiency | 15 | 3 / 20.00% | 12 | 80.00% | +1.3400% | +1.1993% |

Means are per-trade notional returns after costs, not account returns. All exits are stops or targets.436 ledger rows overlap four policies and two cost scenarios; they are not436 independent trades.

## Stops avoided and winners lost

Always/directional RSI removes exactly three historical admitted trades: one ETH stop and two winners (ETH and SOL). There are no new or displaced admissions. Trade count41 to38, stops15 to14, targets26 to24. Win rate falls63.41% to63.16%. The removed bundle averages+0.6124% stressed, above the benchmark’s+0.5003%; removing it lowers mean to+0.4914%. Historical additive net sum falls0.205117 to0.186745, a0.018372-unit reduction. These sums are not compounded or funded account PnL.

| Token / side | Entry (UTC) | Outcome | Net stressed | Entry RSI14 | Prior ER24 | Extension ATR |
|---|---|---|---:|---:|---:|---:|
| ETHUSDT / SHORT | 2022-06-11 09:00:00+00:00 | target | +2.1961% | 16.05 | 0.543 | 4.061 |
| ETHUSDT / LONG | 2024-05-04 11:00:00+00:00 | stop | -2.3085% | 73.14 | 0.415 | 1.624 |
| SOLUSDT / LONG | 2024-07-26 14:00:00+00:00 | target | +1.9496% | 73.86 | 0.479 | 1.262 |

The original signal pool tells the same story with an important scope difference: always/directional RSI removes four approved raw historical opportunities (one stop,three targets). One of those targets was already blocked by occupancy, so only three actual benchmark trades disappear.2025 raw and admitted sets are unchanged for all policies.

Low-efficiency RSI excludes ZERO approved raw opportunities and ZERO admitted trades in either period. All33 historical and14 evaluation low-efficiency benchmark trades already satisfy RSI14. This is observed redundancy within the tested sample, not a universal theorem about these indicators. The directional benchmark cells contain only8 historical trades and1 evaluation trade.

## What the interaction teaches us

The original RSI standalone improvement does not survive as an incremental gain on the selected combination. Its exclusion set overlaps what our other filters already removed. Applying RSI in directional conditions excludes the same three trades that the approved conditional cap intentionally retains. As a post-result descriptive check, always/directional RSI yields the identical106 cost-scenario ledger rows as the earlier ALWAYS-ON extension-cap arm. This is a sample identity, not a newly optimized policy or claim of indicator equivalence.

Historical BTC is unchanged. ETH loses one stop and one target, so its mean rises slightly; SOL loses one target and its mean falls.2022 weakens,2023 is unchanged,2024 improves. These mixed subgroups do not justify a post-result token/year switch.2025 contains only15 total trades, including two ETH target winners.

| Token | Approved2022–24 trades / stops / stress mean | Always/directional RSI2022–24 trades / stops / stress mean |
|---|---|---|
| BTCUSDT | 15 / 5 / +0.6972% | 15 / 5 / +0.6972% |
| ETHUSDT | 17 / 8 / +0.0759% | 15 / 7 / +0.0935% |
| SOLUSDT | 9 / 2 / +0.9738% | 8 / 2 / +0.8518% |

## Uncertainty

Paired calendar bootstrap uses the same1week/4week blocks,10,000 draws and empty weeks. For always/directional RSI, the historical stressed mean difference is small and its confidence intervals cross zero. No statistical harm or improvement is established. Low-efficiency differences are identically zero because the trades are identical. All2025 differences are identically zero for the same reason.

| Period | Always/directional difference | 1-week95% interval (pp) | 4-week95% interval (pp) |
|---|---:|---:|---:|
| 2025 | +0.0000 pp | [+0.0000, +0.0000] | [+0.0000, +0.0000] |
| 2022–24 | -0.0089 pp | [-0.1762, +0.1914] | [-0.1630, +0.1805] |

Absolute intervals, subgroup/year/leave-one-token-out results and holding-time/cost metrics are retained in the supporting tables. Reused2025 is exploratory, not independent confirmation. Whole years are not assigned trend/chop labels.

## Decision and next step

Close H-RSI-REGIME-01 as NO INCREMENTAL BENEFIT on the current approved benchmark. Always/directional fail because historical mean falls; low-efficiency fails because neither period improves. Keep hourly_compression_btc_connors_loweff_v1 unchanged. No additional RSI14 gate or threshold tuning is approved or deployed. Cloud activation/scanning remains pending Grok’s operational verification; this offline experiment does not inspect or alter the VM.

The next priority is independent confirmation, not another filter on this shrinking historical sample. Before opening new outcomes, audit whether the reserved2026 BTC/ETH/SOL interval was used in earlier work, establish complete data coverage and freeze a separate validation protocol with the strategy/costs unchanged. Only genuinely unused periods can be described as independent. Broader-token validation remains queued until its data arrive. Continue collecting prospective paper trades after deployment is verified. No background monitor or follow-on experiment was started here.

## Verification and reproducibility

23 focused rule/causality/occupancy tests pass.143 RSI and143 prior-efficiency contexts independently reconstructed from minutes;286 cached raw cost rows match prior RSI evidence;120 approved opportunity cost rows and112 approved ledger rows match the preceding experiment.16 independent admissions and12 attribution reconciliations pass.28 summary/contrast rows match the per-trade ledger. Reused validated minute paths, no new path simulation. One successful attempt,results_v1; input/source/reference/output hashes and packages frozen. Ordinary CSVs and a restore-verified checkpoint are supplied.
