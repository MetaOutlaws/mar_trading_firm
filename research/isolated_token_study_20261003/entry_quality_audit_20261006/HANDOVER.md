# MAR research handover — updated 7 October 2026

Owner: Brian / Meta Outlaws. Repository: MetaOutlaws/mar_trading_firm.
Purpose: reproducible handover and restart without reconstructing the chat.


## Latest status: BTC / Connors interaction and paper approval — 8 October 2026 Dubai

Brian approved standalone Connors RSI for PAPER at 01:08 Dubai. This is the latest
paper preference: BTC/ETH/SOL LONG/SHORT, 1h, original compression plus CRSI(3,2,100),
LONG<=90 / SHORT>=10, SL2%/TP2.5%, no timeout. Preserve the prior BTC approval record
as history. No combined-filter, broader-token, live or leverage activation.

The next four-arm test is COMPLETE. Stressed average net returns per trade:

| Arm | 2022–24 trades / stops / mean | 2025 trades / stops / mean |
|---|---|---|
| Original | 97 / 44 / +0.1037% | 36 / 14 / +0.3685% |
| BTC only | 89 / 37 / +0.2825% | 35 / 13 / +0.4505% |
| Connors only | 60 / 26 / +0.1952% | 19 / 5 / +0.9205% |
| Both | 56 / 22 / +0.3849% | 19 / 5 / +0.9205% |

Both removes four additional historical stops without losing any Connors target
winner; 2025 admissions are identical to Connors. The predeclared requirement to
strictly improve over EACH standalone in BOTH periods therefore FAILS. Preserve
as historical incremental benefit, not independently validated regime behavior.
Point estimates favor the combination historically and tie Connors in 2025, but
owner approval remains standalone Connors; no silent switch to the stack.

Full research: hourly_btc_connors_interaction_20261008/{PROTOCOL,FINDINGS}.md and
results_v1. Protocol-before-scoring commit 6d2d4018935efb439e9acfe3e8b299976f2496f1.
143 verified cached raw paths, 286 raw cost rows reconciled; all three old arms
exactly reproduced (266/248/158 admitted cost rows), 16 independent admissions,
12 attribution checks. Ledger822 rows=(133 baseline+124 BTC+79 Connors+75 both)*2
costs, NOT822 independent trades. No2026 price outcomes. Reused2025 exploratory.

Runtime: standalone rule implemented, 17 focused tests pass, 143 full and143
rolling850-hour context checks pass, six full signal frames checked. Published
runtime commit c0d1328810d3e9d39a8bc1998eadb1b75205a8ee, draft PR101 stacked on PR100.
Installer replaces only six exact baseline paper records, preserves unrelated
approvals and positions, and verifies a subsequent healthy scan. Production
fills/exits/risk occupancy differ from the frozen research simulation.

CLOUD INSTALLATION/SCANNING NOT VERIFIED. DigitalOcean droplet605464227 is active;
this workspace's SSH to178.128.215.94 reports Network is unreachable. No shell
connector is available. Latest observed original scan remains
2026-10-07T10:05:31.385232+00:00. Run enable_hourly_connors_20261008.py through the
owner's Windows PowerShell SSH connection, then the --verify command in
ENABLE_HOURLY_CONNORS.md. Publication or installed_awaiting_cycle is not proof of
scanning_verified. No background monitoring/research by this chat.

NEXT RESEARCH: predeclare common causal trend/chop states and test the retained
H-EXT-REGIME-01 and H-RSI-REGIME-01 separately; retain H-BTC-CRSI-REGIME-01 alongside.
No calendar switches or blanket characterization of all2022–24/all2025. Then
broader-token and genuinely prospective confirmation when data become available.
More tokens may increase opportunities but do not guarantee transferable edge.

Restore the newest MAR_btc_connors_checkpoint_20261008.zip over the full original
MAR_hourly_compression_checkpoint_20261007.zip; raw data remain separate. Earlier
incremental evidence is included, so no previous increment also needs extraction.
Read RESTORE_BTC_CONNORS_STUDY.md. Older sections below are dated history and are
superseded by this latest status where operational preferences have changed.

## Historical record before latest approval: Connors RSI candidate, 8 October 2026 Dubai

Fixed LONG CRSI(3,2,100)<=90 / SHORT>=10 on ORIGINAL hourly compression,
same 2%SL/2.5%TP. Positive stressed mean and improvement both periods PASS.
2022–24 baseline 97 trades/44 stops/+0.2268% base/+0.1037% stress becomes
Connors 60/26/+0.3193%/+0.1952%. Directly avoids 19 stops and removes 19 targets;
one newly admitted ETH stop gives net 18 fewer actual stops.
2025 baseline 36/14/+0.4992%/+0.3685% becomes 19/5/+1.0580%/+0.9205%.
Nine original stops avoided, eight target winners excluded; no new/displaced
admissions. Win rate 61.11% to 73.68%. All token means improve both periods,
but historical ETH stays negative and shorts worsen in BOTH periods.

Historical confidence intervals span zero; 2025 four-week absolute/difference
intervals are positive but ONE-week intervals both span zero. This sensitivity
and only 19 trades in repeatedly inspected data limit confidence. Intervals
are unadjusted for multiple research attempts. No independent edge established.
Connors has higher 2025 but lower historical mean than BTC confirmation.
Retain PROMISING EXPLORATORY CANDIDATE; no automatic approval or combination.

Protocol-before-scoring commit fbc792125db770aad6a27182341f60cfd4ad29f2.
18 tests, 143 independently reconstructed contexts/barriers and anatomy equality,
eight admissions, exact baseline and 150 report rows verified. One successful
results_v1. Read hourly_connors_filter_20261008/{NOVELTY_AUDIT,PROTOCOL,FINDINGS}.md.
Ledger 424 scenario rows = (133 baseline+79 Connors)*2 costs; excluded CSV 110 rows
= 55 original admissions*2 costs. No 2026 price feature/outcome scored.

## Owner regime-use note retained

H-RSI-REGIME-01 now explicitly preserves Brian's potential use of RSI when
observable conditions resemble the historical sample. Read RSI REGIME_FOLLOWUP.md.
Label HISTORICAL IMPROVEMENT (2022–24), REGIME EXPLANATION UNVALIDATED.
H-EXT-REGIME-01 remains intact. Neither year range is a trading state; 2023 and
token counterexamples remain visible. No conditional switch tested/deployed.

## Current paper preference and cloud status

BTC24 confirmation remains OWNER-APPROVED preferred PAPER variant. Connors is
a new research candidate, not an automatic replacement. Read BTC OWNER_APPROVAL.md.
BTC activation PENDING / NOT VERIFIED. Latest observed operational cycle remains
original baseline 2026-10-07T10:05:31.385232+00:00, six configurations, errors [].
No new SSH monitoring, approval-book/runtime/live/leverage change. Existing
paper approval persists; preserve positions and avoid duplicate entries when
eventually implementing/activating the exact approved predicate and verifying it.

## Next research priority, updated because Connors passed

1. NEXT: freeze one four-arm interaction comparison: original baseline, BTC24
   only, Connors only, both fixed filters. Require incremental value versus BOTH
   standalone candidates, not merely the original baseline. Study overlap in
   excluded stops/winners and replay all raw opportunities. Unscored/unfrozen.
2. THEN: H-EXT-REGIME-01 and H-RSI-REGIME-01, common causal states across both
   periods, each fixed filter separately. Exact states remain unscored/unfrozen.
3. WHEN AVAILABLE: broader-token/prospective confirmation. Reserved 2026 unscored.
   No cutoff rescue, automatic stacking or background research running.

Restore MAR_connors_filter_checkpoint_20261008.zip over the full original
MAR_hourly_compression_checkpoint_20261007.zip. All previous increments and
BTC owner approval included; previous increments need not also be extracted.
Keep raw inputs separately; read connors_filter_handover/RESTORE_CONNORS_STUDY.md.
Older sections below are dated history superseded by this latest status.

## Previous completed: independent RSI exhaustion exclusion, 8 October 2026 Dubai

Fixed LONG RSI14<=70 / SHORT RSI14>= 30 on the ORIGINAL hourly compression
baseline. Both periods stay positive after stressed costs, but improvement in
both FAILS. Historical improvement retained; regime explanation UNVALIDATED.
2022–24: baseline 97 trades/44 stops/+0.2268% base/+0.1037% stress; RSI 69/29/
+0.3727%/+0.2445%. Directly excludes 16 stops and 13 targets; one new ETH stop
means net 15 fewer stops. 2023 and historical SOL worsen; ETH remains negative.
2025: baseline 36/14/+0.4992%/+0.3685%; RSI 35/14/+0.4480%/+0.3164%.
Zero stops avoided and one BTC SHORT target excluded; no added/displaced entry.
The one excluded winner (2025-03-09 11:00 UTC, RSI 28.4743) explains the difference.

Protocol published before scoring at 0d86fcd168518e405d26835e2749b5537a3ea72c.
Earlier pre-scoring commit 28c3da989a518dbf161c108893cbffbd2bb957d4 corrected its
RSI provenance wording before freeze; same definition as original anatomy.
15 tests, 143 independently reconstructed contexts/barriers, original-feature
equality, eight admissions, exact baseline and 152 report rows verified.
Read hourly_rsi_filter_20261008/{NOVELTY_AUDIT,PROTOCOL,FINDINGS}.md.
Single successful run results_v1. Ledger 474 scenario rows = 133 baseline +104
RSI admissions, both costs; excluded ledger 60 scenario rows = 30 admissions.

## Paper preference and operational status

BTC24 confirmation remains OWNER-APPROVED preferred paper variant. Read
hourly_btc_confirmation_20261007/OWNER_APPROVAL.md. Approval does not establish
independent edge or cloud activation. Activation PENDING / NOT VERIFIED;
latest observed operational cycle still original baseline at
2026-10-07T10:05:31.385232+00:00, six hourly configurations, errors []. No fresh
SSH monitoring or runtime edit is claimed. Already-granted paper approval
persists; implement/activate exact predicate, avoid duplicate entries, preserve
positions and verify scan before claiming deployment. No live/leverage change.

## Active research queue

1. NEXT: audit/freeze one Connors RSI predicate against ORIGINAL hourly baseline.
   No implicit BTC, ADX, RSI or extension stacking. Exact rule unscored/unfrozen.
2. THEN: review H-EXT-REGIME-01 and separately preregister causal state definitions
   if testing a regime explanation for retained historical observations. Neither
   calendar 2022–24 nor 2025 is itself a market-state rule. Extension and RSI
   historical improvements remain documented with their later failures.
3. WHEN AVAILABLE: additional-token/prospective confirmation. Reserved 2026 is
   unscored. No background research runs and no cutoff rescue.

Restore MAR_rsi_filter_checkpoint_20261008.zip over the full original
MAR_hourly_compression_checkpoint_20261007.zip. It includes all prior increments,
BTC owner approval and the RSI study. Prior increments need not also be applied.
Keep raw data separately. Read rsi_filter_handover/RESTORE_RSI_STUDY.md.
Older sections below are dated history superseded by this latest status.

## Previous completed: independent ADX strength gate — 7 October 2026

ADX14>=25 on the ORIGINAL hourly baseline fails consistent improvement.
Protocol-before-scoring commit 1cc0931d185ca586d2f5cca9d5274e2431eca41f.
2022–24: baseline 97 trades /44 stops /+0.2268% base /+0.1037% stress;
ADX 39 /22 /-0.2724% /-0.3931%. It excludes 22 original stops and38 targets,
then admits two additional target winners. Stop rate worsens45.36% to56.41%.
2025: baseline36 /14 /+0.4992% /+0.3685%; ADX8 /3 /+0.5874% /+0.4874%.
It excludes11 stops and18 targets, then admits one new BTC winner. The seven
retained original entries have a LOWER mean than baseline; the extra winner
produces the improved actual mean. Positive2025 evidence is retained with its
thin sample: seven BTC trades, one ETH target and zero SOL trades.

Every historical ADX year is negative; absolute/difference intervals cross zero.
15 tests,143 independent ADX contexts/barriers, eight admissions, exact baseline
reconciliation and144 report rows passed. Ledger360 scenario rows =133 baseline
+47 ADX admissions at two costs. Read hourly_adx_filter_20261007/{NOVELTY_AUDIT,
PROTOCOL,FINDINGS}.md. Single completed scoring attempt results_v1.

## Current owner-approved paper preference and deployment status

Brian approved btc24_confirm as the preferred current hourly paper variant on
7 October 2026 at 23:18 Dubai time. Read
hourly_btc_confirmation_20261007/OWNER_APPROVAL.md. Scope: original hourly
BTC/ETH/SOL both directions,2% SL/2.5% TP; ETH/SOL must agree with completed
BTC24 sign; BTC entries unchanged. Paper approval persists for later activation.
Do not conflate the owner's decision with statistical proof: independent edge
is unestablished and 2025 benefit comes from one excluded SOL stop.

Cloud activation of BTC confirmation is PENDING / NOT VERIFIED. This research
task did not install it or edit the cloud approval book. Latest operational
evidence remains the original six-sleeve baseline scan at
2026-10-07T10:05:31.385232+00:00, errors []. No fresh SSH monitoring is claimed.
Operational follow-up: implement/activate the exact approved BTC predicate,
avoid duplicate baseline/variant entries, preserve positions and verify scanning
before recording deployment complete. Do not ask again for already granted
paper-variant approval. Live trading or leverage was not authorized here.

## Active research queue

1. NEXT: one separately audited/frozen RSI predicate against the ORIGINAL baseline.
2. THEN: independent Connors RSI predicate, same controls and execution.
3. REVISIT: H-EXT-REGIME-01 with causal state definitions across both periods.
   Extension cap retains its historical 2022–24 improvement label; regime
   explanation is unvalidated. No calendar period is treated as a regime rule.
4. WHEN DATA RETURNS: broader-token and prospective confirmation of retained
   candidates. Reserved 2026 remains unscored. No filters stacked implicitly.

Preserve both positive and negative observations; current ADX's positive 2025
sample does not erase its failed historical screen. Later predicates remain
unfrozen/unscored and no next study runs in the background. Older dated status
sections below describe earlier decisions and are superseded by this section.

Restore MAR_adx_filter_checkpoint_20261007.zip over the full
MAR_hourly_compression_checkpoint_20261007.zip. It includes all earlier research
increments, the BTC owner approval and this ADX study. Keep original raw data
separately; previous increments need not also be extracted. Read
adx_filter_handover/RESTORE_ADX_STUDY.md.

## Previous completed: BTC direction confirmation — 7 October 2026

PROMISING EXPLORATORY CANDIDATE. ETH/SOL hourly LONG requires BTC24 > 0;
SHORT requires BTC24 < 0, using completed hourly closes. BTC entries unchanged.
Original 2% stop / 2.5% target, fees/funding, slippage and occupancy retained.
Protocol-before-scoring commit a4ce9d72ca67e7483fea78b1b436cf925fa80a3c.

Full basket 2022–24: baseline 97 trades / 44 stops / +0.2268% base / +0.1037%
stress; confirmed 89 / 37 / +0.4017% / +0.2825%. Seven stops avoided and one
target sacrificed. 2025: baseline 36 / 14 / +0.4992% / +0.3685%; confirmed
35 / 13 / +0.5791% / +0.4505%, with one SOL stop avoided and zero winners lost.
ETH/SOL stressed means improve -0.0580% to +0.2343% historically and +0.4077%
to +0.5692% in 2025. No new or displaced admissions; BTC paths unchanged.

Both affected-subset and full-basket point screens pass. However, the entire
2025 gain comes from ONE trade, historical ETH and 2023 remain negative, and
absolute mean intervals cross zero. Independent edge/deployment qualification
remain false. Retain the candidate; the approved paper baseline stays unchanged.

15 tests; 143 independently verified BTC contexts and143 barriers; eight
admission replays; exact baseline and BTC reconciliation; 180 report rows passed.
514 cost-scenario rows =133 baseline +124 confirmed admissions at two costs,
with overlapping arms. Read hourly_btc_confirmation_20261007/{NOVELTY_AUDIT,
PROTOCOL,FINDINGS}.md. results_v1 is the single completed scoring attempt.

## Preserved owner observation: extension cap and regimes

Label the extension cap HISTORICAL IMPROVEMENT (2022–24), REGIME EXPLANATION
PENDING. Historical stressed mean rose +0.1037% to +0.1834%, but 2025 worsened.
Keep this evidence under H-EXT-REGIME-01 in
hourly_extension_filter_20261007/REGIME_FOLLOWUP.md. The unconditional rejection
does not erase its historical benefit. No causal market-state rule is tested
yet and no finding says all of 2025 was choppy. Calendar periods are not regime
definitions; the cap's 2023 result worsened. A future separately registered
study must compare common, entry-time states within both periods.

## Active queue

1. NEXT: audit/freeze one ADX condition against the ORIGINAL hourly baseline.
2. THEN: RSI and Connors RSI independently, with predeclared definitions/cutoffs.
3. REVISIT: H-EXT-REGIME-01 after these context studies, using one causal state
   definition and an explicit separate protocol. Preserve both positive and
   negative cells; don't choose a regime using eventual winning trades.
4. WHEN DATA RETURNS: broader-token replication and confirmation of retained
   candidates. Prospective paper evidence stays separate; reserved 2026 unscored.

Do not stack the BTC condition or extension cap into the next comparison.
Later predicates are not frozen, scored or running in the background. Every
test reports trade/stop counts and rates, excluded winners, costs, uncertainty,
and token/year concentration. Earlier dated next-step sections are historical.

Latest observed cloud cycle remains 2026-10-07T10:05:31.385232+00:00, six hourly
BTC/ETH/SOL LONG/SHORT paper configurations, errors []. No fresh SSH observation
or runtime/approval change is claimed.

Restore MAR_btc_confirmation_checkpoint_20261007.zip over the full
MAR_hourly_compression_checkpoint_20261007.zip. This increment includes both
exit studies, sweep, extension (with the regime note), and BTC confirmation.
Keep the original raw candle/funding ZIP separately. Previous increment ZIPs
need not also be extracted. Read btc_confirmation_handover/RESTORE_BTC_STUDY.md.

## Previous completed: hourly breakout-extension filter — 7 October 2026

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


## Start here

## Latest completed: fixed failed-breakout exit — 7 October 2026

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
admission replays, 266 exactly reconciled baseline rows, 1, 330 alternative
ledger rows. Six implementation tests pass; 143 research entry signals and
1,734 rolling candidate checks match. No new token or 2026 price scoring.

At this earlier stage, the queued research was a profit-protection comparison with unchanged
hourly entries and initial 2%/2.5% barriers, counting winners cut short as well
as stopped-trade profits saved. That comparison has since completed; see the latest section above. New-token confirmation remains
pending. None of the old negative family findings or positive hourly findings
has been overwritten. Older status sections below describe their dated stages.


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


Read [RESEARCH_ROADMAP.md](../RESEARCH_ROADMAP.md) for the current hypothesis sequence, decisions and experiment reporting rules. The three focused follow-ups are complete; only hourly compression met the local continuation point criterion. The prior positive examples were selected configurations, while the full-family and shared-position tests were negative.

Read the latest completed experiment below first; the older stages follow.

## Earlier completed three-token basket — 7 October 2026

Brian authorized a local BTC/ETH/SOL diagnostic while additional-token data
were unavailable. Read `three_token_compression_20261007/FINDINGS.md` relative
to the research root, and its frozen scope amendment `PROTOCOL.md`.

- All three entry clocks (5m, 15m, 1h), both sides, unchanged compression entry;
  full raw opportunities replayed under shared per-token occupancy.
- Pooled 2025 primary 2% SL / 2.5% TP: 222 closed trades, 114 stops (51.35%),
  mean net -0.0559% base / -0.1839% stressed slippage. No terminal mark.
- Pooled 3% SL / 3% TP: 196 entries, 195 closed, 102 stops (52.31% of closed),
  one terminal mark; mean net -0.3885% base / -0.5196% stress including the mark.
- Both arms negative in historical 2022–24 too. No qualified strategy.
- Admitted 1h primary subset: 27 evaluation trades, 11 stops, +0.4201% base /
  +0.2869% stress. Confidence intervals cross zero. This is a post-review
  descriptive subset of the shared basket, not a separately replayed 1h system.
- Original 216 compression cells reconciled; four focused tests passed.
  Eighteen signal groups, 2,992 independent raw barrier checks, eight admission
  replays and 232 pooled/subgroup/annual summaries verified; 3,736 ledger rows
  include alternative arms and duplicated base/stress scenarios.
- 2026 remains unscored. Zero new tokens. No production or leverage changes.

`MAR_three_token_compression_checkpoint_20261007.zip` contains the full source
needed for this run, the nine frozen feature files, all new evidence, reference
verification and restoration instructions. It requires only the separately
saved original `isolated_token_study_1m_2022_20261002_v2.zip` for raw candles and
funding; older evidence archives remain available for earlier research stages.
The new archive's `CHECKPOINT_SHA256SUMS.json` and `verify_checkpoint.py` verify
its payload. Its outer SHA256 and published commit are in the separate
`MAR_three_token_compression_checkpoint_verification_20261007.json`.

Additional-token acquisition remains pending. No Grok/SSH/cloud collection was
started from this workspace. If pursuing 1h alone, freeze a new hypothesis and
replay all hourly signals before independent new-asset/forward confirmation.
Do not treat this three-token diagnostic as passing the original eight-new-token gate.


1. Read ../compression_replication_20261006/RUN_STATUS.md for the latest work:
   broader-token protocol/collector/runner are prepared and verified, but new
   market-data acquisition is blocked in this workspace. No new-token result.
   Read ../entry_discovery_20261006/FINDINGS.md for the latest completed entry research.
   Compression expansion has sparse positive leads, but 0/180 new configurations
   passed the frozen screen. 2026 remains unscored in that experiment.
   Read FINDINGS.md for the primary-audit result, SECONDARY_FINDINGS.md for
   the completed 1h/24h audit, COSTED_FINDINGS.md for the completed matched
   costed-opportunity diagnostic, and ../breakout_retest_20261006/FINDINGS.md
   for the completed standalone breakout/retest experiment. No entry qualified.
2. Read each frozen protocol and RECONSTRUCTION_AMENDMENT.md before rerunning.
   Protocol status text describes the pre-run state; this handover tracks completion.
3. Use the private checkpoint archive for complete code, detailed evidence and
   historical files. Public GitHub contains reports, protocols and aggregates;
   it is not the only copy of the research evidence.

## Durable artifacts

| Artifact | Purpose | Verification |
|---|---|---|
| isolated_token_study_1m_2022_20261002_v2.zip | Original BTC/ETH/SOL data and funding, saved privately | SHA256 below; 17 ZIP members pass CRC |
| MAR_research_checkpoint_20261006.zip | Updated research code/evidence, reconstruction, primary and secondary comparisons, breakout/retest results and pinned report snapshots | SHA256SUMS.json verifies every packaged payload; previous saved version retained |
| MAR_entry_discovery_checkpoint_20261006.zip | Incremental discovery code/evidence, features, training labels, signals, ledgers, report snapshot and updated handover; restore alongside the base checkpoint | DISCOVERY_SHA256SUMS.json and verify_discovery_checkpoint.py; base archive SHA recorded below |
| individual_trades_reconstructed.csv.gz | 38,469 reconstructed baseline positions, base costs | Reconstruction manifest and 72-row published reconciliation |
| prediction_v1/primary_summary.csv | 36 period-specific primary results, CIs, coverage and flags | Prediction manifest |
| prediction_v1/paired_signals.csv.gz | Every matched signal and mean control result | Prediction manifest |
| prediction_v1/control_draws.csv.gz | All 1,126,166 control draws, including reuse | Prediction manifest |
| prediction_v1/excluded_signals.csv.gz | Unmatched/censored signal reasons | Prediction manifest |
| secondary_v1/ | 1h/24h observations, all matches/exclusions, 216 result rows | Secondary manifest |
| costed_v1/ | 144 matched costed comparisons, complete outcomes/draws/pairs/exclusions and cost attribution | Run manifest and COSTED_REPORT_VERIFICATION.json |
| ../breakout_retest_20261006/results_v1/ | 576 costed result rows, 140,120 ledger rows including both costs, setups and 432 control contrasts | Run manifest and REPORT_VERIFICATION.json |
| published_snapshot/ | 23 research files retrieved from pinned GitHub commit | Snapshot index and package hashes |
| published_stage2_snapshot/ | Exact newly published reports, protocols and aggregate tables | Package hashes and ARTIFACT_INDEX.json |
| published_costed_snapshot/ | Latest costed protocol, findings, aggregates and updated handover | Package hashes and ARTIFACT_INDEX.json |

Base research checkpoint (costed stage, saved version 2) SHA256:
`7d357d4b5176d8190ee8efdd42fb3a6bd02a0b2c94262dc8b04ea04c49d9dc92`

Original data ZIP SHA256:
`344ac29b5b2ee2fe9ba5966026914489dc22dfaed75374fbe86316052da863dc`

Pinned public report commit:
`f55bcac0cdd8e3c82768205958424a99e14f4582`

Important version distinction: the PR98 description was stale at recovery and
still called fixed-stop work queued. The published fixed-stop, adaptive-stop,
standalone-zone and winner-diagnostics files describe later completed work.
Use their contents and the pinned snapshot, not the old PR description.

## What is complete

- Six original candle/funding hashes verified; no new data substitution.
- 57 earlier artifact/hash/archive checks passed.
- Standalone-zone reconstruction: 38,469 positions; all 72 published 2025
  configuration rows match counts exactly and returns/PF within report rounding.
- Primary matched-entry audit: 58,687 matched signals; 36 period results;
  0/18 groups pass the frozen two-period gate.
- Two focused implementation checks passed by direct Python invocation.
- Secondary 1h/24h diagnostic: 117, 310 matched signal-horizon observations,
  2,251,014 control draws, 216 result rows. Primary failure unchanged.
- Standalone breakout/retest: 0/36 configurations pass. All 36 have negative
  discovery mean net return. The three controls also have no passing configuration.
- Five additional focused tests passed (one secondary-window and four setup-state
  tests). All 144 control reconciliations passed; all 576 summary rows match
  their ledgers and respect position occupancy. Sixteen frozen output hashes verified.
- Matched costed-opportunity diagnostic: 58,690 of 59,617 zone signals matched;
  1,126,229 control draws and 144 arm/period/cost contrasts. Pooled 2025 zone
  net returns are -0.4402% and -0.4295%, below matched controls in both arms.
  All discovery arm/group means are negative; the failed primary gate is unchanged.
- Two costed-diagnostic implementation tests passed. All 72 chronological
  reference checks passed; report verification checked 184 frozen output hashes
  and all 144 contrasts against saved outcomes, matched pairs and weights.

- Distinct entry discovery: 180 new configurations plus 72 controls across 5m,
  15m and 1h, both directions and two stop/target arms; 1,512 result rows.
  13 configurations positive in all three historical partitions at normal costs,
  six at doubled slippage, but 0 pre-2025 finalists. Compression supplies five
  of those six sparse stressed-cost leads. No 2026 scoring or strategy promotion.
- Reverse engineering: three depth-two trees and 1,688,248 overlapping training
  opportunities; best selected training regions remained negative after costs.
- Four focused discovery tests passed. Verified 114 frozen output hashes, five
  frozen sources, 3,528 period/annual summaries against 390,696 ledger rows,
  every ledger's occupancy and every training label's pre-2024 dates.

Original row-level identity is not proven. The reconstructed export does not
claim to reproduce the former feature-enriched CSV column for column.

## Broader-token replication setup

Brian approved scaling the unchanged compression entry across a broader token
universe, accepting low per-token trade frequency. PROTOCOL.md freezes monthly
selection of up to 15 new tokens using prior liquidity and listing history.
The primary pooled test uses 2% SL/2.5% TP across all three clocks and both sides,
one position per token, six overall and three per direction. The 3%/3% arm is
descriptive. Historical universe/funding provenance and statistical evidence
are required before qualification; leverage remains untested.

A resumable public-data collector, input validator and offline runner are ready.
Four focused tests passed and 216 prior compression cells reconciled. Direct
Bybit access returned a non-JSON Site Unavailable page, including the collector
preflight. No collector has been launched on Singapore from this workspace.
The private MAR_compression_replication_kit_20261006.zip includes code, protocol,
verification and exact RUN_ME.md instructions. It is a code/readiness package,
not a replacement for the two previous full evidence checkpoints or source data.

## Pending, not running in the background

- Broader-universe replication of the frozen compression entry and historical
  open-interest/liquidation/flow data acquisition; neither has run.
- Separate profit-protection comparison (deferred by Brian's entry-research priority).
- The cost-aware minimum zone-target-distance fallback remains unverified as
  completed; check evidence before asserting it has run.
- Fresh confirmation of any future selected strategy. 2025 is already reused.

Existing ATR-cap comparisons have already been completed and failed their
screen. A new adaptive-stop experiment must name a genuinely different
hypothesis; do not silently repeat or relabel the old test.

The latest breakout/retest rule is closed with a failed screen; do not tune its
lookback, ATR band or expiry merely to make a historical cell survive. The latest
entry-discovery experiment is also complete; its positive examples are exploratory
and were highlighted after reviewing 2025. Preserve the exact compression rule
for broader replication; do not tune it to force a historical finalist. The planned profit-protection
test must keep reference entries, initial stop/target and regime exit fixed,
and replay occupancy to measure both saved profits and winners cut short.
More model credits do not change sample independence. Reserve unused data for
eventual confirmation.

## Restart instructions

Extract MAR_research_checkpoint_20261006.zip (base version 2) into a new directory
and run its verify_checkpoint.py BEFORE applying the discovery supplement.
Then extract MAR_entry_discovery_checkpoint_20261006.zip into that same directory
and run verify_discovery_checkpoint.py. The supplement updates START_HERE.md and
the research HANDOVER.md, so the old base hash check is expected to differ for
those files after applying it; its separate original archive remains unchanged.
Extract the original source ZIP into `data_cache/` there. Use Python 3.12; the
recorded run used 3.12.14. The base archive and source data are separately indexed
in DISCOVERY_ARTIFACT_INDEX.json.

```bash
python -m pip install -r research/isolated_token_study_20261003/entry_quality_audit_20261006/requirements-audit.txt
python verify_discovery_checkpoint.py
python research/isolated_token_study_20261003/entry_quality_audit_20261006/audit_inputs.py --cache data_cache
```

Fresh reconstruction (output directory must not already exist):

```bash
python research/isolated_token_study_20261003/entry_quality_audit_20261006/reconstruct_zone.py --cache data_cache --out rerun_reconstruction --published published_snapshot/research/isolated_token_study_20261003/standalone_zone_20261006/FINDINGS.md
```

Fresh primary diagnostic:

```bash
python research/isolated_token_study_20261003/entry_quality_audit_20261006/run_prediction.py --cache data_cache --reconstructed rerun_reconstruction --out rerun_prediction
```

Fresh secondary and breakout/retest runs, each into a new directory:

```bash
python research/isolated_token_study_20261003/entry_quality_audit_20261006/run_secondary.py --cache data_cache --reconstructed rerun_reconstruction --out rerun_secondary
python research/isolated_token_study_20261003/breakout_retest_20261006/run_breakout.py --cache data_cache --reconstructed rerun_reconstruction --out rerun_breakout
```

Fresh entry discovery (also needs scikit-learn 1.8.0):

```bash
python -m pip install scikit-learn==1.8.0
python research/isolated_token_study_20261003/entry_discovery_20261006/run_discovery.py --cache data_cache --reconstructed research/isolated_token_study_20261003/entry_quality_audit_20261006/reconstruction_v1 --out rerun_entry_discovery
```

Fresh costed-opportunity diagnostic:

```bash
python research/isolated_token_study_20261003/entry_quality_audit_20261006/run_costed.py --cache data_cache --reconstructed rerun_reconstruction --out rerun_costed
```

Costed opportunities overlap and do not enforce position occupancy. Their counts
and mean returns are not a portfolio replay. The chronological pass in that runner
is solely a reference check. Do not mistake costed-summary rows or reused control
draws for independent executed trades.

The report generator reads the archived `results_v1` and `secondary_v1` paths;
it is a report/checking utility, not the scoring runner. All entry clocks remain
5m, 15m and 1h. The completed 4h regime is context; 1h/4h/24h outcome horizons
are measurements, not holding caps. This stage did not test the expansion tokens.

The scripts reject changed raw input hashes. Preserve any failed run directory
and its error reason; use a new directory for a corrected invocation.
No elapsed-time promises or background execution are implied by this handover.

## Operating boundaries

Research remains separate from the Singapore cloud paper scanner. Do not copy
an old local approval file onto the server: the cloud approval book differed
from GitHub when checked. No production code, orders, stops, targets, worker
settings or approvals were changed during this recovery/audit.

Never archive credentials, API keys, SSH private keys or environment secrets.
Share the private checkpoint with a named handover recipient only when Brian
authorizes that disclosure. Nothing in this handover grants live-trading rights.

## Required practice for each later experiment

Freeze a protocol; record input/code hashes and package versions; retain every
attempt, negative result and exclusion; export full ledgers plus concise tables;
save a checkpoint; reopen it and verify its manifest; publish permitted reports;
update this status register with completed, pending and blocked work separately.
Do not mark an experiment complete merely because code or a plan was saved.
