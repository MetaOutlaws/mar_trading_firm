# MAR current research status,8 October2026

## Latest completed: fill-price SL/TP audit, 8 October 2026

H-FILL-BRACKETS-01 is complete. Applying the approved2% stop/2.5% target to the
slipped fill changes outcomes materially. All three period means remain positive
at both costs, but historical stressed expectancy is thin. Paper already uses
fill-based levels; no runtime,approval,entry,stop/target percentage or mode changed.
Use the fill-origin results as the execution-aligned research reference going
forward. Preserve the earlier quote-origin results as their original model outputs.

| Period | Trades | Quote-origin net/trade | Fill-origin net/trade | Stops, old → new | Fill targets | Fill win rate |
|---|---:|---:|---:|---:|---:|---:|
| 2022–24 | 41 | +0.5003% | +0.0702% | 15 → 20 | 21 | 51.22% |
| 2025 | 15 | +1.1993% | +1.0412% | 3 → 4 | 11 | 73.33% |
| 2026 Jan–2 Oct | 9 | +1.5689% | +1.7240% | 1 → 1 | 8 | 88.89% |

Table uses doubled slippage,fees and funding. Five historical target winners and
one2025 target winner become stops. No stop becomes a target;2026 exit categories
are unchanged. No new or displaced admissions: the SAME65 trades are admitted in
both arms and both costs.260 ledger rows are overlapping scenario observations.
At base costs,three historical winners become stops and2025/2026 categories hold.

Historical ETH turns negative:17 trades,11 stops,mean−0.6246% stressed. BTC remains
+0.7929% over15 trades;SOL +0.1783% over9. Do not exclude ETH after observing this
result or retune entries to recover the old average. Historical pooled stressed
mean is+0.0702%,95% four-week interval−0.6258% to+0.6902%. The historical incremental
mean difference is−0.4301 percentage points; its four-week interval is−0.8978 to
−0.0207 percentage points. Bootstrap intervals condition on already examined data
and cannot establish future certainty or remove strategy-selection bias.

2025 fill-origin stressed mean+1.0412%,4 stops/15 trades;2026 +1.7240%,1 stop/9.
2026 had already been opened: this is execution sensitivity,not fresh validation.
The frozen positive-point robustness screen passes. Statistical equivalence,
full production parity and an independently established edge are NOT established.

Only bracket origin changed. Conservative research exit slippage on stops was
retained,although the runtime OHLC execution contract omits that second stop
slippage. Quote polling,actual spreads/fills,other strategies and live account
occupancy also remain distinct. No leverage/live change or cloud activation claim.

Protocol-before-scoring commit3b29ac2da5f20ff9e6b2850148a26958ef4c3a57.25 focused
tests passed;quote preflight reproduces138 raw and130 admitted cost rows. Full run:
276 independently checked minute paths,cost rows and runtime risk-level pairs;
12 independent admission replays;6 attribution reconciliations. All report tables
and48 bootstrap intervals were independently reconstructed. One successful run,
results_v1. Existing frozen research records remain unchanged.

ALSO FROZEN before any new-token outcomes: H-HOURLY-EXPANSION-01 in
hourly_expanded_replication_20261008/PROTOCOL.md. It adds this exact approved
hourly combination as a separate candidate beside the original6October all-clock
protocol. New-token primary uses fill-based brackets chosen BEFORE this audit's
outcomes;quote-origin comparison is diagnostic. Same pre-entry universe/liquidity
rules,strict BTC confirmation for each new token,conservative costs and provenance
gates. Both original95% and joint97.5% intervals are required as specified. No
new-token data or outcomes were inspected;the expanded runner is not yet implemented.

NEXT: separately audit scanner latency and sampled exit supervision against the
fill-origin benchmark,using actual cadence/log evidence where available and
clearly labelled minute-data proxies otherwise. Record the stop-exit slippage
convention separately. Then inspect winners and losses under this execution model
before proposing risk changes; the earlier19-stop/46-target count belongs to the
quote model. Current stressed fill model has25 stops/40 targets across65 trades.
Additional-token scoring follows its frozen protocol when audited data arrive.
No further experiment or background monitor has started in this turn.

See hourly_fill_brackets_20261008/FINDINGS.md,PROTOCOL.md and results_v1 in PR99.
Restore original MAR_hourly_compression_checkpoint_20261007.zip then
MAR_fill_brackets_checkpoint_20261008.zip;it includes all preceding increments.
Earlier sections below are historical and do not override this current status.
