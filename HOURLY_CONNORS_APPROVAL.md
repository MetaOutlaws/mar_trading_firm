> SUPERSEDED 8 October2026 08:11 Dubai: owner now approves BTC + Connors. Read GROK_START_HERE.md and use scripts/install_hourly_btc_connors_20261008.py. The standalone instructions below are historical.

# Activate the approved standalone Connors hourly paper sleeve

Status: owner approved; code and installer tested; cloud installation and scanning
NOT YET VERIFIED. Singapore VM is active, but this workspace cannot reach SSH.

Download `enable_hourly_connors_20261008.py` to your Windows Downloads folder.
Open Windows PowerShell (the prompt should start `PS`, not `root@`). Run:

```powershell
Get-Content -Raw "$env:USERPROFILE\Downloads\enable_hourly_connors_20261008.py" | ssh -o ConnectTimeout=15 -i "$env:USERPROFILE\Downloads\mo-paper-vm-ops_id_ed25519" root@178.128.215.94 "python3 -"
```

This uses your existing SSH key. Do not put passwords or private keys in chat.
It installs six PAPER-only BTC/ETH/SOL LONG/SHORT 1h configurations: original
compression plus CRSI(3,2,100), LONG<=90 / SHORT>=10, SL2% / TP2.5%, no timeout.
It retires only the exact six original hourly baseline entry records, preserving
all unrelated records. Existing positions retain their exits. No BTC filter is
added and no live/risk/leverage configuration is changed.

It validates pinned runtime code, PAPER mode and approval-file consumers before
writing, saves the original approval book, and briefly restarts the existing
paper/API containers so Docker remounts the new approval file correctly. Exit
supervision pauses during this restart. Unexpected code, mounts or changed
hourly records cause a refusal instead of an overwrite. Run on the HOST via SSH,
not inside `docker exec`. The patch survives container restart; container
recreation from an older image requires deployment of the committed source again.

After the next scheduled scan completes, verify:

```powershell
ssh -o ConnectTimeout=15 -i "$env:USERPROFILE\Downloads\mo-paper-vm-ops_id_ed25519" root@178.128.215.94 "docker exec mo-paper-paper-1 python /app/scripts/enable_hourly_connors.py --verify"
```

Success must say `scanning_verified`, list all six `hourly_compression_connors_v1`
sleeves, and identify a healthy completed cycle newer than activation and less
than 30 minutes old, with exit supervision and no errors. `installed_awaiting_cycle`
means installation succeeded but scanning has not yet been verified. Paste the
installer and verification output if either refuses or fails; do not bypass a
pinned-code/configuration mismatch. Closing PowerShell after installation does
not stop the Docker engine. A separate dashboard SSH tunnel closes with its
PowerShell session.

Validation: 17 focused tests, 143 full-history feature/predicate comparisons,
143 trailing-window comparisons (maximum CRSI difference zero), six full-history
signal frames. This establishes entry parity, not production return parity:
production uses sampled quotes, fill-relative brackets, common account risk and
other strategy occupancy; historical research uses the frozen minute-path model.
