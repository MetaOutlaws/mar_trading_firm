# H-STOP-COST-01 findings

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

## Complete model results

poll_minutes=0 is the intrabar comparator;1/5/15 are observation intervals,not entry delays. Fractions in CSVs are multiplied by100 below.

| Period | Poll minutes | Cost model | Slippage | Trades | Stops | Targets | Mean net | Four-week95% interval |
|---|---:|---|---|---:|---:|---:|---:|---|
| 2025 | 0 | research_all_exit_slip | Base | 15 | 3 | 12 | +1.4097% | +0.3875% to +2.3048% |
| 2025 | 0 | research_all_exit_slip | Doubled | 15 | 4 | 11 | +1.0412% | +0.1309% to +1.8958% |
| 2022–24 | 0 | research_all_exit_slip | Base | 41 | 18 | 23 | +0.3529% | -0.3315% to +0.9607% |
| 2022–24 | 0 | research_all_exit_slip | Doubled | 41 | 20 | 21 | +0.0702% | -0.6258% to +0.6902% |
| 2026 Jan–2 Oct | 0 | research_all_exit_slip | Base | 9 | 1 | 8 | +1.8015% | +0.0484% to +2.3103% |
| 2026 Jan–2 Oct | 0 | research_all_exit_slip | Doubled | 9 | 1 | 8 | +1.7240% | -0.0125% to +2.2352% |
| 2025 | 1 | research_all_exit_slip | Base | 15 | 3 | 12 | +1.4942% | +0.4558% to +2.3741% |
| 2025 | 1 | research_all_exit_slip | Doubled | 15 | 5 | 10 | +0.8269% | -0.3857% to +1.8653% |
| 2022–24 | 1 | research_all_exit_slip | Base | 41 | 19 | 22 | +0.3819% | -0.4341% to +1.1085% |
| 2022–24 | 1 | research_all_exit_slip | Doubled | 41 | 21 | 20 | +0.0681% | -0.7325% to +0.7697% |
| 2026 Jan–2 Oct | 1 | research_all_exit_slip | Base | 9 | 1 | 8 | +1.8227% | +0.0528% to +2.3464% |
| 2026 Jan–2 Oct | 1 | research_all_exit_slip | Doubled | 9 | 2 | 7 | +1.3193% | -0.3295% to +2.4175% |
| 2025 | 5 | research_all_exit_slip | Base | 15 | 3 | 12 | +1.5569% | +0.4549% to +2.4964% |
| 2025 | 5 | research_all_exit_slip | Doubled | 15 | 4 | 11 | +1.1222% | -0.2661% to +2.1478% |
| 2022–24 | 5 | research_all_exit_slip | Base | 41 | 18 | 23 | +0.4303% | -0.4216% to +1.1893% |
| 2022–24 | 5 | research_all_exit_slip | Doubled | 41 | 19 | 22 | +0.2586% | -0.5791% to +1.0045% |
| 2026 Jan–2 Oct | 5 | research_all_exit_slip | Base | 9 | 1 | 8 | +1.9805% | +0.1916% to +2.6042% |
| 2026 Jan–2 Oct | 5 | research_all_exit_slip | Doubled | 9 | 2 | 7 | +1.4312% | -0.2041% to +2.4790% |
| 2025 | 15 | research_all_exit_slip | Base | 15 | 3 | 12 | +1.5187% | +0.3352% to +2.5160% |
| 2025 | 15 | research_all_exit_slip | Doubled | 15 | 4 | 11 | +1.0849% | -0.3982% to +2.2029% |
| 2022–24 | 15 | research_all_exit_slip | Base | 41 | 18 | 23 | +0.4321% | -0.4664% to +1.2389% |
| 2022–24 | 15 | research_all_exit_slip | Doubled | 41 | 18 | 23 | +0.3724% | -0.4994% to +1.1575% |
| 2026 Jan–2 Oct | 15 | research_all_exit_slip | Base | 9 | 2 | 7 | +1.4538% | -0.3066% to +2.5809% |
| 2026 Jan–2 Oct | 15 | research_all_exit_slip | Doubled | 9 | 2 | 7 | +1.3560% | -0.3467% to +2.4597% |
| 2025 | 0 | runtime_stop_fill | Base | 15 | 3 | 12 | +1.4229% | +0.4162% to +2.3048% |
| 2025 | 0 | runtime_stop_fill | Doubled | 15 | 4 | 11 | +1.0742% | +0.1916% to +1.9041% |
| 2022–24 | 0 | runtime_stop_fill | Base | 41 | 18 | 23 | +0.3786% | -0.2963% to +0.9790% |
| 2022–24 | 0 | runtime_stop_fill | Doubled | 41 | 20 | 21 | +0.1289% | -0.5497% to +0.7312% |
| 2026 Jan–2 Oct | 0 | runtime_stop_fill | Base | 9 | 1 | 8 | +1.8069% | +0.0729% to +2.3103% |
| 2026 Jan–2 Oct | 0 | runtime_stop_fill | Doubled | 9 | 1 | 8 | +1.7349% | +0.0365% to +2.2352% |
| 2025 | 1 | runtime_stop_fill | Base | 15 | 3 | 12 | +1.5074% | +0.4844% to +2.3741% |
| 2025 | 1 | runtime_stop_fill | Doubled | 15 | 5 | 10 | +0.8729% | -0.3010% to +1.8811% |
| 2022–24 | 1 | runtime_stop_fill | Base | 41 | 19 | 22 | +0.4086% | -0.3980% to +1.1278% |
| 2022–24 | 1 | runtime_stop_fill | Doubled | 41 | 21 | 20 | +0.1291% | -0.6516% to +0.8119% |
| 2026 Jan–2 Oct | 1 | runtime_stop_fill | Base | 9 | 1 | 8 | +1.8281% | +0.0773% to +2.3464% |
| 2026 Jan–2 Oct | 1 | runtime_stop_fill | Doubled | 9 | 2 | 7 | +1.3411% | -0.2736% to +2.4175% |
| 2025 | 5 | runtime_stop_fill | Base | 15 | 3 | 12 | +1.5701% | +0.4840% to +2.4964% |
| 2025 | 5 | runtime_stop_fill | Doubled | 15 | 4 | 11 | +1.1616% | -0.1825% to +2.1547% |
| 2022–24 | 5 | runtime_stop_fill | Base | 41 | 18 | 23 | +0.4547% | -0.3875% to +1.2043% |
| 2022–24 | 5 | runtime_stop_fill | Doubled | 41 | 19 | 22 | +0.3099% | -0.5105% to +1.0381% |
| 2026 Jan–2 Oct | 5 | runtime_stop_fill | Base | 9 | 1 | 8 | +1.9860% | +0.2161% to +2.6042% |
| 2026 Jan–2 Oct | 5 | runtime_stop_fill | Doubled | 9 | 2 | 7 | +1.4530% | -0.1482% to +2.4790% |
| 2025 | 15 | runtime_stop_fill | Base | 15 | 3 | 12 | +1.5319% | +0.3641% to +2.5160% |
| 2025 | 15 | runtime_stop_fill | Doubled | 15 | 4 | 11 | +1.1242% | -0.3121% to +2.2115% |
| 2022–24 | 15 | runtime_stop_fill | Base | 41 | 18 | 23 | +0.4565% | -0.4319% to +1.2539% |
| 2022–24 | 15 | runtime_stop_fill | Doubled | 41 | 18 | 23 | +0.4212% | -0.4294% to +1.1901% |
| 2026 Jan–2 Oct | 15 | runtime_stop_fill | Base | 9 | 2 | 7 | +1.4647% | -0.2787% to +2.5809% |
| 2026 Jan–2 Oct | 15 | runtime_stop_fill | Doubled | 9 | 2 | 7 | +1.3777% | -0.2908% to +2.4597% |

## Reconciled stopped losses, doubled slippage

| Period | Poll minutes | Stops | Mean stopped net | Worst stopped net |
|---|---:|---:|---:|---:|
| 2025 | 0 | 4 | -2.1151% | -2.1236% |
| 2022–24 | 0 | 20 | -2.1017% | -2.2291% |
| 2026 Jan–2 Oct | 0 | 1 | -2.1706% | -2.1706% |
| 2025 | 1 | 5 | -2.1659% | -2.2264% |
| 2022–24 | 1 | 21 | -2.1879% | -2.6890% |
| 2026 Jan–2 Oct | 1 | 2 | -2.2023% | -2.2257% |
| 2025 | 5 | 4 | -2.3280% | -2.5326% |
| 2022–24 | 5 | 19 | -2.2979% | -2.8696% |
| 2026 Jan–2 Oct | 5 | 2 | -2.2593% | -2.3146% |
| 2025 | 15 | 4 | -2.5632% | -2.9729% |
| 2022–24 | 15 | 18 | -2.3635% | -3.2045% |
| 2026 Jan–2 Oct | 15 | 2 | -2.3834% | -2.5628% |

## Accounting interpretation

Let d be1 for LONG or−1 for SHORT,e the entry fill,q the resolved exit quote,
and s the per-side slippage. Original exit=q*(1−d*s);reconciled stop exit=q.
Gross return=d*(exit/e−1). Fees=.00055*(1+exit/e). Funding is exactly inherited.
Stop net improvement=q*s/e*(1−.00055*d). Long exit fees rise slightly because
their corrected sell notional is higher;short exit fees fall because their
corrected buy notional is lower. Neither changes the entry fee or funding.
Targets and marks are byte-for-byte equal at dataframe level.

Under stress, intrabar reconciled means are+0.1289%,+1.0742%,+1.7349% across
the three periods,with20/4/1 stops. Primary one-minute values differ because
three original targets became stops in H-EXIT-POLLING-01,one in each period.
Those three transitions are unchanged here. The cost correction cannot recover
them or change the approved entry quality.

All primary stressed four-week intervals include zero:2022–24−0.6516% to
+0.8119%;2025−0.3010% to+1.8811%;2026−0.2736% to+2.4175%. Some base-cost
intervals are positive;there is no blanket claim that every cost/path interval
includes zero. Repeated inspection and small samples prevent treating these
intervals as confirmatory selection-adjusted evidence. Cost-difference intervals
describe a mechanical accounting change,not an empirical trading improvement.

No live quote,spread,exchange-fill or cloud-cycle measurements were available
in this audit. Paper stops filling at a sampled quote is a model convention;
matching it does not guarantee a live stop executes there. Target requoting,
funding provenance and exit-observation precision remain separate limitations.

## Exports and reproducibility

individual_trades.csv contains65 admitted identities x4 fixed paths x2 slip
scenarios x2 accounting models=1,040 rows. all_opportunities.parquet contains
69 x4 x2 x2=1,104 rows. paired_cost_changes.csv has552 old/new raw pairs and
an admitted flag. contrasts.csv contains24 path/period/slippage comparisons.
The primary-trades export has65 reconciled one-minute stressed trades,not1040;
it retains entry-time features and clearly labeled outcome/cost columns.

side1=LONG,−1=SHORT;stress1=base,2=doubled;return columns are fractions.
Entry and exit timestamps use UTC. Sampled exit_time_lower_utc equals
exit_time_upper_utc;intrabar bounds span one minute. No within-minute timestamp
is fabricated. stop_quote_overshoot retains its prior fill-notional denominator
and excludes fees/funding. slippage_drag includes entry effects and the remaining
exit tick on non-stops. net_R divides net_return by the nominal.02 initial stop.
R and summed returns are attribution units,not compounded portfolio returns.

Source preflight validates prior552 raw/520 admitted all-exit-slip calculations
without treatment scoring. Runtime tests extract real source methods with AST
and controlled dependencies;whole-runtime import was unavailable because the
research environment lacks httpx. This is targeted semantics coverage,not an
end-to-end broker integration test. Existing minute-path validation is inherited;
this study reprices frozen paths and verifies exact identity,without resimulation.

Read PROTOCOL.md,results_v1/freeze.json,VERIFICATION.json,status.json,
REPORT_VERIFICATION.json and ATTEMPTS.md. Preserved reports remain authoritative
for their original cost convention. No historical result was silently replaced.
