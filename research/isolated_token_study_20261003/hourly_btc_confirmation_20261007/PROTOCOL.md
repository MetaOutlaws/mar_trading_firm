# BTC direction confirmation for hourly ETH/SOL compression

Pre-scoring protocol, 7 October 2026. Brian authorized the next comparison in
the saved plan. Read NOVELTY_AUDIT.md. One condition, no fitted threshold, no
extension cap and no oscillator condition. No runtime or approval change.

## Hypothesis and exact rule

ETH/SOL hourly compression entries aligned with BTC's recent direction may
have better expectancy than entries opposing it. The baseline already checks
each token's own 24-hour direction; BTC adds a separate market-context condition.

At the unchanged entry time T, an exact UTC hour boundary, let C(T) be BTC's
last completed hourly close, the minute close at T minus one minute. Let
C(T-24h) be the corresponding hourly close exactly 24 hours earlier. Define
BTC24(T) = C(T)/C(T-24h) - 1.

- ETHUSDT/SOLUSDT LONG: retain only BTC24(T) > 0.
- ETHUSDT/SOLUSDT SHORT: retain only BTC24(T) < 0.
- Exactly zero rejects either alt direction. Equality is not confirmation.
- BTCUSDT: retain every original baseline signal, with no new BTC condition.

The completed signal-hour BTC close is allowed because it is known at T; no
minute at or after T may influence confirmation. Use exact timestamp joins,
no future fill or stale forward fill. Require contiguous UTC minute inputs,
complete hourly blocks, finite positive BTC closes and finite return at every
eligible signal. Missing/invalid context fails verification rather than silently
removing trades. No BTC entry price, eventual BTC trade result or future path
is used. No search over 4h/12h/48h, moving averages or magnitude thresholds.

## Baseline and chronology

Use all 143 membership-eligible original 1h compression opportunities across
BTC/ETH/SOL, both sides. Original SL2%, TP2.5%, no holding timeout. Preserve
each retained opportunity's exact entry time and raw path. Same quote-based
barriers, stop-first ties, adverse stop gaps, quoted targets, actual funding,
fees 0.055%/side, base slippage 0.05% BTC/ETH and 0.10% SOL per side; stress
doubles slippage. R = net return / 0.02. Additive sums are not account returns.

Same original monthly membership/rank, one position per token across sides,
six basket/three same-direction slots and no reentry during an exit minute.
Replay both arms from ALL eligible raw opportunities, including signals formerly
blocked by occupancy. Never merely delete trades from the admitted ledger.
Two arms: baseline and btc24_confirm. Two cost levels, two periods.

Historical 2022–24 and flat-reset reused 2025. No 2026 price feature or outcome.
Existing funding boundary accounting stays fixed. 2025 is already repeatedly
reviewed and is not independent validation. No additional-token data is claimed.

## Primary and diagnostic comparisons

Primary question concerns the affected ETH/SOL entries. Report them as the
ETH/SOL subset of each FULL chronological basket, not an independently replayed
portfolio. Also report the full BTC/ETH/SOL basket. An unaffected positive BTC
sleeve must not hide losing or worsened alt entries.

Exploratory continuation requires nonempty ETH/SOL arms, positive stressed
ETH/SOL mean and positive stressed ETH/SOL mean difference versus baseline in
BOTH periods. The full basket must also have positive stressed mean and improve
in BOTH periods. Empty arms are insufficient, not a pass. A point pass is not
deployment qualification. Report uncertainty and token/year concentration even
if the point conditions pass. No lower standard introduced after scoring.

For both scopes report trades, closed/terminal counts, stop hits/rates, targets,
win rate, mean net/PF, mean/sum R, holding times, annual and token/side detail.
Use existing one-week and four-week shared-calendar block resampling with
10,000 draws/fixed seeds and empty weeks. Show intervals for each mean and its
difference. Leave-one-token-out summaries are descriptive without replacement.

Count excluded baseline winners and stops separately from raw exclusions. Show
retained identical trades, directly excluded admissions, otherwise eligible
entries lost through changed occupancy, and newly admitted trades. Reconcile
additive return change as new returns minus dropped returns. Confirm BTC raw
signals and admission paths remain identical in this three-token setup; do not
silently remove BTC if a capacity interaction occurs.

## Verification and reproducibility

Publish this protocol before scoring; freeze sources, input/features and four
original reference hashes. Reconstruct BTC24 independently from exact minute
indices at every signal and compare with frozen btc24 features and the main
hourly aggregation. Test long/short/zero, BTC bypass, invalid symbol/context,
24-hour clock arithmetic, missing/duplicate data, exact timestamp joins and
invariance under future perturbation/truncation. Test occupancy replay.

Independently verify all 143 original raw stop/target paths, reproduce baseline
286 raw and 266 admitted cost rows, and independently replay eight admissions.
Reconcile the reported subset/full, annual, symbol and contrast tables.
Preserve every attempt. Publish findings/aggregates in draft PR99 and save full
code, ordinary CSV ledgers, context and changed-trade evidence in the checkpoint.

## Related retained hypothesis

The prior one-ATR extension cap remains labelled historical improvement
(2022–24), with regime usefulness unvalidated. See
../hourly_extension_filter_20261007/REGIME_FOLLOWUP.md (H-EXT-REGIME-01).
No conclusion that all of 2025 was choppy is assumed. This BTC test does not
test that explanation and does not include the extension cap. ADX, RSI and
Connors RSI remain subsequent independent comparisons with unfrozen predicates.
