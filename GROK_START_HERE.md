# Grok: fill-price research audit and current paper rule,8 October2026

## Latest research: entry latency completed, 8 October 2026

H-ENTRY-LATENCY-01 tested 0,1,5,15-minute fills with the same approved signals,
fill-origin SL2%/TP2.5%, fees, funding and slippage. Five minutes was the primary
comparison frozen before outcomes. All delays retain positive pooled means at
both costs in every period, but recent-period expectancy weakens.

Doubled-slippage results, immediate -> five minutes:
- 2022–24:41 trades, mean +0.0702% -> +0.2947%, stops20 ->18.
- 2025:15 trades, mean +1.0412% -> +0.4414%, stops4 ->6.
- 2026 Jan–2 Oct:9 trades, mean +1.7240% -> +1.2216%, stops1 ->2.

The same65 signals remain admitted in all arms/costs. No deliberate delay is
approved. Every delayed-arm four-week95% mean interval includes zero. These are
reused-data sensitivity results, not new independent confirmation or leverage evidence.
40 tests passed;552 paths/cost rows and24 admission replays verified;576 report
rows and156 bootstrap intervals independently rebuilt. One treatment run.

Runtime code accepts signals until15 minutes after close and waits900 seconds
after scan/worker execution by default. This is not a guaranteed15-minute elapsed
cycle. The15-second exit poll applies within the waiting loop; no observed cloud
latency or continuous supervision claim follows from the constant alone.

Current PAPER rule remains hourly_compression_btc_connors_loweff_v1, BTC/ETH/SOL
LONG+SHORT,1h,2% SL/2.5% TP,no timeout. Implementation unchanged at
3c226bca19cca1c771bcb2ed637f9ec39f74c432. This commit changes documentation only.
Next isolated study: sampled exit supervision, with minute-data limitations stated.
Keep entry latency and the separate OHLC stop-slippage convention out of that
one-variable comparison. Expanded-token protocol remains frozen; no new-token
outcomes were opened.

Research results:commit 52f0a70a175bae3427163e0ef1c7e50ca0121f52, PR99,
research/isolated_token_study_20261003/hourly_entry_latency_20261008/FINDINGS.md.
Protocol-before-outcomes:4d1792891682b7570ee1c3a799defb988b1df72a.
Newest cumulative archive:MAR_entry_latency_checkpoint_20261008.zip;restore over
the original MAR_hourly_compression_checkpoint_20261007.zip and verify its latest
manifest. Per-trade evidence and complete private operational handover are saved
with the checkpoint. Earlier sections below are historical.

Approved PAPER strategy remains hourly_compression_btc_connors_loweff_v1:
BTC/ETH/SOL,both sides,1h,SL2%/TP2.5%,no timeout. Original compression + Connors +
BTC confirmation + one-ATR extension cap only when pre-signal ER24<0.30.
No runtime or approval change. Actual installation/scanning is not verified here.

Latest H-FILL-BRACKETS-01 audit aligns research bracket origin with the slipped
entry fill already used by runtime. Stressed mean returns:2022–24 +0.0702%
(41 trades,20 stops,21 targets);2025 +1.0412%(15,4,11);2026 +1.7240%(9,1,8).
Old quote-origin means were+0.5003%,+1.1993%,+1.5689% respectively. Five historical
winners and one2025 winner become stops;no admission identities change. Historical
ETH is negative. Positive pooled point results remain,but historical margin is thin
and uncertainty/earlier selection prevent a certainty claim. No retuning followed.

Read [PR99](https://github.com/MetaOutlaws/mar_trading_firm/pull/99),
research/isolated_token_study_20261003/hourly_fill_brackets_20261008/FINDINGS.md
and PROTOCOL.md.25 tests,276 paths/cost/risk-level checks,12 admissions,6 attributions,
and48 independently reconstructed intervals pass.260 rows are65 overlapping trades
under two arms/two costs. Prior evidence is preserved.2026 is already examined.

New-token protocol is frozen in hourly_expanded_replication_20261008/PROTOCOL.md.
It adds this exact hourly candidate alongside the preserved original all-clock
study;primary fill-origin brackets were chosen before this audit's results.
No new-token data were inspected and no new-token runner has been implemented.
Freeze and verify acquisition coverage and scoring code before opening outcomes.

Next research: scanner latency and sampled exits,separately from the stop-exit
slippage convention. Use real operational evidence when available;minute-data
proxies do not establish full production parity. Winner/loss diagnosis should use
the fill-origin results (25 stops/40 targets),not only the old quote-based ledger.

Runtime [PR101](https://github.com/MetaOutlaws/mar_trading_firm/pull/101) and its
reviewed HOURLY_LOWEFF_APPROVAL.md remain the operational source. Publication is
not proof of scanning. No new symbol,live/leverage or duplicate strategy approval.
The complete operational instructions remain in the owner's private checkpoint.

Recovery:original MAR_hourly_compression_checkpoint_20261007.zip followed by
MAR_fill_brackets_checkpoint_20261008.zip;raw inputs separate. Current checkpoint
preserves all previous increments. No background test/monitor is running.
