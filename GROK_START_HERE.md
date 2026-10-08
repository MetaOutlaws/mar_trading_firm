# Grok: fill-price research audit and current paper rule,8 October2026

## Owner update: retest challenger approved for PAPER,8 October2026

At20:30:58 Asia/Dubai,Brian approved the exact fixed retest challenger for paper
testing and explicitly approved public GitHub publication to MetaOutlaws/
mar_trading_firm,PR99/PR101. This supersedes the earlier 'not approved' status.
It does not rewrite the recorded research-screen result or prior evidence.

Approved challenger:hourly_compression_btc_connors_loweff_retest_v1.
Baseline/control:hourly_compression_btc_connors_loweff_v1,immediate entry.
Current paper approval scope:BTC/ETH/SOL,LONG+SHORT,1h,SL2%,TP2.5%,no holding
timeout. Challenger waits at most60 minutes for a frozen boundary retest and
completed-minute reclaim,then enters at next-minute open. No fallback or retuning.
The baseline remains available as the separately measured comparison control.

PRIMARY doubled-cost mean net/trade:2022–24 +0.1291%→+0.7682%;2025
+0.8729%→+1.8852%;2026 through2October +1.3411%→+2.2594%.2026's marginal decline
was net per ORIGINAL signal,+1.3411%→+1.2552%,not net per completed trade.
The owner accepts the observed opportunity-cost/trade-frequency trade-off for
paper testing. All-period historical screen remains failed;owner paper approval
is recorded separately in OWNER_APPROVAL.md/json. Small samples and reused
periods do not establish future certainty.

RUNTIME STATUS:paper approval is recorded;retest runtime integration and cloud
activation verification are pending. Research code already implements the rule;
the pinned cloud implementation implements immediate entry. Do not claim retest
scanning/trading is active,and do not clone the old approval under a new strategy
name without its causal pending-entry adapter and restart/idempotency tests.
No execution code,production config or live-trading permission changes this turn.

NEXT COMPARISON:H-RETEST-EXPANSION-01,registered separately before new-token
outcomes. Compare the two fixed entry rules on ALL eligible newly downloaded
tokens under identical historical membership,signals,SL/TP,costs and independent
portfolio admission replays. Report net/trade AND net/original signal,win rates,
stop counts/rates,missed winners,fill delays and all token/side cells.
2022–24 historical replication and2025 evaluation;additional-token2026 outcomes
remain unopened for a separately specified later stage. Original
H-HOURLY-EXPANSION-01 and its accounting remain unchanged.

Read hourly_retest_expansion_20261008/PROTOCOL.md and TODO.md. Data-readiness
checks are scheduled hourly at21:00,22:00,23:00 on8October and00:00 on9October,
Asia/Dubai. Accessible data and engineering/parity gates are required before
scoring. Prevent duplicate runs across workers;record any missing-data blocker.
Do not assume files downloaded in another worker's environment are accessible.

Publication package:original25 research files plus this owner approval and the
new companion protocol/queue,with updated public handover on both branches.
Earlier GitHub-publication blocks are historical;the owner now supplied the
specific authorization. Publication commit/readback evidence is recorded in
retest_approval_handover/PUBLICATION.json after completion.

Latest handover overlay:MAR_retest_approval_handover_20261008.zip. Apply it after
MAR_retest_entry_checkpoint_20261008.zip (complete repaired archive SHA256
 a0d73470e4607d7995d4f789107d06d301de77747d8452bf05b73eaa3f4d3a80),itself restored
over MAR_hourly_compression_checkpoint_20261007.zip. All trading outcomes and
frozen protocols from the previous experiment remain unchanged. Earlier sections
below describe their historical point in time and do not override this update.

## Latest completed: breakout retest entry, 8 October 2026

H-BREAKOUT-RETEST-ENTRY-01 is complete. The fixed retest rule is a promising
research challenger: higher net return per filled trade in ALL three periods
and all four exit/cost views. It is NOT a newly approved paper strategy.
Its predeclared primary screen fails because2026 net per ORIGINAL signal
is slightly lower, despite better return per filled trade. Preserve the result
and the rule; do not change the screen, optimize the waiting window or deploy it.

Rule: keep the approved hourly compression+BTC+Connors+low-efficiency signals;
wait at most60 minutes for a minute touch of the frozen prior20h breakout
boundary and a completed minute close strictly back beyond it. Enter at the
following minute open. Touch and reclaim in one completed minute are allowed.
No fallback. SL2%/TP2.5% from actual slipped fill, no holding timeout. Admission
is replayed at actual fill, without reserving capacity while waiting.

Primary results include fees, funding, doubled slippage, reconciled stop costs
and one-minute sampled exits. Both directions, BTC/ETH/SOL:

| Period | Immediate trades / stops | Immediate mean net | Retest trades / stops | Retest mean net | Immediate → retest win rate |
|---|---:|---:|---:|---:|---:|
| 2022–24 | 41 / 21 | +0.1291% | 26 / 10 | +0.7682% | 48.78% → 61.54% |
| 2025 | 15 / 5 | +0.8729% | 9 / 1 | +1.8852% | 66.67% → 88.89% |
| 2026 Jan–2 Oct | 9 / 2 | +1.3411% | 5 / 0 | +2.2594% | 77.78% → 100.00% |

| Period | Raw signals | Qualified / admitted | No trade: no retest / no reclaim | Immediate net / original signal | Retest net / original signal |
|---|---:|---:|---:|---:|---:|
| 2022–24 | 45 | 28 / 26 | 15 / 2 | +0.1176% | +0.4438% |
| 2025 | 15 | 9 / 9 | 5 / 1 | +0.8729% | +1.1311% |
| 2026 Jan–2 Oct | 9 | 5 / 5 | 4 / 0 | +1.3411% | +1.2552% |

The2026 sample ends exclusively at2 October16:00UTC. There are no boundary
marks or endpoint-censored entries. Historical28 qualified retests become26
admitted trades after two occupancy rejections. Across69 raw signals there
are42 qualified and40 admitted retests, with27 no-fills. Do not count the420
ledger rows across scenarios as420 independent trades.

Primary stops:28/65 immediate trades versus11/40 retest trades. Nonfills miss
12 immediate target winners but avoid14 immediate stops:2022–24 misses6 targets
and10 stops;2025 misses4 targets and2 stops;2026 misses2 targets and2 stops.
A previously blocked historical signal becomes admitted and stops out. That
replacement and changes in shared-trade outcomes are included in the totals.

2026 return per original signal falls from+1.3411% to+1.2552%, a difference
of−0.0858 percentage points. The2025 improvement on that denominator occurs
only in the primary one-minute doubled-slippage view;intrabar and base-cost
views show a decline. Historical net per signal improves in all four views.
All12 per-filled-trade mean comparisons improve, but this does not establish
higher total return at the existing signal supply or future profitability.
The user values fewer,higher-quality trades and broader token coverage:the
conditional improvement is useful evidence to retain,not a reason to overwrite
the preregistered opportunity-cost screen. Broader-token transfer is untested.

All three primary paired four-week95% intervals for improvement include zero,
for both mean net per trade and net per original signal.2026 has only five
retained trades and two tokens,all winners;100% observed win rate is not a
forecast. All periods have already been examined in prior research.

Verification:14 focused tests;276 baseline paths/costs and260 admissions exactly
reconciled;69 reconstructed boundaries;69 independent retest selections and69
causal prefixes;168 treatment path/cost checks;24 admission replays;276 paired
rows,132 report rows and144 bootstrap values independently rebuilt. One successful
preflight and one successful treatment run,with no scoring or verifier retries.

PUBLICATION STATUS:local rules/code were frozen before scoring at
2026-10-08T16:10:59.917840+00:00. The preregistration ZIP was saved before scoring.
GitHub protocol_commit is null. Automatic approval review blocked public upload
twice,including after destination verification and removal of per-signal data.
This study has NOT been published to GitHub. The last research head remains
61b1e70e2762d625d15bc8feccd26cbe44c590dd. A concrete public patch is prepared
for explicit confirmation;no further GitHub writes are attempted this turn.

APPROVED PAPER remains hourly_compression_btc_connors_loweff_v1,BTC/ETH/SOL,
LONG+SHORT,1h,SL2%/TP2.5%,no timeout,immediate entry. Runtime implementation
remains3c226bca19cca1c771bcb2ed637f9ec39f74c432. No cloud health/activation check,
runtime change,approval change,new-token outcome or order occurred in this test.

NEXT:freeze this exact challenger for broader-token and prospective comparison
against the approved immediate-entry rule. Prepare a separate companion protocol
BEFORE opening expanded-token outcomes;preserve H-HOURLY-EXPANSION-01 unchanged,
including its original conservative accounting. Do not silently append this
challenger to that previously frozen experiment. New data should test both
conditional trade quality and opportunity cost. More threshold/deadline searching
on the same69 signals is lower priority than this independent comparison.
This companion replication is proposed,not run or deployed.

Newest cumulative archive:MAR_retest_entry_checkpoint_20261008.zip,restore over
MAR_hourly_compression_checkpoint_20261007.zip. It retains previous experiments,
full per-trade/per-signal evidence,failures and the pinned runtime snapshot.
Read hourly_retest_entry_20261008/{PROTOCOL,FINDINGS,PUBLICATION_EXCEPTION}.md.
Earlier sections below are historical and do not override this status.

## Latest completed: winner/loser diagnostic, 8 October 2026

H-WINNER-LOSER-DIAGNOSTIC-01 is complete. Keep the approved PAPER strategy.
The historically strongest lead,smaller breakout extension,does not transfer
consistently:it improves2022–24 and2026,but weakens2025 in ALL eight fixed
execution/cost views. Do not add the tighter extension filter or replace it
post hoc with another indicator from this diagnostic.

Twelve causal entry features were examined,including volume,RSI14,Connors RSI,
ADX,volatility,compression,body size,BTC/own-token momentum and prior efficiency.
The nominee was selected using2022–24 only,then published BEFORE generating
later-period feature/outcome tables. The frozen split is extension_atr<=
0.5337759022674707,the historical median distance beyond the prior20-hour
breakout boundary in units of priorATR. It is a diagnostic split,not a deployable
precision-optimized threshold. All periods were already examined in prior work.

Primary evidence:one-minute sampled exits,doubled slippage,reconciled stop
accounting,fees and funding. These are ORIGINAL ADMITTED SUBSETS,not a new
portfolio backtest;an actual filter requires replaying all69 raw opportunities.

| Period | Baseline trades / stops / mean net | Closer-entry subset trades / stops / mean net | Excluded targets / stops |
|---|---:|---:|---:|
| 2022–24 | 41 / 21 / +0.1291% | 21 / 7 / +1.0745% | 6 / 14 |
| 2025 | 15 / 5 / +0.8729% | 7 / 4 / -0.2288% | 7 / 1 |
| 2026 Jan–2 Oct | 9 / 2 / +1.3411% | 5 / 0 / +2.3685% | 2 / 2 |

Historical retained win rate66.67% versus baseline48.78%;2025 retained42.86%
versus66.67%;2026 retained100% versus77.78%,with only5 retained trades.2025's
tighter split removes SEVEN target winners and only ONE stop. The2025 loss of
performance persists with intrabar exits,base costs,and the old cost convention;
it is not explained solely by the sampled-exit mismatch. The2026 result contains
only two baseline losses and no retained ETH trades,so100% is very limited evidence.

No one of the12 continuous features has a strictly consistent winner/loser rank
direction in all three primary periods. Lower ADX,lower volatility and lower
aligned Connors were historical associations,not stable replacement filters.
Higher volume is not universally better. Calendar years are not trading regimes;
do not label2025 'chop' merely because a preferred rule weakens there.

PATH FINDINGS:19/37 eventual winners (51.35%) moved at least1% against the slipped
entry,7/37 moved at least1.5%,and none reached2% adverse excursion before their
sampled target exit.15/28 stopped trades (53.57%) had first shown at least1%
gross favorable excursion;7/28 reached at least2%. These extrema include held
minute highs/lows and the exit quote. They are not executable net profit or an
alternate stop/trailing backtest. A1% stop risks interrupting many winning paths,
but this does not establish that widening2% or tightening after profit improves
the whole portfolio. The earlier failed profit-protection studies remain valid.

Historical results remain fragile:remove the single largest sampled winner and
mean net falls from+0.1291% to about+0.0075%. The41 historical trades span38 dates
and36 active weeks;15 evaluation trades span15 dates/14 weeks;9 recent trades
span7 dates/7 weeks. The stopped trades have distinct entry dates within each
period. This small sample cannot establish a calendar/regime switching rule.

Verification:13 tests passed;276 independent indicator checks;6 causal prefix
checks;520 reference outcome rows exactly reconciled;65 independent sampled
path checks;24 historical candidate rows,1,473 report rows and96 bootstrap
intervals independently rebuilt. One preflight,one historical run and one later
diagnostic run. The first report verifier encountered CSV float rounding at
exact median boundaries;round-trip parsing corrected only the verifier.
Original verifier and correction are preserved;outcomes and nomination unchanged.

Protocol-before-associations:bfd30e13a4ebe0240e3e4d82d91dbb9fbdac7255,10 files
read back exactly. Historical nomination-before-later-tables:
e71c81dceba1be016fdc1c727402edbff645b90a,9 files read back exactly.
Read hourly_winner_loser_20261008/{PROTOCOL,FINDINGS,DEVELOPMENT_FINDING}.md,
development_v1/selection.json and results_v1 in research PR99.

APPROVED PAPER remains hourly_compression_btc_connors_loweff_v1,BTC/ETH/SOL,
LONG+SHORT,1h,SL2%/TP2.5%,no timeout;the existing low-efficiency extension cap
remains1ATR. No new0.534ATR cap,RSI/ADX gate,stop width or polling setting is
approved or deployed. Runtime implementation stays
3c226bca19cca1c771bcb2ed637f9ec39f74c432. No cloud-health verification this turn.

NEXT PROPOSED ISOLATED TEST:H-BREAKOUT-RETEST-ENTRY-01. Hypothesis:an approved
breakout can obtain a better entry after a boundary retest and completed
one-minute reclaim,without excluding it solely for its initial extension.
Compare immediate entry against one fixed retest rule;keep signal eligibility,
initial2% stop/2.5% target from fill,and exit model unchanged. Report nonfills,
missed target winners,stops,new admissions,mean per filled trade AND net per
original signal including unfilled zeros. A retest can miss strong continuations;
that opportunity cost is central,not a reason to hide nonfills.
This is a proposal requiring its own exact protocol and novelty audit before
outcomes;no retest result or background run exists. It is a different entry
mechanism from raising an indicator threshold. Additional-token replication
remains the preferred source of new evidence when its data become available.

Newest cumulative archive:MAR_winner_loser_checkpoint_20261008.zip,restore over
MAR_hourly_compression_checkpoint_20261007.zip. Full per-trade anatomy,all
entry-feature comparisons,older increments,failed attempts and runtime snapshot
are retained. H-HOURLY-EXPANSION-01 remains unchanged;no new-token outcomes opened.
Earlier status sections below are historical and do not override this one.

Results commit:61b1e70e2762d625d15bc8feccd26cbe44c590dd,PR99. This commit updates research documentation only.

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
