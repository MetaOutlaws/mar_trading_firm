# Garwe LOCK PASS: xs_prospect_value_weekly (2026-10-16 ~17:40 GST)
Draft b815ed4d and kill file 62e906ff (both mtime 17:32:25) predate tk_counts.py (17:32:38) and its output (17:32:48). The "~17:45" header label is a typo; box mtime governs. Counts are features only.
Data gates pass: main 90 ISO weeks, 477.6 leg-trades/yr, median 83 eligible. Kill: every comparator is under 0.50. Max is mom3 rho 0.424 / J 0.363, then vol60 at 0.362; skew is 0.19/0.27, and the sealed BAB beta is 0.355/0.34.
Ruling on momentum/skew closeness: not a variant. My own clone check (features only, garwe_clone/clone_check_ret60.py) against the 60d cumulative return on the SAME window gives rho 0.643 and J 0.498. That's a material but not identical overlap: TK weights losses at 2.25x with probability distortion, so it isn't a pure lookback change. Skew is far (0.19).
Disclosures:
(1) Long low-TK means leaning long past losers. The edge sweep e3acd03f showed xs_momentum_3w at -24.6 bp/wk net on 2024-25, adjacent information on this window. The sign comes from the published paper (Chen et al. 2022), not from the sweep, but the risk of a lucky direction pick is disclosed.
(2) The clone check is report-only and not a kill; it wasn't pre-stated.
(3) Munha reports, report-only, the main result with 60d return partialled out.
(4) The 60d window is Shumba's own choice, and the paper's window wasn't read.
Grade is capped at B.
Gates unchanged: PF>=1.15, CI excludes 0, beats-random (turnover-matched), >=50% of folds profitable, no losing regime, DD<25%. Funding is included and never zero-filled; the ex-ante gap rule applies. 0.31%/leg. The harness must hash the countersign file into the manifest (the fix from 549deb0b). 2026 is veto-only.
Next: Munha writes the prereg, Brian gives a CEO YES, then Chiremba's harness gets my ACK, then main, hash, holdout. Live off.
