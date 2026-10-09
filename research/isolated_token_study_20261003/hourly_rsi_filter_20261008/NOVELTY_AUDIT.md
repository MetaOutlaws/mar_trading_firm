# Prior-work audit: RSI on hourly compression

Inspected 8 October2026 Dubai before scoring. Research branch head was
cdc603f6f77ffd40bb9ae116455c96caa35e28ae; runtime paper branch remains
d56eac5cf82c403089d5a2bab20f13bc931de654. GitHub RSI PR search returned96,99,
17,78,24. Compression+RSI PR search returned only current research PR99;
compression+RSI commit search returned no match. Searches are not proof that
every external Grokbot runtime ledger has been inspected.

RSI is NOT a new feature or universally untested idea:

- trade_anatomy_20261006 studied RSI/Connors values, coarse bins and directional
  extremes at signal and in the previous three bars on EMA-reclaim entries.
  These were associations on unchanged admissions, not filtered replay. Signal
  reversal extremes were absent; retain that result. Here we exclude same-trend
  extremes on a DIFFERENT hourly compression trigger and replay occupancy.
- entry_discovery_20261006 exposed RSI to small learned models; no qualifying
  edge emerged and selected trees did not select RSI. Existing original RSI
  fields are retained but the explicit arithmetic-seeded RSI is recomputed.
- PR96 contains sealed failed BTC4h RSI combinations: ma_rsi_agree70/30 and
  80/20, va_rsi_agree70/30 and80/20, adx_rsi_agree20/25 floors with DI direction
  and RSI70/30, and ma_macd_rsi_agree. These are different entry systems, clocks
  and combined predicates; they remain FAIL. Do not rerun or relabel them.
- Earlier sweep work recorded 15m RSI as context, without a threshold filter.
- The completed hourly extension, BTC24 and ADX tests explicitly excluded RSI.
  Preserve their positive and negative findings and the separate BTC approval.

No exact standalone long RSI<=70 / short RSI>=30 predicate on these143 original
hourly compression opportunities was found in inspected saved/GitHub evidence.
This is one isolated entry-filter comparison, not a new entry family or an
independent confirmation of an untouched hypothesis. Both periods have already
been explored. No outcome-derived cutoff, side selection or token selection.

Source motivation is the primary educational Fidelity RSI page linked in the
protocol. Conventional extremes can persist in trends, so the test explicitly
counts continuation winners lost. Its existence does not establish an edge.
Raw retrieval/search evidence is retained in the private handover.
