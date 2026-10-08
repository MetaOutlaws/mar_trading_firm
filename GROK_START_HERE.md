# Grok: current research and paper approval, 8 October 2026

Current approved PAPER strategy: hourly_compression_btc_connors_loweff_v1.
BTC/ETH/SOL, both directions, hourly. Original compression + Connors + BTC
confirmation, with a one-ATR extension cap only when pre-signal ER24<0.30.
SL2%, TP2.5%, no maximum hold. No RSI14 or ADX addition. No runtime rule changed
in this research update; this document does not verify cloud activation.

H-2026-REPLICATION-01 is complete. Frozen rule tested from 1 January through
2 October 2026 16:00 UTC exclusive: 9 trades, 8 targets, 1 stop (11.11%),
88.89% win rate; mean net +1.7240% base / +1.5689% doubled slippage.
Earlier stressed means: 2022–24 +0.5003% (41 trades/15 stops), 2025 +1.1993%
(15 trades/3 stops). All three tokens positive in2026; ETH has just one trade.

The four-week-block95% interval is −0.1300% to +2.0857%, so the stronger uncertainty
check does not pass. This is positive temporal replication, not an untouched
holdout: earlier descriptive2026 market outcomes were exposed, and outside-worker
use is unknown. No certainty, independent-edge or leverage qualification is claimed.

Research source: [PR99](https://github.com/MetaOutlaws/mar_trading_firm/pull/99),
research/isolated_token_study_20261003/hourly_reserved_2026_20261008/.
Read FINDINGS.md, PROTOCOL.md, PRIOR_USE_AUDIT.md and results_v1.
Protocol was published and verified before scoring; historical preflight reproduced
all56 previously approved trades across two cost assumptions. New-run contexts,
runtime signals, minute paths, costs, admissions and bootstrap reports were checked.
The results CSV contains18 rows representing9 trades at two cost settings.

Runtime source: [PR101](https://github.com/MetaOutlaws/mar_trading_firm/pull/101).
Retain the owner-approved rule and existing reviewed deployment procedure in
HOURLY_LOWEFF_APPROVAL.md. Do not treat publication as proof of installation or
scanning. Do not enable duplicate older hourly variants or change existing exits.

Next: obtain actual paper cycle/signal/fill evidence and collect forward observations
with the frozen rule. Run the preregistered broader-token replication when data
arrive. Further tuning on2026 is exploratory. No background monitor was started.

Recovery: original MAR_hourly_compression_checkpoint_20261007.zip followed by
MAR_2026_replication_checkpoint_20261008.zip; raw inputs remain separate.
The complete operational handover and older checkpoint upload instructions remain
in the owner's private checkpoint. This public handover contains research only.
