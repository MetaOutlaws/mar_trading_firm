# Scope and novelty audit before scoring

Current research head before this experiment:45e17746fdc86ee9ac47bed190406e686eb89a3f.
Runtime documentation head:be69670168deeffe988c589325b76571950ebb93; approved runtime
implementation3c226bca19cca1c771bcb2ed637f9ec39f74c432 remains unchanged.

The hourly stop-width, extension, ADX, Connors and conditional-cap protocols
explicitly retain quote-based barriers. Their raw runner in
diagnostic_optimization_20261004/optimize.py uses t.o[entry_i] for the bracket anchor.
The latest reserved replay imports that same runner and also preserves quote levels.
Runtime core/execution/engine.py instead calls risk_levels(fill_price,...) after
the broker returns a fill. core/execution/contract.py defines those fill-based levels.
Its comment about research parity refers to the separate runtime BacktestEngine;
it does not establish parity with this isolated research runner.

Earlier zone entry delays, fixed stop widths and exit/profit-protection experiments
did not isolate bracket anchor for this exact approved entry combination. Generic
F04 parity work exists; this test is specifically a reconciliation of the newer
isolated research model with the approved runtime bracket origin. It is not claimed
to be a novel concept across all company history or unobserved Grok work.

A second contract difference was identified before scoring: OHLC-resolved stop
exits do not take extra exit slippage in the runtime contract, but the isolated
research cost routine applies adverse exit slippage to every outcome. Hold that
conservative cost rule fixed in BOTH arms here. Thus this test audits bracket origin
only, not complete paper-execution equivalence. No engine or approval file is edited.

One small read-only schema inspection printed valid counts but the Python process
aborted at Arrow shutdown. It computed no new outcomes and wrote no experiment
results. The new runner uses single Arrow CPU/IO threads and synchronous reads.
Any scoring/preflight failures will be retained with their exact logs and sources.
