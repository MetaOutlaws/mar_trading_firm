# Data-only boundary amendment, before additional-token outcomes

The supplied collector archive has SHA256
`c49af11ec116836ccfc5129f1fa92c80c72714adc52bc2556fb919de1ae001eb`.
All 162,661 manifest entries and 162,663 ZIP CRC checks passed. The inventory
contains 153,846,672 minute candles across 93 selected new tokens and the three
reference assets. There are no gaps between a symbol's first and last observed
minute, no missing minutes inside its selected months, and no funding gap over
eight hours. Funding cadence and historical-universe provenance remain provisional.

The funding endpoint check separately found LINA's last candle nine hours after
its final supplied funding event. A public-API recheck returned no usable JSON;
the possible missing settlement is not assumed to have a zero rate. Uniformly
cap the available endpoint at the earlier of the last complete candle hour and
last supplied funding time plus eight hours. This changes only LINA, removing
60 additional terminal minutes and ending its execution cache at 27 March 2025
08:00 UTC exclusive. LINA's only selected month is July 2023. No outcomes were
consulted to choose this cutoff; any unresolved position is marked before it.

The strict catalog-boundary audit is preserved as blocked: catalog launch times
precede first observed quotes for 54 symbols, producing 21,013 expected but
unobserved boundary minutes. Those minutes will not be invented or filled.

Apply the protocol's explicitly permitted data-only cutoff amendment uniformly:
start each symbol at its first complete observed UTC hour; end at the last
complete observed UTC hour. This removes 1,509 leading partial-hour minutes and
three trailing minutes from execution caches. Full original data are retained.
Every interior missing minute still blocks scoring. No token is silently dropped.
The 2022-2024 / 2025 study partitions remain fixed. A position unresolved at its
available data endpoint is marked, separately identified, and is not a completed
trade or a holding-timeout exit.

Monthly membership and frozen turnover ranks remain unchanged: 675 selected
token-months across 93 new tokens. The original collector's 90-day rule uses
catalog launch and first daily observation, not the first intraday quote. SUI's
first selected month has 89.4167 days of complete observed intraday history;
that discrepancy is disclosed, not resolved by inventing a new universe rule.
All signal features must still pass their existing finite-history requirements.

Before scoring, repair implementation omissions discovered in code review:
carry hourly timeframe metadata into admission; include eligible tokens with no
signals in reports; distinguish signal-year cohorts from actual entry-year
tables; separate completed-trade win rates and boundary marks; export separate
portfolio ledgers; include per-arm original-signal confidence intervals; pin the
reference and runtime source trees in the immutable freeze. These implement
already required accounting. They do not change entry gates, stops, targets,
costs, admission limits, decision thresholds, or the frozen protocol.

The prior strict-audit failure and test-harness dependency failures are retained.
No new-token trade outcome has been scored at this amendment. Additional-token
2026 outcomes remain closed. Possible prior Grok use remains disclosed.
