# BTC / ETH / SOL compression diagnostic — findings

Completed 7 October 2026 UTC. User requested execution on the three available tokens while additional-token data remained unavailable.

## Decision

The predeclared pooled compression entry does **not demonstrate a profitable edge** on these three assets. Both stop/target arms have negative mean net returns in historical 2022–24 and reused evaluation 2025, at base and stressed costs. The 3% stop / 3% target arm performs worse in 2025. This comparison changes both barriers and the admitted trades; it does not isolate the effect of widening the stop.

No production configuration, approvals, scanner or leverage settings changed. No 2026 price outcomes were scored. These are previously studied assets and years, so the run is a diagnostic, not independent replication.

## 2025 pooled results

All 5m, 15m and 60m clocks and both directions compete under one-position-per-token admission.

| SL / TP | Trades | Closed | Terminal marks | Closed win rate | Stops / closed | Mean net, base | Mean net, stress |
|---|---|---|---|---|---|---|---|
| 2% / 2.5% | 222 | 222 | 0 | 48.6% | 114/222 (51.4%) | -0.0559% | -0.1839% |
| 3% / 3% | 196 | 195 | 1 | 47.7% | 102/195 (52.3%) | -0.3885% | -0.5196% |

Mean returns include fees, slippage, actual cached settled funding and terminal marks. Stop fractions and win rates use completed positions only. The 3%/3% arm has one BTC terminal mark at the end of 2025, net -0.5351% at base and -0.6346% at stress. Its completed-trade mean is -0.3877% base and -0.5190% stress. Base/stress replay the same quoted exits and admissions; stress doubles slippage only. Counts must not be added across the two cost scenarios or across the two alternative arms.

The primary arm has 108 target hits and 114 stops. The wider arm has 93 target hits and 102 stops, plus the terminal mark. There are no regime exits or ambiguous stop/target candles in either pooled 2025 arm.

## Historical context, 2022–24

| SL / TP | Trades | Stops | Mean net, base | Mean net, stress |
|---|---|---|---|---|
| 2% / 2.5% | 780 | 435 | -0.2515% | -0.3809% |
| 3% / 3% | 670 | 331 | -0.2102% | -0.3422% |

Monthly eligibility starts in April 2022 because the archive begins in January and the frozen rule requires 90 observed days. All three assets qualify in every subsequent month through December 2025. All completed daily observations are required; monthly ranking uses only the preceding 30 days. Annual primary base means are -0.1724% in 2022, -0.4631% in 2023, -0.1153% in 2024 and -0.0559% in 2025. The historical replay carries trades across year boundaries; annual tables attribute outcomes to entry year.

## Uncertainty and qualification

| SL / TP | Costs | 95% CI, 1-week blocks | 95% CI, 4-week blocks |
|---|---|---|---|
| 2% / 2.5% | base | -0.3814% to +0.2760% | -0.3479% to +0.2329% |
| 2% / 2.5% | stress | -0.5098% to +0.1487% | -0.4776% to +0.1049% |
| 3% / 3% | base | -0.8137% to +0.0337% | -0.8314% to +0.0280% |
| 3% / 3% | stress | -0.9449% to -0.0983% | -0.9638% to -0.1038% |

Intervals are for mean net return per trade, obtained by converting nominal-stop R back to return units. Both calendar-week block lengths use 10,000 draws; tokens are sampled together and zero-trade weeks are included. These conditional intervals do not adjust for previous hypothesis selection. They cannot establish performance on unseen assets or years.

The primary has 222 closed positions across 171 entry dates and 53 calendar-week bins (including partial boundary weeks), meeting the original numerical trade/date/week support thresholds. Its mean and lower confidence bounds fail. Removing any one token does not produce uniformly positive stressed expectancy. The eight-new-token requirement is unavailable: this run contains zero new tokens and only three reference tokens. No arm qualifies. Funding gap checks pass, but independent historical cadence/universe certification remains incomplete.

## Where the remaining exploratory lead sits

Primary 2% stop / 2.5% target, grouped by the clock of the **admitted** signal:

| tf | Trades | Stops | Win rate | Mean net, base | Mean net, stress |
|---|---|---|---|---|---|
| 5m | 143 | 78 (54.5%) | 45.5% | -0.1987% | -0.3268% |
| 15m | 52 | 25 (48.1%) | 51.9% | +0.0896% | -0.0354% |
| 60m | 27 | 11 (40.7%) | 59.3% | +0.4201% | +0.2869% |

The admitted 60m subset also has positive historical 2022–24 mean: +0.3308% base and +0.2000% stress over 63 trades. The 2025 subset has only 27 trades; its mean is +0.4201% base and +0.2869% stress. Its 95% confidence intervals cross zero under both block lengths and cost levels. This is a descriptive lead observed after subgroup review. It is not a standalone 1h-only replay: some 1h signals were unavailable because other clocks occupied the token. Removing 5m/15m requires a fresh occupancy replay and then independent confirmation, not arithmetic subtraction from this pooled result. `clock_diagnostics.csv` includes conditional subgroup intervals.

The 5m subset is negative in both periods. The 15m subset is negative in historical context, and its modest positive 2025 base mean disappears with stressed slippage. The all-clock test therefore fails despite sparse positive hourly observations. Do not promote the best historical subgroup or tune its thresholds after seeing these results.

### Token contributions, primary arm

| symbol | Trades | Stops | Win rate | Mean net, base | Mean net, stress |
|---|---|---|---|---|---|
| BTCUSDT | 96 | 49 (51.0%) | 49.0% | -0.0187% | -0.1188% |
| ETHUSDT | 64 | 31 (48.4%) | 51.6% | +0.1065% | +0.0066% |
| SOLUSDT | 62 | 34 (54.8%) | 45.2% | -0.2812% | -0.4813% |

### Direction contributions, primary arm

| side | Trades | Stops | Win rate | Mean net, base | Mean net, stress |
|---|---|---|---|---|---|
| Short | 94 | 49 (52.1%) | 47.9% | -0.0745% | -0.2003% |
| Long | 128 | 65 (50.8%) | 49.2% | -0.0423% | -0.1718% |

ETH is the only token with positive primary 2025 mean at base and stress; stressed mean is only +0.0066%. Both pooled directions are negative. These subgroups retain pooled admission and are descriptive, with no per-token strategy approval.

## Costs and admission

Primary 2025 mean quoted return is +0.1892%; average base slippage drag is 0.1280%, fees 0.1100%, and funding cost 0.0071%, leaving -0.0559%. Under stress the slippage drag is 0.2560%, leaving -0.1839%. A positive move before costs does not meet the experiment's net-profitability criterion.

There are 300 eligible raw 2025 compression opportunities per arm before occupancy. Primary admits 222: 77 token-busy skips and one lower-clock-priority skip. The wider arm admits 196: 103 token-busy skips and one lower-clock-priority skip. Median holding time rises from 12.08 to 18.81 hours. The six-position cap cannot bind with only three tokens, so this run does not test a larger basket's capacity or correlated margin exposure.

## Verification

- Original data ZIP and both saved code/evidence ZIP hashes verified, including 79 kit and 145 discovery payload hashes.
- All six candle/funding hashes and nine cached feature hashes match the frozen discovery manifest. Each asset has 2,103,840 complete minute observations for 2022–25.
- The original compression engine reconciles all 216 prior reference cells. Four focused causality/admission/gate tests pass.
- 18 signal groups exactly match the original entry function. 2,992 raw base-cost opportunities pass direct candle-by-candle first-barrier verification. This includes opportunities rejected by pooled admission.
- Eight independently replayed admission runs match accepted identities and rejection counts; one position per token and conservative same-minute occupancy hold.
- 8 pooled, 208 subgroup and 16 annual summaries reconcile with 3,736 ledger rows across alternative arms/periods/cost scenarios. Cost identities and pre-2026 execution bounds pass.

## Files and handover

`individual_trades.csv` is an ordinary uncompressed CSV with all 3,736 accepted ledger rows, both periods, both alternative arms and both cost scenarios; filter `partition`, `stop` and `stress` before interpreting it. `all_opportunities.parquet`, `signals.parquet` and `rejections.csv` preserve the full admission history. `pooled_results.csv`, `pooled_subgroups.csv`, `annual_by_entry_year.csv`, `leave_one_token_out.csv` and `clock_diagnostics.csv` contain the aggregate evidence.

`PROTOCOL.md`, frozen hashes, verification, exact runner and dependency source are retained in the private checkpoint. Original market-data ZIP remains a separately indexed required input. Public GitHub receives reports, protocols and aggregate tables only. Cumulative trade-return units and additive entry-order drawdown in compatibility tables are not account returns or account drawdown.

## Next decision

Keep the failed pooled rule unapproved. Preserve the unchanged rule for the already planned broader-token replication when its data are available. If a separate 1h-only hypothesis is pursued, freeze it as a new experiment, replay all raw hourly opportunities under shared occupancy, and seek new-asset or forward confirmation. No additional filters, stop optimization or leverage experiment were run in this task.
