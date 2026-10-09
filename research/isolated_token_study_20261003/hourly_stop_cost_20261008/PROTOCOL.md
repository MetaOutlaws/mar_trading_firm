# H-STOP-COST-01: frozen-path stop-cost reconciliation

Registered 8 October 2026, before calculating the treatment. This is an
execution-accounting audit, not a new trading signal or independent edge test.

## Question and isolated change

Does charging a second adverse exit-slippage tick on a resolved stop explain
part of the difference between our research convention and the pinned paper
execution code? Preserve all original conservative outcomes alongside the audit.

Comparator: H-EXIT-POLLING-01 results_v1, research_all_exit_slip.
Treatment: runtime_stop_fill. Stop exit fill equals the already resolved quote;
targets and endpoint marks retain their original adverse exit tick. Recalculate
exit-notional fees as .00055*(1+exit_fill/entry_fill), gross return, net return,
slippage drag and net_R. Entry fees and funding assumptions remain fixed.

Primary comparison: previously frozen one-minute observed-quote paths.
Intrabar (poll_minutes=0), five-minute and fifteen-minute paths are contextual
checks fixed in advance. No polling-speed selection. Base slippage remains
BTC/ETH .05% per side and SOL .10%; stress doubles it. For treatment stops this
slippage still affects entry fills, brackets and therefore the already frozen
path. We do not regenerate signals, paths or entry fills for either cost model.

## Invariants and data

BTCUSDT, ETHUSDT, SOLUSDT, both sides; approved
hourly_compression_btc_connors_loweff_v1, 1h, SL2%, TP2.5%, no holding timeout.
Freeze all signal IDs, entry features, quotes, timestamps, stop/target levels,
exit reasons, holding times, funding charges and admitted/rejected identities.
69 distinct raw signals; 65 admitted for each existing polling/cost combination.
The 552 raw scenario rows and 520 admitted rows are repeated scenarios, not
independent trades. Replay admission constraints to verify exact identity.

Periods, independently flat starts, UTC exclusive end:
- historical: 2022-01-01 to 2025-01-01;
- evaluation: 2025-01-01 to 2026-01-01;
- reserved_replication (historical name only): 2026-01-01 to 2026-10-02 16:00.

All periods were already inspected. No new-token data or new holdout is opened.
Verify every pinned predecessor source/input/reference/output hash and runtime
source hash before freezing this calculation. No interpolation or path rerun is
needed for a cost-only change. Previous minute-path verification is inherited.

## Predeclared reporting and checks

Report every model x path x period x cost cell: trades, stops, targets, win rate,
mean net return, mean and worst stopped return, and cost attribution. Report
paired change in mean net return and paired per-trade rows. Stops and targets
must be identical across cost models; every non-stop row must be exactly equal.
No benefit should be interpreted as improved prediction or recovered trades.

Independent scalar checks use one unit of base asset and compute cash P&L and
fees on entry and exit notionals. Verify long and short signs, adverse gaps,
funding credits/debits, zero slip, target/mark identity, and frozen runtime
function semantics. Separate verifier rebuilds aggregates and 95% circular
calendar-week bootstrap intervals, blocks1/4, 10,000 draws, seed20261006+block,
including zero-trade weeks. Intervals describe these repeatedly examined data;
a positive mechanical cost delta is not evidence of an entry edge.

No profitability optimization gate or parameter search. Acceptance is exact
accounting and path/admission invariance. Preserve every attempted output run;
publish protocol/code before calculating treatment outcomes. One planned run.

## Interpretation and subsequent work

After this audit, label runtime_stop_fill with immediate entry and fill-origin
brackets as the reconciled accounting reference for the next BTC/ETH/SOL
winner/loser diagnostic. Keep intrabar and one-minute sensitivity views visible;
neither reproduces measured production latency. Keep all-exit-slip as the
conservative comparison. Do not amend the separately frozen expanded-token
protocol's primary execution model or any previous result.

Next substantive research: entry-time winner/loser diagnostics on the reconciled
outcomes, with 2022–24 development and later periods clearly labeled already
examined checks. No entry/risk gate selected during this audit. Production code,
approvals, cloud, stop/target parameters and polling schedule remain unchanged.
Matching this one cost convention does not validate real executable prices,
funding parity, target requoting, spread, capacity or continuous exit supervision.
