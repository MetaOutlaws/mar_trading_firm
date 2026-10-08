# H-BREAKOUT-RETEST-ENTRY-01

Registered 8 October 2026 before treatment selection or outcome scoring.
Hypothesis: a completed breakout retest and reclaim can improve entry quality
enough to offset winners missed while waiting. This is one rule, not a grid.

## Frozen control and treatment

Use the exact 69 approved hourly_compression_btc_connors_loweff_v1 raw signals
from H-STOP-COST-01: BTC/ETH/SOL, both directions, 45/15/9 raw signals in
2022–24 /2025 /2026 through 2 October 16:00 UTC. All periods have already been
examined; this is exploratory, not independent validation. Immediate entry
at the next minute open after the signal hour is the control (65 admitted).

For each signal at T, freeze its prior20h breakout boundary B. Exclude the
signal hour from that boundary. For LONG, a completed minute low <= B arms
the retest; a subsequent completed minute close > B confirms the reclaim.
For SHORT, high >= B arms it and close < B confirms it. Touch and reclaim
may occur in the same completed minute: the close follows that minute's touch.
The armed state persists through the entry deadline. Equality counts as touch
but never as reclaim. A gap through the boundary is allowed. No new volume,
body, RSI or regime predicate is applied during this waiting period.

Inspect minute candles starting T through T+59m. Enter at the next minute open
after the FIRST confirmed reclaim, hence T+1m through T+60m inclusive. The
fill must be strictly before the partition endpoint. No retest or no reclaim
means no trade; there is no fallback. Report partial-window endpoint censorship
separately. Do not cancel on hypothetical immediate-entry SL/TP events.
The one-hour entry deadline comes from the signal timeframe, not outcome tuning.
It is not a holding timeout: there is still no maximum holding duration.

Keep original signal membership, monthly rank and entry features frozen.
Pending signals do not reserve capacity. Replay all qualified fills at their
actual fill times: one position/token, basket6, direction3, exit minute occupied,
same frozen conflict and rank ordering. No later replacement entry after an
occupancy rejection. Preserve every unfilled and rejected raw signal.

SL2% and TP2.5% measured from actual slipped entry fill. Primary: one-minute
sampled quote exits, first sample strictly after actual entry. Fixed sensitivity:
intrabar exits with conservative stop-first ties and adverse gap stops.
Base and doubled slippage: BTC/ETH .05%, SOL .10% per side before doubling.
Fees .055% each side. Reconciled runtime_stop_fill convention: stop fill uses
its observed/gap quote without a second adverse exit tick; target/mark exits
retain adverse exit slippage. Funding uses actual delayed entry, excludes the
entry timestamp, and retains predecessor open/bar/close exit conventions.
No change to the separately frozen expanded-token accounting protocol.

Periods start flat and end exclusively: 2022-01-01 to2025-01-01;
2025-01-01 to2026-01-01;2026-01-01 to2026-10-02 16:00 UTC.
Earlier partitions retain the pre2026 tape; the last retains its exact cutoff.

## Evidence and predeclared decision

Report raw signals, qualified fills, unfilled reasons, admissions/rejections,
stops/targets/marks, win rate and net return per admitted trade. Also report
net sum divided by ALL original raw signals, counting no-fill and rejects as
zero. This fixed opportunity denominator prevents selection-only improvement.
Return sums are additive trade statistics, not account portfolio PnL.

Show baseline winners missed and baseline stops avoided due to no-fill and
occupancy separately. Match original admitted signals with no-fill=0 as a
clearly labeled counterfactual. Decompose full ledger change into shared-trade
return changes + newly admitted returns - removed baseline returns. Include
delay, side-adjusted fill-price improvement (negative means worse), changed
outcomes, fees/funding, token/side strata and all per-signal/per-trade rows.

Circular calendar-week paired bootstrap,1/4-week blocks,10,000 draws,
seeds20261006+block; include empty weeks. For net per original signal use the
resampled original raw signal count, including unfilled/rejected observations.
Align both arms on ORIGINAL signal week. Report intervals without claiming
multiple-testing-adjusted significance or a fresh holdout.

The single primary continuation screen requires, in EACH of the three periods:
at least one completed treatment trade, positive treatment mean net under
doubled costs with one-minute sampled exits, and strictly positive improvement
in net per original raw signal. Report base-cost and intrabar sensitivities;
do not promote another model if primary fails. Passing is only a lead for
new-token/prospective validation, never automatic deployment or certainty.
No revised deadline, fallback, token exclusion or secondary rule is selected
from these outcomes. Preserve negative evidence and leave approved paper
configuration unchanged. No live orders, leverage or cloud mutation.

## Verification and publication

Before treatment scoring, verify all source/input/reference/runtime hashes,
rebuild the 276 baseline raw paths/costs and replay 260 baseline admissions.
Independently rebuild 69 breakout boundaries and validate the signal close.
Intended registration was GitHub protocol publication before treatment.
Automatic approval review blocked that publication twice, including after
repository/branch verification and removing the per-signal CSV. The exact
public destination/payload requires user confirmation. See PUBLICATION_EXCEPTION.md.
Before ANY treatment scoring, freeze local source/input/reference hashes and
protocol SHA256 with a UTC timestamp; protocol_commit remains null. Preserve
this distinction: the test is locally preregistered, not GitHub-preregistered.
Complete the authorized local research and prepare publication for final approval.
Check each real retest selection with a separate sequential state machine,
and prefix/future perturbation checks; independently verify every new path,
cost and admission replay. Independently rebuild reporting and bootstrap
intervals from saved evidence. Preserve every attempt, including failures.
Publish findings, updated research handover, plain CSVs and a cumulative
restore-verified checkpoint. Production implementation remains unchanged.
