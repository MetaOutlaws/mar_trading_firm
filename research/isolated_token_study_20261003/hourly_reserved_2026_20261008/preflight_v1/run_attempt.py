"""One frozen approved rule; historical preflight or reserved temporal replication."""
import argparse, datetime as dt, json, platform, sys
from dataclasses import replace
from pathlib import Path
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
sys.path.insert(0,str(ROOT/'hourly_extension_filter_20261007'))
from run_extension import base,opt,enrich,admit,replay,sha,write,report_metrics,score,reconcile,check_path,STOP,TARGET,SYMBOLS,KEYS
from extension_rule import extension,minute_context
from features import feature_frame
from run_three_token import compression_entries
sys.path.insert(0,str(ROOT/'hourly_connors_filter_20261008'))
import connors_rule as cr
sys.path.insert(0,str(ROOT/'hourly_btc_confirmation_20261007'))
import btc_rule as br
sys.path.insert(0,str(ROOT/'hourly_extension_regime_20261008'))
import regime_rule as er
ARM='hourly_compression_btc_connors_loweff_v1'
BEGIN='2026-01-01';END='2026-10-02 16:00'
PRIOR=ROOT/'hourly_extension_regime_20261008/results_v1'

def load(cache,symbol,end):
    cut=pd.Timestamp(end,tz='UTC')
    c=base.study.load(cache/f'{symbol}_1m.parquet');f=base.study.load(cache/'funding'/f'{symbol}_funding.parquet',True)
    return c[c.index<cut],f[f.index<=cut]

def membership(cache,begin,end):
    rows=[]
    for s in SYMBOLS:
        c,_=load(cache,s,end);d=c.turnover.resample('D').sum(min_count=1440)
        for month in pd.date_range(begin,end,freq='MS',inclusive='left',tz='UTC'):
            w=d.reindex(pd.date_range(month-pd.Timedelta(days=30),month,freq='D',inclusive='left'))
            days=(month-c.index.min()).days;med=w.median() if w.notna().all() else np.nan
            rows.append(dict(symbol=s,month=month.strftime('%Y-%m'),observed_days=days,prior_30d_median_turnover=med,eligible=bool(days>=90 and np.isfinite(med) and med>=10_000_000)))
    m=pd.DataFrame(rows).sort_values(['month','prior_30d_median_turnover','symbol'],ascending=[True,False,True]);m['rank']=np.nan
    m.loc[m.eligible,'rank']=m[m.eligible].groupby('month').cumcount()+1
    return m

def contexts(c,f,btc,symbol,member,begin,end,runtime):
    b=feature_frame(c,f,btc.btc24,60);q=cr.hourly_context(c);ind=cr.independent_context(c)
    state=er.context(c.close.resample('h',closed='left',label='right').last());geo=minute_context(c)
    start,stop=[c.index.searchsorted(pd.Timestamp(v,tz='UTC')) for v in [begin,end]]
    ranks=member[(member.symbol==symbol)&member.eligible].set_index('month')['rank']
    candidates=[];checks=0
    for side in [1,-1]:
        g=compression_entries(b,side,start,stop).copy()
        g['rank']=pd.Series(g.index.strftime('%Y-%m'),index=g.index).map(ranks)
        g=g[g['rank'].notna()].copy();g['symbol']=symbol;g['side']=side;g['entry']=g.index
        g=g.join(cr.context_at(q,g.index)).join(br.context_at(btc,g.index).drop(columns=['btc24'])).join(state)
        g['entry_boundary']=g.high20 if side==1 else g.low20
        g['extension_atr'],g['passes_extension']=extension(g.close,g.entry_boundary,g.prior_atr,side)
        g['passes_crsi']=cr.gate(g.filter_crsi,side);g['passes_btc']=br.confirmation(symbol,side,g.btc24)
        g['passes_approved']=g.passes_crsi & g.passes_btc & (g.directional|g.passes_extension)
        for row in g.itertuples():
            T=row.entry
            for col in ['filter_crsi','price_rsi3','streak_rsi2','rank100','streak','return1']:
                assert np.isclose(getattr(row,col),ind.loc[T,col],rtol=1e-11,atol=1e-9),(symbol,T,col)
            assert np.isclose(row.efficiency24_before_signal,er.independent_at(c,T),atol=1e-12)
            x=geo.loc[T];boundary=x.high20 if side==1 else x.low20
            for a,z in [(row.prior_atr,x.prior_atr),(row.entry_boundary,boundary),(row.close,x.signal_close)]:assert np.isclose(a,z,atol=1e-9,rtol=1e-11)
            assert row.crsi_asof==row.btc_asof==row.feature_asof==T
            assert row.regime_asof==T-pd.Timedelta(hours=1) and row.crsi_last_minute<T and row.btc_last_minute<T
            checks+=1
        candidates.append(g)
    raw=pd.concat(candidates);runtime_checks=runtime_parity(c,btc,symbol,b,raw,begin,end,runtime,set(ranks.index))
    return raw,dict(independent_contexts=checks,**runtime_checks)

def runtime_parity(c,btc,symbol,b,raw,begin,end,runtime,eligible_months):
    sys.path.insert(0,str(runtime))
    from core.strategy.base import SignalSide
    from core.strategy.hourly_compression_btc_connors_loweff_v1 import HourlyCompressionBtcConnorsLoweffV1Strategy as Rule
    h=c.resample('h').agg(dict(open='first',high='max',low='min',close='last',volume='sum'))
    # Only BTC closes are consumed by runtime market preparation.
    bh=pd.DataFrame({'close':btc.btc_close.to_numpy()},index=btc.index-pd.Timedelta(hours=1))
    window=frames=0;hours=0
    for side in [SignalSide.LONG,SignalSide.SHORT]:
        rule=Rule(replace(Rule().params,side=side));full=rule.generate_signals(rule.prepare_market_context(symbol,h,bh))
        ix=b.index[(b.index>=pd.Timestamp(begin,tz='UTC'))&(b.index<pd.Timestamp(end,tz='UTC'))]
        # Apply research finite-feature and membership eligibility separately from runtime.
        compare=full.loc[ix-pd.Timedelta(hours=1),'signal'].to_numpy()
        candidates=raw[raw.side==side.sign]
        # Preflight contains early-history/ineligible months; compare eligible research hours.
        valid=b.loc[ix,'eligible'].to_numpy() & ix.strftime('%Y-%m').isin(eligible_months)
        expected=np.where(ix.isin(candidates.loc[candidates.passes_approved].index),side.sign,0)
        assert np.array_equal(compare[valid],expected[valid]),(symbol,side,'runtime/research full signals')
        frames+=1;hours+=int(valid.sum())
        for row in candidates.itertuples():
            T=row.entry-pd.Timedelta(hours=1);j=h.index.get_loc(T);v=full.loc[T]
            assert v.signal==(side.sign if row.passes_approved else 0)
            for col in ['filter_crsi','efficiency24_before_signal','extension_atr','entry_boundary']:
                assert np.isclose(v[col],getattr(row,col),atol=1e-9,rtol=1e-11)
            w=rule.generate_signals(rule.prepare_market_context(symbol,h.iloc[j-849:j+1],bh.loc[:T].tail(850))).iloc[-1]
            assert w.signal==v.signal and w.passes_crsi==v.passes_crsi and w.passes_btc==v.passes_btc and w.passes_loweff_cap==v.passes_loweff_cap
            window+=1
    return dict(runtime_frames=frames,runtime_hour_side_checks=hours,runtime_850_hour_checks=window)

def independent_cost(c,f,r,side,slip):
    i,j=int(r.entry_i),int(r.exit_i);ep=c.open.iloc[i]*(1+side*slip);xp=r.quote*(1-side*slip)
    def funding(end):
        q=f[(f.index>c.index[i])&(f.index<=end)]
        loc=c.index.get_indexer(q.index,method='pad')
        return side*float(np.sum(q.funding_rate.to_numpy()*c.open.to_numpy()[np.clip(loc,0,len(c)-1)]))/ep
    early=funding(c.index[j]);late=funding(c.index[j]+pd.Timedelta(minutes=1))
    charge=late if r.fund_mode=='close' else max(early,late)
    fees=.00055*(1+xp/ep);net=side*(xp/ep-1)-fees-charge
    for col,expected in [('entry_price',ep),('exit_price',xp),('fees',fees),('funding',charge),('net_return',net)]:
        assert np.isclose(getattr(r,col),expected,rtol=0,atol=1e-11),(col,getattr(r,col),expected)

def calculate(cache,runtime,periods,out):
    end=list(periods.values())[-1][1];begin=list(periods.values())[0][0]
    member=membership(cache,begin,end);member.to_csv(out/'membership_audit.csv',index=False)
    bc,_=load(cache,'BTCUSDT',end);btc=br.hourly_context(bc);del bc
    opp=[];signals=[];verification=[];paths=costs=0
    for symbol in SYMBOLS:
        c,f=load(cache,symbol,end);tape=base.Tape(c,f)
        raw,v=contexts(c,f,btc,symbol,member,begin,end,runtime);verification.append(dict(symbol=symbol,**v))
        raw['tf']=60;raw['partition']=''
        for part,(a,z) in periods.items():
            raw.loc[(raw.entry>=pd.Timestamp(a,tz='UTC'))&(raw.entry<pd.Timestamp(z,tz='UTC')),'partition']=part
        signals.append(raw)
        for (part,side),g in raw[raw.passes_approved].groupby(['partition','side']):
            end_i=int(c.index.searchsorted(pd.Timestamp(periods[part][1],tz='UTC')));rr=[]
            for i in g.entry_i:
                r=opt.raw_trade(tape,int(i),int(side),TARGET,STOP,end_i,end_i);check_path(tape,r,int(side),end_i);rr.append(r);paths+=1
            lookup=g.set_index('entry_i')
            for stress in [1,2]:
                slip=(.001 if symbol=='SOLUSDT' else .0005)*stress
                t=enrich(tape,pd.DataFrame(rr),int(side),slip,STOP).assign(symbol=symbol,side=side,tf=60,partition=part,stop=STOP,target=TARGET,stress=stress,slippage_per_side=slip,arm=ARM)
                for col in ['rank','filter_crsi','price_rsi3','streak_rsi2','rank100','streak','return1','btc24','efficiency24_before_signal','directional','extension_atr','entry_boundary','prior_atr','volume_ratio','compression','rsi14','r24','regime_asof','feature_asof','hourly_asof','crsi_asof','btc_asof']:
                    t[col]=t.entry_i.map(lookup[col])
                for r in t.itertuples():independent_cost(c,f,r,int(side),slip);costs+=1
                opp.append(t)
        print('CONTEXTS_RUNTIME_PATHS_COSTS_VERIFIED',symbol,v,flush=True)
    # Explicit schema supports a future run with no selected signals.
    columns=['entry_i','exit_i','quote','reason','fund_mode','ambiguous','entry','exit_bar','entry_price','exit_price','fees','funding','gross_return','net_return','net_R','holding_minutes','quoted_return','slippage_drag','symbol','side','tf','partition','stop','target','stress','arm','rank']
    allopp=pd.concat(opp,ignore_index=True) if opp else pd.DataFrame(columns=columns)
    allopp.to_parquet(out/'all_opportunities.parquet',index=False)
    pd.concat(signals).to_parquet(out/'signal_contexts.parquet',index=False)
    ledgers=[];rejects=[];summaries=[];subs=[];leaveouts=[]
    for part,(a,z) in periods.items():
        for stress in [1,2]:
            g=allopp[(allopp.partition==part)&(allopp.stress==stress)];t,rej=admit(g);ids,counts=replay(g)
            assert ids==list(t[['symbol','tf','side','entry_i']].itertuples(index=False,name=None))
            assert counts==(rej.reason.value_counts().to_dict() if len(rej) else {}) and len(t)+len(rej)==len(g)
            for _,q in t.groupby('symbol'):
                q=q.sort_values('entry');assert (q.entry.to_numpy()[1:]>q.exit_bar.to_numpy()[:-1]).all()
            meta=dict(arm=ARM,partition=part,stress=stress)
            ledgers.append(t);summaries.append(meta|dict(opportunities=len(g),rejected=len(rej))|report_metrics(t,STOP,a,z))
            if len(rej):rejects.append(rej.assign(**meta))
            if len(t):
                t=t.assign(month=t.entry.dt.strftime('%Y-%m'))
                for grouping in [['symbol'],['side'],['symbol','side'],['month'],['directional']]:
                    for k,q in t.groupby(grouping):
                        k=k if isinstance(k,tuple) else (k,)
                        subs.append(meta|dict(grouping='+'.join(grouping))|dict(zip(grouping,k))|score(q,STOP))
            for symbol in SYMBOLS:
                q=t[t.symbol!=symbol];leaveouts.append(meta|dict(excluded_symbol=symbol,n=len(q),mean_net=q.net_return.mean(),method='remove from admitted ledger; no replacement replay'))
    ledger=pd.concat(ledgers,ignore_index=True);ledger.to_parquet(out/'pooled_ledger.parquet',index=False);ledger.to_csv(out/'individual_trades.csv',index=False)
    summary=pd.DataFrame(summaries);summary.to_csv(out/'pooled_results.csv',index=False)
    pd.DataFrame(subs).to_csv(out/'subgroups.csv',index=False);pd.DataFrame(leaveouts).to_csv(out/'leave_one_token_out.csv',index=False)
    (pd.concat(rejects,ignore_index=True) if rejects else pd.DataFrame(columns=['partition','stress','reason'])).to_csv(out/'rejections.csv',index=False)
    v=dict(status='pass',contexts=verification,independent_minute_paths=paths,independent_cost_rows=costs,independent_admission_runs=2*len(periods),ledger_rows=len(ledger))
    write(out/'VERIFICATION.json',v)
    return allopp,ledger,summary

def preflight(cache,runtime,out):
    out.mkdir(parents=True,exist_ok=False)
    opp,t,summary=calculate(cache,runtime,{'historical':('2022-01-01','2025-01-01'),'evaluation':('2025-01-01','2026-01-01')},out)
    old=pd.read_parquet(PRIOR/'all_opportunities.parquet').query('arm=="combo_loweff"');old_t=pd.read_parquet(PRIOR/'pooled_ledger.parquet').query('arm=="combo_loweff"')
    n=reconcile(opp,old);m=reconcile(t,old_t);assert n==120 and m==112
    v=json.loads((out/'VERIFICATION.json').read_text());v.update(historical_opportunity_rows_reconciled=n,historical_admitted_rows_reconciled=m,scores_2026=False)
    write(out/'VERIFICATION.json',v);print(json.dumps(v,indent=2))

def freeze(cache,runtime,out,commit):
    audit=json.loads((HERE/'DATA_AUDIT.json').read_text());pre=json.loads((HERE/'preflight_v1/VERIFICATION.json').read_text())
    assert pre['status']=='pass' and pre['historical_admitted_rows_reconciled']==112
    prior=json.loads((PRIOR/'freeze.json').read_text())
    assert audit['inputs']==prior['inputs']
    out.mkdir(parents=True,exist_ok=False)
    sources={str(p.relative_to(ROOT)):sha(p) for p in ROOT.rglob('*.py')}
    for n in ['PROTOCOL.md','PRIOR_USE_AUDIT.md','DATA_AUDIT.json','prior_entry_date_inventory.csv','preflight_v1/VERIFICATION.json']:
        sources[str((HERE/n).relative_to(ROOT))]=sha(HERE/n)
    runtime_sources={str(p.relative_to(runtime)):sha(p) for p in runtime.rglob('*.py')}
    write(out/'freeze.json',dict(frozen_at=dt.datetime.now(dt.timezone.utc).isoformat(),protocol_commit=commit,sources=sources,runtime_sources=runtime_sources,inputs=audit['inputs'],periods={'reserved_replication':(BEGIN,END)},arm=ARM,stop=STOP,target=TARGET,scores_2026=True,independent_holdout=False,packages=dict(python=platform.python_version(),numpy=np.__version__,pandas=pd.__version__)))
    print('FROZEN',out,flush=True)

def run(cache,runtime,out):
    f=json.loads((out/'freeze.json').read_text())
    for kind,root in [('sources',ROOT),('runtime_sources',runtime),('inputs',cache)]:
        for n,h in f[kind].items():assert sha(root/n)==h,n
    assert not (out/'status.json').exists(),'Preserve attempts; use a new directory'
    write(out/'status.json',dict(status='running',started_at=dt.datetime.now(dt.timezone.utc).isoformat()))
    opp,t,s=calculate(cache,runtime,f['periods'],out)
    point=bool(len(s)==2 and (s.n>0).all() and (s['mean']>0).all())
    intervals=bool(all(s.get(f'block_{k}_low_R',pd.Series([-np.inf])).gt(0).all() for k in [1,4]))
    write(out/'decision.json',dict(positive_point_replication_both_costs=point,both_block_interval_lower_bounds_positive_both_costs=intervals,independent_edge_established=False,holdout_untouched=False,automatic_deployment=False,leverage_qualified=False))
    write(out/'status.json',dict(status='complete',completed_at=dt.datetime.now(dt.timezone.utc).isoformat(),scores_2026=True,output_hashes={p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='status.json'}))
    print(s[['partition','stress','n','mean','stop_count','target_count','boundary_count']].to_string(index=False),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['preflight','freeze','run']);p.add_argument('--cache',type=Path,required=True);p.add_argument('--runtime',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--protocol-commit');a=p.parse_args()
    if a.command=='freeze':
        assert a.protocol_commit and len(a.protocol_commit)==40;freeze(a.cache,a.runtime,a.out,a.protocol_commit)
    else:globals()[a.command](a.cache,a.runtime,a.out)
