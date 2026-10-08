# H-FILL-BRACKETS-01: isolated execution-origin audit

Owner approved 8 October 2026 10:21 Dubai. Publish this protocol and tested code
before opening any fill-based outcomes. This is execution sensitivity on previously
examined data, not new holdout validation or strategy selection.

Hypothesis: the approved hourly compression/BTC/Connors/conditional-cap strategy
retains positive mean net trade return when its 2% SL and 2.5% TP are anchored to
the slipped entry fill, matching runtime risk_levels(), rather than the entry quote.

## Single change and fixed controls

Arms: quote_brackets (saved research comparator), fill_brackets (treatment).
Entry quote Q is next-minute open after the completed hourly signal; side s is
+1 LONG/-1 SHORT; per-side slippage d is unchanged. Actual entry fill E=Q*(1+s*d).
Quote arm: SL=Q*(1-s*.02), TP=Q*(1+s*.025).
Fill arm: SL=E*(1-s*.02), TP=E*(1+s*.025).
The slipped entry is charged ONCE. Target/stop levels change with cost scenario
in the treatment, so rerun paths and admissions for each scenario separately.

Reuse every frozen approved raw opportunity, not only admitted trades: historical
45,2025 15,2026 9 =69 unique signals. Two cost scenarios =138 source opportunity
rows. Saved admitted benchmark is41/15/9 =65 trades or130 cost rows. Entry feature
values, eligibility, rank and clocks are copied from hashed approved references.
No discarded entry family or rejected filter is opened. No additional-token data
is loaded. Same original compression + CRSI<=90 LONG/>=10 SHORT + exact aligned
BTC24 confirmation for ETH/SOL + extension<=1 prior ATR only for prior ER24<.30.

Periods, independently flat at each start:
- historical:2022-01-01 through2025-01-01 exclusive;
- evaluation:2025-01-01 through2026-01-01 exclusive;
- reserved_replication:2026-01-01 through2026-10-02 16:00 UTC exclusive.
2026 has already been scored and had earlier descriptive exposure. Warm-up is
causal; no maximum hold; endpoint marks remain explicitly separate.

Keep fees0.055% each side, base per-side slippage0.05% BTC/ETH and0.10% SOL,
stress doubles slippage; funding and conservative upper-minute-bound convention
unchanged. Use the predecessor's tape cutoff for each period (pre2026 tape for
the first two,16:00 cutoff for2026), preserving terminal funding proxy semantics.
Keep one position/token across sides,basket6,direction3,rank ordering and exit
minute occupancy. Stop first on same-minute ambiguity; adverse gap at worse open;
target quote at target; terminal mark at final close. Exit slippage applies to
ALL outcomes as before, including stops. The runtime contract omits second stop
slippage on OHLC-resolved stops; that separate difference is documented, not mixed
into this one-variable audit. Quote polling and live fills are also not replicated.

## Three views, all mandatory

1. All69 raw entry opportunities under both arms/costs, with paired exit reasons,
   timestamps, bracket prices, fees/funding, net changes and admission flags.
2. Same original65 admitted entries, using treatment outcomes without readmission.
   This isolates bracket changes but may imply overlapping positions; explicitly
   counterfactual, not an executable portfolio.
3. Full chronological admission replay for both arms and each cost/period. Report
   new/displaced entries and decompose additive net change into shared-entry PnL
   changes + new-entry PnL - displaced-comparator PnL. Do not confuse sums with
   compounded account returns or mean effects when counts differ.

Report n,stop count/rate,target count,boundary marks,closed win rate,mean net,
profit factor,holding times,ambiguities,loss streak,token/side/year cells and
leave-one-token-out admitted subsets. Report target-to-stop and stop-to-target
transitions for raw opportunities AND original admitted entries. Include same-reason
price/timing changes and occupancy effects. Save plain CSVs and complete ledgers.

Primary robustness screen: treatment has nonempty closed trades and positive mean
under both costs in EACH of the three periods. Report incremental mean difference
and calendar-week paired circular block95% intervals,blocks1/4,10,000 draws,seeds
20261007/20261010,including zero-trade weeks. Also report treatment mean intervals.
No cutoff fitting, stop/target search or practical-equivalence margin selected
after results. Positive point robustness is not statistical equivalence, certified
profitability, full production parity, or a deployment change.

Before scoring: synthetic LONG/SHORT gap/tie/boundary tests,zero-slip identity,
runtime risk-level parity, and exact quote-arm reconciliation to138 opportunity/
130 admitted cost rows. Freeze raw inputs, source, runtime contract and references.
During scoring: independent minute-array path and cost checks for every row;
independent admission replay and attribution conservation. Preserve every attempt.

Paper configuration remains unchanged. Additional-token protocol is separately
frozen before new-token results, without choosing its execution model on this
test's profitability. Next execution questions are separately controlled stop-exit
slippage, scanner latency and sampled exits; actual cloud operations require logs.
