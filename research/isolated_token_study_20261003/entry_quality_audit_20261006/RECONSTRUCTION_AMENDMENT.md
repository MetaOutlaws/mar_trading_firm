# Source amendment before new outcome scoring

6 October 2026. The original standalone-zone runner was not published; the
published standalone-zone protocol was recovered at GitHub commit
f55bcac0cdd8e3c82768205958424a99e14f4582. `reconstruct_zone.py` implements those
rules using the earlier archived zone map and scalar-checked exit engine.

Reconstruction produced exactly 38,469 base-cost positions across 144 groups.
All 72 published 2025 configuration rows match closed count and stop count
exactly, mean return within 0.000051 percentage points and profit factor within
0.000501 (the published rounding). This does not prove original row identity;
there are no individual original rows available for byte-level comparison.

Proceed with the primary four-hour prediction diagnostic on this explicitly
reconstructed candidate set. Do not claim to have recovered the original
feature-enriched export. The one-hour/24-hour excursion diagnostics and new
costed matched-control exit comparisons remain separate pending stages; they
cannot rescue a failed primary gate. This staged execution does not change the
registered primary hypothesis or qualification rule.

Implementation detail: four-week bootstrap uses circular moving blocks over
the complete calendar-week grid, including weeks with zero matched signals.
Each draw retains the paired signal-versus-control-mean difference. Controls
are drawn from the same calendar week as their signal. Control reuse and
overlapping horizons remain dependence limitations.

The initial reconstruction invocation stopped on a missing pyarrow dependency
before scoring. The subsequent invocation installed that dependency and
completed. No parameter variants were tried during reconstruction.
