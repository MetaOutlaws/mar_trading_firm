# Matched costed-opportunity diagnostic: frozen supplement

6 October 2026. Authorized continuation of the pending component of PROTOCOL.md.
The primary prediction gate remains failed (0/18). This diagnostic cannot rescue
that claim or authorize an entry for deployment. No parameter search.

## Scope and matching

BTCUSDT, ETHUSDT, SOLUSDT; 5m/15m/1h completed entry candles; long and short.
2022–24 discovery and reused 2025 historical evaluation. No 2026 scoring.
Use the same verified minute candles, funding and reconstructed standalone-zone
candidates. Original individual row identity remains unproven.

Reuse the primary context_frame, discovery-only ATR volatility tertiles, matching
strata and seed 20261006. Match token, direction, clock, historical period,
calendar week, six-hour UTC block, completed 4h directional regime and ATR bin.
Exclude every original zone signal time from that cell's control pool. Require
five eligible controls; draw up to twenty without replacement per signal;
allow reuse across signals. Do not relax strata or match on eventual outcomes.

Unlike fixed-horizon diagnostics, there is no four-hour boundary exclusion:
all in-period entry times are eligible, and open opportunities are marked at
the partition end using the archived execution rule. Rebuild matches once on
that cohort, then use EXACTLY the same pairs for both SL/TP arms and cost levels.
Retain unmatched and context-missing signals with reasons. Export strata,
indicator as-of timestamps, signal/control mapping, unique controls and reuse.

## Execution and cost attribution

Two arms: 2% SL / 2.5% TP and 3% SL / 3% TP. Stops and targets are measured from
the unadjusted next-minute entry quote, exactly as in the existing engine.
Keep identical regime exits, adverse stop gaps, conservative stop-first
intrabar ordering and funding treatment. No maximum holding period.

Reuse optimize.raw_trade and base.Tape.cost unchanged. Fee is 0.055% on each
side's notional; base per-side slippage is 0.05% BTC/ETH and 0.10% SOL.
Reprice the same exits under doubled slippage, with fees and funding calculated
on the resulting fills. No order-book/liquidity model is introduced.

Simulate each opportunity independently, including signals that would be busy
in an executable strategy. This is NOT a portfolio. Cache each unique entry's
outcome per cell, arm and cost scenario, and retain the mapping to all draws.
Do not calculate or report portfolio drawdown for overlapping opportunities.
Separately apply the existing chronological scheduler to ALL original signals
solely to reconcile the 72 base-cost reference rows against reconstruction_v1.

For each signal compare its net return with the average of its controls. Each
signal has unit weight. Each control draw has weight 1/(that signal's number
of controls), so signals with larger pools do not dominate. Control profit
factor, win/loss size, stop rate and costs use those weights. Report raw draw
stop counts separately from weighted rates and effective counts; reused draws
are not additional independent trades.

Quoted return = side * (exit_quote / entry_quote - 1).
Slippage drag = quoted return minus fill-based gross return.
Net = quoted return - slippage drag - fees - funding.
Funding may be negative (a receipt). Export each component and its paired
difference, net R, holding duration, target/stop/regime/boundary reasons and
ambiguity. Stop-out rates exclude partition-boundary marks from denominators.

## Reporting and uncertainty

36 token/clock/direction/period cells x 2 arms x 2 costs =144 comparisons.
For each, show all-original-signal and matched-signal counts, unmatched reasons,
coverage, unique control times, draw reuse, matched signal and weighted control
means/PF/win rate/average win and loss/stop counts and rates/exit reasons/costs,
and paired net-return uplift. Also retain annual breakdowns and all evidence.

Use existing 10,000-draw paired calendar bootstrap at one- and four-week block
lengths on signal-entry weeks. Report ordinary 95% intervals only, explicitly
unadjusted secondary evidence. Shared controls inside a week remain together;
long overlapping holding paths and repeated historical exploration limit
interpretation. No new pass gate, parameter selection or profit claim follows
from these intervals. The failed simultaneous primary gate is unchanged.

Compare stop/target arms descriptively and in initial-stop R; both SL and TP
change, so differences cannot be attributed solely to wider stops. Preserve
negative results and every failed attempt. Freeze protocol/code before scoring,
verify all six data hashes and control reconciliation, save the full checkpoint,
and publish permitted reports/aggregates only. No cloud or approval changes.
