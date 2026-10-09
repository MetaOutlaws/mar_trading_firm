# H-2026-REPLICATION-01 findings

## Latest completed: fixed-strategy 2026 replication, 8 October 2026

H-2026-REPLICATION-01 is complete. The approved PAPER rule remains
`hourly_compression_btc_connors_loweff_v1`: hourly compression + BTC confirmation
+ Connors + a one-ATR extension cap only when prior ER24<0.30; BTC/ETH/SOL,
LONG+SHORT, SL2%, TP2.5%, no timeout. No runtime/approval change was made.

**Positive point replication:** 9 trades, 8 targets, 1 stop-out (11.11%), 88.89%
closed win rate. Mean net return is +1.7240% at base costs and +1.5689% at doubled
slippage. No boundary marks, ambiguous exits or admission rejections. Nine trades
across seven entry dates/seven calendar weeks; 18 exported rows are the SAME nine
trades under two cost assumptions, not 18 independent observations.

| Period | Trades | Stops | Targets | Win rate | Stressed mean net/trade |
|---|---:|---:|---:|---:|---:|
| 2022–24 | 41 | 15 | 26 | 63.41% | +0.5003% |
| 2025 | 15 | 3 | 12 | 80.00% | +1.1993% |
| 2026 reserved interval | 9 | 1 | 8 | 88.89% | +1.5689% |

Interval: 1 January 2026 00:00 UTC through 2 October 2026 16:00 UTC exclusive.
Last eight candle hours omitted based on funding coverage before scoring. No
carry-in positions; pre-2026 data used only as causal warm-up for this replay.

This is a **temporal replication, not an untouched holdout**: original PR92 exposed
full-span future-path opportunity summaries including 2026, and external Grok use
is unknown. The current sequence had no saved 2026 strategy trades before this
run. Raw funding provenance remains provisional; it matches the approved sequence.

Stressed 95% bootstrap intervals for the mean: one-week blocks +0.2505% to +2.0922%;
four-week blocks -0.1300% to +2.0857%. The latter includes zero.
Both point means are positive; the predeclared stronger interval check does not
pass. This supports continued paper evaluation, not certainty or leverage readiness.

Protocol-before-scoring commit `988bb74b17854704c7fc4094f5577619d017726c`.
Historical preflight reproduced all120 approved opportunity cost rows and112
admitted cost rows (56 trades). New run verified30 independent entry contexts,
six runtime signal frames/39,552 hour-side decisions,30 trailing850-hour decisions,
all9 minute barrier paths,18 independent cost calculations and two admissions.
Four bootstrap intervals were independently reconstructed. One successful 2026
run, results_v1; initial historical-only adapter failure is preserved separately.

NEXT: verify actual paper installation/scanning and compare subsequent signal/fill
logs with the frozen rule; collect forward observations without tuning on them.
Use the preregistered broader-token replication when additional data arrive.
2026 has now been opened: any further optimisation on it is exploratory. No new
filter sweep, live/leverage change or background monitor was started. Cloud
activation is still unverified here; GitHub publication is not operational proof.

Read hourly_reserved_2026_20261008/FINDINGS.md and PROTOCOL.md in PR99. Restore the
original hourly base then MAR_2026_replication_checkpoint_20261008.zip; this increment
includes preceding increments. Older notes below describe historical work and do
not override this current status.

## Token detail, doubled slippage

| Token | Trades | Stops | Targets | Mean net/trade |
|---|---:|---:|---:|---:|
| BTCUSDT | 3 | 1 | 2 | +0.6708% |
| ETHUSDT | 1 | 0 | 1 | +2.1679% |
| SOLUSDT | 5 | 0 | 5 | +1.9880% |

SOL supplies five of nine trades and about70.4% of positive token net-return sums;
ETH has only one observation. Removing each token from the admitted ledger keeps
the remaining stressed mean positive; this is descriptive, without replacement.
LONG:5 trades/1 stop/4 targets, +1.1906% mean. SHORT:4 trades/0 stops/4 targets,
+2.0418% mean. Do not interpret tiny token/side cells as selection rules.

The sole stop is BTC LONG, entry2026-07-10 02:00 UTC, exit2026-07-13 05:00 UTC,
stressed net−2.3663%, about75.02h held. This documents the loss; no recovery or
exit optimisation was run. Median hold16.22h; longest75.02h. Stressed profit
factor6.97 is a nine-trade estimate. Net percentages are per-trade returns under
the research model; their additive sum is not a compounded account return.

Thirty original compression entry contexts were examined causally; nine passed
all approved filters. Only those nine were scored. No 2026 counterfactual arms,
RSI policies or alternate stops were calculated, and no winners-sacrificed contrast
is claimed. Historical and2025 positive outcomes remain intact but are selected
or reused evidence. No year was labelled categorically trending/choppy here.

Saved CSVs contain base stress=1 and doubled-slippage stress=2; values are fractions
(0.015689 means1.5689%), side1 LONG/-1 SHORT, timestamps UTC. Entry contexts are
known at entry; exit/path/cost columns are later outcomes and cannot be predictors.
Production sampled quotes, fill-relative brackets and shared-account occupancy
differ from the research simulator; entry parity is not realised-PnL parity.
