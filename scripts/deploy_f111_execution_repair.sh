#!/usr/bin/env bash
# Owner-run deployment through the existing Singapore SSH session.
set -euo pipefail
umask 077

# Same helper as the collector. While HEAD is still the L01 base (868f1c9a),
# only the ten pinned overlay paths may differ, and only when both the index
# and the worktree are that blob at mode 100644. Any other dirty path fails.
# A missing helper fails closed.
f111_deploy_clean_preflight() {
  local repo=$1
  local helper
  helper="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/f111_repair_clean_tree.py"
  test -f "$helper"
  python3 "$helper" "$repo"
}

if [[ "${BASH_SOURCE[0]}" != "$0" ]]; then
  return 0
fi

repair_sha=${1:?Supply the reviewed full repair commit SHA}
[[ "$repair_sha" =~ ^[0-9a-f]{40}$ ]]
test "$(hostname)" = mo-paper-vm-sgp1
base_sha=868f1c9a7a34c240dd81fb0c4b2f25b02455d4a4
test "$(git -C /data/app rev-parse HEAD)" = "$base_sha"
f111_deploy_clean_preflight /data/app
git -C /data/app cat-file -e "$repair_sha^{commit}"
git -C /data/app merge-base --is-ancestor "$base_sha" "$repair_sha"
docker exec -w /app mo-paper-paper-1 python -c 'from core.strategy.f111_config import assert_f111_paper_only; assert_f111_paper_only()'
data_root=$(python3 - <<'PY'
import json,subprocess
roots=[]
for name in ['mo-paper-paper-1','mo-paper-api-1']:
    c=json.loads(subprocess.check_output(['docker','inspect',name]))[0]
    assert c['State']['Running'], name
    mounts={x['Destination']:x['Source'] for x in c['Mounts']}
    assert mounts.get('/app')=='/data/app', 'Unexpected code mount'
    root=mounts.get('/app/data','')
    assert root.startswith('/data/state/') or root=='/data/state', 'Unexpected data mount'
    roots.append(root)
assert roots[0]==roots[1], 'Data mounts differ'
print(roots[0])
PY
)
test ! -e "$data_root/f111_paper_scan_disabled"
docker stop --timeout 30 mo-paper-paper-1
trap 'printf "%s\n" "Deployment stopped before completion. Inspect the failure and backup before restarting the paper worker." >&2' ERR
python3 - "$data_root" "$base_sha" "$repair_sha" <<'PY'
import json,shutil,sqlite3,sys
from datetime import datetime,timezone
from pathlib import Path
root=Path(sys.argv[1]); backup=Path('/data/backups')/('f111-execution-v2-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
backup.mkdir(parents=True,mode=0o700)
assert (root/'firm.db').is_file() and (root/'paper_cash.json').is_file()
with sqlite3.connect(f'file:{root/"firm.db"}?mode=ro',uri=True) as src,sqlite3.connect(backup/'firm.db') as dst:
    src.backup(dst)
    assert dst.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
for name in ['paper_cash.json','f111_paper_state.json','l01_paper_enabled.json','approved_strategies.json']:
    p=root/name
    if p.exists():shutil.copy2(p,backup/name)
(backup/'deployment.json').write_text(json.dumps({'base_commit':sys.argv[2],'repair_commit':sys.argv[3],'data_root':str(root)},indent=2)+'\n')
print('BACKUP_OK:',backup)
PY
git -C /data/app switch --detach "$repair_sha"
printf '%s\n' "$repair_sha" > /data/app/GIT_SHA
printf '%s\n' "$repair_sha" > "$data_root/DEPLOYED_SHA"
docker exec -w /app mo-paper-api-1 python scripts/upgrade_f111_execution.py --apply
docker restart --timeout 30 mo-paper-api-1
docker start mo-paper-paper-1
trap - ERR
printf '%s\n' 'Execution repair installed. Verify the worker restart and reconcile the saved book next.'
