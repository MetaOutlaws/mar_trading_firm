# H-RETEST-EXPANSION-01: frozen entry head-to-head on additional tokens

Registered8 October2026 after owner paper approval of the retest challenger,
BEFORE accessing or scoring additional-token outcomes. Status:awaiting accessible,
audited downloads. No new-token outcomes were inspected in this approval turn.
This separate companion leaves H-HOURLY-EXPANSION-01 and its A/B candidates,
accounting and original qualification decisions unchanged.

## Question and two fixed arms

Does the approved60-minute breakout retest/reclaim improve net return per filled
trade on new tokens,and what happens to win rate,stop-outs and opportunities
missed? Fewer trades are acceptable to the owner. Report conditional quality
and total opportunity capture as separate outcomes;one must not hide the other.

Immediate control:hourly_compression_btc_connors_loweff_v1.
Retest challenger:hourly_compression_btc_connors_loweff_retest_v1.
Use identical causal approved source signals and monthly membership for both.
LONG+SHORT;1h source signals. Retest rule exactly hourly_retest_entry_20261008/
entry_rule.py:touch frozen prior20h boundary,strict completed-minute reclaim,
next-minute open,60-minute deadline,first valid reclaim,no fallback.
No entry-feature/threshold/token/direction/stop/target tuning after outcomes.
SL2%,TP2.5% from each actual slipped fill;no holding timeout. Waiting reserves no
capacity. Each arm receives an INDEPENDENT portfolio replay with identical
one/token,basket6,direction3 limits and exit-minute occupancy. Do not put both
arms into one competing book or add their results together as independent PnL.
Frozen monthly turnover rank and same-time conflict priority are unchanged.

Use all additional downloaded symbols that satisfy the existing historical
acquisition/membership rules. Inherit up-to15 eligible new tokens per UTC month,
90-day history,complete previous30 daily turnover observations,median>=10m,
classification filters and recorded exclusions. The union can exceed15 symbols.
Do not handpick a profitable subset or silently replace failed data. Report
all supplied symbols and why each is included/excluded. If the available files
are a convenience sample,label them accurately. Original BTC/ETH/SOL are
reference-reconciliation assets,excluded from primary new-token aggregates.
All new tokens inherit strict matching completed BTC24 direction;missing exact
BTC context blocks a signal. Existing BTC reference treatment remains unchanged.

## Windows, execution and costs

2022-01-01 through2025-01-01 exclusive:historical replication.
2025-01-01 through2026-01-01 exclusive:new-token evaluation.
Start each arm flat at partition start;mark unresolved positions at exclusive end.
Keep additional-token2026 OUTCOMES unopened for a separately specified later
replication. Preserve full downloads;2026 need not be deleted to remain unscored.
A data-only cutoff amendment is allowed before scoring if coverage requires it,
with reason and hashes;never choose a cutoff based on returns.

PRIMARY:one-minute observed-quote exits,doubled slippage,runtime_stop_fill
accounting. Fixed sensitivities:intrabar exits and base slippage. Intrabar
stop-first ambiguity/adverse gaps are unchanged. Base slippage .10% per side
for ALL new tokens;stress .20%. Fees .055% each side. Targets/marks take adverse
exit slippage;stops use the observed/gap fill without a second adverse tick.
Use provided funding from actual entry to exit,excluding the entry timestamp,
with frozen open/bar/close conventions and explicit funding provenance.
This differs from H-HOURLY-EXPANSION-01's original conservative stop cost;report
that earlier experiment separately and never relabel its primary results.
Two arms x two exit models x two slip scenarios;no model selection by outcome.

## Outputs and inference fixed in advance

Report by period,token,side and entry year,plus the pooled eligible universe:
raw signals,qualified fills,unfilled/no-reclaim/endpoint counts,admissions and
rejections,targets,STOP-LOSS counts and rates,marks,net-positive win rate,mean net
per completed trade,mean including marks,median net,profit factor and durations.
Report ALL original-signal net denominators with no-fill/reject=0,missed baseline
target winners,baseline stops avoided,entry delay,fill-price improvement,and
shared/new/displaced admission attribution. Full plain CSV ledgers and per-signal
pairs are required,including negative cells. Return sums are not account PnL.

PRIMARY comparison:retained trade quality on new-token2025,measured by stressed
mean net per admitted trade for challenger minus immediate,with boundary marks
identified separately. Opportunity-cost difference on all original signals is
co-reported even if negative. This new emphasis reflects the owner's preference;
it does NOT retrospectively change H-BREAKOUT-RETEST-ENTRY-01's failed screen.

Use paired calendar-week bootstrap across ALL tokens together,including empty
weeks,circular1/4-week blocks,10,000 draws,seeds20261007 and20261010. Align arms
on original signal week. Report95% intervals for both differences and each mean.
Show token concentration,admitted-subset leave-one-token-out means and removal
of the single largest winner. Do not treat correlated tokens as independent.
Provide full ledger replay first;label subset sensitivities as subsets.

Classification:positive point evidence if challenger stressed mean>0 and its
mean-per-trade difference>0 in BOTH2022–24 and2025. Strong statistical support
additionally requires2025 >=100 closed challenger trades,50 entry dates,
26 entry weeks,eight new tokens,positive lower95% paired mean-difference bounds
at both block lengths and both costs,positive challenger lower mean bounds,
positive stressed leave-one-token-out means,and independently verified
historical-universe,funding and classification provenance. Otherwise call the
result encouraging,unfavorable or inconclusive according to the numbers,not
'proven'. Opportunity capture is a separate explicit trade-off,not a hidden
qualification gate. Report the fraction of baseline net missed and its interval.
No wider deployment or leverage follows automatically from either classification.

## Data and engineering gates before first scoring

1. Resolve/download the supplied data;inventory symbols,timestamps,candle gaps,
   funding/listing/delisting coverage and monthly membership without outcomes.
2. Hash raw inputs,catalog,membership,source,packages and this protocol. Check
   whether another worker already ran this exact comparison to avoid duplicates.
3. Implement the offline new-token adapter using pinned rules. Independently
   verify indicator seeds/as-of timing,strict BTC matching,retest prefix causality,
   fill-origin brackets,funding and admission. Reproduce all69 existing raw signals
   and the completed3-token control/treatment ledger before new-token scoring.
4. Publish/freeze the reviewed runner BEFORE outcomes. Run once,preserve failures,
   verify paths/costs/attribution and save all reports,plain CSVs and a checkpoint.
5. Report both original protocols and this companion with exact experiment IDs.

No new-token runner is implemented by this protocol file. Readiness watch may
find data and advance these engineering gates;it must not claim a backtest ran
because downloads exist. If files are inaccessible,record the blocker and ask
for their location once. No fabricated data or unverified cloud execution.
