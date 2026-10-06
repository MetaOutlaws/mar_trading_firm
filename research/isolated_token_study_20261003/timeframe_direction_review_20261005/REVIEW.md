# Entry timeframe, direction and market context review

5 October 2026. This is a re-analysis of archived results, not a new performance test. No 2026 outcomes were opened.

## Fixed-reference comparison

Every row uses the same EMA20 reclaim entry, completed 4h EMA50/200 regime, fixed 1% stop, 2.5% target and regime-reversal exit. One position per configuration. Base fees, slippage and historical funding included. No holding-time exit. These are descriptive comparisons, not newly selected winners.

Cells show mean net return as a percentage of entry notional, followed by completed trade count. Means include boundary marks; detailed CSV includes both total observations and completed counts. Discovery-year results are attributed by entry year within the continuous 2022–2024 partition, not independently restarted annual simulations.

| Token | Direction | Entry | 2022 | 2023 | 2024 | 2025 |
|---|---|---|---|---|---|---|
| BTCUSDT | Long | 5m | -0.434% (139) | -0.099% (295) | -0.099% (334) | -0.158% (147) |
| BTCUSDT | Long | 15m | -0.323% (94) | -0.182% (236) | -0.110% (256) | +0.016% (106) |
| BTCUSDT | Long | 60m | -0.597% (51) | -0.002% (116) | +0.075% (134) | +0.030% (69) |
| BTCUSDT | Short | 5m | -0.238% (514) | -0.161% (91) | -0.281% (194) | -0.230% (279) |
| BTCUSDT | Short | 15m | -0.162% (344) | -0.152% (65) | -0.295% (132) | -0.112% (186) |
| BTCUSDT | Short | 60m | -0.190% (165) | -0.311% (38) | -0.127% (63) | -0.274% (101) |
| ETHUSDT | Long | 5m | -0.250% (252) | -0.360% (355) | -0.194% (377) | -0.143% (319) |
| ETHUSDT | Long | 15m | -0.258% (184) | -0.394% (255) | -0.209% (274) | -0.221% (220) |
| ETHUSDT | Long | 60m | -0.199% (69) | -0.249% (129) | -0.184% (124) | -0.105% (93) |
| ETHUSDT | Short | 5m | -0.195% (707) | -0.182% (120) | -0.213% (337) | -0.267% (594) |
| ETHUSDT | Short | 15m | -0.089% (435) | -0.296% (94) | -0.265% (227) | -0.148% (359) |
| ETHUSDT | Short | 60m | -0.189% (165) | -0.302% (56) | -0.322% (121) | -0.393% (169) |
| SOLUSDT | Long | 5m | -0.239% (231) | -0.277% (971) | -0.357% (735) | -0.304% (444) |
| SOLUSDT | Long | 15m | -0.329% (130) | -0.284% (579) | -0.377% (459) | -0.189% (276) |
| SOLUSDT | Long | 60m | -0.436% (48) | -0.251% (212) | -0.405% (192) | -0.187% (115) |
| SOLUSDT | Short | 5m | -0.290% (1153) | -0.283% (296) | -0.344% (445) | -0.302% (711) |
| SOLUSDT | Short | 15m | -0.211% (649) | -0.388% (204) | -0.355% (264) | -0.298% (434) |
| SOLUSDT | Short | 60m | -0.235% (231) | -0.437% (97) | -0.393% (103) | -0.348% (178) |

## What was actually implemented

| Component | Baseline / parameter optimization | Earlier context study (PR97) |
|---|---|---|
| Completed 4h trend regime | Yes: fast/slow EMA alignment, close relative to slow EMA and fast EMA slope over 3 completed bars | Yes |
| Daily context | No | No |
| Confirmed higher highs/higher lows or lower highs/lower lows | No in optimization | Optional 4h structural filter with 2-bar pivot confirmation |
| Entry near bottom/top of a defined range | No | No explicit range-position test |
| Support/resistance rejection | No | Optional confirmed hourly pivot bands and rejection |
| Observed supply/demand orders or order-flow | No | No; candle-derived proxy only |
| Break-and-retest entry | No | No |
| AI exit decisions | No; deterministic EMA-regime exits only | No |

## Direction and selection coverage

The six optimized report rows did not blend long and short trades: BTC was long in both folds, ETH short in both, SOL short in both. Each comparison reference uses the selected side/timeframe. The broad loss-diagnostic summaries do pool directions/settings and overlap trades; they must not be used to infer a side-specific edge.

Each token/fold initially tested 36 entry settings: 3 timeframes × 2 directions × 3 entry EMAs × 2 regime EMA pairs. Each side/timeframe therefore had 6 Stage A settings. Only the top TWO entries overall advanced to Stage B, which tested 18 stop/target/exit combinations for each. This selection could eliminate a whole direction or timeframe before later-year evaluation.

Total: (36 + 36) × 3 tokens × 2 folds = 432 setting evaluations; 864 rows including two costs, 261 distinct token/configuration pairs. Six selected token/fold configurations were evaluated against reference and entry-only variants under two costs, producing 36 later-period rows. The other training outcomes are preserved in training_ledger.csv. They were not all evaluated in 2025. The earlier baseline and context studies separately evaluated 180 and 720 configurations across their prescribed periods. These counts are overlapping designs, not independent discoveries.

## Interpretation

At the fixed 2.5% target, BTC long 1h improves from negative 2022/2023 to positive 2024/2025. BTC short remains negative at all three clocks in all four years. ETH and SOL are negative in all cells shown. The relative ordering depends on side and year: there is no universal best entry timeframe. Positive annual slices are not evidence of a qualified strategy and this reference is only one target/exit definition.

The omission of daily structure and explicit pullback location means the full top-down system Brian describes has not been tested. The failure of EMA reclaim and one restrictive zone proxy does not establish that all top-down pullback/reversal patterns fail. Equally, adding those rules is a hypothesis, not an assumed improvement.

## Files

- all_baseline_annual_results.csv: all archived annual baseline rows, with target, side, timeframe, year and cost identity.
- fixed_reference_by_year_timeframe_direction.csv: 72 comparable cells underlying this table.
- all_context_configurations_by_direction.csv: all 720 context configurations, discovery/validation and stress fields.
- search_coverage.csv: actual optimization attempts by token/fold/stage/timeframe/side.
- ../diagnostic_optimization_20261004/results/training_ledger.csv: every training attempt and score.
- NEXT_TEST_DESIGN.md: proposed experiment, not yet executed.

Reproduce with python research/isolated_token_study_20261003/timeframe_direction_review_20261005/build_review.py.


## Publication scope

This GitHub publication contains written findings and aggregate comparison tables only. Source scripts, detailed configuration ledgers and trade evidence referenced above remain in the local research package pending specific export approval. No production changes or new tests were executed for this publication.
