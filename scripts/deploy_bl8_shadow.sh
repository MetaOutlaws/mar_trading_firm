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
if systemctl is-active --quiet mar-bl8-shadow.service; then
  printf 'mar-bl8-shadow.service is running. Stop only that unit, then re-run. Do not restart the hourly container.\n' >&2
  exit 1
fi
root=/opt/mar-bl8
release="$root/releases/$sha"
state=/data/state/bl8-paper
mkdir -p "$root/releases" "$state"
chmod 700 "$root" "$root/releases" "$state"
stage="$(mktemp -d "$root/releases/.prepare-XXXXXX")"
trap 'rm -rf -- "$stage"' EXIT
git -C /data/app archive "$sha" \
 core/strategy/bl8.py core/execution/bl8_shadow.py core/execution/bl8_public.py \
 core/risk/limits.py core/risk/sizing.py \
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
# A changed sizing rule refuses the previous book. Preserve that file; do not delete it.
if ! python3 -I -S "$release/scripts/run_bl8_paper.py" --db "$state/paper.db" --audit; then
  printf 'Existing BL8 book refused this release. Preserve %s/paper.db and its -wal/-shm files, move them aside, and re-run. Do not delete them. Hourly state was not touched.\n' "$state" >&2
  exit 1
fi
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
Environment=BL8_PUBLIC_CONCURRENCY=2
Environment=BL8_PUBLIC_MIN_INTERVAL_S=0.2
Environment=BL8_PUBLIC_MAX_ATTEMPTS=5

[Install]
WantedBy=multi-user.target
UNIT
target=/etc/systemd/system/mar-bl8-shadow.service
install -m 0644 "$unit" "$target"
systemctl daemon-reload
systemctl enable mar-bl8-shadow.service
if systemctl is-active --quiet mar-bl8-shadow.service; then
  printf 'mar-bl8-shadow.service became active. This installer leaves it stopped.\n' >&2
  exit 1
fi
printf 'BL8 release installed and left stopped. Hourly checkout and worker were untouched.\n'
printf 'Start only when the owner asks:\n'
printf 'systemctl start mar-bl8-shadow.service\n'
printf 'After the initial 96-symbol scan, verify with:\n'
printf 'python3 %q/scripts/verify_bl8_paper.py --db %q/paper.db --expected-commit %q\n' "$release" "$state" "$sha"
