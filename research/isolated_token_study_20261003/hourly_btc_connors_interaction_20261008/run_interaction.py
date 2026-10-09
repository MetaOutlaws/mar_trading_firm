"""Frozen four-arm interaction using independently validated cached paths."""
import argparse, datetime as dt, json, platform, sys
from pathlib import Path
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
sys.path.insert(0,str(ROOT/'hourly_extension_filter_20261007'))
from run_extension import admit,replay,sha,write,report_metrics,score,contrast,reconcile,KEYS,STOP,TARGET,PERIODS,SYMBOLS
sys.path.insert(0,str(ROOT/'hourly_btc_confirmation_20261007'))
from btc_rule import confirmation
sys.path.insert(0,str(ROOT/'hourly_connors_filter_20261008'))
from connors_rule import gate
BTC=ROOT/'hourly_btc_confirmation_20261007/results_v1'
CRSI=ROOT/'hourly_connors_filter_20261008/results_v1'
ARMS=('baseline','btc24_confirm','crsi_not_exhausted','both')

def freeze(cache,out,commit):
    out.mkdir(parents=True,exist_ok=False)
    refs={}
    for p in [BTC,CRSI]:
        status=json.loads((p/'status.json').read_text());assert status['status']=='complete'
        old=json.loads((p/'freeze.json').read_text())
        for n,h in status['output_hashes'].items():assert sha(p/n)==h,n
        for n,h in old['sources'].items():assert sha(ROOT/n)==h,n
        for n,h in old['features'].items():assert sha(ROOT/n)==h,n
        for n,h in old['inputs'].items():assert sha(cache/n)==h,n
        for n in ['status.json','freeze.json','all_opportunities.parquet','pooled_ledger.parquet','VERIFICATION.json']:
            refs[str((p/n).relative_to(ROOT))]=sha(p/n)
    sources={str(p.relative_to(ROOT)):sha(p) for p in ROOT.rglob('*.py')}
    sources[str((HERE/'PROTOCOL.md').relative_to(ROOT))]=sha(HERE/'PROTOCOL.md')
    write(out/'freeze.json',dict(frozen_at=dt.datetime.now(dt.timezone.utc).isoformat(),protocol_commit=commit,
        inputs=old['inputs'],features=old['features'],sources=sources,cached_references=refs,
        arms=ARMS,stop=STOP,target=TARGET,scores_2026=False,
        packages=dict(python=platform.python_version(),numpy=np.__version__,pandas=pd.__version__)))
    print('FROZEN',out,flush=True)

def run(cache,out):
    f=json.loads((out/'freeze.json').read_text())
    for kind,root in [('inputs',cache),('features',ROOT),('sources',ROOT),('cached_references',ROOT)]:
        for n,h in f[kind].items():assert sha(root/n)==h,n
    assert not (out/'status.json').exists(),'Preserve attempts'
    write(out/'status.json',dict(status='running',started_at=dt.datetime.now(dt.timezone.utc).isoformat()))
    raw=pd.read_parquet(CRSI/'all_opportunities.parquet').query('arm == "baseline"').copy()
    btc=pd.read_parquet(BTC/'all_opportunities.parquet').query('arm == "baseline"').copy()
    raw_n=reconcile(raw,btc);assert raw_n==286
    cols=['btc_close','btc_close_24h_ago','btc24','btc_asof','btc_last_minute','passes_btc']
    raw=raw.merge(btc[KEYS+['stress']+cols],on=KEYS+['stress'],validate='one_to_one')
    assert (raw.btc_asof==raw.entry).all() and (raw.crsi_asof==raw.entry).all()
    assert (raw.btc_last_minute<raw.entry).all() and (raw.crsi_last_minute<raw.entry).all()
    assert np.array_equal(gate(raw.filter_crsi,raw.side),raw.passes_crsi)
    check=np.array([bool(confirmation(r.symbol,r.side,r.btc24)) for r in raw.itertuples()])
    assert np.array_equal(check,raw.passes_btc)
    assert np.allclose(raw.filter_crsi,(raw.price_rsi3+raw.streak_rsi2+raw.rank100)/3,atol=1e-12)
    raw['passes_both']=raw.passes_btc & raw.passes_crsi
    masks={'baseline':np.ones(len(raw),bool),'btc24_confirm':raw.passes_btc,'crsi_not_exhausted':raw.passes_crsi,'both':raw.passes_both}
    opp=pd.concat([raw.loc[m].assign(arm=a) for a,m in masks.items()],ignore_index=True)
    opp.to_parquet(out/'all_opportunities.parquet',index=False)
    raw.to_csv(out/'raw_signal_outcomes.csv',index=False)
    ledgers=[];rejections=[];summaries=[];annual=[];subgroups=[];leaveouts=[]
    for arm in ARMS:
        for part,(a,z) in PERIODS.items():
            for stress in [1,2]:
                g=opp[(opp.arm==arm)&(opp.partition==part)&(opp.stress==stress)]
                t,rej=admit(g);ids,counts=replay(g)
                assert ids==list(t[['symbol','tf','side','entry_i']].itertuples(index=False,name=None))
                assert counts==(rej.reason.value_counts().to_dict() if len(rej) else {})
                assert len(t)+len(rej)==len(g)
                meta=dict(arm=arm,partition=part,stress=stress)
                ledgers.append(t)
                if len(rej):rejections.append(rej.assign(**meta))
                summaries.append(meta|dict(sum_net_R=float(t.net_R.sum()),opportunities=len(g),rejected=len(rej))|report_metrics(t,STOP,a,z))
                for year,y in t.groupby(t.entry.dt.year):annual.append(meta|dict(entry_year=int(year))|score(y,STOP))
                for grouping in [['symbol'],['side'],['symbol','side']]:
                    for keys,y in t.groupby(grouping):
                        keys=keys if isinstance(keys,tuple) else (keys,)
                        subgroups.append(meta|dict(grouping='+'.join(grouping))|dict(zip(grouping,keys))|score(y,STOP))
                for s in SYMBOLS:
                    q=t[t.symbol!=s];leaveouts.append(meta|dict(excluded_symbol=s,n=len(q),mean_net=q.net_return.mean(),method='remove from admitted ledger, no replacement replay'))
    ledger=pd.concat(ledgers,ignore_index=True);reconciled={}
    for arm,p in [('baseline',CRSI),('btc24_confirm',BTC),('crsi_not_exhausted',CRSI)]:
        old=pd.read_parquet(p/'pooled_ledger.parquet');old=old[old.arm==arm]
        reconciled[arm]=reconcile(old,ledger[ledger.arm==arm])
    assert ledger.exit_bar.max()<pd.Timestamp('2026-01-01',tz='UTC')
    assert np.allclose(ledger.net_return,ledger.quoted_return-ledger.slippage_drag-ledger.fees-ledger.funding,atol=1e-12,rtol=0)
    for _,q in ledger.groupby(['arm','partition','stress','symbol']):
        q=q.sort_values('entry');assert (q.entry.to_numpy()[1:]>q.exit_bar.to_numpy()[:-1]).all()
    ledger.to_parquet(out/'pooled_ledger.parquet',index=False);ledger.to_csv(out/'individual_trades.csv',index=False)
    summary=pd.DataFrame(summaries);summary.to_csv(out/'pooled_results.csv',index=False)
    pd.DataFrame(annual).to_csv(out/'annual_by_entry_year.csv',index=False)
    pd.DataFrame(subgroups).to_csv(out/'subgroups.csv',index=False)
    pd.DataFrame(leaveouts).to_csv(out/'leave_one_token_out.csv',index=False)
    (pd.concat(rejections,ignore_index=True) if rejections else pd.DataFrame()).to_csv(out/'rejections.csv',index=False)
    comparisons=[];changes=[];decomp=[]
    for (part,stress),g in ledger.groupby(['partition','stress']):
        t=g[g.arm=='both'];ti=pd.MultiIndex.from_frame(t[KEYS])
        for comparator in ARMS[:-1]:
            b=g[g.arm==comparator];bi=pd.MultiIndex.from_frame(b[KEYS])
            meta=dict(partition=part,stress=int(stress),treatment='both',comparator=comparator)
            comparisons.append(meta|dict(difference_mean_net=t.net_return.mean()-b.net_return.mean())|contrast(t,b,*PERIODS[part]))
            left=b[~bi.isin(ti)];new=t[~ti.isin(bi)];shared=t[ti.isin(bi)]
            reconcile(shared,b[bi.isin(ti)])
            direct=left[~left.passes_both];occupied=left[left.passes_both]
            delta=t.net_return.sum()-b.net_return.sum()
            assert np.isclose(delta,new.net_return.sum()-direct.net_return.sum()-occupied.net_return.sum(),atol=1e-12)
            row=meta|dict(shared=len(shared),direct_exclusions=len(direct),lost_through_occupancy=len(occupied),newly_admitted=len(new),
                direct_excluded_net_sum=direct.net_return.sum(),occupancy_lost_net_sum=occupied.net_return.sum(),new_net_sum=new.net_return.sum(),actual_difference_net_sum=delta)
            for label,q in [('retained',shared),('excluded_by_combination',direct),('lost_to_changed_occupancy',occupied),('newly_admitted',new)]:
                changes.append(q.assign(comparator=comparator,admission_status=label))
                row[label+'_stops']=int((q.reason=='stop').sum());row[label+'_targets']=int((q.reason=='target').sum())
            decomp.append(row)
    comparisons=pd.DataFrame(comparisons);comparisons.to_csv(out/'contrasts.csv',index=False)
    pd.DataFrame(decomp).to_csv(out/'admission_decomposition.csv',index=False)
    pd.concat(changes,ignore_index=True).to_csv(out/'admission_changes.csv',index=False)
    overlap=[]
    raw['filter_overlap']=np.select([raw.passes_both,~raw.passes_btc&raw.passes_crsi,raw.passes_btc&~raw.passes_crsi],['both_pass','btc_only_reject','crsi_only_reject'],default='both_reject')
    for (part,stress,group),q in raw.groupby(['partition','stress','filter_overlap']):
        overlap.append(dict(partition=part,stress=int(stress),filter_overlap=group,n=len(q),stop_count=int((q.reason=='stop').sum()),target_count=int((q.reason=='target').sum()),mean_net=q.net_return.mean()))
    pd.DataFrame(overlap).to_csv(out/'filter_overlap.csv',index=False)
    t=summary[(summary.arm=='both')&(summary.stress==2)]
    checks=dict(positive_stressed_both=bool(len(t)==2 and (t['mean']>0).all()),nonempty_both=bool(len(t)==2 and (t.n_closed>0).all()))
    for comparator in ARMS[:-1]:
        d=comparisons[(comparisons.comparator==comparator)&(comparisons.stress==2)]
        checks['improved_vs_'+comparator+'_both']=bool(len(d)==2 and (d.difference_mean_net>0).all())
    write(out/'decision.json',dict(checks=checks,exploratory_point_pass=all(checks.values()),independent_edge_established=False,deployment_qualified=False,scores_2026=False))
    write(out/'VERIFICATION.json',dict(status='pass',cached_raw_cost_rows_reconciled=raw_n,prior_arm_cost_rows_reconciled=reconciled,
        independent_admission_runs=16,causal_predicate_rows=286,ledger_rows=len(ledger),cached_minute_paths=143,new_minute_paths_simulated=0,
        attribution_checks=12,cost_causality='pass',scores_2026=False))
    write(out/'status.json',dict(status='complete',completed_at=dt.datetime.now(dt.timezone.utc).isoformat(),output_hashes={p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='status.json'}))
    print(summary[['arm','partition','stress','n','mean','stop_count','target_count']].to_string(index=False),flush=True)
    print(json.dumps(checks,indent=2),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['freeze','run']);p.add_argument('--cache',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--protocol-commit')
    a=p.parse_args()
    if a.command=='freeze':
        assert a.protocol_commit and len(a.protocol_commit)==40;freeze(a.cache,a.out,a.protocol_commit)
    else:run(a.cache,a.out)
