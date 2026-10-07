# BTC confirmation: promising exploratory improvement

Completed 7 October 2026. The fixed BTC24 sign condition passes the predeclared
exploratory point screen: affected ETH/SOL entries and the complete basket both
have positive stressed means and improve over baseline in 2022–24 and reused
2025. Retain this candidate for further evidence. Independent edge and deployment
qualification remain false. The approved paper baseline is unchanged.

## Exact comparison and overlap with earlier work

On the unchanged hourly compression signals, ETH/SOL LONG requires BTC's last
completed 24-hour return > 0; SHORT requires it < 0. Zero rejects both. BTC's own
entries are unchanged. Use the completed signal-hour close, available at the
next-minute entry, divided by the close exactly 24 hours earlier. No later
minute or future price enters the predicate. All exact timestamps are checked.

The baseline already requires agreement with the token's OWN 24-hour direction.
This adds BTC direction, with no new trigger, entry delay, extension cap, RSI or
ADX. Stop 2%, target 2.5%, no timeout, costs/funding and chronological occupancy
remain fixed. Stress doubles slippage; it does not change entry/exit paths.

BTC direction was already an available input in the earlier learned-feature
search; its frozen selected leaves used own-token 168 h and funding conditions.
BTC residual fades and Soko regime gates are different interventions. No exact
standalone comparison on these hourly compression signals was found in the
inspected record; external Grokbot runtime history is not certified. See audit.
Protocol and audit were published BEFORE scoring at
a4ce9d72ca67e7483fea78b1b436cf925fa80a3c.

## Full BTC/ETH/SOL basket

| Period | Rule | Trades | Stops / rate | Targets | Win rate | Mean net base | Mean net stress | Stress PF |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2022–24 | baseline | 97 | 44 (45.4%) | 53 | 54.6% | +0.2268% | +0.1037% | 1.098 |
| 2022–24 | btc24_confirm | 89 | 37 (41.6%) | 52 | 58.4% | +0.4017% | +0.2825% | 1.292 |
| 2025 | baseline | 36 | 14 (38.9%) | 22 | 61.1% | +0.4992% | +0.3685% | 1.400 |
| 2025 | btc24_confirm | 35 | 13 (37.1%) | 22 | 62.9% | +0.5791% | +0.4505% | 1.514 |

## Affected ETH/SOL entries

| Period | Rule | Trades | Stops / rate | Targets | Win rate | Mean net base | Mean net stress | Stress PF |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2022–24 | baseline | 58 | 28 (48.3%) | 30 | 51.7% | +0.0807% | -0.0580% | 0.949 |
| 2022–24 | btc24_confirm | 50 | 21 (42.0%) | 29 | 58.0% | +0.3687% | +0.2343% | 1.239 |
| 2025 | baseline | 19 | 7 (36.8%) | 12 | 63.2% | +0.5660% | +0.4077% | 1.456 |
| 2025 | btc24_confirm | 18 | 6 (33.3%) | 12 | 66.7% | +0.7250% | +0.5692% | 1.708 |

ETH/SOL rows are the subset of each full chronological basket, not a separate
portfolio replay. BTC cannot conceal the affected subset's result: historical
ETH/SOL stressed mean changes from -0.0580% to +0.2343%; 2025 changes from
+0.4077% to +0.5692%. All entries close at a stop or target; no terminal marks.
Every target is a net winner and every stop a net loser at both cost levels.

## Which trades changed

2022–24: eight baseline admissions excluded, **seven stops avoided and one
target winner sacrificed**. No new trade is admitted and no otherwise eligible
trade is displaced. The seven stops comprise three ETH and four SOL trades;
the target winner is SOL LONG. Their stressed net sum is -0.150762 return units,
so exclusion adds +0.150762 to the basket's additive return sum. The original
97 admissions become 89, and the other 89 retain identical paths/costs.

2025: exactly **one SOL SHORT stop** is excluded, at 2025-05-25 01:00 UTC.
No target winner is excluded; no new or displaced admission. BTC and ETH are
unchanged. This single exclusion explains ALL the 2025 improvement: the
full-basket stressed mean rises by 0.0820 percentage points and ETH/SOL by 0.1615
points. The stop would lose -2.2955% base/-2.5002% stress after fills, fees and
funding. Avoiding it adds those return units; it is not an account-equity return.

Across the two periods, nine excluded trades occur at only seven distinct
timestamps. Two historical timestamps each contain an ETH and SOL stop, so
these observations are not nine independent market episodes. Eight exclusions
are stops and one is a target. These counts are descriptive after repeated
research; they do not establish that future BTC-disagreement entries will lose.

Raw opportunity counts fall 104 to 96 historically and 39 to 38 in 2025. Every
excluded raw opportunity happened to be a baseline admission, so raw and
admitted exclusions agree here. Occupancy was nevertheless independently
replayed. admission_decomposition.csv confirms zero extra/displaced entries
and exact additive reconciliation. All 56 BTC admissions (112 cost rows) match
across arms. No synthetic result is counted as an observed trade.

## Concentration, annual results and uncertainty

| Period | Token | Baseline trades / stops | Confirmed trades / stops | Baseline stress mean | Confirmed stress mean |
| --- | --- | --- | --- | --- | --- |
| historical | BTCUSDT | 39 / 16 | 39 / 16 | +0.3442% | +0.3442% |
| historical | ETHUSDT | 36 / 20 | 33 / 17 | -0.3040% | -0.1220% |
| historical | SOLUSDT | 22 / 8 | 17 / 4 | +0.3446% | +0.9260% |
| evaluation | BTCUSDT | 17 / 7 | 17 / 7 | +0.3247% | +0.3247% |
| evaluation | ETHUSDT | 8 / 3 | 8 / 3 | +0.4909% | +0.4909% |
| evaluation | SOLUSDT | 11 / 4 | 10 / 3 | +0.3472% | +0.6319% |

Historical ETH improves but remains negative under stress (-0.1220% per trade).
Historical SOL rises to +0.9260%, with 17 trades. In 2025, ETH is identical and only
SOL changes. Each leave-one-token-out basket mean is positive for the treatment,
but this diagnostic removes an admitted token without replacement replay and
does not show that each individual token is profitable in every period.

The filter changes no 2022 admissions. Full-basket stressed 2023 improves from
-0.4624% to -0.0734%, still negative; 2024 improves from +0.1744% to +0.3207%.
ETH/SOL stressed 2023 remains negative at -0.2690%. Do not hide the weaker years
behind a positive historical aggregate or select tokens after review.

| Scope | Period | Rule | Stressed mean | 95% four-week block interval |
| --- | --- | --- | --- | --- |
| full_basket | historical | baseline | +0.1037% | [-0.3772%, +0.5817%] |
| eth_sol | historical | baseline | -0.0580% | [-0.6877%, +0.5690%] |
| full_basket | evaluation | baseline | +0.3685% | [-0.2725%, +1.0038%] |
| eth_sol | evaluation | baseline | +0.4077% | [-0.7058%, +1.2871%] |
| full_basket | historical | btc24_confirm | +0.2825% | [-0.2012%, +0.7716%] |
| eth_sol | historical | btc24_confirm | +0.2343% | [-0.4113%, +0.8761%] |
| full_basket | evaluation | btc24_confirm | +0.4505% | [-0.2367%, +1.1498%] |
| eth_sol | evaluation | btc24_confirm | +0.5692% | [-0.5408%, +1.4571%] |

| Scope | Period | Stress mean difference (pp) | 95% four-week difference interval (pp) |
| --- | --- | --- | --- |
| full_basket | evaluation | +0.0820 | [+0.0000, +0.2970] |
| eth_sol | evaluation | +0.1615 | [+0.0000, +0.5899] |
| full_basket | historical | +0.1787 | [+0.0167, +0.3814] |
| eth_sol | historical | +0.2923 | [+0.0258, +0.6222] |

All displayed ABSOLUTE mean intervals cross zero. Historical difference lower
bounds are positive in these descriptive block estimates; 2025 difference lower
bounds are exactly zero. Many 2025 resamples omit the single excluded trade,
making both arms identical. That zero lower bound is not robust statistical
confirmation from many independent observations. The common calendar resamples
use 10,000 draws, fixed seeds, and empty weeks, with 1-week and 4-week variants.
Neither normal-cost nor stressed positive point estimates establish certainty.
2025 has been repeatedly reviewed; new-token or prospective evidence is still
needed, and reserved 2026 remains unscored.

## Verification and reproducibility

15 focused synthetic tests passed before freezing and scoring: sign/zero,
BTC bypass, bad context/symbols, 24-hour clock, exact joins, missing/duplicate
minutes, future perturbation/truncation and occupancy changes. Independently
reconstructed 143 BTC contexts from exact minute indices, matched the frozen
BTC24 features, checked 143 original raw barriers and replayed eight admissions.
Baseline 286 raw and 266 admitted cost rows reconcile exactly. BTC's 112 admitted
cost rows are unchanged. All 180 report rows reconcile against the saved ledger.

Frozen evidence contains 86 sources, 9 feature files, 6 input files, 4 original
reference files and 19 output hashes. There was one successful scoring attempt,
results_v1. CSV ledger 514 rows = 133 baseline + 124 confirmed admissions, each
at two costs; arms overlap and are not 514 independent trades. The excluded
trade file has 9 original trades at two costs = 18 rows. btc_entry_context.csv
records contemporaneous confirmation inputs. Exit/path columns are outcomes.
CSV return values are fractions (0.005=0.5%), side 1 LONG/-1 SHORT, stress 1 base
and 2 doubled slippage. Store full source, raw paths and ordinary CSVs privately;
public GitHub contains protocol, audit, findings and aggregate evidence.

## Retained extension observation and next step

The owner asked us to preserve the previous extension cap's improvement in
2022–24. It is now labelled **historical improvement; regime explanation pending**
in ../hourly_extension_filter_20261007/REGIME_FOLLOWUP.md, H-EXT-REGIME-01.
Historical stress improved +0.1037% to +0.1834%, while 2025 worsened. That does not
establish a tradable calendar/regime switch, or that 2025 was uniformly choppy.
The extension cap even worsened 2023; entry-time state definitions and comparisons
within the same states across periods would be required. The original negative
unconditional-improvement decision and positive historical finding both stand.

Next in the existing plan: audit and freeze one ADX entry-time comparison against
the ORIGINAL hourly baseline. RSI and Connors RSI follow separately. The BTC
condition is saved as a promising candidate, not silently stacked with these
tests. Exact later predicates remain unfrozen/unscored. Revisit H-EXT-REGIME-01
after those independent context studies using a separately registered design.
Broader-token replication and forward confirmation remain pending; no runtime,
approval, live/leverage setting or cloud process changed in this experiment.
