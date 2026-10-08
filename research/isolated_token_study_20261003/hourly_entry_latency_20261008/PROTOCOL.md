# H-ENTRY-LATENCY-01: execution delay on the approved hourly rule

Authorized 8 October 2026: proceed with the next test. Publish this protocol,
code, synthetic checks and zero-delay reconciliation before delayed outcomes.

Hypothesis: the approved hourly compression + BTC + Connors + conditional
low-efficiency extension cap retains positive mean net return when entry occurs
five minutes after its completed hourly signal. The 1- and 15-minute arms are
prespecified execution sensitivity diagnostics, not candidate strategies to rank
or deploy. Zero delay is the saved fill-origin benchmark.

## Timing evidence and scope

Pinned runtime core/execution/engine.py uses MAX_CANDLE_LATENCY=15 minutes and
rejects now > close_at + MAX_CANDLE_LATENCY. Exactly 15 minutes is accepted at
evaluation, but has no remaining processing margin. scripts/run_paper_trading.py
defaults to 900 seconds of waiting AFTER cycle/worker execution, not a guaranteed
wall-clock schedule. PAPER_EXIT_POLL_SECONDS=15 only governs the waiting loop;
worker/scan time is additional. We do not have observed production latency logs.
These constant delays are sensitivity scenarios, not measured latency estimates.
Signals missed beyond the actionable window and repeated scan/retry behavior
are not simulated. No claimed full production parity or cloud activation check.

## Frozen arms and single change

Delay minutes: 0,1,5,15. Primary delay:5. A signal at completed-hour timestamp T
normally enters at the one-minute bar open T; delayed entry uses open T+d minutes.
Use all 69 unique frozen approved raw signals (45 historical,15 evaluation,9 in
2026), not only the 65 previously admitted trades. Preserve signal_i/signal_time
as immutable identities, separate from actual entry_i/entry. Copy all entry-time
features and historical eligibility/ranks from the hashed reference. No new
signals, refreshed features, waiting-period price gate, cancellation or revalidation.
A hypothetical baseline SL/TP hit while waiting is diagnostic only and must not
cancel an entry. Skip/report a scheduled entry at or after a period endpoint.

Apply entry slippage once to the delayed open Q: E=Q*(1+s*d_slip). SL=E*(1-s*.02),
TP=E*(1+s*.025). 2% SL,2.5% TP,no timeout unchanged. Restart the path at the actual
fill minute; candles before it cannot stop or target that trade. Minute bars must
be continuous; no future/nearest-price substitution. Funding exposure starts at
actual entry. Use unchanged adverse gap fills, stop-first same-minute ambiguity,
target quote at target, and explicit endpoint mark at last close.

Fees .055% per side. Per-side slippage BTC/ETH .05%, SOL .10%; stressed doubles
slippage. Adverse exit slippage still applies to ALL exits including stops, as
in the fill-origin benchmark. Runtime's separate OHLC stop-slippage convention
and sampled exit polling are excluded from this isolated test. Funding uses the
same conservative upper-minute boundary and open-price proxy.

Independently flat periods (UTC, exclusive endpoint): historical2022-01-01 to
2025-01-01; evaluation2025-01-01 to2026-01-01; previously examined2026-01-01 to
2026-10-02 16:00. Preserve the predecessor's tape cutoffs (pre2026 for the first
two,16:00 cutoff for2026), including terminal funding semantics. All three periods
are already examined. This is no new holdout and no market regime assigned by year.

## Admissions and mandatory evidence

For every arm/cost/period, rerun admissions chronologically at actual entry time:
one position/token across sides, basket6,direction3, frozen rank then token name,
exit minute occupied. Independently replay and reconcile. Pair by original signal
identity, never by shifted entry_i. Produce:

1. All raw opportunities with original/actual timestamps, entry-price movement,
   SL/TP, exits, costs and admission flags.
2. Counterfactual outcomes on the original65 admitted signals, explicitly allowed
   to overlap and therefore not an executable portfolio.
3. Full admission replay and attribution: shared-entry net changes + newly
   admitted net - displaced baseline net equals total additive net difference.
   Additive sums are not compounded or account returns.

Report trade/closed counts, stop count/rate, targets, boundary marks, win rate,
mean net,profit factor,holding times,ambiguities,loss streak,token/side/year cells,
leave-one-token-out subsets, target-to-stop/stop-to-target transitions for raw
and baseline-admitted signals, and pre-entry baseline barrier hits. No tuning
or token exclusion from descriptive subgroup findings.

Primary point screen: 5-minute arm has nonempty closed trades and positive mean
under BOTH cost assumptions in EACH period. Show all arms regardless of result.
Mean and paired calendar-week circular-block95% intervals: blocks1/4,10,000 draws,
seeds20261007/20261010,including zero-trade weeks. Paired contrasts align weeks to
original signal timestamps. Intervals are descriptive, not corrected confirmation
after sequential research. No post-result equivalence margin or winning-delay
selection. Positive points do not establish certain profitability or scalability.

Before treatment scoring: verify restored manifests/inputs/references; synthetic
clock, zero-delay identity, pre-entry ignored barriers, LONG/SHORT delayed-fill
and first-minute tie tests, endpoint exclusion, gaps, admission timing; reconcile
zero-delay138 opportunity and130 admitted cost rows exactly. Freeze hashes and
GitHub protocol commit. During scoring independently verify every minute path,
cost row, chronology and admission attribution. Preserve attempts.

No production settings change. Next: sampled-exit audit as a separate experiment,
with achievable resolution stated (one-minute candles cannot prove 15-second
polling fills). Expanded-token protocol remains frozen; no new-token outcomes.
