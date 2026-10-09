"""Historical nomination before later-period entry/outcome diagnostics."""
import argparse,datetime as dt,json,platform,sys
from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow as pa
pa.set_cpu_count(1);pa.set_io_thread_count(1)
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
sys.path.insert(0,str(ROOT/'hourly_stop_cost_20261008'))
import run_cost as prev
from run_cost import sha,write,PERIODS
from run_polling import load,contrast
from diagnostic_rule import FEATURES,KEYS,auc,stats,mask,nominate,path_anatomy
from entry_context import context,at_entries,verify_indicators
REF=ROOT/'hourly_stop_cost_20261008/results_v1'
PRIMARY=dict(poll_minutes=1,stress=2,cost_model='runtime_stop_fill')
MODELS=['research_all_exit_slip','runtime_stop_fill']
META=['poll_minutes','stress','cost_model','partition']

def primary(frame):
    q=frame
    for k,v in PRIMARY.items():q=q[q[k]==v]
    return q.copy()

def verify_reference(cache,runtime):
    f=json.loads((REF/'freeze.json').read_text());s=json.loads((REF/'status.json').read_text());assert s['status']=='complete'
    for group,root in [('sources',ROOT),('inputs',cache),('runtime_sources',runtime),('cached_references',ROOT)]:
        for n,h in f[group].items():assert sha(root/n)==h,n
    for n,h in s['output_hashes'].items():assert sha(REF/n)==h,n
    return f

def prepare(cache,runtime):
    out=HERE/'preflight_v1';out.mkdir(exist_ok=False);f=verify_reference(cache,runtime)
    raw=pd.read_parquet(REF/'all_opportunities.parquet',use_threads=False);signals=primary(raw)
    assert len(signals)==69 and not signals.duplicated(KEYS).any()
    btc,_=load(cache,'BTCUSDT','2026-10-02 16:00')
    btc24=btc.close.resample('h',closed='left',label='right').last().pct_change(24,fill_method=None);del btc
    features=[];checks=prefixes=0
    for symbol in ['BTCUSDT','ETHUSDT','SOLUSDT']:
        c,_=load(cache,symbol,'2026-10-02 16:00');records=signals[signals.symbol==symbol].copy()
        q=context(c);x=at_entries(q,records,btc24)
        checks+=verify_indicators(c,q,records)
        for cutoff in ['2025-01-01','2026-01-01']:
            cut=pd.Timestamp(cutoff,tz='UTC');prefix=context(c[c.index<cut])
            pd.testing.assert_frame_equal(prefix,q.loc[prefix.index],rtol=1e-11,atol=1e-11);prefixes+=1
        for col in ['prior_atr','volume_ratio','rsi14','filter_crsi','btc24','r24','efficiency24_before_signal','extension_atr']:
            assert np.allclose(x[col],records[col],atol=1e-8,rtol=1e-10),col
        assert (x.last_input_minute<x.index).all() and np.isfinite(x[list(FEATURES)]).all().all()
        g=records[KEYS+['entry']].reset_index(drop=True)
        for col in list(FEATURES)+['open','high','low','close','prior_atr','rsi14','filter_crsi','btc24','r24','last_input_minute']:
            g[col]=x[col].to_numpy()
        g['feature_asof']=g.entry;features.append(g)
        print('FEATURE_CONTEXT_VERIFIED',symbol,flush=True)
    full=pd.concat(features,ignore_index=True)
    assert not full.duplicated(KEYS).any()
    full.to_parquet(out/'entry_features.parquet',index=False);full.to_csv(out/'entry_features.csv',index=False)
    write(out/'VERIFICATION.json',dict(status='pass',raw_signals=len(full),independent_indicator_checks=checks,
          all_pinned_entry_features_match=True,causal_prefix_checks=prefixes,new_associations_scored=False,
          feature_sha256=sha(out/'entry_features.parquet')))

def freeze(cache,runtime,commit):
    f=verify_reference(cache,runtime);p=HERE/'preflight_v1';v=json.loads((p/'VERIFICATION.json').read_text())
    assert v['status']=='pass' and not v['new_associations_scored'];assert len(commit)==40
    out=HERE/'development_v1';out.mkdir(exist_ok=False)
    sources={str(p.relative_to(ROOT)):sha(p) for p in ROOT.rglob('*.py')}
    for n in ['PROTOCOL.md','NOVELTY_AUDIT.md','TEST_VERIFICATION.json','preflight_v1/VERIFICATION.json']:
        sources[str((HERE/n).relative_to(ROOT))]=sha(HERE/n)
    write(out/'freeze.json',dict(protocol_commit=commit,frozen_at=dt.datetime.now(dt.timezone.utc).isoformat(),
          sources=sources,inputs=f['inputs'],runtime_sources=f['runtime_sources'],
          features={str((p/'entry_features.parquet').relative_to(ROOT)):sha(p/'entry_features.parquet')},
          cached_references={str(p.relative_to(ROOT)):sha(p) for p in REF.iterdir() if p.is_file()},
          periods=PERIODS,entry_features=FEATURES,independent_holdout=False,
          packages=dict(python=platform.python_version(),numpy=np.__version__,pandas=pd.__version__,pyarrow=pa.__version__)))

def check_freeze(cache,runtime,out):
    f=json.loads((out/'freeze.json').read_text())
    for group,root in [('sources',ROOT),('inputs',cache),('runtime_sources',runtime),('features',ROOT),('cached_references',ROOT)]:
        for n,h in f[group].items():assert sha(root/n)==h,n
    return f

def evidence(historical_only=False):
    ledger=pd.read_parquet(REF/'pooled_ledger.parquet',use_threads=False)
    ledger=ledger[ledger.poll_minutes.isin([0,1])].copy()
    if historical_only:ledger=ledger[ledger.partition=='historical'].copy()
    features=pd.read_parquet(HERE/'preflight_v1/entry_features.parquet',use_threads=False)
    extra=[c for c in features if c not in ledger or c in KEYS]
    q=ledger.merge(features[extra],on=KEYS,validate='many_to_one')
    for col in FEATURES:assert np.isfinite(q[col]).all(),col
    return q

def profile(q,meta):
    output=[];wins=q.net_return>0
    for feature in FEATURES:
        x=q[feature];a=x[wins];b=x[~wins];matched_num=matched_den=0.
        for _,cell in q.groupby(['symbol','side']):
            good=cell.net_return>0;n=int(good.sum())*int((~good).sum())
            if n:matched_num+=auc(cell[feature],good)*n;matched_den+=n
        output.append(meta|dict(feature=feature,n=len(q),winners=int(wins.sum()),losers=int((~wins).sum()),
            winner_median=a.median(),loser_median=b.median(),winner_q25=a.quantile(.25),winner_q75=a.quantile(.75),
            loser_q25=b.quantile(.25),loser_q75=b.quantile(.75),auc=auc(x,wins),
            within_token_side_auc=matched_num/matched_den if matched_den else np.nan,within_token_side_pairs=matched_den))
    return output

def finish(out):
    write(out/'status.json',dict(status='complete',completed_at=dt.datetime.now(dt.timezone.utc).isoformat(),
          output_hashes={p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='status.json'}))

def develop(cache,runtime):
    out=HERE/'development_v1';check_freeze(cache,runtime,out);assert not (out/'status.json').exists()
    write(out/'status.json',dict(status='running'))
    q=primary(evidence(True));assert len(q)==41 and (q.partition=='historical').all()
    candidates,selection=nominate(q);candidates.to_csv(out/'historical_candidates.csv',index=False)
    pd.DataFrame(profile(q,dict(partition='historical'))).to_csv(out/'historical_features.csv',index=False)
    edges={f:dict(median=float(q[f].median()),q33=float(q[f].quantile(1/3)),q67=float(q[f].quantile(2/3))) for f in FEATURES}
    write(out/'bin_edges.json',edges);write(out/'selection.json',selection)
    write(out/'VERIFICATION.json',dict(status='pass',historical_rows=len(q),later_rows_scored=0,candidates=len(candidates)))
    finish(out);print(json.dumps(selection,indent=2),flush=True)

def group_summary(q):
    row=stats(q);stops=q[q.reason=='stop'];w=q[q.net_return>0]
    dates=q.entry.dt.floor('D');weeks=q.entry.dt.tz_localize(None).dt.to_period('W-SUN')
    lossweeks=(-stops.net_return).groupby(stops.entry.dt.tz_localize(None).dt.to_period('W-SUN')).sum()
    row.update(active_dates=int(dates.nunique()),active_weeks=int(weeks.nunique()),
        max_same_day_stops=int(stops.groupby(stops.entry.dt.floor('D')).size().max()) if len(stops) else 0,
        top3_loss_week_share=float(lossweeks.nlargest(3).sum()/lossweeks.sum()) if lossweeks.sum()>0 else np.nan,
        mean_without_largest_winner=float(q.drop(w.net_return.idxmax()).net_return.mean()) if len(w) and len(q)>1 else np.nan)
    return row

def diagnose(cache,runtime,selection_commit):
    dev=HERE/'development_v1';f=check_freeze(cache,runtime,dev)
    st=json.loads((dev/'status.json').read_text());assert st['status']=='complete'
    for n,h in st['output_hashes'].items():assert sha(dev/n)==h,n
    assert len(selection_commit)==40
    out=HERE/'results_v1';out.mkdir(exist_ok=False)
    f['selection_commit']=selection_commit;f['selection_sha256']=sha(dev/'selection.json')
    f['cached_references'].update({str(p.relative_to(ROOT)):sha(p) for p in dev.iterdir() if p.is_file()})
    f['frozen_at']=dt.datetime.now(dt.timezone.utc).isoformat();write(out/'freeze.json',f)
    write(out/'status.json',dict(status='running'))
    allrows=evidence();q=primary(allrows);assert len(allrows)==520 and len(q)==65
    sel=json.loads((dev/'selection.json').read_text());edges=json.loads((dev/'bin_edges.json').read_text())
    profiles=[];bins=[];summaries=[];subset=[];nominee_groups=[];clusters=[];overall=[]
    for values,g in allrows.groupby(META):
        meta=dict(zip(META,values));profiles+=profile(g,meta)
        summaries.append(meta|stats(g))
        for feature in FEATURES:
            cuts=[edges[feature]['q33'],edges[feature]['q67']]
            tags=np.searchsorted(cuts,g[feature],side='right')
            for b in [0,1,2]:bins.append(meta|dict(feature=feature,bin=b,q33=cuts[0],q67=cuts[1])|stats(g[tags==b]))
        if sel['status']=='nominated':
            keep=mask(g,sel['feature'],sel['threshold'],sel['direction']);a=g[keep];b=g[~keep]
            row=meta|dict(feature=sel['feature'],direction=sel['direction'],threshold=sel['threshold'])
            for name,frame in [('baseline',g),('retained',a),('excluded',b)]:
                row.update({name+'_'+k:v for k,v in stats(frame).items()})
            row['difference_vs_baseline']=a.net_return.mean()-g.net_return.mean()
            row['difference_vs_excluded']=a.net_return.mean()-b.net_return.mean()
            for label,other in [('baseline',g),('excluded',b)]:
                row.update({label+'_'+k:v for k,v in contrast(a,other,*PERIODS[meta['partition']]).items()})
            subset.append(row)
    for part,g in q.groupby('partition'):
        overall.append(dict(partition=part)|group_summary(g))
        for grouping in [['symbol'],['side'],['entry_year']]:
            z=g.assign(entry_year=g.entry.dt.year)
            for key,cell in z.groupby(grouping):
                key=key if isinstance(key,tuple) else (key,)
                meta=dict(partition=part,grouping='+'.join(grouping))|dict(zip(grouping,key))
                profiles+=profile(cell,meta|PRIMARY)
                nominee=mask(cell,sel['feature'],sel['threshold'],sel['direction']) if sel['status']=='nominated' else np.zeros(len(cell),bool)
                for name,frame in [('baseline',cell),('retained',cell[nominee]),('excluded',cell[~nominee])]:
                    nominee_groups.append(meta|dict(subset=name)|stats(frame))
        for grouping,labels in [('date',g.entry.dt.strftime('%Y-%m-%d')),('week',g.entry.dt.tz_localize(None).dt.to_period('W-SUN').astype(str)),('utc_6h_block',(g.entry.dt.hour//6).astype(str))]:
            for name,cell in g.groupby(labels):clusters.append(dict(partition=part,grouping=grouping,label=name)|stats(cell))
    anatomy=[];independent_paths=0
    for symbol in ['BTCUSDT','ETHUSDT','SOLUSDT']:
        c,_=load(cache,symbol,'2026-10-02 16:00');ctx=context(c)
        for r in q[q.symbol==symbol].itertuples():
            p=path_anatomy(c,r)
            held=c.loc[(c.index>=r.entry)&(c.index<r.exit_bar)]
            high=max([r.quote]+held.high.tolist());low=min([r.quote]+held.low.tolist())
            expected_mfe=max(0.,r.side*((high if r.side==1 else low)-r.entry_price)/r.entry_price)
            expected_mae=max(0.,-r.side*((low if r.side==1 else high)-r.entry_price)/r.entry_price)
            assert np.allclose([p['mfe'],p['mae']],[expected_mfe,expected_mae],atol=1e-12,rtol=0)
            at=r.exit_bar.floor('h');exit_context=ctx.loc[at];assert exit_context.last_input_minute<r.exit_bar
            row=r._asdict();row.pop('Index');row.update(p)
            row.update(exit_indicator_asof=at,exit_rsi14=float(exit_context.rsi14),
                       exit_crsi=float(exit_context.filter_crsi),exit_adx14=float(exit_context.adx14))
            anatomy.append(row);independent_paths+=1
    anatomy=pd.DataFrame(anatomy);anatomy.to_csv(out/'primary_trade_anatomy.csv',index=False)
    anatomy.to_parquet(out/'primary_trade_anatomy.parquet',index=False)
    anatomy_stats=[];excursions=[]
    for (part,outcome),g in anatomy.assign(outcome=np.where(anatomy.net_return>0,'winner','loser')).groupby(['partition','outcome']):
        row=dict(partition=part,outcome=outcome)|stats(g)
        for col in ['mfe','mae','holding_minutes','exit_rsi14','exit_crsi','exit_adx14']:
            for quantile,label in [(.25,'q25'),(.5,'median'),(.75,'q75')]:row[col+'_'+label]=g[col].quantile(quantile)
        anatomy_stats.append(row)
        for threshold in [.005,.01,.015,.02]:
            excursions.append(dict(partition=part,outcome=outcome,n=len(g),threshold=threshold,
                mfe_ge=int((g.mfe>=threshold).sum()),mae_ge=int((g.mae>=threshold).sum())))
    allrows.to_csv(out/'entry_outcome_evidence.csv',index=False);allrows.to_parquet(out/'entry_outcome_evidence.parquet',index=False)
    for name,rows in [('feature_profiles',profiles),('feature_bins',bins),('model_summaries',summaries),
        ('nominee_subsets',subset),('nominee_subgroups',nominee_groups),('calendar_clusters',clusters),
        ('primary_summary',overall),('path_summary',anatomy_stats),('excursion_counts',excursions)]:
        pd.DataFrame(rows).to_csv(out/(name+'.csv'),index=False)
    s=pd.DataFrame(subset)
    checks={}
    if len(s):
        z=primary(s)
        for r in z.itertuples():checks[r.partition]=bool(r.retained_n>0 and r.excluded_n>0 and r.retained_mean_net>0 and r.difference_vs_baseline>0)
    write(out/'decision.json',dict(historical_nominee=sel,primary_subset_point_screen=checks,
        later_periods_both_support=bool(checks.get('evaluation',False) and checks.get('reserved_replication',False)),
        filtered_portfolio_replayed=False,independent_edge_established=False,automatic_deployment=False))
    write(out/'VERIFICATION.json',dict(status='pass',raw_signals=69,unique_admitted=65,evidence_rows=len(allrows),
        independent_sampled_anatomy_rows=independent_paths,entry_features=12,nominee_fixed_before_later_tables=True,
        selection_sha256=sha(dev/'selection.json'),no_runtime_changes=True))
    finish(out);print(json.dumps(checks,indent=2),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['prepare','freeze','develop','diagnose']);p.add_argument('--cache',type=Path,required=True);p.add_argument('--runtime',type=Path,required=True);p.add_argument('--commit');a=p.parse_args()
    if a.command in ['freeze','diagnose']:globals()[a.command](a.cache,a.runtime,a.commit)
    else:globals()[a.command](a.cache,a.runtime)
