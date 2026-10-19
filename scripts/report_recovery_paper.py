#!/usr/bin/env python3
"""Read-only audit/report. Unlimited opportunity totals are never account ROI."""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import html
import json
from pathlib import Path
import sqlite3
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from core.execution.recovery_paper import canonical, digest, funding_known


def report(db_path, status_path, *, expected_commit=None, now=None):
    now=int(time.time()*1000) if now is None else now
    db=sqlite3.connect(f'file:{db_path}?mode=ro',uri=True);db.row_factory=sqlite3.Row
    failures=[]
    if db.execute('PRAGMA quick_check').fetchone()[0]!='ok': failures.append('database integrity')
    state=json.loads(db.execute('SELECT body FROM state').fetchone()[0])
    config=json.loads(db.execute("SELECT value FROM meta WHERE key='config'").fetchone()[0])
    status=json.loads(status_path.read_text()) if status_path.is_file() else {}
    if not 0<=now-status.get('heartbeat_ms',0)<=30000: failures.append('fresh worker heartbeat required')
    if status.get('config_sha256')!=digest(config): failures.append('worker configuration mismatch')
    if expected_commit and status.get('release')!=expected_commit: failures.append('worker commit mismatch')
    scan=status.get('last_scan',{})
    if scan.get('coverage')!=96 or scan.get('errors',1): failures.append('complete clean 96-symbol scan required')
    if not 0<=now-scan.get('completed_ms',0)<=65*60_000: failures.append('fresh hourly scan required')
    if scan.get('hour',0)<status.get('first_forward_hour',now+1): failures.append('first complete forward hour pending')
    if status.get('manual_entry_halt'): failures.append('manual entry halt active')
    positions=[json.loads(r[0]) for r in db.execute('SELECT body FROM positions')]
    decisions={(r['book'],r['uid']):dict(status=r['status'],**json.loads(r['body']))
               for r in db.execute('SELECT * FROM decisions')}
    result=dict(paper_only=True,release=status.get('release'),config=config,
                config_sha256=digest(config),heartbeat_ms=status.get('heartbeat_ms'),
                last_scan=scan,accounts={},opportunities={},breakdowns=[],failures=failures,
                note='Forward outcomes only. Historical returns were not rerun at 20000 USDT/15 positions.')
    for book,account in state['accounts'].items():
        ps=[p for p in positions if p['book']==book]
        expected=20000+sum(-p['entry_fee']-p['funding']+
            (p.get('gross_pnl',0)-p['exit_fee'] if p['exit_ms'] is not None else 0) for p in ps)
        reconciled=abs(expected-account['cash'])<1e-6
        if not reconciled: failures.append(book+': cash reconciliation')
        open_ps=[p for p in ps if p['status']=='open']
        known=all(funding_known(p,p['exit_ms'] or now) for p in ps)
        marks=not open_ps or account.get('mark_ms') is not None and 0<=now-account['mark_ms']<=15000
        if not marks: failures.append(book+': fresh complete marks required')
        if not known: failures.append(book+': funding reconciliation pending')
        if account['supervision_gap']: failures.append(book+': supervision gap requires reconciliation')
        if account['killed']: failures.append(book+': drawdown entry stop latched')
        result['accounts'][book]=dict(cash=account['cash'],equity=account['equity'],
            net_return_pct=(account['equity']/20000-1)*100 if marks and known else None,
            maximum_drawdown_pct=account['maximum_drawdown']*100,closed_pnl=account['realised_pnl'],
            closed_trades=account['closed_trades'],open_positions=len(open_ps),
            effective_streak=account['streak'],raw_streak=account['raw_streak'],
            recoveries=len(account['recovery_events']),cash_reconciled=reconciled,
            funding_known=known,marks_fresh=marks,killed=account['killed'],supervision_gap=account['supervision_gap'])
    ops={p['uid']:p for p in positions if p['book']=='OPPORTUNITY'}
    for book in ('NONE','C24'):
        rejected=[(uid,d) for (b,uid),d in decisions.items() if b==book and d['status']=='rejected']
        reasons=defaultdict(int)
        resolved=[]
        for uid,d in rejected:
            for reason in d['reasons']: reasons[reason]+=1
            if uid in ops and ops[uid]['status']=='closed': resolved.append(ops[uid])
        result['opportunities'][book]=dict(rejected_signals=len(rejected),
            rejection_reasons=dict(reasons),closed_counterfactuals=len(resolved),
            positive_counterfactuals=sum(p['net_pnl']>0 for p in resolved),
            resolved_with_missing_exit_minutes=sum(p.get('missed_exit_minutes',0)>0 for p in resolved),
            independent_notional_pnl_sum=sum(p['net_pnl'] for p in resolved),
            basis='2000 USDT notional per independently simulated signal; not portfolio ROI',
            missing_or_still_open=len(rejected)-len(resolved))
    groups=defaultdict(list)
    for p in positions:
        if p['status']!='closed': continue
        year=str(datetime.fromtimestamp(p['exit_ms']/1000,timezone.utc).year)
        for dimension,key in [('overall','all'),('year',year),('token',p['symbol']),
                              ('sector',p['sector']),('source',p['source']),('regime',p['regime'])]:
            groups[p['book'],dimension,key].append(p)
    for (book,dimension,key),ps in sorted(groups.items()):
        result['breakdowns'].append(dict(book=book,dimension=dimension,key=key,trades=len(ps),
            wins=sum(p['net_pnl']>0 for p in ps),net_pnl=sum(p['net_pnl'] for p in ps),
            fees=sum(p['entry_fee']+p['exit_fee'] for p in ps),funding=sum(p['funding'] for p in ps)))
    result['activation_verified']=not failures
    result['profitability_verified']=False
    db.close()
    return result


def render(result):
    def table(headers,rows):
        return '<table><thead><tr>'+''.join('<th>'+html.escape(h)+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join(
            '<tr>'+''.join('<td>'+html.escape(f'{v:,.2f}' if isinstance(v,float) else str(v))+'</td>' for v in row)+'</tr>' for row in rows)+'</tbody></table>'
    accounts=table(['Account','Equity USDT','Net return %','Max drawdown %','Closed trades','Open positions','C24 resets'],
        [[b,a['equity'],a['net_return_pct'],a['maximum_drawdown_pct'],a['closed_trades'],a['open_positions'],a['recoveries']] for b,a in result['accounts'].items()])
    opportunities=table(['Account','Rejected signals','Resolved opportunities','Profitable opportunities','Independent P&L sum USDT'],
        [[b,o['rejected_signals'],o['closed_counterfactuals'],o['positive_counterfactuals'],o['independent_notional_pnl_sum']] for b,o in result['opportunities'].items()])
    detail=table(['Book','Breakdown','Group','Trades','Wins','Net P&L','Fees','Funding'],
        [[r[k] for k in ('book','dimension','key','trades','wins','net_pnl','fees','funding')] for r in result['breakdowns']])
    warning='; '.join(result['failures']) or 'Runtime checks passed. This is not profitability approval.'
    return '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MAR recovery paper trial</title><style>body{font:16px system-ui;max-width:1200px;margin:40px auto;padding:0 20px;background:#f5f7fa;color:#162234}table{border-collapse:collapse;width:100%;margin:24px 0;background:white}th,td{padding:12px;text-align:right;border-bottom:1px solid #dde3eb}th:first-child,td:first-child{text-align:left}h1,h2{color:#173d59}.status{padding:18px;background:#fff2ce}p{line-height:1.6}section{overflow:auto}</style><h1>Recovery paper trial</h1><p>Two separate 20,000 USDT accounts, up to 15 open positions. NONE is the control; C24 can clear the six-loss entry pause after 24 hours. All other account limits remain.</p><p class="status">'+html.escape(warning)+'</p><h2>Actual paper account results</h2><section>'+accounts+'</section><h2>What the limits prevented</h2><p>Each opportunity uses a separate 2,000 USDT notional simulation. These overlapping trade sums are not account returns and cannot be added to portfolio performance.</p><section>'+opportunities+'</section><h2>Year, token, sector and strategy breakdown</h2><p>Closed-trade P&amp;L attribution, not independent subgroup portfolio returns. Empty tables mean there are no closed trades yet. Historical backtest returns do not describe these new account settings.</p><section>'+detail+'</section></html>'


def main():
    p=argparse.ArgumentParser();p.add_argument('--db',type=Path,required=True)
    p.add_argument('--expected-commit');p.add_argument('--output',type=Path,required=True)
    p.add_argument('--html',type=Path);p.add_argument('--require-active',action='store_true')
    a=p.parse_args();result=report(a.db,a.db.parent/'status.json',expected_commit=a.expected_commit)
    a.output.write_text(json.dumps(result,indent=2)+'\n')
    if a.html: a.html.write_text(render(result))
    print(json.dumps({k:result[k] for k in ('activation_verified','profitability_verified','failures','accounts')},indent=2))
    if a.require_active and not result['activation_verified']: raise SystemExit(1)


if __name__=='__main__': main()
