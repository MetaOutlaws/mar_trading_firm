# Entry-quality audit: primary result and handover

6 October 2026. The primary four-hour prediction audit is complete. **0 of 18 token/direction/timeframe groups passed the frozen two-period gate.** This is a prediction diagnostic, not a new trading profitability backtest.

## Evidence restored

- Original source ZIP and all six minute-candle/funding files match the archived SHA256 hashes.
- Reconstructed all 38,469 standalone-zone base-cost positions across 144 configuration-period groups.
- All 72 published 2025 rows match trade counts and stop counts exactly; mean net returns and profit factors match the published rounding.
- Original individual-row identity and original feature-enriched export were not recovered. The new ledger is explicitly labelled reconstructed.

## Primary experiment

Compared zone-rejection signals against non-signal entry-clock times matched by token, direction, timeframe, week, six-hour UTC block, 4h trend regime and discovery-defined ATR volatility tertile. Fills are measured from next-minute open. Outcome is signed close return after four hours; four hours is an observation horizon, not a trading exit or holding cap. No fees or funding are applied to this prediction metric.

| Period | Eligible signals | Matched signals | Match coverage | Mean paired uplift |
|---|---:|---:|---:|---:|
| 2022–2024 | 45,047 | 44,342 | 98.43% | -0.0020 pp |
| 2025, reused | 14,570 | 14,345 | 98.46% | -0.0675 pp |

58,687 matched signal observations; 1,126,166 control draws. These overlap and reuse control times, so they are not independent market events. Pooled means are descriptive and do not represent a portfolio.

## Every group

Numbers are signal-minus-control mean directional four-hour returns in percentage points. Positive means better entry prediction on this metric, not positive trading expectancy.

| Token | Clock | Direction | 2022–2024 uplift | 2025 uplift | Both-period gate |
|---|---|---|---:|---:|---|
| BTC | 5m | Short | +0.0120 | -0.0094 | Fail |
| BTC | 5m | Long | -0.0095 | -0.0326 | Fail |
| BTC | 15m | Short | +0.0049 | -0.0241 | Fail |
| BTC | 15m | Long | -0.0076 | -0.0545 | Fail |
| BTC | 60m | Short | -0.0073 | -0.0513 | Fail |
| BTC | 60m | Long | -0.0453 | +0.0408 | Fail |
| ETH | 5m | Short | +0.0558 | -0.3056 | Fail |
| ETH | 5m | Long | -0.0229 | +0.0383 | Fail |
| ETH | 15m | Short | +0.0234 | -0.2591 | Fail |
| ETH | 15m | Long | -0.0399 | +0.0215 | Fail |
| ETH | 60m | Short | +0.0328 | -0.3362 | Fail |
| ETH | 60m | Long | -0.0828 | -0.0366 | Fail |
| SOL | 5m | Short | +0.0093 | +0.0426 | Fail |
| SOL | 5m | Long | +0.0128 | -0.0930 | Fail |
| SOL | 15m | Short | +0.0053 | +0.0923 | Fail |
| SOL | 15m | Long | -0.0281 | -0.0747 | Fail |
| SOL | 60m | Short | -0.1210 | -0.0229 | Fail |
| SOL | 60m | Long | -0.1120 | -0.1547 | Fail |

The simultaneous confidence intervals and coverage counts are in primary_summary.csv. Only SOL 5m short and SOL 15m short have positive point estimates in both periods; neither passes the uncertainty gate. No configuration passes even the individual period gate.

## Interpretation and limits

The present rules have not demonstrated robust four-hour predictive uplift over these matched alternatives. This does not prove that every support/resistance entry is ineffective, nor does it rule out a different time horizon. It provides no basis to promote this particular entry rule or rescue it by selecting favourable subgroups after seeing results.

Matching is observational, using coarse categories. Controls can share price paths and can repeat across signals. Week and four-week calendar bootstrap intervals retain paired differences but cannot guarantee that all market dependence is captured. The 10,000-draw extreme-tail simultaneous intervals have Monte Carlo uncertainty. Prior use of 2022–2025 remains an additional selection limitation.

## Next work and current boundaries

- Primary registered comparison completed; no qualifying cell.
- One-hour/24-hour excursion diagnostics and matched costed exit comparisons remain pending. They cannot override the failed primary gate.
- A new breakout/retest entry family remains a separate prospective experiment requiring explicit frozen rules. Do not repeat already completed RSI/Connors recovery or adaptive ATR-stop tests as if they were new.
- Profit protection and any new adaptive-stop policy remain separate from entry changes. No cloud or approval changes were made.

## Validation

Two focused checks passed by direct invocation: ATR prefix causality/seed and preservation of paired constant differences in calendar-block bootstrap. Reconstruction checked the published 72-row table and total position count. Candidate files and input data hashes are verified before prediction. Future 2026 observations were excluded before feature construction.

See HANDOVER.md for the complete artifact register and restart instructions.
