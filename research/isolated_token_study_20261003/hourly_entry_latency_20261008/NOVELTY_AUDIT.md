# Novelty and timing audit

Restored original hourly checkpoint and cumulative fill-brackets checkpoint,
verified their archive hashes and every one of the 933 latest payload hashes.
Searched saved PROTOCOL.md/FINDINGS.md/NOVELTY_AUDIT.md for delay/latency/poll.
Earlier zone timing and sweep confirmation experiments changed other entry
families or confirmation conditions. They do not test constant scanner delays
on the now-approved compression/BTC/Connors/low-efficiency rule with fill-origin
brackets. Previous approved-rule protocols explicitly used immediate entry;
the latest fill audit names scanner latency and sampled exits as next questions.
No identical test appears in this available saved history. External uncommitted
Grok runs cannot be certified absent.

Source inspection: reserved_2026_handover/runtime/core/execution/engine.py
MAX_CANDLE_LATENCY and _evaluate(): completed bar +15-minute actionable window,
strict greater-than rejection. scripts/run_paper_trading.py:900-second default
sleep after scan/worker tasks, with paper exit supervision in the waiting loop.
Runtime source hashes are pinned in freeze.json. This source inspection does
not establish the deployed configuration, observed scanner latency or cloud health.

Prior results and executable references remain unchanged. New work lives only in
hourly_entry_latency_20261008. This audit selects no thresholds using new outcomes.
