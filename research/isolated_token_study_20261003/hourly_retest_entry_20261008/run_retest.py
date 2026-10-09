"""Preregistered breakout retest entry, with opportunity-denominator accounting."""
import argparse, datetime as dt, json, platform, sys
from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow as pa
pa.set_cpu_count(1); pa.set_io_thread_count(1)
HERE=Path(__file__).resolve().parent; ROOT=HERE.parent
sys.path.insert(0,str(ROOT/'hourly_exit_polling_20261008'))
from run_polling import base,load,enrich,admit,replay,sha,write,score,report_metrics,contrast,PERIODS,SYMBOLS,STOP,TARGET
from polling_rule import poll_trade,verify_path,independent_cost
sys.path.insert(0,str(ROOT/'hourly_stop_cost_20261008'))
from cost_rule import reconcile_cost
from entry_rule import select_entry,sequential_entry
REF=ROOT/'hourly_stop_cost_20261008/results_v1'
KEYS=['partition','symbol','side','signal_i']; PAIR=KEYS+['stress','poll_minutes']
POLLS=(0,1); ARMS=('immediate','retest')

def verified_reference(cache,runtime):
    f=json.loads((REF/'freeze.json').read_text());s=json.loads((REF/'status.json').read_text())
    assert s['status']=='complete'
    for group,root in [('sources',ROOT),('inputs',cache),('runtime_sources',runtime),('cached_references',ROOT)]:
        for n,h in f[group].items():assert sha(root/n)==h,n
    for n,h in s['output_hashes'].items():assert sha(REF/n)==h,n
    frames=[]
    for name in ['all_opportunities.parquet','pooled_ledger.parquet']:
        q=pd.read_parquet(REF/name,use_threads=False)
        q=q[(q.cost_model=='runtime_stop_fill')&q.poll_minutes.isin(POLLS)].copy()
        frames.append(q)
    raw,ledger=frames
    assert len(raw)==276 and len(ledger)==260
    assert not raw.duplicated(PAIR).any() and not ledger.duplicated(PAIR).any()
    return f,raw,ledger

def signals_of(raw):
    q=raw[(raw.stress==1)&(raw.poll_minutes==1)].copy()
    assert len(q)==69 and q.groupby('partition').size().to_dict()==dict(evaluation=15,historical=45,reserved_replication=9)
    return q

def admission(g):
    t,rej=admit(g);ids,counts=replay(g)
    assert ids==list(t[['symbol','tf','side','entry_i']].itertuples(index=False,name=None))
    assert counts==(rej.reason.value_counts().to_dict() if len(rej) else {})
    assert len(t)+len(rej)==len(g)
    if len(rej):
        rej['entry']=pd.to_datetime(rej.entry,utc=True)
        rej=rej.merge(g[['entry','symbol','side','tf','signal_i','signal_time']],on=['entry','symbol','side','tf'],validate='one_to_one')
    for _,q in t.groupby('symbol'):
        q=q.sort_values('entry');assert (q.entry.to_numpy()[1:]>q.exit_bar.to_numpy()[:-1]).all()
    return t,rej

def cost_check(row):
    xp=row.quote if row.reason=='stop' else row.quote*(1-row.side*row.slippage_per_side)
    cash=(xp-row.entry_price)*row.side-.00055*(row.entry_price+xp)-row.funding*row.entry_price
    assert np.isclose(row.exit_price,xp,atol=1e-11,rtol=0)
    assert np.isclose(row.net_return,cash/row.entry_price,atol=1e-11,rtol=0)

def replay_fill(c,f,tape,original,fill_i):
    side=int(original.side);slip=float(original.slippage_per_side)
    end=int(c.index.searchsorted(pd.Timestamp(PERIODS[original.partition][1],tz='UTC')))
    r=poll_trade(tape,int(fill_i),side,slip,end,int(original.poll_minutes))
    r['signal_i']=int(original.signal_i)
    verify_path(tape,r,side,slip,end,int(original.poll_minutes))
    fresh=enrich(tape,pd.DataFrame([r]),side,slip,STOP)
    independent_cost(c,f,next(fresh.itertuples()),side,slip)
    combined=original.to_dict();combined.update(fresh.iloc[0].to_dict())
    combined['stop_quote_overshoot']=max(0,side*(r['stop_price']-r['quote'])/r['entry_fill']) if r['reason']=='stop' else 0.
    combined['target_quote_overshoot']=max(0,side*(r['quote']-r['target_price'])/r['entry_fill']) if r['reason']=='target' else 0.
    q=reconcile_cost(pd.DataFrame([combined]))
    cost_check(next(q.itertuples()))
    assert q.entry_price.iloc[0]==q.entry_fill.iloc[0]
    return q.iloc[0]

def preflight(cache,runtime):
    out=HERE/'preflight_v1';out.mkdir(exist_ok=False)
    f,raw,ledger=verified_reference(cache,runtime);signals=signals_of(raw)
    paths=boundaries=admissions=0;rebuilt=[];boundary_rows=[]
    for symbol in SYMBOLS:
        for limit,parts in [('2026-01-01',['historical','evaluation']),('2026-10-02 16:00',['reserved_replication'])]:
            c,fund=load(cache,symbol,limit);tape=base.Tape(c,fund)
            assert (c.index.to_series().diff().dropna()==pd.Timedelta(minutes=1)).all()
            ss=signals[(signals.symbol==symbol)&signals.partition.isin(parts)]
            for r in ss.itertuples():
                i=int(r.signal_i);prior=c.iloc[i-21*60:i-60]
                boundary=prior.high.max() if r.side==1 else prior.low.min()
                assert len(prior)==1200 and np.isclose(boundary,r.entry_boundary,atol=1e-10,rtol=0)
                assert r.side*(c.close.iloc[i-1]-boundary)>0
                assert c.index[i]==r.signal_time and r.feature_asof==r.signal_time and r.regime_asof<r.signal_time
                boundary_rows.append(dict(partition=r.partition,symbol=symbol,side=r.side,signal_i=i,signal_time=r.signal_time,entry_boundary=boundary,signal_close=c.close.iloc[i-1]))
                boundaries+=1
            for _,r in raw[(raw.symbol==symbol)&raw.partition.isin(parts)].iterrows():
                x=replay_fill(c,fund,tape,r,int(r.signal_i))
                pd.testing.assert_series_equal(r,x[r.index],check_names=False,check_exact=True)
                rebuilt.append(x);paths+=1
        print('BASELINE_REBUILT',symbol,flush=True)
    q=pd.DataFrame(rebuilt)
    for key,g in q.groupby(['poll_minutes','partition','stress']):
        t,_=admission(g);r=ledger[(ledger.poll_minutes==key[0])&(ledger.partition==key[1])&(ledger.stress==key[2])]
        pd.testing.assert_frame_equal(t.sort_values(PAIR).reset_index(drop=True),r[t.columns].sort_values(PAIR).reset_index(drop=True),check_exact=True)
        admissions+=1
    pd.DataFrame(boundary_rows).to_csv(out/'boundaries.csv',index=False)
    v=dict(status='pass',baseline_paths_and_costs=paths,baseline_admitted_rows=len(ledger),independent_boundaries=boundaries,admission_replays=admissions,runtime_sources=len(f['runtime_sources']),inputs=len(f['inputs']),treatment_scored=False)
    write(out/'VERIFICATION.json',v);print(json.dumps(v,indent=2))

def freeze(cache,runtime,commit):
    f,_,_=verified_reference(cache,runtime)
    assert json.loads((HERE/'preflight_v1/VERIFICATION.json').read_text())['treatment_scored'] is False
    assert commit is None or len(commit)==40
    out=HERE/'results_v1';out.mkdir(exist_ok=False)
    sources={str(p.relative_to(ROOT)):sha(p) for p in ROOT.rglob('*.py')}
    for n in ['PROTOCOL.md','NOVELTY_AUDIT.md','PUBLICATION_EXCEPTION.md','TEST_VERIFICATION.json','preflight_v1/VERIFICATION.json','preflight_v1/boundaries.csv']:
        sources[str((HERE/n).relative_to(ROOT))]=sha(HERE/n)
    expansion=ROOT/'hourly_expanded_replication_20261008/PROTOCOL.md';sources[str(expansion.relative_to(ROOT))]=sha(expansion)
    refs={str(p.relative_to(ROOT)):sha(p) for p in REF.iterdir() if p.is_file()}
    write(out/'freeze.json',dict(frozen_at=dt.datetime.now(dt.timezone.utc).isoformat(),protocol_commit=commit,local_protocol_sha256=sha(HERE/'PROTOCOL.md'),github_publication_blocked=commit is None,sources=sources,inputs=f['inputs'],runtime_sources=f['runtime_sources'],cached_references=refs,periods=PERIODS,arms=ARMS,polls=POLLS,wait_minutes=60,stop=STOP,target=TARGET,cost_model='runtime_stop_fill',primary_poll_minutes=1,primary_stress=2,independent_holdout=False,packages=dict(python=platform.python_version(),numpy=np.__version__,pandas=pd.__version__,pyarrow=pa.__version__)))
    print('FROZEN',commit,flush=True)

def opportunity_intervals(g,part):
    a,z=PERIODS[part]
    weeks=pd.period_range(pd.Timestamp(a).to_period('W-SUN'),(pd.Timestamp(z)-pd.Timedelta(minutes=1)).to_period('W-SUN'),freq='W-SUN')
    w=pd.DataFrame({'week':g.signal_time.dt.tz_localize(None).dt.to_period('W-SUN'),'delta':g.delta_realized_net})
    w=w.groupby('week').delta.agg(['sum','count']).reindex(weeks,fill_value=0)
    result={}
    for block in [1,4]:
        n=len(w);starts=np.random.default_rng(20261006+block).integers(0,n,(10000,int(np.ceil(n/block))))
        ix=((starts[:,:,None]+np.arange(block))%n).reshape(10000,-1)[:,:n]
        den=w['count'].to_numpy()[ix].sum(1);num=w['sum'].to_numpy()[ix].sum(1);v=num[den>0]/den[den>0]
        lo,hi=np.quantile(v,[.025,.975]);result.update({f'per_signal_block_{block}_low':float(lo),f'per_signal_block_{block}_high':float(hi),f'per_signal_block_{block}_draws':len(v)})
    return result

def comparisons(opp,ledger,plans,out):
    baseline=opp[opp.entry_rule=='immediate'];treatment=opp[opp.entry_rule=='retest']
    cols=PAIR+['signal_time','entry','entry_i','exit_bar','exit_i','reason','entry_price','exit_price','fees','funding','net_return','net_R','holding_minutes','quote']
    pairs=baseline[cols].merge(treatment[cols],on=PAIR,how='left',suffixes=('_baseline','_retest'),validate='one_to_one')
    pairs=pairs.merge(plans,on=KEYS,how='left',validate='many_to_one')
    for rule in ARMS:
        pairs[rule+'_admitted']=pd.MultiIndex.from_frame(pairs[PAIR]).isin(pd.MultiIndex.from_frame(ledger[ledger.entry_rule==rule][PAIR]))
    pairs['baseline_realized_net']=np.where(pairs.immediate_admitted,pairs.net_return_baseline,0.)
    pairs['retest_realized_net']=np.where(pairs.retest_admitted,pairs.net_return_retest.fillna(0),0.)
    pairs['delta_realized_net']=pairs.retest_realized_net-pairs.baseline_realized_net
    pairs['fill_price_improvement']=pairs.side*(pairs.entry_price_baseline-pairs.entry_price_retest)/pairs.entry_price_baseline
    pairs['admission_change']=np.select([pairs.immediate_admitted&pairs.retest_admitted,~pairs.immediate_admitted&pairs.retest_admitted,pairs.immediate_admitted&~pairs.retest_admitted],['shared','newly_admitted','removed'],default='neither')
    pairs['no_trade_reason']=np.where(pairs.retest_admitted,'admitted',np.where(pairs.entry_status=='filled','occupancy_rejected',pairs.entry_status))
    pairs['reason_changed']=pairs.reason_baseline!=pairs.reason_retest
    pairs['entry_delay_minutes']=pairs.entry_i_retest-pairs.entry_i_baseline
    pairs.to_csv(out/'paired_raw_outcomes.csv',index=False)
    rows=[];decomp=[];matched=[];timing=[];missed=[];transitions=[]
    for (poll,part,stress),p in pairs.groupby(['poll_minutes','partition','stress']):
        a=ledger[(ledger.entry_rule=='immediate')&(ledger.poll_minutes==poll)&(ledger.partition==part)&(ledger.stress==stress)]
        b=ledger[(ledger.entry_rule=='retest')&(ledger.poll_minutes==poll)&(ledger.partition==part)&(ledger.stress==stress)]
        meta=dict(poll_minutes=int(poll),partition=part,stress=int(stress));n=len(p)
        shared=p[p.admission_change=='shared'];new=p[p.admission_change=='newly_admitted'];removed=p[p.admission_change=='removed']
        common_delta=(shared.net_return_retest-shared.net_return_baseline).sum();actual=b.net_return.sum()-a.net_return.sum()
        assert np.isclose(actual,common_delta+new.net_return_retest.sum()-removed.net_return_baseline.sum(),rtol=0,atol=1e-12)
        d=meta|dict(shared=len(shared),newly_admitted=len(new),removed=len(removed),shared_delta_net_sum=common_delta,new_net_sum=new.net_return_retest.sum(),removed_baseline_net_sum=removed.net_return_baseline.sum(),actual_difference_additive_sum=actual)
        for label,mask in [('unfilled',removed.entry_status!='filled'),('occupancy',removed.entry_status=='filled')]:
            q=removed[mask];d['removed_'+label]=len(q);d['removed_'+label+'_net_sum']=q.net_return_baseline.sum()
        decomp.append(d)
        aa=a.assign(entry=a.signal_time);bb=b.assign(entry=b.signal_time)
        rows.append(meta|dict(raw_signals=n,baseline_n=len(a),retest_n=len(b),baseline_mean_net=a.net_return.mean(),retest_mean_net=b.net_return.mean(),difference_mean_net=b.net_return.mean()-a.net_return.mean(),baseline_net_per_signal=a.net_return.sum()/n,retest_net_per_signal=b.net_return.sum()/n,difference_net_per_signal=actual/n)|contrast(bb,aa,*PERIODS[part])|opportunity_intervals(p,part))
        original=p[p.immediate_admitted].copy();original['counterfactual_retest_net']=original.net_return_retest.fillna(0)
        matched.append(meta|dict(view='counterfactual_original_admitted_signals_no_admission_replay',original_admitted=len(original),qualified=int((original.entry_status=='filled').sum()),unfilled=int((original.entry_status!='filled').sum()),baseline_mean_net=original.net_return_baseline.mean(),retest_zero_fill_mean_net=original.counterfactual_retest_net.mean(),difference_mean_net=(original.counterfactual_retest_net-original.net_return_baseline).mean()))
        for scope,q in [('all_raw_fills',p[p.entry_status=='filled']),('admitted_retest',p[p.retest_admitted])]:
            timing.append(meta|dict(scope=scope,n=len(q),mean_delay_minutes=q.entry_delay_minutes.mean(),median_delay_minutes=q.entry_delay_minutes.median(),mean_fill_price_improvement=q.fill_price_improvement.mean(),better_fills=int((q.fill_price_improvement>0).sum()),worse_fills=int((q.fill_price_improvement<0).sum()),equal_fills=int((q.fill_price_improvement==0).sum())))
        for why in ['no_retest','retest_no_reclaim','endpoint_censored','occupancy_rejected']:
            q=original[original.no_trade_reason==why]
            missed.append(meta|dict(no_trade_reason=why,n=len(q),baseline_targets_missed=int((q.reason_baseline=='target').sum()),baseline_stops_avoided=int((q.reason_baseline=='stop').sum()),baseline_marks_missed=int((q.reason_baseline=='boundary_mtm').sum()),baseline_net_sum=q.net_return_baseline.sum()))
        for scope,q in [('all_raw',p),('original_admitted',original)]:
            q=q.copy();q['to_reason']=q.reason_retest.fillna(q.entry_status)
            for (fr,to),cell in q.groupby(['reason_baseline','to_reason']):transitions.append(meta|dict(scope=scope,from_reason=fr,to_reason=to,n=len(cell)))
    for name,r in [('contrasts',rows),('admission_decomposition',decomp),('matched_results',matched),('entry_timing',timing),('missed_trades',missed),('outcome_transitions',transitions)]:pd.DataFrame(r).to_csv(out/(name+'.csv'),index=False)
    pairs[pairs.immediate_admitted].to_csv(out/'matched_baseline_signals.csv',index=False)
    return pd.DataFrame(rows)

def run(cache,runtime):
    out=HERE/'results_v1';f=json.loads((out/'freeze.json').read_text())
    for group,root in [('sources',ROOT),('inputs',cache),('runtime_sources',runtime),('cached_references',ROOT)]:
        for n,h in f[group].items():assert sha(root/n)==h,n
    assert not (out/'status.json').exists(),'Preserve attempts'
    write(out/'status.json',dict(status='running',started_at=dt.datetime.now(dt.timezone.utc).isoformat()))
    try:
        _,baseline,reference=verified_reference(cache,runtime);signals=signals_of(baseline)
        plans=[];treatment=[];paths=prefix=selection=0
        for symbol in SYMBOLS:
            for limit,parts in [('2026-01-01',['historical','evaluation']),('2026-10-02 16:00',['reserved_replication'])]:
                c,fund=load(cache,symbol,limit);tape=base.Tape(c,fund)
                for _,s in signals[(signals.symbol==symbol)&signals.partition.isin(parts)].iterrows():
                    i=int(s.signal_i);side=int(s.side);end=int(c.index.searchsorted(pd.Timestamp(PERIODS[s.partition][1],tz='UTC')))
                    p=select_entry(tape.h,tape.l,tape.cl,i,end,side,s.entry_boundary)
                    assert p==sequential_entry(tape.h,tape.l,tape.cl,i,end,side,s.entry_boundary);selection+=1
                    # Full decision needs at most60 completed candles and a following fill timestamp.
                    trunc=min(end,i+61)
                    assert p==select_entry(tape.h[:trunc],tape.l[:trunc],tape.cl[:trunc],i,trunc,side,s.entry_boundary);prefix+=1
                    plan={k:s[k] for k in KEYS+['signal_time','entry_boundary']};plan.update(p)
                    plan['touch_time']=c.index[p['touch_i']] if p['touch_i']>=0 else pd.NaT
                    plan['confirmation_time']=c.index[p['confirm_i']]+pd.Timedelta(minutes=1) if p['confirm_i']>=0 else pd.NaT
                    plan['planned_entry_time']=c.index[p['planned_entry_i']] if p['planned_entry_i']>=0 else pd.NaT
                    plans.append(plan)
                    if p['entry_status']!='filled':continue
                    assert 1<=p['delay_minutes']<=60
                    rows=baseline[(baseline.symbol==symbol)&(baseline.partition==s.partition)&(baseline.side==side)&(baseline.signal_i==i)]
                    assert len(rows)==4
                    for _,r in rows.iterrows():
                        x=replay_fill(c,fund,tape,r,p['planned_entry_i']);paths+=1
                        x['entry_rule']='retest';x['arm']='retest';x['delay_minutes']=p['delay_minutes']
                        assert x.signal_time<x.entry and x.feature_asof<=x.entry
                        treatment.append(x)
            print('RETEST_SELECTION_PATHS_COSTS_VERIFIED',symbol,flush=True)
        plans=pd.DataFrame(plans);plans.to_parquet(out/'entry_plans.parquet',index=False);plans.to_csv(out/'entry_plans.csv',index=False)
        signals.to_parquet(out/'frozen_signals.parquet',index=False)
        delayed=pd.DataFrame(treatment) if treatment else baseline.iloc[:0].assign(entry_rule='retest',delay_minutes=0)
        opp=pd.concat([baseline.assign(entry_rule='immediate',arm='immediate',delay_minutes=0),delayed],ignore_index=True)
        assert not opp.duplicated(PAIR+['entry_rule']).any()
        ledgers=[];rejections=[];summaries=[];subs=[];admissions=0
        for rule in ARMS:
            for poll in POLLS:
                for part,(a,z) in PERIODS.items():
                    for stress in [1,2]:
                        meta=dict(entry_rule=rule,poll_minutes=poll,partition=part,stress=stress)
                        g=opp[(opp.entry_rule==rule)&(opp.poll_minutes==poll)&(opp.partition==part)&(opp.stress==stress)]
                        t,rej=admission(g);admissions+=1;ledgers.append(t)
                        if len(rej):rejections.append(rej.assign(**meta))
                        n=int((signals.partition==part).sum())
                        summaries.append(meta|dict(raw_signals=n,qualified=len(g),unfilled=n-len(g),rejected=len(rej),net_per_original_signal=t.net_return.sum()/n)|report_metrics(t,STOP,a,z))
                        if rule=='immediate':
                            ref=reference[(reference.poll_minutes==poll)&(reference.partition==part)&(reference.stress==stress)]
                            # Arm labels are intentionally renamed, all execution/accounting fields identical.
                            stable=[c for c in ref.columns if c!='arm']
                            pd.testing.assert_frame_equal(t[stable].sort_values(PAIR).reset_index(drop=True),ref[stable].sort_values(PAIR).reset_index(drop=True),check_exact=True)
                        for group in [['symbol'],['side'],['symbol','side']]:
                            for key,q in t.groupby(group):
                                key=key if isinstance(key,tuple) else (key,)
                                subs.append(meta|dict(grouping='+'.join(group))|dict(zip(group,key))|score(q,STOP))
        ledger=pd.concat(ledgers,ignore_index=True);summary=pd.DataFrame(summaries)
        opp.to_parquet(out/'all_opportunities.parquet',index=False);ledger.to_parquet(out/'pooled_ledger.parquet',index=False);ledger.to_csv(out/'individual_trades.csv',index=False)
        summary.to_csv(out/'pooled_results.csv',index=False);pd.DataFrame(subs).to_csv(out/'subgroups.csv',index=False)
        (pd.concat(rejections,ignore_index=True) if rejections else pd.DataFrame(columns=['entry_rule','poll_minutes','partition','stress','reason'])).to_csv(out/'rejections.csv',index=False)
        contrasts=comparisons(opp,ledger,plans,out)
        checks={}
        for part in PERIODS:
            s=summary[(summary.entry_rule=='retest')&(summary.poll_minutes==1)&(summary.stress==2)&(summary.partition==part)].iloc[0]
            c=contrasts[(contrasts.poll_minutes==1)&(contrasts.stress==2)&(contrasts.partition==part)].iloc[0]
            checks[part]=bool(s.n_closed>0 and s['mean']>0 and c.difference_net_per_signal>0)
        write(out/'decision.json',dict(primary_continuation_screen_pass=all(checks.values()),checks=checks,automatic_deployment=False,independent_edge_established=False,new_deadline_selected=False,additional_token_outcomes_scored=False,runtime_changed=False))
        write(out/'VERIFICATION.json',dict(status='pass',unique_signals=69,independent_entry_selections=selection,causal_prefix_checks=prefix,treatment_paths_and_cost_checks=paths,independent_admission_replays=admissions,baseline_raw_rows_exact=276,baseline_admitted_rows_exact=260,attribution_checks=len(contrasts),qualified_unique_signals=int((plans.entry_status=='filled').sum()),ledger_rows=len(ledger)))
        write(out/'status.json',dict(status='complete',completed_at=dt.datetime.now(dt.timezone.utc).isoformat(),output_hashes={p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='status.json'}))
        print(summary[['entry_rule','poll_minutes','partition','stress','raw_signals','qualified','unfilled','rejected','n','mean','stop_count','target_count','net_per_original_signal']].to_string(index=False),flush=True)
    except Exception as exc:
        write(out/'status.json',dict(status='failed',error=repr(exc),failed_at=dt.datetime.now(dt.timezone.utc).isoformat()));raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['preflight','freeze','run']);p.add_argument('--cache',type=Path,required=True);p.add_argument('--runtime',type=Path,required=True);p.add_argument('--protocol-commit');a=p.parse_args()
    if a.command=='freeze':freeze(a.cache,a.runtime,a.protocol_commit)
    else:globals()[a.command](a.cache,a.runtime)
