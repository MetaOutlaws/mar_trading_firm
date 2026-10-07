# Hourly ADX strength filter: fails consistent improvement

Completed 7 October 2026. The single own-token hourly ADX14 >=25 condition
fails the predeclared screen. Historical 2022–24 becomes negative; reused 2025
has a modestly higher average on only eight trades. Preserve that positive
2025 observation, with its admission and sample limitations. Do not adopt this
rule or retune its cutoff to rescue the result.

Brian's BTC-confirmation variant is now owner-approved as the preferred paper
variant. See ../hourly_btc_confirmation_20261007/OWNER_APPROVAL.md. Paper approval
does not rewrite statistical qualification or establish cloud installation.
BTC-filter activation is PENDING / NOT VERIFIED; latest operational evidence
still describes the original baseline. No live/leverage change was authorized.

## Isolated question and prior work

Does requiring established trend strength improve the original compression
entries? Apply ADX14 >=25 to BTC/ETH/SOL, both sides, using the completed signal
hour. Same SL2%, TP2.5%, no timeout, fees, fills, funding and admission rules.
No BTC sign condition, extension cap, DI direction or rising-ADX requirement.

The 25 level was fixed before scoring, with conventional motivation from
[Fidelity's ADX explanation](https://www.fidelity.com/viewpoints/active-investor/average-directional-index-ADX).
That explanation concerns trend strength; it is not evidence this crypto
strategy has an edge. Exact smoothing seeds, zero-range behavior and timing
are specified in PROTOCOL.md. This study uses arithmetic Wilder seeds; earlier
sweep ADX diagnostics used EWM-first-observation seeds and remain unchanged.

ADX is not a new feature: PR96 already contains failed BTC4h ADX+RSI and ADX+MA
conditions at floors20/25, and ema_adx_trend is an older EMA pullback family.
Those entry/clock combinations remain closed. No exact standalone ADX condition
on these hourly compression entries was found in inspected records. External
Grokbot runtime ledgers are not certified. Protocol/audit and the separate
owner approval were published before scoring at
1cc0931d185ca586d2f5cca9d5274e2431eca41f.

## Chronological BTC/ETH/SOL results

| Period | Rule | Trades | Stops / rate | Targets | Win rate | Mean net base | Mean net stress | Stress PF |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2022–24 | baseline | 97 | 44 (45.4%) | 53 | 54.6% | +0.2268% | +0.1037% | 1.098 |
| 2022–24 | adx14_ge25 | 39 | 22 (56.4%) | 17 | 43.6% | -0.2724% | -0.3931% | 0.703 |
| 2025 | baseline | 36 | 14 (38.9%) | 22 | 61.1% | +0.4992% | +0.3685% | 1.400 |
| 2025 | adx14_ge25 | 8 | 3 (37.5%) | 5 | 62.5% | +0.5874% | +0.4874% | 1.560 |

All entries close at stops or targets, with no terminal marks. All actual stops
lose and targets win after costs in this run. Counts are identical at both cost
levels. Stress doubles slippage; it does not change trade paths. Returns include
fees, fills and funding, so realized stop/target returns differ from quoted
2%/2.5%. Positive stressed means and improvement in BOTH periods were required;
both conditions fail due to the historical result.

## Stops avoided, winners excluded and new admissions

In 2022–24, the ADX condition directly excludes 60 baseline admissions:
**22 stops avoided but 38 target winners lost**. The other 37 original trades
remain unchanged. Replaying all raw opportunities adds two target winners,
BTC LONG and SOL LONG at 2024-07-13 23:00 UTC, giving 39 actual trades.
No retained-eligible baseline entry is displaced by changed occupancy.

The excluded historical basket was itself profitable: +0.6178% base and
+0.4922% stressed mean per trade. Its stressed return sum of +0.295328 is
removed, while the two new targets add +0.041393. The net additive difference
is -0.253935 return units. Historical stop count falls 44 to 22, but stop RATE
worsens 45.36% to 56.41%, and win rate drops 54.64% to 43.59%.

In 2025, 29 baseline admissions are excluded: **11 stops avoided and 18 target
winners lost**. Only seven original trades survive. A formerly blocked BTC LONG
at 2025-10-26 10:00 UTC becomes eligible and reaches its target, giving eight
actual trades. Again, no eligible baseline trade is displaced.

This admission change is important. The seven retained original trades average
+0.3461% base/+0.2464% stress, BELOW the original baseline +0.4992%/+0.3685%.
Adding the new winner raises the actual eight-trade result to +0.5874%/+0.4874%.
The 2025 higher mean is therefore not simply evidence that ADX selected a better
subset of the originally executed entries. The excluded basket's stressed mean
was +0.3980%; excluding its +0.115409 return sum and adding the new trade's
+0.021738 produces a lower total additive return by 0.093671 units. Additive
sums are not funded account returns, and taking fewer trades changes totals.

All 143 raw opportunities were evaluated. Before occupancy, ADX retains 41 of 104
historical and 8 of 39 evaluation signals. Raw exclusions (23 stops/40 targets
historically, 12 stops/19 targets in 2025) differ from excluded actual admissions.
Both scopes are explicitly saved; raw overlapping trades are not a portfolio.

## Token, year and uncertainty checks

| Period | Token | Baseline trades / stops | ADX trades / stops | Baseline stress mean | ADX stress mean |
| --- | --- | --- | --- | --- | --- |
| historical | BTCUSDT | 39 / 16 | 13 / 6 | +0.3442% | +0.1011% |
| historical | ETHUSDT | 36 / 20 | 18 / 12 | -0.3040% | -0.8029% |
| historical | SOLUSDT | 22 / 8 | 8 / 4 | +0.3446% | -0.2741% |
| evaluation | BTCUSDT | 17 / 7 | 7 / 3 | +0.3247% | +0.2479% |
| evaluation | ETHUSDT | 8 / 3 | 1 / 0 | +0.4909% | +2.1634% |
| evaluation | SOLUSDT | 11 / 4 | 0 / 0 | +0.3472% | No trades |

All three tokens' stressed historical means worsen; ETH and SOL are negative.
Every historical calendar year is negative for the filter: 2022 -0.0723%,
2023 -1.1861%, 2024 -0.2841%. The 2025 sample has seven BTC trades and one ETH
target winner, with ZERO SOL trades. It cannot establish broad token coverage.

| Period | Rule | Stress mean | 95% four-week block interval |
| --- | --- | --- | --- |
| historical | baseline | +0.1037% | [-0.3772%, +0.5817%] |
| evaluation | baseline | +0.3685% | [-0.2725%, +1.0038%] |
| historical | adx14_ge25 | -0.3931% | [-1.2739%, +0.4890%] |
| evaluation | adx14_ge25 | +0.4874% | [-1.4261%, +2.1695%] |

| Period | Stressed mean difference (pp) | 95% four-week difference interval (pp) |
| --- | --- | --- |
| evaluation | +0.1189 | [-1.5978, +1.4521] |
| historical | -0.4968 | [-1.1125, +0.1370] |

All displayed absolute and difference intervals cross zero. 2025 has eight
entry dates spanning seven entry weeks. With 10,000 attempted shared-calendar
resamples, only 9,992 one-week and 9,998 four-week draws contain treatment trades;
empty-treatment draws are omitted from mean estimation, and valid counts are
reported. Empty weeks are included in the calendar sampling. Historical draws
all have observations. Neither the positive 2025 mean nor its difference gives
independent confirmation after repeated exploration. Reserved 2026 is unscored.

## Verification and exported evidence

15 focused tests passed before freezing/scoring. Independent raw-minute hourly
aggregation and a separate explicit ADX recurrence matched all 143 entry contexts.
All 143 original raw barriers and eight chronological admissions were independently
checked. Baseline 286 raw and 266 admitted cost rows reconcile exactly; retained
trades have identical execution and costs. All 144 report rows reconcile.

Frozen evidence contains 89 source files, 9 feature files, 6 raw inputs, 4 baseline
references and 19 output hashes. One successful scoring attempt, results_v1.
The ordinary CSV ledger has 360 scenario rows: 133 baseline plus 47 ADX admissions,
each at two costs, with overlapping arms. These are not 360 independent trades.
The excluded export has 89 original trades at two costs = 178 rows. Return columns
use fractions (0.005=0.5%), side 1 LONG/-1 SHORT, stress 1 base/2 doubled slippage.
adx_entry_context.csv preserves entry-time values and last input minute; exit
and path columns are outcomes. Full source and detailed evidence are checkpointed.

## Decision, approval and next test

Close the unconditional ADX14>=25 comparison as unsuccessful. Preserve its
positive-but-thin 2025 observation without labeling it a proven regime edge.
No conclusion that ADX is universally useless, or that all 2025 was choppy,
follows from this result. A different predicate would be a separate experiment.

The owner-approved preferred paper variant remains BTC24 confirmation, whose
approval record is now saved separately from its exploratory qualification.
It has not been activated/verified in Singapore by this chat. The original
baseline remains the fixed research CONTROL for upcoming isolated comparisons.

Next: audit and freeze one RSI entry-time predicate, then Connors RSI separately.
Neither exact predicate is frozen/scored yet. Do not stack ADX or BTC conditions
into those tests. Preserve H-EXT-REGIME-01 for a later separately registered
within-state comparison, including the extension cap's 2022–24 improvement.
Continue seeking additional-token/prospective evidence for retained candidates.
No runtime, approval-book file, trading mode, live order or leverage was changed.
