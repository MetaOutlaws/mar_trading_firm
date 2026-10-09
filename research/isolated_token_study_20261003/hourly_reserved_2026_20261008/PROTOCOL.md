# H-2026-REPLICATION-01 — frozen-strategy temporal replication

Frozen before any new 2026 strategy return is calculated. Owner authorization:
8 October 2026, “ok please proceed,” following the reserved-period audit proposal.

Hypothesis: the approved hourly BTC+Connors+low-efficiency extension rule retains
positive average net return per admitted trade in the later reserved interval,
under both the established base costs and doubled slippage.

## Provenance and endpoint

This is NOT certified independent or untouched validation. Original PR92 generated
full-span future-path opportunity summaries including 2026; its findings explicitly
warn that Grok may have used 2026. The documented compression sequence stopped at
2025. A date-only inventory of 58 local ledger Parquets finds no 2026 entries.
External Grok activity and organisation-wide access cannot be ruled out.
See PRIOR_USE_AUDIT.md, DATA_AUDIT.json and prior_entry_date_inventory.csv.

Primary period: 2026-01-01 00:00 UTC inclusive through 2026-10-02 16:00 UTC exclusive.
The final eight candle hours are excluded solely because the last funding event
is at 16:00 and the inherited conservative accounting can include funding at the
exit-minute upper bound. This endpoint is chosen before feature/outcome scoring.
Use pre-2026 history for causal warm-up only; start positions flat on 1 January.
There is no maximum hold. Positions still open at the endpoint are separately
labelled boundary marks, not target/stop exits. Retain the existing terminal
funding mark proxy (last available minute open if the settlement is at the cutoff).
Raw file identity is pinned to the existing research inputs. Funding cadence is
continuous in these files; independent exchange schedule/provenance is unverified.

## Exactly one strategy

hourly_compression_btc_connors_loweff_v1, BTCUSDT/ETHUSDT/SOLUSDT, both sides, 1h.
Original compression: prior 6 TR mean / prior 60 TR median <=0.7; signal TR >=1.5
prior Wilder ATR14; volume >=1.5 prior 20-hour median; directional candle body;
own 24h return aligned (zero allowed); close beyond prior 20-hour range with close
location >=0.75 LONG or <=0.25 SHORT. Preserve inherited finite-feature eligibility.
CRSI(3,2,100) <=90 LONG / >=10 SHORT, arithmetic RSI seeds and strict prior-only rank.
ETH/SOL require same completed-hour BTC24 return strictly aligned; BTC unchanged.
ER24 uses 25 closes ending BEFORE the signal hour: absolute endpoint change divided
by sum of absolute changes; flat path zero, missing data ineligible. ER<0.30 requires
extension <=1 prior ATR beyond the prior 20-hour boundary; ER>=0.30 has no cap.
SL 2%, TP 2.5%. No RSI14/ADX addition, profit protection, delay, extra arm or retuning.

Monthly membership: >=90 observed history days and median turnover of the prior
30 completed UTC days >=10m; rank eligible symbols by descending median, then name.
One position per token across sides; basket 6 / direction 3; exit minute remains
occupied. Entry next minute open after completed signal. Stop-first intraminute
ties, adverse gaps at open, target at target quote, quote-based bracket unchanged.
Fees 0.055% per side; slippage per side BTC/ETH 0.05%, SOL 0.10%; stress doubles
slippage only. Funding and conservative exit-minute convention unchanged.

## Analysis fixed before scoring

Primary: stressed mean net trade return, counts, stop/target/boundary counts and
closed win rate. Also base costs, closed-only mean, profit factor, holding times,
ambiguous bars and maximum loss streak. Report nominal R using initial 2% stop.
Calendar-week circular block bootstrap of pooled trades: blocks 1 and 4 weeks,
10,000 draws each, existing seeds 20261007 and 20261010; include zero-trade weeks.
95% percentile intervals, cross-token calendar blocks together. These intervals
describe sampling variation, not compensation for earlier selection or prior use.
Positive point replication requires >0 mean in BOTH cost scenarios. Report whether
both interval lower bounds are >0 separately; no leverage/independence qualification.
No minimum-count threshold will be selected after observing the sample size.

Descriptive breakdowns: token, side, token×side, month, prior efficiency state;
leave-one-token-out by removing admitted rows without replacement replay. Compare
to saved 2022–24 and 2025 benchmark summaries for context, not a treatment effect.
No ranking or selecting a new configuration on 2026. Any follow-up is exploratory
on this now-open interval and must not be advertised as fresh confirmation.

## Verification and persistence

Before scoring: reproduce the approved historical opportunity/admitted ledgers
exactly from minute data; verify research vs frozen runtime entry rules. Publish
this protocol, runner and preflight results to GitHub before freezing the scoring
run. Pin code, runtime sources, raw inputs and references by SHA256. Preserve every
attempt; fail loudly, never overwrite results or silently adjust a scoring rule.

During scoring: independent Connors, ER and extension contexts; runtime full-hour
signals and rolling 850-hour decisions; minute-array barrier checks; independent
funding/fee/slippage calculation; independent admission replay; no overlapping
token positions. Save trades as plain CSV, summaries, audit, verification and a
restorable checkpoint with the living roadmap and handover updated.

Production quote sampling, fill-relative brackets and shared-account occupancy
differ from this research simulation. No runtime change or automatic activation
follows this test. The already approved PAPER configuration remains the reference;
cloud activation is not verified by this research run.
