"""Isolate bracket origin using exactly the approved frozen signal universe."""
import argparse,datetime as dt,json,platform,sys
from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow as pa
pa.set_cpu_count(1);pa.set_io_thread_count(1)
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
sys.path.insert(0,str(ROOT/'hourly_reserved_2026_20261008'))
from run_replication_2026 import load,independent_cost
from run_extension import base,admit,replay,sha,write,score,report_metrics,reconcile,contrast,KEYS
from bracket_rule import STOP,TARGET,levels,raw_trade,independent_path
PERIODS={'historical':('2022-01-01','2025-01-01'),'evaluation':('2025-01-01','2026-01-01'),'reserved_replication':('2026-01-01','2026-10-02 16:00')}
REFS=[ROOT/'hourly_extension_regime_20261008/results_v1',ROOT/'hourly_reserved_2026_20261008/results_v1']
ARMS=['quote_brackets','fill_brackets'];SYMBOLS=['BTCUSDT','ETHUSDT','SOLUSDT']
PAIR=KEYS+['stress']

def references():
    opportunities=[];ledgers=[]
    for p in REFS:
        for name,collection in [('all_opportunities.parquet',opportunities),('pooled_ledger.parquet',ledgers)]:
            q=pd.read_parquet(p/name,use_threads=False)
            if p==REFS[0]:q=q[q.arm=='combo_loweff'].copy()
            collection.append(q)
    a=pd.concat(opportunities,ignore_index=True);b=pd.concat(ledgers,ignore_index=True)
    assert len(a)==138 and len(b)==130 and not a.duplicated(PAIR).any() and not b.duplicated(PAIR).any()
    assert (a.tf==60).all() and (a.stop==STOP).all() and (a.target==TARGET).all()
    for col in ['prior_atr','volume_ratio','rsi14','r24','feature_asof','hourly_asof']:
        old='entry_'+col
        if old in a:a[col]=a[col].fillna(a[old])
    a['arm']='quote_brackets';b['arm']='quote_brackets'
    return a,b

def verify_reference_files(cache,runtime):
    refs={}
    for p in REFS:
        f=json.loads((p/'freeze.json').read_text());status=json.loads((p/'status.json').read_text());assert status['status']=='complete'
        for group,root in [('sources',ROOT),('inputs',cache),('features',ROOT),('cached_references',ROOT),('runtime_sources',runtime)]:
            for n,h in f.get(group,{}).items():assert sha(root/n)==h,n
        for n,h in status['output_hashes'].items():assert sha(p/n)==h,n
        for n in ['freeze.json','status.json','VERIFICATION.json','all_opportunities.parquet','pooled_ledger.parquet']:
            refs[str((p/n).relative_to(ROOT))]=sha(p/n)
    return f['inputs'],refs

def calculate(cache,runtime,out,arms):
    old,old_ledger=references();signals=old[old.stress==1].copy();assert len(signals)==69
    sys.path.insert(0,str(runtime))
    from core.execution.contract import risk_levels
    outputs=[];paths=costs=runtime_checks=0
    for symbol in SYMBOLS:
        for limit,parts in [('2026-01-01',['historical','evaluation']),('2026-10-02 16:00',['reserved_replication'])]:
            c,f=load(cache,symbol,limit);tape=base.Tape(c,f)
            selected=signals[(signals.symbol==symbol)&signals.partition.isin(parts)]
            for (part,side),g in selected.groupby(['partition','side']):
                side=int(side);end=int(c.index.searchsorted(pd.Timestamp(PERIODS[part][1],tz='UTC')));lookup=g.set_index('entry_i')
                for stress in [1,2]:
                    slip=(.001 if symbol=='SOLUSDT' else .0005)*stress
                    for arm in arms:
                        raw=[]
                        for i in g.entry_i:
                            r=raw_trade(tape,int(i),side,slip,end,arm);independent_path(tape,r,side,slip,end,arm);paths+=1
                            tp,sl=risk_levels(r['bracket_anchor'],'LONG' if side==1 else 'SHORT',TARGET,STOP)
                            assert np.isclose(tp,r['target_price'],atol=1e-10) and np.isclose(sl,r['stop_price'],atol=1e-10);runtime_checks+=1
                            raw.append(r)
                        t=enrich(tape,pd.DataFrame(raw),side,slip,STOP).assign(symbol=symbol,side=side,tf=60,partition=part,stress=stress,slippage_per_side=slip,stop=STOP,target=TARGET,arm=arm)
                        assert np.allclose(t.entry_price,t.entry_fill,atol=1e-12,rtol=0)
                        for col in ['rank','filter_crsi','btc24','efficiency24_before_signal','directional','extension_atr','entry_boundary','prior_atr','volume_ratio','rsi14','r24','feature_asof','hourly_asof','crsi_asof','btc_asof','regime_asof']:
                            t[col]=t.entry_i.map(lookup[col])
                        assert (t.feature_asof==t.entry).all() and (t.hourly_asof==t.entry).all() and (t.regime_asof<t.entry).all()
                        for r in t.itertuples():independent_cost(c,f,r,side,slip);costs+=1
                        outputs.append(t)
        print('PATHS_AND_COSTS_VERIFIED',symbol,flush=True)
    opp=pd.concat(outputs,ignore_index=True);n=reconcile(opp[opp.arm=='quote_brackets'],old);assert n==138
    opp.to_parquet(out/'all_opportunities.parquet',index=False);signals.to_parquet(out/'frozen_approved_signals.parquet',index=False)
    ledgers=[];rejected=[];summaries=[];subs=[];loo=[];admissions=0
    for arm in arms:
        for part,(a,z) in PERIODS.items():
            for stress in [1,2]:
                g=opp[(opp.arm==arm)&(opp.partition==part)&(opp.stress==stress)]
                t,rej=admit(g);ids,counts=replay(g)
                assert ids==list(t[['symbol','tf','side','entry_i']].itertuples(index=False,name=None))
                assert counts==(rej.reason.value_counts().to_dict() if len(rej) else {}) and len(t)+len(rej)==len(g)
                for _,q in t.groupby('symbol'):
                    q=q.sort_values('entry');assert (q.entry.to_numpy()[1:]>q.exit_bar.to_numpy()[:-1]).all()
                meta=dict(arm=arm,partition=part,stress=stress);admissions+=1;ledgers.append(t)
                if len(rej):rejected.append(rej.assign(**meta))
                summaries.append(meta|dict(opportunities=len(g),rejected=len(rej))|report_metrics(t,STOP,a,z))
                t=t.assign(entry_year=t.entry.dt.year)
                for group in [['symbol'],['side'],['symbol','side'],['entry_year']]:
                    for key,q in t.groupby(group):
                        key=key if isinstance(key,tuple) else (key,)
                        subs.append(meta|dict(grouping='+'.join(group))|dict(zip(group,key))|score(q,STOP))
                for symbol in SYMBOLS:
                    q=t[t.symbol!=symbol];loo.append(meta|dict(excluded_symbol=symbol,n=len(q),mean_net=q.net_return.mean(),method='remove from admitted ledger; no replacement replay'))
    ledger=pd.concat(ledgers,ignore_index=True);m=reconcile(ledger[ledger.arm=='quote_brackets'],old_ledger);assert m==130
    ledger.to_parquet(out/'pooled_ledger.parquet',index=False);ledger.to_csv(out/'individual_trades.csv',index=False)
    summary=pd.DataFrame(summaries);summary.to_csv(out/'pooled_results.csv',index=False)
    pd.DataFrame(subs).to_csv(out/'subgroups.csv',index=False);pd.DataFrame(loo).to_csv(out/'leave_one_token_out.csv',index=False)
    (pd.concat(rejected,ignore_index=True) if rejected else pd.DataFrame(columns=['arm','partition','stress','reason'])).to_csv(out/'rejections.csv',index=False)
    verification=dict(status='pass',unique_frozen_signals=69,independent_minute_paths=paths,independent_cost_rows=costs,runtime_risk_level_checks=runtime_checks,independent_admission_runs=admissions,quote_opportunity_rows_reconciled=n,quote_admitted_rows_reconciled=m,ledger_rows=len(ledger))
    return opp,ledger,summary,verification

from run_extension import enrich

def comparisons(opp,ledger,out):
    a=opp[opp.arm=='quote_brackets'];b=opp[opp.arm=='fill_brackets']
    cols=PAIR+['entry','exit_bar','exit_i','reason','quote','entry_price','exit_price','stop_price','target_price','fees','funding','net_return','net_R','holding_minutes','ambiguous']
    pairs=a[cols].merge(b[cols],on=PAIR,suffixes=('_quote','_fill'),validate='one_to_one')
    for arm,col in [('quote_brackets','baseline_admitted'),('fill_brackets','treatment_admitted')]:
        ids=pd.MultiIndex.from_frame(ledger[ledger.arm==arm][PAIR]);pairs[col]=pd.MultiIndex.from_frame(pairs[PAIR]).isin(ids)
    pairs['delta_net_return']=pairs.net_return_fill-pairs.net_return_quote
    pairs['reason_changed']=pairs.reason_quote!=pairs.reason_fill;pairs['exit_minute_changed']=pairs.exit_i_quote!=pairs.exit_i_fill
    pairs.to_csv(out/'paired_raw_outcomes.csv',index=False)
    pairs[pairs.reason_changed|pairs.exit_minute_changed|(pairs.baseline_admitted!=pairs.treatment_admitted)].to_csv(out/'changed_trade_paths.csv',index=False)
    contrasts=[];decomp=[];matched=[];matched_summary=[];transitions=[];admission_rows=[]
    for (part,stress),g in ledger.groupby(['partition','stress']):
        aa=g[g.arm=='quote_brackets'];bb=g[g.arm=='fill_brackets'];ai=pd.MultiIndex.from_frame(aa[KEYS]);bi=pd.MultiIndex.from_frame(bb[KEYS])
        oldshared=aa[ai.isin(bi)];shared=bb[bi.isin(ai)];new=bb[~bi.isin(ai)];dropped=aa[~ai.isin(bi)]
        ta=shared.merge(oldshared[KEYS+['net_return']],on=KEYS,suffixes=('_fill','_quote'))
        shared_delta=float((ta.net_return_fill-ta.net_return_quote).sum());delta=float(bb.net_return.sum()-aa.net_return.sum())
        assert np.isclose(delta,shared_delta+new.net_return.sum()-dropped.net_return.sum(),atol=1e-12)
        meta=dict(partition=part,stress=int(stress))
        row=meta|dict(shared=len(shared),newly_admitted=len(new),displaced=len(dropped),shared_delta_net_sum=shared_delta,new_net_sum=new.net_return.sum(),displaced_quote_net_sum=dropped.net_return.sum(),actual_difference_additive_sum=delta)
        for label,q in [('shared',shared),('newly_admitted',new),('displaced',dropped)]:
            row[label+'_stops']=int((q.reason=='stop').sum());row[label+'_targets']=int((q.reason=='target').sum());admission_rows.append(q.assign(admission_status=label))
        decomp.append(row)
        contrasts.append(meta|dict(view='full_admission_replay',difference_mean_net=bb.net_return.mean()-aa.net_return.mean())|contrast(bb,aa,*PERIODS[part]))
        rawb=b[(b.partition==part)&(b.stress==stress)]
        match=rawb[pd.MultiIndex.from_frame(rawb[KEYS]).isin(ai)].copy();assert len(match)==len(aa)
        match['view']='counterfactual_original_admitted_entries';matched.append(match)
        matched_summary.append(meta|dict(arm='fill_brackets',view='counterfactual_original_admitted_entries')|report_metrics(match,STOP,*PERIODS[part]))
        contrasts.append(meta|dict(view='counterfactual_original_admitted_entries',difference_mean_net=match.net_return.mean()-aa.net_return.mean())|contrast(match,aa,*PERIODS[part]))
        p=pairs[(pairs.partition==part)&(pairs.stress==stress)]
        for scope,q in [('all_raw',p),('original_admitted',p[p.baseline_admitted])]:
            for (fr,to),cell in q.groupby(['reason_quote','reason_fill']):
                transitions.append(meta|dict(scope=scope,from_reason=fr,to_reason=to,n=len(cell),difference_additive_sum=cell.delta_net_return.sum(),exit_minute_changes=int(cell.exit_minute_changed.sum())))
    pd.DataFrame(contrasts).to_csv(out/'contrasts.csv',index=False);pd.DataFrame(decomp).to_csv(out/'admission_decomposition.csv',index=False)
    pd.concat(admission_rows,ignore_index=True).to_csv(out/'admission_changes.csv',index=False)
    pd.concat(matched,ignore_index=True).to_csv(out/'matched_baseline_entries.csv',index=False)
    pd.DataFrame(matched_summary).to_csv(out/'matched_results.csv',index=False);pd.DataFrame(transitions).to_csv(out/'outcome_transitions.csv',index=False)
    return len(decomp)

def preflight(cache,runtime,out):
    out.mkdir(parents=True,exist_ok=False);verify_reference_files(cache,runtime)
    _,_,_,v=calculate(cache,runtime,out,['quote_brackets']);v['new_fill_outcomes_scored']=False
    write(out/'VERIFICATION.json',v);print(json.dumps(v,indent=2))

def freeze(cache,runtime,out,commit):
    inputs,refs=verify_reference_files(cache,runtime);pre=json.loads((HERE/'preflight_v1/VERIFICATION.json').read_text());assert pre['status']=='pass' and pre['new_fill_outcomes_scored'] is False
    sources={str(p.relative_to(ROOT)):sha(p) for p in ROOT.rglob('*.py')}
    for p in [HERE/'PROTOCOL.md',HERE/'NOVELTY_AUDIT.md',HERE/'preflight_v1/VERIFICATION.json',HERE/'TEST_VERIFICATION.json',ROOT/'hourly_expanded_replication_20261008/PROTOCOL.md']:
        sources[str(p.relative_to(ROOT))]=sha(p)
    rt=json.loads((REFS[-1]/'freeze.json').read_text())['runtime_sources']
    out.mkdir(parents=True,exist_ok=False)
    write(out/'freeze.json',dict(frozen_at=dt.datetime.now(dt.timezone.utc).isoformat(),protocol_commit=commit,sources=sources,runtime_sources=rt,inputs=inputs,cached_references=refs,arms=ARMS,periods=PERIODS,stop=STOP,target=TARGET,only_change='bracket anchor quote versus slipped fill',scores_2026=True,independent_holdout=False,packages=dict(python=platform.python_version(),numpy=np.__version__,pandas=pd.__version__,pyarrow=pa.__version__)))
    print('FROZEN',out,flush=True)

def run(cache,runtime,out):
    f=json.loads((out/'freeze.json').read_text())
    for group,root in [('sources',ROOT),('inputs',cache),('runtime_sources',runtime),('cached_references',ROOT)]:
        for n,h in f[group].items():assert sha(root/n)==h,n
    assert not (out/'status.json').exists(),'Preserve attempts'
    write(out/'status.json',dict(status='running',started_at=dt.datetime.now(dt.timezone.utc).isoformat()))
    opp,t,s,v=calculate(cache,runtime,out,ARMS);v['admission_attribution_checks']=comparisons(opp,t,out);write(out/'VERIFICATION.json',v)
    checks={}
    for part in PERIODS:
        q=s[(s.arm=='fill_brackets')&(s.partition==part)]
        checks[part]=bool(len(q)==2 and (q.n_closed>0).all() and (q['mean']>0).all())
    write(out/'decision.json',dict(positive_point_robustness_all_periods=all(checks.values()),checks=checks,statistical_equivalence_established=False,independent_edge_established=False,production_execution_parity=False,automatic_deployment=False,additional_token_outcomes_scored=False))
    write(out/'status.json',dict(status='complete',completed_at=dt.datetime.now(dt.timezone.utc).isoformat(),output_hashes={p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='status.json'}))
    print(s[['arm','partition','stress','n','mean','stop_count','target_count','boundary_count']].to_string(index=False),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['preflight','freeze','run']);p.add_argument('--cache',type=Path,required=True);p.add_argument('--runtime',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--protocol-commit');a=p.parse_args()
    if a.command=='freeze':
        assert a.protocol_commit and len(a.protocol_commit)==40;freeze(a.cache,a.runtime,a.out,a.protocol_commit)
    else:globals()[a.command](a.cache,a.runtime,a.out)
