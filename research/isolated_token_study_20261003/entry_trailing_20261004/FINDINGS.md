# Findings — entry diagnostics and trailing exits

Research-null: no qualifying candidate.

Date: 2026-10-04. Status: `CLOSED_NULL`. Do not merge for trading. Do not retune. Do not add configs. Do not enlarge the search because it failed.

Munha's score, recorded as PASS at about 09:32 GST, says the null stands. That PASS is his check of the null. It is not a screen pass and it is not an Inbox. The memo file does not contain the 09:32 clock time. It is `MUNHA_NULL_2026-10-04.md`. He did not rerun.

Eighteen Stage 2 rows. `passes_screen` is false on every row in `stage2_summary.csv`. No row is positive in both periods. Every validation mean is negative. Stage 3 was not scored. `scores_2026` is false. Frozen selection is null for BTC, ETH, and SOL.

Least negative validation row is `rule_fade_SOLUSDT_long`, n=46. The summary mean `-0.001013` is a leading prefix of the ledger cell `-0.0010134189179124343`. Still under zero, and under the n floor of 50.

Best discovery row `model_l2_SOLUSDT_long` failed validation. The close-out summary prints n=60, mean `-0.002733`, PF `0.798`. The ledger cells on that row, spec `l2_C1_p60`, are n=60, mean `-0.0027326713929634026`, PF `0.7984988037936258`. The summary mean and PF are rounded prints of those cells. A green discovery slice is not a pass.

The box run used a fresh clone that was checked out at `c2693bc5eb0fd272cb016dc7a387a7316fdfb263`. That sha is not written inside the run log or `manifest.json`. Do not claim the artifacts self-identify that commit. Munha's memo says the short label `c2693bc` is not in the log or the manifest and calls that label unconfirmed.

Cache zip SHA256 was `344ac29b5b2ee2fe9ba5966026914489dc22dfaed75374fbe86316052da863dc`. Ledger mtime 09:28:39 GST.

The attached archive SHA256 `c66b276502ea43786d46f7b0081e875d0f3a071b53e8a4c32663539d602a4e26` unpacks to the same box files already in `results_box_20261004/`. Cell-level reconciliation is in `FINDINGS_2026-10-04.md`.
