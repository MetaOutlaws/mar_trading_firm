# Audit: standalone hourly ADX strength gate

7 October 2026, before scoring. Research head inspected:
4934e8876e5af0d22dcc4a92a0e584dc2b7851f2. This is a new comparison on the approved
hourly compression entry, not a claim that ADX or an ADX25 threshold is novel.

Related prior tests explicitly preserved:
- PR96 contains sealed FAILED BTC4h adx_rsi_agree and adx_ma_agree tests at
  floors20 and25. They add DI direction plus RSI70/30 or close versus EMA21,
  use different entries and a different execution/target-first framework.
  None is rerun, reclassified or promoted by this experiment.
- ema_adx_trend is an existing EMA20/50 pullback family, ADX14 default floor20,
  different trigger and target settings. PR4 explicitly fixes duplicate walks
  of completed legacy grids; this study is not another legacy grid walk.
- The previous-day sweep study saved15m ADX14 as a diagnostic, using EWM seed;
  it did not trade an ADX cutoff on the hourly compression baseline.
- Earlier token-trade anatomy recorded RSI/Connors and context, not this exact
  ADX-only compression comparison. Original hourly runtime source at
  d56eac5cf82c403089d5a2bab20f13bc931de654 has no ADX gate.
- Earlier extension/BTC comparisons are separate interventions. No combination
  of these with ADX is scored here.

Fresh GitHub commit search 'compression ADX' found no matches; corresponding PR
search found the current research queue. Broader EMA/ADX search identified the
legacy tests above. Local source/protocol/history inspection found no completed
standalone own-token hourly ADX14>=25 gate on these143 compression opportunities.
Search absence alone is not proof; this scoped source comparison supports
proceeding. External Grokbot runtime ledgers are not accessible/certified.

Additional continuity note: PR96 also preserves a failed eth_btc_return_agree
BTC4h entry (lagged ETH one-bar move >=0.3% plus BTC candle direction). It is
distinct from the completed ETH/SOL hourly compression BTC24-sign condition.
Keep that predecessor explicit alongside the earlier learned BTC24 feature.

The indicator's exact seeds and zero-range behavior are frozen in PROTOCOL.md;
they are not a new fitted parameter or a change to previous results. A single
25 cutoff is conventional motivation, not empirical evidence of an edge.

References:
https://github.com/MetaOutlaws/mar_trading_firm/pull/96
https://github.com/MetaOutlaws/mar_trading_firm/pull/4
https://github.com/MetaOutlaws/mar_trading_firm/pull/99
https://github.com/MetaOutlaws/mar_trading_firm/pull/100
https://www.fidelity.com/viewpoints/active-investor/average-directional-index-ADX
