# H-WINNER-LOSER-DIAGNOSTIC-01

Registered 8 October 2026 before calculating these feature/outcome associations.
This is exploratory diagnosis of an already selected strategy on repeatedly
examined data. It cannot create an independent holdout or establish certainty.

## Fixed reference

Approved hourly_compression_btc_connors_loweff_v1; BTC/ETH/SOL, both directions,
1h entries, SL2%, TP2.5%, no timeout. H-STOP-COST-01 results_v1 supplies frozen
quotes, costs, labels, admissions and outcomes. Primary: one-minute observed
quote exits, doubled slippage, runtime_stop_fill accounting, 65 admitted trades
(41 in2022–24,15 in2025,9 in2026 through2October16:00UTC).
Keep intrabar/one-minute x base/doubled slippage x original/reconciled accounting
as eight fixed sensitivity views. No5/15-minute optimization. Retain all69 raw
opportunities for provenance, including the four unadmitted historical signals.
No entry, exit, initial risk, production configuration or approval changes.

## Entry-only features

Exactly12 continuous features:
volume_ratio; prior_atr_pct; extension_atr; aligned_rsi14; aligned_crsi;
aligned_btc24; aligned_own24; efficiency24_before_signal; adx14; compression;
signal_tr_atr; aligned_body_atr.

Signal bar is the completed hour ending at entry T; last input minute T−1m.
Volume is signal-hour volume / median previous20 hourly volumes.
Prior ATR is arithmetic-seeded Wilder14 through T−1h; prior_atr_pct divides
that ATR by signal close. Signal TR uses previous close; signal_tr_atr=TR/priorATR.
Compression is prior6 TR mean / prior60 TR median. Body is side*(close−open)/priorATR.
RSI14 and CRSI(3,2,100) use the previously pinned arithmetic-seed implementations.
aligned RSI and CRSI = side*(indicator−50). Aligned24h returns multiply by side.
ADX14 uses the pinned explicit Wilder seed. Efficiency24 excludes the signal
hour, as in the approved rule. Extension uses the approved prior20 boundary.
All features are known at entry, no funding outcome or exit information.

Rebuild hourly OHLCV from minute inputs and check against frozen entry fields.
Independently reconstruct ADX,RSI,CRSI and prior-efficiency; prefix recomputation
must match at each period cutoff. No silent missing-feature exclusions.
Token,side,year,calendar week,date and six-hour UTC block are descriptive strata.
Year is never substituted for a market regime.

## Two-stage historical nomination

First inspect2022–24 ONLY. Report winner/loser feature medians,quartiles and
rank AUC=P(Xwinner>Xloser)+0.5*P(tie), plus within-token/side rank AUC.
No p-value-based discovery. Show each feature's three bins using historical
admitted feature-only tertiles, then freeze those same edges for later periods.

To prevent later-period choice, nominate at most ONE exploratory lead before
opening new2025–26 association tables. For each feature,split at its historical
admitted median into lower (<=median) and upper (>median) groups. Both directions
are considered. Require >=12 retained and >=12 excluded historical trades,
positive retained mean net,positive retained-minus-excluded mean,aligned rank
AUC>0.5,and positive retained-minus-excluded mean after separately leaving out
each of BTC,ETH,SOL (nonempty arms). Rank eligible leads by the minimum of those
three leave-one-token-out differences,then full difference,then feature name
and direction. This rule nominates a hypothesis,not a qualified filter.
If no candidate passes,record NONE;do not relax criteria.

Publish historical selection JSON and development tables before generating
later-period association tables. Thereafter report every feature,not just the
nominee, in2025 and2026 and all fixed execution/cost sensitivities. Historical
nomination still suffers selection bias and cannot be validated on already
examined periods. Do not change the nominated feature,direction or median.

For the nominee,report original admitted subsets:retained/excluded counts,
stops,targets,win rates,net means,mean difference versus original basket and
retained-minus-excluded differences. Circular calendar-week bootstrap for mean
differences:1/4-week blocks,10,000 draws,seeds20261006+block,zero-trade weeks
included. This is NOT a filtered portfolio replay. Removing an original trade
can admit a formerly blocked opportunity;an actual next filter experiment must
replay all raw opportunities. No strategy performance or deployment claim from
subsetting. Show token/side/year strata and largest-winner removal sensitivity.

## Post-entry anatomy and clustering

Primary65 trades: MFE and MAE from the slipped entry fill using all fully held
minute candles [entry,exit) plus the observed exit quote, excluding the exit
minute's later high/low. MFE and MAE are nonnegative gross price excursions,
not executable net profit. No within-minute ordering is inferred.
Count stopped trades with MFE>=0.5%,1%,1.5%,2%,and winners with MAE>=the same.
Report outcome medians/quartiles and durations. Exit RSI14/CRSI/ADX use the last
fully closed hourly bar at the actual sampled exit timestamp and are explicitly
post-entry diagnostics,never nomination inputs. These are not a trailing-stop
backtest and do not justify moving the original stops.

Summarize token/side and entry-year/day/week clusters,distinct active dates/weeks,
max same-day stops,and loss contribution of the top three loss weeks. Report
returns after removing the single largest winner. Return sums are not account PnL.

## Verification, publication, decision

Hash all predecessor sources,inputs,references,outputs and runtime source files.
Freeze new code/protocol before associations. Focused synthetic tests cover
causal hourly cutoffs,alignment,rank ties,median equality,selection independent
of later periods,and path exclusion of the exit candle. Independent verifier
rebuilds feature statistics,subset attribution and selected bootstrap intervals.
Preserve every failed attempt. Plain per-trade and comparison CSVs and a
cumulative restore-verified checkpoint accompany GitHub findings and handover.

No new token data,live orders,leverage,automatic approval or cloud mutation.
The expanded-token protocol remains unchanged. A stable nominee can motivate
one separately preregistered full-admission filter test next;an unstable nominee
is retained as a failed lead and the evidence directs the next hypothesis.
