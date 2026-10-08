# Scope and lineage

H-FILL-BRACKETS-01 changed bracket origin; H-ENTRY-LATENCY-01 changed entry
timing; H-EXIT-POLLING-01 changed exit observation. Those experiments retained
the all-exit adverse-slippage convention. Their saved outcomes remain intact.
H-STOP-COST-01 isolates only the omitted second stop tick, on those frozen paths.

Pinned runtime source evidence:
- core/execution/contract.py::exit_fill_price returns quote for stop_loss.
- core/execution/paper.py::peek_exit_triggers sets at_mark=True for stops.
- PaperBroker.quote_mark_close uses fill_price directly and fees its notional.
- PaperBroker.quote_market_close slips the latest mark for targets/timeouts.
- core/execution/engine.py::_settle_paper_exit selects the corresponding quote.

This is a new controlled decomposition of a known runtime convention, not a
claim that stop-cost reconciliation is a novel strategy. Prior tests did not
isolate it across the frozen sampled-exit paths. Source snapshot and predecessor
hashes are retained. No claims about external Grok work unavailable in this repo.
