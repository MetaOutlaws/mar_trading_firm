# Execution addendum — entry diagnostics and trailing exits

Frozen 2026-10-04 before any fitting, scoring, or result generation for this protocol.
Status: pre-registered. No market outcome in this document has been computed.
This file is the experiment contract. Thresholds below are the complete hyperparameter set. There is no grid, and none may be added after outcomes are seen.

Supersedes nothing in `independent_review/`. The original 48 configurations and the 20 alternatives stay archived as null. This protocol does not retune them. Their thresholds are not reused as search seeds.

## Ownership

- Entry research, execution simulation, and synthetic verification for this protocol are owned by the isolated research package in this directory. One cloud agent wrote it while executing `GROKBOT_ENTRY_TRAILING_BRIEF_2026-10-04.md`. No second worker is assigned.
- `research/eager_impulse_pullback_continuation.py` loads a separate production wire. This package does not import it, edit it, search its parameters, or deploy it. There is no shared candidate list with that sleeve.
- Offline research only. No VM, running worker, approval book, live setting, or production strategy is changed. Nothing here is an inbox item or a promotion.

## Garwe interlock

Scoring is forbidden until a parent reply records that the Garwe lock exists. `run_study.py` must exit before reading the cache unless `--acknowledge-garwe-lock` is passed. This agent does not pass that flag. The flag is an execution interlock, not a strategy parameter. Unit tests use synthetic bars only.

## Data

- Tokens: BTCUSDT, ETHUSDT, SOLUSDT only.
- Archive SHA256: `344ac29b5b2ee2fe9ba5966026914489dc22dfaed75374fbe86316052da863dc` (218,177,784 bytes). Raw candles are not committed.
- Cache layout: `{TOKEN}_1m.parquet` and `funding/{TOKEN}_funding.parquet`.
- File fingerprints, copied from `independent_review/results_20261004/manifest.json` and checked before any score:

| File | SHA256 |
|---|---|
| BTCUSDT_1m.parquet | `a6d3cf242680123f4bc3ca16cf88009d0567d5db65ab770270d98d6d6a9c7aa0` |
| BTCUSDT_funding.parquet | `8f72152a9e8dab4723c58904dcdea059d1b4484ac63bb9c3c93db3d98136ed2a` |
| ETHUSDT_1m.parquet | `d14e7fca972102acbb215afa7681863e93cada9be5d296b0dc2a746cfa72a2ab` |
| ETHUSDT_funding.parquet | `8b95a6e358acb7a0f70a502baa31aded1feb10b407678cc01e64335b152108ef` |
| SOLUSDT_1m.parquet | `55a4c6a06700cfb4d8b1ba219b94a07fb2daaf96e2c4588a4042ae2a8e84eca6` |
| SOLUSDT_funding.parquet | `5e43787de674452d41a852bba85eee904e272aac7d052d91b9997bce4d4bdc45` |

- Coverage audit uses the existing `study.audit` rules on the full tape, including the reserved window. That audit is a data check, not a strategy return.
- After the audit passes, every scored frame drops minute bars with open timestamp `>= 2026-01-01 00:00:00 UTC`. No 2026 bar is an entry, an exit, a label, or a feature input. The funding tape may keep the single boundary settlement at exactly `2026-01-01 00:00:00 UTC` so a last-minute 2025 time exit can apply the conservative funding rule. Later 2026 funding prints are dropped. No 2026 strategy return is computed in this protocol.

## Clocks and partitions

All timestamps UTC. Decision time `T` is the close of a completed 15-minute bar, which is also the next one-minute open. That is the same clock as `study.signals`: the fill, when a later stage trades, is the one-minute open at `T`.

- Discovery: `2022-01-01` inclusive to `2025-01-01` exclusive. Already explored by prior work. Further use is exploratory.
- Validation: `2025-01-01` inclusive to `2026-01-01` exclusive. Reused, not fresh confirmation.
- Reserved 2026: not scored.

A window of `H` minutes starting at `T` is inside a partition only when `T >= partition_start` and `T + H minutes <= partition_end`. The last bar open inside the window is `T + (H-1) minutes`. This is the same boundary test as `Tape.run`.

15-minute bars are resampled `closed='left'`, `label='right'`, and kept only when they contain 15 one-minute closes. The bar labelled `T` covers `[T-15min, T)`.

## Costs

Comparable model, matching the archived studies:

- Taker fee `0.00055` per side, charged on every fill notional. No maker fills.
- Slippage per side: BTCUSDT and ETHUSDT `0.0005`; SOLUSDT `0.001`.
- Entry fill `ep = quoted_open * (1 + side * slip)`. Exit fill `xp = quote * (1 - side * slip)`. `side` is `+1` long and `-1` short.
- Doubled-slippage stress multiplies those slippage rates by 2 and resimulates the path, including stop, target, activation, and partial prices, because those levels are measured from `ep`. Stress is a robustness check, not an extra candidate.
- Funding uses historical rates. Mark proxy is the one-minute open at the settlement, the same proxy as `study.Tape`. Settlements with timestamp `t` satisfy `entry < t <= exit` under the conservative minute rule below. The entry timestamp itself is excluded. Funding is divided by `ep` and scaled by the notional fraction still open. It is subtracted once for each fraction. It is not charged twice on the same fraction.

Conservative funding minute, copied from `Tape.funding`: for an exit bar open `x`, compare the sum through `x` with the sum through `x + 1 minute`. Stop, target, trail, and partial exits pay the more costly of the two (the maximum of the two signed funding returns). A time exit pays the sum through `x + 1 minute`.

Desk disclosure model, reported beside the comparable model and not used as a second search: `0.001` slippage per side on every token, plus the same `0.00055` fee per side. Before funding, that is 31 bp round trip on BTC, ETH, and SOL. The comparable model is 21 bp round trip on BTC and ETH and 31 bp on SOL, again before funding. Screening gates use the comparable model only. The desk column is a disclosure. A survivor that fails the desk column is still reported as failing that reality check; the column does not add candidates.

Position sizing for every return, drawdown, and streak: fixed entry notional of 1 quote unit. Partial exits are returns on that original 1, not on a new account. Sums and drawdowns are additive. They are not compounded equity, margin return, or leveraged return.

Fee identity for a full exit: `fee = 0.00055 * (1 + xp / ep)`.
Fee identity for a 50% partial then a remainder: `fee = 0.00055 * (1 + 0.5 * xp_partial / ep + 0.5 * xp_remainder / ep)`. The entry fee is the leading `1` and appears once.

Profit factor: sum of strictly positive net returns divided by the absolute sum of strictly negative net returns. No losing trades makes profit factor null, which fails `PF >= 1.15`. No trades fails the screen. Payoff ratio: mean positive net divided by the absolute mean negative net, null if either side is empty. Win rate: share of nets strictly above zero. Expectancy: mean net return per trade. Drawdown: maximum peak-to-trough decline of the cumulative sum of those unit-notional nets, in trade order. Losing streak: longest run of strictly negative nets. Adverse excursion: largest adverse quoted move versus `ep` from the entry bar through the exit bar, as a positive fraction. Profit giveback: that same window's maximum favourable excursion versus `ep`, minus the realized price return at the fill quotes before exit slippage, fees, and funding. For a partial, the realized price return is the notional-weighted quote return of the partial fill and the remainder fill.

## Features

Nine features. No others. No cross-asset residual, no order-book feature, no feature selection. All of them use completed 15-minute bars only. Future extrema may define research labels and must not define a feature or an entry.

On the 15-minute frame, bar `T` included:

1. `rv_24h`: sample standard deviation (`ddof=1`) of the last 96 completed 15-minute log closes ending at `T`.
2. `atr_pct`: simple mean of the last 14 true ranges ending at `T`, divided by `close[T]`. True range is the maximum of high-low, absolute high minus prior close, and absolute low minus prior close. This is an SMA, not Wilder.
3. `rel_volume`: `volume[T] / median(volume of the 96 bars strictly before T)`.
4. `range_compression`: range of the 96-bar lookback's last 16 bars strictly before `T`, divided by the range of the 96 bars strictly before `T`. The bar `T` is excluded so the signal bar does not write its own compression. A zero denominator makes the feature missing.
5. `trend`: `close[T] / EMA(close, span=48, adjust=False, min_periods=48) - 1`, EMA through `T` inclusive.
6. `dist_high`: `close[T] / max(high of the 96 bars strictly before T) - 1`.
7. `dist_low`: `close[T] / min(low of the 96 bars strictly before T) - 1`.
8. `hour_sin`: `sin(2π * hour(T) / 24)`.
9. `hour_cos`: `cos(2π * hour(T) / 24)`.

A decision is eligible only when all nine are finite. That warm-up is part of the sampler, not a drop decided after seeing labels. Feature column order for the model is the order above.

## Stage 1 — describe moves, including failures

One descriptive protocol. Not a trading system. The cells below are all reported and none is promoted to a target.

- Horizons: 60, 240, 480, and 1440 minutes.
- Barriers: 1%, 2%, 3%, and 5% in both directions. These are labels, not optimized targets.
- Reference price: the quoted one-minute open at `T`. Stage 1 does not apply fees, slippage, or funding.
- Long favourable barrier `open * (1+p)`, adverse barrier `open * (1-p)`, with `p` in `{0.01, 0.02, 0.03, 0.05}`. Short barriers swap the directions.
- Same-bar race: walk minutes from `T` inclusive for `H` bars. If the favourable and adverse barriers of the same `p` are both touched on one minute, adverse is first. A gap through a barrier counts on that bar.
- Outcomes recorded for every eligible decision, including failures: maximum favourable excursion, maximum adverse excursion, minutes to the favourable barrier (censored at `H` when it is not first), and the race result `favourable_first`, `adverse_first`, or `neither`.
- Dense sample: every eligible 15-minute decision whose horizon lies inside the partition. Overlapping labels are not independent. Uncertainty for the favourable-first rate is a weekly-block bootstrap, 1000 resamples, seed `20261004`, 2.5 and 97.5 percent quantiles. Weeks with no decisions stay in the resample as empty blocks.
- Declustered sample: the subset of those decisions whose `T` lies on the grid `2022-01-01 00:00 UTC + k * H`. Horizons are multiples of 15 minutes, so the grid is a subset of decision times. These non-overlapping windows are the independent-count sample. Both samples are reported. Capture counts from different horizons or sides are not added together.
- Partitions: discovery and validation separately. No 2026 rows.
- Controls: inside each token, side, partition, horizon, and barrier, an event is `favourable_first`. A non-event is every other eligible dense decision. Volatility quartile edges are the empirical quartiles of `rv_24h` inside that token and partition (`qcut`, `duplicates='drop'`). They are descriptive bins, fit inside the partition being described, and they are not a trading rule carried into Stage 2. Match 1:1 without replacement inside UTC hour × quartile. Walk groups in order of hour then quartile. Seed `20261004`. If events outnumber non-events in a group, sample the events down. Report matched count, unmatched count, and the difference in means of each of the nine features (event minus control). Also report the cell base rate.

Stage 1 budget: `3 tokens × 2 sides × 4 horizons × 4 barriers = 96` descriptive cells. Identifiers are `s1_{TOKEN}_{long|short}_{H}m_{P}pct` with `H` in `{60,240,480,1440}` and `P` in `{1,2,3,5}`. Every cell is attempted. None may be deleted after the rates are known.

## Stage 2 — bounded entry discovery

Question asked before any exit is chosen: does information available at `T` identify a 4-hour quoted move large enough to clear the comparable cost hurdle?

Fixed label horizon: 240 minutes. Quoted entry is the one-minute open at `T`. Quoted exit is the close of the bar at `T+239 minutes`. Signed quoted return is `side * (exit_close / entry_open - 1)`. Binary label `y = 1` when that signed quoted return exceeds the comparable round-trip hurdle before funding: `0.0021` for BTC and ETH, `0.0031` for SOL. Otherwise `y = 0`.

The gate does not use `y` as a profit. The gate uses the costed fixed-horizon return: slipped entry, slipped exit at that same close, one entry fee, one exit fee, and funding with `exact_close=True`. No stop and no target in Stage 2.

Two views:

- Overlapping diagnostic: every signal. Dependent. Not the gate.
- Gate sample: walk signals in time and keep one only when it is at least 240 minutes after the previous kept signal. Labels do not share bars.

### Rules — 12 configs, zero fitted thresholds

Family `compression`, continuation:

- Long: `range_compression <= 0.40` and `rel_volume >= 2.0` and `trend >= 0` and `dist_high > 0`.
- Short: `range_compression <= 0.40` and `rel_volume >= 2.0` and `trend <= 0` and `dist_low < 0`.

Family `fade`:

- Long: `dist_low <= -0.01` and `rel_volume >= 2.0`.
- Short: `dist_high >= 0.01` and `rel_volume >= 2.0`.

No other rule, cutoff, or lookback. Identifiers: `rule_compression_{TOKEN}_{long|short}` and `rule_fade_{TOKEN}_{long|short}`.

Rule discovery window: `T >= 2022-01-01` and `T + 240 minutes <= 2025-01-01`. Rule validation window: `T >= 2025-01-01` and `T + 240 minutes <= 2026-01-01`. Rules have no estimated weights, so these full windows are the gate samples. The three model folds below are also tabulated for rules, as a readability check, and are not a second gate.

### Model — 6 configs, one hyperparameter value

Identifier: `model_l2_{TOKEN}_{long|short}`.

- L2 logistic regression. Coefficient vector includes an intercept.
- Objective: `0.5 * ||w||^2 + C * sum_i (sample_weight_i * logloss_i)` with `C = 1.0` only. The intercept is not penalized.
- Balanced training weights: `n / (2 * n_class)` inside the training fold.
- Standardize the nine features with the training-fold mean and sample standard deviation (`ddof=1`). A training standard deviation below `1e-12` is replaced by `1.0`. The test fold uses that frozen scaler. The intercept column is not standardized.
- Start coefficients at zero. Newton / IRLS for at most 50 iterations. Stop when the largest absolute coefficient change is below `1e-8`. Clip probability to `[1e-12, 1-1e-12]` when forming weights. If the Hessian is singular, add `1e-8` to its diagonal once and continue. If the step still fails, the fold is `failed_fit`, emits no trades, and is not refit under another `C` or threshold.
- If the training fold has fewer than 50 positives or fewer than 50 negatives, the fold is `failed_class_count`, emits no trades, and the threshold is not loosened.
- Enter when `P(y=1) >= 0.60`. That cutoff is not tuned.
- No shuffle. No bootstrap of rows. No feature drop.

Expanding folds. Purge is 24 hours, wider than the 4-hour label, so a label cannot touch the test period.

| Fold | Train | Test | Role |
|---|---|---|---|
| fold_2023 | `T >= 2022-01-01` and `T + 24h <= 2023-01-01` | `T >= 2023-01-01` and `T + 4h <= 2024-01-01` | discovery, out of fold |
| fold_2024 | `T >= 2022-01-01` and `T + 24h <= 2024-01-01` | `T >= 2024-01-01` and `T + 4h <= 2025-01-01` | discovery, out of fold |
| fold_2025 | `T >= 2022-01-01` and `T + 24h <= 2025-01-01` | `T >= 2025-01-01` and `T + 4h <= 2026-01-01` | exploratory validation |

Model discovery for the gate is the pooled out-of-fold test rows from fold_2023 and fold_2024, then declustered at 240 minutes. Model validation is fold_2025 only, declustered the same way. Year 2022 is training material for the model and is not scored. In-sample predictions are not scored.

### Freeze rule

A Stage 2 config is eligible only when, on the declustered gate sample, under the comparable cost model:

- at least 50 trades in discovery and at least 50 in validation;
- mean net return strictly positive in both;
- profit factor at least 1.15 in both, and not null;
- doubled-slippage mean net strictly positive in both.

At most one config is frozen per token. Rank is discovery mean net, descending. Ties break by identifier, ascending. Rank does not look at 2025. If none are eligible, the token's frozen id is null. Gates are not loosened. 2026 is not consulted. Eighteen configs are attempted whether or not they are eligible.

Frozen entry timestamps, used only if an id freezes:

- Rules: every fire inside the Stage 2 discovery window, and every fire inside the validation window. Stage 3 then drops fires whose 24-hour maximum hold would cross the partition end. Those late fires remain in the Stage 2 4-hour sample when their 4-hour window fits.
- Models: out-of-fold fires with probability at least 0.60. Discovery uses fold_2023 and fold_2024. Validation uses fold_2025. The model is not refit after the freeze. The same 24-hour boundary drop applies in Stage 3.

## Stage 3 — four exits on the frozen entries only

Stage 3 does not run on a token whose frozen id is null. It does not borrow a near-miss. The four exits are the entire exit budget. They are not crossed with the seventeen configs that lost the freeze. Doubled slippage reruns these same cells. The desk 31 bp column reruns them again for disclosure. Neither rerun is a new config.

Common execution:

- Unit entry notional 1. Initial risk 1% of `ep`: long stop `ep * 0.99`, short stop `ep * 1.01`, active from the entry bar.
- Maximum hold 1440 one-minute bars, entry bar included. Time exit uses that last bar's close, then adverse slippage, full remaining size.
- Trails update from a completed bar for the next bar only. The stop tested on bar `j` was known at the open of bar `j`. The high or low of bar `j` must not tighten the stop that bar `j` is tested against.
- Favourable extreme starts at `ep`. After a bar completes without an exit of the whole position, the long extreme becomes `max(extreme, high)` and the short extreme becomes `min(extreme, low)`.
- A trail is inactive until `side * (extreme - ep) / ep >= 0.01` on that completed-bar extreme. Activation is 1% from `ep`, not from the quoted open.
- Once active, a long protective price never decreases and a short protective price never increases. The initial stop remains in force when the raw trail is looser.
- Gap: if the open is already through the protective price, the quote is the open, then adverse slippage. The stop price is not a guaranteed fill. Target and partial quotes do not improve when the open gaps through them; the quote stays at the target or partial price.
- Same bar: if the protective price known at the open and a target or partial are both touched, the protective exit takes the entire remaining position. No partial is credited on that bar.
- One chronological position per token per exit. A new signal with index at or before the prior exit bar is skipped. Paired mode does the opposite: every in-partition signal is simulated under all four exits even when the holds overlap. Paired results are not a portfolio. The write-up must show how many chronological entries each exit kept versus the paired signal count.
- Flat at the partition boundary via the 1440-minute test above.

Exit `fixed`:

- Stop 1% and target 2% of `ep`. No trail and no partial.
- Same-bar stop and target: stop wins. Target quote is `ep * (1 + side * 0.02)`.

Exit `trail`:

- Stop 1%. No fixed target.
- After activation, long trail `extreme * (1 - 0.008)` and short trail `extreme * (1 + 0.008)`. The 0.8% is of the extreme price, not of `ep`.
- The new trail applies on the next bar, then the monotonic clamp versus the initial stop is applied.

Exit `trail_atr`:

- Stop 1%. Activation 1%, same completed-bar rule.
- Absolute ATR is `atr_pct * close[T]` of the signal 15-minute bar, frozen for the trade. It is not refreshed.
- Raw distance is `1.5 * ATR`, clamped to `[0.003 * ep, 0.020 * ep]`.
- Long trail `extreme - distance`. Short trail `extreme + distance`. Next bar only, then monotonic.

Exit `partial_trail`:

- Stop 1%. Partial fraction 0.50 of the original coins, quoted at `ep * (1 + side * 0.01)`, then adverse slippage on that half.
- The partial fills on the touch bar only when the protective stop known at that bar's open is not also touched.
- The remainder is protected by the same 0.8% extreme trail as `trail`, starting on the bar after the partial bar. Until that trail tightens, the remainder still carries the initial stop.
- Fees use the partial identity above. Funding for the closed half runs from entry through the partial exit. Funding for the remainder runs from entry through the final exit. A settlement before the partial is therefore charged once at full notional, split across the two fraction calls. A later settlement is charged only on the remainder.

Reason codes: `stop`, `target`, `trail`, `time`, `partial_stop`, `partial_trail`, `partial_time`. `trail` and `partial_trail` mean the protective price had already tightened off the initial stop. `stop` and `partial_stop` mean the initial stop was still the protective price.

Stage 3 identifiers, instantiated only for a frozen entry: `s3_{TOKEN}_{entry_id}_{fixed|trail|trail_atr|partial_trail}`. Budget: at most `3 tokens × 1 entry × 4 exits = 12` scored strategy cells. If the freeze is empty, zero cells are scored and the four exit names stay unused.

## Screening and what is not claimed

Necessary screen, comparable model, declustered Stage 2 sample or Stage 3 trade list as applicable: at least 50 trades, positive mean net, and profit factor at least 1.15, in both discovery and validation, plus positive doubled-slippage mean net in both. The screen is not sufficient. This protocol does not compute weekly-block confidence intervals, matched random entry tests, or 2026 returns unless a later, separately frozen addendum says so after a non-null freeze. An empty freeze stops the study.

Multiple testing: 18 entry configs are the search. The screen is unadjusted. Eighteen attempts are recorded, including discards.

## Experiment ledger template

Outcome cells stay blank until a locked run writes a new output directory. Status before that run is `pre-registered`.

Columns: `experiment_id`, `stage`, `token`, `side`, `family`, `spec`, `status`, `trades_discovery`, `mean_discovery`, `pf_discovery`, `trades_validation`, `mean_validation`, `pf_validation`, `stress_mean_discovery`, `stress_mean_validation`, `desk_mean_discovery`, `desk_mean_validation`, `notes`.

Rows:

- 96 Stage 1 ids from the product in the Stage 1 section. `family` is `descriptive`. `spec` is `{H}m_{P}pct`. Notes: `not a trading candidate`.
- 12 rule ids and 6 model ids from Stage 2. `spec` repeats the frozen thresholds (`compression`, `fade`, or `l2_C1_p60`). Notes: `gate uses declustered 4h fixed-horizon net`.
- 4 exit specs with token blank: `exit_fixed`, `exit_trail`, `exit_trail_atr`, `exit_partial_trail`. Notes: `scored only after a per-token freeze; otherwise unused`.

Attempted trading configs in this protocol: 18. Descriptive cells: 96. Exit specs waiting on a freeze: 4.

## Reproduce

From the repository root, after the Garwe lock is recorded and the cache fingerprints match:

```bash
python3 -m unittest discover -s research/isolated_token_study_20261003/entry_trailing_20261004 -p "test_*.py"
python3 research/isolated_token_study_20261003/entry_trailing_20261004/run_study.py \
  --cache /path/to/cache \
  --out /path/to/new_output_directory \
  --acknowledge-garwe-lock
```

`--out` must be a directory that does not yet exist. The runner writes summary tables and per-trade `csv.gz` files there. It does not write raw candles. Without `--acknowledge-garwe-lock` the process exits 2 and does not open the cache.

Per-trade columns, when a run exists: `experiment_id`, `entry`, `exit_bar`, `side`, `entry_price`, `exit_price`, `partial_price`, `gross_return`, `fees`, `funding`, `net_return`, `reason`, `ambiguous`, `holding_minutes`, `mfe`, `mae`, `giveback`, `activated`. Paired files and chronological files are separate. Stage 2 files use the fixed-horizon reason `horizon` and leave partial fields blank.
