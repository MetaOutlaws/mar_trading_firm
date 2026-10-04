# Market structure, zones and target sensitivity
## Independent research report | 2026-10-04

**Decision: no configuration is ready for promotion.** The complete comparison contains 720 configurations across BTC, ETH and SOL, including the original 180 baseline configurations. All 720 fail the prespecified full screen. Adding structure sometimes improves descriptive results; this particular zone definition removes almost all opportunities and does not establish a repeatable positive return.

## 1. Executive table

| Entry context | Configurations | 2025 opportunities retained | Median 2025 trades/config | Positive in both periods | Full-screen passes |
|---|---:|---:|---:|---:|---:|
| EMA regime baseline | 180 | 100.00% | 231.5 | 0 | 0 |
| + confirmed structure | 180 | 42.42% | 123 | 0 | 0 |
| + zone rejection and target room | 180 | 2.62% | 11 | 2 | 0 |
| + structure and zones | 180 | 1.37% | 6 | 6 | 0 |

Retention counts are opportunity-target combinations, before enforcing one open position, weighted across the three entry clocks and directions. They are not a unique-market-event count. Median trade counts refer to chronological configurations, not the total trades available across the organization.

**Why the positive exceptions do not pass:** all eight combinations positive in both periods have only two or three validation trades. Some share exactly the same trades under both exit policies, so eight is not eight independent discoveries. No zone-filtered positive validation configuration has 50 completed trades. All settings using both filters have fewer than 50 validation trades.

## 2. What was tested

| Dimension | Specification |
|---|---|
| Data | Verified BTCUSDT, ETHUSDT, SOLUSDT one-minute candles and historical funding |
| Entry clocks | 5m, 15m, 60m, using completed bars |
| Direction | Long and short configurations separately |
| Baseline regime | Completed 4h EMA50/EMA200 alignment, close vs EMA200, EMA50 slope over three 4h bars |
| Entry trigger | Completed close crosses EMA20 in the aligned regime |
| Structural filter | Last two confirmed 4h highs and lows both rising for longs; both falling for shorts |
| Zone filter | Confirmed 1h pivot bands, rejection candle, and no opposing active zone blocking the target |
| Targets | 1%, 1.5%, 2%, 2.5%, 3% underlying quote movement |
| Initial stop | Fixed 1% adverse quote movement |
| Exits | Target/stop alone; or target/stop plus EMA-regime invalidation |
| Holding limit | None; still-open positions marked at historical partition boundaries |
| Costs | Base fees/slippage/funding and doubled-slippage stress |
| Periods | 2022–2024 discovery; reused 2025 validation; no 2026 outcomes |

The original 180 configurations are retained. Three additional context variants add 540. Two periods × two cost models × paired/chronological views yield 5,760 summary rows. There is no expansion after inspecting outcomes.

Paired comparisons use the same original entry opportunity set, with filters admitting subsets; chronological results also reflect blocked entries while a position is open. Filters affect entry only, so an improvement cannot be attributed to an untested change in exit logic. Regime exits here are deterministic EMA-state exits, not an AI reviewer or immediate structural-break exit.

## 3. Results by token and timeframe

Each cell is the number of positive-mean 2025 chronological configurations with at least 50 completed validation trades, out of 20 configurations in that token/clock/context group. Positivity in this table alone is not a pass.

| Token | Entry clock | Baseline | Structure | Zones | Both |
|---|---|---:|---:|---:|---:|
| BTCUSDT | 5m | 0/20 | 0/20 | 0/20 | 0/20 |
| BTCUSDT | 15m | 1/20 | 5/20 | 0/20 | 0/20 |
| BTCUSDT | 60m | 4/20 | 0/20 | 0/20 | 0/20 |
| ETHUSDT | 5m | 0/20 | 0/20 | 0/20 | 0/20 |
| ETHUSDT | 15m | 0/20 | 0/20 | 0/20 | 0/20 |
| ETHUSDT | 60m | 0/20 | 0/20 | 0/20 | 0/20 |
| SOLUSDT | 5m | 0/20 | 0/20 | 0/20 | 0/20 |
| SOLUSDT | 15m | 0/20 | 0/20 | 0/20 | 0/20 |
| SOLUSDT | 60m | 0/20 | 0/20 | 0/20 | 0/20 |

Across all contexts, only 10 of the 720 configurations combine a positive 2025 mean with >=50 validation trades: five baseline BTC settings and five structure-filtered BTC settings. Every baseline and every structure-filtered configuration has a negative discovery mean.

## 4. Target sensitivity

Targets are price movement, not net account returns. Each target has 144 configurations across tokens, entry clocks, directions, exits and context filters.

| Target | Configurations | Positive 2025 mean, any sample | Positive 2025 mean and n>=50 | Full-screen passes |
|---|---:|---:|---:|---:|
| 1% | 144 | 4 | 0 | 0 |
| 1.5% | 144 | 19 | 0 | 0 |
| 2% | 144 | 16 | 1 | 0 |
| 2.5% | 144 | 16 | 5 | 0 |
| 3% | 144 | 17 | 4 | 0 |

The earlier baseline’s strongest 2025 slice remains BTC long on the 1h entry clock with EMA-regime exits. Its 2% target averages −0.1271% net per trade in 2025; 2.5% gives +0.0300%; 3% gives +0.1214% (62 trades, PF1.158). The 3% setting loses −0.0857% per trade in discovery, and its 2025 mean drops to +0.0213% with doubled slippage. This slice was noticed after inspecting the grid and is descriptive, not independently selected proof. Full five-target tables are in the baseline report and supporting result files.

No pair of adjacent targets passes the full screen for any fixed token/clock/direction/exit/context. A stable profitable parameter region has not been demonstrated.

## 5. Positive exceptions and evidence quality

| Configuration | Filter | Discovery n | Discovery net/trade | 2025 n | 2025 net/trade |
|---|---|---:|---:|---:|---:|
| ETHUSDT_15m_short_3pct_orders | both | 8 | +0.2936% | 2 | +0.7965% |
| ETHUSDT_15m_short_3pct_regime | both | 8 | +0.2936% | 2 | +0.7965% |
| SOLUSDT_60m_long_2.5pct_orders | both | 9 | +0.2411% | 3 | +1.0169% |
| SOLUSDT_60m_long_2.5pct_regime | both | 9 | +0.2411% | 3 | +1.0169% |
| SOLUSDT_60m_long_3pct_orders | both | 6 | +1.3477% | 2 | +0.6827% |
| SOLUSDT_60m_long_3pct_orders | zones | 14 | +0.6827% | 3 | +0.0194% |
| SOLUSDT_60m_long_3pct_regime | both | 6 | +1.3477% | 2 | +0.6827% |
| SOLUSDT_60m_long_3pct_regime | zones | 14 | +0.6827% | 3 | +0.0194% |

The trade-level records behind every row in this table are included in positive_both_trade_evidence.csv. Very small samples are not treated as winners. The screen requires >=50 completed trades in each period, positive net means and PF>=1.15 in both periods, and positive means at doubled slippage. Those are minimum exploratory requirements, not proof of deployable alpha. No confidence-interval promotion claim is made because no candidate passes that screen.

## 6. What the filters actually did

- Structure retained 42.42% of target-specific 2025 opportunities. It raised the number of positive-mean validation configurations from 5 to 8, but only 5 of those have >=50 validation trades. Its 2022–2024 means are all negative.
- Zones retained 2.62%. Twenty-four configurations show a positive validation mean, but none of those has >=50 validation trades. Six zone configurations have zero validation trades.
- Both retained 1.37%. Thirty-five show positive validation means, but median validation count is six; eight configurations have zero validation trades. This definition is too selective to support a robust positive-return claim from this sample.
- These filters did not massively improve the evidence. They changed the sample, and the strictest variants produced very sparse observations. Lower activity is not itself an edge.

## 7. Zone/structure specification and limits

Pivots require two bars on each side and strict extrema; a pivot is available only after its two confirming bars complete. A pivot at time k cannot be used at time k. Structure requires both the latest confirmed high and low to advance in the same direction. It can lag immediate price breaks between confirmations.

A zone is a band ±0.25×hourly ATR14 around a confirmed hourly pivot, with at most six active zones of each type. It expires 30 days after confirmation and is discarded after an hourly close through its invalidation edge. Entries require a candle that overlaps and rejects the appropriate zone; any opposite zone intersecting entry-to-target blocks the trade. No future zone is consulted.

This is one explicit support/resistance proxy. It does not represent measured resting orders, institutional inventory, base-and-displacement supply/demand formations, volume profile or every discretionary zone methodology. Rejecting this implementation does not reject all uses of market structure or zones.

## 8. Verification and audit trail

- All 360 baseline chronological base-cost configuration-period results were reconstructed: counts match, maximum mean difference 9.89e-17. Source hash matched the completed baseline runner.
- Six market file hashes verified. Context features and outcomes are cut before 2026. Protocol commits: baseline 37e5dc00f98011c4766e2b6c5cbf7186d4a9cbdc; context c3905f1ef2fd1f01c5b5926b3cde49d16f09cd13.
- Nine baseline tests pass (including 800 scalar execution comparisons and 600 barrier-search comparisons). Eight context tests pass: confirmation lag/ties, structure direction, zone creation/invalidation/expiry, long/short rejection and target room, future perturbations and no-trade behavior.
- Mark-to-market drawdown uses minute-close liquidation-value estimates, including fees and accrued funding; worse intraminute drawdown may be missed. Units are additive returns on fixed position entry notional, not account equity percentages. No leverage or liquidation model.
- Stop gaps, same-minute stop/target ambiguity and regime exits at the open follow conservative documented conventions. Historical funding uses minute-open traded prices as mark proxies. Fees/slippage are assumptions rather than actual measured account fills.
- Both historical periods have been used in earlier research. Selection bias remains; no fresh holdout or prospective confirmation is claimed. Hundreds of correlated configurations must not be presented as independent evidence.
- No worker, VM, production file, strategy approval or live setting was changed. Research PRs remain separate from production promotion.

## 9. Recommendation and next steps

**Do not deploy a candidate from this batch.** Preserve this report as evidence that this specific EMA-reclaim framework, its target grid and these context filters have not established repeatable profitability.

1. Review the accepted/rejected entry audit before another experiment. Confirm whether the frozen zone definition represents the organization’s intended supply/demand concept. If not, document a materially different definition rather than quietly changing a threshold after seeing returns.
2. Avoid optimizing on two or three winning trades. Any subsequent study needs a capped hypothesis budget, training-only calibration and a clearly reserved or prospective evaluation plan.
3. If continuing with this entry family, fixed 1% stops versus token-specific volatility is a separate unresolved hypothesis. A new study could compare predeclared volatility-scaled stops at fixed account risk. This report does not claim that will repair expectancy.
4. Prospectively record spreads, depth, trade prints and actual/simulated order fills if the next hypothesis depends on liquidity or execution advantage. Candle-derived zones alone do not establish that mechanism.
5. Keep the trading book and live settings unchanged; this work makes no promotion request.

## 10. Deliverables and reproduction

- FINDINGS.md: executive report and caveats.
- results/executive_summary.csv, window_comparison.csv, target_summary.csv: clean management tables.
- results/all_720_configuration_comparisons.csv: complete chronological results, both periods and stress.
- results/all_5760_results.parquet: every paired/chronological/cost/period row.
- results/entry_acceptance_audit.parquet: every baseline opportunity-target decision, structure state, selected zone boundaries and confirmation time, opposing blocker and acceptance flags.
- results/positive_both_trade_evidence.csv: all trade records behind the small-sample positive exceptions.
- results/discovery_selected.csv: choices ranked on discovery only, where discovery count>=50; missing groups had no eligible selection.
- results/baseline_reconciliation.csv, manifest.json and supporting hashes: reproducibility trail.
- The sibling regime_target_20261004 directory contains the complete initial sensitivity study and its own report.

From repository root, with numpy/pandas/pyarrow available:

```bash
python3 -m unittest discover -s research/isolated_token_study_20261003/regime_target_20261004 -p "test_*.py"
python3 -m unittest discover -s research/isolated_token_study_20261003/context_filters_20261004 -p "test_*.py"
python3 research/isolated_token_study_20261003/regime_target_20261004/run_study.py --cache /path/to/cache --out /path/to/new_baseline
python3 research/isolated_token_study_20261003/context_filters_20261004/run_context.py --cache /path/to/cache --baseline /path/to/new_baseline --out /path/to/new_context
```

All return fields in machine-readable files are fractions (0.01=1%); target field is also a fraction. Entry timeframe tf is minutes. Column filter identifies the entry permission variant; policy identifies the exit policy. Open-at-boundary marks are included and separately flagged. Complete chronological trade exports are produced locally by the runner, with accepted/rejected context audit. Raw candles remain outside GitHub.
