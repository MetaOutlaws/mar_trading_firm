# Incremental context study: non-blocking zones and daily trend

5 October 2026. Frozen before this run. Supersedes the unexecuted 108-configuration proposal for this step. User requests one variable at a time and support/resistance as context without excluding opportunities.

## Design

Three arms across BTC/ETH/SOL × 5m/15m/1h × long/short = 18 fixed cells:
- A: archived 4h EMA50/200 regime + lower-clock EMA20 reclaim.
- B: A plus the EXACT PR97 confirmed 4h structure filter. This is replication of existing evidence, not a new hypothesis. No new immediate-break invalidation rule.
- C: B plus ONE daily trend permission: last completed UTC daily close vs EMA50, with EMA50 slope over 3 completed days; above and rising for long, below and falling for short, otherwise neutral. This daily module is the only new tradable variable. Its two fixed predicates form one predefined trend definition, not separately optimized indicators. Daily swing structure is NOT added.

All arms: fixed quote stop1%, target2.5%, deterministic original 4h EMA-regime exit, original fees/slippage/funding, no holding cap, conservative intraminute/gap conventions, one position at a time within each independent cell. Daily state affects entry only, never exits. No risk/target/entry-EMA tuning, lower-timeframe pattern change or zone-based gate. No joint portfolio or account-return claim.

Periods: 2022–2024 and 2025, already used historical data; no 2026 features/outcomes. Start flat each partition, mark positions at partition boundaries including liquidation costs. Annual results group by entry-year and may include exits in later years within a partition. Same raw entry-opportunity set and outcomes across arms; permission determines accepted subsets. Keep paired opportunity comparisons separately from chronological one-position results. Newly freed capacity may create chronological trades absent from the baseline actual-trade list.

Budget: 18 NEW C configurations; 36 A/B reference replications. 3 arms ×18 cells ×2 periods ×2 costs ×2 views =432 aggregate rows. No adaptively added configurations. Baseline and B chronological counts/means must match archived PR97 rows. If reconciliation fails, stop and resolve before interpreting C.

## Non-blocking support/resistance map

Every original baseline entry opportunity is retained as one annotated row. Zone annotations never enter A/B/C permission expressions or modify fills, targets, stops or exits. Disabling annotations must leave trade IDs and returns unchanged.

Use all still-valid hourly strict pivots over a rolling 30 days, confirmed only after two subsequent completed hourly bars. At confirmation freeze a band ±0.25 completed-hour ATR14 (simple mean true range) around the pivot; no arbitrary six-zone cap. Support invalidates on completed-hour close below lower edge, resistance on close above upper edge. Distinct hourly overlap episodes after confirmation count as touches; touches are descriptive, not a calibrated strength probability. Save nearest geometrically relevant support/resistance below/above or containing current entry quote, its bounds, pivot/confirmation timestamps, age, distance in percent/ATR and touches. Do not pretend absent active levels are known liquidity.

Also record previous completed daily high/low and 20 completed-4h-bar range high/low/position as SEPARATELY LABELED references. They do not silently replace a missing pivot zone. Log distance to opposing band, whether entry is within a band, and target-room ratio descriptively. No zone overlap, age, touch, range-position or room threshold can reject an entry. A quote outside current confirmed geometry may have missing mapped support/resistance; opportunity retention remains100%.

Higher-timeframe inputs must be completed as of entry. Maps may use newly completed hourly confirmation at entry open, but no claim is made that such a level was known earlier during the just-ended trigger candle. No retrospective rejection-pattern labels.

## Comparison and uncertainty

All tables separate symbol, direction, timeframe, period/year, cost and view. Report counts, retained opportunity fraction, mean net/gross return, PF, win rate, cost components, stops/targets/regime exits, duration, boundary marks and minute-close MTM drawdown (fixed-notional additive return units). Rejecting trades is a possible consequence of B/C permissions, but NEVER of the zone map. Report accepted and rejected opportunity means without claiming randomized causality.

Primary incremental comparison is C minus B mean net/trade, separately by cell and period; B minus A is historical context. Show 2025 weekly-entry-block bootstrap intervals for C-minus-B, resampling common calendar-week blocks jointly, 5000 draws, seed20261005. Ordinary95% and Bonferroni18 intervals are descriptive: they do not remove previous historical selection or long-position dependence. No claim of fresh out-of-sample confirmation.

Pre-existing exploratory screen unchanged: >=50 completed trades, positive mean net and PF>=1.15 in each period under base cost, and positive means in both periods under doubled slippage. Do not select winning cells or tune thresholds after viewing C. A strong filter with inadequate trades is inconclusive. Preserve all18 cells, including no-trade results. Stop this stage and report before introducing another variable.

## Verification and artifacts

Verify six input hashes; hash code/imported baseline/context; test daily close availability, future perturbation, long/short mirroring, pivot confirmation/expiry/invalidation/touch episodes, one annotation per input opportunity including missing-zone cases, and no annotation influence on trade permission or price path. Replicate A/B against all72 archived base-cost configuration-period rows. Output protocol, run manifest, all comparison/year rows, annotated opportunities, local trade evidence, report and exact next decision. Findings may be saved to GitHub; detailed dataset export remains blocked pending the specific approval previously requested. No worker/live setting changes.
