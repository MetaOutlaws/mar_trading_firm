"""Prospective paper evidence. Unfinished/unknown outcomes stay explicit."""
from collections import Counter, defaultdict
from datetime import datetime, timezone
import html
import json
from pathlib import Path

from .desk_cost import desk_cost_read
from .freeze import TWELVE_LOOKS, enforce_identity
from .ledger import BOOKS, OPPORTUNITIES, funding_known
from .seed import SeedStore, atomic_json

COMPARISON_ORDER = ('I', 'IC', 'IM', 'IF')
PROMINENT_COSTS = ('baseline', 'moderate')
ONE_SERVICE = (
    'One paper service holds 12 internal simulated portfolios. They are not '
    'exchange accounts, testnet accounts, or subaccounts, and they do not add '
    'capital or an API key per portfolio. '
) + TWELVE_LOOKS


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


def _forward(rows, cutoff, time_key):
    """Drop warmup rows. A missing cutoff means the forward window is not set yet."""
    if cutoff is None:
        return list(rows), 0
    kept = [row for row in rows if int(row[time_key]) >= int(cutoff)]
    return kept, len(rows) - len(kept)


def report(ledger,now):
    state=ledger.state();positions=ledger.positions(None)
    # `accounts` is the persisted simulated-cash key. The report also exposes
    # the same 12 records as internal portfolios. Nothing here is ranked.
    output=dict(paper_only=True,observed_ms=now,accounts={},opportunities={},
        historical_backtest=False,severe_is_secondary=True,
        one_paper_service=True,internal_simulated_portfolios=12,
        exchange_accounts=0,testnet_accounts=0,subaccounts=0,extra_capital=False,
        twelve_looks_statement=TWELVE_LOOKS,service_statement=ONE_SERVICE,
        ranks_portfolios=False,crowns_a_config_or_cost=False,
        comparison_order=list(COMPARISON_ORDER),
        prominent_costs=list(PROMINENT_COSTS),secondary_cost='severe',
        cost_roles=desk_cost_read(),
        significance='Descriptive forward evidence only; no superiority claim from short samples.')
    decisions=[dict(row) for row in ledger.db.execute('SELECT * FROM decisions')]
    cutoff=ledger.feed('first_forward_hour')
    positions, omitted_positions = _forward(positions, cutoff, 'entry_ms')
    decisions, omitted_decisions = _forward(decisions, cutoff, 'at_ms')
    output['warmup_rows_omitted']=omitted_positions+omitted_decisions
    output['warmup_performance_suppressed']=True
    tainted=omitted_positions>0
    for book,account in state['accounts'].items():
        ps=[p for p in positions if p['book']==book]
        samples=[dict(r) for r in ledger.db.execute('SELECT * FROM equity_samples WHERE book=? ORDER BY minute',(book,))]
        if cutoff is not None:
            samples=[sample for sample in samples if int(sample['at_ms'])>=int(cutoff)]
        calendar={};prior=20000.
        # Warmup P&L stays out of the performance calendar. Book equity is not
        # shown as a return when any warmup trade was dropped.
        if not tainted:
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
        shown_equity=None if tainted else account['equity']
        shown_return=None if tainted else 100*(account['equity']/20000-1)
        output['accounts'][book]=trade_stats(ps,now)|dict(equity=shown_equity,
            return_pct=shown_return,
            max_drawdown_pct=None if tainted else 100*account['maximum_drawdown'],
            equity_observed_ms=account['mark_ms'],calendar_years=calendar,
            gross_usdt=sum(p['quantity']*p['mark'] for p in ps if p['status']=='open'),
            killed=account['killed'],supervision_gap=account['supervision_gap'],
            streak=account['streak'],raw_streak=account['raw_streak'],
            rejections=dict(reasons),attribution=attrs,
            record='internal simulated portfolio')
    for book in OPPORTUNITIES:
        ps=[p for p in positions if p['book']==book]
        blocked={}
        for arm in COMPARISON_ORDER:
            paired=book.split(':')[0]+':'+arm
            ids={d['uid'] for d in decisions if d['book']==paired and d['status']=='rejected'}
            blocked[paired]=trade_stats([p for p in ps if p['uid'] in ids],now)
        output['opportunities'][book]=trade_stats(ps,now)|dict(
            basis='Overlapping independent 2000 USDT hypothetical signals; not a simulated-portfolio return',
            blocked_funded_decisions=blocked)
    def _sub(a,b):
        if a is None or b is None: return None
        return a-b
    output['cost_contrasts']={cost:{arm:dict(
        incremental_return_percentage_points=_sub(output['accounts'][cost+':'+arm]['return_pct'], output['accounts'][cost+':I']['return_pct']),
        incremental_closed_R=_sub(output['accounts'][cost+':'+arm]['closed_net_R'], output['accounts'][cost+':I']['closed_net_R']))
        for arm in ('IC','IM','IF')} for cost in ('baseline','moderate','severe')}
    output['comparisons']={}
    for arm in COMPARISON_ORDER:
        output['comparisons'][arm]=dict(
            arm=arm,
            primary={cost: output['accounts'][f'{cost}:{arm}'] for cost in PROMINENT_COSTS},
            secondary={'severe': output['accounts'][f'severe:{arm}']},
        )
    output['data_coverage']=dict(last_scan=ledger.feed('last_scan',{}),
        first_forward_hour=cutoff,
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
        if account['killed'] or account['supervision_gap']: failures.append(book+': simulated portfolio entry hold')
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
        verification_scope='isolated comparison only; does not certify production paper-book guards')


def _cell(value, suffix=''):
    if value is None:
        return 'suppressed'
    if isinstance(value, float):
        return f'{value:.2f}{suffix}'
    return str(value)


def _cost_lines(roles):
    lines=[]
    for name in ('baseline','moderate','severe'):
        row=roles['settings'][name]
        lines.append(
            f"{name}: entry {row['entry']['percent']} ({row['entry']['role']}), "
            f"non-stop exit {row['nonstop_exit']['percent']} ({row['nonstop_exit']['role']}), "
            f"stop exit {row['stop_exit']['percent']} ({row['stop_exit']['role']}). "
            f"Setting label: {row['role']}. Display: {row['display']}."
        )
    return ' '.join(lines)


def render(value):
    void=value.get('void') or {}
    banner=''
    if void.get('void'):
        banner=('<h1 id="void">VOID</h1><p><strong>'+html.escape(void.get('banner') or 'VOID')
                +'</strong> Entries are disabled. This run is not evidence.</p>')
    verified=(value.get('verification') or {}).get('activation_verified')
    roles=value['cost_roles']
    sections=[]
    for arm in value['comparison_order']:
        comp=value['comparisons'][arm]
        primary=[]
        for cost in value['prominent_costs']:
            a=comp['primary'][cost]
            primary.append('<tr>'+''.join('<td>'+html.escape(_cell(x))+'</td>' for x in
                [cost, _cell(a['return_pct'], '%'), _cell(a['closed_net_R']),
                 _cell(a['max_drawdown_pct'], '%'), a['closed'], a['open'],
                 roles['settings'][cost]['role']])+'</tr>')
        severe=comp['secondary']['severe']
        severe_row='<tr>'+''.join('<td>'+html.escape(_cell(x))+'</td>' for x in
            ['severe', _cell(severe['return_pct'], '%'), _cell(severe['closed_net_R']),
             _cell(severe['max_drawdown_pct'], '%'), severe['closed'], severe['open'],
             'secondary display only'])+'</tr>'
        sections.append(
            f'<section id="comparison-{html.escape(arm)}"><h2>Strategy comparison {html.escape(arm)}</h2>'
            '<table><thead><tr><th>Cost</th><th>Marked return</th><th>Closed net R</th>'
            '<th>Max DD</th><th>Closed trades</th><th>Open trades</th><th>Desk label</th></tr></thead><tbody>'
            +''.join(primary)+'</tbody></table>'
            '<details><summary>Severe cost, secondary display only</summary>'
            '<table><tbody>'+severe_row+'</tbody></table></details></section>')
    return '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>MAR forward paper comparison</title><style>body{font:16px system-ui;margin:2rem auto;max-width:1150px;padding:0 1rem;color:#17243b}table{border-collapse:collapse;width:100%}th,td{text-align:left;padding:.6rem;border-bottom:1px solid #ccd6e0}pre{white-space:pre-wrap;overflow-wrap:anywhere}p,h1,h2{line-height:1.5}#void{background:#7a1020;color:#fff;padding:1rem}</style>
'''+banner+'''<h1>Forward paper comparison</h1>
<p>'''+html.escape(value['service_statement'])+'''</p>
<p>'''+html.escape(value['twelve_looks_statement'])+''' Reports do not rank these portfolios and do not select a config or cost.</p>
<p>Results are four strategy comparisons, in fixed order I, IC, IM, IF. Inside each comparison, baseline and moderate are prominent. Severe is secondary display only and stays collapsed. Each of the 12 simulated portfolios keeps its own record.</p>
<p>I = hourly L01/F111 + BL8. IC = I + original 3R short. IM = I + half-size 3R short. IF = I + fixed-filter 3R short. BL8: port verified byte-identical to PR #149 @0519f425; strategy logic not desk-reviewed.</p>
<p>Technical activation verified: '''+html.escape(str(verified))+'''. Returns below are new forward paper observations, not the 2022–2025 backtest. No superiority claim is made. Warmup bars are indicator state only and are omitted from performance.</p>
<p>Desk binding cost is 0.31% per leg on entry and on exit. '''+html.escape(roles['escalation'])+''' '''+html.escape(_cost_lines(roles))+'''</p>
'''+''.join(sections)+'''
<p>R uses original entry-to-stop price risk. Marked returns include accrued fees and funding but no hypothetical exit fee. Unknown funding and stale marks remain provisional. Opportunity totals are not simulated-portfolio returns. Simulated cash starts at 20,000 USDT inside each portfolio record.</p>
<details><summary>Full calendar-year, token, sector, source, cost and blocked-opportunity breakdown</summary><pre>'''+html.escape(json.dumps(value,indent=2,allow_nan=False))+'''</pre></details></html>'''


def report_and_verify(ledger,now,root,seed_root):
    guard=enforce_identity(root, now)
    ledger.db.execute('BEGIN')
    try:
        value=report(ledger,now)
        value['void']=guard
        value['run_void']=bool(guard.get('void'))
        value['verification']=verification(ledger,now,root,seed_root)
        if guard.get('void'):
            value['verification']['failures']=sorted(set(
                list(value['verification']['failures'])+[guard.get('banner') or 'VOID']))
            value['verification']['activation_verified']=False
    finally: ledger.db.execute('ROLLBACK')
    atomic_json(Path(root)/'report.json',value)
    atomic_json(Path(root)/'activation_evidence.json',value['verification'])
    path=Path(root)/'report.html';tmp=path.with_suffix('.tmp')
    tmp.write_text(render(value));tmp.replace(path)
    day=datetime.fromtimestamp(now/1000,timezone.utc).strftime('%Y-%m-%d')
    daily=Path(root)/'daily';daily.mkdir(exist_ok=True)
    atomic_json(daily/(day+'.json'),value)
    return value
