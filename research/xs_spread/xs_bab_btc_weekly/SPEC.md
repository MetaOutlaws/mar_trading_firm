# Garwe LOCK PASS: xs_bab_btc_weekly (2026-10-16 ~15:20 GST)
Draft 1ca85938 (mtime 15:12:31) and kill file 12dd3ae0 (15:12:16) both predate bab_counts.py (15:12:47) and bab_counts_out.json (15:12:58); verified. Counts are features only.
The data gates pass: main has 90 week-clusters, 283.9 leg-trades/yr and a median of 82 eligible names.
Kill: every comparator is under the pre-stated 0.50 line.
Overlap ruling: the btc_shock gate Jaccard of 0.454 is under 0.50, so it PASSES. Not a variant: btc_shock was an event cell (shorts only on BTC shock bars, with 4h beta used only as a gate). This cell is an unconditional weekly rank on daily 90d beta, both sides, beta-neutral. No re-timing, sign flip or same-gap reuse. Disclosed: the overlap is near the line, and btc_shock's high-beta short was a sealed FAIL (+0.001R).
Further disclosures: low-IVOL outcomes (Munha aa19efc8, -0.05%/wk) were viewed on main; that's a different factor (J 0.26, rho 0.20), so no contamination ruling, but it's disclosed. The legs aren't dollar-neutral (3x per-side cap), so net exposure, BTC funding and costs must be in the P&L. Grade is capped at B, and the prior is ~10%.
Gates unchanged: PF>=1.15, cluster CI excludes 0, beats-random (turnover-matched), >=50% of folds profitable, no losing regime, DD<25%. Funding is included and never zero-filled. 2026 is veto-only.
Next: Munha writes the prereg, Brian gives a CEO YES for the harness, Chiremba hashes it for my ACK, then main, hash, holdout. Live off.

ERRATUM (see 2026-10-16_garwe_countersign_munha_preregs_listing_bab.md): aa19efc8 is pre-main only; no main outcomes were viewed.
