# Grok: fill-price research audit and current paper rule,8 October2026

PUBLICATION COMPLETE:research commit b2140ca485c9d5ad645cb8c2acc59a65d2cafd44 and runtime public handover commit1e24a411c42a05b10a85a9e6dc56626e47568481 were uploaded and read back exactly. PR101 had already merged;its new source-branch handover is a post-merge publication,not part of the historical merged diff. See hourly_retest_entry_20261008/PUBLICATION_RECORD.json.

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
