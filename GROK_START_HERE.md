# Grok handover — current approval and completed RSI regime study, 8 October 2026

CURRENT approved PAPER rule: BTC + Connors + an extension cap ONLY in low-efficiency
conditions. This supersedes BTC+Connors without a cap and standalone Connors.
Read this file before any older checkpoint's START_HERE.md or installer.

## Exact deployment

`hourly_compression_btc_connors_loweff_v1`, BTCUSDT/ETHUSDT/SOLUSDT, LONG and SHORT,
1h. Original compression + own CRSI(3,2,100), LONG<=90 / SHORT>=10. ETH/SOL also
need matching completed BTC24 return >0 for LONG / <0 for SHORT; zero fails.
BTC's own-direction predicate is unchanged. SL2%, TP2.5%, no timeout.

Own-token ER24 is measured BEFORE the signal hour: abs(C[T-1h]-C[T-25h]) divided
by the 24 absolute hourly changes over those endpoints; T=entry time and these
closes are labelled by close time. Flat path gives ER0. At ER<0.30, require
extension<=1 priorATR14 beyond the prior20bar high/low breakout boundary.
At ER>=0.30, do not cap extension. Same constants in every year; no year labels.
Missing/gapped context fails closed. No RSI14/ADX filter has been added.

Six PAPER-only overrides: approved=false,paper_override=true. Replace exact known
original / standalone Connors / BTC+Connors entry rows, preserving unrelated
strategies, positions and their original exits, risk sizing, live-off state and
leverage. No duplicate hourly variants or new tokens. Parent strategy source
remains available for existing positions. Unknown modified records cause refusal.

## GitHub source and verification

Repository MetaOutlaws/mar_trading_firm. Review current branch heads:
- PR99, `codex/research-handover-20261006`: research/isolated_token_study_20261003/
  hourly_extension_regime_20261008/OWNER_APPROVAL.md and RESEARCH_ROADMAP.md.
- PR101, `codex/hourly-connors-paper-20261008`: historical branch name now contains
  the latest conditional-cap runtime, including PR100 baseline and BTC context hook.
- core/strategy/hourly_compression_btc_connors_loweff_v1.py
- scripts/enable_hourly_btc_connors_loweff.py
- scripts/deploy_hourly_btc_connors_loweff.py
- scripts/install_hourly_btc_connors_loweff_20261008.py
- LOWEFF_PARITY_VERIFICATION.json, LOWEFF_TEST_VERIFICATION.json,
  LOWEFF_INSTALLER_MANIFEST.json.

43 targeted tests passed. 143 research opportunities match full-history features,
gates and signals; 143 trailing850-hour checks and six complete signal frames
also pass. One unrelated API approved-count test remains excluded because local
FastAPI is unavailable. This verifies entries, not parity of production fills:
production sampled quotes, fill-relative brackets and shared-account occupancy
can differ from the frozen research minute-path model.

## Deploy and confirm actual scanning

Target Singapore mo-paper-vm-sgp1 (178.128.215.94), containers mo-paper-paper-1
and mo-paper-api-1. The authoring workspace has no reachable SSH session.
Do not report the new version installed/running from GitHub publication alone.
Inspect current code, mode, mounts, approval book and open positions first.

Run the pinned installer with HOST python3, not docker exec:
`python3 scripts/install_hourly_btc_connors_loweff_20261008.py`
SHA256:48e2a0f5ef6d90c7818be313909c5828d7d234291f72e37ec86d48a2dc496971

It validates PAPER mode and exact runtime interfaces, backs up changed code and
approval bytes, installs seven pinned modules, briefly stops approval-file
consumers, atomically updates the host file, restarts the same consumers and
verifies remounted bytes. Paper exit supervision pauses briefly during restart.
Unknown code/mount/approval differences cause refusal; reconcile those differences
in a reviewed patch, never bypass checks. For recreated containers, build from
committed source and retain persistent mounts/account data.

After activation and the next UTC hourly close, require a healthy completed cycle
within the first15 minutes so entry and BTC context checks were evaluated. Run:
`docker exec mo-paper-paper-1 python /app/scripts/enable_hourly_btc_connors_loweff.py --verify`

Require all six new keys, no duplicate earlier hourly entries, no errors/halt,
exit supervision active and preserved open positions. Check logs for fresh
own-token/BTC context. Zero signals is valid; do not force an order. Record the
installed commit, restart policies, cycle timestamp, plan, positions and command
output. `installed_awaiting_cycle` is not `scanning_verified`.

## Two requested historical checkpoint ZIPs

Both exact archives were recovered and verified locally; they are not release
assets yet. The current authoring connector supports repository text but does
not expose release asset uploads, and no authenticated CLI is available here.
Brian authorized publishing these archives. No further owner approval is needed
for an operator with the existing GitHub access to finish that upload.

- MAR_research_checkpoint_20261006.zip:344597378 bytes;
  SHA256 7d357d4b5176d8190ee8efdd42fb3a6bd02a0b2c94262dc8b04ea04c49d9dc92.
- MAR_entry_discovery_checkpoint_20261006.zip:334164151 bytes;
  SHA256 8667f9ffa8085e6c241f8e23bdba994154a8cf67b54c343aa3d28143cd1bd1cc.

The owner can download both exact files from this chat and give them to Grok.
Both contain historical research/raw parquet; all 618 and 145 internal manifest
hashes respectively were verified, plus archive CRC checks. Do not substitute
newer increment archives for these specifically requested originals.

They exceed GitHub's100MiB normal-file limit; use release assets. In PR99,
`handover/checkpoints_20261006/` contains CHECKPOINT_ASSETS.json and a standalone
`upload_research_checkpoints.py`. On an operator machine with authenticated `gh`
and both ZIPs in /path/to/checkpoints, run:

```bash
python3 handover/checkpoints_20261006/upload_research_checkpoints.py --directory /path/to/checkpoints
python3 handover/checkpoints_20261006/upload_research_checkpoints.py --directory /path/to/checkpoints --apply
```

The first command verifies local bytes. The second creates/reuses release tag
research-checkpoints-20261006, uploads missing assets without overwrite, downloads
both remote assets and compares hashes. Require RELEASE_UPLOAD_VERIFIED.json
and report its real release/download URLs. No release upload is claimed before
that succeeds. The helper's upload path has not been run by this chat.

## Research state

Conditional cap stressed means:2022–24 41 trades/15 stops/26 targets/+0.5003%;
2025 15 trades/3 stops/12 targets/+1.1993%. No-cap comparison:56/22/+0.3849%
and19/5/+0.9205%. Higher means do not establish certain profitability: historical
additive sum falls slightly, incremental intervals span zero, and2025 is reused.

The two6October ZIPs predate the hourly studies and this approval. Preserve their
original bytes and historical notes. For the latest hourly research use the
7October hourly base +8October extension-regime increment, then this approval
and current GitHub handover. Old deployment notes are superseded.

H-RSI-REGIME-01 is now complete. Read hourly_rsi_regime_20261008/FINDINGS.md in
PR99. RSI14 adds no value: low-efficiency-only changes no trades; always or
directional-only removes one historical stop and two winners, lowering stressed
mean+0.5003% to+0.4914%. All2025 variants remain15 trades/3 stops/+1.1993%.
No RSI policy passes the frozen point screen. Do not add RSI14 or retune thresholds.
23 focused tests,143 independent RSI and143 ER checks,16 admission replays pass.
No2026 outcomes scored. Runtime rule, installer and approval are unchanged.

Next research is independent confirmation, beginning with a provenance/coverage
audit of reserved2026 BTC/ETH/SOL data before a separate preregistered validation.
Only genuinely unused data can be called independent. Broader-token work awaits
new data. No automatic follow-on experiment or background monitor is running.
