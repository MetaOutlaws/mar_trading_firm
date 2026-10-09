# Audit: BTC 24-hour direction confirmation on hourly compression

7 October 2026, before scoring. This is a specific isolated condition on an
existing entry family, not a claim that BTC market context is a novel idea.

Inspected research head 068d5cd9007f191cece85c1014f650ebbb31c0e3 from a fresh
branch inventory. Current hourly runtime source was read at
d56eac5cf82c403089d5a2bab20f13bc931de654, path
core/strategy/hourly_compression_v1.py. It has own-token 24-hour direction,
compression/volume/body/close-location and prior-20-hour breakout conditions.
It does not require ETH/SOL entries to agree with BTC direction.

The entry-discovery package already computes btc24, token-minus-BTC24 and
signed_btc24 as candidate learned-model inputs. The frozen learned selections
use signed_r168 and signed_funding, not this fixed BTC24 sign predicate.
That earlier exposure is preserved and means BTC context is not a fresh,
previously unseen feature. No isolated comparison of this sign condition on
the exact approved hourly compression rule was found in the inspected package.

Other related work is distinct:
- alt_btc_residual_stretch_fade (PR78): 4h price-beta residual stretch/fade
  using prior fitted levels and ATR20, not BTC direction confirmation.
- Soko paper regime gates (PR51/72): categorical activation rules, not this
  exact causal BTC24 sign predicate on hourly compression.
- Earlier regime/structure and zone studies use different entries/interventions.
- The pinned Grokbot execution addendum at
  d79735916aab139ced1d827d601404484cb30003 uses own-token EMA trend for its
  15m compression rule, with different compression/volume/breakout thresholds.
  Its recorded 18-config CLOSED_NULL is not reopened by this comparison.
- The just-completed extension cap is an entry-location condition; it is
  omitted here. The original baseline, not the filtered result, is the control.

Fresh GitHub commit search 'BTC confirmation' returned no commits. A BTC
confirmation/alignment/24h PR search returned related work and the new queue;
the inspected source and protocols, rather than search absence alone, support
the scoped decision. Local git history/source/protocol searches found no exact
completed standalone match. Raw search/read evidence is retained privately.

Proceed with one registered comparison. External Grokbot runtime job ledgers
are not accessible here, so universal absence of a duplicate is not certified.

References:
https://github.com/MetaOutlaws/mar_trading_firm/pull/99
https://github.com/MetaOutlaws/mar_trading_firm/pull/100
https://github.com/MetaOutlaws/mar_trading_firm/pull/78
https://github.com/MetaOutlaws/mar_trading_firm/pull/51
https://github.com/MetaOutlaws/mar_trading_firm/pull/72
