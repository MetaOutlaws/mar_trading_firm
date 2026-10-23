# Four-book 3R forward comparison — preparation

Status: **candidate port verified; funded forward worker not implemented or
activated by this change**. This is the next preparation step after
MAR-3R-ALLOCATION-08, not another performance-optimization sweep.

The branch contains a frozen candidate evaluator, four-book routing and sizing
contracts, a private-fixture parity command, a read-only runtime audit, and the
prospective protocol. None is registered with the production strategy worker.
No balance, position, risk setting, timer, kill switch or deployed file changes.

## Exact comparison

| Book | Sources | New short risk ceiling / position cap |
|---|---|---|
| I | L01 long / F111 short hourly + original BL8 | None |
| IC | I + original 3R short | 1% / 10% |
| IM | I + original 3R short | 0.5% / 5% |
| IF | I + already-fixed filtered 3R short | 1% / 10% |

Each book starts with its **own 20,000 USDT**, 15 slots and 50% marked gross
admission cap. Hourly and BL8 retain 1% risk / 10% position caps in every book.
Half size scales only the challenger's two caps; remaining gross headroom is
not halved again. The same timestamped input snapshot feeds all books, but
their cash, positions, daily gates, C24 streaks and drawdown latches are separate.

Use the 15% paper drawdown entry stop in this prospective specification. The
70% stop was for the completed historical simulation. Changing it on the
running account was not authorized by that simulation instruction. This is
a material bridge: do not present the historical returns as expected results
under the prospective 15% guard. Exits continue after entry stops. Independent
2,000-USDT-per-signal opportunity records continue through account restrictions;
they are overlapping counterfactuals, not attainable account ROI.

No token whitelist, new target, late profit lock, maximum holding period,
new ranking rule or parameter grid. The fixed filtered variant uses prior
24-hour turnover >= 2,835,443.3309875005 USDT and structural stop distance
<= 4.818264711062109 percent, exactly as researched.

## Signal and implementation parity

`research/cipher_forward/features.py` retains the frozen research arithmetic.
Only the optional Numba import/decorator was removed. The port requires complete
UTC hourly OHLCV **and actual turnover**, an empty fixed seed boundary, and
missing-hour rows rather than interpolation. Do not substitute volume-times-
close for turnover. The 4h short context is strictly earlier than the signal
close; the older hourly L01 long context has its own unchanged convention.

`strategy.py` maps the W11S short confluence to the T30 target. The 3R target
uses the **signal-close-to-structural-stop distance**, while trade R uses the
**entry-fill-to-original-stop distance**. Admission still uses the original
2R target's fee/slippage-aware 1.5 minimum planned reward/risk. Using the 3R
target to pass that gate silently changes the strategy and is prohibited.

The historical candidate inputs cover only 2022–2025. The endpoint labelled
2026-01-01 00:00 is the final completed 2025 candle, not a 2026 trading sample.
The parity verifier does not score new outcomes or tune rules. Full execution,
ledger, funding, cash and forward-feed parity remain separate required checks.

```bash
python -m pytest -q tests/test_cipher_forward.py
python scripts/verify_cipher_forward_parity.py \
  --features /PRIVATE/mar_volume_range_20261021/features \
  --signals /PRIVATE/mar_cipher_test_20261022/results/signals.parquet \
  --paths /PRIVATE/mar_cipher_test_20261022/results/paths.parquet \
  --late-paths /PRIVATE/mar_cipher_portfolio_20261022/inputs/late_paths.parquet \
  --output /PRIVATE/candidate-parity.json
```

The external parity command additionally requires `pyarrow`. Fixtures are not
in this public repository. Their hashes and the successful local receipt are
in `CANDIDATE_PARITY.json`; a fresh clone can run the synthetic tests, but cannot
claim private-data reproduction without those fixtures.

## Runtime reconciliation

Read `SOURCE_RECONCILIATION.json`. The inspected default head is
`4d70db57ba6c665a25d9c54bf3aacc386baf697b`; PR #149's current head is
`0519f425369b0fde68f6559719ab4a233f59e013`, later than the old recorded
`ecf709dc...` release. PR #149 remains draft/unmerged. Default-branch risk
declarations are 15 slots, 1%/10%, **80% gross**, and **15% drawdown**.
These are source observations, not proof of the effective remote settings.

The historical A00 control is L01 long / unchanged F111 short, not a different
new strategy. Its hourly protection and L01 context source files are unchanged
between the historical pin and inspected default head. BL8 and recovery trial
modules still live on the open branch. Recent default-head exit-supervision and
ledger fixes must not be lost by installing an older branch over production.

To collect declarations from the actual running paper container, an operator
with the repository available can run this **read-only** command:

```bash
docker exec -i -w /app mo-paper-paper-1 python - --root /app \
  < scripts/audit_cipher_forward_runtime.py > /tmp/cipher-runtime-audit.json
```

This emits selected non-secret source hashes/settings only. It does not prove
worker activity, cash, fills, configured overrides or reconciliation. Attach
fresh worker and ledger evidence separately; never infer deployment from a PR
merge or a local test. No remote execution was performed for this preparation.

## Remaining implementation and start condition

Follow `INTEGRATION_HANDOFF.md`. Build one isolated four-book executor and
independent opportunity recorder, reusing reviewed concepts from PR #149 while
preserving newer production fixes. Do not run its account-resize installer.
Fix and record the forward quote sampling/exit cadence in the execution release;
research OHLC and forward depth fills are different observation models.

Warm indicators separately before activation. Record a fixed seed boundary,
complete warmup source hashes and subsequent incremental inputs; never reseed
from a moving 800-hour window. Warmup is not a historical 2026 performance test.
The trial starts only at the first full future signal after the verified
activation timestamp. There are no retrospective fills or synthetic start date.

Baseline and moderate cost accounts are primary. Severe is a secondary stress,
not the sole rejection gate. Cost sidecars must re-admit and resize independently,
not simply subtract fees from another book's already-selected trades. The four
portfolio variants never share budgets with each other or with cost sidecars.

Daily reports include account returns, net R, drawdown, fees/funding, token,
sector, source and rejection breakdowns. Review operation at 30/60 days and the
fixed experiment at 90 days. Report the actual sample and uncertainty; elapsed
time alone does not establish profitability. Sparse or inconclusive evidence
continues under the same frozen rules, without an arbitrary trade-count veto
or outcome-driven tuning. Technical failures can stop new entries at any time
while existing positions remain supervised.
