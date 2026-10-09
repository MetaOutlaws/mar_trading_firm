# Connors RSI prior-work audit

8 October2026 Dubai, before scoring. Research branch head
0fc915a162c607e761ed15a408e1597824593d4c. GitHub Connors PR search returns
current research PR99; compression+Connors commit search has no match. Search
scope does not certify completeness of external Grokbot runtime experiments.

Existing overlaps acknowledged:

- core/strategy/connors_rsi_fade.py is present in runtime paper branch
  d56eac5cf82c403089d5a2bab20f13bc931de654. Default3/2/100, long CRSI<=10 and
  rising, short>=90 and falling, default2% SL/4% TP. Its coding brief specifies
  4h/BOTH. This is a separate reversal trigger; do not relabel it novel or rerun
  it as this test. No deployment/performance claim follows from its existence.
- Prior trade anatomy uses arithmetic-seeded CRSI(3,2,100), strict-less rank
  of current return against previous100, ties excluded, streak resets on flat.
  It analyzed EMA-reclaim entries, bins and opposite-direction reversal extremes
  at signal and over the prior3 bars. Those were observational comparisons,
  not filtered chronological replays. Preserve their zero signal-extreme counts.
- Original entry-discovery learned models included RSI14, but not Connors RSI.
- Completed hourly RSI14 exclusion is distinct: long<=70/short>=30, with
  historical improvement but worse2025. Preserve H-RSI-REGIME-01 requested by
  Brian; do not transform that observation into a proven calendar switch.
- Hourly extension, BTC24 and ADX comparisons did not stack Connors RSI.

No exact standalone long CRSI<=90/short>=10 exclusion on these143 hourly
compression opportunities was found in inspected code and records. This is a
new comparison on an existing family, not a new indicator or entry strategy.
Thresholds are fixed from prior indicator conventions, not selected from these
outcomes. Both study periods are reused; independent confirmation remains absent.

Primary sources linked in PROTOCOL.md support formula and conventional extremes.
The original author's daily-equity research does not validate hourly crypto.
Private handover preserves retrieval evidence and the inspected runtime source;
no full third-party article or source PDF is redistributed.
