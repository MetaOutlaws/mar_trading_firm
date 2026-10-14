# Approved directional paper strategy — 14 October 2026

The owner approved L01 for longs while retaining F111 shorts, then explicitly
authorized Git push and paper activation. This is the current specification;
earlier hourly/F111 approvals remain historical context.

| Part | Frozen requirement |
| --- | --- |
| Long filter | Latest completed UTC 4h close > EMA50, and EMA50 > EMA50 three completed 4h bars earlier |
| EMA | `ewm(span=50, adjust=False, min_periods=50)`; 53 complete bars for slope; continue the verified historical seed |
| Candle construction | Right-labelled, left-closed UTC blocks of 240 distinct 1m candles; no forming bar or interpolation |
| Filter timing | Original hourly signal time, before creating a pending retest |
| Shorts | Original F111 admission, independent of 4h context |
| Inherited gates | Approved hourly compression/BTC/Connors/low-efficiency base; prior ATR/close >= 1%; compression > 0.5; signed extension <= 1 ATR |
| Entry | First touch/reclaim within 60 minutes, next actionable minute/forward quote; no old-open fill after a missed minute |
| Exits | Initial stop 3 ATR, target 4 ATR; protection trigger +1.25 original R, intended +0.25R floor effective next minute; actual fills may be worse |
| Occupancy | One position per token across both directions through the exit minute |
| Universe | Same 96 tokens / 192 directional sleeves; no aliases or new token exclusions |
| Risk and mode | Existing paper sizing/caps/costs; paper only; no live approval |

Missing, malformed, future or stale 4h context rejects a new long explicitly.
The runtime requires the latest completed 4h interval; that availability guard
produced zero additional rejections in the saved 1,026-signal comparison.
It does not convert unavailable instruments into tradable aliases.

## Verification and research scope

[VALIDATION.json](VALIDATION.json) records a read-only replay of all 1,026
original signals across 96 tokens (572 longs, 454 shorts), all 96 indicator
seeds, and both saved cost settings. It reproduces 185 all-universe admissions
per cost setting: 57 longs and 126 shorts in the additional-93 cohort plus two
reference-token trades. The short admission set equals the F111 control.
Exit paths used in this admission check are the saved research paths, not a
claim of full forward-engine replay parity.

In the main cohort at primary research costs, L01 longs produced 16.294058 R
across 57 trades versus F111 longs' 7.848584 R across 145 trades. The unchanged
126 shorts contributed 29.726368 R. Long yearly results were positive in
2022–2025 at both examined cost settings; 2025 had only 13 long trades. The
directional hypothesis followed full-history diagnostics and its uplift
confidence intervals cross zero. It remains a paper candidate, not proven
future profitability. No new 2026 backtest was opened for this implementation.

Full inherited engine path parity remains **UNVERIFIED**. Existing forward
quote fills, cost handling and exit polling differ from the historical
research engine; this change preserves those documented operational choices.
Unit/integration tests cover gate failures, short independence, causal minute
aggregation, incremental EMA, restart migration, activation marker integrity
and false-positive activation evidence.

Local validation: **136 passed, 1 skipped** using:

```sh
python -m pytest tests/test_l01_paper.py tests/test_f111_paper.py tests/test_execution.py tests/test_paper_cash_hydrate.py tests/test_paper_guards.py tests/test_cycle_scan_counts.py tests/test_scan_inbox.py -rA
```

The skipped pre-existing test is the explicit full-engine saved-path parity
placeholder. The new L01 research parity replay passed separately; it does
not turn that inherited limitation into a pass.

Reproduce the historical check using the owner's checkpoint:

```sh
python scripts/verify_l01_research_parity.py --checkpoint-root RESTORED_CHECKPOINT_DIRECTORY
```

The candle datasets remain outside this repository. Only the compact,
hash-verified indicator seed is included. Source checkpoint:
`MAR_structure_research_checkpoint_20261014.zip`, SHA256
`36f16f8487911982ab1d5830523c3292512ce7e82e0c1827a00e9e07de4f1d15`.

## Deployment status

This repository does not itself prove remote activation. The implementation
keeps F111 selected until an operator completes the preparation, marker and
same-worker restart steps in [the activation runbook](../runbooks/l01_paper_activation.md).
Use its runtime evidence check before changing any operational record to
"activated". Git publication and local tests alone are insufficient.
