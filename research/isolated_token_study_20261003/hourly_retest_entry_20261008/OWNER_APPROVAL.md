# Owner decision: approve the fixed retest challenger for PAPER

Decision received8 October2026 at20:30:58 Asia/Dubai (16:30:58UTC).
The owner explicitly approved this challenger and publication to the public
MetaOutlaws/mar_trading_firm repository,following the prepared PR99/PR101 review.

Status:OWNER-APPROVED PAPER CHALLENGER.
Identifier:hourly_compression_btc_connors_loweff_retest_v1.
Reference:hourly_compression_btc_connors_loweff_v1 immediate-entry baseline.
Approved scope:BTCUSDT,ETHUSDT,SOLUSDT;LONG andSHORT;1h source signals;
fixed60-minute retest/reclaim deadline;SL2%,TP2.5% from slipped actual fill;
no fallback,no holding timeout. Exact selection is entry_rule.py and PROTOCOL.md.
The baseline remains the comparison control. This approval is paper-only.

The owner accepts fewer,higher-quality trades and the observed small2026
opportunity-cost decline.2026 mean net per COMPLETED trade increased from
1.3411% to2.2594%;net per ORIGINAL signal fell from1.3411% to1.2552% because
unfilled signals count as zero. These are distinct denominators.

The frozen research decision remains unchanged:the all-period net-per-original-
signal continuation screen failed. No result,threshold or decision.json is
rewritten. This is an explicit owner decision after reviewing the evidence,
not a claim of independent statistical qualification or future certainty.

Approval is distinct from runtime activation. The existing cloud implementation
at3c226bca19cca1c771bcb2ed637f9ec39f74c432 implements immediate entry;the retest
state machine is currently research code. A durable minute-reclaim adapter,
restart/idempotency handling and separate paper attribution require integration
and verification before claiming the challenger scans or trades autonomously.
This publication does not change execution code,production approval config,
live-trading permissions or cloud state. No fresh activation evidence was read.
Do not merely clone the immediate-entry approval under the retest strategy name.

Authorized next research:compare these TWO FROZEN entry rules across all other
eligible downloaded tokens as data becomes accessible. Use the separate companion
protocol hourly_retest_expansion_20261008/PROTOCOL.md and TODO.md. Keep original
H-HOURLY-EXPANSION-01 unchanged. New-token research does not automatically expand
paper deployment eligibility. Preserve original BTC/ETH/SOL evidence separately.

Historical reports stating 'not approved' describe the state before this owner
message. This addendum supersedes approval status,not those historical results.
