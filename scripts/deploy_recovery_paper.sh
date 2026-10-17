#!/usr/bin/env bash
# Owner-authorized isolated comparison plus the current paper account top-up.
# Does not checkout an old branch over the running app or alter live limits.
set -euo pipefail
umask 077
test "$(hostname)" = mo-paper-vm-sgp1
test "$(id -u)" = 0
sha="${1:?Pass the full reviewed recovery release commit SHA}"
[[ "$sha" =~ ^[0-9a-f]{40}$ ]]
app=/data/app
git -C "$app" cat-file -e "$sha^{commit}"
test "$(docker inspect -f '{{.State.Running}}' mo-paper-paper-1)" = true
test "$(docker inspect -f '{{.State.Running}}' mo-paper-api-1)" = true
docker exec -w /app mo-paper-paper-1 python -c 'from core.strategy.f111_config import assert_f111_paper_only; assert_f111_paper_only()'
if systemctl is-active --quiet mar-recovery-paper.service; then
  printf 'Recovery service already runs. Verify its status; do not duplicate it.\n' >&2
  exit 1
fi
# Resolve actual mounted paths rather than assume the old deployment layout.
mount_json="$(docker inspect -f '{{json .Mounts}}' mo-paper-paper-1)"
python3 - "$mount_json" "$app" <<'PY'
import json,sys
from pathlib import Path
mounts=json.loads(sys.argv[1]);path='/app/core/risk/limits.py'
matches=[m for m in mounts if path==m['Destination'] or path.startswith(m['Destination'].rstrip('/')+'/')]
if not matches: raise SystemExit('Current source is not bind-mounted; reconcile the image deployment first')
m=max(matches,key=lambda m:len(m['Destination']))
actual=(Path(m['Source'])/path[len(m['Destination']):].lstrip('/')).resolve()
if actual!=(Path(sys.argv[2])/'core/risk/limits.py').resolve(): raise SystemExit('Unexpected current source mount')
PY
data="$(python3 - "$mount_json" <<'PY'
import json,sys
from pathlib import Path
mounts=json.loads(sys.argv[1]);matches=[m for m in mounts if '/app/data'==m['Destination'] or '/app/data'.startswith(m['Destination'].rstrip('/')+'/')]
if not matches: raise SystemExit('Cannot resolve the paper data mount')
m=max(matches,key=lambda m:len(m['Destination']))
path=Path(m['Source'])/('/app/data'[len(m['Destination']):].lstrip('/'))
print(path.resolve())
PY
)"
test -f "$data/paper_cash.json"
test -f "$data/firm.db"
test -d "$data/l01_4h_context"
docker exec -w /app mo-paper-paper-1 python -c 'from pathlib import Path; import hashlib; print(hashlib.sha256(Path("core/risk/limits.py").read_bytes()).hexdigest())' > /run/mar-recovery-limits.sha
test "$(sha256sum "$app/core/risk/limits.py" | cut -d ' ' -f1)" = "$(cat /run/mar-recovery-limits.sha)"
release="/opt/mar-recovery/releases/$sha"
state=/data/state/recovery-paper-v1
mkdir -p /opt/mar-recovery/releases "$state" /data/backups
chmod 700 /opt/mar-recovery /opt/mar-recovery/releases "$state"
if test -e "$release"; then
  test "$(cat "$release/RECOVERY_RELEASE_SHA")" = "$sha"
else
  stage="$(mktemp -d /opt/mar-recovery/releases/.prepare-XXXXXX)"
  git -C "$app" archive "$sha" core config scripts tests docs/recovery-paper | tar -x -C "$stage"
  printf '%s\n' "$sha" > "$stage/RECOVERY_RELEASE_SHA"
  mv "$stage" "$release"
fi
image="mar-recovery-paper:${sha:0:12}"
docker build --label "mar.release=$sha" -t "$image" -f "$release/docs/recovery-paper/Dockerfile" "$release/docs/recovery-paper"
docker run --rm --network none -v "$release:/research:ro" "$image" \
  -c 'import sys,unittest;sys.path.insert(0,"/research");s=unittest.defaultTestLoader.discover("/research/tests",pattern="test_recovery_paper.py");r=unittest.TextTestRunner(verbosity=1).run(s);raise SystemExit(not r.wasSuccessful())'
# Complete the dry run before stopping the running account.
docker run --rm --network none -v "$release:/research:ro" -v "$app:/current-app:ro" \
  -v "$data:/current-data:ro" "$image" /research/scripts/resize_paper_account.py \
  --app-root /current-app --data-root /current-data --backup-root /backups > "$state/resize-preview.json"
if test -f "$state/paper.db"; then
  docker run --rm --network none -v "$release:/research:ro" -v "$state:/state" "$image" \
    /research/scripts/run_recovery_paper.py --db /state/paper.db --audit > "$state/prestart-audit.json"
else
  if test -e "$state/status.json" || test -e "$state/initialized.json"; then
    printf 'Prior trial state exists but its database is missing. Restore it; do not start a replacement book.\n' >&2
    exit 1
  fi
  docker run --rm --network none -v "$release:/research:ro" -v "$state:/state" "$image" \
    /research/scripts/run_recovery_paper.py --db /state/paper.db --initialize > "$state/initialized.json"
fi
# Stop both writers. On an interruption, restart the existing services;
# the resize is idempotent and never removes old cash events.
stopped=0
restart_existing() {
  if test "$stopped" = 1; then
    docker start mo-paper-paper-1 mo-paper-api-1
  fi
}
trap restart_existing EXIT
stopped=1
docker stop --timeout 60 mo-paper-paper-1 mo-paper-api-1
test "$(docker inspect -f '{{.State.Running}}' mo-paper-paper-1)" = false
test "$(docker inspect -f '{{.State.Running}}' mo-paper-api-1)" = false
docker run --rm --network none -e MAR_PAPER_CONTAINERS_STOPPED=yes \
  -v "$release:/research:ro" -v "$app:/current-app" -v "$data:/current-data" \
  -v /data/backups:/backups "$image" /research/scripts/resize_paper_account.py \
  --app-root /current-app --data-root /current-data --backup-root /backups --apply > "$state/resize-applied.json"
docker start mo-paper-paper-1 mo-paper-api-1
stopped=0
trap - EXIT
docker exec -w /app mo-paper-paper-1 python -c 'from core.strategy.f111_config import assert_f111_paper_only;from core.risk.limits import PAPER_LIMITS;assert_f111_paper_only();assert PAPER_LIMITS.max_concurrent_positions==15;assert PAPER_LIMITS.max_risk_per_trade_pct==.01;assert PAPER_LIMITS.max_position_pct==.1;print("Current account: paper mode; max 15 positions; 1% risk; 10% position cap")'
cat > /etc/systemd/system/mar-recovery-paper.service <<UNIT
[Unit]
Description=MAR NONE/C24 paper accounts and independent opportunities
After=docker.service network-online.target
Requires=docker.service
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/bin/docker run --rm --name mar-recovery-paper --read-only --cap-drop ALL --security-opt no-new-privileges --tmpfs /tmp:rw,noexec,nosuid,size=128m --cpus 1.5 --memory 1500m -v $release:/research:ro -v $state:/state -v $data/l01_4h_context:/context:ro $image /research/scripts/run_recovery_paper.py --db /state/paper.db --context-root /context
ExecStop=/usr/bin/docker stop --timeout 30 mar-recovery-paper
Restart=on-failure
RestartSec=10
TimeoutStopSec=45
UMask=0077

[Install]
WantedBy=multi-user.target
UNIT
cat > /etc/systemd/system/mar-recovery-report.service <<UNIT
[Unit]
Description=Audit and render MAR recovery paper results
After=mar-recovery-paper.service

[Service]
Type=oneshot
ExecStart=/usr/bin/docker run --rm --network none --read-only --cap-drop ALL --security-opt no-new-privileges --tmpfs /tmp:rw,noexec,nosuid,size=64m -v $release:/research:ro -v $state:/state $image /research/scripts/report_recovery_paper.py --db /state/paper.db --expected-commit $sha --output /state/evidence.json --html /state/report.html
UMask=0077
UNIT
cat > /etc/systemd/system/mar-recovery-report.timer <<'UNIT'
[Unit]
Description=Refresh recovery paper evidence and report every five minutes

[Timer]
OnBootSec=2min
OnUnitActiveSec=5min
Persistent=true

[Install]
WantedBy=timers.target
UNIT
systemctl daemon-reload
systemctl enable --now mar-recovery-paper.service mar-recovery-report.timer
printf 'Installed and started. Runtime validation remains pending the first full forward-hour scan.\n'
printf 'Current-account receipt: %s/resize-applied.json\n' "$state"
printf 'Comparison heartbeat: %s/status.json\n' "$state"
printf 'Comparison report: %s/report.html\n' "$state"
printf 'Verification: systemctl start mar-recovery-report.service; cat %s/evidence.json\n' "$state"
