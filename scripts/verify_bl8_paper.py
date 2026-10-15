#!/usr/bin/env python3
"""Read-only evidence snapshot. Activation and profitable trading are distinct."""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import time

ROOT=Path(__file__).resolve().parents[1]


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--db',required=True,type=Path);ap.add_argument('--expected-commit',required=True);args=ap.parse_args()
    now=time.time_ns()//1_000_000;status=json.loads((args.db.parent/'status.json').read_text())
    config=(ROOT/'config/sleeves/mar_bl8_shadow_v1.json').read_bytes();sha=hashlib.sha256(config).hexdigest();cfg=json.loads(config);universe=set(cfg['universe'])
    db=sqlite3.connect(args.db.resolve().as_uri()+'?mode=ro',uri=True);db.row_factory=sqlite3.Row;db.execute('PRAGMA query_only=ON');db.execute('BEGIN')
    failures=[]
    stored_sha=db.execute("SELECT v FROM meta WHERE k='config_sha'").fetchone()
    if stored_sha is None or stored_sha[0]!=sha:failures.append('database_config_mismatch')
    if not 0<=now-status['heartbeat_ms']<=30_000:failures.append('stale_or_future_heartbeat')
    if status['config_sha']!=sha:failures.append('config_mismatch')
    release=(ROOT/'BL8_RELEASE_SHA').read_text().strip()
    if release!=args.expected_commit or status['release']!=args.expected_commit:failures.append('release_mismatch')
    manifest=json.loads((ROOT/'docs/bl8-paper-validation/RELEASE_MANIFEST.json').read_text())
    for name,digest in manifest['runtime_sha256'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest:failures.append('runtime_hash:'+name)
    context={};context_times={}
    for r in db.execute("SELECT t,payload FROM observations WHERE kind='context' AND t>=? ORDER BY id",(status['started_ms'],)):
        p=json.loads(r['payload']);context[p['symbol']]=p;context_times[p['symbol']]=r['t']
    if set(context)!=universe:failures.append('initial_universe_scan_incomplete')
    if any(not 0<=now-t<=70*60_000 for t in context_times.values()):failures.append('stale_context_scan')
    errors=[dict(r) for r in db.execute("SELECT t,payload FROM observations WHERE kind='error' AND t>=? ORDER BY id DESC LIMIT 30",(status['started_ms'],))]
    gap_count=db.execute("SELECT count(*) FROM observations WHERE kind='supervision_gap' AND t>=?",(status['started_ms'],)).fetchone()[0]
    events=[dict(r) for r in db.execute('SELECT * FROM events')];positions=[json.loads(r[0]) for r in db.execute('SELECT payload FROM positions')]
    cash=0.;incomplete=[]
    for p in positions:
        ev=[r for r in events if r['uid']==p['uid']];fund=-sum(r['amount'] for r in ev if r['kind']=='funding');net=sum(r['amount'] for r in ev)
        expected=-p['entry_fee']-fund+p.get('gross_pnl',0)-p.get('exit_fee',0)
        if abs(net-expected)>1e-9:failures.append('cash_bridge:'+p['uid'])
        if sum(r['kind']=='entry_fee' for r in ev)!=1 or sum(r['kind']=='close' for r in ev)!=int(p['exit_ms'] is not None):failures.append('event_count:'+p['uid'])
        cash+=net
        if p['exit_ms'] and p['funding_status']!='observed_through_exit':incomplete.append(p['uid'])
    if abs(cash-sum(r['amount'] for r in events))>1e-9:failures.append('orphan_cash_event')
    available=sum(isinstance(p.get('instrument'),dict) and p['instrument'].get('status')=='Trading' for p in context.values())
    if not available:failures.append('no_available_instruments_verified')
    missing=[s for s,p in context.items() if p['reason'] in ['missing_context','stale_context']]
    if missing:failures.append('available_context_missing')
    output={'captured_ms':now,'paper_only':True,'activation_verified':not failures,'failures':failures,
            'expected_commit':args.expected_commit,'config_sha':sha,'heartbeat_ms':status['heartbeat_ms'],
            'symbols_checked':len(context),'available_symbols':available,'missing_context':missing,
            'recent_errors':errors,'supervision_gaps_since_start':gap_count,'cash_pnl_usdt':cash,
            'open_positions':sum(p['exit_ms'] is None for p in positions),'closed_positions':sum(p['exit_ms'] is not None for p in positions),
            'closed_funding_incomplete':incomplete,'observed_fill_close_cash_checks_pass':any(p['exit_ms'] is not None for p in positions) and not incomplete and not failures and not errors and gap_count==0,
            'full_forward_parity':'UNVERIFIED',
            'profitability_validated':False,'zero_fills_is_valid_activation':True,'hourly_repair_reconciliation':'SEPARATE_UNVERIFIED_UNLESS_OPERATOR_SUPPLIES_EVIDENCE',
            'position_sizing':{
                'policy':cfg.get('sizing_policy'),
                'starting_equity_usdt':cfg.get('starting_equity_usdt'),
                'max_risk_per_trade_pct':cfg.get('max_risk_per_trade_pct'),
                'max_position_pct':cfg.get('max_position_pct'),
                'max_total_exposure_pct':cfg.get('max_total_exposure_pct'),
                'max_leverage':cfg.get('max_leverage'),
                'min_notional_usdt':cfg.get('min_notional_usdt'),
                'below_min_notional':'reject_never_upsize',
            },
            'account_return_or_leverage_policy':'hourly PAPER_LIMITS on the isolated BL8 book; leverage 1x; live off'}
    db.rollback();db.close();print(json.dumps(output,indent=2));raise SystemExit(bool(failures))


if __name__=='__main__':main()
