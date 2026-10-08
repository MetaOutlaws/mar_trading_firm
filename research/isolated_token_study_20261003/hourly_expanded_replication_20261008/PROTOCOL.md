# H-HOURLY-EXPANSION-01: approved-rule additional-token replication

Prospective specification,8 October2026,BEFORE additional-token trade outcomes.
Status:PROTOCOL FROZEN; data downloading elsewhere; no new-token files inspected,
no scoring run, no deployed symbol expansion. This is a separate hypothesis from
compression_replication_20261006/PROTOCOL.md, which remains unchanged.

## Candidate and execution fixed now

Replicate exactly the current hourly entry combination: original compression,
own CRSI(3,2,100) <=90 LONG/>=10 SHORT, strict side-aligned completed BTC24 return
for EVERY new token, and extension<=1 prior Wilder ATR14 only when own pre-signal
ER24<0.30. Full definitions, arithmetic seeds, feature eligibility and timestamps
are in hourly_reserved_2026_20261008/PROTOCOL.md and its hashed entry implementations.
Both directions,1h only,SL2%,TP2.5%,no timeout. Do not use a token's later profitability
to choose thresholds, category, direction, clock or exclusion. Missing exact BTC
context blocks entry; no stale fill. Original BTC/ETH/SOL are reference assets only.

PRIMARY execution uses fill-based SL/TP, because this matches the reviewed runtime
risk-level origin; it is chosen BEFORE H-FILL-BRACKETS-01 results. Keep the conservative
research cost convention,including adverse exit slippage on stops. Quote-origin
brackets are a clearly labelled diagnostic and cannot rescue primary failure.
No automatic choice of execution model based on profitability. Later execution
audits may justify a separately versioned research model, never silent replacement.

Same next-minute entry,stop-first ambiguity,adverse gap handling,actual provided
funding,0.055% fee per side,0.10% slippage per side on ALL new tokens,0.20% stress.
Shared new-token occupancy:one/token,basket6,direction3,exit minute occupied;
simultaneous rank descending prior turnover then symbol; opposing same-token
signals skipped. Flat at each partition start,explicit boundary marks at end.
The three reference tokens are excluded from this primary basket and denominator.

## Data and eligibility: inherit the original acquisition protocol

Up to15 eligible new tokens per UTC month,union may exceed15. Use the existing
collector's historical catalog/daily turnover selection,90 days observed/listing
history,all previous30 completed daily observations,median daily turnover>=10m,
same classification rules and every exclusion recorded. Freeze catalog,monthly
membership,raw files and coverage before outcomes. No replacement of failed files
with lower-ranked winners. Audit missing bars,funding schedules/listings/delistings;
modern catalog availability is not proof of historical completeness.

Primary data2022-01-01 through2026-01-01 exclusive,with terminal funding event
included if applicable.2022–24 is historical replication;2025 is evaluation on
new assets but an already examined calendar period/hypothesis. Do not open any
additional-token2026 outcomes; future use requires a separate protocol and exposure
audit. Funding/history provenance flags from the original protocol remain binding.
If downloads are merely a convenience sample, explicitly classify results as such
and do not claim historically complete-universe confirmation.

## Two recorded hypotheses, never silently overwrite the original

A:original all-clock compression primary from6October; retain its original runner,
quote-origin execution,thresholds,2%/2.5% primary and stated qualification gate.
B:this approved hourly combination with fill-origin primary. Report A and B
separately,including failures and low support. B does not erase or relabel A.
Quote-origin B is descriptive only,not a third selection candidate. No extra
filter/stop/target families are opened after observing new-token outcomes.

For B report positive/nonpositive mean at both costs,all token/side/year cells,
stops/targets/boundaries,closed win rate,weekly clustering,concentration,leave-one-
token-out admitted-subset means and full admission/rejection evidence. Use nominal
R=net/.02,not leveraged/compounded account returns. Bootstrap common calendar weeks
across tokens together,including zero-trade weeks,1/4-week circular blocks,
10,000 draws,seeds20261007/20261010. Do not treat correlated tokens as independent.

B's strong confirmation gate inherits the original support/provenance standard:
at least100 closed2025 trades,50 entry dates,26 entry weeks,eight new tokens,
positive lower95% bounds at both costs and block lengths,positive stressed
leave-one-token-out means,and independently verified historical universe,funding
and classification coverage. Also require positive pooled2022–24 means at both
costs. Positive point evidence below this gate is reported as encouraging but
insufficient confirmation; it is not erased or forced into a negative-profit label.

MULTIPLICITY: retain A's original95% result unchanged. For any new claim that one
of the two candidate families is confirmed after examining both, additionally
require its97.5% two-sided lower bootstrap bounds >0 at both costs/block lengths
(conservative Bonferroni allowance for two candidate hypotheses). Publish both95%
and97.5% intervals for A and B; no selection among block/cost scenarios. This extra
joint screen does not rewrite A's original registered verdict or guarantee
independence from prior research. Neither strategy is promoted automatically.

## Engineering gate and handover

Before new-token scoring: verify the offline expanded-symbol entry adapter against
the original3-token frozen contexts; extend BTC confirmation logic only to accept
new symbols with the SAME strict BTC sign test. Verify independent indicators,
brackets,minute paths,costs and shared admissions. Pin the reviewed scoring code,
packages,input/universe hashes and this protocol in a run manifest before outcomes.
If audited timestamps make the declared boundary unusable, record a data-only
amendment before scoring; never shorten a window based on returns.

Production's3-token allowlist and approvals remain unchanged. Symbol expansion
requires a subsequent explicit operational review; no live/leverage permission.
Preserve raw downloads,source,all results and failed attempts. No further model
retuning follows automatically. The present turn registers this specification;
it does not implement or run the unavailable-data study.
