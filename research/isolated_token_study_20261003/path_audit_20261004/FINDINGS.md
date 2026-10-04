# Trade-path and trailing-exit findings — 2026-10-04

**Outcome: 12 of 12 tested entry/exit combinations fail the exploratory screen. All 48 period/cost result rows have negative net means.** This separate study completes the question left unanswered by PR94: some losing four-hour trades had temporary gains, but the predefined trailing exits did not convert the selected entries into a profitable strategy. PR94 remains CLOSED_NULL.

## What was actually done

- Protocol published at commit `4faf3d4c141b50ecc38da85521690b1d6b9c639c` before computing these diagnostics. Archived inputs fixed at PR94 `d79735916aab139ced1d827d601404484cb30003`.
- Used the exact archived entries; no retraining, threshold changes or new signal discovery. Six market file hashes match the original manifest. All candles used for features/outcomes precede 2026.
- Reconstructed 5,553 archived trades across 18 configurations and two periods, with maximum endpoint-return difference 2.09e-16. These are configuration-level observations, not 5,553 independent opportunities; configurations can overlap.
- Sampled 27,550 matched control draws, matching token/side/quarter/hour and trailing volatility quartile. Quartile thresholds fit on 2022 only. Controls exclude four-hour overlap with that configuration’s archived real entries. They may overlap each other and may be reused. Coverage is at least 95.71%.
- Examined four-hour paths for all 18 configurations. Chose at most one entry configuration per token from discovery diagnostics only under the frozen rule. Selection indicates eligibility for an exit experiment, not trading approval.
- Compared four fixed-in-advance exits on each selected entry set, at base and doubled slippage: 12 combinations, 48 period/cost rows. All holds are capped at four hours; this is distinct from PR94’s unexecuted 24-hour exit stage.
- Archived real entries are already at least four hours apart, so these exit comparisons are both paired on identical entries and chronological/nonoverlapping within each configuration. Controls do not form a portfolio.

## Temporary gains existed, but their frequency alone did not establish an edge

The primary diagnostic asks whether hypothetical net +1% was available at a favourable minute extreme BEFORE a 1% initial price stop was touched. A stop touch takes priority over a favourable extreme in the same minute. Hypothetical peak liquidation includes modeled costs and funding, but it is a hindsight upper bound, not an executable profit.

Selected configurations and their validation diagnostics:

| Token and entry | Trades | Net +1% before stop | Matched controls | Difference | Positive peak but negative endpoint |
|---|---:|---:|---:|---:|---:|
| BTCUSDT: rule_fade_BTCUSDT_long | 11 | 18.2% | 23.6% | -5.5 pp | 45.5% |
| ETHUSDT: rule_compression_ETHUSDT_short | 82 | 35.4% | 28.3% | +7.1 pp | 56.1% |
| SOLUSDT: model_l2_SOLUSDT_long | 60 | 35.0% | 33.7% | +1.3 pp | 50.0% |

For SOL, 21 of 60 validation trades reached a hypothetical cost-covered +1% before the initial stop, but the matched control rate was 33.7%, close to the signal’s 35.0%. Half of the SOL trades showed some hypothetical positive net peak and ultimately ended negative at four hours. This supports the existence of giveback, not a reliable trading advantage.

Across all 18 configurations, no validation primary-diagnostic Bonferroni interval excludes zero. Three discovery comparisons have positive Bonferroni lower bounds (BTC long compression, ETH long compression, ETH short compression), but that evidence does not carry through the validation intervals. The intervals themselves are exploratory: selection history, repeated controls, cross-week matching and overlapping configurations limit inferential strength. We do not claim proof of no effect.

BTC selection is the long fade rule; its validation set contains only 11 trades and cannot meet the sample-size screen. It was selected by discovery criteria, not substituted after seeing validation. ETH selection is short compression. SOL selection is the long L2 model. Selection was written before any new exit results were evaluated.

## Executable exit comparison

Percent figures below are mean net return per trade on entry notional. D=discovery, V=2025 validation. Stress doubles slippage and reruns execution. PF is profit factor after costs. Same-bar ordering is conservative; a trail computed from the current candle applies only on the next candle.

| Token | Exit | D mean | D PF | V mean | V PF | Stress D mean | Stress V mean |
|---|---|---:|---:|---:|---:|---:|---:|
| BTCUSDT | fixed | -0.1936% | 0.726 | -0.8413% | 0.113 | -0.3271% | -0.9001% |
| BTCUSDT | partial_trail | -0.1771% | 0.713 | -0.6904% | 0.181 | -0.2881% | -0.7492% |
| BTCUSDT | trail | -0.0861% | 0.861 | -0.7021% | 0.167 | -0.2178% | -0.7655% |
| BTCUSDT | trail_atr | -0.0147% | 0.977 | -0.7783% | 0.077 | -0.1466% | -0.8416% |
| ETHUSDT | fixed | -0.2871% | 0.562 | -0.4453% | 0.448 | -0.3653% | -0.5242% |
| ETHUSDT | partial_trail | -0.2348% | 0.585 | -0.3618% | 0.449 | -0.3284% | -0.4469% |
| ETHUSDT | trail | -0.2403% | 0.575 | -0.4086% | 0.378 | -0.3292% | -0.5018% |
| ETHUSDT | trail_atr | -0.2506% | 0.570 | -0.4537% | 0.341 | -0.3383% | -0.5469% |
| SOLUSDT | fixed | -0.2196% | 0.714 | -0.5244% | 0.429 | -0.4511% | -0.8319% |
| SOLUSDT | partial_trail | -0.2419% | 0.619 | -0.4613% | 0.397 | -0.3909% | -0.6550% |
| SOLUSDT | trail | -0.2024% | 0.682 | -0.4467% | 0.416 | -0.3529% | -0.6346% |
| SOLUSDT | trail_atr | -0.1453% | 0.795 | -0.5878% | 0.311 | -0.3600% | -0.8195% |

Definitions: fixed=1% initial stop/2% target; trail=1% initial stop, +1% activation, 0.8% extreme trail; trail_atr=same stop/activation and 1.5×entry ATR distance clamped to 0.3–2%; partial_trail=half out at +1%, remainder on the 0.8% trail. All maximum holds are four hours.

All selected configurations’ validation exit returns also underperform their matched controls under the same exits. Some trailing variants lose less than the fixed stop/target baseline; that is not a positive return. For example, ETH partial-trail improves validation mean from −0.4453% for fixed exits to −0.3618%, but still loses.

The original no-stop four-hour endpoint is a different baseline. SOL’s archived validation endpoint mean was −0.2733%; its least-negative tested exit, the 0.8% trail, is worse at −0.4467%. Changing to protective exits can cut off recovery paths as well as reduce giveback. No extra exit settings were searched after seeing these results.

## Interpretation and decision

The data confirm that temporary gains occur. The tested executable rules do not capture enough of them to offset losing paths and costs. A higher win rate is insufficient when average losses and execution costs outweigh the gains. A hindsight peak cannot be used as an attainable exit target.

Do not promote any tested configuration. Do not use leverage to turn these negative unit-notional means into a profitability claim. This result applies to the frozen entries, four-hour horizon and four exit specifications; it does not reject every possible entry/exit system.

The next evidence should address a genuinely different predictive mechanism or measured execution advantage, with a new registered design. Order-flow/liquidity data and observed fills could test whether there is entry information missing from candles. More random trail-distance searches on reused 2025 results would create additional selection bias. This report proposes no new deployment or worker instruction.

## Verification, caveats and reproduction

- Eight new synthetic test methods pass. Thirty-three archived engine/feature/protocol tests pass. New checks cover independent scalar peak-cost arithmetic, archived endpoint identity, adverse-first extrema, profit-before-stop, gap after trail activation, control exclusion, future-feature independence, boundaries and bootstrap constants.
- Archived funding uses minute-open traded-price proxies and conservative settlement bounds. Fees are 5.5bp per side, slippage 5bp BTC/ETH and 10bp SOL per side at base costs. These assumptions are not measured account-specific fills.
- Real returns are fixed entry notional. Additive drawdown is not compounded account equity or leveraged margin drawdown. No liquidation, queue priority, order-book depth or within-minute tick path is modeled.
- Selection of the discovery-maximizing diagnostic induces optimism. Validation was already explored in earlier studies. No independent confirmation or 2026 returns are claimed.
- Control matching is observational, not causal. Wide volatility bins and hourly matching do not eliminate every regime difference. Bootstrap clustering uses real-entry weeks; reuse and cross-week control dependence remain limitations.
- PR94’s execution commit was not embedded in its original run artifact. This audit records the exact source snapshot it read and reconciles exported endpoints to the supplied tape; it does not retroactively repair PR94’s original provenance.

Run from repository root with numpy, pandas and pyarrow available:

```bash
python3 -m unittest discover -s research/isolated_token_study_20261003/path_audit_20261004 -p "test_*.py"
python3 -m unittest discover -s research/isolated_token_study_20261003/entry_trailing_20261004 -p "test_*.py"
python3 research/isolated_token_study_20261003/path_audit_20261004/run_audit.py --cache /path/to/verified/cache --out /path/to/new_output_directory
```

The archived test suite intentionally verifies that its own original runner refuses scoring without its lock acknowledgement. This audit imports the library functions and does not invoke that runner.

Results include all 36 diagnostic rows, all 48 exit rows, all 12 failed screens, selection, manifest, complete real-trade path/exit exports and a compact matched-control timestamp schedule. Full per-control calculations are emitted by the reproducible runner. The CSV percentage fields are stored as fractions: 0.01 means 1%. In the combined gzip files, sample identifies original configuration/partition/exit/cost; set_id maps each matched control to the row in that configuration’s original chronological real-entry export.
