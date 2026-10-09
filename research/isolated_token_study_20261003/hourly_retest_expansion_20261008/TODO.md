# Active queue — updated 9 October 2026

The additional-token comparison is complete and independently verified. See
`RESULTS_20261009.md` and `NEXT_STAGES_20261009.md`. The 2026 acquisition
attempt is blocked at public-API availability; no 2026 outcomes were scored.


| Priority | Task | Status | Completion evidence |
|---|---|---|---|
| P0 | Publish retest experiment and owner paper approval to PR99/PR101 | Complete | Research b2140ca485c9d5ad645cb8c2acc59a65d2cafd44; runtime public handover1e24a411c42a05b10a85a9e6dc56626e47568481; exact readbacks |
| P1 | Check additional-token download availability tonight,Asia/Dubai | Complete | Supplied archive downloaded; all ZIP CRC and manifest checks pass; 93 new tokens audited |
| P1 | Restore frozen reference inputs and prevent duplicate independent runs | Complete | Retest checkpoint and six BTC/ETH/SOL inputs re-hashed; `run_state.py` uses an atomic `codex_independent` claim |
| P1 | Prepare outcome-blind collector audit | Complete | `data_gate.py`; manifest/membership/grid/funding/closed-2026 gates; synthetic tests in `test_preparation.py` |
| P1 | Complete adapter and frozen-reference parity | Complete | 69 signals; 276 immediate paths; 168 retest paths; 24 admission replays; 420 ledger rows exact |
| P1 | Bind audited inputs, signals, protocol and runner before claim | Complete | `freeze_gate.py`; changed-input, closed-2026 and source-hash tests; prior-use audit recorded |
| P1 | Compare frozen immediate baseline versus frozen60m retest across all eligible new tokens | Complete — inconclusive | 207 signals; all 16 books independently replayed; full ledgers and both return denominators saved |
| P1 | Integrate approved retest challenger into PAPER runner | Pending engineering | Durable pending state,minute-close reclaim,deadline,next-open execution,restart/idempotency and attribution tests |
| P2 | Verify actual cloud activation after integration | Pending | Strategy/config hashes,current cycles,eligible symbols,pending decisions and paper ledger evidence |
| P2 | Separate additional-token2026 replication | Protocol fixed; acquisition blocked | H-RETEST-EXPANSION-2026-01 registered before viewing these returns; initial official API request non-JSON |

Keep baseline and challenger separately attributable. Do not silently share a
position book in the comparative research or allow duplicate exposure under
cloned strategy names. Paper approval is recorded in OWNER_APPROVAL.json;
activation is not yet verified. Production/live permissions remain unchanged.

The prior failed all-period opportunity-cost screen remains in the historical
record. The owner explicitly accepts that trade-off for paper testing;comparison
metrics and hypotheses remain clear as new evidence arrives.

Data-readiness watch created:21:00,22:00,23:00 on8October and00:00 on9October2026,Asia/Dubai. It checks accessible GitHub/Library download records and advances the fixed research gates only when files are accessible. Stop on an existing active/completed run;disable after handoff/start.
