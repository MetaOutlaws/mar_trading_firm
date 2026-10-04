# Regime and target sensitivity, no holding-time exit
Registered 2026-10-04 before this study's signals/results. User explicitly requests entry timeframes 5m/15m/1h, target sensitivity including 2/2.5/3%, no imposed maximum holding time, and a regime-review exit comparison.

## Scope and data
Offline only, no production settings, book, VM or worker changes. Separate research branch based on PR95 commit 2307cbbc8ec36d1ef4abd7b85dc2850ede1f7f86. Earlier studies stay closed. Read-only overlap review found Grokbot's impulse_pullback_continuation uses a 4h/4h impulse geometry with daily SMA200 permission; this study uses EMA reclaim on 5/15/60m with a shared 4h EMA context. No production module is imported or altered; live worker state is not reverified here.

Use verified BTC/ETH/SOL one-minute candles and historical funding, six hashes from PR94 manifest. Discovery 2022–2024; reused validation 2025. Data cut before 2026 prior to signal generation. No 2026 strategy outcomes. No assertion of fresh out-of-sample confirmation after prior use of these periods.

## Frozen rules
Resample complete bars left-closed/right-labelled: timestamp T is the minute open immediately following the completed bar, so entry at open T is feasible under zero-latency bar simulation. Real latency is approximated only by slippage.

Shared market regime, computed only on completed FOUR-HOUR bars: EMA50 and EMA200, adjust=False with min_periods equal to span. Bullish if close>EMA200, EMA50>EMA200, and EMA50>its value three 4h bars ago. Bearish if all reverse. Otherwise neutral. No trading until both averages and slope history exist. Carry the last completed regime forward to each decision; never use the still-forming 4h bar.

One entry family, on each of 5m,15m,60m separately: long when the completed close crosses from <=EMA20 to >EMA20 and the current shared regime is bullish; short when it crosses from >=EMA20 to <EMA20 and regime is bearish. EMA20 adjust=False, min_periods=20. Same-side fires during an open chronological position are ignored. Long and short configurations are reported separately, not silently combined into a capital portfolio. No extra filters, indicators or tuned thresholds.

Initial protective stop = 1% adverse movement from QUOTED entry open. Targets = 1%,1.5%,2%,2.5%,3% favourable movement from QUOTED entry open. Using quote-based barriers ensures the user's underlying-movement targets and identical price paths at base/stressed fills; costs still reduce net realized profit. Target distances are not promised net returns. No stop-loss sensitivity in this experiment.

Two exits: A=target or initial stop only; B=same orders plus regime invalidation. B reviews the latest completed shared 4h regime at each completed entry-timeframe bar; closes at that bar's next minute open when regime is no longer aligned, including neutral. Since 4h boundaries align with all entry clocks, regime changes first become visible at those boundaries. This is a deterministic, auditable proxy for reviewing market context, NOT a backtest of discretionary AI judgments.

No time-based exit. Orders persist until one of these conditions occurs. Boundaries are observational censoring: if still open at the discovery/validation end, mark at the final minute close, including hypothetical exit fee/slippage and funding, tag boundary_mtm, and report open-at-boundary count/return separately. Include those valuations in all-in returns so unresolved losses cannot disappear; also show closed-only mean. Do not count boundary marks as target/stop hits. Start each partition flat. Long-held trades may cross years inside discovery.

## Execution and costs
Minute OHLC order simulation: known protective stop wins a same-minute stop/target touch; stop gaps fill at worse open. Targets fill at the target quote without favourable gap improvement. A regime exit occurs at the minute OPEN: at that open a preexisting breached stop/target takes priority, otherwise exit immediately without examining later highs/lows of that minute. All other barrier touches use intraminute conservative stop-first ordering.

Entry/exit slippage per side: BTC/ETH 5bp, SOL10bp. Stress doubles those slippage rates. Fee5.5bp per fill side, charged on actual fill notional. Unit entry notional1; no leverage or compounding. Historical funding uses minute-open price as mark proxy. Entry timestamp excluded. Intraminute exits take the worse of funding through minute open vs next minute open; regime-open exits charge through exit timestamp only; boundary-close marks through following minute boundary. Record these timing approximations. No quote-book, queue, liquidation or spread measurements implied.

Two evaluation views: paired runs every identical entry opportunity under all five targets and both exits, allowing overlapping trades (diagnostic only); chronological view has one position per configuration, skipping fires at or before exit minute, no same-minute reentry. Target choice can change the chronological eligible entries. Report both and do not pool overlapping candidate PnLs into a strategy portfolio.

## Finite budget and evaluation
3 tokens x3 entry timeframes x2 directions x5 targets x2 exit policies=180 distinct configurations. Two costs x two partitions x paired/chronological views =1440 summary rows; those repeats are not 1440 independent strategies. All configurations reported, no expansion after results. Frozen stop/regime/EMA values have no alternate settings.

Primary comparison is chronological net expectancy, trade count, PF, win rate, target/stop/regime/boundary counts, median/p95/max holding time, market exposure and drawdown. Paired view isolates exit effect on identical entries. Report costs and gross returns, average win/loss, losing streak, net result sums (additive not account return), closed-only mean and marked boundary contribution. Drawdown main metric is mark-to-market including fees, accrued funding and liquidation-cost assumptions, not just realized closed-trade drawdown.

Exploratory screen: chronological >=50 completed trades (exclude boundary marks) in each period; mean net>0 and PF>=1.15 in both, plus positive net means under doubled slippage in both. This is only a research screen, not promotion. A stable target region requires >=2 adjacent target values within a fixed token/timeframe/direction/exit policy to pass. No passing row is called proven alpha. For any passes report 2025 weekly-block intervals and Bonferroni correction across all180 attempts, keeping temporal dependence caveats. No holdout scoring or deployment in this study.

Headline tables: number of configurations and screen passes for each token/timeframe; five-target sensitivity for each token (equally weighted configuration diagnostics clearly not portfolio returns); discovery-selected setting per token/timeframe (highest discovery mean among n>=50 completed discovery trades, deterministic tie by id), with its later validation mean/PF/sample/cost stress. That last ranking never picks on validation. Include all180 configurations and year-level summaries, no hidden negative rows.

## Verification
Independent scalar execution oracle against optimized barrier lookup on randomized bars; long/short, same-bar ambiguity, stop gaps, regime-open precedence, no holding cap, boundary marks, funding timing and accounting. Feature future-perturbation and resampling checks. No source refitting to repair losses. Publish code, tables, input/source hashes, tests and limitations on isolated draft PR. Stop after the declared study.
