# Grok: fill-price research audit and current paper rule,8 October2026

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

Approved PAPER strategy remains hourly_compression_btc_connors_loweff_v1:
BTC/ETH/SOL,both sides,1h,SL2%/TP2.5%,no timeout. Original compression + Connors +
BTC confirmation + one-ATR extension cap only when pre-signal ER24<0.30.
No runtime or approval change. Actual installation/scanning is not verified here.

Latest H-FILL-BRACKETS-01 audit aligns research bracket origin with the slipped
entry fill already used by runtime. Stressed mean returns:2022–24 +0.0702%
(41 trades,20 stops,21 targets);2025 +1.0412%(15,4,11);2026 +1.7240%(9,1,8).
Old quote-origin means were+0.5003%,+1.1993%,+1.5689% respectively. Five historical
winners and one2025 winner become stops;no admission identities change. Historical
ETH is negative. Positive pooled point results remain,but historical margin is thin
and uncertainty/earlier selection prevent a certainty claim. No retuning followed.

Read [PR99](https://github.com/MetaOutlaws/mar_trading_firm/pull/99),
research/isolated_token_study_20261003/hourly_fill_brackets_20261008/FINDINGS.md
and PROTOCOL.md.25 tests,276 paths/cost/risk-level checks,12 admissions,6 attributions,
and48 independently reconstructed intervals pass.260 rows are65 overlapping trades
under two arms/two costs. Prior evidence is preserved.2026 is already examined.

New-token protocol is frozen in hourly_expanded_replication_20261008/PROTOCOL.md.
It adds this exact hourly candidate alongside the preserved original all-clock
study;primary fill-origin brackets were chosen before this audit's results.
No new-token data were inspected and no new-token runner has been implemented.
Freeze and verify acquisition coverage and scoring code before opening outcomes.

Next research: scanner latency and sampled exits,separately from the stop-exit
slippage convention. Use real operational evidence when available;minute-data
proxies do not establish full production parity. Winner/loss diagnosis should use
the fill-origin results (25 stops/40 targets),not only the old quote-based ledger.

Runtime [PR101](https://github.com/MetaOutlaws/mar_trading_firm/pull/101) and its
reviewed HOURLY_LOWEFF_APPROVAL.md remain the operational source. Publication is
not proof of scanning. No new symbol,live/leverage or duplicate strategy approval.
The complete operational instructions remain in the owner's private checkpoint.

Recovery:original MAR_hourly_compression_checkpoint_20261007.zip followed by
MAR_fill_brackets_checkpoint_20261008.zip;raw inputs separate. Current checkpoint
preserves all previous increments. No background test/monitor is running.
