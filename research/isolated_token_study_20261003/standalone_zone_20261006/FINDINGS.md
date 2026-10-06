# Standalone zone entries with wider stops: completed findings

6 October 2026. Protocol frozen in local commit49c2403 before outcomes. **None of144 configuration cells passes the predefined performance screen.** There are72 standalone-zone configurations and72 EMA entry controls. All discovery-period net means are negative. No strategy promoted or live settings changed.

## Design

Standalone zone rejection generates entries directly, without an EMA-cross trigger. Existing completed4h EMA50/200 trend regime remains required. Hourly pivot bands must be confirmed before the rejection candle opens and still active at its close. Long candles overlap support and close above the band and their own open; shorts mirror at resistance. Enter next minute open with ordinary gaps/costs. No oscillator, daily-structure or opposing-zone room filter.

Tested1%stop/2.5%TP control, requested2%/2.5% and3%/3%, plus3%/2.5% bridge. The bridge isolates stop widening from TP change. Both entry families use identical four combinations. BTC/ETH/SOL, long/short,5m/15m/1h;2022–2024 discovery and reused2025 validation. Original regime exits, fees, slippage and historical funding retained; no holding cap.1152aggregate rows and432 old EMA reference checks completed. No2026 features or outcomes used.

## 2025 chronological results, pooled

Trade-weighted descriptions across separate strategies, not portfolio returns. Each arm schedules independently, so counts differ. Stop rate uses completed trades. Net/trade is return on trade notional; meanR divides each trade by its initial stop fraction. Wider stops lower unit-risk exposure at equal initial risk; that is different from fixed-notional accounting.

| Entry | Stop / TP | Completed | Stops | Stop rate | Net/trade | Mean R |
|---|---|---:|---:|---:|---:|---:|
| ema20 | 1% / 2.5% | 4,800 | 3,259 | 67.90% | -0.2352% | -0.2352 |
| ema20 | 2% / 2.5% | 3,193 | 1,621 | 50.77% | -0.2731% | -0.1366 |
| ema20 | 3% / 2.5% | 2,468 | 924 | 37.44% | -0.2580% | -0.0860 |
| ema20 | 3% / 3% | 2,230 | 906 | 40.63% | -0.2687% | -0.0896 |
| zone_rejection | 1% / 2.5% | 3,409 | 2,328 | 68.29% | -0.3208% | -0.3208 |
| zone_rejection | 2% / 2.5% | 2,321 | 1,166 | 50.24% | -0.3937% | -0.1969 |
| zone_rejection | 3% / 2.5% | 1,853 | 668 | 36.05% | -0.3851% | -0.1284 |
| zone_rejection | 3% / 3% | 1,719 | 667 | 38.80% | -0.3867% | -0.1289 |

Wider stops reduce stop frequency substantially, but all pooled returns remain negative. Under fixed-notional accounting every wider-stop arm has worse pooled2025 net/trade than its own1%control. Risk-scaled losses are smaller but still negative. Standalone-zone pooled results are worse than the corresponding EMA controls. Pooled totals are not proof about every token/timeframe.

## Did the1% stop cut off recoveries?

Yes, some trades recover under the wider-stop policy. Below we hold the exact executed1%baseline entries fixed and follow their actual alternative exits. Denominator is the same original stopped-out cohort for every row within a family. A rescued winner means positive net after costs/funding; target-hit count is separately recorded in CSVs. Worse means lower net return than that same trade with1%stop. These alternative paths can overlap and are diagnostics, not a tradable portfolio schedule.

| Entry | Alternative stop / TP | Original1% stops | Become net winners | Stop again | Worse net outcomes | Mean net change (pp) |
|---|---|---:|---:|---:|---:|---:|
| ema20 | 2% / 2.5% | 3,259 | 596 | 2,480 | 2,564 | -0.1215 |
| ema20 | 3% / 2.5% | 3,259 | 1,018 | 1,795 | 2,121 | -0.0758 |
| ema20 | 3% / 3% | 3,259 | 928 | 1,870 | 2,205 | -0.0787 |
| zone_rejection | 2% / 2.5% | 2,328 | 401 | 1,707 | 1,809 | -0.1311 |
| zone_rejection | 3% / 2.5% | 2,328 | 681 | 1,171 | 1,498 | -0.0681 |
| zone_rejection | 3% / 3% | 2,328 | 615 | 1,222 | 1,554 | -0.0811 |

For zone entries,2%/2.5% rescues401/2328(17.2%) original stop-outs;3%/3% rescues615/2328(26.4%). But1809 and1554 original stop-outs respectively have worse net outcomes. The average changes remain negative even within the stopped-out cohort. A later recovery on selected examples therefore cannot justify widening every stop. Regime exits and additional funding remain part of each counterfactual path.

## All matched baseline entries: improvements versus deterioration

These include winners and other exits as well as stops. Sums use additive unit-notional return units, not account equity. Gain/loss columns aggregate positive and negative paired net differences respectively. Different entry families have different baseline cohorts.

| Entry | Alternative stop / TP | Matched entries | Improvement sum | Deterioration sum | Net difference sum |
|---|---|---:|---:|---:|---:|
| ema20 | 2% / 2.5% | 4,800 | 21.1130 | 25.0727 | -3.9597 |
| ema20 | 3% / 2.5% | 4,800 | 35.8897 | 38.3605 | -2.4708 |
| ema20 | 3% / 3% | 4,800 | 43.4182 | 46.4646 | -3.0464 |
| zone_rejection | 2% / 2.5% | 3,409 | 14.3294 | 17.3818 | -3.0523 |
| zone_rejection | 3% / 2.5% | 3,409 | 24.1279 | 25.7124 | -1.5845 |
| zone_rejection | 3% / 3% | 3,409 | 28.5990 | 30.9333 | -2.3343 |

## Every standalone-zone2025 cell at base costs

| Token | TF min | Side | Stop / TP | Completed | Stops | Stop rate | Net/trade | PF |
|---|---:|---|---|---:|---:|---:|---:|---:|
| BTCUSDT | 5 | short | 1% / 2.5% | 165 | 102 | 61.82% | -0.2455% | 0.685 |
| BTCUSDT | 5 | short | 2% / 2.5% | 115 | 47 | 40.87% | -0.2803% | 0.734 |
| BTCUSDT | 5 | short | 3% / 2.5% | 93 | 25 | 26.88% | -0.2466% | 0.790 |
| BTCUSDT | 5 | short | 3% / 3% | 88 | 24 | 27.27% | -0.1139% | 0.904 |
| BTCUSDT | 5 | long | 1% / 2.5% | 118 | 69 | 58.47% | -0.2180% | 0.720 |
| BTCUSDT | 5 | long | 2% / 2.5% | 67 | 20 | 29.85% | -0.0021% | 0.998 |
| BTCUSDT | 5 | long | 3% / 2.5% | 58 | 12 | 20.69% | -0.1286% | 0.884 |
| BTCUSDT | 5 | long | 3% / 3% | 52 | 11 | 21.15% | -0.0746% | 0.935 |
| BTCUSDT | 15 | short | 1% / 2.5% | 145 | 92 | 63.45% | -0.2968% | 0.633 |
| BTCUSDT | 15 | short | 2% / 2.5% | 105 | 48 | 45.71% | -0.4413% | 0.616 |
| BTCUSDT | 15 | short | 3% / 2.5% | 83 | 24 | 28.92% | -0.3531% | 0.723 |
| BTCUSDT | 15 | short | 3% / 3% | 78 | 23 | 29.49% | -0.2837% | 0.786 |
| BTCUSDT | 15 | long | 1% / 2.5% | 103 | 60 | 58.25% | -0.1538% | 0.801 |
| BTCUSDT | 15 | long | 2% / 2.5% | 66 | 21 | 31.82% | -0.0471% | 0.950 |
| BTCUSDT | 15 | long | 3% / 2.5% | 56 | 12 | 21.43% | -0.1410% | 0.874 |
| BTCUSDT | 15 | long | 3% / 3% | 52 | 12 | 23.08% | -0.0939% | 0.919 |
| BTCUSDT | 60 | short | 1% / 2.5% | 128 | 84 | 65.62% | -0.2904% | 0.645 |
| BTCUSDT | 60 | short | 2% / 2.5% | 88 | 40 | 45.45% | -0.3092% | 0.726 |
| BTCUSDT | 60 | short | 3% / 2.5% | 76 | 22 | 28.95% | -0.2924% | 0.771 |
| BTCUSDT | 60 | short | 3% / 3% | 68 | 21 | 30.88% | -0.3407% | 0.754 |
| BTCUSDT | 60 | long | 1% / 2.5% | 78 | 41 | 52.56% | 0.0400% | 1.058 |
| BTCUSDT | 60 | long | 2% / 2.5% | 55 | 17 | 30.91% | 0.1184% | 1.136 |
| BTCUSDT | 60 | long | 3% / 2.5% | 48 | 10 | 20.83% | 0.0739% | 1.073 |
| BTCUSDT | 60 | long | 3% / 3% | 42 | 9 | 21.43% | 0.1285% | 1.122 |
| ETHUSDT | 5 | short | 1% / 2.5% | 276 | 202 | 73.19% | -0.4302% | 0.525 |
| ETHUSDT | 5 | short | 2% / 2.5% | 184 | 102 | 55.43% | -0.5755% | 0.560 |
| ETHUSDT | 5 | short | 3% / 2.5% | 146 | 61 | 41.78% | -0.6503% | 0.574 |
| ETHUSDT | 5 | short | 3% / 3% | 141 | 64 | 45.39% | -0.7099% | 0.570 |
| ETHUSDT | 5 | long | 1% / 2.5% | 189 | 131 | 69.31% | -0.2627% | 0.692 |
| ETHUSDT | 5 | long | 2% / 2.5% | 120 | 56 | 46.67% | -0.2219% | 0.804 |
| ETHUSDT | 5 | long | 3% / 2.5% | 89 | 30 | 33.71% | -0.1489% | 0.881 |
| ETHUSDT | 5 | long | 3% / 3% | 84 | 30 | 35.71% | -0.0748% | 0.944 |
| ETHUSDT | 15 | short | 1% / 2.5% | 261 | 186 | 71.26% | -0.3948% | 0.556 |
| ETHUSDT | 15 | short | 2% / 2.5% | 180 | 102 | 56.67% | -0.6074% | 0.542 |
| ETHUSDT | 15 | short | 3% / 2.5% | 142 | 62 | 43.66% | -0.7282% | 0.539 |
| ETHUSDT | 15 | short | 3% / 3% | 135 | 60 | 44.44% | -0.6337% | 0.608 |
| ETHUSDT | 15 | long | 1% / 2.5% | 173 | 120 | 69.36% | -0.2297% | 0.728 |
| ETHUSDT | 15 | long | 2% / 2.5% | 111 | 55 | 49.55% | -0.2035% | 0.825 |
| ETHUSDT | 15 | long | 3% / 2.5% | 85 | 27 | 31.76% | 0.0044% | 1.004 |
| ETHUSDT | 15 | long | 3% / 3% | 77 | 27 | 35.06% | -0.0000% | 1.000 |
| ETHUSDT | 60 | short | 1% / 2.5% | 179 | 128 | 71.51% | -0.3471% | 0.608 |
| ETHUSDT | 60 | short | 2% / 2.5% | 137 | 80 | 58.39% | -0.6142% | 0.549 |
| ETHUSDT | 60 | short | 3% / 2.5% | 110 | 46 | 41.82% | -0.6118% | 0.608 |
| ETHUSDT | 60 | short | 3% / 3% | 107 | 47 | 43.93% | -0.5071% | 0.686 |
| ETHUSDT | 60 | long | 1% / 2.5% | 136 | 88 | 64.71% | -0.0782% | 0.901 |
| ETHUSDT | 60 | long | 2% / 2.5% | 94 | 43 | 45.74% | 0.0019% | 1.002 |
| ETHUSDT | 60 | long | 3% / 2.5% | 73 | 24 | 32.88% | 0.0700% | 1.060 |
| ETHUSDT | 60 | long | 3% / 3% | 67 | 24 | 35.82% | 0.1163% | 1.091 |
| SOLUSDT | 5 | short | 1% / 2.5% | 342 | 237 | 69.30% | -0.3447% | 0.628 |
| SOLUSDT | 5 | short | 2% / 2.5% | 230 | 120 | 52.17% | -0.4035% | 0.682 |
| SOLUSDT | 5 | short | 3% / 2.5% | 185 | 72 | 38.92% | -0.4076% | 0.723 |
| SOLUSDT | 5 | short | 3% / 3% | 168 | 70 | 41.67% | -0.4175% | 0.737 |
| SOLUSDT | 5 | long | 1% / 2.5% | 268 | 198 | 73.88% | -0.5216% | 0.467 |
| SOLUSDT | 5 | long | 2% / 2.5% | 165 | 94 | 56.97% | -0.6683% | 0.513 |
| SOLUSDT | 5 | long | 3% / 2.5% | 117 | 49 | 41.88% | -0.6568% | 0.581 |
| SOLUSDT | 5 | long | 3% / 3% | 111 | 51 | 45.95% | -0.7303% | 0.573 |
| SOLUSDT | 15 | short | 1% / 2.5% | 297 | 205 | 69.02% | -0.3434% | 0.629 |
| SOLUSDT | 15 | short | 2% / 2.5% | 203 | 107 | 52.71% | -0.4022% | 0.685 |
| SOLUSDT | 15 | short | 3% / 2.5% | 168 | 65 | 38.69% | -0.3687% | 0.746 |
| SOLUSDT | 15 | short | 3% / 3% | 155 | 66 | 42.58% | -0.3936% | 0.752 |
| SOLUSDT | 15 | long | 1% / 2.5% | 207 | 149 | 71.98% | -0.4559% | 0.522 |
| SOLUSDT | 15 | long | 2% / 2.5% | 142 | 78 | 54.93% | -0.5727% | 0.568 |
| SOLUSDT | 15 | long | 3% / 2.5% | 112 | 46 | 41.07% | -0.6233% | 0.599 |
| SOLUSDT | 15 | long | 3% / 3% | 99 | 46 | 46.46% | -0.8312% | 0.532 |
| SOLUSDT | 60 | short | 1% / 2.5% | 201 | 136 | 67.66% | -0.2224% | 0.751 |
| SOLUSDT | 60 | short | 2% / 2.5% | 152 | 80 | 52.63% | -0.3072% | 0.754 |
| SOLUSDT | 60 | short | 3% / 2.5% | 123 | 45 | 36.59% | -0.2299% | 0.835 |
| SOLUSDT | 60 | short | 3% / 3% | 112 | 46 | 41.07% | -0.2803% | 0.820 |
| SOLUSDT | 60 | long | 1% / 2.5% | 143 | 100 | 69.93% | -0.3618% | 0.610 |
| SOLUSDT | 60 | long | 2% / 2.5% | 107 | 56 | 52.34% | -0.4696% | 0.635 |
| SOLUSDT | 60 | long | 3% / 2.5% | 89 | 36 | 40.45% | -0.4677% | 0.683 |
| SOLUSDT | 60 | long | 3% / 3% | 83 | 36 | 43.37% | -0.5028% | 0.686 |

## Checks and limits

All six raw-data hashes match prior studies. All432 old EMA reference rows match counts, means and exit reasons; maximum absolute mean difference <1e-15. Three new rejection tests and seven existing zone-map tests pass. Imported execution engine is unchanged from the scalar-checked prior studies. Manifest records protocol commit and source/input hashes. Full evidence retains zone identity/confirmation/rejection timestamps, all candidates, chronological base/stress trades and matched alternative paths. Annual CSVs, holding times, fees/funding, average loss, boundary counts and fixed-notional/initial-R MTM drawdowns are included.

Screen requires>=50completed trades in EACH period, positive baseline mean and PF>=1.15 both, and positive mean under doubled slippage both. All discovery means are negative, so none qualifies. Isolated positive2025 cells, such as BTC1h long, are not confirmed winners. Repeated research on2022–2025 reduces independence; no statistical-significance or optimal-stop claim is made.

Conclusion: the user's concern is partly supported—1%does cut off trades that subsequently become profitable—but widening stops uniformly does not improve fixed-notional expectancy in these tests. The next planned entry family remains breakout/retest, with its own frozen rules. Recovery subgroups may motivate hypotheses using entry-known features, but may not be selected by knowing which trades later recovered. No additional tuning or deployment performed.
