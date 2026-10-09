"""Reprice only stops in the already verified polling ledger."""
import argparse, datetime as dt, json, platform, sys
from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow as pa
pa.set_cpu_count(1); pa.set_io_thread_count(1)
HERE=Path(__file__).resolve().parent; ROOT=HERE.parent
sys.path.insert(0,str(ROOT/'hourly_exit_polling_20261008'))
from run_polling import sha,write,admit,replay,report_metrics,score,contrast,PERIODS,SYMBOLS,STOP
from cost_rule import reconcile_cost,MODELS,CHANGED,FEE
REF=ROOT/'hourly_exit_polling_20261008/results_v1'
KEYS=['poll_minutes','partition','stress','symbol','side','signal_i']

def verified_reference(cache,runtime):
    f=json.loads((REF/'freeze.json').read_text()); s=json.loads((REF/'status.json').read_text())
    assert s['status']=='complete'
    for group,root in [('sources',ROOT),('inputs',cache),('runtime_sources',runtime),('cached_references',ROOT)]:
        for n,h in f[group].items(): assert sha(root/n)==h,n
    for n,h in s['output_hashes'].items(): assert sha(REF/n)==h,n
    raw=pd.read_parquet(REF/'all_opportunities.parquet',use_threads=False)
    ledger=pd.read_parquet(REF/'pooled_ledger.parquet',use_threads=False)
    assert len(raw)==552 and len(ledger)==520
    assert not raw.duplicated(KEYS).any() and not ledger.duplicated(KEYS).any()
    return f,raw,ledger

def preflight(cache,runtime):
    out=HERE/'preflight_v1';out.mkdir(exist_ok=False)
    f,raw,ledger=verified_reference(cache,runtime)
    for q in [raw,ledger]:
        xp=q.quote*(1-q.side*q.slippage_per_side)
        assert np.allclose(xp,q.exit_price,atol=1e-12,rtol=0)
        expected=q.side*(xp/q.entry_price-1)-FEE*(1+xp/q.entry_price)-q.funding
        assert np.allclose(q.net_return,expected,atol=1e-12,rtol=0)
    v=dict(status='pass',reference_raw_rows=len(raw),reference_admitted_rows=len(ledger),
           reference_sources=len(f['sources']),runtime_sources=len(f['runtime_sources']),
           input_hashes=len(f['inputs']),treatment_scored=False)
    write(out/'VERIFICATION.json',v);print(json.dumps(v,indent=2))

def freeze(cache,runtime,commit):
    f,_,_=verified_reference(cache,runtime)
    assert json.loads((HERE/'preflight_v1/VERIFICATION.json').read_text())['treatment_scored'] is False
    assert len(commit)==40
    out=HERE/'results_v1';out.mkdir(exist_ok=False)
    sources={str(p.relative_to(ROOT)):sha(p) for p in ROOT.rglob('*.py')}
    for n in ['PROTOCOL.md','NOVELTY_AUDIT.md','TEST_VERIFICATION.json','preflight_v1/VERIFICATION.json']:
        sources[str((HERE/n).relative_to(ROOT))]=sha(HERE/n)
    refs={str(p.relative_to(ROOT)):sha(p) for p in REF.iterdir() if p.is_file()}
    write(out/'freeze.json',dict(frozen_at=dt.datetime.now(dt.timezone.utc).isoformat(),protocol_commit=commit,
          sources=sources,inputs=f['inputs'],runtime_sources=f['runtime_sources'],cached_references=refs,
          models=MODELS,primary_poll_minutes=1,polls_minutes=[0,1,5,15],periods=PERIODS,
          only_change='omit second adverse exit tick on stops; fee at revised exit notional',
          independent_holdout=False,packages=dict(python=platform.python_version(),numpy=np.__version__,pandas=pd.__version__,pyarrow=pa.__version__)))
    print('FROZEN',commit,flush=True)

def assert_invariants(a,b):
    stable=[c for c in a.columns if c not in CHANGED]
    pd.testing.assert_frame_equal(a[stable],b[stable],check_exact=True)
    pd.testing.assert_frame_equal(a.loc[a.reason!='stop'],b.loc[b.reason!='stop'],check_exact=True)
    for old,new in zip(a.itertuples(),b.itertuples()):
        # Cash calculation on one unit of the underlying, independently of ratio arithmetic.
        exit_fill=old.quote if old.reason=='stop' else old.exit_price
        cash_gross=(exit_fill-old.entry_price) if old.side==1 else (old.entry_price-exit_fill)
        cash_fees=FEE*old.entry_price+FEE*exit_fill
        cash_funding=old.funding*old.entry_price
        assert np.isclose(new.net_return,(cash_gross-cash_fees-cash_funding)/old.entry_price,atol=1e-12,rtol=0)
        expected_delta=(old.quote*old.slippage_per_side/old.entry_price*(1-FEE*old.side) if old.reason=='stop' else 0)
        assert np.isclose(new.net_return-old.net_return,expected_delta,atol=1e-12,rtol=0)

def run(cache,runtime):
    out=HERE/'results_v1';f=json.loads((out/'freeze.json').read_text())
    for group,root in [('sources',ROOT),('inputs',cache),('runtime_sources',runtime),('cached_references',ROOT)]:
        for n,h in f[group].items():assert sha(root/n)==h,n
    assert not (out/'status.json').exists(),'Preserve attempts'
    write(out/'status.json',dict(status='running',started_at=dt.datetime.now(dt.timezone.utc).isoformat()))
    try:
        _,raw,reference=verified_reference(cache,runtime)
        new=reconcile_cost(raw);assert_invariants(raw,new)
        opportunities=pd.concat([raw.assign(cost_model=MODELS[0]),new.assign(cost_model=MODELS[1])],ignore_index=True)
        ledgers=[];summaries=[];risk=[];subgroups=[];admissions=[];rejections=[]
        for (model,poll,part,stress),g in opportunities.groupby(['cost_model','poll_minutes','partition','stress'],sort=True):
            t,rej=admit(g);ids,counts=replay(g)
            assert ids==list(t[['symbol','tf','side','entry_i']].itertuples(index=False,name=None))
            assert counts==(rej.reason.value_counts().to_dict() if len(rej) else {})
            r=reference[(reference.poll_minutes==poll)&(reference.partition==part)&(reference.stress==stress)]
            aa=r.sort_values(KEYS).reset_index(drop=True);bb=t.sort_values(KEYS).reset_index(drop=True)
            pd.testing.assert_frame_equal(aa,bb[aa.columns],check_exact=True) if model==MODELS[0] else assert_invariants(aa,bb[aa.columns])
            meta=dict(cost_model=model,poll_minutes=int(poll),partition=part,stress=int(stress))
            ledgers.append(t);summaries.append(meta|dict(opportunities=len(g),rejected=len(rej))|report_metrics(t,STOP,*PERIODS[part]))
            admissions.append(meta|dict(raw=len(g),admitted=len(t),rejected=len(rej),identity_unchanged=True))
            if len(rej):rejections.append(rej.assign(**meta))
            stops=t[t.reason=='stop'];targets=t[t.reason=='target']
            risk.append(meta|dict(n=len(t),stops=len(stops),targets=len(targets),mean_stopped_net=stops.net_return.mean(),worst_stopped_net=stops.net_return.min(),worst_trade_net=t.net_return.min()))
            for group in [['symbol'],['side'],['symbol','side']]:
                for key,q in t.groupby(group):
                    key=key if isinstance(key,tuple) else (key,)
                    subgroups.append(meta|dict(grouping='+'.join(group))|dict(zip(group,key))|score(q,STOP))
        ledger=pd.concat(ledgers,ignore_index=True)
        cols=KEYS+['entry','exit_bar','reason','entry_price','exit_price','quote','gross_return','fees','funding','net_return','net_R']
        pairs=raw[cols].merge(new[cols],on=KEYS,suffixes=('_old','_reconciled'),validate='one_to_one')
        pairs['admitted']=pd.MultiIndex.from_frame(pairs[KEYS]).isin(pd.MultiIndex.from_frame(reference[KEYS]))
        for col in ['gross_return','fees','funding','net_return']:pairs['delta_'+col]=pairs[col+'_reconciled']-pairs[col+'_old']
        contrasts=[]
        for (poll,part,stress),g in ledger.groupby(['poll_minutes','partition','stress']):
            a=g[g.cost_model==MODELS[0]];b=g[g.cost_model==MODELS[1]]
            pd.testing.assert_frame_equal(a[KEYS].reset_index(drop=True),b[KEYS].reset_index(drop=True),check_exact=True)
            contrasts.append(dict(poll_minutes=int(poll),partition=part,stress=int(stress),n=len(a),stops=int((a.reason=='stop').sum()),targets=int((a.reason=='target').sum()),
                old_mean_net=a.net_return.mean(),reconciled_mean_net=b.net_return.mean(),difference_mean_net=b.net_return.mean()-a.net_return.mean(),
                difference_mean_gross=b.gross_return.mean()-a.gross_return.mean(),difference_mean_fees=b.fees.mean()-a.fees.mean(),difference_mean_funding=b.funding.mean()-a.funding.mean(),
                **contrast(b,a,*PERIODS[part])))
        opportunities.to_parquet(out/'all_opportunities.parquet',index=False)
        ledger.to_parquet(out/'pooled_ledger.parquet',index=False);ledger.to_csv(out/'individual_trades.csv',index=False)
        for name,rows in [('pooled_results',summaries),('contrasts',contrasts),('stop_risk',risk),('subgroups',subgroups),('admission_identity',admissions)]:pd.DataFrame(rows).to_csv(out/(name+'.csv'),index=False)
        pairs.to_csv(out/'paired_cost_changes.csv',index=False)
        pd.concat(rejections,ignore_index=True).to_csv(out/'rejections.csv',index=False)
        write(out/'VERIFICATION.json',dict(status='pass',reference_raw_rows=552,reference_admitted_rows=520,
              unique_signals=69,unique_admitted_per_scenario=65,raw_cost_rows=len(opportunities),ledger_rows=len(ledger),
              independent_cash_cost_checks=552,admission_replays=len(admissions),unchanged_paths=True,unchanged_nonstop_rows=True,
              no_new_tokens=True,no_runtime_changes=True))
        write(out/'decision.json',dict(accounting_reconciliation_pass=True,independent_edge_established=False,automatic_deployment=False,
              new_entry_gates_selected=False,expanded_token_protocol_amended=False,next='Entry-time winner/loser diagnostics on reconciled outcomes; preserve conservative comparison'))
        write(out/'status.json',dict(status='complete',completed_at=dt.datetime.now(dt.timezone.utc).isoformat(),output_hashes={p.name:sha(p) for p in out.iterdir() if p.is_file() and p.name!='status.json'}))
        print(pd.DataFrame(contrasts).to_string(index=False),flush=True)
    except Exception as exc:
        write(out/'status.json',dict(status='failed',error=repr(exc),failed_at=dt.datetime.now(dt.timezone.utc).isoformat()))
        raise

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['preflight','freeze','run']);p.add_argument('--cache',type=Path,required=True);p.add_argument('--runtime',type=Path,required=True);p.add_argument('--protocol-commit');a=p.parse_args()
    if a.command=='freeze':freeze(a.cache,a.runtime,a.protocol_commit)
    else:globals()[a.command](a.cache,a.runtime)
