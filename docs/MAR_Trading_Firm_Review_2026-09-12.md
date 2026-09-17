# MAR Trading Firm: code review and recovery plan

Prepared for Brian Zhanda • 12 September 2026

Repository: MetaOutlaws/mar_trading_firm  
Branch reviewed: `feat/employee-floor-and-openai`  
Commit: `c04028cbcb00f3eabfafbcad8a4912bdd20aa4d3`

**Assessment: repair the measurement and execution system before selecting more strategies.** The design has useful foundations, but the current code does not establish that its approved strategies have a reliable edge or that paper trading executes the system being backtested. Several material defects were reproduced offline. More strategy generation would currently produce more unreliable evidence.

This is a comprehensive review of the principal execution, risk, accounting, validation and worker coordination paths, with targeted strategy inspection. It is not a line-by-line certification of all 157 Python modules in the strategy directory, a production penetration test, or a new historical performance study.

## 1. What is verified, and what is missing

The repository was accessed through GitHub and cloned for read-only analysis at the commit above. No production process, exchange account, approval file or deployed code was changed. The repository working tree remained clean after verification.

The reported six losses from seven paper trades is **user-reported**, not independently verified. The repository excludes `data/*.db`, research artifacts, price caches and trading logs. Its checked-in data folder contains only an example sentiment snapshot. Consequently, I cannot attribute those seven outcomes to particular signals, fills, fees, market regimes, overrides or deployed code versions.

The code contains an internal employee orchestrator, Cursor coding handoffs and file-based hooks for external sentiment/regime inputs. I did not find a Grokbot deployment manifest or its external workers' operating instructions in the inspected source. Grokbot may run or modify these components externally; verifying that deployment requires its configuration and runtime evidence.

**Verified approval-file inventory**

| Item | Committed state |
|---|---:|
| Strategy/pair/side/timeframe records | 880 |
| Distinct strategy prefixes among those records | 97 |
| `approved: true` records | 3 |
| Additional `paper_override: true` records | 4 |
| Approved long strategies | 0 |

| Approved configuration | Reported OOS trades | Reported win rate | Reported profit factor | Reported expectancy per trade |
|---|---:|---:|---:|---:|
| ATR channel / BTC / SHORT / 4h | 284 | 48.94% | 1.447 | 0.5235% |
| ATR channel / ETH / SHORT / 4h | 333 | 50.75% | 1.500 | 0.6327% |
| Doji star / SOL / SHORT / 1h | 119 | 52.10% | 1.504 | 0.6528% |

These are stored outputs, **not validated performance estimates endorsed by this review**. The walk-forward defect below calls their reliability into question. The approval header also retains a REJECTED verdict while individual rows grant approval, showing documentation/status drift.

The four paper overrides are mass-index SOL LONG and ETH SHORT, and MAMA/FAMA BTC SHORT and ETH SHORT, all 4h. The SOL mass-index override has only five reported OOS trades. These are experiments, and their results should not be pooled into a validated portfolio's record.

Source: [committed approvals](https://github.com/MetaOutlaws/mar_trading_firm/blob/c04028cbcb00f3eabfafbcad8a4912bdd20aa4d3/config/approved_strategies.json).

## 2. Functionality and architecture

| Component | Implemented functionality | Assessment |
|---|---|---|
| Market data | Bybit candles, caching, funding history, positioning and sentiment inputs | Useful foundation; dataset lineage and quality gates need strengthening |
| Strategy layer | Deterministic strategy interface and registry | Shared signal functions are good, but do not guarantee execution parity |
| Research | Parameter search, walk-forward, bootstrap, randomized-entry comparison, regime breakdown | Substantial framework; boundary and statistical defects compromise approval evidence |
| Risk | Position, sector, exposure, daily-loss and drawdown checks; size reductions; file-backed halt | Several real constraints exist; exit continuity, cooldown recovery and post-fill checks are incomplete |
| Paper broker | Simulated fills, fees, in-memory positions and polled exits | Accounting persistence and execution semantics differ from research |
| Bybit broker | Market orders, fill lookup, TP/SL and position reads | Acknowledgements, retries and external closures are not safely reconciled |
| Employee organization | Ten internal roles, structured outputs, proposals, budgets and trust levels | Action delivery and scheduling are incomplete; organizational activity is not evidence of alpha |
| API/dashboard | Blotter, equity, worker floor, research and go-live views | Several headline metrics can be inaccurate because their underlying state is inaccurate |

The main operating loop runs pipeline advancement, then a trading cycle, then due employees sequentially, then sleeps. The next trading cycle therefore waits for all that work. Exit monitoring shares this loop.

## 3. Critical findings

Priority definitions: **P0** prevents trusting performance or safely promoting the system; **P1** materially impairs operation, research or control. Reproduced means an offline test exercised the current implementation, with synthetic prices or mocks where appropriate. Static means the conclusion follows from the inspected code path; it has not been observed on your deployment.

### F01 — P0: walk-forward warm-up bars can be counted as OOS trades

`_slice_with_warmup()` prepends 300 historical bars. `walk_forward()` gives that entire frame to `BacktestEngine.run()`. There is no explicit trade-start boundary. The implementation relies on each strategy's `min_bars`, but ATR uses 54 bars and doji uses 12. Signals after that shorter warm-up can open positions before the intended test period.

**Reproduced:** a synthetic hourly dataset, the actual ATR strategy and seven folds produced 174 reported OOS trades. **57 entered before their fold's test start.** The first test window began 31 January; its first reported OOS entry was 22 January at 12:00 UTC. This is a defect demonstration, not an estimate of contamination in the historical approval records.

At 4h, the 246-bar gap between the default prefix and ATR's suppression length spans approximately 41 days. It can substantially contaminate a 60-day test and create overlapping fold exposure. Inclusive window endpoints are another boundary to resolve.

**Repair:** add explicit eligible signal/entry times; indicators may consume preceding history but no pre-test fill may enter the OOS ledger. Define half-open windows, boundary exits and position carry consistently. Assert all OOS trades fall within their specified window, and detect duplicate/overlapping trade identities. Revalidate all surviving candidates under a new research version.

Source: [walk-forward implementation](https://github.com/MetaOutlaws/mar_trading_firm/blob/c04028cbcb00f3eabfafbcad8a4912bdd20aa4d3/research/walkforward.py#L344-L420).

### F02 — P0: paper cash resets on restart

`build_engine()` constructs a new broker with the original starting equity. `hydrate()` restores open positions but not cumulative realized P&L, prior fees or a reconciled cash balance.

**Reproduced:** broker cash was $9,994 after a round trip and $10,000 after reconstruction and hydration. The trade ledger still retained the loss.

**Repair:** persist a cash/event ledger and replay it on startup, including entry fees on still-open positions. Preserve capital contributions separately from P&L. Restarting with open and closed trades must leave cash, equity and exposure unchanged at identical marks.

Sources: [broker hydration](https://github.com/MetaOutlaws/mar_trading_firm/blob/c04028cbcb00f3eabfafbcad8a4912bdd20aa4d3/core/execution/paper.py#L76-L108), [engine construction](https://github.com/MetaOutlaws/mar_trading_firm/blob/c04028cbcb00f3eabfafbcad8a4912bdd20aa4d3/core/execution/engine.py#L1183-L1225).

### F03 — P0: ledger P&L omits entry fees; paper omits funding

The broker deducts entry fees, but `_place_order()` does not persist them on the position. On paper exit, only the closing fee reaches `Ledger.close_position()`. The ledger consequently overstates net P&L. Paper does not accrue funding, although historical research does. Research also applies symbol-dependent slippage while the paper broker uses its default cost model for every symbol.

**Reproduced:** with deliberately explicit test costs, an unchanged-price round trip lost $6 cash but recorded a $4.998 ledger loss. The $1.002 difference was the entry fee.

**Repair:** record every entry/exit fee, funding event and fill. Reconcile realized cash against trade P&L, with open-entry fees accounted for. Use the same versioned per-symbol cost assumptions for comparison runs. Clearly separate assumed costs from measured executions.

Sources: [order and exit recording](https://github.com/MetaOutlaws/mar_trading_firm/blob/c04028cbcb00f3eabfafbcad8a4912bdd20aa4d3/core/execution/engine.py#L1075-L1180), [ledger calculation](https://github.com/MetaOutlaws/mar_trading_firm/blob/c04028cbcb00f3eabfafbcad8a4912bdd20aa4d3/core/ledger/store.py#L116-L190).

### F04 — P0: paper execution does not reproduce the tested strategy

Static findings:

- Research enters at next-bar open and derives TP/SL from the slipped fill. Execution derives TP/SL from the prior signal close and submits later at the current price. There is no corresponding post-fill risk/level validation.
- Research enforces `max_holding_bars`; runtime exit management only checks TP/SL. The default 96 bars means 16 days on 4h or four days on 1h, not universally 24 hours.
- Paper checks a sampled current price, not the intervening path. A stop touched and recovered between cycles is invisible. A later crossing is filled at the later current price.
- Research omits additional exit slippage on stop-loss exits; paper applies exit slippage when closing. This is another explicit mismatch to resolve.
- Historical tests run individual sleeves; runtime permits only one position per symbol. Competition between approved sleeves and overrides changes which signals get executed.

**Repair:** specify one execution contract covering timing, stops, expiry, fees, funding and position conflicts. Store strategy version, full parameters, timeframe and expiry on every position. Replay the same market events through research and paper and reconcile signals, fills, exits and P&L. Intrabar uncertainty should be explicit.

Sources: [backtest entry/exits](https://github.com/MetaOutlaws/mar_trading_firm/blob/c04028cbcb00f3eabfafbcad8a4912bdd20aa4d3/research/engine.py#L375-L460), [runtime evaluation/execution](https://github.com/MetaOutlaws/mar_trading_firm/blob/c04028cbcb00f3eabfafbcad8a4912bdd20aa4d3/core/execution/engine.py#L920-L1180).

### F05 — P0: halts disable paper position management

A tripped kill switch returns from `run_cycle()` before `_manage_open_positions()`. The script then exits its loop. An empty startup plan also exits the process, even if positions need management. If all entries are temporarily ineligible, that must not stop managing existing exposure.

**Reproduced:** a tripped switch prevented position management from being called.

**Repair:** distinguish “disable entries” from “flatten” and “stop service.” Exit supervision and accounting must remain active during an entry halt. Put paper stop monitoring on an independent event-driven or tightly scheduled path. Only stop the service after exposure is safely handled under the selected halt policy.

Sources: [cycle early return](https://github.com/MetaOutlaws/mar_trading_firm/blob/c04028cbcb00f3eabfafbcad8a4912bdd20aa4d3/core/execution/engine.py#L803-L866), [runner](https://github.com/MetaOutlaws/mar_trading_firm/blob/c04028cbcb00f3eabfafbcad8a4912bdd20aa4d3/scripts/run_paper_trading.py).

### F06 — P0: legitimate exchange exits halt before settlement

The cycle reconciles before processing exchange-closed positions. A server-side stop or target therefore appears as “open in ledger but not at broker,” trips the switch and returns before the code intended to close the ledger row. Even that later path uses the current ticker, not actual exit executions, to infer realized P&L.

**Reproduced:** a mocked externally closed position halted the cycle and never reached exit settlement.

**Repair:** ingest and deduplicate executions, settle legitimate closes, then reconcile the remaining book. Unknown discrepancies should block new entries and trigger investigation. Actual fill quantities, fees and prices must determine settlement.

Source: [reconciliation and exit ordering](https://github.com/MetaOutlaws/mar_trading_firm/blob/c04028cbcb00f3eabfafbcad8a4912bdd20aa4d3/core/execution/engine.py#L834-L866).

### F07 — P0: failed operations can be reported as successful

**Reproduced:** a paper close returning `success=False` was still counted as closed and passed an exit price of zero to the ledger. A long could consequently appear to lose its entire notional without actually closing.

Additional static findings: `_attempt_entry()` returns its approved risk decision even when the order fails, so the cycle increments `orders_placed`. If stop placement fails, the emergency-close result is ignored and the event claims “position closed immediately.” A successful emergency round trip is also absent from the ordinary trade ledger on that path.

**Repair:** separate risk approval, order acknowledgement, fill confirmation, stop confirmation and close confirmation. Update metrics and ledger state only from confirmed outcomes. Persist the fill before attaching protection; failed protection must enter a tracked recovery state.

Source: [order/exit lifecycle](https://github.com/MetaOutlaws/mar_trading_firm/blob/c04028cbcb00f3eabfafbcad8a4912bdd20aa4d3/core/execution/engine.py#L1070-L1180).

### F08 — P0: Bybit acknowledgement is treated as a fill; retries lack stable identity

`_resolve_fill()` falls back to the requested quantity/reference price/zero fee when fill lookup fails. The parent returns success. `_call()` retries writes after exceptions, while market orders do not carry a stable `orderLinkId`. A lost response after exchange acceptance could therefore produce a duplicate order attempt.

Bybit documents asynchronous order acknowledgement and supports unique client order identifiers. Its market orders can also be unfilled/cancelled under liquidity conditions, so acceptance cannot stand in for a confirmed execution.

**Repair:** persist a unique intent/client order ID before submitting, reconcile that ID after uncertainty, track partial and final execution states, and never invent a fill. Confirm leverage/margin mode and protection state as part of startup/order checks.

Sources: [Bybit adapter](https://github.com/MetaOutlaws/mar_trading_firm/blob/c04028cbcb00f3eabfafbcad8a4912bdd20aa4d3/core/execution/bybit.py#L81-L314), [official order documentation](https://bybit-exchange.github.io/docs/v5/order/create-order).

### F09 — P0: reconciliation exceptions fail open

On a reconciliation exception, the engine logs the error and assigns an empty discrepancy list, then continues.

**Reproduced:** an injected reconciliation exception produced `halted=False` and reached the later cycle stages.

**Repair:** make unavailable portfolio state an explicit entry-blocking state. Preserve exit recovery where possible; never interpret missing reconciliation evidence as a clean reconciliation.

Source: [exception handling](https://github.com/MetaOutlaws/mar_trading_firm/blob/c04028cbcb00f3eabfafbcad8a4912bdd20aa4d3/core/execution/engine.py#L834-L842).

## 4. Research, worker and governance findings

| ID / priority | Finding and consequence | Required change |
|---|---|---|
| F10 / P1 | Random-entry testing compares net strategy returns after TP/SL/costs with gross random close-to-close returns. This contradicts the stated equal-mechanics comparison and can distort rejection decisions. | Use the same simulator/costs/exposure rules on both arms, or compute identical timing-only returns for both. Restrict comparisons to matching eligible windows. |
| F11 / P1 | Hundreds of candidate configurations are screened without a visible search-wide multiplicity correction. IID bootstrap also ignores clustered trades and repeated fold exposure. | Log every experiment, preserve an untouched final holdout and use dependence-aware resampling plus a documented multiple-testing procedure. |
| F12 / P1 | Research regimes are retrospective quarterly BTC returns; runtime regimes come from a different live feed/analyst. A quarter's final return is unavailable during that quarter. | Keep retrospective labels for diagnosis; validate a causal regime classifier using only data available at each decision time. Test the whole filtered strategy. |
| F13 / P1 | Soko input has no enforced timestamp expiry. `ON` bypasses blocked regimes. The scan-loop activation lookup uses `symbol:side`, whereas the file hook uses a full approval key. Live/testnet explicitly bypass paper regime sit-outs. | Enforce freshness and schema; use one full strategy identity; define override authority and require the promoted runtime to use the same validated regime policy. |
| F14 / P1 | `CycleAdvice.sit_out` is populated but `apply_to()` drops it. Reproduced with an empty-veto global sit-out instruction. | Add an explicit global entry gate, expiry and acknowledgement. Test global and symbol-level instructions end to end. |
| F15 / P1 | Sequential workers plus a fixed sleep delay the next scan and stop check. The actionable signal window is only 15 minutes after close. Applied advice can also survive beyond its intended expiry until replaced. | Separate workers from trading; schedule around candle closes, persist deadlines, enforce advice TTL at consumption and publish lag/missed-signal metrics. |
| F16 / P1 | Six consecutive losses cause “cooling down” without a time boundary/reset state. Once flat, no new trade can break the streak. | Define a documented time/review-bound cooldown and recovery event; retain the loss history. Do not silently reset performance to restart trading. |
| F17 / P1 | Concurrent validators read/merge/write a shared approvals JSON without a lock/atomic transaction. Parallelism defaults to three. | Serialize approval commits or use database transactions with version checks. Immutable per-job reports already help, but shared approval state still needs protection. |
| F18 / P1 | A PID-file check followed by an ordinary write is not an atomic execution lease. API and trading orchestrators also keep separate in-memory scheduling state. | Use an exclusive OS/database lease and durable worker scheduling/ownership, including retry and crash recovery. |
| F19 / P1 | Per-cycle equity is read before exits and entries, then recorded afterwards without refresh. The equity snapshot labels equity minus starting capital as realized P&L while unrealized defaults to zero. | Capture cash, realized, unrealized, fees and equity from one coherent snapshot; never conflate the fields. |
| F20 / P1 | Trade records omit full approval key, timeframe, parameter hash, signal-bar ID and research provenance. A 15-minute entry window is not durable signal deduplication. | Persist all identities, including a unique signal intent. Prevent restart/re-entry from executing the same bar's signal again unintentionally. |
| F21 / P1 | Approved and override sleeves share a symbol-limited book. Scan order can determine allocation; the PM gathers no actual open-position/correlation matrix despite its described role. Attribution assigns full trade P&L to each contributing agent. | Replay a shared portfolio; implement explicit conflict allocation and paired counterfactual measurements of worker value. Keep experimental books separate. |

Relevant source files: [significance](https://github.com/MetaOutlaws/mar_trading_firm/blob/c04028cbcb00f3eabfafbcad8a4912bdd20aa4d3/research/significance.py), [regime dataset](https://github.com/MetaOutlaws/mar_trading_firm/blob/c04028cbcb00f3eabfafbcad8a4912bdd20aa4d3/research/datasets.py), [Soko hook](https://github.com/MetaOutlaws/mar_trading_firm/blob/c04028cbcb00f3eabfafbcad8a4912bdd20aa4d3/core/data/soko_trend.py), [orchestrator](https://github.com/MetaOutlaws/mar_trading_firm/blob/c04028cbcb00f3eabfafbcad8a4912bdd20aa4d3/firm/orchestrator.py), [risk engine](https://github.com/MetaOutlaws/mar_trading_firm/blob/c04028cbcb00f3eabfafbcad8a4912bdd20aa4d3/core/risk/engine.py), [approval writer](https://github.com/MetaOutlaws/mar_trading_firm/blob/c04028cbcb00f3eabfafbcad8a4912bdd20aa4d3/research/validate.py#L1589-L1655), [process lock](https://github.com/MetaOutlaws/mar_trading_firm/blob/c04028cbcb00f3eabfafbcad8a4912bdd20aa4d3/firm/locks.py), [portfolio manager](https://github.com/MetaOutlaws/mar_trading_firm/blob/c04028cbcb00f3eabfafbcad8a4912bdd20aa4d3/firm/employees/portfolio_manager.py).

The concern about searching many strategies is established in the primary research on [the probability of backtest overfitting](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf). In this repository, the search volume makes independent validation especially important; the file inventory alone does not quantify the actual false-discovery rate.

## 5. The current go-live panel is not a sufficient gate

`check_go_live.py` has several material weaknesses:

- OOS sample size sums rejected configurations as well as approved ones.
- It opens `Ledger(mode=settings.trading_mode.value)`. Under LIVE settings, the claimed paper checks read live records, potentially blocking the first legitimate live start or checking the wrong evidence.
- It has no explicit positive paper expectancy/profitability or minimum completed paper-trade gate.
- It asks for `performance['max_drawdown_pct']`, but `Ledger.performance()` does not supply that field. Missing paper drawdown is allowed through.
- “Continuous paper days” means elapsed time since the first equity snapshot, without checking gaps, uptime or strategy changes.
- Regime coverage comes from a shared report's dataset labels, not proof that the exact promoted portfolio traded enough across those regimes.
- `_weighted_pf()` actually takes the minimum sleeve PF. That is not a replayed portfolio PF. Maximum individual sleeve drawdown is likewise not portfolio drawdown.
- The kill-switch gate is hardcoded true even when the returned metadata says it is tripped. The engine still stops on a tripped switch, but the panel can misstate readiness.
- Paper slippage includes an assumed model cost; it is not independent evidence of real execution quality.

**Replacement:** a promotion artifact tied to exact code, parameters, datasets, cost model and portfolio policy; complete corrected OOS evidence; reconciled forward results; health/coverage evidence; confirmed operational failure tests; and explicit operator release. Invalidate it when material inputs change. Current approved records should be treated as candidates pending revalidation, not proof that these conditions are met.

Source: [go-live checks](https://github.com/MetaOutlaws/mar_trading_firm/blob/c04028cbcb00f3eabfafbcad8a4912bdd20aa4d3/scripts/check_go_live.py).

## 6. What the seven trades do and do not tell us

One win in seven is a 14.3% observed win rate. Under the illustrative assumptions of independent trades and a true 50% win probability, one or fewer wins occurs 6.25% of the time. Your trades may be correlated, so this is context rather than a fitted probability model.

The result deserves investigation, but does not identify whether the cause is weak alpha, a short-heavy portfolio in adverse conditions, late entries, different exits, bad state or some combination. None of those deployment-specific explanations is established without the actual records.

Profitability depends on **net expectancy**, not win rate alone:

`expectancy = win probability × average gross win − loss probability × average gross loss − average trading costs`

For illustration, 5% winners and 3% losers break even at 37.5% wins before costs; an approximate 0.31% round-trip cost raises that to 41.4%. This is not the actual strategy expectancy: timeouts, gaps, fees, funding and variable fills change the result.

The review should reconstruct every trade against three paths: the intended research execution, a corrected realistic paper replay, and the observed execution. Differences should be assigned to signal selection, latency, size, exits, costs, data and system faults. Use the result to diagnose, not to tune seven examples into seven historical winners.

## 7. Research strategy after repairs

**Reduce concurrent hypotheses and require a reason for an edge.** The repository is largely an indicator/pattern factory. Another indicator name is not necessarily an independent economic hypothesis. Group related signals by return correlation and underlying mechanism.

Start with the existing BTC/ETH 4h ATR short and SOL 1h doji short as candidates for corrected revalidation. They have stronger stored evidence than the overrides, but do not merit automatic retention. Keep override experiments in isolated shadow portfolios.

For each candidate:

1. State the mechanism, market, expected holding period, invalidation conditions and expected costs before running the test.
2. Verify closed, ordered candles; detect gaps, duplicates and malformed bars; preserve venue, symbol history, dataset timestamp and hash. Verify indicator values/signals against the runtime history length.
3. Fix OOS boundaries, then run nested chronological selection and evaluation. Freeze a final holdout that neither worker nor operator repeatedly uses for tuning. Log failed trials as well as winners.
4. Compare the strategy with matched random entries and simple direction/exposure benchmarks, using identical costs and exit rules. Correct search-wide statistical inference and use resampling that respects dependence.
5. Test parameter neighborhoods, delayed entries, worse costs, missed data and market-regime changes. Report capacity and trade frequency. Avoid choosing a single isolated optimum.
6. Replay the actual combined portfolio with symbol, sector, exposure and allocation limits. All approved candidates currently short; measure common BTC/directional exposure rather than calling BTC/ETH/SOL independent bets.
7. Freeze surviving versions for forward testing. Research, deterministic filters and AI overlays should have paired shadow comparisons on the same opportunity set. Permit an overlay only if its incremental benefit survives costs and uncertainty.

Potential additional mechanisms, once the evaluation system is trustworthy: medium-horizon trend continuation, range-conditioned mean reversion, and positioning/funding effects with timestamped data. These are research directions, not recommendations to deploy them. Do not add a long strategy merely to make the portfolio look balanced; staying flat is a valid outcome.

A minimum sample count can screen out thin evidence, but no universal number proves an edge. Size the validation sample around effect size, dispersion, dependence and regime coverage. Your existing 300-OOS-trade policy should apply to the precise release under review, not pooled rejected experiments.

## 8. How Grokbot and the workers should operate

Keep Grokbot as the coordinator around a deterministic, independently supervised trading service. The execution process should not await research or LLM calls.

| Role | Accountable output | Success measure |
|---|---|---|
| Grokbot / coordinator | Persisted tasks, owners, deadlines, dependencies and evidence links | Completed and independently accepted work, not number of messages |
| Data worker | Versioned market datasets and quality report | Reproducibility, completeness and freshness |
| Quant worker | Preregistered hypothesis and full experiment ledger | Robust incremental OOS evidence per research cost |
| Coding worker | Small patch plus regression cases | Accepted behavior with no execution parity regressions |
| Validation worker | Independent replay and promotion assessment | No leakage; reproducible results; no self-approval |
| Risk worker/service | Deterministic entry checks and exposure supervision | Limits enforced through errors, restarts and halts |
| Execution service | Durable order/fill/position state | No duplicate intents, invented fills or unexplained positions |
| Performance auditor | Reconciled P&L and counterfactual attribution | Accounting equality and explainable deviations |
| Regime/sentiment workers | Timestamped optional features/advice | Demonstrated incremental benefit over the same baseline |

Every task should carry an immutable ID, specification, base commit, input artifact IDs, expected output schema, owner, lease, heartbeat, deadline, attempt count and acceptance tests. States should include queued, running, blocked, submitted, verified and rejected. An author should not be the sole verifier of its own strategy.

Every consumed instruction needs strategy/symbol scope, issue time, expiry, author, authority level and an acknowledgement explaining whether it was applied or rejected. L1 roles are advisory by design. Do not grant extra trading authority merely because the workers currently appear inactive; first distinguish policy restrictions from broken handoffs.

## 9. Prioritized implementation backlog

These are proposed work packages, not changes already applied. Sequence by acceptance gates, not a promised date for profitability.

| Order | Work package / suggested owner | Dependencies | Acceptance criteria |
|---|---|---|---|
| 0 | Capture runtime evidence / Ops + auditor | None | Consistent database export, deployed commit, sanitized configuration, logs and worker configuration archived; seven trades identified |
| 1 | Cash, fees and funding / ledger engineer | 0 | Cash and ledger reconcile; flat/open restart cases preserve balances; all fills/costs traceable |
| 2 | Order and exit state machine / execution engineer | 0 | No phantom fills/closes; stable intent IDs; external stops settle exactly once; partial fills and uncertain acknowledgements remain tracked |
| 3 | Exit supervision and scheduling / Ops engineer | 1–2 | Halted entries and empty plans retain exit management; slow/down workers do not delay exit processing; candle-close timing is measured |
| 4 | OOS boundaries and parity / research engineer + independent validator | 0 | No warm-up trades in OOS; no duplicated fold exposure; identical event replay reconciles entry/exit/cost behavior |
| 5 | Worker action delivery and leases / orchestration engineer | 2–3 | Global sit-out works; advice expires at consumption; concurrent starts cannot own the same task/execution service |
| 6 | Approval store and release gate / risk + validation | 1–5 | Atomic approvals, immutable evidence IDs, exact portfolio coverage, correct paper ledger, paper drawdown and performance checks |
| 7 | Revalidate narrow candidate set / Quant | 4–6 | Search-adjusted, independent evidence; coherent portfolio replay; stress tests and documented rejections |
| 8 | Controlled forward experiment / auditor + Ops | 7 | Frozen versions; approved/experimental books separated; reliable P&L, coverage and overlay counterfactuals |

**Immediate direction:** preserve the current run; do not erase the losing history; suspend new strategy promotions until the OOS and accounting defects are repaired; keep existing exposure under supervision. This review has not paused or altered your running system.

## 10. Measure organization profitability

Trading P&L and business profitability need separate lines. Track trading returns net of execution costs, then subtract LLM, compute, data and infrastructure costs. The configured LLM ceiling is $200/month; actual spend was not available.

At that ceiling alone, required monthly trading P&L is equivalent to 20% of a $1,000 account, 4% of $5,000, or 2% of $10,000, before other overhead. This does not justify leverage. It means a small account can be suitable for validation while remaining economically unsuitable for running a costly organization.

For scale illustration only: 0.6% net expectancy on a $1,000 position is $6/trade. Covering $200 would require about 34 such expected-value trades before other overhead and variability. The stored strategy estimates cannot presently support that projection; the example shows why frequency, position size and worker costs must be modelled together.

The operator view should show three concise scorecards:

| Scorecard | Required measures |
|---|---|
| Reliability | Exit-monitor uptime/lag, missed signal windows, rejected/failed/filled counts, duplicate intents, reconciliation errors, advice freshness |
| Investment performance | Net expectancy and interval, average win/loss, profit factor, marked equity drawdown, turnover, exposure, regime and strategy attribution |
| Organization economics | Trading net P&L, actual LLM/compute/data costs, contribution after overhead, research cost per independently accepted hypothesis |

## 11. Verification performed

**Existing tests:** 130 passed across execution, backtest engine, risk, paper guards, validation gates and significance. This was a targeted six-module test run, not the full repository suite. No exchange order or live market experiment was performed.

**Additional offline reproductions:** all eight demonstrated the defects described, using the current implementation:

| Scenario | Observed behavior |
|---|---|
| Ledger fee completeness | Cash −$6.000; ledger −$4.998 |
| Paper restart | Cash $9,994 → $10,000 |
| Real ATR walk-forward on synthetic data | 57 of 174 reported OOS entries occurred before test start |
| Global sit-out application | Request true; no global entry gate applied |
| Kill-switch cycle | Position-management method never called |
| External exchange closure | Reconciliation halted before exit settlement |
| Failed paper close | Counted as closed with exit price zero |
| Reconciliation exception | Cycle continued with `halted=False` |

Passing unit tests establish that the tested behaviors work. They do not certify the untested lifecycle, accounting identities or OOS boundaries above. Each repair should add a regression case asserting the corrected invariant.

## 12. Evidence needed to complete the seven-trade diagnosis

Provide a consistent copy/export of `data/firm.db` from the running machine, the trading log covering the seven trades, the deployed commit, and sanitized Grokbot/worker configuration. A SQLite backup/export is preferable to copying an actively written database without its WAL state.

Also retain the runtime `approved_strategies.json`, per-job validation reports and fold trades, `last_cycle.json`, regime/positioning/sentiment snapshots and any capital resets. Do not include API keys or credentials.

With those records, the next deliverable is a trade-by-trade reconciliation and causal failure analysis. Until then, the strongest supported conclusion is: **the organization needs trustworthy execution and evidence before it can determine which strategies deserve capital.**
