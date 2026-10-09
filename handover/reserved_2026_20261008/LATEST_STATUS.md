# MAR current status, 8 October 2026

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
