# Entry-family follow-ups — completed findings

7 October 2026. BTC, ETH and SOL; three predeclared comparisons. Protocol published before scoring. Historical context 2022–24; reused evaluation 2025. No 2026 price outcomes or new tokens. No production settings changed.

## Decision

Only these hypotheses meet the frozen local continuation point criterion: hourly_compression. No independent edge or deployment qualification is established by these reused-data diagnostics. The primary arm is 2% stop / 2.5% target; the 3%/3% arm is descriptive sensitivity.

| Hypothesis | Positive treatment at stress in both periods | Positive difference at stress in both periods | Local decision | Independent edge established |
|---|---|---|---|---|
| hourly_compression | yes | yes | exploratory_continuation | no |
| funding_condition | no | no | no_continuation_support | no |
| trend_alignment | no | no | no_continuation_support | no |

For hourly compression, continuation requires positive stressed treatment means in both periods; the difference versus all clocks is descriptive. Funding and trend also require positive stressed differences versus their comparators in both periods. Wider-arm results cannot rescue primary failure. Wide intervals and token/year concentration keep any continuation exploratory.

## Primary 2025 results: 2% SL / 2.5% TP

| Variant | Trades | Closed | Marks | Stops | Stops/closed | Closed win rate | Net/trade, base | Net/trade, stress |
|---|---|---|---|---|---|---|---|---|
| Compression, all clocks | 222 | 222 | 0 | 114 | 51.4% | 48.6% | -0.0559% | -0.1839% |
| Compression, 1h only | 36 | 36 | 0 | 14 | 38.9% | 61.1% | +0.4992% | +0.3685% |
| Breakout without extreme-funding condition | 1465 | 1462 | 3 | 800 | 54.7% | 45.3% | -0.2210% | -0.3663% |
| Original extreme-funding breakout | 213 | 211 | 2 | 124 | 58.8% | 41.2% | -0.3952% | -0.5490% |
| Original trend pullback | 363 | 361 | 2 | 193 | 53.5% | 46.5% | -0.1538% | -0.2927% |
| Trend pullback + aligned 4h regime | 220 | 220 | 0 | 115 | 52.3% | 47.7% | -0.1036% | -0.2440% |

Average net returns include fees, slippage, actual settled funding and explicit terminal marks. Stop fractions and win rates use closed positions only. Return values are per-trade percentages, not account returns. Each variant and each cost scenario is an alternative replay; counts must not be added together.

## Historical context: 2022–24, primary arm

| Variant | Trades | Closed | Marks | Stops | Stops/closed | Closed win rate | Net/trade, base | Net/trade, stress |
|---|---|---|---|---|---|---|---|---|
| Compression, all clocks | 780 | 780 | 0 | 435 | 55.8% | 44.2% | -0.2515% | -0.3809% |
| Compression, 1h only | 97 | 97 | 0 | 44 | 45.4% | 54.6% | +0.2268% | +0.1037% |
| Breakout without extreme-funding condition | 4266 | 4264 | 2 | 2431 | 57.0% | 43.0% | -0.3246% | -0.4730% |
| Original extreme-funding breakout | 934 | 934 | 0 | 529 | 56.6% | 43.4% | -0.2825% | -0.4210% |
| Original trend pullback | 1058 | 1058 | 0 | 611 | 57.8% | 42.2% | -0.3475% | -0.4842% |
| Trend pullback + aligned 4h regime | 657 | 657 | 0 | 384 | 58.4% | 41.6% | -0.3810% | -0.5162% |

The original membership rule starts entries in April 2022 after 90 observed days. Positions can cross 2022/23 and 2023/24 inside this historical partition. The annual table uses entry-year attribution, not extra forced year-end closes.

## What the tests changed

Hourly compression removes 5m and 15m entries from the basket and replays every unchanged hourly candidate. Funding compares the original extreme settled-funding predicate against the same six-hour breakout, momentum, candle, funding-age and per-settlement de-duplication rules without that predicate. Trend adds only the completed 4h regime agreeing with the trade to the unchanged pullback rule. The 4h regime is an entry condition here, not an exit.

The all-clock compression comparator exactly reproduces the prior ledger and summary. Neither the old positive screenshot examples nor the former 27-trade hourly subset are treated as a new test result.

Clarification to the funding protocol's discussion of first qualifying events: the frozen feature tables hold the settled rate and its quantiles constant between settlements. On these data, the predicate selects funding episodes; additional earlier entries in the unfiltered basket can then change occupancy across episodes. A changing funding value within one settled episode is not assumed in the market replay. This clarification does not change a rule or result.

## Incremental effect and uncertainty

Stressed treatment-minus-comparator mean differences, primary arm (percentage points per trade):

| Comparison | 2022–24 difference | 2025 difference | 2025 difference 95% CI, 4-week blocks |
|---|---|---|---|
| hourly_compression | +0.4847% | +0.5524% | +0.0075% to +1.0947% |
| funding_condition | +0.0520% | -0.1828% | -0.4034% to +0.0592% |
| trend_alignment | -0.0320% | +0.0487% | -0.1897% to +0.3000% |

Absolute stressed treatment means and uncertainty in 2025:

| Treatment | Mean net | 95% CI, 1-week blocks | 95% CI, 4-week blocks | Entry dates | Week bins | Worst leave-one-token-out mean |
|---|---|---|---|---|---|---|
| Compression, 1h only | +0.3685% | -0.4015% to +1.0970% | -0.2725% to +1.0038% | 30 | 26 | +0.3335% |
| Original extreme-funding breakout | -0.5490% | -0.8983% to -0.1907% | -0.8265% to -0.2371% | 129 | 43 | -0.6231% |
| Trend pullback + aligned 4h regime | -0.2440% | -0.6353% to +0.1318% | -0.6314% to +0.1622% | 111 | 46 | -0.2808% |

Both baskets use common calendar-block draws, 10,000 draws at each block length, including empty weeks and all tokens together. Each basket has its own sampled trade-count denominator. These are observational strategy contrasts, not matched trades or randomized causal effects. A higher mean with fewer trades is not automatically a higher account return.

The intervals are conditional on reused history. They do not correct for selection across these three hypotheses, all descriptive subgroups, or earlier experiments. New-token/forward confirmation must predeclare candidates and multiplicity handling. The original eight-new-token replication gate is unchanged and cannot be met here.

## Hourly compression: breadth and admission changes

2025 primary by token:

| Token | Trades | Stops | Stops/closed | Mean net, base | Mean net, stress |
|---|---|---|---|---|---|
| BTCUSDT | 17 | 7 | 41.2% | +0.4246% | +0.3247% |
| ETHUSDT | 8 | 3 | 37.5% | +0.5903% | +0.4909% |
| SOLUSDT | 11 | 4 | 36.4% | +0.5483% | +0.3472% |

Primary by entry year:

| Entry year | Trades | Stops | Mean net, base | Mean net, stress |
|---|---|---|---|---|
| 2022 | 27 | 10 | +0.6052% | +0.4866% |
| 2023 | 24 | 14 | -0.3492% | -0.4624% |
| 2024 | 46 | 20 | +0.3052% | +0.1744% |
| 2025 | 36 | 14 | +0.4992% | +0.3685% |

The positive historical aggregate is not uniformly positive: 2023 primary mean is -0.3492% base / -0.4624% stress. Historical ETH is negative, and removing BTC makes the remaining historical primary basket negative at stress. In 2025, all three token means are positive at stress, but individual token samples are only 8–17 trades. This instability and the intervals above keep hourly compression a lead rather than a confirmed edge.
2025 primary base-cost hourly events versus the previously admitted hourly subset:

| Admission group | Trades | Stops | Mean net |
|---|---|---|---|
| retained | 26 | 11 | +0.3487% |
| newly_admitted | 10 | 3 | +0.8906% |
| no_longer_admitted | 1 | 0 | +2.2761% |

The new hourly replay can admit events previously blocked by lower clocks and can subsequently block a different hourly event. Do not derive it by subtracting losing lower-clock rows. Detailed changes and both arms/cost levels are saved in hourly_admission_changes.csv.

## Costs and filter mechanisms

2025 primary average components at base costs. Positive funding is a cost; negative funding is a credit. Net equals quoted move minus slippage drag, fees and funding.

| Variant | Quoted move | Slippage drag | Fees | Funding | Net |
|---|---|---|---|---|---|
| Compression, all clocks | +0.1892% | +0.1280% | +0.1100% | +0.0071% | -0.0559% |
| Compression, 1h only | +0.7500% | +0.1308% | +0.1100% | +0.0099% | +0.4992% |
| Breakout without extreme-funding condition | +0.0365% | +0.1453% | +0.1100% | +0.0022% | -0.2210% |
| Original extreme-funding breakout | -0.1419% | +0.1535% | +0.1102% | -0.0104% | -0.3952% |
| Original trend pullback | +0.0956% | +0.1389% | +0.1099% | +0.0006% | -0.1538% |
| Trend pullback + aligned 4h regime | +0.1477% | +0.1403% | +0.1100% | +0.0011% | -0.1036% |

trend_raw_context_cohorts.csv preserves aligned and excluded raw pullback opportunities, including target hits that the regime filter excludes. Those raw opportunities overlap and are not an executed portfolio. The actual basket comparisons already include changed occupancy and missed opportunities. Entry-time RSI, volume, returns, funding and regime are retained in the detailed trade CSV; no new RSI, ADX or Connors RSI filter was tested.

## Wider arm: 3% stop / 3% target, 2025

| Variant | Trades | Closed | Marks | Stops | Stops/closed | Closed win rate | Net/trade, base | Net/trade, stress |
|---|---|---|---|---|---|---|---|---|
| Compression, all clocks | 196 | 195 | 1 | 102 | 52.3% | 47.7% | -0.3885% | -0.5196% |
| Compression, 1h only | 35 | 35 | 0 | 14 | 40.0% | 60.0% | +0.3439% | +0.2126% |
| Breakout without extreme-funding condition | 1032 | 1029 | 3 | 521 | 50.6% | 49.4% | -0.2982% | -0.4444% |
| Original extreme-funding breakout | 188 | 186 | 2 | 95 | 51.1% | 48.9% | -0.3115% | -0.4664% |
| Original trend pullback | 291 | 289 | 2 | 149 | 51.6% | 48.4% | -0.3469% | -0.4858% |
| Trend pullback + aligned 4h regime | 183 | 182 | 1 | 90 | 49.5% | 50.5% | -0.2154% | -0.3557% |

This changes both stop and target. Compare it as a combined sensitivity, not a stop-width-only causal result. Full historical sensitivity, costs, individual token/clock/direction cells and annual breakdowns are in pooled_results.csv, subgroups.csv and annual_by_entry_year.csv.

## Validation and records

Four focused tests passed: funding-predicate/de-duplication logic, entry-regime filtering, prefix causality and common-block contrast identity. All six original data hashes and nine feature hashes verified. 108 original compression/funding/trend signal groups reconcile exactly; 57,728 unique raw opportunities pass direct first-barrier checks. 48 independent admission replays agree with the stored baskets. The old 3,736-row compression ledger is reproduced exactly.

48 pooled, 1116 subgroup, 96 annual and 24 contrast rows reconcile with 36,488 accepted ledger rows across alternative scenarios. Execution remains before 2026; entry features are available at entry; cost identities and base/stress admission identity pass. Funding-gap checks do not independently certify historical funding cadence.

Source, original signals, all raw opportunities, accepted/rejected positions and ordinary CSV trade exports are saved privately with hashes and restoration instructions. Public GitHub contains this protocol/report and aggregate tables. No cash/margin/account drawdown or liquidation simulation, new-token test or live trade was run.

An integrity check found that the saved rejection log had 12,558,621 bytes and did not match its recorded hash. Independent reconstruction from the frozen raw opportunities recovered the original expected SHA256 exactly (13,097,459 bytes). The mismatched copy, recovery script, failed verification log and recovery record are preserved in the private checkpoint. Other frozen outputs matched; root cause is undetermined. The trade outcomes and selection rules were unchanged.

## Next action

Retain only hypotheses meeting the stated local criterion as candidates for further evidence, with the concentration and uncertainty above disclosed. Preserve all failures. Prepare any additional-token comparison as a separate protocol amendment before viewing new outcomes; retain the original all-clock primary result. Volume-shock and learned-rule work remain paused pending materially new data/hypotheses. No automatic filter sweep, exit optimization or leverage step follows from a positive historical point estimate.
