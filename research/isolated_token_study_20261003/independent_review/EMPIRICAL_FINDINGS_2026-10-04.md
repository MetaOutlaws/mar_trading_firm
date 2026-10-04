# Independent empirical findings — 2026-10-04

**Decision: no candidate qualifies for promotion.** The data transfer is complete. This report supersedes the data-unavailable status in the earlier INDEPENDENT_REVIEW.md. We independently reproduced the original 48 configurations and tested 20 additional predefined configurations. None passes the discovery/validation profitability gates. This is evidence against these implementations, not proof that every possible trading strategy is unprofitable.

## Data and reproducibility

- Input archive SHA256: `344ac29b5b2ee2fe9ba5966026914489dc22dfaed75374fbe86316052da863dc` (218,177,784 bytes); matches the supplied fingerprint.
- BTCUSDT, ETHUSDT and SOLUSDT each contain 2,499,840 one-minute candles from 2022-01-01 through 2026-10-02 UTC. Candle audit: no missing required bars. Six individual input hashes appear in the result manifests.
- Funding audit includes one preceding settlement: 5,209 BTC/ETH and 5,569 SOL records; in-window counts are 5,208 and 5,568. The independently checked SOL two-hour schedule segment (2022-11-10 08:00 through 2022-12-20 08:00 UTC) has no missing scheduled timestamps. The earlier synthetic audit test exposes a validator weakness, not an actual missing event in this supplied cache.
- Original study SHA256: `a5e4bf7f29c047b287af773275c12df59855d5dca8221f6c4da7e6dec2bca6f9`. Source and input hashes are recorded in manifests.
- Discovery: 2022–2024. Validation: 2025, already reused by earlier research. No 2026 strategy-return evaluation was performed because selection was empty. Earlier opportunity summaries partially exposed 2026, so it is not a completely pristine holdout.
- Offline research only. No VM, running worker, production approval book, live mode or execution configuration was changed.

## Original 48 configurations: independent reproduction

All 96 discovery/validation result rows match the published trade counts and reported net-mean/profit-factor rounding. All 96 have negative net means and profit factors below 1. The reproduction uses the original engine; independent scalar-oracle tests separately check its price and funding arithmetic. It is not a second fully independent backtesting implementation.

The following are equally weighted means across configuration cells, expressed as percent of entry notional per trade. They are diagnostics, not a tradable combined portfolio; candidates overlap. Quoted-path return reconstructs prices on the original exit paths, rather than rerunning hypothetical zero-cost barriers.

| Token | Period | Quoted-path return | Slippage drag | Fees | Funding cost | Net return |
|---|---|---:|---:|---:|---:|---:|
| BTCUSDT | discovery | 0.02232% | 0.10002% | 0.11001% | 0.00012% | -0.18783% |
| BTCUSDT | validation | -0.00280% | 0.09996% | 0.10998% | 0.00040% | -0.21314% |
| ETHUSDT | discovery | -0.00081% | 0.10001% | 0.11000% | 0.00002% | -0.21084% |
| ETHUSDT | validation | 0.01635% | 0.09994% | 0.10997% | 0.00068% | -0.19424% |
| SOLUSDT | discovery | -0.03637% | 0.19992% | 0.10998% | 0.00044% | -0.34671% |
| SOLUSDT | validation | -0.02993% | 0.19999% | 0.11000% | 0.00040% | -0.34032% |

Only 41 of 96 cells have a positive average quoted-path return, and all become negative after modeled execution costs. Under these assumptions, direction/timing provides too little advantage to cover roughly 0.21% round-trip fees plus slippage for BTC/ETH and 0.31% for SOL. Funding is a much smaller average contributor here. These are model assumptions, not measured account-specific fills.

## Twenty alternative configurations

Twelve continuation variants use completed hourly breakouts, an EMA trend condition, volatility-scaled stops/targets and optional elevated-volatility filtering. Eight relative-value variants trade ETH or SOL residual extremes against a frozen BTC hedge, with fixed-time or normalization exits. Exact rules were fixed in EXECUTION_ADDENDUM.md before alternative returns were inspected.

The table reports percent return on entry notional (gross combined notional for the hedged package). D = discovery, V = validation. Stress doubles slippage on both entry and exit, including both hedge legs, and reruns execution. PF is gross winning net-return sum divided by absolute losing net-return sum. Side is the traded token; residual configurations hold the opposite BTC hedge. Variant meanings: continuation 0=no volatility filter, 1=filter; residual 0=fixed four hours, 1=normalization or four hours.

| Family | Token | Side | Variant | D trades | D mean | D PF | V trades | V mean | V PF | Stress D mean | Stress V mean |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| continuation | BTCUSDT | long | 0 | 487 | -0.0817% | 0.889 | 184 | -0.3256% | 0.529 | -0.1791% | -0.4264% |
| continuation | BTCUSDT | long | 1 | 217 | -0.1014% | 0.888 | 73 | -0.4907% | 0.458 | -0.2289% | -0.5874% |
| continuation | BTCUSDT | short | 0 | 410 | -0.2462% | 0.727 | 170 | -0.1744% | 0.761 | -0.3635% | -0.2623% |
| continuation | BTCUSDT | short | 1 | 221 | -0.2669% | 0.757 | 88 | -0.3007% | 0.678 | -0.4270% | -0.3648% |
| continuation | ETHUSDT | long | 0 | 467 | -0.0912% | 0.898 | 166 | -0.0323% | 0.966 | -0.1917% | -0.1092% |
| continuation | ETHUSDT | long | 1 | 214 | -0.0608% | 0.942 | 64 | 0.0372% | 1.032 | -0.1762% | -0.0205% |
| continuation | ETHUSDT | short | 0 | 442 | -0.0751% | 0.929 | 163 | -0.1246% | 0.898 | -0.2143% | -0.2045% |
| continuation | ETHUSDT | short | 1 | 250 | -0.1075% | 0.917 | 109 | -0.2333% | 0.841 | -0.2719% | -0.3308% |
| continuation | SOLUSDT | long | 0 | 484 | -0.2034% | 0.862 | 179 | -0.5456% | 0.595 | -0.4140% | -0.7112% |
| continuation | SOLUSDT | long | 1 | 233 | -0.3812% | 0.794 | 70 | -0.7164% | 0.586 | -0.5309% | -0.8664% |
| continuation | SOLUSDT | short | 0 | 449 | -0.5310% | 0.698 | 176 | -0.2665% | 0.806 | -0.7383% | -0.4867% |
| continuation | SOLUSDT | short | 1 | 220 | -1.0147% | 0.574 | 95 | -0.5794% | 0.669 | -1.2687% | -0.7409% |
| residual | ETHUSDT | long | 0 | 278 | -0.1730% | 0.452 | 94 | -0.3450% | 0.228 | -0.2701% | -0.4414% |
| residual | ETHUSDT | long | 1 | 292 | -0.2193% | 0.191 | 98 | -0.2685% | 0.181 | -0.3174% | -0.3811% |
| residual | ETHUSDT | short | 0 | 316 | -0.2357% | 0.306 | 112 | -0.2441% | 0.252 | -0.3351% | -0.3382% |
| residual | ETHUSDT | short | 1 | 332 | -0.2224% | 0.168 | 119 | -0.1823% | 0.214 | -0.3294% | -0.2785% |
| residual | SOLUSDT | long | 0 | 281 | -0.1593% | 0.657 | 80 | -0.1595% | 0.540 | -0.3170% | -0.3171% |
| residual | SOLUSDT | long | 1 | 299 | -0.1990% | 0.437 | 85 | -0.1040% | 0.580 | -0.3441% | -0.2606% |
| residual | SOLUSDT | short | 0 | 366 | -0.3442% | 0.346 | 110 | -0.3158% | 0.347 | -0.4734% | -0.4369% |
| residual | SOLUSDT | short | 1 | 386 | -0.3025% | 0.236 | 118 | -0.2188% | 0.336 | -0.4369% | -0.3387% |

The sole positive base-cost validation cell is ETH long continuation with the volatility filter: 0.0372% per trade, PF 1.032, across 64 trades. Its discovery mean is -0.0608%, and its doubled-slippage validation mean is -0.0205%. It fails both the discovery profitability requirement and PF>=1.15, and fails cost stress. It is not a survivor or a recommendation.

All 20 alternatives lose in discovery at base costs; all 40 stressed discovery/validation cells lose. Relative-value hedging did not produce positive net results in any tested cell. Selection is null for BTC, ETH and SOL. With no survivors, there are no confirmatory 2026 tests, confidence-interval claims or random-control promotion claims.

## What this means for further research

The useful question is whether entry information predicts a subsequent move large enough to exceed actual execution costs. The existence of large future high/low swings alone does not answer that: it includes moves before a feasible entry, adverse paths and extrema only known afterward. This batch does not support a continuous 3–5% capture claim. Leverage is not a missing signal variable in these unit-notional tests; no leveraged equity curve or liquidation claim is made.

A bounded next experiment should change the information or execution evidence rather than continue optimizing these losing thresholds. Proposed sequence for the Grokbot team:

1. Keep these four tested families archived with their full negative results. Do not retune the single slightly positive ETH cell against 2025 and call it a fresh validation.
2. Collect prospective bid/ask spreads, available depth, trade prints, account fee tier, and timestamped simulated orders/fills for BTC, ETH and SOL separately. Candle data cannot establish maker queue position, fill probability or adverse selection. Do not replace taker costs with assumed maker fills.
3. Before observing outcomes, register a small token-specific test of whether an order-flow/liquidity event predicts a move over a fixed horizon. Compare against entries matched by token, side, hour and volatility. First test predictive value; only then optimize execution in a separately reserved period. This is a new hypothesis, not evidence of profitability.
4. Use strictly chronological evaluation and report every tested variant. A candidate must survive costs, stress, sufficient independent observations and prospective paper confirmation before consideration by the existing approval process. Coordinate ownership with Grokbot before changing its active experiment; this package needs no production deployment.

## Verification and limitations

- Eleven unittest methods pass, including 800 randomized scalar-oracle paths, timestamp-unit equivalence, both-leg fees/funding and feature future-perturbation checks. Tests check implementation properties; they do not prove alpha.
- Fee model is 5.5bp per side; slippage is 5bp per side for BTC/ETH and 10bp for SOL. Funding uses historical rates with traded minute-open prices as a mark-price proxy. Entry exactly at funding settlement excludes that event; actual exchange timing needs separate verification.
- Continuation uses the original conservative same-minute stop-first engine. Hedged residual stops are checked on synchronized minute opens and can miss intraminute losses; asynchronous leg fills, queue effects and liquidations are not modeled.
- Fixed unit-notional returns and sums are not account equity, CAGR or portfolio drawdown. No leverage or compounding is simulated.
- Repeated historical research reduces independence. These negative results reject these specific candidates under stated assumptions, and do not establish that the token or all future methods lack opportunity.

## Reproduce

From repository root, with Python, numpy, pandas and pyarrow installed (tested: numpy 2.3.5, pandas 2.2.3, pyarrow 25.0.1):

```bash
python3 -m unittest discover -s research/isolated_token_study_20261003/independent_review -p "test_*.py"
python3 research/isolated_token_study_20261003/independent_review/diagnose_baselines.py --cache /path/to/cache --out /path/to/new_baseline_output
python3 research/isolated_token_study_20261003/independent_review/alternative_study.py --cache /path/to/cache --out /path/to/new_alternative_output
```

Use new output directories. Cache layout: TOKEN_1m.parquet and funding/TOKEN_funding.parquet for BTCUSDT, ETHUSDT and SOLUSDT. The programs emit per-trade compressed CSVs as well as summary tables. Raw market data is intentionally not committed; use the archive fingerprint above. Committed results_20261004 contains all 96 baseline rows, quarterly diagnostics, all 80 alternative rows (20 configurations × two periods × two costs), manifests and empty selection.
