Implementation clarifications, fixed before the run:

- The optimization screen profit factor is computed from standardized net R returns (pf_R), consistent with training rankings at equal initial price risk. Conventional fixed-notional PF is separately reported as pf. Neither is account equity.
- Training eligibility uses completed trade counts by entry year. Worst-year mean R includes boundary marks, so unresolved losses are not hidden. Trades spanning years inside training are attributed to entry year, a limitation of this annual ranking.
- Bootstrap uses 5,000 weekly-entry-block resamples. Six base-cost optimized fold/token evaluations are primary; stress intervals are secondary diagnostics.
- Zone/structure filters are not retuned. Prior sparse samples motivate focusing on the EMA-regime entry family and risk design; this does not claim zones are universally ineffective.
