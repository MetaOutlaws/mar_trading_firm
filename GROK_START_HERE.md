# Grok: fill-price research audit and current paper rule,8 October2026

## Latest completed: stop-cost reconciliation, 8 October 2026

H-STOP-COST-01 is complete. Research previously applied an extra adverse exit
slippage tick to every stop. The pinned paper execution contract and sampled
paper stop method instead close at the resolved quote, without that extra tick.
This audit reconciles only that convention and fees on the revised exit notional.
Every signal, path, stop/target, exit time, funding charge and admission stays fixed.
Targets and endpoint marks remain exactly unchanged. This is accounting alignment,
not a better entry signal, rescued trade or new independent edge.

Primary:one-minute observed-quote paths, doubled-slippage scenario. All returns
include fees and funding. The same65 admitted signals appear in both cost models.

| Period | Trades | Stops | Targets | Previous mean net | Reconciled mean net | Change, percentage points |
|---|---:|---:|---:|---:|---:|---:|
| 2022–24 | 41 | 21 | 20 | +0.0681% | +0.1291% | +0.0610 |
| 2025 | 15 | 5 | 10 | +0.8269% | +0.8729% | +0.0460 |
| 2026 Jan–2 Oct | 9 | 2 | 7 | +1.3193% | +1.3411% | +0.0218 |

All28 primary stressed stops remain stops;37 targets remain targets. Stop rates
are51.22%,33.33%,22.22% by period;net win rates48.78%,66.67%,77.78% are unchanged.
The historical mean remains thin at+0.1291% per trade. The primary four-week95%
interval includes zero in each period. Positive cost deltas are mechanically
expected and do not establish stronger prediction or future profitability.

The biggest primary stopped loss improves from−2.7864% to−2.6890%,but remains
beyond the nominal2% stop. Observed quote overshoot,fees and funding remain.
This correction does not solve missed targets, gaps or delayed supervision.
No polling interval is selected from the contextual5/15-minute comparisons.

29 focused tests passed, including actual AST-extracted pinned runtime quote
methods. One initial test harness namespace error was fixed before freeze and
retained. One successful preflight and one treatment run; no treatment retuning.
552 raw reference rows and520 admitted reference rows reconciled;48 independent
admission replays;1,072 independent scalar cash checks;616 report rows and144
bootstrap intervals rebuilt.1,104 raw and1,040 admitted output rows are repeated
cost/path scenarios,not that many independent trades. Only69 raw/65 admitted
signals exist. Sources,6 inputs,358 runtime Python files and output hashes verified.

Protocol published before outcomes:84fd62b97d714898db09669546c63cc8ac91dc2d,
10 files read back exactly. Results in research PR99 under
research/isolated_token_study_20261003/hourly_stop_cost_20261008/FINDINGS.md.

APPROVED PAPER stays hourly_compression_btc_connors_loweff_v1,BTC/ETH/SOL,
LONG+SHORT,1h,SL2%/TP2.5%,no timeout. No strategy,approval,polling,cloud or
implementation change. Runtime implementation remains
3c226bca19cca1c771bcb2ed637f9ec39f74c432. Paper activation/health was not checked.
Matching this one convention does not imply full runtime execution parity.

RESEARCH REFERENCE going forward for these three tokens:immediate entries,
fill-origin brackets,runtime_stop_fill accounting;retain intrabar and one-minute
execution sensitivity views alongside the conservative all-exit-slip results.
Neither minute-based scenario represents measured15-second execution. Do not
overwrite prior evidence. The separately frozen H-HOURLY-EXPANSION-01 primary
cost model remains unchanged;no new-token outcomes were opened.

NEXT:H-WINNER-LOSER-DIAGNOSTIC-01. Compare entry-time features of winners AND
losers under the reconciled accounting,with original conservative and intrabar
outcomes visible. First describe volume,volatility/extension,Connors RSI/RSI,
BTC alignment,efficiency and calendar clustering;check whether relationships
persist by token/side and later periods. MFE/MAE and time-to-exit describe paths,
not entry predictors. Use2022–24 for proposing any rule,then freeze one isolated
candidate before later-period comparison. All three periods have already been
examined;this cannot create an untouched holdout. No thresholds or new filters
were selected by this cost audit. New-token replication remains the next source
of genuinely additional cross-token evidence when the data are ready.

Newest cumulative archive:MAR_stop_cost_checkpoint_20261008.zip,restore over
MAR_hourly_compression_checkpoint_20261007.zip. It includes every earlier
increment,frozen code,ledgers,attempt records and pinned runtime snapshot.
Raw inputs stay in the separate saved raw-data archive. Public root handover
and private operational handover are distinguished in the restore instructions.
Earlier status sections below are historical and do not override this one.

Research results commit:e1e57b380bf22d9bd69b52f5e48cc5a7809d2a71,PR99. This runtime-branch update is documentation only.

## Latest research: sampled exits completed, 8 October 2026

H-EXIT-POLLING-01 compares intrabar exits with current-price checks every1,5,15
minutes. One minute is primary. All use immediate entries,fill-origin SL2%/TP2.5%,
unchanged fees/funding/slippage rules and the approved entry filters.

Doubled-slippage mean net/trade, intrabar -> one-minute sampling:
- 2022–24:41 trades,+0.0702% -> +0.0681%,stops20 ->21.
- 2025:15 trades,+1.0412% -> +0.8269%,stops4 ->5.
- 2026 Jan–2 Oct:9 trades,+1.7240% -> +1.3193%,stops1 ->2.

One former target winner becomes a stop in each period. Same65 signals remain
admitted. All sampled pooled means stay positive at both costs;every sampled
four-week95% mean interval includes zero. Worst net stopped loss reaches2.7864%
with1-minute sampling and3.3014% with15 minutes despite a2% stop trigger.
Coarser polling can skip recoverable stops and capture favorable target overshoot,
but also miss winners and deepen losses. Do not select a slower polling cadence.

47 tests;138 raw/130 admitted comparator rows reconciled;552 paths/cost rows,
24 admissions and18 attributions verified;592 report rows and156 intervals
independently rebuilt. One successful preflight and one treatment run.

Clarified runtime difference:sampled paper stops ALSO omit the second adverse
exit-slippage charge,as OHLC replay does. This research retains that charge in
all arms to isolate sampling. Reconcile it separately next. One-minute data cannot
reconstruct15-second quotes,worker interruptions or target re-quoting latency.
No claim of observed cloud reliability follows from the15-second waiting-loop constant.

APPROVED PAPER remains hourly_compression_btc_connors_loweff_v1,BTC/ETH/SOL
LONG+SHORT,1h,SL2%/TP2.5%,no timeout. No execution or approval change.
Implementation remains3c226bca19cca1c771bcb2ed637f9ec39f74c432.
Next:isolated stop-exit cost reconciliation,then winner/loser review under the
reconciled model. Expanded-token protocol stays frozen;no new-token outcomes.

Protocol-before-outcomes:a058b599b4b7473260bf90466be231487c327c9a.
Results:7535474d278ece30f8260046b70666603bdc4f0e,PR99,
research/isolated_token_study_20261003/hourly_exit_polling_20261008/FINDINGS.md.
Newest archive:MAR_exit_polling_checkpoint_20261008.zip,over the original
MAR_hourly_compression_checkpoint_20261007.zip. Full per-trade evidence and
private operational handover are in the checkpoint. Earlier sections are historical.

## Latest research: entry latency completed, 8 October 2026

H-ENTRY-LATENCY-01 tested 0,1,5,15-minute fills with the same approved signals,
fill-origin SL2%/TP2.5%, fees, funding and slippage. Five minutes was the primary
comparison frozen before outcomes. All delays retain positive pooled means at
both costs in every period, but recent-period expectancy weakens.

Doubled-slippage results, immediate -> five minutes:
- 2022–24:41 trades, mean +0.0702% -> +0.2947%, stops20 ->18.
- 2025:15 trades, mean +1.0412% -> +0.4414%, stops4 ->6.
- 2026 Jan–2 Oct:9 trades, mean +1.7240% -> +1.2216%, stops1 ->2.

The same65 signals remain admitted in all arms/costs. No deliberate delay is
approved. Every delayed-arm four-week95% mean interval includes zero. These are
reused-data sensitivity results, not new independent confirmation or leverage evidence.
40 tests passed;552 paths/cost rows and24 admission replays verified;576 report
rows and156 bootstrap intervals independently rebuilt. One treatment run.

Runtime code accepts signals until15 minutes after close and waits900 seconds
after scan/worker execution by default. This is not a guaranteed15-minute elapsed
cycle. The15-second exit poll applies within the waiting loop; no observed cloud
latency or continuous supervision claim follows from the constant alone.

Current PAPER rule remains hourly_compression_btc_connors_loweff_v1, BTC/ETH/SOL
LONG+SHORT,1h,2% SL/2.5% TP,no timeout. Implementation unchanged at
3c226bca19cca1c771bcb2ed637f9ec39f74c432. This commit changes documentation only.
Next isolated study: sampled exit supervision, with minute-data limitations stated.
Keep entry latency and the separate OHLC stop-slippage convention out of that
one-variable comparison. Expanded-token protocol remains frozen; no new-token
outcomes were opened.

Research results:commit 52f0a70a175bae3427163e0ef1c7e50ca0121f52, PR99,
research/isolated_token_study_20261003/hourly_entry_latency_20261008/FINDINGS.md.
Protocol-before-outcomes:4d1792891682b7570ee1c3a799defb988b1df72a.
Newest cumulative archive:MAR_entry_latency_checkpoint_20261008.zip;restore over
the original MAR_hourly_compression_checkpoint_20261007.zip and verify its latest
manifest. Per-trade evidence and complete private operational handover are saved
with the checkpoint. Earlier sections below are historical.

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
