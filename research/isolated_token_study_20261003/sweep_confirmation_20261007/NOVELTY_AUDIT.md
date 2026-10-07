# Duplicate audit — prior-day sweep confirmation
Audit date: 7 October 2026. Completed before scoring this variant.

## Finding
The underlying family is NOT new. Describing it as a new family was too broad.
The distinct question is whether immediate-next-15-minute-candle confirmation
adds value to a strict previous-day sweep/reclaim, versus the same setup entered
immediately. No exact match was found in the inspected records. This is not
proof that an unrecorded external Grokbot job never ran it.

| Prior work | Verified rule / evidence | Relationship |
|---|---|---|
| prior_day_extreme_reject, family 118 | 4h, raw previous UTC day H/L, tag then close inside, next-open fill, first signal/day/side; tolerance 0 or 0.1 ATR. PR16, merged commit 597393f164675ad80f1de91b06c7197c0dd5af3f | Direct family predecessor. No next-candle confirmation. Coding PR explicitly did not start walk-forward. Later requests call family 118 spent; detailed job-118 results were not found, so its performance is unknown here. |
| sweep_reclaim, original isolated study | 15m, prior 16-bar rolling high/low, sweep and close back through level, immediate entry | Same rejection concept, different level construction; no next-candle confirmation. Existing study stays closed. |
| session_liquidity_sweep | Fixed intraday sessions, 1h London/NY, sweep cap; PR4 reports job220 finished 0/12 | Related failed sweep family, not previous UTC-day 15m confirmation. |
| Grokbot entry/trailing branch | rule_fade: close at least 1% beyond preceding 96-bar extreme and volume >=2; fixed 4-hour outcome. Addendum plus findings at d79735916aab139ced1d827d601404484cb30003 | No reclaim or next-candle confirmation; 18-config budget CLOSED_NULL, all validation means negative, exits not scored. Do not reopen it. |
| failed_break_reclaim / failed_range_break_reversion | 4h rolling range, multi-bar probe or close-through then close back inside; PR31/19 | Related reversal hypotheses, distinct from the frozen comparison. |
| Recent shock_reversal | Volume/ATR shock, midpoint reclaim within next 3 candles | Different trigger and confirmation level. Prior budget stays closed. |

## Audit scope and limits
Inspected current GitHub default head 75eba65705f2a8b1f4e89d83edd5b3cd1ed7fbdf,
research head bf0512d8cc0d42e807a634f21952acb29e2331c5, recorded Grokbot handoff
branch d79735916aab139ced1d827d601404484cb30003, local nonshallow Git history,
relevant strategy sources, briefs, research protocols and findings. Inventoried
101 remote branches (two pages); this was not a full line-by-line audit of every
branch. GitHub commit, PR and issue searches were supplemented by source reads:
code search returned no hits despite the existing strategy, so absence from
search is not evidence of absence. No direct external Grokbot runtime ledger
or Singapore SSH access was available. No numeric result is invented for family118.

Source links:
- https://github.com/MetaOutlaws/mar_trading_firm/pull/16
- https://github.com/MetaOutlaws/mar_trading_firm/commit/597393f164675ad80f1de91b06c7197c0dd5af3f
- https://github.com/MetaOutlaws/mar_trading_firm/pull/31
- https://github.com/MetaOutlaws/mar_trading_firm/pull/4
- https://github.com/MetaOutlaws/mar_trading_firm/blob/d79735916aab139ced1d827d601404484cb30003/research/isolated_token_study_20261003/entry_trailing_20261004/EXECUTION_ADDENDUM.md
- https://github.com/MetaOutlaws/mar_trading_firm/blob/d79735916aab139ced1d827d601404484cb30003/research/isolated_token_study_20261003/entry_trailing_20261004/FINDINGS_2026-10-04.md

## Decision
Proceed only with the explicitly authorized bounded confirmation comparison,
not a restart, renaming or re-approval of any spent family. The immediate arm is
a contemporaneous control, not an exact reproduction of job118: clock15m,
strict pierce, SL2%/TP2.5%, and the repaired research execution contract differ.
This amends the roadmap with one separate entry hypothesis after both exit
treatments failed. Broader-token replication and prospective evidence remain
the confirmation route; no automatic additional parameter search.
