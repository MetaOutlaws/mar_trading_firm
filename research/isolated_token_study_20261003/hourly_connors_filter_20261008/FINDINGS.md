# Hourly Connors RSI: promising exploratory candidate

Completed 8 October 2026 Dubai (7 October UTC). The one fixed Connors RSI
exhaustion exclusion passes the predeclared POINT screen: positive stressed
mean and improvement versus the ORIGINAL hourly baseline in BOTH periods.
Retain it as a promising exploratory candidate. This is not independent edge
qualification, automatic owner approval, or deployment.

## Fixed question and overlap with prior research

Retain LONG only at completed-hour own-token ConnorsRSI(3,2,100)<=90, SHORT
only at>=10; equality passes. ORIGINAL hourly BTC/ETH/SOL compression, both
sides, same 2%SL/2.5%TP, no timeout, fees, fills, funding and capacity rules.
No BTC24, RSI14, ADX or extension filter is stacked into either arm.

Connors RSI combines short price momentum, signed streak momentum and the
relative rank of the current return. Formula motivation comes from the original
[TradingMarkets indicator specification](https://www.tradingmarkets.com/media/2012/CRHS.pdf).
Their [10/90 discussion](https://tradingmarkets.com/analytics/how-does-connorsrsi-compare-to-rsi2-1583255)
motivates fixed extreme levels; their [timeframe discussion](https://tradingmarkets.com/connorsrsi/the-most-popular-technical-indicators-1583330)
describes a daily-price research focus. None of those sources validates this
hourly crypto filter; reported returns below are from our own dataset/replay.

Exact arithmetic RSI seeds, signed-streak resets, strict-less-than prior 100
return rank and completed-hour timing were frozen in PROTOCOL.md. All components
are saved per entry. A flat history has CRSI 33.3333 under the declared tie rule.
The definition matches the earlier anatomy research, independently checked here.

Existing connors_rsi_fade is a separate reversal family with extreme-and-turning
entries and a 4h coding brief. Earlier anatomy analyzed CRSI on EMA-reclaim
signals without filtered admission replay. No exact standalone exhaustion
exclusion on these 143 hourly compression opportunities was found in inspected
records; external Grokbot runtime completeness is not certified. Protocol,
audit and the owner's RSI regime hypothesis were published BEFORE scoring at
fbc792125db770aad6a27182341f60cfd4ad29f2.

## Chronological basket results

| Period | Rule | Trades | Stops / rate | Targets | Win rate | Mean net base | Mean net stress | Stress PF |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2022–24 | baseline | 97 | 44 (45.36%) | 53 | 54.64% | +0.2268% | +0.1037% | 1.098 |
| 2022–24 | crsi_not_exhausted | 60 | 26 (43.33%) | 34 | 56.67% | +0.3193% | +0.1952% | 1.192 |
| 2025 | baseline | 36 | 14 (38.89%) | 22 | 61.11% | +0.4992% | +0.3685% | 1.400 |
| 2025 | crsi_not_exhausted | 19 | 5 (26.32%) | 14 | 73.68% | +1.0580% | +0.9205% | 2.458 |

All trades close at a stop or target, with no terminal marks. All actual stops
lose and targets win after fees/slippage/funding. Doubled-slippage stress changes
returns, not paths/counts. Positive stressed mean both periods PASS; improved
stressed mean both PASS; nonempty both PASS. All are exploratory point criteria.

## Stop-outs avoided, target winners excluded and new admissions

Historical 2022–24: the filter directly excludes 38 original admissions, comprising
**19 stops and 19 target winners**. Shared 59 trades keep identical execution.
Freed capacity admits one extra ETH SHORT at 2023-09-15 12:00 UTC, which hits its
stop. This yields 60 trades, 26 stops, 34 targets: a net reduction of 18 actual stops.
No eligible baseline trade is displaced through changed occupancy.

The excluded historical admissions average -0.1045% stressed. Removing their
-0.039706 additive return units and adding the new stop's -0.023206 gives a
+0.016499 total additive difference. The retained 59 average +0.2379% stressed,
falling to +0.1952% after the new losing admission. Base-cost additive return
falls from 0.219986 to 0.191599 because fewer trades are taken, even though mean
per trade improves. Under stress it rises from 0.100627 to 0.117127. Thus the
point screen should not be read as maximizing total return at every cost level.
Additive return units are not funded account returns.

Reused 2025: directly excludes 17 original admissions, **nine stops and eight
target winners**. No new or displaced admission. The retained 19 trades contain
five stops and 14 targets, giving 73.68% wins versus 61.11% baseline. Stop rate
falls 38.89% to 26.32%. The excluded group averages -0.2484% stressed; removing it
raises the additive return sum by 0.042235 units. This benefit is spread across
several exclusions, unlike the BTC-confirmation result's single excluded 2025 stop.

Before occupancy, 104 historical/39 evaluation raw opportunities reduce to 65/19.
Raw historical exclusions are 19 stops/20 targets; evaluation 10 stops/10 targets.
These overlap in time and are not a portfolio. Reports keep raw and admitted
scopes separate; all 143 opportunities were replayed.

## Token, side and annual limitations

| Period | Token | Baseline trades / stops | Connors trades / stops | Baseline stress mean | Connors stress mean |
| --- | --- | --- | --- | --- | --- |
| historical | BTCUSDT | 39 / 16 | 26 / 10 | +0.3442% | +0.4653% |
| historical | ETHUSDT | 36 / 20 | 20 / 11 | -0.3040% | -0.2791% |
| historical | SOLUSDT | 22 / 8 | 14 / 5 | +0.3446% | +0.3712% |
| evaluation | BTCUSDT | 17 / 7 | 9 / 3 | +0.3247% | +0.6828% |
| evaluation | ETHUSDT | 8 / 3 | 3 / 0 | +0.4909% | +2.1583% |
| evaluation | SOLUSDT | 11 / 4 | 7 / 2 | +0.3472% | +0.6957% |

Each token's stressed mean improves in both periods, but historical ETH stays
negative. The 2025 ETH sample is only three target winners, not a dependable
100% win-rate estimate. Removing any one token leaves the 2025 basket positive;
removing BTC from the historical basket leaves 34 trades at -0.0113% mean.
These leave-one-token-out figures remove trades from the full admitted ledger
without replacement replay, as predeclared.

Annual filtered stressed means: 2022 +0.3511%, 2023 +0.0481%, 2024 +0.1908%,
2025 +0.9205%. All are positive point estimates, but 2022 worsens versus its
+0.4866% baseline. The three historical annual samples have 15, 15 and 30 trades.

The side split is an important counterweight: LONG improves from +0.2837% to
+0.6040% historically and +0.2124% to +1.0700% in 2025. SHORT worsens from
-0.1223% to -0.3044% historically and +0.7743% to +0.5965% in 2025. The pooled
pass does not establish benefit for every side. Do not silently remove shorts
after viewing this diagnostic; any change needs a separately registered test.

## Uncertainty and evidence status

| Period | Rule | Stress mean | 95% one-week interval | 95% four-week interval |
| --- | --- | --- | --- | --- |
| historical | baseline | +0.1037% | [-0.3748%, +0.5851%] | [-0.3772%, +0.5817%] |
| evaluation | baseline | +0.3685% | [-0.4015%, +1.0970%] | [-0.2725%, +1.0038%] |
| historical | crsi_not_exhausted | +0.1952% | [-0.3986%, +0.7915%] | [-0.3800%, +0.7726%] |
| evaluation | crsi_not_exhausted | +0.9205% | [-0.1406%, +1.7754%] | [+0.0936%, +1.6869%] |

| Period | Stressed mean difference (pp) | 95% one-week difference interval (pp) | 95% four-week difference interval (pp) |
| --- | --- | --- | --- |
| evaluation | +0.5520 | [-0.0245, +1.1654] | [+0.0846, +1.1300] |
| historical | +0.0915 | [-0.3158, +0.4690] | [-0.2970, +0.4510] |

Historical absolute and difference intervals cross zero. The 2025 four-week
absolute and difference intervals are positive under the frozen resampling
procedure. This is a stronger descriptive result than the prior RSI exclusion,
but the 2025 ONE-week absolute and difference intervals BOTH cross zero.
The uncertainty conclusion is therefore sensitive to block length. Report both;
do not select only the positive four-week intervals. The point screen passes,
but it remains only 19 trades across 18 entry dates/17 entry weeks in repeatedly
inspected 2025. All 10,000 resamples are valid in each block/cost/period; empty
calendar weeks remain included. These intervals are not adjusted for selection
across the many previous strategy/filter experiments, and are NOT independent
confirmation. Reserved 2026 prices/outcomes remain unscored.

Connors has a higher 2025 average than BTC confirmation (+0.9205% vs +0.4505%
stressed), but a lower historical average (+0.1952% vs +0.2825%) and fewer trades.
It is not uniformly superior to the approved paper variant. Their combination
has not been scored; adding both may duplicate exclusions or lose more winners.

## Owner's retained regime hypotheses

Brian's RSI comment is saved explicitly in
../hourly_rsi_filter_20261008/REGIME_FOLLOWUP.md as H-RSI-REGIME-01: historical
2022–24 improvement, potential use in similar observable conditions, explanation
unvalidated. H-EXT-REGIME-01 remains intact. Neither calendar period is itself
a regime rule, and neither conditional filter has been deployed. Preserve all
year/token counterexamples alongside the positive aggregates.

## Verification and decision

18 focused tests passed before scoring. Independent minute-array aggregation,
scalar calculation of every CRSI component and prior anatomy convention matched
all 143 selected contexts. All 143 raw barriers, eight chronological admissions,
286 raw/266 admitted baseline cost rows and 150 report rows verified. Shared
executions/costs match. Frozen 95 source files, 9 features, 6 inputs, 4 references
and 19 output hashes checked. One successful attempt results_v1.

Ordinary CSV 424 scenario rows = (133 baseline +79 Connors admissions)*2 cost
assumptions. Arms overlap, so these are not 424 independent trades. Excluded CSV
has 55 original admissions*2 costs = 110 rows. Return columns are fractions
(0.005=0.5%), side 1 LONG/-1 SHORT, stress 1 base/2 doubled slippage. CRSI and
components are causal entry context; exits/path columns are outcomes.

Retain crsi_not_exhausted as PROMISING EXPLORATORY CANDIDATE, with no parameter
retuning. It passes the fixed aggregate screen but independent edge is not
established. BTC24 remains the owner-approved preferred PAPER variant; Connors
is not automatically approved, combined or deployed. BTC cloud activation is
still PENDING / NOT VERIFIED. No runtime/approval-book/live/leverage change.

## Next-test priority update after this result

The protocol queued common-state regime planning after the indicator series.
This positive result motivates one bounded interaction test first: ORIGINAL
baseline, BTC confirmation only, Connors only, and BOTH fixed filters. Question:
does the combination add value over EACH standalone candidate, or do they
exclude the same losses while sacrificing additional winners? Keep entries,
2%SL/2.5%TP, fees, funding and replay rules fixed. Freeze the interaction protocol
before scoring; do not call a combination qualified just because it beats the
unfiltered baseline. No combined result exists yet.

Then return to H-EXT-REGIME-01 and H-RSI-REGIME-01 using common causal market-state
definitions across both periods. Those definitions/cutoffs remain unfrozen and
unscored. This priority change preserves the owner's hypotheses and avoids
silently stacking two individually promising filters. Broader-token/prospective
confirmation stays separate. No background study is running.
