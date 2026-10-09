# Winner/loser diagnostic: extension lead fails to transfer consistently

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

## All12 entry-feature associations

Rank AUC below0.5 means smaller feature values tend to belong to winners;above0.5 means larger values. This is descriptive,with ties given half weight,not a predictive model score or significance test.2026 has only7 winners and2 losers.

| Feature | 2022–24 AUC | 2025 AUC | 2026 AUC |
|---|---:|---:|---:|
| volume_ratio | 0.433 | 0.280 | 0.571 |
| prior_atr_pct | 0.405 | 0.700 | 0.571 |
| extension_atr | 0.252 | 0.680 | 0.214 |
| aligned_rsi14 | 0.414 | 0.500 | 0.714 |
| aligned_crsi | 0.448 | 0.860 | 0.286 |
| aligned_btc24 | 0.513 | 0.400 | 0.500 |
| aligned_own24 | 0.452 | 0.500 | 0.571 |
| efficiency24_before_signal | 0.483 | 0.360 | 0.500 |
| adx14 | 0.319 | 0.620 | 0.571 |
| compression | 0.393 | 0.220 | 0.857 |
| signal_tr_atr | 0.517 | 0.160 | 0.357 |
| aligned_body_atr | 0.579 | 0.300 | 0.429 |

## Nominee robustness by execution and cost

| Period | Poll minutes(0=intrabar) | Slippage | Accounting | Retained trades / stops | Retained mean net | Change vs original basket,pp |
|---|---:|---|---|---:|---:|---:|
| 2025 | 0 | Base | research_all_exit_slip | 7 / 2 | +1.0261% | -0.3837 |
| 2022–24 | 0 | Base | research_all_exit_slip | 21 / 6 | +1.0491% | +0.6962 |
| 2026 Jan–2 Oct | 0 | Base | research_all_exit_slip | 5 / 0 | +2.3062% | +0.5047 |
| 2025 | 0 | Base | runtime_stop_fill | 7 / 2 | +1.0404% | -0.3826 |
| 2022–24 | 0 | Base | runtime_stop_fill | 21 / 6 | +1.0636% | +0.6850 |
| 2026 Jan–2 Oct | 0 | Base | runtime_stop_fill | 5 / 0 | +2.3062% | +0.4993 |
| 2025 | 0 | Doubled | research_all_exit_slip | 7 / 3 | +0.3225% | -0.7187 |
| 2022–24 | 0 | Doubled | research_all_exit_slip | 21 / 7 | +0.7715% | +0.7013 |
| 2026 Jan–2 Oct | 0 | Doubled | research_all_exit_slip | 5 / 0 | +2.2277% | +0.5037 |
| 2025 | 0 | Doubled | runtime_stop_fill | 7 / 3 | +0.3651% | -0.7091 |
| 2022–24 | 0 | Doubled | runtime_stop_fill | 21 / 7 | +0.8051% | +0.6763 |
| 2026 Jan–2 Oct | 0 | Doubled | runtime_stop_fill | 5 / 0 | +2.2277% | +0.4928 |
| 2025 | 1 | Base | research_all_exit_slip | 7 / 2 | +1.0738% | -0.4204 |
| 2022–24 | 1 | Base | research_all_exit_slip | 21 / 7 | +1.1170% | +0.7351 |
| 2026 Jan–2 Oct | 1 | Base | research_all_exit_slip | 5 / 0 | +2.3423% | +0.5196 |
| 2025 | 1 | Base | runtime_stop_fill | 7 / 2 | +1.0881% | -0.4193 |
| 2022–24 | 1 | Base | runtime_stop_fill | 21 / 7 | +1.1338% | +0.7252 |
| 2026 Jan–2 Oct | 1 | Base | runtime_stop_fill | 5 / 0 | +2.3423% | +0.5142 |
| 2025 | 1 | Doubled | research_all_exit_slip | 7 / 4 | -0.2993% | -1.1263 |
| 2022–24 | 1 | Doubled | research_all_exit_slip | 21 / 7 | +1.0409% | +0.9728 |
| 2026 Jan–2 Oct | 1 | Doubled | research_all_exit_slip | 5 / 0 | +2.3685% | +1.0492 |
| 2025 | 1 | Doubled | runtime_stop_fill | 7 / 4 | -0.2288% | -1.1017 |
| 2022–24 | 1 | Doubled | runtime_stop_fill | 21 / 7 | +1.0745% | +0.9454 |
| 2026 Jan–2 Oct | 1 | Doubled | runtime_stop_fill | 5 / 0 | +2.3685% | +1.0274 |

## Primary subset difference uncertainty

| Period | Retained minus basket mean,pp | Four-week95% interval,pp |
|---|---:|---|
| 2025 | -1.1017 | -2.5838 to +0.1187 |
| 2022–24 | +0.9454 | +0.2223 to +1.7949 |
| 2026 Jan–2 Oct | +1.0274 | -0.0103 to +2.4622 |

These intervals account for calendar clustering through circular weekly blocks,
including zero-trade weeks. They do NOT adjust for historical nomination from
24 feature/direction candidates or repeated prior research. Historical positive
intervals cannot be treated as confirmatory evidence. The2025 difference interval
includes zero despite its negative point estimate;the2026 positive point estimate
also has an interval including zero. No statistically established harm/benefit
or future certainty is claimed. No full filtered portfolio was replayed.


## Winner and loser path anatomy

| Period | Outcome | Trades | Median MFE | Median MAE | Median holding hours |
|---|---|---:|---:|---:|
| 2025 | loser | 5 | 1.095% | 2.102% | 22.50 |
| 2025 | winner | 10 | 2.676% | 1.041% | 19.40 |
| 2022–24 | loser | 21 | 0.749% | 2.111% | 11.92 |
| 2022–24 | winner | 20 | 2.703% | 1.003% | 18.26 |
| 2026 Jan–2 Oct | loser | 2 | 1.984% | 2.435% | 99.49 |
| 2026 Jan–2 Oct | winner | 7 | 2.615% | 0.947% | 14.62 |

## Excursion counts

| Period | Outcome | Trades | Gross threshold | MFE at least threshold | MAE at least threshold |
|---|---|---:|---:|---:|---:|
| 2025 | loser | 5 | 0.5% | 3 | 5 |
| 2025 | loser | 5 | 1.0% | 3 | 5 |
| 2025 | loser | 5 | 1.5% | 2 | 5 |
| 2025 | loser | 5 | 2.0% | 2 | 5 |
| 2025 | winner | 10 | 0.5% | 10 | 9 |
| 2025 | winner | 10 | 1.0% | 10 | 6 |
| 2025 | winner | 10 | 1.5% | 10 | 3 |
| 2025 | winner | 10 | 2.0% | 10 | 0 |
| 2022–24 | loser | 21 | 0.5% | 11 | 21 |
| 2022–24 | loser | 21 | 1.0% | 10 | 21 |
| 2022–24 | loser | 21 | 1.5% | 6 | 21 |
| 2022–24 | loser | 21 | 2.0% | 4 | 21 |
| 2022–24 | winner | 20 | 0.5% | 20 | 16 |
| 2022–24 | winner | 20 | 1.0% | 20 | 10 |
| 2022–24 | winner | 20 | 1.5% | 20 | 2 |
| 2022–24 | winner | 20 | 2.0% | 20 | 0 |
| 2026 Jan–2 Oct | loser | 2 | 0.5% | 2 | 2 |
| 2026 Jan–2 Oct | loser | 2 | 1.0% | 2 | 2 |
| 2026 Jan–2 Oct | loser | 2 | 1.5% | 1 | 2 |
| 2026 Jan–2 Oct | loser | 2 | 2.0% | 1 | 2 |
| 2026 Jan–2 Oct | winner | 7 | 0.5% | 7 | 5 |
| 2026 Jan–2 Oct | winner | 7 | 1.0% | 7 | 3 |
| 2026 Jan–2 Oct | winner | 7 | 1.5% | 7 | 2 |
| 2026 Jan–2 Oct | winner | 7 | 2.0% | 7 | 0 |

Exit RSI14,CRSI and ADX,measured on the last fully completed hour at each sampled
exit,are included in primary_trade_anatomy.csv and path_summary.csv. They are
post-entry explanations and were never used to nominate an entry filter.
Large intraminute MFE can disappear before the next observed quote;this is why
'stopped after showing2%' is not equivalent to executable2% profit protection.
No within-minute ordering of MFE/MAE is inferred. Losing path extrema are not
available at entry. All primary losses are stop exits and all wins target exits.

## What the diagnostic supports

The lower-extension lead is worth preserving with its exact historical conditions
and2026 observation;it is not a universal admission rule. The reversal is visible
inside token/side strata as well as pooled data. In2025,the retained BTC subset
contains four trades with three stops and averages−1.0323%;its ETH subset has
one winner;SOL has two trades,one stop.2026's retained group contains BTC2 and
SOL3,all winners,and no ETH. Such tiny cells cannot define token exclusions.

ADX strength,RSI overextension and volume measures add context,but the observed
directions change across periods. The entry sample has already passed Connors,
BTC alignment and conditional extension gates,so these are conditional
associations within that filtered sample,not conclusions about all breakouts.
The smaller feature range and repeated testing make further threshold stacking
especially vulnerable to fitting noise. No replacement gate was selected after
the nominated extension lead failed the later-period point screen.

Nineteen winning paths recovering from>=1% adverse movement support further
attention to entry location and risk geometry. Fifteen stopped paths showing
>=1% favorable movement support studying path order if profit protection is
revisited. Neither observation itself overturns the prior controlled stop-width,
profit-protection or failed-breakout-exit results. Those decisions remain intact.

The proposed boundary-retest entry is unscored. A local protocol/novelty search
found no retest treatment in the completed isolated-study protocols;the original
discovery explicitly specified no retest. Earlier zone timing and generic
pullback families must still be distinguished in its full preregistration.
No claim is made about unseen external Grok experiments.

## Data dictionary and reproducibility

entry_features.csv/parquet has69 original raw signals and only causal features.
entry_outcome_evidence has520 rows=65 admitted signals x2 path models x2 slip
scenarios x2 accounting conventions;these are not520 independent trades.
primary_trade_anatomy has65 unique primary trades with entry features,outcomes,
MFE/MAE and explicitly exit_-prefixed post-entry indicators.
nominee_subsets contains24 fixed model/period comparisons;nominee_subgroups
preserves tokens,sides and years,including empty cells. historical_candidates
contains all24 tested feature/direction nominations,not only the selected lead.

The feature median and tertile edges were learned only from2022–24 admitted
feature values. Lower means <=median;upper means >median. Use JSON thresholds
or CSV round-trip float parsing when checking equality at boundaries. Do not
round0.5337759022674707 to0.5 and claim to reproduce this diagnostic.
RSI/Connors aligned values equal side*(indicator−50);aligned returns multiply
by side. prior_atr_pct,returns and excursions are fractions;volume and signal
TR are ratios;extension is priorATR units. side1 LONG/−1 SHORT. stress1 base,
stress2 doubled slippage. MFE/MAE are nonnegative gross price excursions.
Feature asof is the completed hour at entry;last input minute is strictly before
entry. Exit indicators use a completed hour with last input before exit.

Read results_v1/freeze.json and status.json,development_v1/selection.json,
TEST_VERIFICATION.json,REPORT_VERIFICATION.json and VERIFIER_AMENDMENT.md.
Reproduce with verify_report_v2.py;the originally frozen verifier is preserved.
No treatment rerun,threshold retuning,new-token scoring or runtime mutation.
