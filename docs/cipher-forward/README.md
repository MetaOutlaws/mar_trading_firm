# Four-book 3R forward paper comparison

Status: **candidate parity and isolated execution tests pass; server installation
and first future scan are still pending**. The user authorized paper deployment
after the preparation commit. See [DEPLOYMENT.md](DEPLOYMENT.md) for the runnable
installer, exact isolation boundary, operational checks and resume instructions.

The branch now includes the public-data worker, persistent indicator seed,
16 internal simulated portfolios, cost scenarios, opportunity records and a
prospective report. One paper service holds those portfolios. They are not
exchange accounts, testnet accounts, or subaccounts, and they are not new capital.
The installer creates its own service and state. It does not register strategies
with the existing worker or change its balances, positions, risk limits or flags.
The preparation receipts and protocol retain their original content and date;
the new runtime receipt is `RUNTIME_VALIDATION.json`.

## Exact comparison

| Book | Sources | New short risk ceiling / position cap |
|---|---|---|
| I | L01 long / F111 short hourly + original BL8 | None |
| IC | I + original 3R short | 1% / 10% |
| IM | I + original 3R short | 0.5% / 5% |
| IF | I + already-fixed filtered 3R short | 1% / 10% |

Each internal simulated portfolio starts with **20,000 USDT of simulated cash**,
15 slots and a 50% marked gross admission cap. That cash is not a deposit and
not an exchange balance. Hourly and BL8 retain 1% risk / 10% position caps in
every portfolio.
Half size scales only the challenger's two caps; remaining gross headroom is
not halved again. The same timestamped input snapshot feeds all books, but
their cash, positions, daily gates, C24 streaks and drawdown latches are separate.

Use the 15% paper drawdown entry stop in this prospective specification. The
70% stop was for the completed historical simulation. Changing it on the
running production paper book was not authorized by that simulation instruction.
This is a material bridge: do not present the historical returns as expected
results under the prospective 15% guard. Exits continue after entry stops.
Independent 2,000-USDT-per-signal opportunity records continue through
portfolio restrictions; they are overlapping counterfactuals, not simulated-portfolio
returns.

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
The parity verifier does not score new outcomes or tune rules. Runtime cash,
funding, restart, quote and causal-order checks are a separate test suite;
actual server market-data coverage and execution latency still need evidence.

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
modules remain on the open branch. Recent default-head exit-supervision and
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

## Installation and start condition

The original `INTEGRATION_HANDOFF.md` is retained as the acceptance checklist.
The implementation now satisfies the local execution checks; follow
`DEPLOYMENT.md` for the separate server build, warmup and activation evidence.
BL8 is a port verified byte-identical to PR #149 @0519f425; strategy logic not desk-reviewed. The runtime does not replace production.
Do not run its resize installer. The quote tick is fixed at 15 seconds;
research OHLC and forward depth fills remain different observation models.

Warm indicators separately before activation. Record a fixed seed boundary,
complete warmup source hashes and subsequent incremental inputs; never reseed
from a moving 800-hour window. Warmup is not a historical 2026 performance test.
After preparation, the worker records its first future hourly cutoff. Technical
activation is verified after that first completed forward scan, not before it.
There are no retrospective fills or synthetic start date.

Reports show four strategy comparisons, in fixed order I, IC, IM, IF. desk031,
baseline, and moderate stay prominent, with desk031 first. Severe is secondary
display only. The 16 portfolios are 16 looks at one idea, not 16 tests, and the
report does not rank them. The one BINDING statistic is the paired weekly
IC-minus-I P&L difference at desk031. IC and I book metrics are REPORT-ONLY.
Baseline, moderate, and severe keep their previous rates.
Severe stays secondary. Cost sidecars
must re-admit and resize independently, not simply subtract fees from another
portfolio's already-selected trades. The four variants never share simulated
budgets with each other or with cost sidecars.

Daily reports include simulated-portfolio returns, net R, drawdown, fees/funding, token,
sector, source and rejection breakdowns. Review operation at 30/60 days and the
fixed experiment at 90 days. Report the actual sample and uncertainty; elapsed
time alone does not establish profitability. Sparse or inconclusive evidence
continues under the same frozen rules, without an arbitrary trade-count veto
or outcome-driven tuning. Technical failures can stop new entries at any time
while existing positions remain supervised.

## Measured ledger growth

Retention is 10 days. The SQLite cap stays 1 GiB (1,073,741,824 bytes). The
figures below were measured on synthetic production-shaped inputs: 96 universe
symbols, 200-level books, the 15-second quote cadence, top-25 levels stored at
most every 15 minutes and hash-only otherwise, and 24 hourly history snapshots
per day. Each snapshot is 860 hourly bars plus 40 four-hour bars, with varying
synthetic prices so the compression is not a run of identical zeros. The clock
is the suite's synthetic pre-2026 fixture. No 2026 bars were used and nothing
was fetched. Tsuro's 51 MiB/day history estimate is not used.

| Component | Bytes/day | MiB/day |
|---|---:|---:|
| Quotes | 28,637,568 | 27.31 |
| History | 44,826,552 | 42.75 |
| Equity | 2,833,920 | 2.70 |
| Total | 76,298,040 | 72.76 |

Ten days of that total is 762,980,400 bytes (727.62 MiB), under the 1 GiB cap.
Sixteen portfolios do not multiply the shared quote feed or the history snapshots.
