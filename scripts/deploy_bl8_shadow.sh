#!/usr/bin/env bash
# Owner-authorized isolated observer. Does not checkout/restart the hourly app.
set -euo pipefail
umask 077
test "$(hostname)" = "mo-paper-vm-sgp1"
test "$(id -u)" = 0
sha="${1:?Pass the reviewed full BL8 commit SHA}"
[[ "$sha" =~ ^[0-9a-f]{40}$ ]]
git -C /data/app cat-file -e "$sha^{commit}"
test "$(docker inspect -f '{{.State.Running}}' mo-paper-paper-1)" = true
docker exec -w /app mo-paper-paper-1 python -c 'from core.strategy.f111_config import assert_f111_paper_only; assert_f111_paper_only()'
root=/opt/mar-bl8
release="$root/releases/$sha"
state=/data/state/bl8-paper
mkdir -p "$root/releases" "$state"
chmod 700 "$root" "$root/releases" "$state"
stage="$(mktemp -d "$root/releases/.prepare-XXXXXX")"
trap 'rm -rf -- "$stage"' EXIT
git -C /data/app archive "$sha" \
 core/strategy/bl8.py core/execution/bl8_shadow.py \
 scripts/run_bl8_paper.py scripts/verify_bl8_paper.py \
 config/sleeves/mar_bl8_shadow_v1.json config/sleeves/mar_l01_long_f111_short_v1.json tests/test_bl8_shadow.py \
 docs/bl8-paper-validation/RELEASE_MANIFEST.json \
 | tar -x -C "$stage"
python3 - "$stage" <<'PY'
import hashlib,json,sys
from pathlib import Path
root=Path(sys.argv[1]);m=json.loads((root/'docs/bl8-paper-validation/RELEASE_MANIFEST.json').read_text())
assert m['local_validation']=='PASS' and m['historical_2026_opened'] is False
for name,sha in m['runtime_sha256'].items():
 assert hashlib.sha256((root/name).read_bytes()).hexdigest()==sha,name
PY
(cd "$stage" && PYTHONPATH="$stage" python3 -m unittest discover -s tests -p test_bl8_shadow.py -q)
printf '%s\n' "$sha" > "$stage/BL8_RELEASE_SHA"
if test -d "$release"; then
 diff -qr "$stage/core" "$release/core" --exclude=__pycache__
 diff -qr "$stage/scripts" "$release/scripts" --exclude=__pycache__
 cmp "$stage/config/sleeves/mar_bl8_shadow_v1.json" "$release/config/sleeves/mar_bl8_shadow_v1.json"
else
 mv "$stage" "$release"
 stage="$(mktemp -d "$root/releases/.cleanup-XXXXXX")"
fi
# Refuse a changed configuration against an existing book before starting anything.
python3 -I -S "$release/scripts/run_bl8_paper.py" --db "$state/paper.db" --audit
unit="$stage/mar-bl8-shadow.service"
cat > "$unit" <<UNIT
[Unit]
Description=BL8 isolated public-data paper validation
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$release
ExecStart=/usr/bin/python3 -I -S $release/scripts/run_bl8_paper.py --db $state/paper.db
Restart=on-failure
RestartSec=10
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$state
Environment=PYTHONDONTWRITEBYTECODE=1

[Install]
WantedBy=multi-user.target
UNIT
target=/etc/systemd/system/mar-bl8-shadow.service
if test -e "$target"; then
 cmp "$unit" "$target"
else
 install -m 0644 "$unit" "$target"
fi
systemctl daemon-reload
systemctl enable --now mar-bl8-shadow.service
systemctl is-active mar-bl8-shadow.service
printf 'BL8 observer started. Hourly checkout and worker were untouched.\n'
printf 'After the initial 96-symbol scan, verify with:\n'
printf 'python3 %q/scripts/verify_bl8_paper.py --db %q/paper.db --expected-commit %q\n' "$release" "$state" "$sha"
