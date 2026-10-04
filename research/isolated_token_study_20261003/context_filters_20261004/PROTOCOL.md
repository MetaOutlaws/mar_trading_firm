# Structure and zone ablation protocol
Frozen 2026-10-04 before new context outcomes. User authorizes a professional, fully reported market-context study. This is exploratory research, not live deployment. The completed regime_target_20261004 study remains the baseline, including its negative results. New results cannot erase prior attempts.

## Comparison and budget
Use the exact baseline EMA-reclaim entries, target distances, 1% quote-based stop, no holding-time limit, fee/slippage/funding assumptions and two exit policies. Entry clocks 5m/15m/60m; tokens BTC/ETH/SOL; separate long/short; targets1/1.5/2/2.5/3%. Baseline4h EMA50/EMA200 regime remains required for every entry.

Compare four entry-permission variants: baseline; structure only; zones only; both. This adds 3×180=540 configurations to the already completed180, a total720. Two periods (2022–2024 discovery, reused2025 validation), two costs, two views (paired identical opportunities versus chronological one-position) produce5760 aggregate rows. All rows remain visible, including no-trade/insufficient-sample outcomes. No 2026 strategy outcomes. No threshold changes after results.

Context filters affect ENTRY only. Existing regime-exit policy remains the same EMA regime invalidation. This isolates added context without simultaneously changing exit management. No claim that an AI reviewer or structural-break exit has been tested.

## Confirmed structure (4h)
Use complete left-closed/right-labelled4h bars. Pivot high at bar k is strictly above highs of k-2,k-1,k+1,k+2; pivot low strictly below the analogous lows. Ties are not pivots. The pivot becomes known only when bar k+2 completes; never place its information at k. Keep last two confirmed highs and last two confirmed lows. Bullish structure requires both most recent high>previous high AND most recent low>previous low. Bearish requires both lower. Otherwise neutral. Persist current state until confirmed pivots update it. Require aligned structure at entry (bull for long, bear for short); do not infer future breaks.

## Candle-based zones (1h)
Zones are proxies for historical support/resistance, NOT observed order-book supply or demand. Identify strict two-bars-each-side pivots on completed1h candles, confirmed at k+2. Compute ATR14 as simple mean true range at the pivot bar, using only data then available. Zone bounds=center±0.25×ATR14 where center is pivot low for demand/support and pivot high for supply/resistance. Omit nonfinite ATR. No alternative width/lookback.

Maintain at most six most recently confirmed active zones of each type, preserving separate overlapping zones (no tuned clustering). Invalidate demand after a later completed hourly close strictly below lower bound; invalidate supply after close strictly above upper bound. At initial confirmation, also reject a zone if that confirmation close is already beyond its invalidation bound. Expire30 calendar days after confirmation. A broken zone is discarded, not automatically flipped. Repeated touches do not increase confidence.

At decision T, use only the latest completed hourly zone state, and expire zones whose age exceeds30d at T. For a long zone entry, the just-completed ENTRY-TIMEFRAME candle must overlap an active demand zone, close strictly above its upper bound, and close>open. Its next-minute entry quote must also be above that upper bound. Short is the inverse at active supply, close below lower bound and close<open, quote below lower bound. If multiple candidates match, choose nearest by distance from entry quote to the relevant zone edge, ties by most recent confirmation.

Room-to-target gate, included in zones and both: reject long when any active supply band intersects [entry_quote,target_quote]; reject short when any active demand band intersects [target_quote,entry_quote]. A band overlapping the entry also blocks the trade. If no opposing active zone intersects that interval, pass. No projection of future zones. Room is evaluated separately per target so retention can differ with target. Log chosen zone bounds, pivot/confirmation times, matched-zone flag, blocking opposite bounds if any, structure state and acceptance flags for every original opportunity.

## Controls and execution
Same exact baseline opportunities and completed-candle clocks; no new pattern discovery or resampling of entries. Same target/stop outcomes per retained paired entry. Chronological admission can differ because filtering frees or consumes time. Report selection effects rather than implying random assignment or causal proof.

Cache fingerprints and baseline parameter/source hashes verified. Import only offline analysis functions; no production module. Reconstruct the original180 summaries using the same immutable raw baseline and report consistency checks. Structure/zone features computed without2026 bars. Live Grokbot state is not inspected or changed.

## Reporting and screens
Report all four variants by token/timeframe: tested counts, retained-signal fraction, trade count, mean net, PF, win rate, mark-to-market drawdown in unit-notional units, typical/max hold, fees/funding, exposure, boundary marks, and pass counts. Targets shown separately. Report discovery-selected settings and all2025-positive exceptions without calling the latter validated winners.

Screen unchanged: >=50 completed chronological trades in EACH period, mean>0 and PF>=1.15 in both, positive doubled-slippage means in both. Adjacent target stability requires >=2 neighboring targets passing within the same token/clock/side/exit/filter. Any passes are exploratory. For passes calculate2025 weekly-block intervals, with adjustment for720 total configurations; long holds and historical selection limit inference. No candidate promoted here. Report fewer-than50 cases as insufficient evidence even if positive.

Publish an executive report with clean tables, full machine-readable results, acceptance/rejection audit and trade-evidence exports, source/input hashes, test log and reproduction command. Distinguish genuine numerical results, assumptions and proposed next experiments.

## Required tests
Pivot confirmation lag, no lookahead under future perturbations, strict-tie handling, structure direction, zone creation/bounds/invalidation/expiry, rejection-candle geometry, opposing-zone blockage for long/short, target-dependent retention, no-trade rows, and unchanged baseline execution. Reuse the independently tested no-time-limit engine. Stop at the fixed budget.
