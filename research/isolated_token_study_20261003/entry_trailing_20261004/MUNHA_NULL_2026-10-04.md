# PR #94 Stage 2 gate score

Sunday 2026-10-04, scored from the finished box artifacts. No rerun. No retune. No added config.

Verdict: PASS. The null stands.

Sources: `/workspace/entry_trailing_20261004_out/experiment_ledger.csv` (18 rows, all stage 2, status scored), `stage2_summary.csv` (`passes_screen` False on all 18), `manifest.json`, `stage3_NOT_SCORED.txt`, `frozen_selection.json`, `/workspace/entry_trailing_20261004_run.log`. Ledger mtime 09:28:39 GST.

Archive SHA256 matches `344ac29b5b2ee2fe9ba5966026914489dc22dfaed75374fbe86316052da863dc`. `scores_2026` is false. Frozen selection is null for BTC, ETH, and SOL. Stage 3 was not run: no Stage 2 row cleared the pre-registered screen, so the four exit specs were not applied. Git head `c2693bc` is not in the log or the manifest. That label is unconfirmed. It does not change the null.

Screen checked, not adopted as an Inbox gate: n at least 50, mean net above 0, and PF at least 1.15 in both discovery and validation, plus stress mean above 0 in both periods. Zero rows pass. No row is positive in both periods. Every validation mean is negative. Least negative validation is `rule_fade_SOLUSDT_long`, n=46, mean -0.001013. Still under zero, and under the n floor.

Best discovery row `model_l2_SOLUSDT_long` matches the quoted read. Discovery n=90, mean 0.005532321, PF 1.568543. Validation n=60, mean -0.002732671, PF 0.798499. Stress means 0.003522182 then -0.004726212. On this row the desk means equal the unstressed means, so the doubled-slippage pair is the stress column.

Other discovery-green rows with PF at least 1.15 also fail validation: `rule_fade_BTCUSDT_long` (validation n=11), `rule_fade_SOLUSDT_long` (n=46), `model_l2_ETHUSDT_long` (validation mean -0.002582, n=217). A green discovery slice is not a pass and not a side cut.

Hard gates were not reached. No bootstrap, no beats-random, no fold gate, no drawdown gate. The screen is not an Inbox. No walk. Book stays 12+56 Option B. Live off.
