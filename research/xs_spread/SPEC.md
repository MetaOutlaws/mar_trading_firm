# Garwe LOCK PASS: xs_realized_skew_weekly (2026-10-16 ~11:40 GST)
Proposal 7512025e. PRESTATED e1cf9850 (mtime 11:33:55, earlier than skew_counts.py at 11:34:21; verified). Tape C SUMS ab447221 (universe96_full_history_20261016), perp_1h e974ef5a, membership_pit.
Cell (frozen, no retune): Mon 00:00 UTC rebalance. RSK = realized skew of the 168 1h log returns ending at the bar closing <= t, needing >=150 bars, >=31d history, and PIT listing. Long bottom tercile, short top tercile, equal-weight, dollar-neutral, 7d hold, 12% per-coin stop, next_open fill, 0.31% per leg-trade.
Windows: main 2023-10-15..2025-06-30 (90 weeks); holdout H2 2025 (26 weeks; the 30-week floor is main-only, holdout = positive week-cluster mean + PF>=1.15, one look after main is hashed); 2026 veto-only.
Rulings:
(1) MAX7 rho 0.475 / J 0.393 is under the PRE-STATED 0.50 line, so it is cleared. The line is not moved after the count, in either direction (same principle as iv_skew 1cba0032). Disclosure: the paper's mechanism runs through extreme up days. Cleared to LOCK, not certified independent beyond the stated test. The sweep's MAX reads (e3acd03f) are a partial information leak and must be noted in the prereg.
(2) Turnover ~33/54 positions a week: admissible. MDE, beats-random (a matched random tercile spread paying the same turnover) and PF are all net of realized turnover; realized turnover is a reported prereg quantity.
(3) Survivorship: grade capped at B is accepted as a disclosure. It does not change any gate.
Next: Munha preregisters (MDE/power at the stated d=0.295, net of turnover), Chiremba builds the spread harness on the pinned CostModel and hashes it before the run, and the run order is main hash, then holdout. Every gate is unchanged. Live off.
