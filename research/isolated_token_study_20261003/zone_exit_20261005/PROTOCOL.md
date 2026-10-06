# Frozen zone-aware exit experiment

5 October 2026. Authorized by Brian. Freeze before viewing outcomes. Evaluate the same exit under immediate, fixed-delay, then zone-timed entries; preserve every cell and no retuning between stages.

## Single intervention

At the ACTUAL entry minute open use only completed hourly zone snapshots from the existing non-blocking map. Long: nearest active resistance band wholly ahead of quote entry, target its lower edge. Short: nearest active support band wholly below quote entry, target its upper edge. If no such edge is strictly between entry and the original 2.5% target, retain the original target. Overlapping/behind-entry bands are unsuitable for a profit target. Freeze this target for the position; do not subsequently move it. No extra cost-distance threshold or buffer is tuned. Very close targets can lose after fees and slippage and must remain visible.

Keep original signal, entry scheduling (including six-bar fallback), 1% initial stop, completed 4h regime-reversal exit, execution priority, taker fees, slippage and funding identical. The target percentage is measured from quote entry, matching the baseline. No maximum holding period, daily filter, new structure filter, trailing stop, maker fills or 2026 outcomes.

## Comparisons

3 entry policies × 18 token/side/timeframe cells × 2 exit arms × 2 historical partitions × 2 cost cases × 2 views = 864 result rows. There are 54 new exit-policy cells, not 864 independent hypotheses. Reused 2022–2024 and 2025 remain exploratory. Run all stages regardless of an intermediate result.

Recompute chronological single-position schedules for both exit arms, including pending entry capacity. Also evaluate every original candidate independently (overlapping, diagnostic only). On the exact set of baseline executed entries measure zone-minus-original outcomes: gains protected, continuation missed, average delta and changed-target frequency. This matched-entry diagnostic isolates exit economics from changes to subsequent capacity; it is not an independently tradable book.

For all cells report count, mean net return, win rate, PF, fixed-notional additive minute-close drawdown, cost components, holding time, boundary valuations and annual outcomes. Slippage is doubled for stress. Same exploratory screen: at least 50 completed positions in each partition, positive means and PF at least 1.15 in both base cases, positive means in both stressed cases. No production certification. Preserve failures.

## Validation and publication

Verify prior artifacts, source and six market hashes. Replicate all 432 prior entry-policy/period/cost/view rows. Synthetic checks cover target side, nearest eligible edge, missing/overlapping/outside target fallback, future independence of zone map, exact barrier execution and stop-first ambiguity.

Save scripts, complete outcomes and detailed evidence locally in the git-backed project. Publish only written protocol/findings and aggregate report tables to PR #98 within the existing publication scope. No messages to Grokbot, no live or worker changes.
