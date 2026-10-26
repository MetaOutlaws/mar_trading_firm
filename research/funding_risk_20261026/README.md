# Funding-aware planned-loss protection

The original sequential-drift strategy lost money after costs and funding. This single-change follow-up ratchets its stop after paid funding becomes observable. **It failed:** desk net R declined from -152.30 to -189.68 over 2022–2025. Baseline and moderate cases also failed. This is not a paper nominee.

The 414 original entries were retained and six new opportunities became available. Same-entry funding savings of 212.52 USDT were outweighed by worse price exits. The largest adverse difference came from a long BONK position crossing its adjusted stop during the retained 10 October 2025 price gap. The model observes minute opens and fills next minute; those are not guaranteed executable order-book prices. Even a generous arithmetic replacement of the worst loss by its planned budget leaves the new book unprofitable.

## Scope and files

- `PROTOCOL.json`, `FREEZE.json`, `code/run_funding.py`, and `code/test_funding.py` were published before new outcomes at commit `ca12333f459be33042425d14dea6ae8ecb9c4501`; their hashes are unchanged.
- `code/verify_and_analyze.py` reconstructs paths with a second implementation and produces annual, token, sector, direction, regime, cashflow, risk and block-bootstrap tables.
- `code/report.py` builds a static, self-contained HTML report from results and the retained input. No JavaScript or external chart resources are required.
- `RESULT_SUMMARY.json` contains machine-readable conclusions. `PROVENANCE.json` records sources, versions, limitations and incidental public 2026 exposure. `NEXT_STEP.md` is proposed follow-up, not a completed test.
- Private output checkpoint: `MAR_funding_aware_stops_results_20261026.zip`. Report: `MAR_funding_aware_stops_20261026.html`. The authoritative research state links their Library identities. Raw market data and Git-backed source code are not duplicated in that output archive.

## Reproduce

Create a local work root with `study/` containing this Git folder and `parent/` containing `research/sequential_drift_20261026` at parent commit `004a44f57ee5814cfa57be8e3c825985bb00eb7b`. Restore the market archive identified in `PROVENANCE.json` to `restored/MAR_relative_value_checkpoint_20261020/` under that work root. Restore the parent output archive to `parent_saved/` (its `results/` directly inside). Restore the new results checkpoint into `study/`, including `results/funded_benchmarks.csv` for the existing account references. Python dependencies and tested versions are in `PROVENANCE.json`.

From that work root:

```bash
python3 -m unittest discover -s parent/code -p test_study.py
python3 -m unittest discover -s study/code -p test_funding.py
python3 parent/code/run_study.py
python3 study/code/run_funding.py
python3 study/code/verify_and_analyze.py
python3 study/code/report.py
```

Before accepting new results, compare all six parent artifacts listed in `results/CONTROL_PARITY.json` against `parent_saved/results/`, verify every market-cache manifest hash, and verify the frozen hashes. There are 14 original and 14 funding-aware cost/timing books. This run reproduced the parent outputs exactly and passed 13 new plus 10 original synthetic tests. The second implementation checked 7,949 unique paths, 10,360 decisions and 694,387 funding settlements and reconciled marked daily cashflows.

All 96 retained tokens are kept, including inactive rows. There is no profitable-token whitelist. Sum R, net dollars and opportunity drawdowns are not account ROI or account drawdown percentages. Existing I/IC funded comparisons are shown separately and were not rerun here. The paper implementation workstream is unaffected.
