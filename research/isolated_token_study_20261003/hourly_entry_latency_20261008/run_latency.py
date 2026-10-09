"""Frozen execution latency audit; signal identity is not execution time."""
import argparse,datetime as dt,json,platform,sys
from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow as pa
pa.set_cpu_count(1);pa.set_io_thread_count(1)
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
sys.path.insert(0,str(ROOT/'hourly_fill_brackets_20261008'))
import run_fill_brackets as prior
from run_fill_brackets import base,load,enrich,admit,replay,reconcile,sha,write,score,report_metrics,contrast,independent_cost,PERIODS,SYMBOLS,STOP,TARGET
from bracket_rule import independent_path
from latency_rule import DELAYS,PRIMARY_DELAY,delayed_trade
REF=ROOT/'hourly_fill_brackets_20261008/results_v1'
KEYS=['partition','symbol','side','signal_i'];PAIR=KEYS+['stress']
FEATURES=['rank','filter_crsi','btc24','efficiency24_before_signal','directional','extension_atr','entry_boundary','prior_atr','volume_ratio','rsi14','r24','feature_asof','hourly_asof','crsi_asof','btc_asof','regime_asof']

def references():
    frames=[]
    for n in ['all_opportunities.parquet','pooled_ledger.parquet']:
        q=pd.read_parquet(REF/n,use_threads=False);q=q[q.arm=='fill_brackets'].copy()
        q['signal_i']=q.entry_i;q['signal_time']=q.entry;q['delay_minutes']=0;q['arm']='delay_0m';frames.append(q)
    a,b=frames
    assert len(a)==138 and len(b)==130 and not a.duplicated(PAIR).any() and not b.duplicated(PAIR).any()
    return a,b

def verify_references(cache,runtime):
    inputs,refs=prior.verify_reference_files(cache,runtime)
    f=json.loads((REF/'freeze.json').read_text());s=json.loads((REF/'status.json').read_text());assert s['status']=='complete'
    for group,root in [('sources',ROOT),('inputs',cache),('cached_references',ROOT),('runtime_sources',runtime)]:
        for n,h in f[group].items():assert sha(root/n)==h,n
    for n,h in s['output_hashes'].items():assert sha(REF/n)==h,n
    for n in ['freeze.json','status.json','all_opportunities.parquet','pooled_ledger.parquet','VERIFICATION.json']:
        refs[str((REF/n).relative_to(ROOT))]=sha(REF/n)
    return inputs,refs,f['runtime_sources']

def calculate(cache,out,delays):
    old,old_ledger=references();signals=old[old.stress==1].copy();assert len(signals)==69
    outputs=[];excluded=[];paths=costs=0
    for symbol in SYMBOLS:
        for limit,parts in [('2026-01-01',['historical','evaluation']),('2026-10-02 16:00',['reserved_replication'])]:
            c,f=load(cache,symbol,limit);tape=base.Tape(c,f)
            assert (c.index.to_series().diff().dropna()==pd.Timedelta(minutes=1)).all()
            selected=signals[(signals.symbol==symbol)&signals.partition.isin(parts)]
            for (part,side),g in selected.groupby(['partition','side']):
                side=int(side);end=int(c.index.searchsorted(pd.Timestamp(PERIODS[part][1],tz='UTC')));lookup=g.set_index('signal_i')
                for stress in [1,2]:
                    slip=(.001 if symbol=='SOLUSDT' else .0005)*stress
                    for delay in delays:
                        raw=[]
                        for signal_i in g.signal_i:
                            r=delayed_trade(tape,int(signal_i),side,slip,end,delay)
                            if r is None:
                                excluded.append(dict(partition=part,symbol=symbol,side=side,signal_i=int(signal_i),stress=stress,delay_minutes=delay,reason='entry_at_or_after_endpoint'));continue
                            independent_path(tape,r,side,slip,end,'fill_brackets');paths+=1;raw.append(r)
                        if not raw:continue
                        t=enrich(tape,pd.DataFrame(raw),side,slip,STOP).assign(symbol=symbol,side=side,tf=60,partition=part,stress=stress,slippage_per_side=slip,stop=STOP,target=TARGET,arm=f'delay_{delay}m')
                        t['signal_time']=t.signal_i.map(lookup.signal_time)
                        for col in FEATURES:t[col]=t.signal_i.map(lookup[col])
                        t['baseline_entry_quote']=t.signal_i.map(lookup.entry_quote)
                        t['entry_quote_move']=side*(t.entry_quote/t.baseline_entry_quote-1)
                        assert (t.entry==t.signal_time+pd.to_timedelta(delay,unit='min')).all()
                        assert (t.feature_asof==t.signal_time).all() and (t.hourly_asof==t.signal_time).all()
                        assert (t.regime_asof<t.signal_time).all() and (t.feature_asof<=t.entry).all()
                        assert np.allclose(t.entry_fill,t.entry_price,atol=1e-12,rtol=0)
                        for r in t.itertuples():independent_cost(c,f,r,side,slip);costs+=1
                        outputs.append(t)
        print('DELAY_PATHS_AND_COSTS_VERIFIED',symbol,flush=True)
    opp=pd.concat(outputs,ignore_index=True)
    n=reconcile(opp[opp.delay_minutes==0],old);assert n==138
    assert not opp.duplicated(PAIR+['delay_minutes']).any()
    opp.to_parquet(out/'all_opportunities.parquet',index=False);signals.to_parquet(out/'frozen_signals.parquet',index=False)
    pd.DataFrame(excluded,columns=PAIR+['delay_minutes','reason']).to_csv(out/'endpoint_exclusions.csv',index=False)
    ledgers=[];rejected=[];summaries=[];subgroups=[];leaveouts=[];admissions=0
    for delay in delays:
        for part,(a,z) in PERIODS.items():
            for stress in [1,2]:
                g=opp[(opp.delay_minutes==delay)&(opp.partition==part)&(opp.stress==stress)]
                t,rej=admit(g);ids,counts=replay(g)
                assert ids==list(t[['symbol','tf','side','entry_i']].itertuples(index=False,name=None))
                assert counts==(rej.reason.value_counts().to_dict() if len(rej) else {}) and len(t)+len(rej)==len(g)
                for _,q in t.groupby('symbol'):
                    q=q.sort_values('entry');assert (q.entry.to_numpy()[1:]>q.exit_bar.to_numpy()[:-1]).all()
                meta=dict(delay_minutes=delay,arm=f'delay_{delay}m',partition=part,stress=stress);admissions+=1;ledgers.append(t)
                if len(rej):
                    rej['entry']=pd.to_datetime(rej.entry,utc=True)
                    rej=rej.merge(g[['entry','symbol','side','tf','signal_i','signal_time']],on=['entry','symbol','side','tf'],validate='one_to_one')
                    rejected.append(rej.assign(**meta))
                summaries.append(meta|dict(opportunities=len(g),rejected=len(rej))|report_metrics(t,STOP,a,z))
                t=t.assign(entry_year=t.entry.dt.year)
                for group in [['symbol'],['side'],['symbol','side'],['entry_year']]:
                    for key,q in t.groupby(group):
                        key=key if isinstance(key,tuple) else (key,)
                        subgroups.append(meta|dict(grouping='+'.join(group))|dict(zip(group,key))|score(q,STOP))
                for symbol in SYMBOLS:
                    q=t[t.symbol!=symbol];leaveouts.append(meta|dict(excluded_symbol=symbol,n=len(q),mean_net=q.net_return.mean(),method='remove admitted subset; no replacement replay'))
    ledger=pd.concat(ledgers,ignore_index=True);m=reconcile(ledger[ledger.delay_minutes==0],old_ledger);assert m==130
    ledger.to_parquet(out/'pooled_ledger.parquet',index=False);ledger.to_csv(out/'individual_trades.csv',index=False)
    summary=pd.DataFrame(summaries);summary.to_csv(out/'pooled_results.csv',index=False)
    pd.DataFrame(subgroups).to_csv(out/'subgroups.csv',index=False);pd.DataFrame(leaveouts).to_csv(out/'leave_one_token_out.csv',index=False)
    (pd.concat(rejected,ignore_index=True) if rejected else pd.DataFrame(columns=['delay_minutes','partition','stress','reason'])).to_csv(out/'rejections.csv',index=False)
    return opp,ledger,summary,dict(status='pass',unique_frozen_signals=69,independent_minute_paths=paths,independent_cost_rows=costs,independent_admission_runs=admissions,zero_delay_opportunity_rows_reconciled=n,zero_delay_admitted_rows_reconciled=m,endpoint_exclusions=len(excluded),ledger_rows=len(ledger))

def aligned_contrast(a,b,part):
    return contrast(a.assign(entry=a.signal_time),b.assign(entry=b.signal_time),*PERIODS[part])

def comparisons(opp,ledger,out):
    baseline=opp[opp.delay_minutes==0];baseline_ledger=ledger[ledger.delay_minutes==0]
    paircols=PAIR+['signal_time','entry','entry_i','exit_bar','exit_i','reason','quote','entry_price','exit_price','stop_price','target_price','fees','funding','net_return','net_R','holding_minutes','ambiguous']
    allpairs=[];contrasts=[];decomp=[];matched=[];matched_summary=[];transitions=[];admission_rows=[];timing=[]
    for delay in DELAYS[1:]:
        treatment=opp[opp.delay_minutes==delay]
        pairs=baseline[paircols].merge(treatment[paircols+['entry_quote_move']],on=PAIR,suffixes=('_baseline','_delayed'),validate='one_to_one')
        pairs['delay_minutes']=delay
        for q,col in [(baseline_ledger,'baseline_admitted'),(ledger[ledger.delay_minutes==delay],'delayed_admitted')]:
            pairs[col]=pd.MultiIndex.from_frame(pairs[PAIR]).isin(pd.MultiIndex.from_frame(q[PAIR]))
        pairs['delta_net_return']=pairs.net_return_delayed-pairs.net_return_baseline
        pairs['reason_changed']=pairs.reason_baseline!=pairs.reason_delayed
        pairs['exit_minute_changed']=pairs.exit_i_baseline!=pairs.exit_i_delayed
        pairs['baseline_hit_before_delayed_entry']=(pairs.exit_i_baseline<pairs.entry_i_delayed)&pairs.reason_baseline.isin(['stop','target'])
        allpairs.append(pairs)
        for (part,stress),g in ledger[ledger.delay_minutes.isin([0,delay])].groupby(['partition','stress']):
            a=g[g.delay_minutes==0];b=g[g.delay_minutes==delay]
            ai=pd.MultiIndex.from_frame(a[KEYS]);bi=pd.MultiIndex.from_frame(b[KEYS])
            shared_a=a[ai.isin(bi)];shared_b=b[bi.isin(ai)];new=b[~bi.isin(ai)];lost=a[~ai.isin(bi)]
            common=shared_b.merge(shared_a[KEYS+['net_return']],on=KEYS,suffixes=('_delayed','_baseline'),validate='one_to_one')
            shared_delta=float((common.net_return_delayed-common.net_return_baseline).sum());actual=float(b.net_return.sum()-a.net_return.sum())
            assert np.isclose(actual,shared_delta+new.net_return.sum()-lost.net_return.sum(),atol=1e-12)
            meta=dict(delay_minutes=delay,partition=part,stress=int(stress))
            decomp.append(meta|dict(shared=len(shared_b),newly_admitted=len(new),displaced=len(lost),shared_delta_net_sum=shared_delta,new_net_sum=new.net_return.sum(),displaced_baseline_net_sum=lost.net_return.sum(),actual_difference_additive_sum=actual))
            for name,q in [('shared',shared_b),('newly_admitted',new),('displaced',lost)]:admission_rows.append(q.assign(comparison_delay_minutes=delay,admission_status=name))
            contrasts.append(meta|dict(view='full_admission_replay',difference_mean_net=b.net_return.mean()-a.net_return.mean())|aligned_contrast(b,a,part))
            raw=treatment[(treatment.partition==part)&(treatment.stress==stress)]
            match=raw[pd.MultiIndex.from_frame(raw[KEYS]).isin(ai)].copy()
            # Missing endpoints must remain explicit; never silently change paired denominators.
            base_match=a[ai.isin(pd.MultiIndex.from_frame(match[KEYS]))]
            matched.append(match.assign(view='counterfactual_original_admitted_signals'))
            matched_summary.append(meta|dict(view='counterfactual_original_admitted_signals',original_admitted=len(a),unfilled_endpoints=len(a)-len(match))|report_metrics(match,STOP,*PERIODS[part]))
            contrasts.append(meta|dict(view='counterfactual_original_admitted_signals',difference_mean_net=match.net_return.mean()-base_match.net_return.mean())|aligned_contrast(match,base_match,part))
            p=pairs[(pairs.partition==part)&(pairs.stress==stress)]
            for scope,q in [('all_raw',p),('baseline_admitted',p[p.baseline_admitted])]:
                for (fr,to),cell in q.groupby(['reason_baseline','reason_delayed']):
                    transitions.append(meta|dict(scope=scope,from_reason=fr,to_reason=to,n=len(cell),difference_additive_sum=cell.delta_net_return.sum(),exit_minute_changes=int(cell.exit_minute_changed.sum())))
                timing.append(meta|dict(scope=scope,n=len(q),mean_adverse_entry_move=q.entry_quote_move.mean(),median_adverse_entry_move=q.entry_quote_move.median(),pre_entry_baseline_stops=int((q.baseline_hit_before_delayed_entry&(q.reason_baseline=='stop')).sum()),pre_entry_baseline_targets=int((q.baseline_hit_before_delayed_entry&(q.reason_baseline=='target')).sum())))
    p=pd.concat(allpairs,ignore_index=True);p.to_csv(out/'paired_raw_outcomes.csv',index=False)
    p[p.reason_changed|p.exit_minute_changed|(p.baseline_admitted!=p.delayed_admitted)].to_csv(out/'changed_trade_paths.csv',index=False)
    pd.DataFrame(contrasts).to_csv(out/'contrasts.csv',index=False);pd.DataFrame(decomp).to_csv(out/'admission_decomposition.csv',index=False)
    pd.DataFrame(transitions).to_csv(out/'outcome_transitions.csv',index=False);pd.DataFrame(timing).to_csv(out/'entry_timing_diagnostics.csv',index=False)
    pd.concat(matched,ignore_index=True).to_csv(out/'matched_baseline_signals.csv',index=False);pd.DataFrame(matched_summary).to_csv(out/'matched_results.csv',index=False)
    pd.concat(admission_rows,ignore_index=True).to_csv(out/'admission_changes.csv',index=False)
    return len(decomp)

def preflight(cache,runtime,out):
    out.mkdir(parents=True,exist_ok=False);verify_references(cache,runtime)
    _,_,_,v=calculate(cache,out,[0]);v['delayed_outcomes_scored']=False;write(out/'VERIFICATION.json',v);print(json.dumps(v,indent=2))

def freeze(cache,runtime,out,commit):
    inputs,refs,rt=verify_references(cache,runtime)
    pre=json.loads((HERE/'preflight_v2/VERIFICATION.json').read_text());assert pre['status']=='pass' and pre['delayed_outcomes_scored'] is False
    sources={str(p.relative_to(ROOT)):sha(p) for p in ROOT.rglob('*.py')}
    for n in ['PROTOCOL.md','NOVELTY_AUDIT.md','TEST_VERIFICATION.json','preflight_v2/VERIFICATION.json']:sources[str((HERE/n).relative_to(ROOT))]=sha(HERE/n)
    out.mkdir(parents=True,exist_ok=False)
    write(out/'freeze.json',dict(frozen_at=dt.datetime.now(dt.timezone.utc).isoformat(),protocol_commit=commit,sources=sources,inputs=inputs,cached_references=refs,runtime_sources=rt,delays_minutes=DELAYS,primary_delay_minutes=PRIMARY_DELAY,periods=PERIODS,stop=STOP,target=TARGET,independent_holdout=False,only_change='fill at original signal time plus constant delay; brackets reanchor to actual fill',packages=dict(python=platform.python_version(),numpy=np.__version__,pandas=pd.__version__,pyarrow=pa.__version__)))
    print('FROZEN',out,flush=True)

def run(cache,runtime,out):
    f=json.loads((out/'freeze.json').read_text())
    for group,root in [('sources',ROOT),('inputs',cache),('runtime_sources',runtime),('cached_references',ROOT)]:
        for n,h in f[group].items():assert sha(root/n)==h,n
    assert not (out/'status.json').exists(),'Preserve every attempt'
    write(out/'status.json',dict(status='running',started_at=dt.datetime.now(dt.timezone.utc).isoformat()))
    opp,t,s,v=calculate(cache,out,DELAYS);v['admission_attribution_checks']=comparisons(opp,t,out);write(out/'VERIFICATION.json',v)
    checks={}
    for delay in DELAYS[1:]:
        checks[str(delay)]={}
        for part in PERIODS:
            q=s[(s.delay_minutes==delay)&(s.partition==part)]
            checks[str(delay)][part]=bool(len(q)==2 and (q.n_closed>0).all() and (q['mean']>0).all())
    write(out/'decision.json',dict(primary_delay_minutes=PRIMARY_DELAY,primary_positive_point_screen=all(checks[str(PRIMARY_DELAY)].values()),checks=checks,automatic_deployment=False,independent_edge_established=False,production_execution_parity=False,additional_token_outcomes_scored=False))
    write(out/'status.json',dict(status='complete',completed_at=dt.datetime.now(dt.timezone.utc).isoformat(),output_hashes={p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='status.json'}))
    print(s[['delay_minutes','partition','stress','n','mean','stop_count','target_count','boundary_count']].to_string(index=False),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['preflight','freeze','run']);p.add_argument('--cache',type=Path,required=True);p.add_argument('--runtime',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--protocol-commit');a=p.parse_args()
    if a.command=='freeze':
        assert a.protocol_commit and len(a.protocol_commit)==40;freeze(a.cache,a.runtime,a.out,a.protocol_commit)
    else:globals()[a.command](a.cache,a.runtime,a.out)
