"""One fixed causal state, extension only; current benchmark plus historical diagnostic."""
import argparse,datetime as dt,json,platform,sys
from pathlib import Path
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
sys.path.insert(0,str(ROOT/'hourly_extension_filter_20261007'))
from run_extension import admit,replay,sha,write,load,report_metrics,score,contrast,reconcile,KEYS,STOP,TARGET,PERIODS,SYMBOLS
from regime_rule import context,independent_at,policy_pass
INTER=ROOT/'hourly_btc_connors_interaction_20261008/results_v1'
EXT=ROOT/'hourly_extension_filter_20261007/results_v1'
POLICIES=('none','always','directional','loweff');ARMS=tuple(f'{b}_{p}' for b in ['combo','original'] for p in POLICIES)

def freeze(cache,out,commit):
 out.mkdir(parents=True,exist_ok=False);refs={}
 for p in [INTER,EXT]:
  st=json.loads((p/'status.json').read_text());assert st['status']=='complete'
  fr=json.loads((p/'freeze.json').read_text())
  for n,h in st['output_hashes'].items():assert sha(p/n)==h,n
  for n,h in fr['sources'].items():assert sha(ROOT/n)==h,n
  for n,h in fr['inputs'].items():assert sha(cache/n)==h,n
  for n,h in fr['features'].items():assert sha(ROOT/n)==h,n
  for n in ['status.json','freeze.json','all_opportunities.parquet','pooled_ledger.parquet','VERIFICATION.json']:refs[str((p/n).relative_to(ROOT))]=sha(p/n)
 sources={str(p.relative_to(ROOT)):sha(p) for p in ROOT.rglob('*.py')}
 sources[str((HERE/'PROTOCOL.md').relative_to(ROOT))]=sha(HERE/'PROTOCOL.md')
 write(out/'freeze.json',dict(frozen_at=dt.datetime.now(dt.timezone.utc).isoformat(),protocol_commit=commit,inputs=fr['inputs'],features=fr['features'],sources=sources,cached_references=refs,arms=ARMS,efficiency_cutoff=.3,extension_cap_atr=1.,stop=STOP,target=TARGET,scores_2026=False,packages=dict(python=platform.python_version(),numpy=np.__version__,pandas=pd.__version__)))
 print('FROZEN',out,flush=True)

def run(cache,out):
 f=json.loads((out/'freeze.json').read_text())
 for kind,root in [('inputs',cache),('sources',ROOT),('features',ROOT),('cached_references',ROOT)]:
  for n,h in f[kind].items():assert sha(root/n)==h,n
 assert not (out/'status.json').exists(),'preserve attempts'
 write(out/'status.json',dict(status='running',started_at=dt.datetime.now(dt.timezone.utc).isoformat()))
 raw=pd.read_parquet(INTER/'all_opportunities.parquet').query('arm=="baseline"').copy()
 ex=pd.read_parquet(EXT/'all_opportunities.parquet').query('arm=="baseline"').copy();assert reconcile(raw,ex)==286
 cols=['signal_close','entry_boundary','extension_atr','passes_extension']
 raw=raw.merge(ex[KEYS+['stress']+cols],on=KEYS+['stress'],validate='one_to_one')
 assert np.allclose(raw.extension_atr,raw.side*(raw.signal_close-raw.entry_boundary)/raw.entry_prior_atr)
 assert np.array_equal(raw.passes_extension,raw.extension_atr<=1.)
 contexts=[];hours=[]
 for symbol in SYMBOLS:
  c,_=load(cache,symbol);closes=c.close.resample('h',closed='left',label='right').last();q=context(closes)
  for part,(a,z) in PERIODS.items():
   valid=q[(q.index>=pd.Timestamp(a,tz='UTC'))&(q.index<pd.Timestamp(z,tz='UTC'))].dropna()
   for state,t in valid.groupby('directional'):hours.append(dict(symbol=symbol,partition=part,directional=bool(state),hours=len(t),total_valid_hours=len(valid)))
  for r in raw[(raw.symbol==symbol)&(raw.stress==1)].itertuples():
   row=q.loc[r.entry];ref=independent_at(c,r.entry)
   assert np.isfinite(row.efficiency24_before_signal) and np.isclose(row.efficiency24_before_signal,ref,atol=1e-12)
   assert row.regime_asof==r.entry-pd.Timedelta(hours=1)
   contexts.append({k:getattr(r,k) for k in KEYS}|row.to_dict())
 ctx=pd.DataFrame(contexts);assert len(ctx)==143
 ctx.to_csv(out/'regime_context.csv',index=False);pd.DataFrame(hours).to_csv(out/'hourly_state_frequency.csv',index=False)
 raw=raw.merge(ctx,on=KEYS,validate='many_to_one');raw.to_csv(out/'raw_signal_outcomes.csv',index=False)
 opp=[]
 for b in ['combo','original']:
  q=raw[raw.passes_both] if b=='combo' else raw
  for p in POLICIES:opp.append(q[policy_pass(q.passes_extension,q.directional,p)].assign(arm=f'{b}_{p}'))
 opp=pd.concat(opp,ignore_index=True);opp.to_parquet(out/'all_opportunities.parquet',index=False)
 ledgers=[];rejections=[];summaries=[];subgroups=[];annual=[];leaveouts=[]
 for arm in ARMS:
  for part,(a,z) in PERIODS.items():
   for stress in [1,2]:
    g=opp[(opp.arm==arm)&(opp.partition==part)&(opp.stress==stress)];t,rej=admit(g);ids,counts=replay(g)
    assert ids==list(t[['symbol','tf','side','entry_i']].itertuples(index=False,name=None))
    assert counts==(rej.reason.value_counts().to_dict() if len(rej) else {}) and len(t)+len(rej)==len(g)
    meta=dict(arm=arm,partition=part,stress=stress,role='primary' if arm.startswith('combo') else 'historical_diagnostic');ledgers.append(t)
    if len(rej):rejections.append(rej.assign(**meta))
    summaries.append(meta|dict(opportunities=len(g),rejected=len(rej))|report_metrics(t,STOP,a,z))
    for year,y in t.groupby(t.entry.dt.year):annual.append(meta|dict(entry_year=int(year))|score(y,STOP))
    for grouping in [['symbol'],['side'],['directional']]:
     for keys,y in t.groupby(grouping):
      keys=keys if isinstance(keys,tuple) else (keys,)
      subgroups.append(meta|dict(grouping='+'.join(grouping))|dict(zip(grouping,keys))|score(y,STOP))
    for symbol in SYMBOLS:
     q=t[t.symbol!=symbol];leaveouts.append(meta|dict(excluded_symbol=symbol,n=len(q),mean_net=q.net_return.mean(),method='remove from admitted ledger; no replacement replay'))
 ledger=pd.concat(ledgers,ignore_index=True);reconciled={}
 for arm,p,oldarm in [('combo_none',INTER,'both'),('original_none',INTER,'baseline'),('original_always',EXT,'extension_cap_1atr')]:
  old=pd.read_parquet(p/'pooled_ledger.parquet');reconciled[arm]=reconcile(ledger[ledger.arm==arm],old[old.arm==oldarm])
 assert ledger.exit_bar.max()<pd.Timestamp('2026-01-01',tz='UTC') and (ledger.regime_asof<ledger.entry).all()
 assert np.allclose(ledger.net_return,ledger.quoted_return-ledger.slippage_drag-ledger.fees-ledger.funding,atol=1e-12,rtol=0)
 for _,g in ledger.groupby(['arm','partition','stress','symbol']):
  g=g.sort_values('entry');assert (g.entry.to_numpy()[1:]>g.exit_bar.to_numpy()[:-1]).all()
 ledger.to_parquet(out/'pooled_ledger.parquet',index=False);ledger.to_csv(out/'individual_trades.csv',index=False)
 summary=pd.DataFrame(summaries);summary.to_csv(out/'pooled_results.csv',index=False)
 for n,x in [('subgroups',subgroups),('annual_by_entry_year',annual),('leave_one_token_out',leaveouts)]:pd.DataFrame(x).to_csv(out/f'{n}.csv',index=False)
 (pd.concat(rejections,ignore_index=True) if rejections else pd.DataFrame()).to_csv(out/'rejections.csv',index=False)
 contrasts=[];changes=[];decomp=[];state_effects=[]
 for (part,stress),g in ledger.groupby(['partition','stress']):
  for base in ['combo','original']:
   b=g[g.arm==base+'_none'];bi=pd.MultiIndex.from_frame(b[KEYS])
   for policy in POLICIES[1:]:
    t=g[g.arm==base+'_'+policy];ti=pd.MultiIndex.from_frame(t[KEYS]);meta=dict(partition=part,stress=int(stress),treatment=base+'_'+policy,comparator=base+'_none')
    contrasts.append(meta|dict(difference_mean_net=t.net_return.mean()-b.net_return.mean())|contrast(t,b,*PERIODS[part]))
    left=b[~bi.isin(ti)];new=t[~ti.isin(bi)];shared=t[ti.isin(bi)];reconcile(shared,b[bi.isin(ti)])
    direct=left[~policy_pass(left.passes_extension,left.directional,policy)];occupied=left[policy_pass(left.passes_extension,left.directional,policy)]
    delta=t.net_return.sum()-b.net_return.sum();assert np.isclose(delta,new.net_return.sum()-direct.net_return.sum()-occupied.net_return.sum(),atol=1e-12)
    row=meta|dict(shared=len(shared),direct_exclusions=len(direct),lost_through_occupancy=len(occupied),newly_admitted=len(new),difference_additive_net_sum=delta)
    for label,q in [('retained',shared),('excluded_by_policy',direct),('lost_to_changed_occupancy',occupied),('newly_admitted',new)]:
     changes.append(q.assign(treatment=base+'_'+policy,comparator=base+'_none',admission_status=label));row[label+'_stops']=int((q.reason=='stop').sum());row[label+'_targets']=int((q.reason=='target').sum());row[label+'_net_sum']=q.net_return.sum()
    decomp.append(row)
   for state,q in b.groupby('directional'):
    kept=q[q.passes_extension];removed=q[~q.passes_extension]
    state_effects.append(dict(base=base,partition=part,stress=int(stress),directional=bool(state),n=len(q),baseline_mean=q.net_return.mean(),retained_n=len(kept),retained_mean=kept.net_return.mean(),removed_n=len(removed),removed_stops=int((removed.reason=='stop').sum()),removed_targets=int((removed.reason=='target').sum()),removed_mean=removed.net_return.mean(),method='diagnostic subset of admitted benchmark, not conditional policy replay'))
 pd.DataFrame(contrasts).to_csv(out/'contrasts.csv',index=False);pd.DataFrame(decomp).to_csv(out/'admission_decomposition.csv',index=False)
 pd.concat(changes,ignore_index=True).to_csv(out/'admission_changes.csv',index=False);pd.DataFrame(state_effects).to_csv(out/'state_effects.csv',index=False)
 checks={}
 for policy in ['directional','loweff']:
  for stress in [1,2]:
   q=pd.DataFrame(contrasts)
   q=q[(q.treatment=='combo_'+policy)&(q.stress==stress)]
   t=summary[(summary.arm=='combo_'+policy)&(summary.stress==stress)]
   checks[f'{policy}_cost{stress}']=bool(len(q)==2 and len(t)==2 and (t['mean']>0).all() and (q.difference_mean_net>=-1e-12).all() and (q.difference_mean_net>1e-12).any())
 write(out/'decision.json',dict(point_screen_by_policy={p:all(checks[f'{p}_cost{x}'] for x in [1,2]) for p in ['directional','loweff']},checks=checks,independent_edge_established=False,statistical_noninferiority_established=False,automatic_deployment=False,scores_2026=False))
 write(out/'VERIFICATION.json',dict(status='pass',independent_regime_contexts=143,cached_raw_cost_rows_reconciled=286,prior_admitted_cost_rows_reconciled=reconciled,independent_admission_runs=32,attribution_checks=24,ledger_rows=len(ledger),new_minute_paths_simulated=0,scores_2026=False))
 write(out/'status.json',dict(status='complete',completed_at=dt.datetime.now(dt.timezone.utc).isoformat(),output_hashes={p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='status.json'}))
 print(summary[['arm','partition','stress','n','mean','stop_count','target_count']].to_string(index=False),flush=True);print(json.dumps(checks),flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('command',choices=['freeze','run']);p.add_argument('--cache',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--protocol-commit');a=p.parse_args()
 if a.command=='freeze':assert a.protocol_commit and len(a.protocol_commit)==40;freeze(a.cache,a.out,a.protocol_commit)
 else:run(a.cache,a.out)
