# Research register

Updated 5 October 2026. Negative results are retained. No study below authorizes production trading. Counts describe each study's design and are not additive independent hypotheses.

| ID | Source | Scope | Result / boundary |
|---|---|---|---|
| R92 | [PR 92](https://github.com/MetaOutlaws/mar_trading_firm/pull/92) | 48 opening-range/sweep-reclaim configurations, BTC/ETH/SOL | All 96 discovery/validation rows negative; original 24h cap |
| R93 | [PR 93](https://github.com/MetaOutlaws/mar_trading_firm/pull/93) | Independent audit plus 20 alternative configurations | No qualified candidate |
| R94 | [PR 94](https://github.com/MetaOutlaws/mar_trading_firm/pull/94) | 18 entry screens, intended trailing stage | All validation means negative; Stage 3 never ran |
| R95 | [PR 95](https://github.com/MetaOutlaws/mar_trading_firm/pull/95) | 5,553 configuration-trades, 27,550 controls; 12 selected-entry/exit combinations | All 48 period/cost outcome rows negative; separate 4h audit horizon |
| R97 | [PR 97](https://github.com/MetaOutlaws/mar_trading_firm/pull/97) | 180 regime/target settings +540 structure/zone extensions; 5,760 result rows | No screen passes; context filters severely reduce sample; no holding cap |
| DOPT-20261004 | [Report](diagnostic_optimization_20261004/REPORT.md) | Loss diagnostics; 432 training evaluations, 36 chronological comparison rows | Six selected folds fail; no holding cap, no 2026 scoring |

| ICTX-20261005 | [Report](incremental_context_20261005/FINDINGS.md) | 18 daily-filter cells plus baseline/structure controls; 84,530 non-blocking zone annotations | No daily-filter screen passes; zone map rejects no candidates |
| ZENTRY-20261005 | [Report](zone_entry_timing_20261005/FINDINGS.md) | 18 zone-entry policies, 18 fixed-delay controls, 18 immediate controls; 432 rows | No full-screen passes; 14.68% of executed zone entries use rejection, remainder deadline fallback |
| ZEXIT-20261005 | [Report](zone_exit_20261005/FINDINGS.md) | 54 opposing-zone target caps across all three entry methods with unchanged-exit controls; 864 rows | All 54 zone-exit cells negative in both periods; 0 passes; 432 controls reconcile; no holding cap or 2026 scoring |

For DOPT-20261004, the stable row keys are symbol + fold + stage + config_id + stress for training (see ledger columns), and symbol + fold + variant + stress for evaluation. Stage repetitions and chronological overlap are intentional. Use configuration IDs and manifests rather than filenames alone to join studies. Do not sum overlapping trade observations across configurations as independent evidence.

Future additions should state hypothesis, protocol commit, input hashes, split boundaries, number of attempts, cost assumptions, execution model, frozen selection, all results, decision and unresolved limitations. Preserve null results and distinguish exploratory chronological evaluation from untouched confirmation. Research PRs must stay separate from production worker changes.
