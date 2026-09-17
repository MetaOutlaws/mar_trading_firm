# Board review response (draft) — 17 September 2026

Prepared for Brian Zhanda (CEO) to send the Board.

**Review under reply:** `docs/MAR_Trading_Firm_Review_2026-09-12.md`  
**Reviewed commit:** `c04028cbcb00f3eabfafbcad8a4912bdd20aa4d3`  
**This assessment HEAD:** `1c9f857b34a6019119564bb441a57a6af85691c4` (`feat/employee-floor-and-openai`)

**Method:** each finding F01–F21 and go-live §5 was re-read on **current HEAD**, not only at `c04028c`. A finding is **not** marked resolved because nearby files changed. Resolution requires the verification criterion below.

**Commits after the reviewed snapshot:** only four — PR #54 `lvn_fill_reject` (`405beef`), PR #55 `inside_bar_break_fail` (`20e4313`), PR #56 `thrust_bar_fail_reversion` (`44a6a3f`), and the review document itself (`1c9f857`). Those add sleeves and the review text. They do **not** repair execution, ledger, walk-forward, go-live, or worker-delivery paths. PR #51/#52 (regime sit-out) are **already inside** `c04028c`; F13 was written against that post-sit-out code.

**Verdict in one line:** the review’s P0 execution and measurement defects are still open on HEAD. Adopt the repair sequence. Do not adopt the proposed Grokbot worker redesign. Keep live off until Board approval after the P0 gates below. Preserve the paper trading history.

---

## 1. What the review misunderstands about Grok Bot / worker org

The review looked for a “Grokbot deployment manifest” in this repo, did not find one, and then proposed a new worker org (review §8: Data / Quant / Coding / Validation / Risk / Execution / Auditor / Regime workers, with Grokbot as a generic coordinator that might modify components).

That is the wrong picture of how this desk actually runs.

| Actual operating rule | Evidence on HEAD |
|---|---|
| **Paper only.** Default `TRADING_MODE=paper`. Live construction refuses unless `GO_LIVE_CONFIRMED=I_ACCEPT_THE_RISK`. | `config/settings.py` 50–51, 113–118; `.env.example` 6–10; `README.md` 21–22, 39–45 |
| **Live stays off** until a human paper→live gate. Coding briefs repeat “Live trading stays off.” | `config/pipeline.py` 74 (`paper_to_live` owner is `operator`); `research/coding_requests/thrust_bar_fail_reversion.md` 9; `firm/org.py` 16 |
| **No auto-advance.** Code default is fail-closed. Harvest/win must not spawn the next walk-forward. Marcus/operator Inbox `start_job(explicit=True)` is the only auto-start bypass. | `config/settings.py` 86–89 (`pipeline_auto_advance: bool = False`); `config/pipeline.py` 29–32; `firm/research_jobs.py` 778–801; `firm/continuity.py` 132–148, 253–263, 279–301; commit `3d7828a` |
| **Mukanya harvests** results; harvest does **not** authorize the next test. | `firm/continuity.py` 279–301 (`unauthorized_clock_expand` / Inbox must authorize); `firm/research_jobs.py` 781–783 |
| **Chiremba codes sleeves** (JSON templates / Cursor coding requests). Does not start walk-forward, does not edit approvals. | `firm/org.py` 73–90; coding briefs: “Do not call `mark_done` (that starts walk-forward)” |
| **Tsuro is ops** (feed, hung jobs, kill switch, LLM seats). Does not pick strategies. | `firm/org.py` 95–109 |
| **Marcus is process-only.** Inbox/operator explicit start; not a trading authority. | `config/pipeline.py` 32; `firm/research_jobs.py` 783 |
| **Munha is research** (catalog / hypothesis stamps). `research.validate` is the only approvals writer. | `firm/org.py` 111–127 |
| **Hammer is audit** (post-mortem, sleeve mismatch, closed-trade review). | `firm/org.py` 132–148 |
| **John/Eng owns the deterministic core** (risk + execution). Employees advise; they cannot raise a limit. | `firm/runtime.py` 18–20; `README.md` 8–11 |
| **Employees start at L1 Advisor.** Output influences; it does not act. | `README.md` 24; `firm/runtime.py` 18–20 |
| **Grok in this repo is optional sentiment search**, not the trading coordinator. Sentiment prefers Luke’s file snapshot. | `core/data/sentiment.py`; `docs/luke_sentiment_feed.md`; `config/settings.py` 60–62 |

The named seats (Mukanya, Chiremba, Tsuro, Marcus, Munha, Hammer, John) are the Grok Bot worker org around this repo. They are **not** supposed to appear as a Kubernetes/Grokbot manifest inside `mar_trading_firm`. Absence of that manifest is not a missing control.

**Caveat (docs drift, not a live-on switch):** `.env.example` still shows `PIPELINE_AUTO_ADVANCE=true` (line 61) and `firm/org.py` 219 still says “Tier A research auto-advances.” Those sentences contradict the fail-closed default and the hardened harvest gate. Treat them as stale template/org copy. **Need runtime evidence** that the paper box’s actual `.env` has `PIPELINE_AUTO_ADVANCE=false` (code default is false if unset).

**On “stop generating strategies”:** new families since `c04028c` are **coding-only** sleeves (Munha/Garwe stamp, no `mark_done`, no approvals edit, live off). That does not create new OOS evidence. The review is right that **walk-forward/approval evidence is currently untrustworthy**; it is wrong if it is read as “the desk is auto-promoting more strategies into the book.”

---

## 2. Classification counts (HEAD)

| Classification | IDs |
|---|---|
| **AGREE still open** | F01, F02, F03, F04, F05, F06, F07, F08, F09, F10, F11, F12, F14, F15, F16, F17, F18, F19, F20, F21, §5 |
| **AGREE still open, with a policy caveat** | F13 (paper defects still open; live/testnet sit-out bypass is explicit product policy while live is off) |
| **AGREE partially mitigated since `c04028c`** | none — no P0/P1 path was repaired after the review commit |
| **ALREADY RESOLVED since `c04028c`** | none |
| **DISAGREE** | review §8 worker-org redesign; “Grokbot may modify these components” as an in-repo gap |
| **NEED MORE EVIDENCE** | the seven paper trades (review §6/§12); deployed `.env` / commit / `data/firm.db` from the running box |

---

## 3. Finding-by-finding table

Priority labels are the review’s. Owner names are the actual org seats.

### F01 — P0: walk-forward warm-up bars can be counted as OOS trades

| | |
|---|---|
| **Classification** | **AGREE still open** |
| **HEAD evidence** | `research/walkforward.py` 309, 361–362, 398–400, 410–420. `_slice_with_warmup()` prepends 300 bars. `walk_forward()` passes that whole frame to `BacktestEngine.run()` with **no eligible-entry cutoff**. Comment at 415–416 still relies on each strategy’s `min_bars`. ATR channel `min_bars = max(ema+5, atr+40) = 54` (`core/strategy/atr_channel_breakout.py` 47). Doji `min_bars = 12` (`core/strategy/doji_star_reversal.py` 31). Default `max_holding_bars = 96` is documented as “96 × 15m = 24h” (`core/strategy/base.py` 91) which is false on 4h (16 days). Inclusive `searchsorted(..., side="right")` endpoints (419–420) still share fold boundaries. |
| **Since `c04028c`** | none |
| **Owner** | Munha (research) + Hammer (independent replay) |
| **Corrective action** | Pass an explicit `test_start` into the engine (or filter trades). Indicators may use the prefix; **no fill with `entry_time < test_start` may enter the OOS ledger**. Use half-open windows; define boundary exits and carry. Bump research version; revalidate surviving candidates. |
| **Verification** | Regression: synthetic ATR, 7 folds, **zero** OOS entries before each fold’s `test_start`; no duplicate trade identities across folds. Re-run ATR BTC/ETH 4h SHORT and doji SOL 1h SHORT under the new version and show the delta vs stored `oos_*` fields. |

### F02 — P0: paper cash resets on restart

| | |
|---|---|
| **Classification** | **AGREE still open** |
| **HEAD evidence** | `core/execution/paper.py` 80–108: `hydrate()` restores positions, **explicitly leaves cash at starting equity**. Comment 85–86 claims fees “already sit in the trade history” — they do not for open positions, and closed-trade ledger fees are incomplete (F03). `core/execution/engine.py` 1200–1202: `build_engine()` constructs a **new** `PaperBroker(starting_equity=...)` then hydrates. Existing test `tests/test_execution.py` 322–344 only asserts positions reappear, **not** cash. |
| **Since `c04028c`** | none |
| **Owner** | John / Eng |
| **Corrective action** | Persist cash (and entry fees on open positions) in a replayable event ledger. Restart with the same marks must leave cash, equity, and exposure unchanged. Do **not** wipe `data/firm.db` to “fix” this. |
| **Verification** | Round-trip then reconstruct+hydrate: cash, `realised_pnl`, `total_fees`, open qty, and ledger equity match pre-restart at identical marks. Include an **open** position with entry fee deducted. |

### F03 — P0: ledger P&L omits entry fees; paper omits funding

| | |
|---|---|
| **Classification** | **AGREE still open** |
| **HEAD evidence** | Paper deducts the entry fee from cash (`paper.py` 250–251) but `_place_order()` never stores it (`engine.py` 1118–1133). `Ledger.open_position()` (`store.py` 52–100) has **no fee field**. `Ledger.close_position()` (`store.py` 102–123) computes `net_pnl = gross_pnl - fees - funding` using only the **exit** `fees=` argument (`engine.py` 1149–1156). Paper never accrues funding (`paper.py` 11–12, no funding path). Research charges both-leg fees **and** funding (`research/engine.py` 433–442). Validation uses `DEFAULT_COSTS.for_symbol(symbol)` (`scripts/validate_strategy.py` 299–304); paper uses unscaled `DEFAULT_COSTS` (`paper.py` 64). |
| **Since `c04028c`** | none |
| **Owner** | John / Eng |
| **Corrective action** | Record entry fee, exit fee, funding, and fills as first-class events. Reconcile `cash_delta == sum(net trade P&L) − open entry fees`. Version the per-symbol cost model and use it in paper comparison runs. |
| **Verification** | Unchanged-price round trip: cash move equals ledger `net_pnl`. Holding across an 8h funding stamp in paper matches research `funding_cost` for the same window. |

### F04 — P0: paper execution does not reproduce the tested strategy

| | |
|---|---|
| **Classification** | **AGREE still open** |
| **HEAD evidence** | Research: next-bar **open**, TP/SL from **slipped fill**, `max_holding_bars`, stop fills **without** extra exit slippage (`research/engine.py` 384–425, 508–520). Runtime: TP/SL from **signal close** (`engine.py` 1011–1018), submit later at **current** price (`paper.py` 181–213), **no** `max_holding` in `_manage_open_positions` (`engine.py` 1135–1159), paper stop check is a **single sampled** `get_price` (`paper.py` 340–370), paper **does** apply exit slippage on SL (`paper.py` 206–213). One position per symbol (`paper.py` 233–234). Signal window is 15 minutes after close (`engine.py` 48, 950–955). |
| **Since `c04028c`** | none |
| **Owner** | John / Eng + Munha (contract) |
| **Corrective action** | Write one execution contract (timing, stops, expiry, fees, funding, symbol conflicts). Store strategy version, full params, timeframe, and expiry on every position. Replay the same events through research and paper. |
| **Verification** | Golden-tape test: identical candles → identical signals, fills, exits, costs, P&L between `BacktestEngine` and a paper replay broker. Assert timeout exits fire at `max_holding_bars`. |

### F05 — P0: halts disable paper position management

| | |
|---|---|
| **Classification** | **AGREE still open** (sit-out makes empty-plan exit more likely) |
| **HEAD evidence** | Kill switch returns **before** `_manage_open_positions()` (`engine.py` 823–829 vs 860). Empty plan at startup **exits the process** (`scripts/run_paper_trading.py` 160–163) after hydrate. Halted cycle **breaks** the loop (203–209). Paper sit-out can omit every entry (`engine.py` 334–375) while comments claim “Open positions are still managed” (`engine.py` 117–118) — true only if the process stays in `run_cycle`. |
| **Since `c04028c`** | none (sit-out already in reviewed commit via #51/#52) |
| **Owner** | John / Eng + Tsuro (ops) |
| **Corrective action** | Split “block entries” / “flatten” / “stop service.” Exit supervision must run during entry halt and empty scan plans. Independent tight stop poll for paper. |
| **Verification** | (1) Tripped kill switch still calls position management / `check_stops`. (2) Restart with open paper position and **zero** plan entries still monitors stops. (3) Process does not exit solely because the scan plan is empty. |

### F06 — P0: legitimate exchange exits halt before settlement

| | |
|---|---|
| **Classification** | **AGREE still open** (live/testnet path; live is off, but the bug remains) |
| **HEAD evidence** | Reconcile runs first (`engine.py` 834–857). Ledger-open / broker-missing is a discrepancy (`store.py` 372–376), trips the kill switch, **returns before** `_manage_open_positions` (860). The intended live settlement path (1161–1178) uses `broker.get_price()`, not actual exit executions. |
| **Since `c04028c`** | none |
| **Owner** | John / Eng |
| **Corrective action** | Ingest/dedupe executions → settle legitimate closes → reconcile the remainder. Unknown leftover blocks **entries** only. |
| **Verification** | Mocked server-side TP/SL: ledger closes **once** at the fill price/qty/fee; kill switch does **not** trip; a true unknown position still blocks new entries. |

### F07 — P0: failed operations can be reported as successful

| | |
|---|---|
| **Classification** | **AGREE still open** |
| **HEAD evidence** | Paper `check_stops` always forwards `close_position()` (`paper.py` 365–368). Engine closes the ledger **without** checking `result.success` (`engine.py` 1145–1158). Failed `OrderResult.fill_price` defaults to `0.0` (`core/execution/broker.py` 90). `_attempt_entry` returns the approved decision even if `_place_order` fails (`engine.py` 1072–1073); cycle increments `orders_placed` on `decision.is_approved` (888–891). Failed stops call `close_position` and **ignore** the result; no ledger row; event still says “position closed immediately” (1101–1116). |
| **Since `c04028c`** | none |
| **Owner** | John / Eng |
| **Corrective action** | Separate risk approval, ack, fill, protection, close. Metrics and ledger update only on confirmed outcomes. Failed protection → tracked recovery state, not a success event. |
| **Verification** | `success=False` close: ledger stays open, `positions_closed` stays 0, exit price 0 never written. Failed entry: `orders_placed` does not increment. Failed `set_stops`: recovery state, not “closed immediately” unless a confirmed flatten exists. |

### F08 — P0: Bybit ack treated as fill; retries lack stable identity

| | |
|---|---|
| **Classification** | **AGREE still open** (live/testnet; live is off — still must not ship) |
| **HEAD evidence** | `_resolve_fill` falls back to requested qty / reference price / **zero fee** (`bybit.py` 258–300). Parent still `success=True` (239–250). `_call` retries writes after exceptions (79–104). `place_order` params have **no** `orderLinkId` (211–221). |
| **Since `c04028c`** | none |
| **Owner** | John / Eng |
| **Corrective action** | Persist client order ID **before** submit; reconcile that ID; never invent a fill; track partial/final states; confirm leverage/margin/protection at startup. |
| **Verification** | Fill-lookup failure → order stays `unconfirmed`, not a success fill. Retry after ack uses the same `orderLinkId` (idempotent). No second live order in a lost-response fixture. |

### F09 — P0: reconciliation exceptions fail open

| | |
|---|---|
| **Classification** | **AGREE still open** |
| **HEAD evidence** | `engine.py` 835–840: exception → log, `discrepancies = []`, cycle **continues** to manage/scan. Contrast: a real discrepancy list trips the switch (842–857). |
| **Since `c04028c`** | none |
| **Owner** | John / Eng |
| **Corrective action** | Unavailable portfolio state is an **entry-blocking** state. Preserve exit recovery where possible. Never treat missing recon as clean. |
| **Verification** | Injected recon exception: `halted` or equivalent entry block is true; no new `_place_order`; stop management still attempted if the book is known. |

### F10 — P1: random-entry test mixes net strategy returns with gross random returns

| | |
|---|---|
| **Classification** | **AGREE still open** |
| **HEAD evidence** | `research/significance.py` 270–315. Comment 283–284 claims both sides ignore TP/SL. **Observed** arm uses `t.return_pct` (300) which is **net of fees/funding/TP/SL** (`research/engine.py` 442, 459). Random arm is unsigned close-to-close (309–314). No tests assert equal mechanics. |
| **Since `c04028c`** | none |
| **Owner** | Munha |
| **Corrective action** | Same simulator, costs, and exit rules on both arms — or identical timing-only returns on both. Restrict to matching eligible windows. |
| **Verification** | Fixture where strategy net ≠ gross: permutation uses the same return definition on both arms. A known no-skill series is not rejected solely because costs sit on one side. |

### F11 — P1: no search-wide multiplicity correction; IID bootstrap

| | |
|---|---|
| **Classification** | **AGREE still open** |
| **HEAD evidence** | `bootstrap_expectancy` resamples trades IID (`significance.py` 174–211). No Bonferroni/FDR/holdout/search log in `research/`. Hundreds of catalog families continue to land as coding requests. Inventory ≠ FDR, but search volume is real. |
| **Since `c04028c`** | more families (#54/#55/#56) — **coding-only**, not new WF evidence |
| **Owner** | Munha + Hammer |
| **Corrective action** | Log every experiment; freeze a final holdout; dependence-aware resampling; documented multiple-testing rule. Do not treat pooled rejected `oos_trades` as sample size (§5). |
| **Verification** | Experiment ledger lists failed trials. Holdout is untouched by grid search. Approval path refuses a candidate that only wins inside the search set. |

### F12 — P1: research regimes are retrospective; runtime regimes are a different feed

| | |
|---|---|
| **Classification** | **AGREE still open** |
| **HEAD evidence** | Research labels quarters by **full-quarter** BTC return (`research/datasets.py` 8–12, 71–120) — the quarter’s final return is not knowable intra-quarter. Runtime uses Soko/file + analyst snapshot (`core/data/soko_trend.py`). |
| **Since `c04028c`** | none on this path (#51/#52 already in reviewed commit) |
| **Owner** | Munha (causal labels) + Hammer (replay of filtered strategy) |
| **Corrective action** | Keep quarterly labels for diagnosis only. Validate a **causal** classifier (data available at decision time). Test the whole filtered strategy, not label overlap. |
| **Verification** | Causal label at time t uses only data ≤ t. Walk-forward with that filter is reported separately from retrospective buckets. |

### F13 — P1: Soko freshness, ON bypass, key mismatch, live bypass

| | |
|---|---|
| **Classification** | **AGREE still open** on paper defects. **Policy caveat:** live/testnet bypass is explicit while live is off — not an accidental hole. |
| **HEAD evidence** | No timestamp/TTL in `core/data/soko_trend.py`. `activation=ON` returns `None` and **skips** blocked/allow lists (`engine.py` 161–162). **Scan-loop** looks up `read_soko_sleeve_activation(entry.key)` where `PlanEntry.key` is `symbol:side` (130–131, 207). **build_plan** uses the full approval key (354). Live/testnet: `paper_regime_sitout_reason` returns immediately (189–191); `sit_out=False` for non-paper (335–336, 588). |
| **Since `c04028c`** | none. PR #51 (`39d834e`) / #52 (`c04028c`) are **in** the reviewed commit. |
| **Owner** | John / Eng (runtime identity + expiry) + Tsuro (feed freshness) + Munha (policy) |
| **Corrective action** | Enforce as_of/TTL + schema. One full strategy identity in both plan and scan loop. Document that `ON` is **not** a blocked-regime override unless a named authority says so. Keep live sit-out off until a causal policy is Board-approved. |
| **Verification** | Stale Soko file → fail-closed sit-out. `ON` does not clear `blocked_regimes`. Scan-loop activation uses the same key as `sleeves[].key`. Two families on one `symbol:side` do not share activation. |

### F14 — P1: `CycleAdvice.sit_out` is populated but `apply_to()` drops it

| | |
|---|---|
| **Classification** | **AGREE still open** |
| **HEAD evidence** | `firm/orchestrator.py` 133, 136–140 (`apply_to` writes vetoes/multipliers/agents only), 283–286 (global sit-out sets the flag). No test references `apply_to` / global sit-out. Agents are L1, so this is a **broken handoff**, not missing trading authority. |
| **Since `c04028c`** | none |
| **Owner** | John / Eng + Marcus (process: advice delivery) |
| **Corrective action** | Explicit global entry gate with expiry and acknowledgement. Do **not** raise L1 to veto in order to “make sit-out work.” |
| **Verification** | Empty-veto global sit-out: zero new entries, exits still managed, ack recorded, expires at consumption. |

### F15 — P1: sequential workers + sleep delay the next scan/stop check

| | |
|---|---|
| **Classification** | **AGREE still open** (employees were moved after the cycle; pipeline still blocks **this** cycle) |
| **HEAD evidence** | `scripts/run_paper_trading.py` 179–220: `advance_pipeline()` **then** `run_cycle()` **then** `orchestrator.run_due()` **then** sleep 900s. Comment at 182–184 says Gemini must not block the clock — pipeline still runs first. `CycleAdvice` is applied to the engine object until the next successful `apply_to` (190–191); TTL is on proposals (`firm/memory.py` 45, 384) not at engine consumption. Actionable window is 15 minutes (`engine.py` 48, 954–955). |
| **Since `c04028c`** | none |
| **Owner** | Tsuro (ops scheduling) + Marcus (process) |
| **Corrective action** | Trading/exit loop independent of research/LLM. Schedule around candle closes. Enforce advice TTL at consumption. Publish lag / missed-signal metrics. |
| **Verification** | Injected 10-minute pipeline/LLM delay: stop checks still meet SLA. Expired proposal cannot remain on `engine.agent_vetoes` after TTL. Missed 15-minute windows are counted. |

### F16 — P1: six consecutive losses cool down with no time bound

| | |
|---|---|
| **Classification** | **AGREE still open** |
| **HEAD evidence** | `core/risk/engine.py` 227–262: consecutive losses are a **halt** (blocks all new entries). `Ledger.consecutive_losses()` (`store.py` 256–272) is a streak over closed trades with **no clock**. Once flat, no new trade can break it. Daily loss is UTC-bounded (251–256); this path is not. Limit default 6 (`core/risk/limits.py` 68, 93). |
| **Since `c04028c`** | none |
| **Owner** | John / Eng + Marcus (documented recovery event) |
| **Corrective action** | Time- or review-bound cooldown; retain loss history; do not silently reset P&L to resume. |
| **Verification** | After 6 losses, entries blocked. After the documented bound (or Hammer/operator recovery event), entries allowed **without** deleting trades. Flat book alone does not self-heal. |

### F17 — P1: concurrent validators merge approvals JSON without a lock

| | |
|---|---|
| **Classification** | **AGREE still open** |
| **HEAD evidence** | `research/validate.py` 1626–1688: read JSON, merge, write. No file lock / version check. Default parallelism 3 (`config/settings.py` 96). Tests cover timeframe merge and paper_override keep, not concurrent writers. |
| **Since `c04028c`** | `validate.py` only gained new family registration (#54/#55/#56) — **not** a lock |
| **Owner** | Munha + Marcus (serialize commits) |
| **Corrective action** | Serialize approval commits or DB transactions with version checks. Immutable per-job reports stay. |
| **Verification** | Two parallel `write_approvals` on distinct keys: both records survive; no torn JSON. Lost-update test fails the current implementation and passes after the fix. |

### F18 — P1: PID-file lease is not atomic; split in-memory schedulers

| | |
|---|---|
| **Classification** | **AGREE still open** |
| **HEAD evidence** | `firm/locks.py` 52–63: check-then-write, not `O_EXCL`. API builds its own `Orchestrator()` (`api/app.py` 82); paper builds another (`run_paper_trading.py` 151–156). Cadence lives in `_last_run` RAM (`orchestrator.py` 161, 236–239). |
| **Since `c04028c`** | none |
| **Owner** | Tsuro + Marcus |
| **Corrective action** | Exclusive OS/DB lease for the trading process; durable worker ownership with retry/crash recovery. |
| **Verification** | Two overlapping `acquire_pidfile` starts: exactly one runs. API restart does not duplicate in-flight research jobs the paper loop already owns. |

### F19 — P1: equity snapshot is stale and mislabels P&L

| | |
|---|---|
| **Classification** | **AGREE still open** |
| **HEAD evidence** | `run_cycle` reads `equity` **before** exits/entries (`engine.py` 831–832, 860, 888) and records that value afterwards (898–905) **without** passing `unrealised_pnl` (defaults 0; `store.py` 285–307). `realised_pnl` is stored as `equity - starting_equity` (301) — includes unrealised if `get_balance()` marked the book (`paper.py` 111–118). `Ledger.performance()` has **no** `max_drawdown_pct` (429–473) — feeds §5. |
| **Since `c04028c`** | none |
| **Owner** | John / Eng |
| **Corrective action** | One coherent snapshot after fills: cash, realised, unrealised, fees, equity. Never conflate fields. |
| **Verification** | Cycle that closes a winner then opens a loser: snapshot matches post-cycle broker cash+marks; `unrealised_pnl != 0` when a position is open; `realised_pnl` equals closed-trade net, not equity−start. |

### F20 — P1: trade records omit identity; 15-minute window is not durable dedup

| | |
|---|---|
| **Classification** | **AGREE still open** |
| **HEAD evidence** | `Position` / `TradeRecord` (`core/ledger/models.py` 45–137): strategy name, no approval key, no timeframe, no param hash, no signal-bar id, no research provenance. Dedup is `now > close_at + 15min` (`engine.py` 48, 950–955). Restart inside the window can re-fire. |
| **Since `c04028c`** | none |
| **Owner** | John / Eng |
| **Corrective action** | Persist full identity + unique signal intent. Re-entry of the same bar after restart is refused. |
| **Verification** | Restart fixture inside the 15-minute window: second fill does not occur. Trade row contains approval key, timeframe, param hash, signal-bar id. |

### F21 — P1: shared symbol book; PM has no positions/correlation; full P&L attribution

| | |
|---|---|
| **Classification** | **AGREE still open** (PM is correctly advisory; the measurement gap is real) |
| **HEAD evidence** | One position per symbol (`paper.py` 233–234). Scan order decides who gets the slot. PM `gather()` sends approvals, regime, sentiment, pending risk — **not** open positions or a correlation matrix (`firm/employees/portfolio_manager.py` 56–70). `attribution_by_agent` adds **full** `net_pnl` to every contributing agent (`store.py` 475–503). Overrides share the paper book (`config/pipeline.py` 53–56 emptied `PAPER_SCAN_SLEEVES`; blotter is approved + `paper_override`). |
| **Since `c04028c`** | none on this path |
| **Owner** | Hammer (attribution) + Munha (conflict policy) + Marcus (keep experimental books separate) |
| **Corrective action** | Replay a shared portfolio; explicit conflict allocation; paired counterfactuals for overlay value. Keep override/experimental books separate. Do not promote PM above L1 to “fix” this. |
| **Verification** | Two approved sleeves, one symbol: documented winner of the slot; shadow P&L for the loser. Attribution does not double-count the same dollar. Override trades are excluded from the validated-portfolio scorecard. |

---

## 4. Go-live §5 — still not a sufficient gate

**Classification: AGREE still open.** Source on HEAD: `scripts/check_go_live.py` (unchanged since `c04028c`).

| Review claim | HEAD evidence | Still true? |
|---|---|---|
| OOS sample sums rejected + approved | 47–54: `sum(v.get("oos_trades") for v in approvals.values())` with no `approved` filter | Yes |
| Ledger opened in `settings.trading_mode` | 40: `Ledger(mode=settings.trading_mode.value)` | Yes. Under LIVE this would read live rows, not paper. |
| No paper expectancy / min completed paper trades | Gates list 47–169: no such gate | Yes |
| Asks for `performance['max_drawdown_pct']` which does not exist | 93–97 vs `store.py` 456–473; `paper_dd is None` is allowed through | Yes |
| “Continuous paper days” = elapsed since first snapshot | 210–224 | Yes. No gap/uptime/strategy-change check. |
| Regime coverage from a shared report, not the promoted portfolio | 189–197: `research/artifacts/validation_report.json` | Yes |
| `_weighted_pf` is min sleeve PF | 200–207 | Yes |
| Kill-switch gate hardcoded `True` | 132–141, even records `tripped` | Yes |
| Paper slippage is the model, not independent execution quality | 118–129 vs paper `DEFAULT_COSTS` | Yes |

**Owner:** Hammer (gate definition) + Marcus (process: this script must not be allowed to print READY) + John (paper ledger mode).

**Corrective action:** replacement promotion artifact tied to exact code, params, dataset hashes, cost model, and portfolio policy. Paper checks **always** read `mode=paper`. Invalidate on material input change. Current `approved: true` rows (ATR BTC/ETH 4h SHORT, doji SOL 1h SHORT) stay **candidates pending revalidation**. Header `_verdict` is still `REJECTED` while those rows are approved (`config/approved_strategies.json` 1–4) — documentation drift, not a live unlock.

**Verification:** unit tests for each bullet: rejected OOS trades do not count; LIVE settings still evaluate the paper ledger; missing `max_drawdown_pct` **fails** the gate; tripped kill switch **fails** the gate; min completed paper trades and net paper expectancy are required. `evaluate_gates()["ready"]` is false on today’s committed data.

**Inventory check (still matches the review):** 3 `approved: true` (all SHORT) and 4 `paper_override: true`. No approved LONG. Do not pool overrides into a validated portfolio.

---

## 5. What to RETAIN vs ADOPT from the recovery plan

### Retain (already policy, or correct advice)

- Keep **live off** until Board approval after P0 repairs. Paper→live remains a human gate.
- **Preserve the current paper run and SQLite history.** Do not reset cash by wiping `data/firm.db`. Do not “fix” F02 by starting a new ledger.
- Treat stored `oos_*` and the three approved rows as **candidates**, not proof.
- Keep override/experimental sleeves on a **separate scorecard**.
- Keep employees **L1 / advisory**. Do not grant extra trading authority because sit-out/advice handoffs are broken (F14).
- Keep **PIPELINE_AUTO_ADVANCE fail-closed**. Mukanya harvest must not auto-expand. Marcus/Inbox explicit start only.
- Keep coding-only sleeve work (Chiremba) from calling `mark_done` / writing approvals.
- Keep Grok Bot as coordinator of **named seats** around a deterministic core — not as something that places orders.
- Capture runtime evidence before more diagnosis of the seven trades (review §12): `data/firm.db` (+ WAL), trading log, deployed commit, sanitized `.env` (no keys), `approved_strategies.json`, `last_cycle.json`, Soko/sentiment snapshots.

### Adopt (repair the measurement/execution system)

- Work packages 1–4 and 6 in review §9, mapped to actual owners (see §6 below): cash/fees/funding; order/exit state machine; exit supervision under halt; OOS boundary + research/paper parity; honest promotion gate.
- Revalidate the **narrow** candidate set (ATR BTC/ETH 4h SHORT, doji SOL 1h SHORT) only after F01/F04 are proven.
- Three operator scorecards (reliability / investment / organization economics) — useful, and they match Hammer + Tsuro + Brian.
- Do not tune seven paper trades into seven historical winners.

### Do not adopt (wrong org / wrong implication)

- Review §8’s generic Data/Quant/Coding/Validation worker chart. We already have Mukanya / Chiremba / Tsuro / Marcus / Munha / Hammer / John.
- Treating “no Grokbot manifest in repo” as a control gap.
- Turning Grok sentiment search into a trading input with authority.
- Enabling auto-advance to “keep slots full” (`firm/org.py` copy, `.env.example`).
- Pausing **coding-only** sleeve registration as if it were approval. Pause **walk-forward promotion and paper-book expansion** until P0 repairs land.
- Adding a long sleeve “for balance.” Staying flat is valid.
- Using this review as permission to flatten, reset the paper account, or go live.

---

## 6. P0 repair order (live off, history preserved)

Sequence is acceptance gates, not a calendar. Live remains off at every step.

| Order | Package | Owner | Unblocks | Acceptance (must pass before the next step) |
|---|---|---|---|---|
| 0 | **Archive, don’t erase.** Export `firm.db` + WAL, logs, deployed commit, sanitized config. Identify the seven trades if present. | Tsuro + Hammer | All later diagnosis | Byte-stable backup; seven trades labeled or documented missing; no DROP/truncate of `trades` / `positions` / `equity_snapshots`. |
| 1 | **Exit supervision under halt / empty plan** (F05, overlap F15 stop path) | John + Tsuro | Existing paper book is safe while we repair | Tests: kill switch and empty plan still run `check_stops`; process does not exit with open paper positions. |
| 2 | **Cash, fees, funding ledger** (F02, F03, F19 snapshot fields) | John | Trustworthy paper P&L | Restart invariance; cash == ledger identity; entry fees on open positions; funding events. |
| 3 | **Order / exit / recon state machine** (F07, F06, F09, F08) | John | No phantom fills/closes | Failed close ≠ ledger close; recon exception blocks entries; external close settles once (even though live is off, the code path must be correct). |
| 4 | **OOS boundaries + execution contract** (F01, F04) | Munha + John + Hammer | Honest candidate evidence | Zero warm-up OOS entries; research/paper golden tape; then **revalidate** ATR/doji only. |
| 5 | **Promotion gate** (§5, F17 serialize) | Hammer + Marcus + Munha | Cannot print READY by accident | Paper ledger always; rejected OOS excluded; missing DD fails; tripped KS fails; min paper trades + expectancy. |
| 6 | **Advice / cooldown / identity / allocation measurement** (F13–F16, F18, F20, F21, F10–F12) | Mixed (see table) | After P0, not instead of it | Per-finding verification above. Global sit-out (F14) should be pulled forward if the desk needs a working “everyone flat” switch. |

**Explicit non-goals until Board approval:** `TRADING_MODE=live`, `GO_LIVE_CONFIRMED`, Bybit live keys, pooling overrides with approved sleeves, auto-advance on, wiping paper history, promoting any employee above L1.

---

## 7. Evidence still needed (does not block P0 engineering)

From the running paper box, not from git:

1. `data/firm.db` backup including WAL.
2. Trading log covering the reported seven trades.
3. Deployed commit SHA vs this HEAD (`1c9f857`).
4. Sanitized `.env`: `TRADING_MODE`, `PIPELINE_AUTO_ADVANCE`, `GO_LIVE_CONFIRMED` empty, no keys.
5. Runtime `approved_strategies.json`, `last_cycle.json`, Soko/sentiment files.

Until those arrive, the seven-trade story stays **user-reported**. Code on HEAD is sufficient to say the measurement and execution system is not yet trustworthy — which is the review’s strongest supported conclusion, and this response agrees with it.

---

*Draft for Brian. Not a code change. Not a go-live recommendation.*
