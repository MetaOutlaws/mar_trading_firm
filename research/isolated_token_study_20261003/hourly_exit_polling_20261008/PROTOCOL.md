# H-EXIT-POLLING-01: sampled quote exits

Authorized8 October2026: proceed with next test. Freeze and publish protocol,
code, tests and baseline reconciliation before sampled-exit outcomes.

Hypothesis: the approved hourly rule retains positive pooled mean net return
when stops and targets trigger only at one-minute price observations. One minute
is primary. Five- and15-minute observations are fixed interruption scenarios,
not deployment candidates or selected polling speeds. Coarser observations can
help or hurt; this is not a guaranteed conservative bound on15-second behavior.

## Runtime evidence and experiment boundary

core/execution/paper.py peek_exit_triggers() compares current quoted price with
stored SL/TP; engine._manage_open_positions() commits the sampled trigger.
Paper stops use mark fills without a second adverse exit-slippage charge;
targets request a market close and may fetch another quote. This stop convention
applies to sampled paper stops as well as the separately documented OHLC replay.
The research comparator charges adverse exit slippage on ALL exits. Retain that
conservative convention in every arm to isolate sampling; changing it is a
separate next audit. Target re-quoting/API latency and spread histories are absent.

PAPER_EXIT_POLL_SECONDS=15 is a waiting-loop interval, not proof of continuous
coverage during worker/scan tasks. The pinned runner waits900 seconds after those
tasks by default. No observed cloud timing or log distribution is available here.
One-minute OHLC contains neither15-second prices nor within-minute paths. Do not
interpolate candles to fabricate those prices or claim production parity.

## Single execution change and exact sampling clock

Arms:poll_0m means the saved immediate-entry,fill-origin,intrabar comparator.
poll_1m (primary),poll_5m,poll_15m use the same immediate entry and fixed brackets,
but inspect ONLY the one-minute OPEN at global UTC minute boundaries divisible
by1,5,15 respectively. First sample is strictly after entry. Phase is fixed at
UTC minute0, not optimized or randomized. Hourly entries already align with this
grid. No missing-bar substitution; input minute grids must be continuous.

At each sample, LONG stop if Q<=SL,target if Q>=TP; SHORT reverses inequalities.
Fill quote is that observed Q, including adverse stop overshoot or favorable
target overshoot. Charge the same adverse exit slippage/fees after that quote.
Do not fill at the nominal threshold. A touch between samples is forgotten:
never retrospectively trigger from highs/lows, queue a missed touch or cancel an
entry based on its path. Endpoints are exclusive: no poll at/after period end;
still-open positions receive the unchanged last-close terminal mark, not a timeout.

Actual sampled exit timestamp is its minute open. exit_bar is that timestamp;
holding_minutes is elapsed entry-to-exit time, with no extra minute. Funding uses
the same rate/open-price proxy and entry exclusion, through the exact known exit
timestamp inclusive. The intrabar comparator retains conservative maximum funding
over the exit-minute boundary and upper-bound holding duration. These timestamp
consequences follow the sampled execution event; no funding rate/cost assumption
is tuned. Terminal marks retain close-time funding.

## Fixed strategy, data and admission controls

Reuse all69 approved raw signals:45 historical,15 evaluation,9 previously examined
2026. Source:hourly_fill_brackets_20261008/results_v1,fill_brackets arm. Baseline
admits41/15/9 =65 trades; preserve every frozen feature, eligibility and rank.
Same compression + directional BTC confirmation + Connors + low-efficiency cap.
SL2%,TP2.5% from slipped entry fill; no maximum hold, profit protection, new filter,
entry delay, universe expansion, threshold fit or token exclusion.

Independent flat-start periods, UTC/exclusive end:
- historical2022-01-01 to2025-01-01;
- evaluation2025-01-01 to2026-01-01;
- reserved_replication2026-01-01 to2026-10-02 16:00.
All are already examined. Preserve predecessor tape cutoffs for terminal funding
semantics:pre2026 for first two;16:00 cutoff for2026. No new holdout claim.
Fees .055% each side. Base per-side slippage .05% BTC/ETH,.10% SOL;stress doubles
slippage. Brackets depend on slipped fill, so paths run separately for each cost.

Full chronological admission replay at unchanged entry timestamps:one position
per token across sides,basket6,direction3,rank/name ordering,exit minute occupied.
For sampled exits the observed exit minute remains occupied, preserving the same
conservative admission convention (runtime exits-before-entries differs).

## Required comparisons and decision

Save all raw counterfactual paths, original65 admitted-signal outcomes (which may
overlap), and executable full admission replay. Pair by original period/token/
side/signal_i plus cost. Attribute additive difference to shared PnL changes +
newly admitted PnL - displaced baseline PnL; do not call it portfolio return.

Report n,closed count,mean net,stops/count/rate,targets,boundary marks,win rate,
profit factor,holding times,ambiguity,loss streak,token/side/year cells and
leave-one-token-out subsets. Report original target-to-stop and stop-to-target
transitions, missed target-to-boundary, changed admission, mean/worst stopped
return,stop quote loss beyond the nominal2%, and target quote overshoot beyond
2.5%. Save per-trade reasons,quotes,fees,funding,timestamps and these diagnostics.

Primary point screen:poll_1m has nonempty closed trades and positive mean under
both cost assumptions in EACH period. Show every prespecified arm regardless.
Mean and paired calendar-week circular-block95% intervals:blocks1/4,10,000 draws,
seeds20261007/20261010,including zero-trade weeks. Pair weeks by original signal
time. Intervals are descriptive on reused data; no multiplicity-corrected edge,
practical equivalence or automatic deployment conclusion. No post-result tuning.

Before scoring:synthetic LONG/SHORT transient touches,observed overshoot,clock
phase,strict post-entry sampling,endpoint and exact funding timestamp tests;
retain original bracket tests. Reconcile138 raw/130 admitted comparator cost rows
exactly. Freeze source/runtime/input/reference hashes and protocol commit.
During scoring:independent sequential sampled-path checks,independent funding/
fee arithmetic,independent admission replay and attribution; reconstruct reports
and confidence intervals independently. Preserve all attempts.

Next after this isolated test: reconcile the stop-exit cost convention separately,
then review losses/winners under the execution model before proposing new filters.
Actual15-second supervision needs finer quote/timestamp logs. Expanded-token
protocol and production approvals remain unchanged; no new-token results opened.
