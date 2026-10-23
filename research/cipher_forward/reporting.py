"""Prospective paper evidence. Unfinished/unknown outcomes stay explicit."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import html
import json
from pathlib import Path

from .ledger import BOOKS, OPPORTUNITIES, funding_known
from .seed import SeedStore, atomic_json


def year(ms):
    return str(datetime.fromtimestamp(ms/1000, timezone.utc).year)


def trade_stats(positions, now):
    closed = [p for p in positions if p['status']=='closed']
    pnl = [p['net_pnl'] for p in closed]
    rs = [p['net_pnl']/p['original_risk_usdt'] for p in closed]
    wins = sum(x for x in pnl if x>0); losses = -sum(x for x in pnl if x<0)
    known = all(funding_known(p, p['exit_ms'] or now) for p in positions)
    marked = sum((p.get('gross_pnl',0.) if p['exit_ms'] is not None else
                  p['side']*p['quantity']*(p['mark']-p['entry']))
                 -p['entry_fee']-p['exit_fee']-p['funding'] for p in positions)
    marked_r = sum(((p.get('gross_pnl',0.) if p['exit_ms'] is not None else
                    p['side']*p['quantity']*(p['mark']-p['entry']))
                   -p['entry_fee']-p['exit_fee']-p['funding'])/p['original_risk_usdt'] for p in positions)
    running=peak=dd=0.
    for p in sorted(closed,key=lambda p:(p['exit_ms'],p['uid'])):
        running+=p['net_pnl']/p['original_risk_usdt'];peak=max(peak,running);dd=max(dd,peak-running)
    return dict(entries=len(positions),closed=len(closed),open=sum(p['status']=='open' for p in positions),
        pending_funding=sum(p['status']=='pending_funding' for p in positions),
        closed_net_usdt=sum(pnl),closed_net_R=sum(rs),mean_R=sum(rs)/len(rs) if rs else None,
        win_rate=sum(x>0 for x in pnl)/len(pnl) if pnl else None,
        profit_factor=wins/losses if losses else None,profit_factor_no_losses=bool(wins and not losses),
        closed_R_drawdown=dd,marked_net_usdt=marked,marked_R=marked_r,funding_known=known,
        marked_basis='observed marks less accrued fees/funding; no hypothetical exit fee; gaps may make marks stale',
        fees=sum(p['entry_fee']+p['exit_fee'] for p in positions),
        signed_funding_cost=sum(p['funding'] for p in positions),
        assumed_slippage_cost=sum(p.get('entry_slippage_usdt',0)+p.get('exit_slippage_usdt',0) for p in positions),
        visible_depth_cost=sum(p.get('entry_depth_usdt',0)+p.get('exit_depth_usdt',0) for p in positions),
        entry_half_spread_cost=sum(p.get('entry_half_spread_usdt',0) for p in positions),
        mean_entry_latency_ms=(sum(p['decision_latency_ms'] for p in positions)/len(positions)) if positions else None,
        max_entry_latency_ms=max((p['decision_latency_ms'] for p in positions),default=None),
        max_entry_quote_age_ms=max((p['quote_age_ms'] for p in positions),default=None),
        missed_exit_ticks=sum(p['missed_exit_ticks'] for p in positions),
        missed_exit_minutes=sum(p['missed_exit_minutes'] for p in positions))


def report(ledger,now):
    state=ledger.state();positions=ledger.positions(None)
    output=dict(paper_only=True,observed_ms=now,accounts={},opportunities={},
        historical_backtest=False,severe_is_secondary=True,
        significance='Descriptive forward evidence only; no superiority claim from short samples.')
    decisions=[dict(row) for row in ledger.db.execute('SELECT * FROM decisions')]
    for book,account in state['accounts'].items():
        ps=[p for p in positions if p['book']==book]
        samples=[dict(r) for r in ledger.db.execute('SELECT * FROM equity_samples WHERE book=? ORDER BY minute',(book,))]
        calendar={};prior=20000.
        for sample in samples:
            y=year(sample['at_ms'])
            if y not in calendar:
                calendar[y]=dict(start_equity=prior,end_equity=prior,complete=True)
            calendar[y]['end_equity']=sample['equity']
            calendar[y]['complete'] &= bool(sample['complete_marks'] and sample['funding_known'])
            prior=sample['equity']
        for val in calendar.values():
            val['net_usdt']=val['end_equity']-val['start_equity']
            val['return_pct']=100*(val['end_equity']/val['start_equity']-1) if val['start_equity']>0 else None
        reasons=Counter(reason for d in decisions if d['book']==book
                        for reason in json.loads(d['body'])['reasons'])
        attrs={}
        for key in ('symbol','sector','source'):
            groups=defaultdict(list)
            for p in ps: groups[p[key]].append(p)
            attrs[key]={k:trade_stats(v,now) for k,v in sorted(groups.items())}
        output['accounts'][book]=trade_stats(ps,now)|dict(equity=account['equity'],
            return_pct=100*(account['equity']/20000-1),max_drawdown_pct=100*account['maximum_drawdown'],
            equity_observed_ms=account['mark_ms'],calendar_years=calendar,
            gross_usdt=sum(p['quantity']*p['mark'] for p in ps if p['status']=='open'),
            killed=account['killed'],supervision_gap=account['supervision_gap'],
            streak=account['streak'],raw_streak=account['raw_streak'],
            rejections=dict(reasons),attribution=attrs)
    for book in OPPORTUNITIES:
        ps=[p for p in positions if p['book']==book]
        blocked={}
        for arm in ('I','IC','IM','IF'):
            paired=book.split(':')[0]+':'+arm
            ids={d['uid'] for d in decisions if d['book']==paired and d['status']=='rejected'}
            blocked[paired]=trade_stats([p for p in ps if p['uid'] in ids],now)
        output['opportunities'][book]=trade_stats(ps,now)|dict(
            basis='Overlapping independent 2000 USDT hypothetical signals; NOT account return',
            blocked_funded_decisions=blocked)
    output['cost_contrasts']={cost:{arm:dict(
        incremental_return_percentage_points=output['accounts'][cost+':'+arm]['return_pct']-output['accounts'][cost+':I']['return_pct'],
        incremental_closed_R=output['accounts'][cost+':'+arm]['closed_net_R']-output['accounts'][cost+':I']['closed_net_R'])
        for arm in ('IC','IM','IF')} for cost in ('baseline','moderate','severe')}
    output['data_coverage']=dict(last_scan=ledger.feed('last_scan',{}),
        first_forward_hour=ledger.feed('first_forward_hour'),
        error_counts={r[0]:r[1] for r in ledger.db.execute("SELECT kind,count(*) FROM observations WHERE kind LIKE '%error%' GROUP BY kind")})
    return output


def verification(ledger,now,root,seed_root):
    failures=[];state=ledger.state()
    status_path=Path(root)/'status.json'
    status=json.loads(status_path.read_text()) if status_path.exists() else {}
    scan=ledger.feed('last_scan',{});cutoff=ledger.feed('first_forward_hour')
    if not 0<=now-status.get('heartbeat_ms',0)<45000: failures.append('worker heartbeat not fresh')
    if not 0<=now-(state['last_cycle_ms'] or 0)<45000: failures.append('execution cycle not fresh')
    if cutoff is None or scan.get('hour',0)<cutoff: failures.append('first future scan pending')
    if scan.get('coverage')!=len(ledger.config['universe']) or scan.get('errors',1): failures.append('scan coverage/errors')
    if now-scan.get('hour',0)>3700000: failures.append('hourly scan stale')
    if scan.get('completed_ms',0)-scan.get('hour',0)>=110000: failures.append('scan missed 110-second latency budget')
    if not scan.get('available',0): failures.append('no available instruments scanned')
    if (Path(root)/'entries_disabled').exists(): failures.append('manual entry halt present')
    for book,account in state['accounts'].items():
        if account['killed'] or account['supervision_gap']: failures.append(book+': account entry hold')
    for p in ledger.positions():
        if not funding_known(p,p['exit_ms'] or now): failures.append(p['book']+': unknown funding')
        if p['status']=='open' and not 0<=now-p['mark_ms']<=20000: failures.append(p['book']+': stale open mark')
    receipt_path=Path(root)/'warmup.json'
    warmup=json.loads(receipt_path.read_text()) if receipt_path.exists() else {}
    seed=SeedStore(seed_root,ledger.config['universe'])
    if not warmup.get('ready'): failures.append('warmup not verified')
    if warmup.get('seed',{}).get('manifest_sha256')!=seed.receipt()['manifest_sha256']:
        failures.append('seed manifest mismatch')
    deployment_path=Path(root)/'deployment.json'
    deployment=json.loads(deployment_path.read_text()) if deployment_path.exists() else {}
    if not deployment.get('image_id') or deployment.get('release')!=status.get('release'):
        failures.append('release/image receipt missing or mismatch')
    ledger.reconcile()
    return dict(activation_verified=not failures,paper_only=True,real_money_authorized=False,
        failures=sorted(set(failures)),last_scan=scan,first_forward_hour=cutoff,
        zero_fills_valid=True,funded_books=len(BOOKS),opportunity_books=len(OPPORTUNITIES),
        release=status.get('release'),deployment=deployment,observed_ms=now,
        config_sha256=ledger.report(now)['config_sha256'],
        verification_scope='isolated comparison only; does not certify production-account guards')


def render(value):
    rows=[]
    for name,a in value['accounts'].items():
        rows.append('<tr>'+''.join('<td>'+html.escape(str(x))+'</td>' for x in
            [name,f"{a['return_pct']:.2f}%",f"{a['closed_net_R']:.2f}",
             f"{a['max_drawdown_pct']:.2f}%",a['closed'],a['open']])+'</tr>')
    verified=value['verification']['activation_verified']
    return '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>MAR forward paper comparison</title><style>body{font:16px system-ui;margin:2rem auto;max-width:1150px;padding:0 1rem;color:#17243b}table{border-collapse:collapse;width:100%}th,td{text-align:left;padding:.6rem;border-bottom:1px solid #ccd6e0}pre{white-space:pre-wrap;overflow-wrap:anywhere}p{line-height:1.5}</style>
<h1>Forward paper comparison</h1><p>I = hourly L01/F111 + BL8. IC = I + original 3R short. IM = I + half-size 3R short. IF = I + fixed-filter 3R short.</p>
<p>Technical activation verified: '''+str(verified)+'''. Returns below are new forward paper observations, not the 2022–2025 backtest. Baseline and moderate costs are primary; severe is secondary. No superiority claim is made.</p>
<table><thead><tr><th>Cost / account</th><th>Marked return</th><th>Closed net R</th><th>Max DD</th><th>Closed trades</th><th>Open trades</th></tr></thead><tbody>'''+''.join(rows)+'''</tbody></table>
<p>R uses original entry-to-stop price risk. Marked returns include accrued fees/funding but no hypothetical exit fee. Unknown funding and stale marks remain provisional. Opportunity totals are not account returns.</p>
<details><summary>Full calendar-year, token, sector, source, cost and blocked-opportunity breakdown</summary><pre>'''+html.escape(json.dumps(value,indent=2,allow_nan=False))+'''</pre></details></html>'''


def report_and_verify(ledger,now,root,seed_root):
    ledger.db.execute('BEGIN')
    try:
        value=report(ledger,now)
        value['verification']=verification(ledger,now,root,seed_root)
    finally: ledger.db.execute('ROLLBACK')
    atomic_json(Path(root)/'report.json',value)
    atomic_json(Path(root)/'activation_evidence.json',value['verification'])
    path=Path(root)/'report.html';tmp=path.with_suffix('.tmp')
    tmp.write_text(render(value));tmp.replace(path)
    day=datetime.fromtimestamp(now/1000,timezone.utc).strftime('%Y-%m-%d')
    daily=Path(root)/'daily';daily.mkdir(exist_ok=True)
    atomic_json(daily/(day+'.json'),value)
    return value
