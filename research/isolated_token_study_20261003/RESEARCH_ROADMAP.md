# MAR entry research: living roadmap and hypothesis register

## Latest completed: fixed-strategy 2026 replication, 8 October 2026

H-2026-REPLICATION-01 is complete. The approved PAPER rule remains
`hourly_compression_btc_connors_loweff_v1`: hourly compression + BTC confirmation
+ Connors + a one-ATR extension cap only when prior ER24<0.30; BTC/ETH/SOL,
LONG+SHORT, SL2%, TP2.5%, no timeout. No runtime/approval change was made.

**Positive point replication:** 9 trades, 8 targets, 1 stop-out (11.11%), 88.89%
closed win rate. Mean net return is +1.7240% at base costs and +1.5689% at doubled
slippage. No boundary marks, ambiguous exits or admission rejections. Nine trades
across seven entry dates/seven calendar weeks; 18 exported rows are the SAME nine
trades under two cost assumptions, not 18 independent observations.

| Period | Trades | Stops | Targets | Win rate | Stressed mean net/trade |
|---|---:|---:|---:|---:|---:|
| 2022–24 | 41 | 15 | 26 | 63.41% | +0.5003% |
| 2025 | 15 | 3 | 12 | 80.00% | +1.1993% |
| 2026 reserved interval | 9 | 1 | 8 | 88.89% | +1.5689% |

Interval: 1 January 2026 00:00 UTC through 2 October 2026 16:00 UTC exclusive.
Last eight candle hours omitted based on funding coverage before scoring. No
carry-in positions; pre-2026 data used only as causal warm-up for this replay.

This is a **temporal replication, not an untouched holdout**: original PR92 exposed
full-span future-path opportunity summaries including 2026, and external Grok use
is unknown. The current sequence had no saved 2026 strategy trades before this
run. Raw funding provenance remains provisional; it matches the approved sequence.

Stressed 95% bootstrap intervals for the mean: one-week blocks +0.2505% to +2.0922%;
four-week blocks -0.1300% to +2.0857%. The latter includes zero.
Both point means are positive; the predeclared stronger interval check does not
pass. This supports continued paper evaluation, not certainty or leverage readiness.

Protocol-before-scoring commit `988bb74b17854704c7fc4094f5577619d017726c`.
Historical preflight reproduced all120 approved opportunity cost rows and112
admitted cost rows (56 trades). New run verified30 independent entry contexts,
six runtime signal frames/39,552 hour-side decisions,30 trailing850-hour decisions,
all9 minute barrier paths,18 independent cost calculations and two admissions.
Four bootstrap intervals were independently reconstructed. One successful 2026
run, results_v1; initial historical-only adapter failure is preserved separately.

NEXT: verify actual paper installation/scanning and compare subsequent signal/fill
logs with the frozen rule; collect forward observations without tuning on them.
Use the preregistered broader-token replication when additional data arrive.
2026 has now been opened: any further optimisation on it is exploratory. No new
filter sweep, live/leverage change or background monitor was started. Cloud
activation is still unverified here; GitHub publication is not operational proof.

Read hourly_reserved_2026_20261008/FINDINGS.md and PROTOCOL.md in PR99. Restore the
original hourly base then MAR_2026_replication_checkpoint_20261008.zip; this increment
includes preceding increments. Older notes below describe historical work and do
not override this current status.

Updated 7 October 2026. Owner: Brian / Meta Outlaws.
Objective: identify positive net expectancy that survives execution costs and independent confirmation, then improve risk and exits. Fewer trades are acceptable; support may be pooled across tokens without assuming those tokens are independent.

## Latest completed: RSI by market state, 8 October 2026

H-RSI-REGIME-01 is complete. The approved PAPER strategy remains
hourly_compression_btc_connors_loweff_v1: BTC+Connors with a one-ATR extension cap
only when pre-signal ER24<0.30. BTC/ETH/SOL both directions,1h,SL2%/TP2.5%,no timeout.
Runtime code commit3c226bca19cca1c771bcb2ed637f9ec39f74c432 in PR101. Cloud installation
and scanning remain unverified here and require Grok’s actual operational evidence.

Four added-RSI policies tested with RSI14 LONG<=70/SHORT>=30, same ER cutoff and
all other assumptions fixed. Stressed results:

| RSI policy | 2022–24 trades / stops / mean | 2025 trades / stops / mean |
|---|---|---|
| None, approved benchmark |41 /15 /+0.5003%|15 /3 /+1.1993%|
| Always |38 /14 /+0.4914%|15 /3 /+1.1993%|
| Directional only |38 /14 /+0.4914%|15 /3 /+1.1993%|
| Low-efficiency only |41 /15 /+0.5003%|15 /3 /+1.1993%|

Always/directional removes one historical stop and two target winners. No new
or occupancy-displaced trades. Low-efficiency changes no raw opportunities or
admissions. All2025 variants are identical. No policy passes the frozen benefit
screen, so no RSI14 addition or retuning. Differences’ intervals include zero.
The approved rule’s earlier positive results remain intact.

Protocol-before-scoring commit7088e063ff876fd7b0c3b9d1c142433be698120c. One successful
run results_v1.23 focused tests;143 independent RSI+143 ER contexts;286 raw cost
rows reconciled;120 approved opportunity/112 approved admission cost rows matched;
16 independent admissions,12 attributions and28 report-row checks.436 overlapping
arm/cost rows, not independent trades. No2026 outcomes or new token scores.

NEXT: independent confirmation. First audit whether the reserved2026 BTC/ETH/SOL
interval is genuinely unused and has sufficient coverage, then preregister a
separate fixed-strategy validation before scoring. If already used, label it
exploratory. Broader-token validation remains queued until data arrive. Prospective
paper observations begin after verified deployment. No new filtering experiment
or background monitor was started in this turn.

Read research/isolated_token_study_20261003/hourly_rsi_regime_20261008/FINDINGS.md,
PROTOCOL.md and results_v1. Restore the original hourly base, then the newest
MAR_rsi_regime_checkpoint_20261008.zip. Old included status/approval notes are
historical where this latest handover supersedes them. Both requested6October
original ZIPs retain their verified bytes and separate identities.

---

## Historical approval checkpoint before the RSI regime study — 8 October 2026 08:39 Dubai

BTC + Connors + LOW-EFFICIENCY-ONLY one-ATR extension cap is now the approved
PAPER deployment. Strategy hourly_compression_btc_connors_loweff_v1. ER24<0.30
before the signal hour applies the cap; ER>=0.30 does not. BTC/ETH/SOL both
sides,1h,SL2%/TP2.5%,no timeout. Read hourly_extension_regime_20261008/
OWNER_APPROVAL.md and the current root GROK_START_HERE.md. All earlier hourly
selection instructions below are historical and superseded.

Runtime prepared in PR101;43 targeted tests and143 full+143 rolling context
checks pass. Cloud installation/scanning remains NOT VERIFIED here. Grok must
use scripts/install_hourly_btc_connors_loweff_20261008.py, then verify a fresh
healthy hourly cycle. Preserve other strategies, positions and their exits.

Approved stressed results:2022–24 41 trades/15 stops/+0.5003% mean;2025 15 trades/
3 stops/+1.1993%. No-cap comparison56/22/+0.3849% and19/5/+0.9205%. Confidence
intervals for improvement include zero; no claim of independent/certain edge.

Both exact6October checkpoint archives were recovered and internally verified.
Release upload remains pending because this connector cannot upload release
assets. See handover/checkpoints_20261006 in PR99 for hashes and the authenticated
Grok upload helper; no archive upload is claimed. Owner has direct downloads.

No new research experiment this turn. RSI regime study remains queued; freeze
its next protocol using the newly approved benchmark before scoring. The old
extension-regime research sources/results remain unchanged.

---

## Historical 08:11 approval and research snapshot: BTC + Connors; extension-regime test complete — 8 October2026 Dubai

CURRENT OWNER-APPROVED PAPER DEPLOYMENT IS BTC + CONNORS. Brian's08:11 Dubai
instruction supersedes standalone Connors. Read hourly_btc_connors_interaction_20261008/
OWNER_APPROVAL.md. BTC/ETH/SOL, both directions,1h,SL2%/TP2.5%,no timeout; own
CRSI(3,2,100) LONG<=90/SHORT>=10, ETH/SOL confirmed by matching completed BTC24
return sign; BTC unchanged. No live/leverage/new-token approval.

Runtime is implemented in PR101, branch codex/hourly-connors-paper-20261008,
commit b7a4178a299273ae86fc1630aa9feea882ed6d3b. Read root GROK_START_HERE.md.
37 targeted tests pass;143 full+143 rolling contexts match. One unrelated API
count test is unverified locally due missing FastAPI, recorded transparently.
Grok will review and deploy with its existing cloud access, then verify a fresh
healthy hourly scan, no duplicate sleeves and preserved positions/exits. Cloud
installation/scanning of the combination remains NOT VERIFIED by this chat.
Do NOT run the superseded standalone installer. No new SSH probe this turn.

Selection rationale: combination improves2022–24 mean +0.1952% to+0.3849%
stressed, saves4 Connors stops and loses0 target winners.2025 identical19 trades,
5 stops,14 targets,+0.9205%. Prior strict experimental flag is preserved, but
owner PAPER selection correctly accepts historical improvement with unchanged
2025. This is point evidence, not statistical non-inferiority or certain profit.

NEXT TEST NOW COMPLETE: H-EXT-REGIME-01. ER24 before the signal hour partitions
states at0.30, same definition across both periods. Extension<=1 priorATR,
unchanged entries/exits otherwise. Main benchmark is BTC+Connors; original
baseline is a separate diagnostic. Protocol committed before scoring:
94ee97be88aacf0dca4dc9f927274c718027dced. No threshold search or2026 outcomes.

| Policy on BTC+Connors | 2022–24 trades/stops/stressed mean | 2025 trades/stops/stressed mean |
|---|---|---|
| No extension cap (approved) |56/22/+0.3849%|19/5/+0.9205%|
| Cap always |38/14/+0.4914%|15/3/+1.1993%|
| Cap only directional |53/21/+0.3720%|19/5/+0.9205%|
| Cap only low-efficiency |41/15/+0.5003%|15/3/+1.1993%|

Low-efficiency-only passes the predeclared practical point screen at both costs;
directional-only fails. Candidate removes7 stops/8 targets historically and2
stops/2 targets in2025, with no new/displaced admissions. Average quality rises,
but historical additive return sum falls slightly; not an account return.
Incremental confidence intervals include zero in both periods. Historical SOL
mean worsens;2025 ETH has only2 trades. All candidate token/annual/leave-one-out
means are positive.2025 directional state has only1 benchmark trade, so no
claim that conditionality beats always-on activation there. Full-year path-state
frequencies differ modestly, not evidence that all2022–24=trend/all2025=chop.

This candidate is RESEARCH ONLY; latest approved deployment stays BTC+Connors.
No auto regime/extension switch. Read hourly_extension_regime_20261008/FINDINGS.md,
PROTOCOL.md and results_v1.32 independent admission replays,143 independent
state checks, exact three prior-arm reproduction,24 attribution checks,56 report
row checks.1372 ledger rows are overlapping eight arms and two cost scenarios.

NEXT: H-RSI-REGIME-01 using exactly the same state definition, separately on the
approved BTC+Connors benchmark; no silent stacking with the new extension cap.
Then broader-token/prospective confirmation when data are available. Previous
extension/RSI/BTC-Connors conditional-use hypotheses remain retained. No background
experiment or monitoring is running in this chat.

Recovery: newest MAR_extension_regime_checkpoint_20261008.zip over the original
full MAR_hourly_compression_checkpoint_20261007.zip; raw inputs remain separate.
The newest increment contains all previous research increments and latest owner
status. Read RESTORE_EXTENSION_REGIME_STUDY.md. Older sections below are historical
and superseded where paper preference or next-test status differs.

## Historical status before owner correction: BTC / Connors interaction and paper approval — 8 October 2026 Dubai

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
