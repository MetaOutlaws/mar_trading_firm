#!/usr/bin/env bash
# Owner-run, read-only evidence collector. No restart, order, migration or reset.
# Run on the existing Singapore host. Share stdout for the separate forward audit.
set -euo pipefail
umask 077
test "$(hostname)" = "mo-paper-vm-sgp1"
test "$(git -C /data/app rev-parse HEAD)" = "b00c4f73147f8319bc9c227c4f4ffb147fc87154"
# Tolerate only the overlay paths pinned in the helper. Each one passes only
# when the index and the worktree both hold that blob at that path's pinned
# mode (100755 for the executable pins, 100644 for every other pin).
# Any other dirty or staged path fails. Different bytes fail.
# The helper sits next to this script; extract both. A missing helper fails closed.
helper="$(cd "$(dirname "$0")" && pwd)/f111_repair_clean_tree.py"
test -f "$helper"
python3 "$helper" /data/app
# Label from the parity artifacts next to a full checkout of this commit.
# An extracted helper has neither file, so the label stays UNVERIFIED.
saved_path_parity=$(python3 - "$helper" <<'PY'
import importlib.util
import sys
from pathlib import Path

path = Path(sys.argv[1])
spec = importlib.util.spec_from_file_location("f111_repair_clean_tree", path)
if spec is None or spec.loader is None:
    raise RuntimeError("clean-tree helper could not be loaded")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
print(module.saved_path_parity(path.resolve().parent.parent))
PY
)
docker exec -w /app mo-paper-paper-1 python -c 'from core.strategy.f111_config import assert_f111_paper_only; assert_f111_paper_only()'
docker ps --format 'table {{.Names}}\t{{.Status}}'
systemctl show mar-l01-context.timer --property=ActiveState,SubState,LastTriggerUSec,NextElapseUSecRealtime
systemctl show mar-l01-context.service --property=ActiveState,SubState,Result,ExecMainStatus,ExecMainStartTimestamp,ExecMainExitTimestamp
docker exec -w /app mo-paper-paper-1 python scripts/verify_l01_paper.py --expected-commit b00c4f73147f8319bc9c227c4f4ffb147fc87154
docker exec -e F111_SAVED_PATH_PARITY="$saved_path_parity" -i -w /app mo-paper-paper-1 python - <<'PY'
import json,os,sqlite3,hashlib
from pathlib import Path
from datetime import datetime,timezone
from dataclasses import asdict
from core.execution.paper_cash import replay_events,merge_cash_events

def digest(data):return hashlib.sha256(data).hexdigest()
root=Path('/app/data');cashfile=root/'paper_cash.json';before=cashfile.read_bytes();cash=json.loads(before)
db=sqlite3.connect((root/'firm.db').as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row
db.execute('PRAGMA query_only=ON');db.execute('BEGIN')
tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
def rows(sql,args=()):return [dict(r) for r in db.execute(sql,args)]
positions=rows("SELECT id,symbol,side,mode,status,strategy,quantity,entry_price,entry_fee,notional,opened_at,closed_at,stop_loss_price,take_profit_price FROM positions WHERE mode='paper' AND (status!='closed' OR id IN (14,19,20)) ORDER BY id")
trades=rows("SELECT id,position_id,cash_event_id,symbol,side,strategy,entry_time,exit_time,gross_pnl,fees,entry_fees,exit_fees,funding,net_pnl,exit_reason,entry_slippage_bps,exit_slippage_bps FROM trades WHERE mode='paper' AND (exit_time>='2026-10-14 16:00:00' OR position_id IN (14,19,20)) ORDER BY exit_time,id")
extra=[]
if 'paper_cash_events' in tables:
 for r in rows("SELECT payload FROM paper_cash_events WHERE mode='paper' ORDER BY id"):
  v=r['payload'];extra.append(json.loads(v) if isinstance(v,str) else v)
merged=merge_cash_events(cash.get('events',[]),extra);replayed=asdict(replay_events(merged));replayed.pop('events',None)
totals=rows("SELECT count(*) AS closed_trades,sum(net_pnl) AS closed_net_pnl,sum(fees) AS fees,sum(funding) AS funding FROM trades WHERE mode='paper'")
db.rollback();db.close();after=cashfile.read_bytes()
snapshot={k:cash.get(k) for k in ['contributed_capital','cash','realised_pnl','total_fees','total_funding','accrued_funding','open_entry_fees','open_funding'] if k in cash}
parity=os.environ.get('F111_SAVED_PATH_PARITY','')
if parity not in ('PASS','FAIL','UNVERIFIED'):
 parity='UNVERIFIED'
report={'captured_at':datetime.now(timezone.utc).isoformat(),'cash_journal_unchanged_during_db_read':before==after,'cash_journal_sha256':digest(before),'cash_snapshot':snapshot,'cash_replay_with_durable_db_events':replayed,'cash_event_counts':{'json':len(cash.get('events',[])),'durable_db':len(extra),'merged':len(merged)},'paper_positions_and_activation_ids':positions,'post_activation_and_activation_position_trades':trades,'all_paper_trade_totals':totals,'saved_path_parity':parity,'note':'A stable read is evidence collection, not a full fill-path parity or restart reconciliation verdict.'}
report['durable_close_funding_coverage']=[{k:v for k,v in x.items() if k in ['event_id','position_id','symbol','ts','funding','funding_status','funding_source','funding_observed_through']} for x in extra]
for name in ['f111_paper_state.json','l01_activation_evidence.json']:
 p=root/name
 if p.exists():
  data=p.read_bytes();report[name]={'sha256':digest(data),'content':json.loads(data)}
telemetry=root/'f111_telemetry.jsonl'
if telemetry.exists():
 from collections import deque
 keep=['record_kind','deploy_marker','recorded_at','timestamp','source_signal_id','symbol','side','decision','rejection_reason','run_id','configuration_sha256','strategy_version','entry_price','exit_price','position_id','order_id','event','status']
 with telemetry.open() as stream:last=list(deque(stream,maxlen=30))
 report['latest_worker_telemetry']=[{k:v for k,v in json.loads(line).items() if k in keep} for line in last if line.strip()]
print(json.dumps(report,indent=2,default=str))
PY
python3 - <<'PY'
import json,sqlite3,hashlib
from pathlib import Path
backups=sorted(Path('/data/backups').glob('f111-execution-v2-*'),reverse=True)
root=None
for candidate in backups:
 p=candidate/'deployment.json'
 if p.is_file() and json.loads(p.read_text()).get('repair_commit')=='b00c4f73147f8319bc9c227c4f4ffb147fc87154':
  root=candidate;break
assert root is not None, 'No pre-upgrade backup for this repair commit'
result={'execution_repair_backup':str(root),'exists':root.exists(),'files':[]}
if root.exists():
 for p in sorted(root.rglob('*')):
  if p.name not in ['firm.db','paper_cash.json'] or not p.is_file():continue
  item={'relative_path':str(p.relative_to(root)),'bytes':p.stat().st_size}
  if p.name=='paper_cash.json':
   raw=p.read_bytes();data=json.loads(raw);item['sha256']=hashlib.sha256(raw).hexdigest();item['snapshot']={k:data.get(k) for k in ['contributed_capital','cash','realised_pnl','total_fees','total_funding','accrued_funding'] if k in data};item['cash_event_count']=len(data.get('events',[]))
  else:
   db=sqlite3.connect(p.as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row;db.execute('PRAGMA query_only=ON')
   item['paper_open_positions']=[dict(r) for r in db.execute("SELECT id,symbol,side,mode,status,strategy,quantity,entry_price,entry_fee,notional,opened_at,stop_loss_price,take_profit_price FROM positions WHERE mode='paper' AND status!='closed' ORDER BY id")]
   item['paper_closed_totals']=[dict(r) for r in db.execute("SELECT count(*) AS trades,sum(net_pnl) AS net_pnl FROM trades WHERE mode='paper'")];db.close()
  result['files'].append(item)
print(json.dumps(result,indent=2,default=str))
PY
