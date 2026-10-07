# Hourly compression extension cap: no consistent improvement

Completed 7 October 2026. Keep the approved hourly compression paper baseline
unchanged. The single fixed one-ATR cap improves the 2022–24 mean but worsens
reused 2025. Both treatment aggregates remain positive after costs; this is a
failed IMPROVEMENT hypothesis, not a claim that the filtered pooled rule loses.
No threshold search follows this result.

Owner clarification: preserve the label **historical improvement (2022–24)**.
Regime usefulness remains a separate unvalidated hypothesis, H-EXT-REGIME-01;
see REGIME_FOLLOWUP.md. The unconditional decision does not erase that finding.

## Frozen question
Does refusing a breakout more than one prior hourly ATR beyond its prior
20-hour boundary improve entry selectivity? Keep only
side*(completed_signal_close - boundary)/prior_ATR <= 1.0. The original breakout
must still be strict. Boundary and Wilder ATR14 exclude the signal hour.
This uses information available at entry, with no entry delay or price change.

BTC/ETH/SOL, both directions, 1h. Initial stop 2%, target 2.5%, no timeout;
unchanged quote-based barriers, gaps/ties, actual funding, fees and admission
rules. Base slippage is 0.05% per side for BTC/ETH and 0.10% for SOL; stress
doubles slippage. Fees are 0.055% per side. The cutoff was chosen before scoring
and is not an optimized value. PROTOCOL.md and NOVELTY_AUDIT.md were published
before scoring at 3565cd83ce2aeddcace324c415880a5ab892ad50.

The inspected hourly runtime, earlier compression family and saved Grokbot
protocol had no equivalent upper extension cap. This scoped audit does not
certify every unrecorded external Grokbot job. Existing negative studies and
the original positive hourly result remain preserved.

## Chronological results

| Period | Rule | Trades | Stops / rate | Targets | Win rate | Mean net base | Mean net stress | Stress PF |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2022–24 | baseline | 97 | 44 (45.4%) | 53 | 54.6% | +0.2268% | +0.1037% | 1.098 |
| 2022–24 | extension_cap_1atr | 60 | 26 (43.3%) | 34 | 56.7% | +0.3109% | +0.1834% | 1.179 |
| 2025 | baseline | 36 | 14 (38.9%) | 22 | 61.1% | +0.4992% | +0.3685% | 1.400 |
| 2025 | extension_cap_1atr | 22 | 10 (45.5%) | 12 | 54.5% | +0.1999% | +0.0635% | 1.059 |

All entries close at a target or stop; there are no terminal marks. Every target
is a net winner and every stop a net loser in this run. Counts are identical at
both cost levels. Returns include fees, fills and funding; they are not simply
the quoted 2%/2.5% barriers. The primary point screen required positive stressed
means AND improvement over baseline in both periods. Positivity passes;
consistent improvement fails. Small samples and reused history prevent any
claim of independently established edge.

## Winners sacrificed versus stops avoided

In 2025 the filter drops 14 originally admitted trades: **4 stop losses avoided
but 10 target winners excluded**. It keeps the other 22 with identical entries,
prices, exits and costs. No new trades are admitted, and none are lost through
changed occupancy. The excluded group itself averages +0.9696% base and
+0.8477% stressed net per trade. These excluded breakouts were valuable in this
period; the cap does not reliably identify poor entries.

The stop count falls from 14 to 10 because fewer trades are taken. The stop
RATE rises from 38.89% to 45.45%, and win rate falls from 61.11% to 54.55%.
Stressed mean falls by 0.3050 percentage points, from +0.3685% to +0.0635%.
The 2025 stressed additive return difference is -0.118681 return units.
This is a sum of per-trade returns, not a funded account return or equity curve.

In 2022–24, the filter directly excludes 38 baseline admissions: 19 stops and
19 targets. Of the original 97, 59 remain. Replaying all raw signals admits
one additional stopped trade, producing 60 trades. No eligible baseline trade
is displaced through occupancy. The excluded group's stressed return sum is
-0.032641; the extra stopped trade contributes -0.023206. The net stressed
additive difference is therefore +0.009435. Base additive return falls by
0.033447 return units despite the improved base mean. Means and total returns
answer different questions when trade counts change.

All 143 original raw opportunities were considered. Historical raw signals
fall from 104 to 63 and 2025 raw signals from 39 to 24. Raw exclusions differ
from actual admissions: 2025 excludes 4 hypothetical stops and 11 targets
before occupancy, but 4 stops and 10 targets among baseline admissions.
Use exclusion_summary.csv with its explicit scope, not overlapping raw paths
as a portfolio. admission_decomposition.csv separates direct filtering from
new or displaced admissions.

## Token, year and uncertainty checks

| Period | Token | Baseline trades | Filter trades | Baseline stress mean | Filter stress mean |
| --- | --- | --- | --- | --- | --- |
| historical | BTCUSDT | 39 | 21 | +0.3442% | +0.4752% |
| historical | ETHUSDT | 36 | 23 | -0.3040% | +0.0397% |
| historical | SOLUSDT | 22 | 16 | +0.3446% | +0.0071% |
| evaluation | BTCUSDT | 17 | 10 | +0.3247% | -0.0683% |
| evaluation | ETHUSDT | 8 | 4 | +0.4909% | -0.0784% |
| evaluation | SOLUSDT | 11 | 8 | +0.3472% | +0.2993% |

All three tokens worsen under stressed costs in 2025. Filtered BTC and ETH are
slightly negative, so the small positive pooled mean depends on SOL. Removing
SOL from the admitted filtered 2025 ledger turns its mean negative. This is a
concentration diagnostic, not a justification for selecting SOL after review.
The annual table also retains the negative 2023 result: filtered stressed mean
-0.5563%, compared with baseline -0.4624%.

| Period | Rule | Stressed mean | 95% four-week block interval |
| --- | --- | --- | --- |
| historical | baseline | +0.1037% | [-0.3772%, +0.5817%] |
| evaluation | baseline | +0.3685% | [-0.2725%, +1.0038%] |
| historical | extension_cap_1atr | +0.1834% | [-0.4211%, +0.7413%] |
| evaluation | extension_cap_1atr | +0.0635% | [-0.9848%, +1.0352%] |

All displayed intervals cross zero. The 2025 stressed difference interval is
-1.0376 to +0.3003 percentage points (four-week block resampling), so the
relative deterioration is not estimated precisely. The point result gives no
consistent improvement; it does not prove every possible extension rule fails.
Both one-week and four-week shared-calendar block intervals use 10,000 draws
with fixed seeds, including empty weeks. They are descriptive after repeated
exploration; 2025 is not an untouched holdout. Reserved 2026 is unscored.

## Verification and files

12 focused tests passed, including equality, long/short symmetry, invalid ATR,
strict breakout, signal-hour exclusion, future perturbation, missing data and
admission changes. Independently reconstructed all 143 entry geometries from
minute candles, checked all 143 original raw barriers, replayed eight admissions,
and exactly reconciled the baseline's 286 raw and 266 admitted cost rows.
150 report rows reconcile to saved ledgers. Frozen evidence includes
83 sources, nine features, six inputs, four references and 19 output hashes.

individual_trades.csv contains 430 cost-scenario rows: 133 baseline plus
82 filtered admissions, each at two cost levels. The arms overlap; these are
not 430 independent trades. excluded_baseline_trades.csv contains 104 scenario
rows for 52 excluded original trades. CSV return columns use fractions
(0.005 = 0.5%); stress 1 is base and 2 is doubled slippage; side 1 is LONG,
-1 SHORT. entry_geometry.csv records the contemporaneous filter inputs.
Raw-path/exit data are outcomes, not entry-time predictors.

## Decision and remaining plan

Close this fixed cap as an unsuccessful improvement. Retain the approved paper
baseline, including its 2% stop and 2.5% target. No runtime or approval changed.

Next: separately audit and freeze **BTC direction confirmation for ETH/SOL
hourly compression entries**. Hypothesis: alignment with broad-market direction
may reject more failed breakouts than winners. BTC's own baseline sleeve stays
unchanged; compare both the affected ETH/SOL subset and full basket. Select one
causal BTC direction rule before scoring. No extension cap is carried forward.

Then examine **ADX**, **RSI** and **Connors RSI**, as independent comparisons
against the original hourly baseline, one predeclared predicate per study.
These exact indicator definitions/cutoffs are not yet frozen or scored. No
stacking of filters or search to rescue the extension result. Audit prior
GitHub/Grokbot experiments before each comparison. Preserve the same costs,
SL/TP and occupancy, and count target winners excluded as well as stops avoided.

Broader-token replication remains pending data access under its existing frozen
protocol. Prospective paper evidence continues separately. No additional study
is running in the background and no fresh cloud monitoring is claimed.
