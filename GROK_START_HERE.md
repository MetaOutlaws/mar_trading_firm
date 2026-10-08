# Grok: fill-price research audit and current paper rule,8 October2026

## Latest completed: sampled-exit audit, 8 October 2026

H-EXIT-POLLING-01 is complete. One-minute quote polling (the prespecified primary
test),five-minute and15-minute scenarios retain positive pooled means in all
three periods at base and doubled-slippage costs. One-minute sampling converts
three former target winners to stops. Historical profit margin remains thin.
No polling-speed,approval,entry,SL/TP or production configuration changed.

The table shows mean NET trade return / stop count with fees,funding and doubled
slippage. All arms use immediate entries and SL2%/TP2.5% from the slipped fill.
Actual sampled exit quotes can be beyond either threshold. Same65 admitted
signals throughout; targets equal trades minus stops. These are exit-polling
intervals, NOT the previous experiment's entry delays.

| Exit model | 2022–24: mean / stops (41 trades) | 2025: mean / stops (15 trades) | 2026: mean / stops (9 trades) |
|---|---:|---:|---:|
| Intrabar benchmark | +0.0702% / 20 | +1.0412% / 4 | +1.7240% / 1 |
| Every1 minute(s) | +0.0681% / 21 | +0.8269% / 5 | +1.3193% / 2 |
| Every5 minute(s) | +0.2586% / 19 | +1.1222% / 4 | +1.4312% / 2 |
| Every15 minute(s) | +0.3724% / 18 | +1.0849% / 4 | +1.3560% / 2 |

Primary1-minute effect:one target-to-stop conversion in EACH period. Across65
trades,25 benchmark stops become28 sampled stops,40 targets become37. No stop
becomes a target in this primary stressed comparison. No new/displaced admissions,
boundary marks or same-minute ambiguities occur. Every sampled stop fills beyond
its nominal2% quote-loss threshold. Worst net stopped loss across periods:
intrabar−2.3271%,1-minute−2.7864%,5-minute−2.9668%,15-minute−3.3014%. A nominal2%
trigger is not a2% realized loss cap when the price is only observed periodically.

All sampled-arm four-week95% mean intervals include zero. Primary intervals:
2022–24 −0.7325% to+0.7697%;2025 −0.3857% to+1.8653%;2026 −0.3295% to+2.4175%.
The point screen passes; independent edge, statistical equivalence, future
certainty and full production execution parity remain unestablished. These are
previously examined periods, not fresh holdouts. No deliberate slower-polling
rule should be inferred from higher averages in selected cells.

Coarser polling sometimes skips stops that later recover, and can capture prices
beyond the target. It can also miss target touches and close later at a loss.
The historical ETH winner entered2023-09-30 14:00 UTC exits at a sampled quote
2.7198 percentage points beyond its2.5% target (net+4.9922%). Such overshoot helps
offset other deterioration; it is not a guaranteed improvement in execution.
Both favorable and adverse overshoot are fully retained in the evidence.

Runtime finding clarified:sampled paper stops, as well as OHLC-resolved stops,
omit the extra adverse exit-slippage tick. This experiment deliberately retains
the original research charge on every exit in every arm to isolate sampling.
Reconciling that convention is the next separate comparison. Targets may be
requoted by the runtime; that extra request latency is not simulated.

Sampling uses observed minute OPEN quotes on fixed global UTC1/5/15-minute
grids, strictly after entry. Funding ends at the known sampled timestamp;
intrabar exits retain their conservative within-minute funding bound. The
15-second runtime waiting-loop constant cannot be reconstructed from minute
candles, and does not prove continuous coverage while workers/scans execute.
These scenarios are neither measured cloud delays nor guaranteed bounds on
actual15-second fills. No candles were interpolated and no missed touch was queued.

Protocol commit a058b599b4b7473260bf90466be231487c327c9a preceded outcomes, with10
exact file readbacks.47 tests passed. preflight_v1 exactly reproduced138 raw and
130 admitted benchmark cost rows. results_v1 is the single treatment run:
552 independent paths/cost rows,24 independent admissions,18 attribution checks;
independent reporting rebuilt592 rows and156 bootstrap intervals.520 trade rows
represent65 signals x4 exit models x2 costs. No failed treatment or retuning.

APPROVED PAPER strategy remains hourly_compression_btc_connors_loweff_v1,
BTC/ETH/SOL LONG+SHORT,1h,SL2%/TP2.5%,no timeout. Keep its existing settings.
Immediate entry with fill-origin brackets remains the research benchmark;
polling scenarios quantify a remaining execution sensitivity, not an approved
strategy replacement. Paper activation/health was not checked in this research run.

NEXT: reconcile the stop-exit cost convention on frozen paths, separately from
sampling or entry delay. Then return to winner/loser diagnostics under the
reconciled execution model before proposing new entry/risk filters. Actual
15-second reliability needs quote/cycle/worker timestamps;minute OHLC cannot
supply it. H-HOURLY-EXPANSION-01 remains frozen,with no new-token results opened.

Read hourly_exit_polling_20261008/FINDINGS.md and PROTOCOL.md in research PR99.
Newest cumulative archive:MAR_exit_polling_checkpoint_20261008.zip,restored over
MAR_hourly_compression_checkpoint_20261007.zip. It carries all earlier increments,
code,ledgers,attempt logs and the runtime snapshot;raw inputs remain separately
saved. Earlier status sections below are historical and do not override this one.

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
