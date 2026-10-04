# Regime and target sensitivity — 2026-10-04

**180 configurations tested; no configuration passes the full exploratory screen.** Five are positive in 2025, all BTC; all 180 lose after costs in 2022–2024. No adjacent target pair qualifies across both periods. This is a test of one fixed EMA-reclaim entry family and one moving-average regime, not every possible trading system.

## What was tested

| Component | Frozen specification |
|---|---|
| Tokens | BTCUSDT, ETHUSDT, SOLUSDT |
| Entry clocks | 5 minutes, 15 minutes, 1 hour |
| Shared context | Completed 4h EMA50/EMA200 alignment, price relative to EMA200, EMA50 slope over three 4h bars |
| Entry | Completed close reclaims EMA20 in aligned bullish regime; inverse for short |
| Targets | 1%, 1.5%, 2%, 2.5%, 3% underlying move from quoted entry |
| Initial stop | 1% adverse move, fixed throughout study |
| Exit policies | Target/stop only; or target/stop plus regime invalidation (neutral or opposite) |
| Time limit | None. Positions persist until an exit condition; open positions are marked at dataset boundaries |
| Costs | 5.5bp fee per fill side; BTC/ETH 5bp, SOL 10bp slippage per side; historical funding. Stress doubles slippage |
| Windows | Discovery 2022–2024, previously used validation 2025; no 2026 strategy results |

Budget: 3 tokens × 3 entry clocks × 2 directions × 5 targets × 2 exit policies = 180 configurations. Two periods × two costs × paired/chronological views produce 1,440 rows, not 1,440 independent strategies. Every registered row was completed.

A 5-minute clock means entries are evaluated on completed five-minute candles; it does not mean positions close after five minutes. Regime decisions use completed four-hour bars on all entry clocks. The regime reviewer is deterministic, not a tested AI agent. EMA parameters were fixed, not optimized.

## Results by token and entry timeframe

| Token | Entry clock | Configurations | Positive in 2025 | Pass both periods and cost stress |
|---|---|---:|---:|---:|
| BTCUSDT | 5m | 20 | 0 | 0 |
| BTCUSDT | 15m | 20 | 1 | 0 |
| BTCUSDT | 60m | 20 | 4 | 0 |
| ETHUSDT | 5m | 20 | 0 | 0 |
| ETHUSDT | 15m | 20 | 0 | 0 |
| ETHUSDT | 60m | 20 | 0 | 0 |
| SOLUSDT | 5m | 20 | 0 | 0 |
| SOLUSDT | 15m | 20 | 0 | 0 |
| SOLUSDT | 60m | 20 | 0 | 0 |

Each row contains 20 configurations: two directions × five targets × two exits. Positive in 2025 means mean net return above zero at base costs, not a profitability approval. Both-period screening also requires >=50 completed trades per period, PF>=1.15 and positive expectancy under doubled slippage.

## The requested 2%, 2.5%, 3% comparison

BTC long, 1h EMA-reclaim entries with regime exits is the strongest 2025 slice in the grid. It is shown **descriptively after inspecting the full grid**, not as a preselected winner. Target sensitivity within that slice:

| Target | 2022–24 mean net/trade | 2025 completed trades | 2025 mean net/trade | 2025 PF | 2025 doubled-slippage mean |
|---|---:|---:|---:|---:|---:|
| 1% | -0.1679% | 104 | -0.2226% | 0.632 | -0.3224% |
| 1.5% | -0.1224% | 85 | -0.2031% | 0.715 | -0.3029% |
| 2% | -0.0484% | 78 | -0.1271% | 0.833 | -0.2270% |
| 2.5% | -0.0685% | 69 | +0.0300% | 1.040 | -0.0700% |
| 3% | -0.0857% | 62 | +0.1214% | 1.158 | +0.0213% |

The 3% target has 62 validation trades, positive mean of +0.1214%, PF1.158, and +0.0213% under doubled slippage. But it loses −0.0857% per trade in 2022–2024 (274 completed trades; PF0.901). It fails the screen. The neighboring 2.5% target is slightly positive in 2025 but becomes negative under doubled slippage. There is no stable qualifying target region.

These are chronological results. Larger targets keep positions open longer and block some subsequent signals, so trade counts differ. Full paired same-entry comparisons for all tokens/timeframes/sides/exits appear in results/paired_target_sensitivity.csv; those paired trades can overlap and must not be interpreted as a capital-constrained portfolio.

## Settings selected using discovery only

For every token/timeframe, the registered display rule selects the highest discovery mean among settings with >=50 completed discovery trades. All those means are negative; selected means least-negative, not approved. Validation was not used for this ranking.

| Token | Clock | Side | Target | Exit | Discovery mean | 2025 n | 2025 mean | 2025 PF |
|---|---|---|---:|---|---:|---:|---:|---:|
| BTCUSDT | 5m | Long | 2.5% | orders | -0.1562% | 141 | -0.1557% | 0.816 |
| BTCUSDT | 15m | Long | 2.5% | orders | -0.1708% | 104 | -0.0137% | 0.983 |
| BTCUSDT | 60m | Long | 2% | regime | -0.0484% | 78 | -0.1271% | 0.833 |
| ETHUSDT | 5m | Short | 3% | regime | -0.1855% | 541 | -0.2980% | 0.670 |
| ETHUSDT | 15m | Short | 3% | orders | -0.1612% | 329 | -0.1747% | 0.805 |
| ETHUSDT | 60m | Long | 3% | regime | -0.1470% | 89 | -0.0726% | 0.915 |
| SOLUSDT | 5m | Long | 2% | regime | -0.2816% | 497 | -0.3224% | 0.624 |
| SOLUSDT | 15m | Short | 1.5% | orders | -0.2524% | 511 | -0.2687% | 0.649 |
| SOLUSDT | 60m | Short | 3% | regime | -0.2874% | 171 | -0.3759% | 0.627 |

## Holding duration, exits and drawdown

There was no time exit. The longest chronological trade across the grid lasted 342.05 hours (about 14.3 days). The BTC 1h long/3%/regime validation slice had median holding time 17.37 hours. Consequently, a several-day path can contribute to a target hit; these results are not claims of earning 2–3% repeatedly every day.

There are 46 boundary marks across the 360 base-cost configuration-period rows. They are included with estimated liquidation costs and accrued funding; each is separately flagged. This count includes overlapping candidate positions and is not 46 unique real account positions. Boundary values are observations at a data cutoff, not a hidden maximum holding rule.

Regime exits improved base-cost mean versus target/stop alone in 51/90 discovery comparisons, but only 32/90 validation comparisons. Across those 90 validation comparisons the equally weighted change was approximately −0.0021 percentage points per trade. That average is a diagnostic across overlapping configurations, not portfolio PnL. Regime exits did not consistently add value.

Full results report target/stop/regime counts, win rate, average win/loss, funding, fees, exposure, duration percentiles, losing streaks and mark-to-market drawdown. Drawdown uses minute-close valuations and includes estimated liquidation costs; it can miss worse intraminute lows. Additive unit-notional drawdown is NOT account percentage drawdown, and the study does not simulate compounded equity or leverage.

## Interpretation and next steps

1. Target choice matters. The BTC 1h example improves materially between 2% and 3% in 2025. That improvement does not generalize across the earlier period, token or entry clock.
2. Five-minute entries did not solve the problem: none of their 60 configurations has positive 2025 net mean. Fifteen-minute entries yield one positive configuration; hourly entries yield four, all BTC.
3. A moving-average regime filter is useful context to test, but these particular EMA rules do not establish a repeatable profitable entry. This is not evidence that an unspecified AI reviewer can repair them.
4. Do not deploy or promote any row from this grid. The 2025-positive slice can be recorded as a hypothesis for fresh prospective evidence, not treated as a validated strategy. Further historical tuning against the same years increases selection bias.
5. If a new bounded study is commissioned, the untested risk-design question is whether a fixed 1% stop is appropriate across different token volatility. Compare a predeclared volatility-scaled stop with fixed risk per trade, using training-only calibration and a reserved evaluation plan. That is a hypothesis, not a claim it will restore profitability. Alternatively, collect prospective spread/order-flow/fill information to test a genuinely different entry advantage. No further experiment or live change is included here.

## Verification and reproducibility

- Protocol committed before execution: 37e5dc00f98011c4766e2b6c5cbf7186d4a9cbdc. Nine synthetic test methods pass, including 800 optimized-execution comparisons to an independent scalar oracle and 600 range-search comparisons.
- Checked no holding cap with a trade extending over 3,000 minutes; open-regime exits precede later intraminute stops; stop gaps, same-bar stop/target ambiguity, funding timing, fee identity, chronological skipping, unrealized drawdown and future-feature independence are tested.
- Input cache hashes match the prior verified archive. Source/input/runtime hashes in results/manifest.json. No raw candles are committed. No 2026 strategy results computed.
- No passing candidates means no candidate confidence-interval promotion claim. Five positive 2025 rows among 180 tests are vulnerable to multiple-testing bias. These periods were previously used; validation is reused historical evidence.
- Execution assumes decisions at the first minute open following completed bars, adverse slippage, stop-first same-bar ordering and no order-book/queue/latency detail beyond slippage. Funding uses traded minute-open proxies and explicit settlement conventions.
- This entry family is separate from the snapshot of Grokbot’s 4h impulse/pullback production wire. No worker, VM, strategy approval, live setting or earlier study was altered.

Reproduce from repository root with Python, numpy, pandas and pyarrow:

```bash
python3 -m unittest discover -s research/isolated_token_study_20261003/regime_target_20261004 -p "test_*.py"
python3 research/isolated_token_study_20261003/regime_target_20261004/run_study.py --cache /path/to/verified/cache --out /path/to/new_output_directory
```

All 1,440 summary rows and entry-year summaries are saved as compressed CSVs. configuration_summary.csv contains the 180 chronological comparisons in a readable wide format. Complete trade exports for the nine discovery-selected settings are included; the runner emits all 720 chronological trade files. Export gzip hashes are recorded for this run, but gzip metadata timestamps can differ on reruns; compare decompressed numerical contents for reproducibility.
