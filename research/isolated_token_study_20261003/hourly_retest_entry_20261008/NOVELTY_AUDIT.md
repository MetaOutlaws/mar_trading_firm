# Narrow novelty and comparator audit

Reviewed the recovered cumulative research sources and current draft PR99 head
61b1e70e2762d625d15bc8feccd26cbe44c590dd before treatment scoring.

- zone_entry_timing_20261005/run_zone_entry.py waits up to six strategy bars
  for rejection of a mapped zone, requires directional candle body, cancels
  on regime changes and falls back at deadline. It can reserve pending capacity.
  This test uses the approved compression boundary, minute reclaim, one hour,
  no fallback and admission only at fill. It is not a rerun of that experiment.
- hourly_entry_latency_20261008 unconditionally delays fills by0/1/5/15m.
  It never conditions entry on a boundary retest. Its negative evidence remains.
- sweep_confirmation_20261007 concerns previous-day sweep/reclaim with15m
  confirmation, a different signal family and boundary.
- hourly_failed_breakout_20261007 changes exits after an hourly boundary failure;
  this test changes entry only, preserving its exit rules and initial risk.
- hourly_winner_loser_20261008 nominated lower extension but failed the2025
  association check. That median filter is not imported into this experiment.

H-STOP-COST-01 supplies the exact reconciled immediate-entry comparator.
No known saved experiment implements this full retest rule. This statement is
limited to the recovered repository and checkpoint record, not unseen work.
