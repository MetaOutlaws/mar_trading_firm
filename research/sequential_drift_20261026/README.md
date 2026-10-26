# Sequential drift research — 26 October 2026

Status: first economic screen completed; reject the frozen bounded-evidence candidate. This is research only. No broker, service, account, approved strategy, or Cipher paper-trial change.

PROTOCOL.json and FREEZE.json were saved before new outcomes were scored. The code tests one bounded daily CUSUM candidate (S01) and one unbounded control (S00), across 96 retained tokens in reused 2022–2025 history. No historical 2026 performance is opened. Parameters are not calibrated financial probabilities.

RESULT_SUMMARY.json has the decision and verification totals. NEXT_TEST.json specifies the funding-aware loss-protection follow-up; it has NOT run. Do not deploy these scripts as strategies or treat any output as promotion authorization.

## Reproduce

Python 3.12 with numpy, pandas, pyarrow and matplotlib. Tests do not need private data:

    python3 -m unittest discover -s research/sequential_drift_20261026/code -p 'test_*.py' -v

Set up a private research working directory with this folder as `study` and the verified source checkpoint extracted at sibling `restored/MAR_relative_value_checkpoint_20261020`. It supplies `results/universe.csv` and `cache/SYMBOL.npz` (minute opens, completed hourly closes, funding indices/rates). Parent archive SHA256: 3b89e8bc7fd11519b1e8144d04d74cae66d5da02508f2af3c020893d4ab891ef. All96cachefile hashes must match that archive's MANIFEST.json. Private data is not in this Git branch. Do not replace it with current surviving exchange tokens or extend it into2026.

    mkdir -p study/results
    python3 study/code/run_study.py
    python3 study/code/verify_and_analyze.py

Code/PROTOCOL hashes in FREEZE.json are checked by the scorer. 10synthetic checks,576prefix checks,1,480signals,10,360decisions,7,801event paths/cashflows and843,124funding settlement evaluations passed. Independent means a second implementation, not a separate research team. The first scoring execution failed at initial Parquet write because pyarrow was absent; after dependency installation, unchanged frozen code was rerun. No outcomes were used to modify the candidate.

Full reports, per-token data and reproducible private output checkpoint are retained with the owner's research artifacts. Aggregate R is the sum of independent fixed-notional trade outcomes divided by each original price-stop risk, not funded ROI or capital-weighted superiority. Opportunity drawdown is not funded account drawdown. Existing I/IC account benchmarks remain a separate, previously matched study.
