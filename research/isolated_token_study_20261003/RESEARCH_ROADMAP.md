# MAR entry research: living roadmap and hypothesis register

Updated 7 October 2026. Owner: Brian / Meta Outlaws.
Objective: identify positive net expectancy that survives execution costs and independent confirmation, then improve risk and exits. Fewer trades are acceptable; support may be pooled across tokens without assuming those tokens are independent.

## Latest completed: hourly breakout-extension filter — 7 October 2026

The approved selectivity plan's first comparison is complete. The fixed cap
keeps a signal only within one prior hourly ATR beyond its 20-hour boundary.
Protocol and duplicate audit published before scoring at
3565cd83ce2aeddcace324c415880a5ab892ad50. No exact cap found in inspected records;
external unrecorded Grokbot jobs are not certified.

2025 baseline: 36 trades, 14 stops, 22 targets, 61.11% win rate,
+0.4992% base / +0.3685% stressed mean net per trade.
Filtered: 22 trades, 10 stops, 12 targets, 54.55% win rate,
+0.1999% / +0.0635%. It avoids four stops but excludes ten target winners;
stop rate worsens from 38.89% to 45.45%. No 2025 admissions are added.
Historical 2022–24: baseline 97 trades / 44 stops / +0.2268% / +0.1037%;
filtered 60 / 26 / +0.3109% / +0.1834%. Historical filtering admits one extra
stop, which is included. All three tokens worsen under stress in 2025.

Decision: reject this cap as a baseline improvement. It remains positive pooled
but fails consistent improvement; intervals cross zero and 2025 is reused.
Keep the approved hourly paper strategy unchanged. Read
hourly_extension_filter_20261007/{NOVELTY_AUDIT,PROTOCOL,FINDINGS}.md.
12 tests, 143 geometry checks, 143 barrier checks, eight independent admissions,
exact baseline reconciliation and report reconciliation passed. The full ledger
has 430 cost-scenario rows across 133 baseline and 82 filtered admissions.

## Active queue while additional-token data is unavailable

1. NEXT: BTC direction confirmation for ETH/SOL hourly compression entries.
   Hypothesis: market alignment improves selection. Audit duplication and freeze
   one causal BTC rule before scoring. BTC's own sleeve stays unchanged; report
   ETH/SOL and full-basket comparisons against the ORIGINAL hourly baseline.
2. THEN: ADX, RSI and Connors RSI as separate entry-time comparisons. Exact
   predicates and thresholds remain unfrozen. Audit, freeze, then score each
   independently; no extension cap or stacking of filters.
3. WHEN DATA RETURNS: resume broader-token replication under its existing
   frozen protocol. Preserve reserved 2026 and collect prospective paper evidence.

Each completed comparison must show trade and stop counts/rates, winners lost,
net means at base/stress costs, token/year concentration and uncertainty. Do not
retune a failed predicate on the same history. No later study has been scored
or left running. Earlier dated next-step text below is historical and superseded
by this queue. Runtime changes require a separate decision.

Latest observed cloud cycle remains 2026-10-07T10:05:31.385232+00:00,
six hourly BTC/ETH/SOL LONG/SHORT paper configurations, errors []. This is the
operator's earlier observation, not new SSH monitoring.

Restore MAR_entry_filters_checkpoint_20261007.zip over the full
MAR_hourly_compression_checkpoint_20261007.zip. It includes the prior two exit
studies, sweep confirmation and this extension study. Keep the original raw
candle/funding ZIP separately; previous incremental ZIPs need not also be
extracted. Follow extension_filter_handover/RESTORE_ENTRY_FILTERS.md.

## Previous completed: previous-day sweep confirmation — 7 October 2026

Duplicate audit corrected the novelty claim: prior_day_extreme_reject was already
family 118/PR16. No exact 15m next-candle confirmation variant was found in the
inspected GitHub/Grokbot records; external runtime history is not certified.
The separately frozen confirmation comparison is now completed and REJECTED.
Protocol-before-scoring commit 7403b72ef1a8c99e920ddcd39dfa3c0597547781.

2025 immediate: 687 entries, 684 closed, 380 stops, 304 targets, 3 terminal marks;
mean net -0.2464% base/-0.3874% stress. Confirmed: 230 entries, 227 closed, 132 stops,
95 targets, 3 marks; mean -0.3505%/-0.4858%, closed win rate 41.85%.
2022–24 immediate 1,825 entries/1004 stops/-0.2249% base/-0.3657% stress;
confirmed 559 entries/293 stops/-0.1088%/-0.2475%. Neither arm is profitable.
Confirmation filters both losers and winners, and later entry consumes the
apparent selection benefit. All three tokens are negative under stress in both
periods. Do not rescue this failed rule by selecting a positive year or cell.

13 tests, 3503 independently reconstructed first setups, 4,151 raw-path checks,
eight admissions and 124 report-row reconciliations passed. 6,602 scenario rows
are 2,512 immediate plus 789 confirmed admissions at two costs, not independent
trades. Read sweep_confirmation_20261007/{NOVELTY_AUDIT,PROTOCOL,FINDINGS}.md.
results_v2 is complete; results_v1 is a preserved pre-scoring software failure.

Next: acquire/audit additional-token data for the frozen replication protocol
and collect prospective evidence from the approved hourly pilot. This new entry
comparison and both previous exit treatments are closed. No further experiment
runs in the background; reserved 2026 remains unscored. Any future entry test
needs a distinct, audited hypothesis and pre-scoring protocol.

The latest observed cloud cycle remains 2026-10-07T10:05:31.385232+00:00,
six hourly BTC/ETH/SOL LONG/SHORT paper configurations, errors [].
No current SSH channel or newer cloud observation is claimed.

Restore MAR_sweep_and_exit_studies_checkpoint_20261007.zip on top of
MAR_hourly_compression_checkpoint_20261007.zip, keeping the original raw ZIP
separately. This combined increment includes both earlier exit studies and the
sweep comparison. The separate previous exit increments are not also required.
See sweep_confirmation_handover/RESTORE_SWEEP_STUDY.md and verify hashes.

## Previous completed: fixed failed-breakout exit — 7 October 2026

The predeclared rule exits at the next minute open after a completed hourly
close back through the FIXED entry-time 20-hour breakout boundary. Original
hourly entries, SL2% / TP2.5%, costs and admission limits remain unchanged.
Protocol was published before scoring at fe51e67511a8ae7b738d7a27c7a0914d3573ba75.

Decision: reject this treatment under the frozen improvement screen. In 2025,
36 baseline trades become 38: actual stops fall 14 to 2, but 23 early failure
exits and 13 targets produce +0.1031% base / -0.0254% stressed mean net return,
versus baseline +0.4992% / +0.3685%. Net win rate falls 61.1% to 34.2%.
On the same 36 entries, 12 original stops improve but 11 target winners are
cut short. Two new winning entries only partly offset the damage.

In 2022–24, 97 baseline trades become 104: 12 stops, 59 failure exits, 33
targets, -0.0432% base / -0.1654% stress, versus +0.2268% / +0.1037% baseline.
Seven newly admitted trades partly offset, but do not reverse, the lost returns.
All three tokens worsen under stressed costs in both partitions. Every one of
the 82 chronological failure exits is a net loss at both cost levels.

Read hourly_failed_breakout_20261007/FINDINGS.md and PROTOCOL.md. Validation:
22 tests; 143 independently reconstructed entry boundaries; 286 independent
raw paths; 286 raw/266 admitted baseline rows exactly reconciled; eight
independent admissions; 124 report-row checks. The 550 ledger rows are cost
scenarios across 133 baseline and 142 treatment admissions, not 550 independent
trades. There are 78 affected original admissions in the changed-trades CSV.

Both the price-break-even and fixed failed-breakout exit hypotheses are now
completed with negative improvement findings. Keep the approved baseline
unchanged and pause further fitting of these exits to the same history.
Priorities: acquire/audit additional-token data for the existing frozen
replication protocol and collect prospective paper evidence. Preserve reserved
2026 outcomes and the broader-token qualification rules. A future exit study
requires a distinct hypothesis and separately frozen protocol. No test is
running in the background; no production exit changes or leverage tests.

Current operational evidence remains the operator-supplied scanning_verified
for all six hourly BTC/ETH/SOL LONG/SHORT configurations, errors [], cycle
2026-10-07T10:05:31.385232+00:00. No newer cloud observation is claimed here.

Restore MAR_exit_studies_checkpoint_20261007.zip on top of the full
MAR_hourly_compression_checkpoint_20261007.zip. This combined increment
contains both exit studies; the earlier standalone profit-protection increment
is not also required. Keep the original raw candle/funding ZIP separately.
Follow RESTORE_EXIT_STUDIES.md and verify all hashes.

## Previous completed: profit protection and confirmed paper scan — 7 October 2026

The operator's screenshot returned `scanning_verified` for all six hourly
BTC/ETH/SOL LONG/SHORT paper configurations, with `errors: []`. The completed
cycle started at 2026-10-07T10:05:31.385232+00:00, after successful activation.
This is evidence of that cycle, not continuous SSH monitoring by this chat.

The profit-protection protocol was published before scoring at
8f26ae5a4c49f521dbdee860c209387fea203976. One fixed treatment moved the stop to
the entry quote on the minute after a completed +2% favorable close, keeping
hourly entries, initial SL2% / TP2.5%, costs and occupancy fixed.

Result: reject this treatment under its improvement screen. In 2025, 36 trades
remain; original stops fall 14 to 13, but five protective exits cut four target
winners and intercept only one original stop. Mean net falls +0.4992% to
+0.2754% base, and +0.3685% to +0.1445% stress. Net win rate falls 61.1% to 50.0%.
In 2022–24, 97 trades remain; two original stops and two target winners are
intercepted, and stressed mean falls +0.1037% to +0.0928%. No extra or dropped
admissions explain either comparison. All nine protective exits are net losses
at both cost levels. The approved paper baseline stays unchanged.

Read hourly_profit_protection_20261007/FINDINGS.md and PROTOCOL.md. Verification:
19 tests; 286 independent raw path checks; 286 raw/266 admitted baseline rows
reconciled exactly; eight independent admissions; 124 report-row checks.
532 ledger rows represent 133 admissions × two arms × two cost scenarios.
All prior outcomes and frozen evidence remain intact. No new-token or 2026
outcome, live change, or leverage test.

Proposed next research: freeze one failed-breakout exit at a completed hourly
close back inside the ENTRY-TIME breakout boundary, with next-minute execution,
and compare winners cut short with losses reduced. This has NOT run and is
not approved for deployment. Broader-token/forward confirmation remains
pending; reused 2025 is not an independent holdout.

Restore the incremental MAR_profit_protection_checkpoint_20261007.zip AFTER
the full MAR_hourly_compression_checkpoint_20261007.zip; keep the original
raw candle/funding ZIP separate. Follow RESTORE_PROFIT_PROTECTION.md and verify
each manifest. No experiment is running in the background.

## Latest owner decision and stop-only experiment — 7 October 2026

Brian explicitly approved hourly compression on BTC/ETH/SOL, both directions,
for PAPER use at SL2% / TP2.5%. Preserve the original positive baseline and
record owner approval separately from independent research qualification.
The runtime module and guarded activation script are prepared and tested;
Singapore is active in DigitalOcean, but this chat has no SSH execution access.
At that earlier preparation stage, cloud activation was pending. The current\noperator-confirmed scanning status is recorded above.

The stop-only protocol was published before scoring. With TP fixed at 2.5%,
2025 results (closed/stops; net base/stress) are: SL1% 37/25, -0.1092%/-0.2385%;
SL2% 36/14, +0.4992%/+0.3685%; SL3% 36/13, +0.2627%/+0.1320%;
SL4% 36/10, +0.4418%/+0.3111%; SL5% 36/8, +0.5779%/+0.4477%.
SL1% loses 11 baseline target winners. SL5% recovers six of 14 baseline stops,
but has lower mean R than SL2%. No alternative improves both stressed mean net
and mean R in both partitions; the approved 2% baseline remains unchanged.
Read hourly_stop_width_20261007/FINDINGS.md and PROTOCOL.md.

Verification: 143 raw signals, 715 independent barriers, 20 independent
admission replays, 266 exactly reconciled baseline rows, 1,330 alternative
ledger rows. Six implementation tests pass; 143 research entry signals and
1,734 rolling candidate checks match. No new token or 2026 price scoring.

At this earlier stage, the queued research was a profit-protection comparison with unchanged
hourly entries and initial 2%/2.5% barriers, counting winners cut short as well
as stopped-trade profits saved. That comparison has since completed; see the latest section above. New-token confirmation remains
pending. None of the old negative family findings or positive hourly findings
has been overwritten. Older status sections below describe their dated stages.


## Where we are

| Work | Question | Status and evidence |
|---|---|---|
| Five-family discovery | Do trend pullbacks, volume-shock reversals, funding-crowding breakouts, compression expansions or a learned entry rule provide an edge? | Completed on BTC/ETH/SOL, 5m/15m/1h, both directions, two stop/target arms: 180 new configurations plus controls. Every full family had negative pooled 2025 mean at base costs. None passed the frozen qualification screen. |
| Selection of research leads | Which individual configurations merit replication? | Thirteen configurations were positive across development 2022–23, selection 2024 and evaluation 2025 at base costs. Six remained positive in all three at doubled slippage: five compression and one funding. These are related, post-review leads; they are not independent discoveries. |
| Three-token pooled compression replay | Does trading the whole unchanged compression rule across all clocks work under shared position limits? | Completed. 2025 primary 2% SL / 2.5% TP: 222 closed, 114 stops, mean net -0.0559% base / -0.1839% stress. Historical 2022–24 also negative. Wider 3%/3% arm negative too. No promotion. |
| Broader-token replication | Does the unchanged event generalize to additional historically eligible tokens? | Original protocol frozen; data acquisition pending. No additional-token outcome has been calculated here. |
| Hourly-only diagnostic | Is the positive admitted hourly subset preserved when all hourly opportunities are replayed on their own? | Completed: 36 evaluation trades; +0.4992% base / +0.3685% stress; 14 stops. Positive historical aggregate, but negative 2023 and wide intervals. Exploratory continuation only. |

The screenshot showed selected compression examples: SOL 1h long (7 trades, +0.894% net), ETH 15m short (8, +0.615%) and BTC 1h short (4, +1.346%). Those original results remain valid. They were not averages for the whole compression family, and the BTC example used the other stop/target arm.

The full compression family was already negative in the original discovery: -0.095% per trade with 2%/2.5%, before the later shared-position replay produced -0.0559%. The original family aggregation allowed overlapping configurations; the later replay admitted one position per token across clocks/sides. The screenshot's positive cells were already net of costs. No later addition of costs explains the apparent change.

The hourly subset of the latest primary basket averaged +0.4201% base / +0.2869% stress over 27 trades in 2025, with 11 stops; it also had positive historical 2022–24 means. Its confidence intervals cross zero. Lower-clock positions could block hourly entries, so this is not a standalone hourly strategy result.

## Latest completed follow-ups — 7 October 2026

Read `family_followups_20261007/FINDINGS.md` and its pre-scoring `PROTOCOL.md`
relative to the research root. Brian approved three focused hypotheses:
hourly compression, the extreme-funding predicate and 4h trend alignment.

Primary 2% stop / 2.5% target, reused 2025:

| Variant | Closed trades | Stops | Mean net base | Mean net stress |
|---|---:|---:|---:|---:|
| Hourly compression | 36 | 14 (38.9%) | +0.4992% | +0.3685% |
| Original extreme-funding breakout | 211 | 124 (58.8%) | -0.3952% | -0.5490% |
| Same breakout without the extreme-funding predicate | 1,462 | 800 (54.7%) | -0.2210% | -0.3663% |
| Trend pullback with aligned 4h regime | 220 | 115 (52.3%) | -0.1036% | -0.2440% |
| Original trend pullback | 361 | 193 (53.5%) | -0.1538% | -0.2927% |

Mean returns include terminal marks: two for funding, three for its comparator,
two for original pullbacks; none for hourly compression or aligned pullbacks.
Closed counts and stop fractions exclude marks.

Hourly compression alone meets the local continuation point criterion. Its
2022–24 mean is +0.2268% base / +0.1037% stress on 97 trades, but 2023 lost
money and confidence intervals cross zero. Historical stressed performance
turns negative without BTC. This remains exploratory, not a confirmed edge.
The 3%/3% hourly sensitivity has 35 closed 2025 trades, 14 stops and +0.3439%
base / +0.2126% stress. It changes both barriers.

Funding and trend-alignment hypotheses have no continuation support under
their frozen primary criteria. Record these comparisons as complete; no
automatic threshold sweep follows. Shock reversal and the learned rule remain
paused pending materially new hypotheses/data.

Validation: 108 original event groups, 57,728 unique raw barrier checks,
48 independent admission replays, 48 pooled/1,116 subgroup/96 annual/24 contrast
rows, and 36,488 ledger rows including alternative variants and cost scenarios.
The old 3,736-row compression basket reproduced exactly. Four focused tests pass.
A rejection-log integrity mismatch was reconstructed to its original recorded
hash exactly; the mismatched copy and recovery evidence are retained. No outcome
or entry rule changed in that recovery.

The private `MAR_entry_family_followups_checkpoint_20261007.zip` contains all
needed source, frozen features, detailed new evidence, prior comparator evidence,
reports and restore instructions. Only the separately saved original candle/
funding ZIP is needed as an external input. Its separate checkpoint-verification
JSON records archive hash and fresh restore checks.

Next: collect/audit additional-token data and predeclare a separate hourly
confirmation comparison before viewing new outcomes. Keep the original broader
all-clock primary protocol and its eight-new-token gate intact. Update the
candidate-set/multiplicity plan before independent confirmation. No new-token
test, 2026 price scoring, cloud change, leverage test or forward process started.

## Route from the current evidence

| Step and hypothesis | Experiment and fixed baseline | Decision after the test |
|---|---|---|
| Hourly isolation: the hourly compression lead survives independent occupancy replay. | Replay every unchanged 1h compression signal on BTC/ETH/SOL, both sides. Primary 2%/2.5%; 3%/3% remains separate sensitivity. Keep entry thresholds, data, costs, monthly eligibility, exits and token occupancy fixed. Restricting the entry clock is the one substantive change. Preserve all accepted/rejected signals and report every token/direction. | Positive stressed mean in both historical context and reused 2025 is a continuation criterion, not qualification. Inspect uncertainty and dependence on individual tokens/years. If negative or concentrated in a few observations, record failure or insufficient evidence; do not automatically sweep thresholds. |
| Generalization: the frozen entry works beyond the original three tokens. | Acquire and audit the additional-token universe using prior liquidity/history. Retain the original all-clock primary replication. Before opening new outcomes, register any hourly-only comparison as a separate hypothesis with its own support/uncertainty rules and a declaration that two hypotheses are being examined. | Apply each predeclared gate. A positive secondary does not erase a failed primary. The original replication requires at least eight new tokens plus its other frozen support, stressed-cost, confidence and provenance checks. Sparse evidence remains insufficient rather than being rescued by a changed threshold. |
| Selectivity, conditional on a supported candidate: a specific entry-time feature improves net expectancy. | Compare winners with losers using information available at entry: volume, RSI, volatility/trend and, in separately specified additions, ADX or Connors RSI. Discovery uses development data. Freeze one motivated filter and its threshold before its evaluation; compare with the unchanged entry baseline and account for lost winners and reduced opportunity count. | Keep a filter only if its benefit survives designated independent confirmation and stressed costs. Reused 2025 comparisons are diagnostic. If entry confirmation fails, do not stack filters indefinitely; close or pause the hypothesis and specify a materially different research branch. |
| Risk and exits, after entry support: a stop or profit-protection change improves the distribution of returns. | First hold TP fixed while comparing stops, then hold the initial stop/target fixed while testing one profit-protection rule. Compare identical raw entry opportunities and also replay the resulting occupancy. Measure stop-outs, pre-exit adverse/favorable paths, net expectancy and drawdown. | Retain improvements that survive the predeclared evaluation. Changing 2%/2.5% to 3%/3% is a combined barrier comparison, not proof about stop width alone. No maximum holding period is added by default. |
| Forward confirmation: historical performance survives actual availability and fills. | Freeze a candidate and collect forward paper observations, including rejected setups, spreads, fills, funding and overlapping exposure. Specify sample support and review dates before starting. | Operational observation is separate from strategy promotion. Account/margin/liquidation and correlated-loss modelling precede any leverage decision. No automatic live changes. |

Independent confirmation is essential. The original three assets and 2025 have been repeatedly examined. 2026 remains closed in this research line until a separate confirmation protocol is frozen and its prior exposure is audited; it must not be described as globally unseen merely because this experiment did not score it.

## Required experiment record

Before each run record:
- Hypothesis and the evidence that motivated it.
- Primary comparison; descriptive comparisons; unchanged baseline.
- Exact entry/exit rule, changed variable, assets, dates and costs.
- Data already examined versus reserved or new evidence.
- Sample/uncertainty criteria and the actions for supported, failed or inconclusive results.
- Protocol version, input/source hashes and execution status.

After each run report:
- All configurations, not only winners; trade counts, stops, target hits and terminal marks.
- Base/stressed net expectancy, win rate, uncertainty, token/timeframe/year contributions and admission exclusions.
- Whether the hypothesis was supported, rejected or remains inconclusive, and why.
- Exact proposed next step and the observation that justified it.
- Saved source, detailed trade evidence, concise public aggregates and updated handover.

A changed plan is recorded as a dated amendment before the next outcome is opened. Preserve the original hypothesis and result. Do not relabel an exploratory subset as a successful primary test.

## Evidence and preservation

- entry_discovery_20261006/FINDINGS.md and research_leads.csv: original five-family results and the positive screenshot examples.
- three_token_compression_20261007/PROTOCOL.md and FINDINGS.md: completed shared-position diagnostic.
- compression_replication_20261006/PROTOCOL.md: unchanged broader-token specification.
- entry_quality_audit_20261006/HANDOVER.md: full history and restoration instructions.
- Private MAR_three_token_compression_checkpoint_20261007.zip: exact source, frozen features, complete new ledgers and verification.

Hourly compression, the funding-predicate comparison and the 4h trend-alignment comparison are now completed. Broader-token confirmation, further entry filters, exit optimization and forward confirmation remain pending. The original frozen protocols and all failed results remain preserved.
