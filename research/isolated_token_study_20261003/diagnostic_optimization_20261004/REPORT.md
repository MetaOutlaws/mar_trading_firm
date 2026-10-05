# Diagnostic optimization — 4 October 2026

**Decision: no candidate qualifies.** This study diagnoses the prior losses and tests bounded parameter changes. It completes 432 training-setting evaluations (864 cost rows), freezes six selections, and evaluates 36 later-period comparisons. One selected outcome is positive under base costs; its equal-risk return turns negative under additional slippage stress, it fails the screen, and the gain does not persist into 2025. The remaining five are negative.

This is offline research only. No production code, workers, VM state, approval book or live-trading setting was changed.

## Main results

Means below are net returns per unit of trade notional, after modeled fees, slippage and funding; they are not account returns. Reference and entry-only variants use the selected timeframe and direction. Trade counts are completed trades for the optimized variant; means also include open-at-boundary marks. ETH 2024 includes 183 completed trades plus one boundary mark. Full counts for every variant are in the ledger.

| Token | Evaluation year | Optimized trades | Reference mean net | Entry-only mean net | Optimized mean net | Optimized PF in R | Screen |
|---|---|---|---|---|---|---|---|
| BTC | 2024 | 125 | -0.110% | -0.078% | +0.148% | 1.073 | FAIL |
| BTC | 2025 | 77 | +0.016% | -0.302% | -0.453% | 0.622 | FAIL |
| ETH | 2024 | 183 | -0.213% | -0.213% | -0.341% | 0.758 | FAIL |
| ETH | 2025 | 221 | -0.267% | -0.284% | -0.457% | 0.713 | FAIL |
| SOL | 2024 | 155 | -0.355% | -0.224% | -0.197% | 0.850 | FAIL |
| SOL | 2025 | 170 | -0.298% | -0.222% | -0.195% | 0.845 | FAIL |

Reference = EMA20, 4h EMA50/200 regime, 1% stop, 2.5% target, regime exit. Entry-only changes EMA/regime parameters. Optimized also changes stop, target and exit policy. This decomposition shows whether an improvement came from entries or risk management. The reference timeframe and direction were selected in training, so it is not a universal independent benchmark.

At equal initial price risk, wider stops imply smaller notional positions. R is net return divided by the initial stop fraction; it is not account equity. Costs and gaps can produce losses exceeding 1R.

| Token | Year | Reference mean R | Entry-only mean R | Optimized mean R | Optimized stressed mean R | Optimized MTM drawdown R |
|---|---|---|---|---|---|---|
| BTC | 2024 | -0.110 | -0.078 | +0.035 | -0.019 | 13.49 |
| BTC | 2025 | +0.016 | -0.302 | -0.253 | -0.323 | 22.00 |
| ETH | 2024 | -0.213 | -0.213 | -0.126 | -0.170 | 25.58 |
| ETH | 2025 | -0.267 | -0.284 | -0.175 | -0.212 | 39.89 |
| SOL | 2024 | -0.355 | -0.224 | -0.068 | -0.139 | 13.98 |
| SOL | 2025 | -0.298 | -0.222 | -0.077 | -0.151 | 18.49 |

BTC improves in 2024 but deteriorates in 2025. ETH's smaller losses in R coexist with worse fixed-notional returns: that does not establish better entries. SOL improves on both measures but remains unprofitable. Every selected configuration has a negative worst training-year stressed mean R. These are exploratory least-negative selections, not profitable training winners.

## What explains the losses?

The stop-recovery audit uses all 180 original EMA-regime configurations at base cost. Records overlap across settings and are not independent market events. For stopped trades, observation begins the minute after the stop bar and requires a complete seven-day window inside the same partition.

| Token | Eligible 2025 stop observations | Original target reached within 7 days | Target reached before 2% adverse movement from original entry | Median 1% stop / hourly ATR |
|---|---:|---:|---:|---:|
| BTC | 6,002 | 58.4% | 20.6% | 1.36 |
| ETH | 12,185 | 78.3% | 23.2% | 0.81 |
| SOL | 14,775 | 78.1% | 24.4% | 0.75 |

Many stopped trades eventually recover, but usually not without exposure to larger adverse moves. These hypothetical recoveries are not realized profits and cannot simply be added to the original backtest. Same-bar target/adverse ambiguity is resolved adversely. Censored observations remain identified in the evidence.

**Seven days is a diagnostic observation window, not a maximum trade holding period. No trading time limit was introduced.**

The 2025 mean quoted-path returns before costs were approximately +0.047% BTC, +0.003% ETH and +0.022% SOL. Modeled round-trip fees plus slippage are approximately 0.21% BTC/ETH and 0.31% SOL, before funding. The observed gross advantage is too small to cover execution costs. This decomposition uses the executed paths, not a separate zero-cost simulation. Full funding and cost components are in loss_diagnostics.csv.

Prior four-hour movement does not reveal a universal late-entry fix. Every timing bin remains negative after costs. Stronger preceding moves are relatively less harmful for ETH; BTC behaves differently. These are descriptive findings and were not turned into new filters after viewing evaluation results.

## Registered experiment design

Protocol commit: `e0abc50d16dbbcb3443af40cb2db113a2239e708`. Implementation clarification commit: `49c46d76255f10622da8a6953fa84198581ed9bb`. Both preceded the run.

| Dimension | Tested values |
|---|---|
| Tokens | BTCUSDT, ETHUSDT, SOLUSDT |
| Entry timeframe | 5, 15, 60 minutes |
| Direction | Long, short |
| Entry EMA | 10, 20, 40 |
| Completed 4h regime EMAs | 20/100, 50/200 |
| Initial stop | Fixed 1%; 1.5 or 2.5 completed-hour ATR14, clipped to 0.5–3% |
| Profit target | 2%, 2.5%, 3% |
| Exit policy | Stop/target only; stop/target plus regime reversal |
| Costs | Base and doubled slippage; fees/funding retained |

Fold A trains on 2022–23 and evaluates 2024. Fold B trains on 2022–24 and evaluates 2025. Stage A tests 36 entry settings per token/fold, with fixed risk and exit settings. The top two eligible entries proceed to 36 Stage B risk/target/exit evaluations. This totals 432 setting evaluations, not 432 unique independent hypotheses: 261 unique token/configuration pairs recur across folds/stages.

Ranking uses the worst annual training mean R under doubled slippage, then pooled stressed mean R and stable configuration ID. Eligibility requires at least 50 completed training trades and 15 per training entry-year. No positivity requirement is imposed for exploratory selection; negative selections are explicitly labeled. Frozen selections are recorded before their later-period evaluation.

The 2025 selections were:

| Token | Entry | Regime | Stop | Target | Exit |
|---|---|---|---|---|---|
| BTC | 15m long, EMA40 | 4h EMA20/100 | 2.5 hourly ATR | 2.5% | Orders + regime reversal |
| ETH | 5m short, EMA20 | 4h EMA20/100 | 2.5 hourly ATR | 3% | Orders only |
| SOL | 15m short, EMA40 | 4h EMA20/100 | 2.5 hourly ATR | 2.5% | Orders + regime reversal |

Structure and supply/demand zone filters were not retuned: PR #97 documented their severe sample attrition. This experiment measures EMA/regime and risk-design changes; it does not claim to exhaust possible market-structure models. Trailing exits were not newly optimized here. Prior trailing investigations remain in the study register.

## Screen and uncertainty

A fold requires at least 50 completed evaluation trades, positive mean R and fixed-notional mean, PF in R >=1.15, positive stressed evaluation mean R, nonnegative worst training-year stressed mean R, and at least one adjacent target passing the registered training checks. No fold passes; no adjacent target qualifies. A token would need both folds to pass.

Weekly-entry-block bootstrap uses 5,000 resamples. The results include ordinary 95% and six-comparison Bonferroni intervals for the six primary optimized base-cost outcomes. BTC 2024's ordinary mean-R interval is approximately [-0.158, +0.220]; its point estimate alone is weak evidence. These intervals do not correct the entire research search history or long-duration dependence.

Both evaluation years have been examined in earlier research, so they are chronological evaluations, not pristine confirmation data. 2026 outcomes were not scored. Flat partition starts and cost-inclusive boundary marks are explicit modeling choices. Training trades crossing calendar years are attributed to entry year. Intrabar uncertainty, modeled fills and absence of queue/order-book replay limit execution realism. No portfolio sizing, leverage or liquidation simulation is implied.

## Verification and reproducibility

Seven new automated tests pass, including 960 scalar execution comparisons, gap/stop ordering, stop-recovery censoring and adverse-first ties, R scaling, ranking independence from evaluation fields, future-feature perturbation across the three clocks, and count eligibility. The imported baseline runner is hash-pinned in the manifest. These checks address concrete execution and leakage risks; they do not prove future profitability.

From the repository root, with Python 3.12, numpy 2.3.5, pandas 2.2.3 and pyarrow 25.0.1:

```bash
python -m unittest discover -s research/isolated_token_study_20261003/diagnostic_optimization_20261004 -p 'test_*.py'
python research/isolated_token_study_20261003/diagnostic_optimization_20261004/optimize.py --cache /path/to/market_cache_v2 --baseline /path/to/regime_target_results_20261004 --out /path/to/new_results
```

The baseline directory must contain the original trade exports used for diagnosis. Raw candles/funding are not committed; manifest.json records their SHA-256 hashes. Preserve the original dataset and baseline exports when handing this package to another worker.

## Evidence index

- `PROTOCOL.md`, `IMPLEMENTATION.md`: preregistered rules and clarifications.
- `optimize.py`, `test_optimization.py`: implementation and verification.
- `results/training_ledger.csv`: all 864 training/cost rows, including failures.
- `results/frozen_selections.json`: six frozen selections and training scores.
- `results/evaluation_results.csv`: all 36 comparison rows, costs, duration, risk and uncertainty.
- `results/training_neighbors.csv`, `results/screen.csv`: robustness evidence and explicit decisions.
- `results/loss_diagnostics.csv`, `results/entry_timing_diagnostics.csv`: diagnostic summaries.
- `results/trade_evidence.zip`: three full diagnostic parquet files and 36 evaluation trade gzip CSVs; these are derived records, not raw candles.
- `results/manifest.json`, `ARTIFACTS_SHA256.json`: input/code provenance and packaged artifact checksums.
- `../STUDY_REGISTER.md`: cumulative experiments and conclusions, so later workers can avoid repeating failed searches.

## Next research decision

Do not promote any of these settings. This bounded search does not support another unrestricted EMA/stop sweep. The next useful hypothesis should explain where conditional gross returns can exceed actual execution costs, then test that hypothesis chronologically with all attempts recorded. Candidate information beyond the tested family could include independently measured liquidity/order-flow or cross-market context, but its availability and cost must be established first. Lower-cost execution must be modeled with fill probability and adverse selection, not assumed maker fills.

Use the existing diagnostics to specify that next hypothesis before opening any unexamined outcomes. Keep 2026 unscored until the specification is frozen, and use prospective paper results for genuinely new evidence. Profitability remains unestablished; the contribution here is a reproducible account of what improved, what failed and why.


## Publication scope

This GitHub publication contains written findings and aggregate comparison tables only. Source scripts, detailed configuration ledgers and trade evidence referenced above remain in the local research package pending specific export approval. No production changes or new tests were executed for this publication.
