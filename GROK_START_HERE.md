# Grok handover — latest owner direction, 8 October2026 08:11 Dubai

Brian explicitly approves BTC + Connors for the existing Singapore PAPER account.
This supersedes the earlier standalone Connors preference. Read this file before
older deployment notes. Do NOT run the old standalone Connors installer.

## Exact approved strategy

`hourly_compression_btc_connors_v1`, BTCUSDT/ETHUSDT/SOLUSDT, LONG and SHORT, 1h.
Original hourly compression + own-token CRSI(3,2,100), LONG<=90 / SHORT>=10.
ETH/SOL additionally require the matching completed BTC24 return >0 for LONG,
<0 for SHORT; zero fails. BTC retains its original own-direction predicate.
SL2%, TP2.5%, no timeout. Missing/gapped BTC context blocks entries; no fill or
fallback. Only completed matching hourly bars; the engine supplies market context.

Six PAPER-only overrides: approved=false,paper_override=true. Retire the exact
six original and/or six standalone Connors entry rows; never run duplicate hourly
variants. Preserve unrelated strategies, live-off state, risk sizing and leverage,
existing open positions and their original exit supervision. Approval is for
three tested tokens only; more tokens need data and validation.

## What to review on GitHub

Repository MetaOutlaws/mar_trading_firm.
- PR99, branch codex/research-handover-20261006: research/isolated_token_study_20261003/
  RESEARCH_ROADMAP.md and hourly_btc_connors_interaction_20261008/OWNER_APPROVAL.md.
- PR101, branch codex/hourly-connors-paper-20261008: latest runtime update now
  implements BTC + Connors; branch name is historical. It includes PR100 baseline
  code. Review the latest head, not just the earlier standalone commit c0d1328.
- core/strategy/hourly_compression_btc_connors_v1.py; the requires_btc_confirmation
  hook in core/execution/engine.py; scripts/enable_hourly_btc_connors.py;
  scripts/deploy_hourly_btc_connors.py and its pinned standalone installer.
- BTC_CONNORS_PARITY_VERIFICATION.json and BTC_CONNORS_TEST_VERIFICATION.json.

Entry parity:143 full research opportunities,143 trailing850-hour windows and
six full signal frames checked. 37 targeted tests pass. One unrelated API-count
test cannot run locally because FastAPI is unavailable; this limitation is
recorded, not hidden. Production sampled quotes, fill-relative brackets and
shared-account risk/occupancy differ from research minute-path execution.

## Deploy with existing cloud access and verify

Target mo-paper-vm-sgp1,178.128.215.94; containers mo-paper-paper-1 and mo-paper-api-1.
The authoring workspace could not reach SSH. No claim of installed/running BTC+
Connors has been made. Inspect current mode, code, mounts, approval book and open
positions first; do not rebuild the VM or replace the whole approval book.

Fetch the latest PR101 head. The HOST-side pinned standalone installer is:
`scripts/install_hourly_btc_connors_20261008.py`.
Run with host python3 (not through docker exec). It checks existing runtime and
PAPER mode, installs only exact payloads, backs up changed code/approval bytes,
stops existing approval-file consumers briefly, atomically replaces the host
approval file and restarts them so Docker file binds see the new inode. This
briefly pauses paper exit supervision. Unknown changed code/mounts/approvals
cause refusal. If code has evolved, reconcile the specific difference in a new
reviewed patch; do not bypass hashes or overwrite unrelated work. For rebuilt
images, use committed source and preserve the same configuration safeguards.

After installation and the next hourly close, run:
`docker exec mo-paper-paper-1 python /app/scripts/enable_hourly_btc_connors.py --verify`

Require a fresh completed cycle after activation, preferably in the first15
minutes after the UTC hourly close so the entry rule and BTC context were actually
evaluated. Confirm all six combination keys, no duplicate original/standalone
keys, no errors or entry halt, and exit supervision running. Confirm candle/BTC
context health from logs; zero signals is a valid result. Do not force an order
to prove scanning. Record deployed commit, restart policies, cycle timestamp,
plan keys, open-position preservation and verification output in the handover.
`installed_awaiting_cycle` is not `scanning_verified`; an active VM is not proof.

Closing the owner's PowerShell does not stop Docker. Code patches persist across
container restart but require the committed source if an older image recreates
the containers. Preserve config mounts and durable account data.

## Research selection and next candidate

Approved combination:2022–24 56 trades,22 stops,34 targets,+0.3849% stressed mean;
2025 19 trades,5 stops,14 targets,+0.9205%. Versus standalone Connors this saves4
historical stops with no lost targets and leaves2025 exactly unchanged. The older
strict experiment flag remains false; owner's PAPER selection expressly accepts
historical improvement with unchanged2025. This is not independent edge proof.

New extension-regime experiment is research ONLY. Do not add an extension cap,
RSI14, ADX or regime switch to the approved deployment without later owner
approval. Read hourly_extension_regime_20261008/FINDINGS.md in PR99 for results.
Next queued is the isolated RSI regime study with the same fixed causal state.
No2026 price outcomes scored; broader-token/prospective confirmation remains open.
