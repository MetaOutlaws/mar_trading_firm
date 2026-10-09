# Retest entry: better conditional trade quality, mixed opportunity cost

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

## Fixed sensitivities

| Period | Exit sampling | Slippage | Retest mean net | Change in mean / trade,pp | Change in net / original signal,pp |
|---|---|---|---:|---:|---:|
| 2025 | Intrabar | Base | +1.8135% | +0.3906 | -0.3348 |
| 2025 | Intrabar | Doubled | +1.7460% | +0.6719 | -0.0265 |
| 2022–24 | Intrabar | Base | +0.7928% | +0.4142 | +0.1131 |
| 2022–24 | Intrabar | Doubled | +0.7478% | +0.6190 | +0.3147 |
| 2026 Jan–2 Oct | Intrabar | Base | +2.2974% | +0.4904 | -0.5306 |
| 2026 Jan–2 Oct | Intrabar | Doubled | +2.2071% | +0.4723 | -0.5087 |
| 2025 | 1 minute | Base | +1.9919% | +0.4845 | -0.3122 |
| 2025 | 1 minute | Doubled | +1.8852% | +1.0123 | +0.2582 |
| 2022–24 | 1 minute | Base | +0.8381% | +0.4295 | +0.1119 |
| 2022–24 | 1 minute | Doubled | +0.7682% | +0.6390 | +0.3262 |
| 2026 Jan–2 Oct | 1 minute | Base | +2.4174% | +0.5893 | -0.4851 |
| 2026 Jan–2 Oct | 1 minute | Doubled | +2.2594% | +0.9183 | -0.0858 |

## Primary uncertainty

| Period | Change in mean / trade,pp | Four-week95% interval,pp | Change per original signal,pp | Four-week95% interval,pp |
|---|---:|---|---:|---|
| 2025 | +1.0123 | -0.1420 to +2.3480 | +0.2582 | -0.8997 to +1.4905 |
| 2022–24 | +0.6390 | -0.0936 to +1.4456 | +0.3262 | -0.1883 to +0.8850 |
| 2026 Jan–2 Oct | +0.9183 | -0.1474 to +2.4809 | -0.0858 | -1.1645 to +1.2122 |

## Entry quality and waiting

| Period | Admitted retests | Mean wait,minutes | Mean side-adjusted price improvement | Better / worse fills |
|---|---:|---:|---:|---:|
| 2025 | 9 | 22.22 | +0.2648% | 9 / 0 |
| 2022–24 | 26 | 18.42 | +0.2335% | 22 / 4 |
| 2026 Jan–2 Oct | 5 | 34.00 | +0.3699% | 5 / 0 |

Price improvement compares slipped retest and immediate fills on the same raw
signal. Positive is favorable to its side. Four historical entries are worse,
so this is not a hindsight 'take only improved fills' rule. Better entry does
not guarantee greater profit on shared winners:fixed brackets reset from the
new fill,and sampled target overshoots/funding also change.

## Admission and mechanism attribution

The fixed primary historical difference in additive trade-return sums is
+14.6786 percentage points: +8.6022pp from changed shared outcomes,
−2.1139pp from the newly admitted stopped trade, and +8.1902pp by omitting the
16 original admitted signals whose combined baseline return was negative.
2025:+8.9870pp shared outcome change minus5.1137pp omitted positive baseline
returns =+3.8733pp.2026:−0.6700pp shared changes minus0.1026pp omitted positive
baseline returns =−0.7726pp. These sums are not account PnL,compounded returns,
capital-adjusted returns or a leverage prescription.

The original-admitted counterfactual reports zero on unfilled signals and no
replacement admission. Its historical mean differs from the actual ledger
because the new stopped trade must be included in the actual strategy.
Full-admission ledgers and explicit paired rows are authoritative.

## Data dictionary and reproduction

entry_plans has69 rows,one per original signal,including all27 no-fills and
first touch/confirmation/fill timestamps. Confirmation_time is minute CLOSE
and equals the earliest eligible next-minute entry timestamp. touch_time labels
the minute containing the touch,not an exact tick timestamp. No intraminute
sequence is inferred beyond the close occurring after that minute's range.

all_opportunities has444 rows:276 immediate plus168 retest,across two exit
models and two slippage scenarios. pooled_ledger/individual_trades has420 rows:
260 immediate plus160 retest. Primary individual-trade export has105 rows:
65 immediate plus40 retest;each arm must be analyzed separately. The primary
signal-pairs export has69 original signals,with both arms and unfilled statuses.
The complete paired CSV has276 rows. stress1=base,stress2=doubled;poll0=intrabar,
poll1=one-minute quotes;side1=LONG,−1=SHORT. All returns/costs are decimal fractions.

A missing treatment outcome is an unfilled candidate,not missing market data.
retest_realized_net and baseline_realized_net are zero for unadmitted signals.
Counterfactual raw trade outcomes must not be summed as a portfolio ledger.
Negative funding is a credit;funding schedules retain their provisional
historical-source limitation. Fees,slippage and funding are included in net.

Run verify_report.py with --cache and --runtime against a complete restore.
It checks original hashes,exact baseline rows,per-signal pairs,denominators,
attribution and circular week bootstrap. Use CSV float_precision='round_trip'.
Prior code and evidence were not altered. Frozen local protocol SHA256:
faabb398772b618522bc2bd6a8ad578b221729a10bfe4df276ca834e0fcb2d46.
Local freeze SHA256:fb43d40759aef3d45f7a3712b64953b6e890c6eb0648a0661431cfdc835300c6.
