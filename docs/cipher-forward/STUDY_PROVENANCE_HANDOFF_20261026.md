# Cipher study provenance and implementation handoff — 26 October 2026

Recipient: Grokbot / the implementation owner of PR #172.
Owner instruction: share the verified provenance directly and proceed with the
already-authorized PAPER implementation. This note supplies the missing answer;
do not request the research date window from the owner again.

## Verified answer

**The research used 1 January 2022 through 31 December 2025 UTC. It was NOT
developed solely from data before mid-October 2023.**

- Universe: 96 retained tokens, subject to each token's actual available history.
- First design: MAR-MOMENTUM-FLOW-CONFLUENCE-01, 22 October 2026.
- 2022 was the development/diagnostic period. 2023–2025 was the chronological
  evaluation period. All these years already had research exposure; the
  original protocol explicitly says the later years were not untouched holdout.
- The two-sided W11 candidate failed its baseline/moderate economic progression.
  Short-side attribution motivated the subsequent W11S short-only study. That
  direction choice therefore followed inspection of historical results.
- Entry-filter, exit/target and portfolio-allocation follow-ups inspected the
  same 2022–2025 archive. The 3R candidate and the selected comparisons cannot
  be represented as fixed before the 2023–2025 outcomes were seen.
- Latest allocation output: MAR-3R-ALLOCATION-08, 23 October 2026. Its historical
  ranking is not independent prospective validation or verified deployed earnings.
- The hourly endpoint labelled 2026-01-01 00:00 UTC closes the last 2025 candle.
  It is not a 2026 performance observation.
- These studies recorded historical_2026_opened=false. This is a statement about
  this research workstream, not a certification that every 2026 dataset elsewhere
  in the firm is untouched. Indicator warmup is not trading performance.

The idea is a transparent Market-Cipher-inspired public-indicator hypothesis,
not a licensed Market Cipher replication or Crypto Face's actual trade record.
It combines an hourly WaveTrend-style momentum turn, weakening adverse CMF21,
and causal completed 4h trend context. The short strategy was selected through
the disclosed research sequence above.

## Evidence already in Git

At the original runnable release
`4d0bc59f229c9b12f0200e245cb865d8efb7175f`:

- [README, historical input window](https://github.com/MetaOutlaws/mar_trading_firm/blob/4d0bc59f229c9b12f0200e245cb865d8efb7175f/docs/cipher-forward/README.md)
- [Candidate parity and input hashes](https://github.com/MetaOutlaws/mar_trading_firm/blob/4d0bc59f229c9b12f0200e245cb865d8efb7175f/docs/cipher-forward/CANDIDATE_PARITY.json)
- [Research/source reconciliation](https://github.com/MetaOutlaws/mar_trading_firm/blob/4d0bc59f229c9b12f0200e245cb865d8efb7175f/docs/cipher-forward/SOURCE_RECONCILIATION.json)

The following original report bytes were recovered and checked on 26 October.
Their descriptions above are verified from the reports, not inferred from names:

| Report | SHA-256 |
|---|---|
| MAR_Market_Cipher_test_20261022.html | 9914af04bbf4254f2fd435dfdef4a8699da9668f23550ed3bbeb35cc7ff19658 |
| MAR_3R_allocation_20261023.html | db144294de0aca0eb69392977cb42769dcc09ed0cb49e24a60b903f486ccaa4b |

Reports and research checkpoints remain preserved in the owner's research
archive. No private raw datasets are added to this public repository by this
handoff. The verified window above is sufficient to resolve the provenance
classification without waiting for an archive transfer.

## Implement now

1. Record the candidate as **developed/evaluated using 2022–2025; fresh validation
   required**. Do not route it through the pre-mid-October-2023-only eligibility
   path, or relabel any 2023–2025 replay as a fresh holdout.
2. Continue the authorized isolated, REPORT-ONLY paper implementation in PR #172.
   Preserve the current Garwe ruling, frozen rules, config/seed identity, twelve
   internal portfolios, opportunity tracking, paper risk limits and no-promotion
   clause. Use the latest reviewed implementation; do not reinstall the older
   October 23 runtime over the newer fixes.
3. Complete destination image tests, current runtime/source checks, SGP1 resource
   headroom checks and indicator preparation. Then start the isolated service
   through the existing authorized operator session. Capture the immutable
   release, image/config/seed hashes, actual first future cutoff, first full scan
   and ledger reconciliation. Zero fills are acceptable. Technical failures
   remain blockers; report the exact failure rather than bypassing it.
4. The 30/60/90-day reviews remain operational/report-only. Keep promotion
   separate: the current filing/LOCK, holdout and desk gates still apply. The
   30-week requirement is not a reason to postpone collecting paper observations.
5. Preserve the cost distinction: the current desk requirement is **0.31% per
   leg on entry and exit**, not 0.31% per completed round trip. None of the
   existing three frozen cost settings exactly matches it. Keep their current
   labels; do not claim a binding-cost pass or silently change a frozen book.
   A binding-cost validation needs its own explicit, versioned specification
   and admission replay through the desk process.
6. Separately audit whether any historical 2026 window is untouched and eligible
   under the desk's holdout rules. Record any prior use, warmup overlap and the
   precise admissible dates. Do not inspect its outcomes until that validation
   protocol is locked. If ineligible, collect fresh forward evidence. Do not
   describe seven months of new waiting as unavoidable without this audit.

Return a concrete deployment result in PR #172: release, service state,
activation_evidence.json, the first report, and any exact outstanding blocker.
No real-money trading, automatic promotion or production-account resize is
authorized by this handoff.
