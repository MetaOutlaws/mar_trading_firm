#!/usr/bin/env python3
"""Offline, idempotent capital top-up; preserve all trades and protective state.

Called by deploy_recovery_paper.sh only while BOTH current account containers
are stopped. No initial-equity reset and no edits to positions or kill switches.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import sqlite3
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from core.execution.paper_cash import replay_events

EVENT_ID='owner-paper-capital-20261017-20000-v1'

# Oct 9 desktop backfill closes, paper_cash_events ids 11-17.
# Payload is {backfill, source_trade_id, net, cash_after} and has no event_id.
# Measured against the matching journal: net == gross_pnl - fee - entry_fee + funding
# on all seven rows (residual under 1e-14). entry_fee and funding are 0, so this
# is the same number as the cash-replay close, which subtracts funding. These
# rows do not distinguish the funding sign. cash_after is the journal field,
# not a from-zero replay of these seven closes (earlier history sits in that balance).
LEGACY_BACKFILL_CLOSE_DESKTOP=re.compile(r'^backfill-close:desktop:\d+$')
LEGACY_BACKFILL_CLOSE_NET_TOLERANCE=1e-6


def legacy_backfill_close_desktop(row, payload):
    """Named rule for the legacy desktop backfill-close shape. Nothing else.

    event_id matches ^backfill-close:desktop:\\d+$, kind is close, payload.backfill
    is true, and the payload has source_trade_id, net and cash_after and no event_id.
    """
    if not isinstance(payload, dict) or not isinstance(row['event_id'], str):
        return False
    if LEGACY_BACKFILL_CLOSE_DESKTOP.fullmatch(row['event_id']) is None:
        return False
    if row['kind']!='close' or payload.get('backfill') is not True or 'event_id' in payload:
        return False
    return all(key in payload for key in ('source_trade_id','net','cash_after'))


def reconcile_legacy_backfill_close(row, payload, journal):
    """Reconcile one legacy backfill-close row against its cash-journal entry.

    The journal entry must exist with the same event_id and symbol, the same
    source_trade_id and the same cash_after. Payload net must equal
    gross_pnl - fee - entry_fee + funding within 1e-6. A miss raises; it does
    not fall through to a softer check.
    """
    event_id=row['event_id']
    if (not isinstance(journal, dict) or journal.get('event_id')!=event_id
            or journal.get('symbol')!=row['symbol']
            or journal.get('source_trade_id')!=payload.get('source_trade_id')
            or 'cash_after' not in journal or journal.get('cash_after')!=payload.get('cash_after')):
        raise ValueError(f'durable cash event identity mismatch ({event_id})')
    try:
        expected=(float(journal['gross_pnl'])-float(journal['fee'])
                  -float(journal['entry_fee'])+float(journal['funding']))
        net=float(payload['net'])
    except (KeyError, TypeError, ValueError):
        raise ValueError(f'durable cash event identity mismatch ({event_id})') from None
    if (not math.isfinite(expected) or not math.isfinite(net)
            or abs(net-expected)>LEGACY_BACKFILL_CLOSE_NET_TOLERANCE):
        raise ValueError(f'durable cash event identity mismatch ({event_id})')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic(path, payload):
    temp=path.with_suffix(path.suffix+'.resize.tmp')
    with temp.open('w') as out:
        json.dump(payload,out,indent=2,allow_nan=False);out.write('\n');out.flush();os.fsync(out.fileno())
    os.replace(temp,path)
    fd=os.open(path.parent,os.O_DIRECTORY)
    try: os.fsync(fd)
    finally: os.close(fd)


def inspect_account(data, app):
    cash_path=data/'paper_cash.json';db_path=data/'firm.db';limits_path=app/'core/risk/limits.py'
    if not all(p.is_file() for p in (cash_path,db_path,limits_path)):
        raise ValueError('existing cash journal, database and limits file are all required')
    raw=json.loads(cash_path.read_text());events=raw.get('events')
    if not isinstance(events,list) or not events or any(not isinstance(e,dict) for e in events):
        raise ValueError('invalid existing cash journal; refusing to initialize/reset it')
    if any(e.get('kind') not in {'capital','open','funding','close'} for e in events):
        raise ValueError('unknown cash event kind')
    seen={}
    for e in events:
        key=e.get('event_id')
        if key and key in seen:
            raise ValueError('duplicate event IDs require cash reconciliation first')
        if key: seen[key]=e
    db=sqlite3.connect(f'file:{db_path}?mode=ro',uri=True)
    db.row_factory=sqlite3.Row
    if db.execute('PRAGMA quick_check').fetchone()[0]!='ok':
        raise ValueError('database integrity check failed')
    positions=[dict(r) for r in db.execute("SELECT * FROM positions WHERE status != 'closed' ORDER BY id")]
    if any(p['mode']!='paper' for p in positions):
        raise ValueError('non-paper open positions; refuse migration')
    tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    missing=[]
    if 'paper_cash_events' in tables:
        for row in db.execute('SELECT event_id,kind,mode,symbol,payload FROM paper_cash_events ORDER BY id'):
            if row['mode']!='paper':
                raise ValueError('non-paper durable cash row')
            payload=json.loads(row['payload'])
            # Only the named legacy backfill-close shape may omit payload event_id.
            if legacy_backfill_close_desktop(row, payload):
                reconcile_legacy_backfill_close(row, payload, seen.get(row['event_id']))
                continue
            if payload.get('event_id')!=row['event_id']:
                raise ValueError('durable cash event identity mismatch')
            if row['event_id'] not in seen:
                missing.append(payload)
            elif seen[row['event_id']] != payload:
                # Legacy migrations can enrich identity fields in the JSON.
                # Economic fields must still agree exactly.
                for key in ('kind','symbol','amount','gross_pnl','fee','entry_fee','funding'):
                    if seen[row['event_id']].get(key) != payload.get(key):
                        raise ValueError('durable cash event economic conflict')
    db.close()
    if missing:
        raise ValueError('durable cash events not yet reconciled; restart/repair existing account before resizing')
    current=replay_events(events)
    for value in (current.cash,current.realised_pnl,current.contributed_capital,current.total_fees,current.total_funding):
        if not math.isfinite(value): raise ValueError('nonfinite cash state')
    for key in ('cash','realised_pnl','contributed_capital','total_fees','total_funding'):
        if key not in raw or abs(float(raw[key])-getattr(current,key))>1e-6:
            raise ValueError('cash snapshot does not reconcile with its journal')
    text=limits_path.read_text()
    old='PAPER_LIMITS = RiskLimits()'
    new='PAPER_LIMITS = RiskLimits(max_concurrent_positions=15)'
    if text.count(old)+text.count(new)!=1:
        raise ValueError('unrecognized PAPER_LIMITS declaration; reconcile deployed settings first')
    # Validate every pre-existing parameter with the actual deployed class.
    namespace={};exec(compile(text,str(limits_path),'exec'),namespace)
    limits=namespace['PAPER_LIMITS']
    if (limits.max_risk_per_trade_pct,limits.max_position_pct,limits.max_total_exposure_pct)!=(.01,.1,.5):
        raise ValueError('deployed risk/notional/exposure settings differ from authorized settings')
    protective={p.name:sha(p) for p in data.iterdir() if p.is_file() and
                ('kill' in p.name or p.name in ('f111_paper_state.json','f111_paper_scan_disabled','l01_paper_enabled.json'))}
    return dict(raw=raw,events=events,current=current,positions=positions,protective=protective,
                limits_text=text,limits_next=text.replace(old,new),limits=limits.to_dict(),
                cash_sha=sha(cash_path),limits_sha=sha(limits_path))


def resize(data, app, backup_root, *, apply=False):
    before=inspect_account(data,app)
    prior=next((e for e in before['events'] if e.get('event_id')==EVENT_ID),None)
    amount=0. if prior else max(0.,20000.-before['current'].cash)
    receipt=dict(version=1,paper_only=True,capital_event_id=EVENT_ID,
                 cash_before=before['current'].cash,capital_addition=amount,
                 cash_after=before['current'].cash+amount,max_open_positions=15,
                 balance_basis='cash; open-position unrealised P&L is additional',
                 realised_pnl_before=before['current'].realised_pnl,
                 existing_open_positions=before['positions'],protective_hashes=before['protective'],
                 already_applied=prior is not None,applied=False)
    if not apply: return receipt
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup=backup_root/f'recovery-paper-{stamp}'
    backup.mkdir(parents=True,mode=0o700)
    for name in ('paper_cash.json',*before['protective']):
        shutil.copy2(data/name,backup/name)
    shutil.copy2(app/'core/risk/limits.py',backup/'limits.py')
    source=sqlite3.connect(f'file:{data/"firm.db"}?mode=ro',uri=True)
    target=sqlite3.connect(backup/'firm.db')
    source.backup(target);target.close();source.close()
    if sha(data/'paper_cash.json')!=before['cash_sha'] or sha(app/'core/risk/limits.py')!=before['limits_sha']:
        raise ValueError('account changed during offline backup')
    events=list(before['events'])
    if prior is None:
        events.append(dict(event_id=EVENT_ID,kind='capital',amount=amount,
            ts=datetime.now(timezone.utc).isoformat(),reason='Owner-authorized paper balance top-up to 20000 USDT',
            target_cash=20000.,cash_before=before['current'].cash))
    after=replay_events(events)
    if abs(after.realised_pnl-before['current'].realised_pnl)>1e-8:
        raise ValueError('capital contribution must not change trading P&L')
    payload=before['raw']|{k:getattr(after,k) for k in
        ('cash','realised_pnl','contributed_capital','total_fees','total_funding')}
    payload['events']=events
    atomic(data/'paper_cash.json',payload)
    limit_path=app/'core/risk/limits.py'
    temp=limit_path.with_suffix('.resize.tmp')
    with temp.open('w') as out:
        out.write(before['limits_next']);out.flush();os.fsync(out.fileno())
    shutil.copymode(limit_path,temp);os.replace(temp,limit_path)
    check=inspect_account(data,app)
    if check['positions']!=before['positions'] or check['protective']!=before['protective']:
        raise ValueError('positions or protective state changed; inspect backup before restart')
    if check['events'][:len(before['events'])]!=before['events']:
        raise ValueError('existing cash history changed')
    receipt.update(applied=True,backup=str(backup),realised_pnl_after=after.realised_pnl,
                   cash_after=after.cash,limits_after=check['limits'])
    atomic(backup/'receipt.json',receipt)
    atomic(data/'recovery_resize_receipt.json',receipt)
    return receipt


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--app-root',type=Path,required=True)
    p.add_argument('--data-root',type=Path,required=True)
    p.add_argument('--backup-root',type=Path,required=True)
    p.add_argument('--apply',action='store_true')
    args=p.parse_args()
    if args.apply and os.environ.get('MAR_PAPER_CONTAINERS_STOPPED')!='yes':
        raise ValueError('apply only through the guarded installer with paper and API containers stopped')
    print(json.dumps(resize(args.data_root,args.app_root,args.backup_root,apply=args.apply),indent=2,default=str))


if __name__=='__main__': main()
