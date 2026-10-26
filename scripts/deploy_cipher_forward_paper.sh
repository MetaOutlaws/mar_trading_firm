#!/usr/bin/env bash
# Authorized isolated PAPER trial only. Never operates the existing account.
set -euo pipefail
umask 077
test "$(hostname)" = mo-paper-vm-sgp1
test "$(id -u)" = 0
release=${1:?Usage: deploy_cipher_forward_paper.sh FULL_40_CHARACTER_COMMIT}
[[ "$release" =~ ^[0-9a-f]{40}$ ]]
command -v docker >/dev/null
command -v git >/dev/null
command -v python3 >/dev/null
command -v systemctl >/dev/null
exec 9>/var/lock/mar-cipher-forward-install.lock
flock -n 9
base=/opt/mar-cipher-forward
state=/data/state/cipher-forward-v1
service=mar-cipher-forward-paper.service
mkdir -p "$base/releases" "$state"
if [[ -f "$state/deployment.json" ]]; then
    python3 - "$state/deployment.json" "$release" <<'PY'
import json,sys
prior=json.load(open(sys.argv[1]))
if prior.get('release')!=sys.argv[2]:
    raise SystemExit('Different release already owns these books; use a separately reviewed upgrade, not an implicit migration')
PY
fi
if systemctl is-active --quiet "$service"; then
    echo 'Trial already running; use its status/report. This installer does not interrupt positions.'
    if [[ -f "$state/activation_evidence.json" ]]; then cat "$state/activation_evidence.json"; fi
    exit 0
fi
if docker ps --format '{{.Names}}' | grep -qx mar-cipher-forward-paper; then
    echo 'Existing comparison container is running outside this service; inspect before proceeding.' >&2
    exit 1
fi
test "$(docker inspect --format '{{.State.Running}}' mo-paper-paper-1)" = true
if [[ ! -d "$base/source.git" ]]; then
    git init --bare "$base/source.git"
    git --git-dir="$base/source.git" remote add origin https://github.com/MetaOutlaws/mar_trading_firm.git
fi
test "$(git --git-dir="$base/source.git" remote get-url origin)" = https://github.com/MetaOutlaws/mar_trading_firm.git
git --git-dir="$base/source.git" fetch --no-tags origin "$release"
test "$(git --git-dir="$base/source.git" rev-parse FETCH_HEAD)" = "$release"
dest="$base/releases/$release"
if [[ ! -d "$dest" ]]; then
    staging=$(mktemp -d "$base/releases/staging.XXXXXX")
    git --git-dir="$base/source.git" archive "$release" | tar -x -C "$staging"
    printf '%s\n' "$release" > "$staging/CIPHER_RELEASE_SHA"
    mv "$staging" "$dest"
fi
test "$(cat "$dest/CIPHER_RELEASE_SHA")" = "$release"
stamp=$(date -u +%Y%m%dT%H%M%SZ)
receipt="$state/install-$stamp"
mkdir "$receipt"
# Only mounts and selected non-secret declarations are observed. No .env or
# Docker environment dump is collected, printed or supplied to the new image.
docker inspect --format '{{json .Mounts}}' mo-paper-paper-1 > "$receipt/mounts.json"
context=$(python3 - "$receipt/mounts.json" <<'PY'
import json,sys
from pathlib import Path, PurePosixPath
target=PurePosixPath('/app/data/l01_4h_context')
matches=[]
for m in json.load(open(sys.argv[1])):
    dest=PurePosixPath(m['Destination'])
    if target==dest or dest in target.parents:
        matches.append((len(dest.parts),Path(m['Source'])/str(target.relative_to(dest))))
if not matches: raise SystemExit('No mounted L01 context found; cannot verify a read-only source')
path=max(matches,key=lambda x:x[0])[1].resolve(strict=True)
if not path.is_dir(): raise SystemExit('L01 context is not a directory')
print(path)
PY
)
[[ "$context" =~ ^/[A-Za-z0-9_./-]+$ ]]
# The comparison has to see the volume that holds the main paper book, not
# only its own state directory. The mount is read-only.
main_db=$(python3 - "$receipt/mounts.json" <<'PY'
import json, sys
from pathlib import Path, PurePosixPath
mounts=json.load(open(sys.argv[1]))
found=[]
for mount in mounts:
    source=Path(mount['Source'])
    destination=PurePosixPath(mount['Destination'])
    candidate=source/'firm.db'
    if candidate.is_file():
        found.append(candidate.resolve())
    elif destination==PurePosixPath('/app/data/firm.db') and source.is_file():
        found.append(source.resolve())
unique=[]
for path in found:
    if path not in unique:
        unique.append(path)
if len(unique)!=1:
    listed=', '.join(map(str, unique)) or 'none'
    raise SystemExit('expected exactly one mounted main paper firm.db; found '+listed)
print(unique[0])
PY
)
main_dir=$(dirname "$main_db")
main_name=$(basename "$main_db")
test -f "$main_db"
[[ "$main_dir" =~ ^/[A-Za-z0-9_./-]+$ ]]
[[ "$main_name" =~ ^[A-Za-z0-9_.-]+$ ]]
docker exec -i -w /app mo-paper-paper-1 python - < "$dest/scripts/audit_cipher_forward_runtime.py" > "$receipt/current-runtime-source.json"
docker exec -i -w /app mo-paper-paper-1 python - > "$receipt/current-paper-mode.json" <<'PY'
import json,os
from config.settings import get_settings
from core.strategy.f111_config import assert_f111_paper_only
assert_f111_paper_only()
s=get_settings()
assert not s.is_live and not os.environ.get('GO_LIVE_CONFIRMED')
print(json.dumps({'paper_only':True,'trading_mode':s.trading_mode.value,
 'scope':'paper-mode assertion; existing paper-book balances and overrides not changed'}))
PY
image="mar-cipher-forward:$release"
docker build --pull -f "$dest/docker/cipher-forward.Dockerfile" -t "$image" "$dest" > "$receipt/build.log" 2>&1
common=(--rm --read-only --cap-drop ALL --security-opt no-new-privileges --pids-limit 128 --cpus 1 --memory 1g --tmpfs /tmp:rw,noexec,nosuid,size=256m)
docker run "${common[@]}" --network none "$image" python -m pytest -q -p no:cacheprovider tests/test_cipher_forward.py tests/test_cipher_forward_runtime.py tests/test_cipher_forward_storage.py tests/test_cipher_forward_ruling.py > "$receipt/tests.log" 2>&1
docker image inspect --format '{{.Id}}' "$image" > "$receipt/image-id.txt"
if [[ -f "$state/trial.db" ]]; then
    python3 - "$state/trial.db" "$receipt/trial-before.db" <<'PY'
import sqlite3,sys
with sqlite3.connect('file:'+sys.argv[1]+'?mode=ro',uri=True) as source, sqlite3.connect(sys.argv[2]) as target:
    source.backup(target)
PY
fi
# Warmup freezes portfolio-config hashes and the code SHA first, then computes
# indicator state only. It cannot place simulated entries.
# This runs as a service so a disconnected SSH session does not kill the job.
cat > /etc/systemd/system/mar-cipher-forward-prepare.service <<EOF
[Unit]
Description=Prepare fixed indicators for isolated 3R paper comparison
After=docker.service network-online.target
Requires=docker.service
[Service]
Type=oneshot
TimeoutStartSec=2h
ExecStart=/usr/bin/docker run --rm --name mar-cipher-forward-prepare --read-only --cap-drop ALL --security-opt no-new-privileges --pids-limit 128 --cpus 1 --memory 1g --tmpfs /tmp:rw,noexec,nosuid,size=256m --mount type=bind,src=$state,dst=/state --mount type=bind,src=$context,dst=/context,readonly --mount type=bind,src=$main_dir,dst=/main-paper,readonly -e CIPHER_FORWARD_MAIN_PAPER_DB=/main-paper/$main_name -e CIPHER_FORWARD_MIN_FREE_BYTES=2147483648 -e CIPHER_FORWARD_LEDGER_MAX_BYTES=1073741824 -e CIPHER_FORWARD_LEDGER_MAX_AGE_MS=1209600000 $image python scripts/run_cipher_forward_paper.py --db /state/trial.db --warmup --context-root /context
ExecStartPost=/usr/bin/systemctl start --no-block $service
EOF
python3 - "$state" "$receipt" "$release" "$context" <<'PY'
import json,sys
from pathlib import Path
state,receipt=map(Path,sys.argv[1:3])
value=dict(release=sys.argv[3],image_id=(receipt/'image-id.txt').read_text().strip(),
 context_source=sys.argv[4],context_read_only=True,production_account_changed=False,
 credentials_supplied=False,installer_receipt=str(receipt),paper_only=True,
 local_runtime_tests_passed=True,server_tests_passed=True,activation_verified=False)
path=state/'deployment.json';tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(value,indent=2)+'\n');tmp.replace(path)
PY
# Initializing is separate and exclusive. A missing ledger beside a previous
# deployment is NOT permission to silently reset accumulated results.
if [[ ! -f "$state/trial.db" ]]; then
    if [[ -f "$state/status.json" || -f "$state/initialized.json" ]]; then
        echo 'Ledger missing beside prior trial state; restore/reconcile before continuing.' >&2
        exit 1
    fi
    docker run "${common[@]}" --network none --mount "type=bind,src=$state,dst=/state" --mount "type=bind,src=$main_dir,dst=/main-paper,readonly" -e CIPHER_FORWARD_MAIN_PAPER_DB=/main-paper/$main_name -e CIPHER_FORWARD_MIN_FREE_BYTES=2147483648 -e CIPHER_FORWARD_LEDGER_MAX_BYTES=1073741824 -e CIPHER_FORWARD_LEDGER_MAX_AGE_MS=1209600000 "$image" python scripts/run_cipher_forward_paper.py --db /state/trial.db --initialize > "$state/initialized.json"
else
    docker run "${common[@]}" --network none --mount "type=bind,src=$state,dst=/state" "$image" python scripts/run_cipher_forward_paper.py --db /state/trial.db --audit > "$receipt/ledger-reconciliation.json"
fi
cat > /etc/systemd/system/$service <<EOF
[Unit]
Description=Isolated four-book 3R forward PAPER comparison
After=docker.service network-online.target
Requires=docker.service
[Service]
Type=simple
Restart=on-failure
RestartSec=10
TimeoutStopSec=40
ExecStartPre=-/usr/bin/docker stop --timeout 10 mar-cipher-forward-paper
ExecStartPre=-/usr/bin/docker rm mar-cipher-forward-paper
ExecStart=/usr/bin/docker run --rm --name mar-cipher-forward-paper --read-only --cap-drop ALL --security-opt no-new-privileges --pids-limit 128 --cpus 1 --memory 1g --tmpfs /tmp:rw,noexec,nosuid,size=256m --mount type=bind,src=$state,dst=/state --mount type=bind,src=$context,dst=/context,readonly --mount type=bind,src=$main_dir,dst=/main-paper,readonly -e CIPHER_FORWARD_MAIN_PAPER_DB=/main-paper/$main_name -e CIPHER_FORWARD_MIN_FREE_BYTES=2147483648 -e CIPHER_FORWARD_LEDGER_MAX_BYTES=1073741824 -e CIPHER_FORWARD_LEDGER_MAX_AGE_MS=1209600000 $image
ExecStop=/usr/bin/docker stop --timeout 30 mar-cipher-forward-paper
[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable "$service"
if python3 - "$state/warmup.json" <<'PY'
import json,sys
from pathlib import Path
p=Path(sys.argv[1])
raise SystemExit(0 if p.exists() and json.loads(p.read_text()).get('ready') else 1)
PY
then
    systemctl start --no-block "$service"
    echo 'Resuming the existing isolated PAPER books; no balances or seed were reset.'
else
    systemctl start --no-block mar-cipher-forward-prepare.service
    echo 'Installed isolated PAPER comparison. Indicator preparation is running first.'
fi
echo 'This is not activation verification; the first complete future hourly scan is still required.'
echo 'Progress: journalctl -u mar-cipher-forward-prepare -u mar-cipher-forward-paper -f'
echo 'Evidence: /data/state/cipher-forward-v1/activation_evidence.json'
