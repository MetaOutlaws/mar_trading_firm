# Hourly compression: fixed ADX strength condition

Pre-scoring protocol, 7 October 2026. Brian authorized the next isolated test.
BTC confirmation is now owner-approved as the preferred paper variant; see
../hourly_btc_confirmation_20261007/OWNER_APPROVAL.md. That approval is distinct
from research qualification and cloud activation. No runtime change in this test.

## Hypothesis and one fixed predicate

An hourly compression breakout occurring with established trend strength may
have better expectancy. Retain an original eligible signal only when its OWN
token's completed hourly ADX14 is >=25, equality included. Apply identically to
BTC/ETH/SOL and both directions. ADX measures strength, not direction: original
body, breakout and own-token24h direction conditions remain unchanged. No DI
direction or rising-ADX condition, no low-ADX arm, and no lookback/cutoff sweep.
The BTC condition and extension cap are not included in either arm.

Twenty-five is fixed before looking at this indicator's signal distribution or
treatment outcomes. It is motivated by a conventional strength threshold,
not a fitted or universally valid boundary. Reference: Fidelity's ADX explanation
https://www.fidelity.com/viewpoints/active-investor/average-directional-index-ADX
(general indicator definition/threshold only, not evidence of a crypto edge).

## Exact indicator and clock

Compute on contiguous completed UTC 1h OHLC bars from the original minute tape.
At entry T use the bar covering [T-1h,T), including its final minute close at
T-1min. No minute at or after T may affect ADX. No forward/stale context fill.

For hour j>0: up=high[j]-high[j-1], down=low[j-1]-low[j]. PlusDM=up only if
up>down and up>0, otherwise0. MinusDM=down only if down>up and down>0, otherwise0.
Equal moves contribute zero to both. TR=max(high-low,abs(high-prevClose),
abs(low-prevClose)). At first observed hour, TR=high-low and both DMs=0.

Seed smoothed TR/PlusDM/MinusDM at zero-based index13 with the arithmetic mean
of the first14 observations, including that defined first hour. Subsequently
smooth[j]=(13*smooth[j-1]+value[j])/14. DIplus/minus=100*smoothedDM/smoothedTR.
If smoothedTR=0, both DIs=0. DX=100*abs(DIplus-DIminus)/(DIplus+DIminus);
zero DI sum gives DX=0. DX is unavailable before index13.

Seed ADX at index26 with the arithmetic mean of the first14 valid DX values
(indices13..26). Then ADX[j]=(13*ADX[j-1]+DX[j])/14. This fully specified seed
avoids implementation-dependent early EWM behavior. Earlier sweep diagnostics
used first-observation EWM seeding and were not a threshold trading test.
Preserve that older definition; do not modify its sources or results.

Missing/duplicate minutes, invalid OHLC, missing/invalid ADX at a selected signal
or timestamp mismatch fail verification. A completely flat valid history has
ADX0 after warmup and fails the strength predicate. No silent data exclusions.
Do not infer chop from calendar-year membership or from eventual trade outcomes.

## Unchanged baseline and execution

All143 original membership-eligible hourly compression raw opportunities, BTC,
ETH and SOL, both directions. SL2%, TP2.5%, no timeout. Retained opportunities
keep exact entry time, price/path and barriers. Fees0.055% per side, base
slippage0.05% BTC/ETH and0.10% SOL per side, doubled-slippage stress and actual
funding. Quote-based barriers, stop-first ties, adverse stop gaps, target quote
and conservative funding boundary rule unchanged. R=net return/0.02.

Original monthly membership/rank, one position/token across sides, six basket
and three per direction slots, no reentry during an exit minute. Independently
replay both arms from ALL remaining raw opportunities; removing a trade may
admit a formerly blocked one. Never only subset the previously admitted ledger.
Two arms: baseline and adx14_ge25. Historical2022–24 and flat-reset reused2025,
both costs. No2026 price feature, entry or outcome; no other-token result.

## Screen and required evidence

Primary exploratory continuation requires nonempty arms, positive stressed
chronological full-basket mean and positive stressed difference versus the
ORIGINAL baseline in BOTH periods. Empty samples are insufficient, not a pass.
A point pass is not independent qualification or automatic approval/deployment.

Report counts, closed/marked trades, stops and stop rate, targets, win rate,
net mean/PF, mean/sum R, holding times, all tokens/sides, annual results and
leave-one-token-out diagnostics. Include1-week and4-week shared-calendar block
intervals,10000 draws, fixed seeds and empty weeks; report difference intervals.
Additive return sums are not funded account returns. Reused2025 is exploratory.

Separate direct exclusions from retained trades, admissions newly possible and
eligible baseline trades lost through changed occupancy. Count excluded target
winners and stops among raw opportunities AND original admissions. Retained
trades must have identical costs/paths. Reconcile total additive change to new
returns minus dropped returns. Preserve entry ADX and its last input timestamp.

## Verification, publication and next steps

Commit protocol/audit before scoring, then freeze sources, six raw inputs,
nine feature files and four baseline references. Test threshold equality,
strength invariance under price reflection, monotonic/flat paths, Wilder seeds,
equal DM ties, exact hourly alignment, missing/duplicate data and future
perturbation/truncation. Independently implement hourly aggregation and recursive
ADX from minute arrays, matching all143 selected contexts. Check all143 raw
barriers, baseline286 raw/266 admitted cost rows and all eight admissions.
Reconcile reports from the ledger. Preserve every attempt, sources and ordinary
CSV evidence; publish findings/aggregates and update the verified checkpoint.

No retuning after this result. RSI and Connors RSI follow independently against
the original baseline. H-EXT-REGIME-01 preserves the extension cap's2022–24
improvement for a separately registered state-dependent comparison; this ADX
study does not test a switch between baseline/extension/BTC variants. Broader
token replication and prospective evidence remain pending. No background work
or cloud activation is implied by this protocol.
